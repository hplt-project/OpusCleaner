#!/usr/bin/env python3
from sys import stdin, stdout, stderr
import argparse


def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filters a parallel or mono dataset based on line lengths")
    parser.add_argument("--max-length", default=150, type=float)
    parser.add_argument("--min-length", default=1, type=float)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def clean_parallel(max_length: float, min_length: float, debug: bool=True) -> None:
    """Cleans the parallel or mono dataset based on line lengths"""
    for line in stdin:
        fields = line.strip().split('\t')
        if len(fields) == 1:
            src = fields[-1].strip()
            trg = None
        else: # Assumes that the multiline filter already run
            src = fields[-2].strip()
            trg = fields[-1].strip()

        srctok = src.split()
        srcpass: bool = (len(srctok) <= max_length and len(srctok) >= min_length)

        trgpass: bool

        # Check lengths
        if trg is None:
            trgpass = True
        else:
            trgtok = trg.split()
            trgpass = (len(trgtok) <= max_length and len(trgtok) >= min_length)

        # write
        if srcpass and trgpass:
            stdout.write(line)
        elif debug:
            stderr.write(f'LENGTH\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    clean_parallel(args.max_length, args.min_length, args.debug)
