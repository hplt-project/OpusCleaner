#!/usr/bin/env python3
import sys
from typing import List
import yaml
from dataclasses import dataclass
import re
import argparse
import random
import sentencepiece as spm

placeholders, sp = {}, None

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='Path to yaml configuration file', required=True)
parser.add_argument('-s', '--source_file', type=str, help='Path to the input file')
parser.add_argument('-v', '--vocab', type=str, help='Path to the vocab file')
parser.add_argument('-n', '--num_placeholders', type=int, default=20, help='Maximum number of placeholders')
parser.add_argument('--placeholder_symbol', type=str, default='@')
mutex_group_1 = parser.add_mutually_exclusive_group(required=True)
mutex_group_1.add_argument('--decode', action='store_true')
mutex_group_1.add_argument('--encode', action='store_true')
mutex_group_2 = parser.add_mutually_exclusive_group()
mutex_group_2.add_argument('-t', '--target_file', type=str, help='Path to the target file')
mutex_group_2.add_argument('--dump_placeholders', action='store_true', help='Check to print placeholders out')


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

        def replace(text, token):
            """Replaces `token` in `text` with placeholder
            """
            new_placeholder = f'{args.placeholder_symbol}{generate_random_in_range()}' if token not in placeholders.values() \
                        else get_key_from_placeholders(token)
            placeholders[new_placeholder] = token
            return re.sub(token, new_placeholder, text)

        # use regex rules
        for rule in rules:
            for grp in [match.group() for match in re.finditer(rule.pattern, self)]:
                self = replace(self, grp)

        # check for <unk>
        if sp:
            for token in self.split():
                # search for '@\d+' pattern
                if res := re.search(r'{}\d+'.format(args.placeholder_symbol), token):
                    # continue if search result is already existing placeholder
                    if res and res.group() in placeholders.keys():
                        continue

                try:  # get piece
                    piece = sp.id_to_piece(sp.encode(token))[1]
                except IndexError:
                    piece = "not_unk"

                if piece == "<unk>":
                    self = replace(self, token)

        return self


    def replace_placeholders(self, placeholders):
        """Replaces placeholders with corresponding strings
        """
        # iterate through placeholder-text pairs sorted by text length
        for idx, placeholder in sorted(placeholders.items(), key=lambda x: len(x), reverse=True):
            self = re.sub(r'{}(?!\d)'.format(idx), placeholder, self)
        return self


def dump_placeholders():
    print(*placeholders.keys())


def get_src() -> List[str]:
    if not args.source_file:
        return [line for line in sys.stdin]
    with open(args.source_file, 'r') as f:
        text = f.readlines()
    return text


def encode() -> None:
    with open(args.target_file, 'w') if args.target_file else sys.stdout as target_file, \
         open(args.config, 'r') as config_file:

        config, text = yaml.safe_load(config_file), get_src()
        rules = [Rule(regex) for regex in config['regexes']]
        [target_file.write(Text(line).make_placeholders(*rules)) for line in text]
        config["placeholders"], config["num-placeholders"] = placeholders, len(placeholders)

    with open(args.config, 'w') as config_file:
        yaml.dump(config, config_file, allow_unicode=True)


def decode() -> None:
    with open(args.target_file, 'w') if args.target_file else sys.stdout as target_file, \
         open(args.config, 'r') as config_file:

        text = get_src()
        placeholders = yaml.safe_load(config_file)['placeholders']
        [target_file.write(Text(line).replace_placeholders(placeholders)) for line in text]


if __name__ == "__main__":
    args = parser.parse_args()

    if args.vocab:
        sp = spm.SentencePieceProcessor(args.vocab)

    if args.dump_placeholders:
        with open(args.config, 'r') as config_file:
            placeholders = yaml.safe_load(config_file)['placeholders']
            dump_placeholders()
        exit()

    if not args.target_file:
        print(f'No target file provided for {sys.argv[0]}, output will be directed to stdout', file=sys.stderr)
    encode() if args.encode else decode()
