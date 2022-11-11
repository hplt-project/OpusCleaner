# Trainer
The purpose of the trainer is to provide the user with a flexible way of scheduling various sources of input data, as well as augment the training data with tittle casing, all caps, etc.

## Configuration file
Define your training process via a configuration file. You define the datasets on top, the stages and then for each stage a mixing criteria and a stage termination criteria. An example configuration file is provided below. The path to the `trainer` is a path to any neural network trainer that supports having stdin as training input format.
```yml
# Datasets are already TSV files
datasets:
  - test/data/clean
  - test/data/medium
  - test/data/dirty

stages:
  - start
  - mid
  - end

start:
  - clean 0.8
  - medium 0.2
  - dirty 0
  - until clean 2 # Until two epochs of clean

mid:
  - clean 0.6
  - medium 0.3
  - dirty 0.1
  - until medium 1

end:
  - clean 0.4
  - medium 0.3
  - dirty 0.3
  - until dirty 5 # use `inf` to mean until forever

uppercase: 0.05 # Apply uppercase randomly to 0.05% of sentences. Use 0 to disable
tittlecase: 0.05 # Apply uppercase randomly to 0.05% of sentences. Use 0 to disable
seed: 1111
trainer: /path/to/trainer/run.py
```

## Usage
```bash
% ./trainer.py --help                                                                                                          :(
usage: trainer.py [-h] --config CONFIG [--temporary-dir TEMPORARY_DIR] [--do-not-resume]

Feeds marian tsv data for training.

options:
  -h, --help            show this help message and exit
  --config CONFIG, -c CONFIG
                        YML configuration input.
  --temporary-dir TEMPORARY_DIR, -t TEMPORARY_DIR
                        Temporary dir, used for shuffling and tracking state
  --do-not-resume, -d   Do not resume from the previous training state
```
Once you fix the paths in the configuration file, `train_config.yml` you can run a test case by doing:
```bash
./trainer.py -c train_config.yml
```
You can check resulting mixed file in `/tmp/test`. If your neural network trainer doesn't support training from `stdin`, you can use this tool to generate a training dataset and then disable data reordering or shuffling at your trainer implementation, as your training input should be balanced.

At the start of the training all datasets are shuffled. Each time a dataset's end is reached, it is re-shuffled. Shuffling happens inside the training directory (by default `./TMP`) where the training state is also kept. If training is interrupted, re-running the trainer should resume from where it was (ALMOST, in case the buffer wasn't consumed by the neural network trainer, it will be skipped, but this is usually only a few hundred sentence pairs, no more).

## Future work

- The data should be augmented with placeholders. We have placeholders generation script that will be added soon.
- Terminology support (using a dictionary). We should augment the training data with terminology (possibly stemmed on the source side) so that we can use it real world models
- A one click run training
