#!/usr/bin/env python3
"""An encoder/decoder for placeholders in python3, using spm vocabulary"""
import sys
from typing import List, Dict, Type, Tuple, Optional
from copy import deepcopy
from dataclasses import dataclass
import re
import argparse
from random import Random
from sentencepiece import SentencePieceProcessor
import yaml


parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='Path to yaml configuration file, required for encoding')
parser.add_argument('-m', '--mappings_file', type=str, default="mappings.yml", help='Path to the mappings, one yaml entry per line.')
parser.add_argument('-s', '--seed', type=int, default=None, help='Seed for random number generator.')
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
        with open(config_file, 'r') as config_handle:
            my_config = yaml.safe_load(config_handle)

        # Parse
        self.rules = [Rule(regex) for regex in my_config['regexes']]
        self.placeholder_symbol = my_config.get('placeholder-symbol', '@')
        self.num_placeholders = my_config.get('num-placeholders', 20)
        self.placeholders = [self.placeholder_symbol + str(i) for i in range(self.num_placeholders)]

        # Add a rule that escapes patterns that look like a placeholder already
        # TODO: this will match placeholders we can't reach because `num_placeholders` might be smaller
        # causing us to replace placeholders that will never be produced by us, and draining our
        # available placeholders.
        self.rules.append(Rule(pattern=re.escape(self.placeholder_symbol) + r'\d+'))

        # During encoding assert that we have vocab
        if 'vocab' in my_config:
            vocab = my_config['vocab']
            self.sp = SentencePieceProcessor(vocab)

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
    def __init__(self, placeholders: List[str], spm_vocab: SentencePieceProcessor, rules: List[Rule], *, random: Random = Random()):
        self.placeholders = placeholders
        self.sp = spm_vocab
        self.rules = rules
        self.unk_id  = self.sp.unk_id()
        self.random = random

        # Compile rules into one mega-pattern
        self.rule_pattern = re.compile('|'.join('(?:{})'.format(rule.pattern) for rule in self.rules))

    def make_placeholders(self, inputline) -> Tuple[str, Dict[str, str]]:
        """Replaces strings that match the regex patterns from the config file
        and words that cause the appearance of <unk>
        """
        my_placeholders = list(self.placeholders) # For each line start with the full set of placeholders
        self.random.shuffle(my_placeholders)

        replacements: Dict[str,str] = {}

        def generate_random_placeholder() -> str:
            """Generates random number in range defined by `num_placeholders` argparse argument
            that is not in `placeholders.keys()`. Can throw IndexError if no placeholders are available.
            """
            return my_placeholders.pop()

        def replace_one(token) -> str:
            """Replaces one token with a placeholder, without going through the whole text. Will
            return the string as-is if there are no tokens available."""
            try:
                if token not in replacements:
                    replacements[token] = generate_random_placeholder()
                return replacements[token]
            except IndexError:
                return token

        # use regex rules
        inputline = re.sub(self.rule_pattern, lambda match: replace_one(match.group()), inputline)

        # check for <unk>
        input_proto = self.sp.encode(inputline, out_type='immutable_proto')
        inputline = ""
        for token_proto in input_proto.pieces:
            token = token_proto.surface
            if token_proto.id == self.unk_id:
                token = replace_one(token_proto.surface)
            inputline += token
        inputline += '\n'

        return (inputline, dict((v, k) for k, v in replacements.items()))


def encode(my_placeholders: List[str], my_sp: SentencePieceProcessor, my_rules: List[Rule], *, random: Random) -> None:
    '''Encodes everything form stdin, dumping it to stdout and dumping a file with
       all replacements'''
    encoder = Encoder(my_placeholders, my_sp, my_rules, random=random)
    with open(args.mappings_file, 'w') as yamlout:
        for counter, line in enumerate(sys.stdin):

            encoded_line, mappings = encoder.make_placeholders(line)
            sys.stdout.write(encoded_line) # Write the encoded line to stdout

            # Keep track of which sentence has what replacement mappings via a yaml config
            sent_mapping = {counter: mappings}
            yaml.dump(sent_mapping, yamlout, allow_unicode=True)
            yamlout.flush()


def decode() -> None:
    """Decodes a string from stdin, given a mappings file and spits it to stdout"""
    with open(args.mappings_file, 'r') as mappings:
        placeholder_lines = yaml.safe_load(mappings)
    for counter, line in enumerate(sys.stdin):
        try:
            my_placeholders = placeholder_lines[counter]
            for placeholder in my_placeholders.keys():
                line = line.replace(placeholder, my_placeholders[placeholder])
            sys.stdout.write(line)
        except KeyError as e:
            sys.stderr.write(f'Input line {counter + 1} contains a placeholder {e.args[0]} but there is no mapping for it.')
            sys.exit(1)
        except IndexError:
            sys.stderr.write("The mappings file contains less lines than the input.")
            sys.exit(1)

if __name__ == "__main__":
    args = parser.parse_args()

    random = Random(args.seed)

    if args.encode or args.dump_placeholders:
        config = Configuration(args.config)

    if args.dump_placeholders:
        print(" ".join(config.placeholders))
        sys.exit(0)
    elif args.encode:
        encode(config.placeholders, config.sp, config.rules, random=random)
    else:
        decode()

