import sys
from typing import List
import yaml
from dataclasses import dataclass
import re
import argparse
import random
import json
import sentencepiece as spm

placeholders, sp = {}, None

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='Path to yaml configuration file', required=True)
parser.add_argument('-s', '--source_file', type=str, help='Path to the input file')
parser.add_argument('-t', '--target_file', type=str, help='Path to the target file', required=True)
parser.add_argument('--dump_placeholders', action='store_true', help='Check to print placeholders out')
parser.add_argument('-v', '--vocab', type=str, help='Path to the vocab file')
parser.add_argument('-n', '--num_placeholders', type=int, default=20, help='Maximum number of placeholders')
mutex_group_1 = parser.add_mutually_exclusive_group(required=True)
mutex_group_1.add_argument('--decode', action='store_true')
mutex_group_1.add_argument('--encode', action='store_true')

@dataclass
class Rule(object):
    pattern: str

class Text(str):

    def make_placeholders(self, *rules):
        """Replaces strings that match the regex patterns from the config file
        and words that cause the appearance of <unk>
        """
        global placeholders, sp
        
        def get_key_from_placeholders(val):
            """Get key correpsonding to given value from the placeholders dictionary
            """
            for key, value in placeholders.items():
                if val == value:
                    return key
 
        def generate_random_in_range() -> int:
            """Generates random number in range defined by `num_placeholders` argparse argument 
            that is not in `placeholders.keys()`
            """
            return random.choice([x for x in range(args.num_placeholders) if x not in placeholders.keys()])

        # use regex rules
        for rule in rules:
            for grp in [match.group() for match in re.finditer(rule.pattern, self)]:
                if grp not in placeholders:
                    # generate new unique number for placeholder
                    new_number = generate_random_in_range()
                    placeholders[new_number] = grp
                else:
                    new_number = get_key_from_placeholders(grp)
                self = re.sub(grp, f'@{new_number}', self)

        # check for <unk>
        if sp:
            for token in self.split():
                # search for '(?<=@)\d+' pattern
                if res := re.search(r'(?<=@)\d+', token):
                    # continue if search result is already existing placeholder
                    if res and int(res.group()) in placeholders.keys():
                        continue
                
                try:  # get piece
                    piece = sp.id_to_piece(sp.encode(token))[1]
                except IndexError:
                    piece = "not_unk"

                if piece == "<unk>":
                    # generate new unique number for placeholder
                    new_number = generate_random_in_range()
                    placeholders[new_number] = token
                    self = re.sub(token, f'@{new_number}', self)
                elif token in placeholders:
                    new_number = get_key_from_placeholders(token)
                    self = re.sub(token, f'@{new_number}', self)
        return self

    def replace_placeholders(self, placeholders):
        """Replaces placeholders with corresponding strings
        """
        for idx, placeholder in placeholders.items():
            self = re.sub(f'@{idx}', placeholder, self)
        return self


def get_src() -> List[str]:
    if not args.source_file:
        return [line for line in sys.stdin]
    with open(args.source_file, 'r') as f:
        text = f.readlines()
    return text


def encode() -> None:
    with open(args.target_file, 'w') as target_file, \
         open(args.config, 'r') as config_file:

        config, text = yaml.safe_load(config_file), get_src()
        rules = [Rule(regex) for regex in config['regexes']]
        [target_file.write(Text(line).make_placeholders(*rules)) for line in text]
        config["placeholders"], config["num-placeholders"] = placeholders, len(placeholders)
    with open(args.config, 'w') as config_file:
        yaml.dump(config, config_file, allow_unicode=True)
    print(json.dumps(placeholders, indent=4)) if args.dump_placeholders else None


def decode() -> None:
    with open(args.config, 'r') as config_file, \
         open(args.target_file, 'w') as target_file:
        
        text = get_src()
        placeholders = yaml.safe_load(config_file)['placeholders']
        [target_file.write(Text(line).replace_placeholders(placeholders)) for line in text]
    print(json.dumps(placeholders, indent=4)) if args.dump_placeholders else None
        

if __name__ == "__main__":
    args = parser.parse_args()
    if args.vocab:
        sp = spm.SentencePieceProcessor(args.vocab)
    encode() if args.encode else decode()
