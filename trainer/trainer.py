#!/usr/bin/env python3
"""A translation model trainer. It feeds marian different sets of datasets with different thresholds
for different stages of the training. Data is uncompressed and TSV formatted src\ttrg
"""
import os
import sys
import signal
import argparse
import random
import subprocess

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Union, Type, TextIO, cast
from tempfile import TemporaryFile
from itertools import islice

import yaml

def ignore_sigint():
    """Used as pre-exec hook for the trainer program as to ignore ctrl-c. We'll
    deal with ctrl-c in the python program, and then be very friendly about
    stopping the trainer.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

# Path to something that can shuffle data. Called with seed, output-path, input-files
# TODO: Ideally this also deduplicates the src side of the sentence pairs it shuffles ;)
PATH_TO_SHUFFLE = os.path.dirname(os.path.realpath(__file__)) + "/shuffle.py"

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

    def __post_init__(self):
        if self.name not in MODIFIERS:
            raise ValueError(f"no modifier named '{self.name}' is defined")


@dataclass(frozen=True)
class Curriculum:
    seed: int
    datasets: Dict[str,Dataset]
    stages: Dict[str,Stage]
    modifiers: List[Modifier]
    stages_order: List[str]

    def __post_init__(self):
        if len(self.stages) != len(frozenset(self.stages)):
            raise ValueError('stages can only occur once')

        if not (frozenset(self.stages) <= frozenset(self.stages.keys())):
            raise ValueError('each stage has to be defined')

    def next_stage(self, stage:Stage) -> Optional[Stage]:
        """Helper to get the next stage given the current stage."""
        index = self.stages_order.index(stage.name)
        if index + 1 < len(self.stages_order):
            return self.stages[self.stages_order[index + 1]]
        else:
            return None


@dataclass(frozen=True)
class EpochTrackerState:
    epoch: int
    line: int


@dataclass(frozen=True)
class TrainerState:
    stage: str
    random_state: Any # whatever the type is returned by random.getstate(), which I think is implementation specific.
    epoch_tracker_state: EpochTrackerState
    datasets: Dict[str,DatasetState]


class DatasetReader:
    """Repeats, shuffles and reads a dataset ad infinitum."""
    dataset: Dataset
    seed: int
    line: int
    epoch: int

    flip: bool
    tmpdir: Optional[str]

    _fh: Optional[TextIO] = None

    def __init__(self, dataset:Dataset, seed:int, flip:bool=False, tmpdir:Optional[str]=None):
        self.dataset = dataset
        self.seed = seed
        self.flip = flip
        self.tmpdir = tmpdir
        self.epoch = 0
        self.line = 0

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
        fh = TemporaryFile(mode='w+', encoding='utf-8', dir=self.tmpdir)

        # Shuffle data to the temporary file. Deduplicate on the src side
        # (different src can have same trg, but same src can never have
        # different trg).
        # TODO: but if we use the reversed system to do backtranslation, isn't
        # this a bad idea? That system might have learned a different
        # combination for the deduplicated pairs. Deduplicating on src and
        # target separately will work around that, but that sounds too
        # restrictive. To do that use `-u 1 -u 2` with shuffle.py.
        subprocess.check_call([PATH_TO_SHUFFLE,
            '--unique', str(2 if self.flip else 1),
            *(['--temporary-directory', self.tmpdir] if self.tmpdir else []),
            str(self.seed),
            f'/dev/fd/{fh.fileno()}',
            *self.dataset.files
        ], pass_fds=(fh.fileno(),))

        # Replace open file handle with this new file
        self._fh = cast(TextIO, fh) # TODO: Not sure why TemporaryFile is an IO[str] according to typing, but seems to implement TextIO.
        self._fh.seek(0)
        self.line = 0

    def __iter__(self):
        return self

    def __next__(self):
        just_opened = False
        if not self._fh or self._fh.closed:
            self._open() # TODO: do we want to do this lazy? Yes, restore()
                         # might be called twice right now and shuffling is
                         # expensive.
            just_opened = True

        assert self._fh is not None
        try:
            # Try to read the next line from our shuffled file
            line = self._fh.readline()
            if line == '':
                raise StopIteration
            self.line += 1

            # Flip source and target position
            if self.flip:
                line = '\t'.join(reversed(line.rstrip('\n').split('\t', maxsplit=1))) + '\n'

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


@dataclass(frozen=True)
class ShuffledFile:
    seed: int
    proc: subprocess.Popen
    file: TextIO


class AsyncDatasetReader(DatasetReader):
    _pending: Optional[ShuffledFile]

    def __init__(self, *args, **kwargs):
        self._pending = None
        super().__init__(*args, **kwargs)

    def _open_async(self, seed:int):
        # Open temporary file which will contain shuffled version of `cat self.files`
        fh = TemporaryFile(mode='w+', encoding='utf-8', dir=self.tmpdir)

        self._pending = ShuffledFile(
            seed=seed,
            file=cast(TextIO, fh),
            proc=subprocess.Popen([PATH_TO_SHUFFLE,
                '--unique', str(2 if self.flip else 1),
                *(['--temporary-directory', self.tmpdir] if self.tmpdir else []),
                str(seed),
                f'/dev/fd/{fh.fileno()}',
                *self.dataset.files
            ], pass_fds=(fh.fileno(),))
        )

    def _kill_async(self):
        if self._pending is not None:
            self._pending.proc.kill()
            self._pending.proc.wait()
            self._pending.file.close()

    def _open(self):
        # First shuffle
        if self._pending is None:
            self._open_async(self.seed)

        assert self._pending is not None
        assert self._pending.seed == self.seed
        self._pending.proc.wait()
        assert self._pending.proc.returncode == 0
        self._fh = self._pending.file
        self._fh.seek(0)
        self.line = 0

        # Start shuffling next
        self._open_async(self.seed + 1)

    def restore(self, state:DatasetState) -> 'AsyncDatasetReader':
        # Kill any advance work we did because it is likely wrong.
        self._kill_async()
        return cast('AsyncDatasetReader', super().restore(state))

    def close(self):
        self._kill_async()
        super().close()


class StateLoader:
    """Tool to read and write TrainerState objects to yaml. Uses unsafe yaml
    because `random.getstate()` basically returns a blob, and it is very
    particular about the data types of that structure. So we use the yaml loader
    that encodes the python data type as well (i.e. tuple vs list).
    """
    def load(self, fh:TextIO) -> TrainerState:
        ymldata = yaml.load(fh, Loader=yaml.Loader)
        if not isinstance(ymldata, dict):
            raise ValueError(f'Empty state file: {fh.name}')
        return TrainerState(
            stage=ymldata['stage'],
            random_state=ymldata['random_state'],
            epoch_tracker_state=ymldata['epoch_tracker_state'],
            datasets={
                dataset_name: DatasetState(int(seed), int(line), int(epoch))
                for dataset_name, [seed, line, epoch] in ymldata['datasets'].items()
            }
        )

    def dump(self, state:TrainerState, fh:TextIO) -> None:
        yaml.dump({
            'stage': state.stage,
            'random_state': state.random_state,
            'epoch_tracker_state': state.epoch_tracker_state,
            'datasets': {
                dataset_name: [state.seed, state.line, state.epoch] #TODO: why a tuple, why not a dict? Isn't a dict more forward compatible?
                for dataset_name, state in state.datasets.items()
            }
        }, fh, allow_unicode=True, sort_keys=False) #TODO: is safe_dump not sufficient?


class CurriculumV1Loader:
    def load(self, ymldata:dict, *, basepath:str='./') -> Curriculum:
        datasets = self._load_datasets(ymldata, basepath)
        stages_order = self._load_stage_order(ymldata)
        return Curriculum(
            seed=int(ymldata['seed']),
            datasets=datasets,
            stages_order=stages_order,
            stages=self._load_stages(ymldata, stages_order, datasets),
            modifiers=self._load_modifiers(ymldata)
        )

    def _load_datasets(self, ymldata:dict, basepath:str) -> Dict[str,Dataset]:
        """Reads
        ```yaml
        datasets:
          - path/to/clean
          - path/to/dirty
        ```
        """
        return {
            os.path.basename(filepath): Dataset(os.path.basename(filepath), [os.path.join(basepath, filepath)])
            for filepath in ymldata['datasets']
        }

    def _load_stage_order(self, ymldata:dict) -> List[str]:
        """Reads
        ```yaml
        stages:
          - stage1
          - stage2
        ```
        """
        return list(ymldata['stages'])

    def _load_stages(self, ymldata:dict, stages_order:List[str], datasets:Dict[str,Dataset]) -> Dict[str,Stage]:
        """Reads:
        ```yaml
        stagename:
          - dataset1 frac
          - dataset2 frac
          - until dataset3 epochs
        ```
        """
        return {
            stage_name: self._load_stage(ymldata, stage_name, datasets, int(ymldata['seed']))
            for stage_name in stages_order
        }

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
            until_epoch=int(max_epochs) if max_epochs != 'inf' else None
        )

    def _load_modifiers(self, ymldata:dict) -> List[Modifier]:
        """Reads
        ```yml
        uppercase: 0.05
        titlecase: 0.05
        ```
        """
        return [
            Modifier(name, float(ymldata[name]))
            for name in MODIFIERS.keys()
            if name in ymldata
        ]


class CurriculumV2Loader(CurriculumV1Loader):
    """Slightly different curriculum format that can have multiple files per
    dataset, and puts the modifiers in their own section."""

    def _load_datasets(self, ymldata:dict, basepath:str) -> Dict[str,Dataset]:
        """Reads
        ```yml
        datasets:
          clean:
            - a.gz
            - b.gz
        ```
        """
        return {
            name: Dataset(name, [
                os.path.join(basepath, filepath)
                for filepath in files
            ])
            for name, files in ymldata['datasets']
        }

    def _load_modifiers(self, ymldata:dict) -> List[Modifier]:
        """Reads
        ```yml
        modifiers:
          - uppercase 0.05
          - titlecase 0.05
        ```
        """
        return [
            self._load_modifier(modifier_line)
            for modifier_line in ymldata.get('modifiers', [])
        ]

    def _load_modifier(self, line:str) -> Modifier:
        name, frequency = line.split()
        return Modifier(name, float(frequency))


class CurriculumLoader:
    """Reads curriculum yaml files. Wrapper that decides which reader to use
    based on a version number that may be in there.
    """

    IMPLEMENTATIONS={
        '1': CurriculumV1Loader,
        '2': CurriculumV2Loader,
    }

    def load(self, fh:Union[TextIO,str,dict], **kwargs) -> Curriculum:
        if isinstance(fh, dict):
            ymldata = fh
        else:
            ymldata = yaml.safe_load(fh)

        impl = self.IMPLEMENTATIONS[str(ymldata.get('version', '1'))]()
        return impl.load(ymldata, **kwargs)


class EpochTracker:
    """Utility to track how many epochs the reader has progressed since the
    tracker started tracking."""
    def __init__(self, reader:DatasetReader):
        self.reader = reader
        self.epoch_offset = reader.epoch
        self.line_offset = reader.line

    @property
    def epoch(self):
        epoch = self.reader.epoch - self.epoch_offset

        # ... but if the reader is behind on where it was, it hasn't completed
        # a full epoch yet.
        if self.reader.line < self.line_offset:
            epoch -= 1
        return epoch

    def restore(self, state:EpochTrackerState) -> 'EpochTracker':
        self.epoch_offset = state.epoch
        self.line_offset = state.line
        return self

    def state(self) -> EpochTrackerState:
        return EpochTrackerState(self.epoch_offset, self.line_offset)


class Trainer:
    """Writes lines to a trainer program according to the curriculum."""
    curriculum: Curriculum
    readers: Dict[str, DatasetReader]
    stage: Optional[Stage]
    epoch_tracker: EpochTracker

    # Whether to reverse src/trg pairs
    flip:bool

    # Path to write temporary shuffled files to
    tmpdir:Optional[str]

    # Reader class to use (I.e. DatasetReader or AsyncDatasetReader)
    _reader_impl: Type[DatasetReader]

    def __init__(self, curriculum:Curriculum, *, reader:Type[DatasetReader] = DatasetReader, flip:bool = False, tmpdir:Optional[str]=None):
        self.curriculum = curriculum
        self.flip = flip
        self.tmpdir = tmpdir
        self._reader_impl = reader
        random.seed(self.curriculum.seed)
        first_stage_name = self.curriculum.stages_order[0]

        #TODO: make sure this doesn't do too much work in case we call
        # restore() manually anyway.
        self.restore(TrainerState(
            stage=first_stage_name,
            random_state=random.getstate(),
            epoch_tracker_state=EpochTrackerState(0, 0),
            datasets={
                dataset.name: DatasetState(seed=curriculum.seed, line=0, epoch=0)
                for dataset in curriculum.datasets.values()
            }
        ))

    def restore(self, state:TrainerState):
        random.setstate(state.random_state)
        self.stage = self.curriculum.stages[state.stage]
        self.readers = {
            dataset.name: self._reader_impl(dataset, self.curriculum.seed, flip=self.flip, tmpdir=self.tmpdir).restore(state.datasets[dataset.name])
            for dataset in self.curriculum.datasets.values()
        }
        self.epoch_tracker = EpochTracker(self.readers[self.stage.until_dataset]).restore(state.epoch_tracker_state)

    def state(self) -> TrainerState:
        return TrainerState(
            stage=self.stage.name if self.stage is not None else '',
            random_state=random.getstate(),
            epoch_tracker_state=self.epoch_tracker.state(),
            datasets={
                name: reader.state()
                for name, reader in self.readers.items()
            }
        )

    def close(self):
        for reader in self.readers.values():
            reader.close()
        self.readers = {}

    def run(self, *, batch_size=100):
        while self.stage is not None:
            while self.stage.until_epoch is not None and self.epoch_tracker.epoch < self.stage.until_epoch:
                batch: List[str] = []

                # Read from each dataset according to its weight in this stage
                # (They will reshuffle and repeat if necessary)
                for dataset, weight in self.stage.datasets:
                    batch.extend(islice(self.readers[dataset.name], 0, int(batch_size * weight)))

                # Apply any modifiers to random lines in the batch
                # (Multiple modifiers could be applied to the same line!)
                # TODO: maybe make this self.stage.modifiers? Would that make sense?
                for modifier in self.curriculum.modifiers:
                    modifier_fun = MODIFIERS[modifier.name]
                    batch = [modifier_fun(line.rstrip('\n')) + '\n' if modifier.frequency > random.random() else line for line in batch]

                random.shuffle(batch)

                # Tell anyone whose listening that something interesting happened
                # TODO: Yield something useful, e.g. progress.
                yield batch

            # Move onto next stage. May be `None`, which would end this generator 🎉
            self.stage = self.curriculum.next_stage(self.stage)
            if self.stage:
                self.epoch_tracker = EpochTracker(self.readers[self.stage.until_dataset])

class StateTracker:
    """Wraps around the trainer.run() call to restore and dump state its."""
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
                yield batch
        finally:
            # Dump on clean exit as well as on exception.
            self._dump(trainer)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Feeds marian tsv data for training.")
    parser.add_argument("--config", '-c', required=True, type=str, help='YML configuration input.')
    parser.add_argument("--state", '-s', type=str, help='YML state file, defaults to ${CONFIG}.state.')
    parser.add_argument("--sync", action="store_true", help="Do not shuffle async")
    parser.add_argument("--temporary-directory", '-T', default=None, type=str, help='Temporary dir, used for shuffling and tracking state')
    parser.add_argument("--do-not-resume", '-d', action="store_true", help='Do not resume from the previous training state')
    parser.add_argument("--flip", action="store_true", help="Flip source and target sides of sentence pairs.")
    parser.add_argument("trainer", type=str, nargs="*", help="Trainer program that gets fed the input. If empty it is read from config.")
    
    args = parser.parse_args()

    with open(args.config, 'r', encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    curriculum = CurriculumLoader().load(config, basepath=os.path.dirname(args.config))

    trainer = Trainer(curriculum, reader=DatasetReader if args.sync else AsyncDatasetReader, flip=args.flip, tmpdir=args.temporary_directory)

    state_harness = StateTracker(args.state or f'{args.config}.state')

    # Disable resume functionality if we don't want it.
    if args.do_not_resume:
        state_harness._restore = lambda trainer: None

    model_trainer = subprocess.Popen(
        args.trainer or config['trainer'],
        stdin=subprocess.PIPE,
        encoding="utf-8",
        preexec_fn=ignore_sigint) # ignore_sigint makes marian ignore Ctrl-C. We'll stop it from here.
    
    assert model_trainer.stdin is not None

    try:
        for batch in state_harness.run(trainer):
            model_trainer.stdin.writelines(batch)
    finally:
        model_trainer.stdin.close()
        model_trainer.wait()
