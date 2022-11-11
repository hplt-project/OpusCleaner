#!/usr/bin/env python3
from sys import stdin, stdout, stderr
from typing import Callable, List
import math
import argparse


def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filters the lines based on the ratio between num_src_tokens and num_trg_tokens")
    parser.add_argument("--ratio-length", default=0.6, type=float)
    parser.add_argument("--filter-identical", action="store_true")
    parser.add_argument("--min-length", default=10, type=float)
    parser.add_argument("--ratio-type", default='words', type=str)
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def compare_log(src: List[str], trg: List[str], ratio: float) -> bool:
    src_len = len(src)
    trg_len = len(trg)

    if src_len > trg_len:
        trg_len, src_len = src_len, trg_len

    ratio_len = math.log10(src_len + 1) / math.log10(trg_len + 1)

    return ratio_len >= ratio


def compare_lin(src: List[str], trg: List[str], ratio: float) -> bool:
    src_len = len(src)
    trg_len = len(trg)

    ratio_len = float(src_len) / float(trg_len)

    return ratio_len >= ratio and ratio_len <= 1.0 / ratio


Comparator = Callable[[List[str], List[str], float], bool]


def clean_parallel(ratio: float, filter_identical: bool, min_length: float, 
                   ratio_type: str, *, debug: bool=False, compare: Comparator=compare_lin) -> None:
    """Cleans the parallel dataset based on the ratio of source to target tokens and vice versa"""
    for line in stdin:
        fields = line.strip().split('\t')
        if len(fields) != 2:
            stderr.write(f'SINGLE/MULTIPLE_LINES\t{line}')
            continue

        src = fields[0].strip()
        trg = fields[1].strip()

        # Remove identical lines
        if filter_identical and src.lower() == trg.lower():
            if debug:
                stderr.write(f'IDENTICAL\t{src}\t{trg}\n')
            continue
        
        # Get List of words or chars
        if ratio_type == 'words':
            src_toks = src.split()
            trg_toks = trg.split()
        elif ratio_type == 'chars':
            src_toks = list(src)
            trg_toks = list(trg)
            
        # Ignore lines if any line is small
        any_small: bool = (len(src_toks) < min_length or len(trg_toks) < min_length)

        if not any_small and not compare(src_toks, trg_toks, ratio):
            if debug:
                stderr.write(f'RATIO_LENGTH: {src}\t{trg}\n')
        else:
            stdout.write(line)


if __name__ == '__main__':
    args = parse_user_args()
    clean_parallel(args.ratio_length, args.filter_identical, 
                   args.min_length, args.ratio_type, debug=args.debug,
                   compare=compare_log if args.log else compare_lin)
