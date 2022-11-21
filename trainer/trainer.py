#!/usr/bin/env python3
'''A translation model trainer. It feeds marian different sets of datasets with different thresholds
for different stages of the training. Data is uncompressed and TSV formatted src\ttrg'''
import os
import sys
import signal
import argparse
import random
import subprocess

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Union, TextIO, cast
from tempfile import TemporaryFile
from itertools import islice

import yaml

def ignore_sigint():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Feeds marian tsv data for training.")
    parser.add_argument("--config", '-c', required=True, type=str, help='YML configuration input.')
    parser.add_argument("--state", '-s', type=str, help='YML state file, defaults to ${CONFIG}.state.')
    # parser.add_argument("--temporary-dir", '-t', default="./TMP", type=str, help='Temporary dir, used for shuffling and tracking state')
    parser.add_argument("--do-not-resume", '-d', action="store_true", help='Do not resume from the previous training state')
    return parser.parse_args()

# Path to something that can shuffle data. Called with seed, output-path, input-files
# Ideally this also deduplicates the src side of the sentence pairs it shuffles ;)
PATH_TO_SHUFFLE = os.path.dirname(os.path.realpath(__file__)) + "/random.sh"

# Available batch modifiers
MODIFIERS = {
    'uppercase': lambda line: line.upper(),
    'titlecase': lambda line: ' '.join([word[0].upper() + word[1:] for word in line.split()]),
}


@dataclass(frozen=True)
class Dataset:
    name: str
    files: List[str]

    
@dataclass(frozen=True)
class DatasetState:
    seed: int
    line: int
    epoch: int


@dataclass(frozen=True)
class Stage:
    name: str
    datasets: List[Tuple[Dataset, float]]
    until_dataset: str
    until_epoch: Optional[int]


@dataclass(frozen=True)
class Modifier:
    name: str
    frequency: float


@dataclass(frozen=True)
class Curriculum:
    seed: int
    datasets: Dict[str,Dataset]
    stages: Dict[str,Stage]
    modifiers: List[Modifier]
    stages_order: List[str]

    def next_stage(self, stage:Stage) -> Optional[Stage]:
        index = self.stages_order.index(stage.name)
        if index + 1 < len(self.stages_order):
            return self.stages[self.stages_order[index + 1]]
        else:
            return None


@dataclass(frozen=True)
class TrainerState:
    stage: str
    random_state: Any
    datasets: Dict[str,DatasetState]


class DatasetReader:
    dataset: Dataset
    seed: int
    line: int
    epoch: int

    _fh: Optional[TextIO] = None

    def __init__(self, dataset:Dataset, seed:int):
        self.dataset = dataset
        self.seed = seed
        self.epoch = 0

    def state(self) -> DatasetState:
        return DatasetState(self.seed, self.line, self.epoch)

    def restore(self, state:DatasetState) -> 'DatasetReader':
        if self._fh:
            self._fh.close()

        self.seed = state.seed
        self.epoch = state.epoch
        
        # Skip forward
        for _ in range(state.line):
            next(self)

        return self

    def close(self):
        if self._fh:
            self._fh.close()

    def _open(self):
        # Open temporary file which will contain shuffled version of `cat self.files`
        fh = TemporaryFile(mode='w+', encoding='utf-8')

        # Shuffle data to the temporary file
        subprocess.check_call([PATH_TO_SHUFFLE, str(self.seed), str(fh.fileno()), *self.dataset.files], pass_fds=(fh,))

        # Replace open file handle with this new file
        self._fh = cast(TextIO, fh) # TODO: Not sure why TemporaryFile is an IO[str]
        self.line = 0

    def __iter__(self):
        return self

    def __next__(self):
        just_opened = False
        if not self._fh:
            just_opened = True
            self._open() # TODO: do we want to do this lazy? Yes, restore()
                         # might be called twice right now and shuffling is
                         # expensive.

        assert self._fh is not None
        try:
            # Try to read the next line from our shuffled file
            line = next(self._fh)
            self.line += 1
            return line
        except StopIteration:
            if just_opened:
                raise RuntimeError('reading from empty shuffled file')

            # Oh no we're out of lines! Close file, and move on to the next epoch
            self._fh.close()
            self.seed += 1
            self.epoch += 1

            # Now try again (will trigger the lazy open + just_opened protection)
            return next(self)
                


class StateLoader:
    def load(self, fh:TextIO) -> TrainerState:
        ymldata = yaml.safe_load(fh)
        return TrainerState(
            stage=ymldata['stage'],
            random_state=ymldata['random_state'],
            datasets={
                dataset_name: DatasetState(int(seed), int(line), int(epoch))
                for dataset_name, [seed, line, epoch] in ymldata['datasets'].items()
            }
        )

    def dump(self, state:TrainerState, fh:TextIO) -> None:
        yaml.safe_dump({
            'stage': state.stage,
            'random_state': state.random_state,
            'datasets': {
                dataset_name: [state.seed, state.line, state.epoch] #TODO: why a tuple, why not a dict? Isn't a dict more forward compatible?
                for dataset_name, state in state.datasets.items()
            }
        }, fh, allow_unicode=True, sort_keys=False) #TODO: is safe_dump not sufficient?


class CurriculumLoader:
    def load(self, fh:Union[TextIO,str,dict]) -> Curriculum:
        if isinstance(fh, dict):
            ymldata = fh
        else:
            ymldata = yaml.safe_load(fh)

        seed = int(ymldata['random_seed'])

        datasets = {
            name: Dataset(name, files)
            for name, files in ymldata['datasets']
        }

        stages_order = list(ymldata['stages'])

        return Curriculum(
            seed=seed,
            datasets=datasets,
            stages_order=stages_order,
            stages={
                stage_name: self._load_stage(ymldata, stage_name, datasets, seed)
                for stage_name in stages_order
            },
            modifiers=[
                self._load_modifier(modifier_line)
                for modifier_line in ymldata.get('modifiers', [])
            ]
        )

    def _load_stage(self, ymldata:dict, stage_name:str, available_datasets:Dict[str,Dataset], seed:int) -> Stage:
        datasets: List[Tuple[Dataset, float]] = []

        for line in ymldata[stage_name][:-1]:
            dataset_name, weight = line.split()
            datasets.append((available_datasets[dataset_name], float(weight)))

        _, dataset_name, max_epochs = ymldata[stage_name][-1].split()
        assert dataset_name in available_datasets, f"until clause of stage '{stage_name}' refers to unknown dataset '{dataset_name}'"
        assert dataset_name in {dataset.name for dataset, weight in datasets if weight > 0.0}, f"until clause of stage '{stage_name}' watches dataset '{dataset_name}' but that dataset is not read during this stage"
        return Stage(
            name=stage_name,
            datasets=datasets,
            until_dataset=dataset_name,
            until_epoch=int(max_epochs) if max_epochs is not 'inf' else None
        )

    def _load_modifier(self, line:str) -> Modifier:
        name, frequency = line.split()
        assert name in MODIFIERS, f"unknown modifier named '{name}'"
        return Modifier(name, float(frequency))


class Trainer:
    curriculum: Curriculum
    stage: Optional[Stage]
    readers: Dict[str, DatasetReader]
    trainer: subprocess.Popen

    _slice_size = 100

    '''This class takes in the config file and starts running training'''
    def __init__(self, curriculum:Curriculum):
        self.curriculum = curriculum
        random.seed(self.curriculum.seed)
        first_stage_name = self.curriculum.stages_order[0]
        first_stage = self.curriculum.stages[first_stage_name]

        #TODO: make sure this doesn't do too much work in case we call
        # restore() manually anyway.
        self.restore(TrainerState(
            stage=first_stage_name,
            random_state=random.getstate(),
            datasets={
                dataset.name: DatasetState(seed=curriculum.seed, line=0, epoch=0)
                for dataset, _ in first_stage.datasets
            }
        ))

    def restore(self, state:TrainerState):
        random.setstate(state.random_state)
        self.stage = self.curriculum.stages[state.stage]
        self.readers = {
            dataset_name: reader.restore(state.datasets[dataset_name])
            for dataset_name, reader in self._create_readers(self.stage).items()
        }

    def _create_readers(self, stage:Stage) -> Dict[str,DatasetReader]:
        return {
            dataset.name: DatasetReader(dataset, self.curriculum.seed)
            for dataset, _ in stage.datasets
        }

    def state(self) -> TrainerState:
        return TrainerState(
            stage=self.stage.name if self.stage is not None else '',
            random_state=random.getstate(),
            datasets={
                name: reader.state()
                for name, reader in self.readers.items()
            }
        )

    def run(self, config:Dict[str,Any]):
        # Initialise the trainer, using Subprocess.Popen
        self.trainer = subprocess.Popen(
            config['trainer'],
            stdin=subprocess.PIPE,
            encoding="utf-8",
            preexec_fn=ignore_sigint) # ignore_sigint makes marian ignore Ctrl-C. We'll stop it from here.

        # Stop type checker from complaining that stdin may be None anyway
        assert self.trainer.stdin is not None

        try:
            while self.stage is not None:
                # Quick access to the reader that determines whether we have
                # read it enough times for this stage to finish and move onto
                # the next.
                until_reader = self.readers[self.stage.until_dataset]

                while self.stage.until_epoch is not None and until_reader.epoch < self.stage.until_epoch:
                    batch: List[str] = []

                    # Read from each dataset according to its weight in this stage
                    # (They will reshuffle and repeat if necessary)
                    for dataset, weight in self.stage.datasets:
                        batch.extend(islice(self.readers[dataset.name], 0, int(self._slice_size * weight)))

                    # Apply any modifiers to random lines in the batch
                    # (Multiple modifiers could be applied to the same line!)
                    # TODO: maybe make this self.stage.modifiers? Would that make sense?
                    for modifier in self.curriculum.modifiers:
                        modifier_fun = MODIFIERS[modifier.name]
                        batch = [modifier_fun(line) for line in batch if modifier.frequency > random.random()]

                    random.shuffle(batch)

                    # Pass batch to trainer. Might block on writing it. Uses default
                    # buffer size, and most likely the trainer will read it async
                    # from training anyway.
                    self.trainer.stdin.writelines(batch)

                    # Tell anyone whose listening that something interesting happend
                    # TODO: Yield something useful, e.g. progress.
                    yield None

                # Move onto next stage. May be `None`, which would end this generator 🎉
                self.stage = self.curriculum.next_stage(self.stage)
                self.readers = self._create_readers(self.stage) if self.stage is not None else {}
        finally:
            # Whatever you do, clean up the trainer.
            self.trainer.stdin.close()
            self.trainer.wait()


class StateTracker:
    path: str
    loader: StateLoader

    def __init__(self, path:str, *, loader:StateLoader=StateLoader()):
        self.path = path
        self.loader = loader

    def _restore(self, trainer:Trainer):
        with open(self.path, 'r', encoding='utf-8') as fh:
            return trainer.restore(self.loader.load(fh))

    def _dump(self, trainer:Trainer):
        with open(self.path, 'w', encoding='utf-8') as fh:
            return self.loader.dump(trainer.state(), fh)

    def run(self, trainer:Trainer, *args, **kwargs):
        if os.path.exists(self.path):
            self._restore(trainer)

        try:
            for batch in trainer.run(*args, **kwargs):
                self._dump(trainer)
                yield batch
        finally:
            # Dump on clean exit as well as exception.
            self._dump(trainer)


if __name__ == '__main__':
    args = parse_user_args()

    with open(args.config, 'r', encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    curriculum = CurriculumLoader().load(config)

    trainer = Trainer(curriculum)

    state_harness = StateTracker(args.state or f'{args.config}.state')

    # Disable resume functionality if we don't want it.
    if args.do_not_resume:
        state_harness._restore = lambda trainer: None

    # Run trainer as a generator. Ideally we get some stats back about
    # the batch we just pushed to it, but since marian is probably reading and
    # training in separate threads, I'm doubtful about how useful this is.
    for _ in state_harness.run(trainer, config):
        pass
