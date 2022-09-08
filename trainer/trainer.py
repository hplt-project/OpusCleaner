#!/usr/bin/env python3
'''A translation model trainer. It feeds marian different sets of datasets with different thresholds
for different stages of the training. Data is uncompressed and TSV formatted src\ttrg'''
import os
import argparse
from sys import stderr
from subprocess import check_call, CalledProcessError
from collections import namedtuple
from typing import List, Type, Tuple

import json
import yaml
from yaml.loader import SafeLoader

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Feeds marian tsv data for training.")
    parser.add_argument("--config", '-c', required=True, type=str, help='YML configuration input.')
    parser.add_argument("--seed", '-s', type=int, default=1111, help='Random seed for shuffling.')
    parser.add_argument("--temporary-dir", '-t', default="./TMP", type=str, help='Temporary dir, used for shuffling.')
    return parser.parse_args()

class Executor:
    '''This class takes in the config file and starts running training'''
    def __init__(self, ymlpath: str):
        ymldata = None
        with open(ymlpath, 'rt', encoding="utf-8") as myfile:
            ymldata = list(yaml.load_all(myfile, Loader=SafeLoader))[0]
        self.dataset_paths = ymldata['datasets']
        self.dataset_names = [x.split('/')[-1] for x in self.dataset_paths]
        self.stages = ymldata['stages']
        self.trainer = ymldata['trainer']


class Dataset:
    '''This class takes care of iterating through a dataset. It takes care of shuffling and
    remembering the position of the dataset'''
    def __init__(self, datapath: str, tmpdir: str, seed: int, weight: float):
        # Create the temporary directory if it doesn't exist
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        # Vars
        self.orig = datapath
        self.filename: str = datapath.split('/')[-1].shuf.start
        self.tmpdir = tmpdir
        self.seed = seed
        self.shufffile = self.tmpdir + "/" + self.filename + ".shuf"
        self.weight = weight
        # RNG file for shuf to read
        self.rng = tmpdir + '/rng'
        # set up state in one file. Filename and line number
        self.state = tmpdir + '/state_' + self.filename
        # filehandle
        self.filehandle = None
        # dataset epoch
        self.epoch = 0

        # Write random seed
        self.__set_seed__(seed)
        # shuffle the initial file
        self.__shuffle__(self.orig, self.shufffile)
        # Open the current file for reading
        self.__openfile__(self.shufffile)

    def __set_seed__(self, myseed):
        with open(self.rng, 'w', encoding="utf-8") as seedfile:
            seedfile.write(str(myseed) + "\n")

    def set_weight(self, neweight):
        '''Used for when we want to switch the sampling strategy based on our schedule'''
        self.weight = neweight

    def __ammend_seed__(self, newseed=None):
        if newseed is None:
            old_seed = None
            with open(self.rng, 'rt', encoding="utf-8") as myfile:
                old_seed = int(myfile.readlines()[0].strip())
            newseed = old_seed + 1
        self.seed = newseed
        self.__set_seed__(newseed)


    def __shuffle__(self, inputfile, outputfile):
        try:
            check_call(["shuf", "--random-source=" + self.rng, "-o", outputfile, inputfile])
        except CalledProcessError as err:
            print("Error shuffling", inputfile, file=stderr)
            print(err.cmd, file=stderr)
            print(err.stderr, file=stderr)

    def __openfile__(self, filepath):
        self.filehandle = open(filepath, 'rt', encoding="utf-8")

    def save(self, filepath):
        """Saves the current dataset training state to the disk"""
        with open(filepath, 'w', encoding="utf-8") as myfilehandle:
            json.dump(self, myfilehandle)

    @staticmethod
    def load(filepath) -> Type['Dataset']:
        """Loads a dataset object, also setting back the state"""
        my_dataset: Type['Dataset'] = json.load(filepath)
        my_dataset.__set_seed__(my_dataset.seed)
        my_dataset.__shuffle__(my_dataset.orig, my_dataset.shufffile)
        my_dataset.__openfile__(my_dataset.shufffile)
        # @TODO rewind the file to the proper location
        return my_dataset

    def get(self) -> Tuple[int, List[str]]:
        '''Gets the next N lines based on the weight of the dataset.
        When the dataset reaches its end, it automatically takes care of wrapping it'''
        #@TODO report which epoch we are at
        myepoch = self.epoch
        retlist: List[str] = []
        try:
            for _ in range(int(self.weight*100)):
                retlist.append(next(self.filehandle))
        except StopIteration:
            # Update seed and re-shuffle the file
            self.filehandle.close()
            self.__ammend_seed__()
            self.__shuffle__(self.orig, self.shufffile)
            self.__openfile__(self.shufffile)
            self.epoch = self.epoch + 1
        return (myepoch, retlist)

if __name__ == '__main__':
    args = parse_user_args()
    config = args.config
    mytmpdir = args.temporary_dir
    theseed = args.seed

    with open(config, 'rt', encoding="utf-8") as f:
        data = list(yaml.load_all(f, Loader=SafeLoader))
        print(data)
