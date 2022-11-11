# Trainer
The purpose of the trainer is to provide the user with a flexible way of scheduling various sources of input data, as well as augment the training data with tittle casing, all caps, etc. This is particularly useful when you have multiple data sources and you want to pretrain the model first on backtranslated data, gradually add other sources of data, and finally fine tune, all in one go.

Alternatively, this tool is particularly suited to training multilingual models, as it provides an easy way to define the desired mixture of datasets from different language sources.

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
titlecase: 0.05 # Apply titlecase randomly to 0.05% of sentences. Use 0 to disable
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

## Generating vocabulary and placeholders before training
To use the placeholder code augment your training data with placeholders before training, look at this example script:
```bash
#!/usr/bin/env bash
# Get the placeholders
../placeholders/placeholders.py -c train_config_bgen.yml --dump_placeholders > my_placeholders
# train vocabulary
spm_train --bos_id=-1 --eos_id=0 --unk_id=1 --user_defined_symbols_file my_placeholders \
  --model_prefix="test/vocab.bgen" --vocab_size=12000 \
  --input="/home/dheart/uni_stuff/postdoc/empty-train/trainer/test/data/clean.bgen" \
  --shuffle_input_sentence=true --character_coverage 1

# Move vocabulary to the new location
mv test/vocab.bgen.model test/vocab.bgen.spm

# Make all datasets placeholded
for myfile in test/data/*.bgen; do
	../placeholders/placeholders.py -n --strict --encode -c train_config_bgen.yml < ${myfile} > ${myfile}.pls
done
```
You need to augment the training configuration with additional placeholder configuration setting:
```yml
vocab: /home/dheart/uni_stuff/postdoc/empty-train/trainer/test/vocab.bgen.spm
placeholder-symbol: "<PLACEHOLDER>"
num-placeholders: 4
regexes:
    - (https?:\/\/www\.\w{1,63}\.\w{1,63}(?:\/\w{0,63}){0,})
    - (www\.\w{1,63}\.\w{1,63}(?:\/\w{0,63}){0,})
    - ([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)
```
After vocabulary is trained and data is preprocessed, proceed with a normal training run.
## Future work

- Terminology support (using a dictionary). We should augment the training data with terminology (possibly stemmed on the source side) so that we can use it real world models
- A one click run training
