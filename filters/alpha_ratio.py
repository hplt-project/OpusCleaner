#!/usr/bin/env python3
from sys import stdin, stdout, stderr
from typing import Optional
import argparse
import re
from clean_common import CHARS

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filters the lines based on the ratio between alphabetic characters in a line from the language and others")
    parser.add_argument("--ratio-words-src", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a src sentence.')
    parser.add_argument("--ratio-words-trg", default=0.6, type=float, help='Ratio between words and non words (eg numbers, foreign words) in a trg sentence.')
    parser.add_argument("--ratio-alpha-src", default=0.4, type=float, help='Ratio between characters from the src language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--ratio-alpha-trg", default=0.4, type=float, help='Ratio between characters from the trg language compared to all characters (eg numbers, emoji, punctuation, etc...)')
    parser.add_argument("--src-lang", default="en", type=str, choices=list(CHARS.keys()))
    parser.add_argument("--trg-lang", type=str, choices=list(CHARS.keys()))
    parser.add_argument("--debug", action='store_true')
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
            if src_len==0:
                if debug:
                    stderr.write(f'EMPTY_SRC\t{src}\t{trg}\n')
                continue

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
            if trg_len==0:
                if debug:
                    stderr.write(f'EMPTY_TRG\t{src}\t{trg}\n')
                continue

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
    clean_parallel(src_lang=args.src_lang, ratio_words_src=args.ratio_words_src, ratio_alpha_src=args.ratio_alpha_src,\
        trg_lang=args.trg_lang, ratio_words_trg=args.ratio_words_trg, ratio_alpha_trg=args.ratio_alpha_trg, debug=args.debug)
