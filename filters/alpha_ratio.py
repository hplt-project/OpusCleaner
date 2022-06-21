#!/usr/bin/env python3
"""Filters the lines based on the ratio between alphabetic characters in a line from the language and others"""
from sys import stdin, stdout, stderr
from typing import Optional
import argparse
import re
from clean_common import CHARS

FILTER_PARAM = { "filter_alpha_ratio": {
        "command": "filters/alpha_ratio.py --src-lang $LANG1 --trg-lang $LANG2 --ratio-words-src $SRCWORDRAT\
         --ratio-words-trg $TRGWORDRAT --ratio-alpha-src $SRCALPHARAT --ratio-alpha-trg $TRGALPHARAT",
        "parameters": {
            "LANG1": {"type": "str", "allowed_values": CHARS.keys()},
            "LANG2": {"type": "str", "allowed_values": CHARS.keys() + None},
            "SRCWORDRAT": {"type": "float"},
            "TRGWORDRAT": {"type": "float"},
            "SRCALPHARAT": {"type": "float"},
            "TRGALPHARAT": {"type": "float"}
        }
    }
}

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratio-words-src", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a src sentence.')
    parser.add_argument("--ratio-words-trg", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a trg sentence.')
    parser.add_argument("--ratio-alpha-src", default=0.4, type=float, help='Ratio between characters from the src language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--ratio-alpha-trg", default=0.4, type=float, help='Ratio between characters from the trg language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--src-lang", default="en", type=str)
    parser.add_argument("--trg-lang", type=str)
    parser.add_argument("--debug", default=True, type=bool, action='store_true')
    return parser.parse_args()

def clean_parallel(src_lang: str, ratio_words_src: float, ratio_alpha_src: float,\
trg_lang: Optional[str]=None, ratio_words_trg: Optional[float]=None, ratio_alpha_trg: Optional[float]=None,\
 debug: Optional[bool]=True) -> None:
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
                    stderr.write(f'RATIO_WORDS_SRC\t{src}')
                continue

            char_alpha = len(re.findall(CHARS[src_lang], src, re.IGNORECASE))
            if char_alpha / float(len(src.replace(' ', ''))) < ratio_alpha_src:
                if debug:
                    stderr.write(f'RATIO_ALPHA_SRC\t{src}')
                continue

        if trg is not None and trg_lang in CHARS:
            trg_toks = trg.split()
            trg_len = len(trg_toks)
            num_words = sum(
                [1 if re.match(CHARS[trg_lang], t, re.IGNORECASE) else 0 for t in trg_toks])
            if num_words / float(trg_len) < ratio_words_trg:
                if debug:
                    stderr.write(f'RATIO_WORDS_TRG\t{trg}')
                continue

            char_alpha = len(re.findall(CHARS[trg_lang], trg, re.IGNORECASE))
            if char_alpha / float(len(trg.replace(' ', ''))) < ratio_alpha_trg:
                if debug:
                    stderr.write(f'RATIO_ALPHA_TRG\t{trg}')
                continue

        else:
            stdout.write(line)

if __name__ == '__main__':
    args = parse_user_args()
    if args.src_lang not in CHARS:
        stderr.write(f'Source language {args.src_lang} is not supported. Please add support for it in filters/clean_common.py')
    if args.trg_lang is not None and args.trg_lang not in CHARS:
        stderr.write(f'Target language {args.trg_lang} is not supported. Please add support for it in filters/clean_common.py')
    clean_parallel(src_lang=args.src_lang, ratio_words_src=args.ratio_words_src, ratio_alpha_src=args.ratio_alpha_src,\
        trg_lang=args.trg_lang, ratio_words_trg=args.ratio_words_trg, ratio_alpha_trg=args.ratio_alpha_trg, debug=args.debug)
