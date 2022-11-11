#!/usr/bin/env bash
# Get the placeholders
../placeholders/placeholders.py -c train_config_bgen.yml --dump_placeholders > my_placeholders
# train vocabulary
/home/dheart/uni_stuff/postdoc/marian-dev/build/spm_train --bos_id=-1 --eos_id=0 --unk_id=1 --user_defined_symbols_file my_placeholders \
  --model_prefix="test/vocab.bgen" --vocab_size=12000 \
  --input="/home/dheart/uni_stuff/postdoc/empty-train/trainer/test/data/clean.bgen" \
  --shuffle_input_sentence=true --character_coverage 1

# Move vocabulary to the new location
mv test/vocab.bgen.model test/vocab.bgen.spm

# Make all datasets placeholded
for myfile in test/data/*.bgen; do
	../placeholders/placeholders.py -n --strict --encode -c train_config_bgen.yml < ${myfile} > ${myfile}.pls
done
