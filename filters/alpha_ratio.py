#!/usr/bin/env python3
"""Filters the lines based on the ratio between alphabetic characters in a line from the language and others"""
from sys import stdin, stdout, stderr
from typing import Optional, List
import argparse
import re
from clean_common import CHARS
import json

def create_json_str(parser_list: List, filestr: str, docstr: str):
    """Creates a json string from the argparser __dict__['_actions']"""
    json_out = {}
    json_out["description"] = docstr
    param_dict = {}

    for i, argument in enumerate(parser_list):
        # We need to skip [0], as this is the prepended `--help`
        current_str = {}
        if i == 0:
            if argument.option_strings[0] == '-h' or argument.option_strings[0] == '--help':
                continue
            else:
                stderr.write(f"Something is wrong, expected first line to be --help, got: {argument.option_strings[0]} instead.\n")
                exit(2)
        else:
            current_str["switch"] = argument.option_strings[0]
            current_str["substitute"] = argument.option_strings[0].replace('-','').upper()

            # Denotes something without an argument
            if argument.type != None:
                current_str["type"] = argument.type.__class__.__name__
            current_str["default"] = argument.default
            current_str["help"] = argument.help

            if argument.choices is not None:
                current_str["allowed_values"] = argument.choices
            current_str["required"] = argument.required

            # Add to the parameter dict
            param_dict[current_str["substitute"]] = current_str
    json_out["parameters"] = param_dict

    json_out["command"] = "./" + filestr
    for _, value in param_dict.items():
        json_out["command"] = json_out["command"] + " "
        if "type" in value:
            json_out["command"] = json_out["command"] + value["switch"] + " $" + value["substitute"]
        else: # Captures debug, but should also capture other types
            json_out["command"] = json_out["command"] + " ${" + value["substitute"] + "+" + value["switch"] + "}"
    print(json.dumps(json_out, indent=4))





def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratio-words-src", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a src sentence.')
    parser.add_argument("--ratio-words-trg", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a trg sentence.')
    parser.add_argument("--ratio-alpha-src", default=0.4, type=float, help='Ratio between characters from the src language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--ratio-alpha-trg", default=0.4, type=float, help='Ratio between characters from the trg language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--src-lang", default="en", type=str, choices=list(CHARS.keys()))
    parser.add_argument("--trg-lang", default="None", type=str, choices=list(CHARS.keys()) + ["None"])
    parser.add_argument("--debug", action='store_true')

    # Try dumping:
    create_json_str(parser.__dict__['_actions'], __file__, __doc__)

    return parser.parse_args()

def clean_parallel(src_lang: str, ratio_words_src: float, ratio_alpha_src: float,\
trg_lang: Optional[str], ratio_words_trg: float, ratio_alpha_trg: float,\
 debug: bool = True) -> None:
    """Cleans the parallel (or monolingual) dataset based on the number of characters"""
    for line in stdin:
        fields = line.strip().split('\t')
        if len(fields) == 1:
            src = fields[-1].strip()
            trg = None
        else: # Assumes that the multiline filter already run
            src = fields[-2].strip()
            trg = fields[-1].strip()

        if src_lang in CHARS:
            src_toks = src.split()
            src_len = len(src_toks)
            num_words = sum(
                [1 if re.match(CHARS[src_lang], t, re.IGNORECASE) else 0 for t in src_toks])
            if num_words / float(src_len) < ratio_words_src:
                if debug:
                    stderr.write(f'RATIO_WORDS_SRC\t{src}\t{trg}\n')
                continue

            char_alpha = len(re.findall(CHARS[src_lang], src, re.IGNORECASE))
            if char_alpha / float(len(src.replace(' ', ''))) < ratio_alpha_src:
                if debug:
                    stderr.write(f'RATIO_ALPHA_SRC\t{src}\t{trg}\n')
                continue

        if trg is not None and trg_lang in CHARS:
            trg_toks = trg.split()
            trg_len = len(trg_toks)
            num_words = sum(
                [1 if re.match(CHARS[trg_lang], t, re.IGNORECASE) else 0 for t in trg_toks])
            if num_words / float(trg_len) < ratio_words_trg:
                if debug:
                    stderr.write(f'RATIO_WORDS_TRG\t{src}\t{trg}\n')
                continue

            char_alpha = len(re.findall(CHARS[trg_lang], trg, re.IGNORECASE))
            if char_alpha / float(len(trg.replace(' ', ''))) < ratio_alpha_trg:
                if debug:
                    stderr.write(f'RATIO_ALPHA_TRG\t{src}\t{trg}\n')
                continue
        # If none of our filters have failed, we're good to go
        stdout.write(line)


if __name__ == '__main__':
    args = parse_user_args()
    #clean_parallel(src_lang=args.src_lang, ratio_words_src=args.ratio_words_src, ratio_alpha_src=args.ratio_alpha_src,\
    #    trg_lang=args.trg_lang, ratio_words_trg=args.ratio_words_trg, ratio_alpha_trg=args.ratio_alpha_trg, debug=args.debug)
