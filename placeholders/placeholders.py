#!/usr/bin/env python3
"""An encoder/decoder for placeholders in python3, using spm vocabulary"""
import sys
from typing import List, Dict, Type, Tuple
from copy import deepcopy
from dataclasses import dataclass
import re
import argparse
import random
import sentencepiece as spm
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='Path to yaml configuration file, required for encoding')
parser.add_argument('-m', '--mappings_file', type=str, default="mappings.yml", help='Path to the mappings, one yaml entry per line.')
mutex_group_1 = parser.add_mutually_exclusive_group(required=True)
mutex_group_1.add_argument('--decode', action='store_true')
mutex_group_1.add_argument('--encode', action='store_true')
mutex_group_1.add_argument('--dump_placeholders', action='store_true', help='Check to print placeholders out')

@dataclass
class Rule:
    """Just a wrapper for regex rules"""
    pattern: str

@dataclass
class Configuration:
    """Object holding the yaml config"""
    def __init__(self, config_file):
        with open(config_file, 'r', encoding='utf-8') as config_handle:
            my_config = yaml.safe_load(config_handle)
            # Parse
            self.rules = [Rule(regex) for regex in my_config['regexes']]
            self.placeholder_symbol = '@'
            self.num_placeholders = 20
            if 'placeholder-symbol' in my_config:
                self.placeholder_symbol = my_config['placeholder-symbol']
            if 'num-placeholders' in my_config:
                self.num_placeholders = my_config['num-placeholders']
            self.placeholders = [self.placeholder_symbol + str(i) for i in range(self.num_placeholders)]

            # During encoding assert that we have vocab
            if 'vocab' in my_config:
                vocab = my_config['vocab']
                self.sp = spm.SentencePieceProcessor(vocab)

                # Ensure that the placeholder symbol doesn't contain unk anywhere (including in the numbers)
                for placeholder in self.placeholders:
                    for token_proto in self.sp.encode(placeholder, out_type='immutable_proto').pieces:
                        if token_proto.id == self.sp.unk_id():
                            sys.stderr.write("The unk token is contained within the placeholder: " + str(token_proto.surface) +
                             " which will cause all sorts of trouble. Please choose a different one.\n")
                            sys.exit(1)
            else:
                self.sp = None


class Encoder:
    '''Encodes spm strings'''
    def __init__(self, placeholders: List[str], spm_vocab: Type['spm'], myrules: List[Type['Rule']]):
        self.placeholders = placeholders
        self.sp = spm_vocab
        self.rules = myrules
        self.unk_id  = self.sp.unk_id()

    def make_placeholders(self, inputline) -> Tuple[str, Dict[str, str]]:
        """Replaces strings that match the regex patterns from the config file
        and words that cause the appearance of <unk>
        """
        my_placeholders = deepcopy(self.placeholders) # For each line start with the full set of placeholders
        replacements = {}

        def generate_random_placeholder() -> str | None:
            """Generates random number in range defined by `num_placeholders` argparse argument
            that is not in `placeholders.keys()`
            """
            if my_placeholders != {}:
                mychoice = random.choice(my_placeholders)
                my_placeholders.remove(mychoice)
                return mychoice

            return None

        def replace_one(token) -> str | None:
            """Replaces one token with a placeholder, without going through the whole text.
               returns none if we don't have an available token."""
            cur_replacement = None
            if token in replacements:
                cur_replacement = replacements[token]
            elif len(my_placeholders) != 0:
                cur_replacement = generate_random_placeholder()
                replacements[token] = cur_replacement
            return cur_replacement

        def replace(text, token) -> str:
            """Replaces `token` in `text` with placeholder. In case we don't have enough placeholders left,
               return the text unchanged.
            """
            cur_replacement = replace_one(token)
            if cur_replacement is not None:
                return re.sub(token, cur_replacement, text)
            return text # We don't have enough placeholders left so just don't encode


        # use regex rules
        for rule in self.rules:
            for grp in [match.group() for match in re.finditer(rule.pattern, inputline)]:
                inputline = replace(inputline, grp)

        # check for <unk>
        input_proto = self.sp.encode(inputline, out_type='immutable_proto')
        inputline = ""
        for token_proto in input_proto.pieces:
            if token_proto.id == self.unk_id:
                candidate = replace_one(token_proto.surface)
                if candidate is not None:
                    inputline = inputline + candidate
                else:
                    inputline = inputline + token_proto.surface
            else:
                inputline = inputline + token_proto.surface
        inputline = inputline + '\n'

        return (inputline, dict((v, k) for k, v in replacements.items()))


def encode(my_placeholders: Dict[str, str], my_sp: Type['spm_vocab'], my_rules) -> None:
    '''Encodes everything form stdin, dumping it to stdout and dumping a file with
       all replacements'''
    encoder = Encoder(my_placeholders, my_sp, my_rules)
    counter = 0
    with open(args.mappings_file, 'w', encoding='utf-8') as yamlout:
        for line in sys.stdin:

            encoded_line, mappings = encoder.make_placeholders(line)
            sys.stdout.write(encoded_line) # Write the encoded line to stdout

            # Keep track of which sentence has what replacement mappings via a yaml config
            sent_mapping = {}
            sent_mapping[counter] = mappings
            yaml.dump(sent_mapping, yamlout, allow_unicode=True)
            yamlout.flush()
            counter = counter + 1 # Move to the next sentence


def decode() -> None:
    """Decodes a string from stdin, given a mappings file and spits it to stdout"""
    with open(args.mappings_file, 'r', encoding='utf-8') as mappings:
        placeholder_lines = yaml.safe_load(mappings)
    counter = 0
    for line in sys.stdin:
        try:
            my_placeholders = placeholder_lines[counter]
            for placeholder in my_placeholders.keys():
                line = line.replace(placeholder, my_placeholders[placeholder])
            sys.stdout.write(line)
            counter = counter + 1
        except KeyError:
            sys.stderr.write("The mappings file contains less lines than the input.")
            sys.exit(1)

if __name__ == "__main__":
    args = parser.parse_args()

    if args.encode or args.dump_placeholders:
        config = Configuration(args.config)

    if args.dump_placeholders:
        print(" ".join(config.placeholders))
        sys.exit(0)
    elif args.encode:
        encode(config.placeholders, config.sp, config.rules)
    else:
        decode()

