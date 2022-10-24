#!/usr/bin/env python3
from sys import stdin, stdout, stderr
import argparse

import pycld2

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Langid")
    parser.add_argument("--src_lang", default=None, type=str)
    parser.add_argument("--trg_lang", default=None, type=str)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def clean_parallel(src_lang: str, trg_lang: str, debug: bool=True) -> None:
    """Cleans the parallel or mono dataset based on language detection"""
    for line in stdin:
        fields = line.strip().split('\t')
        if len(fields) == 1:
            src = fields[-1].strip()
            trg = None
        else: # Assumes that the multiline filter already run
            src = fields[-2].strip()
            trg = fields[-1].strip()

        try:
            src_detection = pycld2.detect(src)[2][0][1]
        except pycld2.error:
            src_detection = src_lang
        srcpass: bool = src_lang == src_detection

        trgpass: bool

        if trg is None:
            trgpass = True
        else:
            try:
                trg_detection = pycld2.detect(trg)[2][0][1]
            except pycld2.error:
                trg_detection = trg_lang
            trgpass: bool = trg_lang == trg_detection

        # write
        if srcpass and trgpass:
            stdout.write(line)
        elif debug:
            stderr.write(f'LANGUAGE\t{src}\t{trg}\t{src_detection}\t{trg_detection}\n')


if __name__ == '__main__':
    args = parse_user_args()
    clean_parallel(args.src_lang, args.trg_lang, args.debug)
