#!/usr/bin/env python3
'''A translation model trainer. It feeds marian different sets of datasets with different thresholds
for different stages of the training. Data is uncompressed and TSV formatted src\ttrg'''
import os
import argparse
import weakref
import random
from sys import stderr
from dataclasses import dataclass
from subprocess import check_call, CalledProcessError
from collections import namedtuple
from typing import List, Type, Tuple, Dict
from math import inf

import json
import yaml
from yaml.loader import SafeLoader

import pexpect

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Feeds marian tsv data for training.")
    parser.add_argument("--config", '-c', required=True, type=str, help='YML configuration input.')
    parser.add_argument("--temporary-dir", '-t', default="./TMP", type=str, help='Temporary dir, used for shuffling and tracking state')
    parser.add_argument("--resume", '-r', default=True, type=bool, help='Resume from the previous training state')
    return parser.parse_args()

Stage = namedtuple('Stage', ['datasets', 'until_dataset', 'until_epoch'])

DatasetState = namedtuple('DatasetState', ['seed', 'line', 'epoch'])

@dataclass
class StateTracker:
    '''The purpose of this class is to store an yml of every single state during training'''
    def __init__(self, ymlpath, restore=True):
        '''Tries to load the state from previous yml, else just writes a new yml. If restore==False
           it always overwrites the previous input'''
        self.ymlpath = ymlpath
        self.stage: str = None
        self.datasetStates: Dict['str', DatasetState] = {}
        self.random_state = None
        if restore and os.path.isfile(self.ymlpath) and os.access(self.ymlpath, os.R_OK):
            with open(self.ymlpath, 'rt', encoding="utf-8") as myfile:
                ymldata = list(yaml.load_all(myfile, Loader=SafeLoader))[0]
                self.stage = ymldata['stage']
                datasets: dict = ymldata['datasets']
                for dataset in datasets:
                    name = dataset
                    seed = int(datasets[dataset][0])
                    line = int(dataset[dataset][1])
                    epoch = int(dataset[dataset][2])
                    self.datasetStates[name] = DatasetState(seed, line, epoch)
                # Restore random state
                self.random_state = ymldata['random_state']
                random.setstate(self.random_state)

    def _dump_(self) -> None:
        '''Dumps the current state to yml.
        This should only be called when there is a model save detected'''
        with open(self.ymlpath, 'w', encoding="utf-8") as ymlout:
            output = {}
            output['stage'] = self.stage
            output['datasets'] = {}
            for dataset, state in self.datasetStates.items():
                seed = state.seed
                line = state.line
                epoch = state.epoch
                output['datasets'][dataset] = [seed, line, epoch]
            yaml.dump(output, ymlout, allow_unicode=True)

    def update_stage(self, newstage: str) -> None:
        '''Update the training stage'''
        self.stage = newstage
        self.random_state = random.getstate()

    def update_dataset(self, dataset_name: str, dataset_state: DatasetState) -> None:
        '''Updates the state of the current dataset'''
        self.datasetStates[dataset_name] = dataset_state




@dataclass
class Executor:
    '''This class takes in the config file and starts running training'''
    def __init__(self, ymlpath: str, tmpdir: str):
        ymldata = None
        with open(ymlpath, 'rt', encoding="utf-8") as myfile:
            ymldata = list(yaml.load_all(myfile, Loader=SafeLoader))[0]
        self.dataset_paths = ymldata['datasets']
        self.dataset_names = [x.split('/')[-1] for x in self.dataset_paths]
        # Correlate dataset path with dataset name:
        tmpdict = {}
        for path in self.dataset_paths:
            tmpdict[path.split('/')[-1]] = path
        self.dataset_paths = tmpdict
        self.stage_names = ymldata['stages']
        self.uppercase_ratio = float(ymldata['uppercase'])
        self.random_seed = int(ymldata['seed'])
        self.trainer = pexpect.spawn(ymldata['trainer'])
        self.trainer.delaybeforesend = None
        # Parse the individual training stages into convenient struct:
        self.stages = {}
        self.dataset_objects = {}

        # Set random seed
        random.seed(self.random_seed)

        for stage in self.stage_names:
            stageparse: List[str] = ymldata[stage]
            # We only want the first N - 1 as the last one describes the finishing condition
            stagesdict = {}
            for i in range(len(stageparse) -1):
                stagename, weight = stageparse[i].split()
                weight = float(weight)
                stagesdict[stagename] = weight

            _, until_stagename, termination_epoch = stageparse[-1].split()
            mystage = Stage(stagesdict, until_stagename, float(termination_epoch))
            self.stages[stage] = mystage

        # Initialise the dataset filestreams. For now just do identity initialisation, do more later.
        for dataset in self.dataset_names:
            self.dataset_objects[dataset] = Dataset(self.dataset_paths[dataset], tmpdir, self.random_seed, 0.1, inf)

        # Start training
        for stage in self.stage_names:
            print(stage)
            self.__init__stage_(self.stages[stage])
            self.train_stage(self.stages[stage])


    def __init__stage_(self, stage): #@TODO make the stupid stage a full object so i can have proper attributes
        '''Init a certain stage of the training'''
        for dataset in stage.datasets.keys():
            self.dataset_objects[dataset].set_weight(stage.datasets[dataset])
            self.dataset_objects[dataset].set_max_epoch(inf)
            self.dataset_objects[dataset].reset_epoch()
        self.dataset_objects[stage.until_dataset].set_max_epoch(stage.until_epoch)

    def train_stage(self, stage):
        '''Trains up to a training stage'''
        stop_training = False
        while not stop_training:
            batch = []
            for dataset in stage.datasets:
                epoch, lines = self.dataset_objects[dataset].get()
                #print(epoch, dataset, stage.until_dataset, stage.until_epoch, len(lines))
                batch.extend(lines)
                if dataset == stage.until_dataset and epoch >= stage.until_epoch:
                    stop_training = True
            # Shuffle the batch
            random.shuffle(batch)
            # Uppercase randomly
            batch =  [x.upper() if random.random() < self.uppercase_ratio else x for x in batch]
            self.trainer.writelines(batch)


@dataclass
class Dataset:
    '''This class takes care of iterating through a dataset. It takes care of shuffling and
    remembering the position of the dataset'''
    def __init__(self, datapath: str, tmpdir: str, seed: int, weight: float, max_epoch: int):
        # Create the temporary directory if it doesn't exist
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        # Vars
        self.orig = datapath
        self.filename: str = datapath.split('/')[-1]
        self.tmpdir = tmpdir
        self.seed = seed
        self.linenum = 0 # line number of the current file
        self.shufffile = self.tmpdir + "/" + self.filename + ".shuf"
        self.weight = weight
        # filehandle
        self.filehandle = None
        # dataset epoch
        self.epoch = 0
        self.max_epoch = max_epoch

        self.rng_filepath = str(os.path.dirname(os.path.realpath(__file__))) + "/random.sh" # HACKY

        # shuffle the initial file
        self._shuffle_(self.orig, self.shufffile)
        # Open the current file for reading
        self._openfile_(self.shufffile)

        # On object destruction, cleanup
        self._finalizer = weakref.finalize(self, self._cleanup_, self.filehandle)

    def set_weight(self, neweight):
        '''Used for when we want to switch the sampling strategy based on our schedule'''
        self.weight = neweight

    def set_max_epoch(self, new_max_epoch):
        '''Used for when we want to switch the sampling strategy based on our schedule'''
        self.max_epoch = new_max_epoch

    def reset_epoch(self):
        '''Used to reset the training epoch of the file, so that training can continue
        from the same shuffling point without eextra fluff'''
        self.epoch = 0

    def _ammend_seed_(self, newseed=None):
        '''Either adds one to the current random seed, or sets a new one completely'''
        if newseed is None:
            newseed = self.seed + 1
        self.seed = newseed

    def _shuffle_(self, inputfile, outputfile):
        try:
            #print(self.rng, outputfile, inputfile)
            check_call([self.rng_filepath, str(self.seed), outputfile, inputfile])
            #check_call(["/usr/bin/shuf", "-o", outputfile, inputfile])
        except CalledProcessError as err:
            print("Error shuffling", inputfile, file=stderr)
            print(err.cmd, file=stderr)
            print(err.stderr, file=stderr)

    def _openfile_(self, filepath):
        self.filehandle = open(filepath, 'rt', encoding="utf-8")

    def save(self, filepath):
        """Saves the current dataset training state to the disk"""
        with open(filepath, 'w', encoding="utf-8") as myfilehandle:
            json.dump(self, myfilehandle)

    @staticmethod
    def load(filepath) -> Type['Dataset']:
        """Loads a dataset object from json, also setting back the state"""
        my_dataset: Type['Dataset'] = json.load(filepath)
        my_dataset._set_seed_(my_dataset.seed)
        my_dataset._shuffle_(my_dataset.orig, my_dataset.shufffile)
        my_dataset._openfile_(my_dataset.shufffile)
        # @TODO rewind the file to the proper location
        return my_dataset

    def get(self) -> Tuple[int, List[str]]:
        '''Gets the next N lines based on the weight of the dataset. It also reports which
        epoch it is.
        When the dataset reaches its end, it automatically takes care of wrapping it'''
        myepoch = self.epoch
        retlist: List[str] = []
        try:
            for _ in range(int(self.weight*100)):
                retlist.append(next(self.filehandle))
                self.linenum = self.linenum + 1
        except StopIteration:
            # Update seed and re-shuffle the file UNLESS we have reached the max epoch
            if self.epoch < self.max_epoch:
                self.filehandle.close()
                self._ammend_seed_()
                self._shuffle_(self.orig, self.shufffile)
                self._openfile_(self.shufffile)
                self.epoch = self.epoch + 1
                self.linenum = 0
        # Send statistics to the state tracker
        name = self.filename
        state = DatasetState(self.seed, self.linenum, self.epoch)
        return (myepoch, retlist)

    @staticmethod
    def _cleanup_(my_filehandle):
        if my_filehandle:
            my_filehandle.close()
        # @TODO save the training state

    def _exit_(self, exc_type, exc_value, traceback):
        self._finalizer()


if __name__ == '__main__':
    args = parse_user_args()
    config = args.config
    mytmpdir = args.temporary_dir
    state_tracker = StateTracker(mytmpdir + '/state.yml', args.resume)

    executor = Executor(config, mytmpdir)
