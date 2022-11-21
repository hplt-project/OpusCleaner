#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
from unicodedata import category as cat
import argparse

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Removes lines with average word lengths between specified min and max values")
    parser.add_argument("--min-avg-length", default=20, type=int)
    parser.add_argument("--max-avg-length", default=20, type=int)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()

def filter_avg_word_length(min_avg_length: int, max_avg_length: int, debug: bool=True) -> None:
    """Removes lines with average word lengths between specified min and max values"""
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip().split()
        trg = fields[-1].strip().split()
    
        src_avg = sum(len(x) for x in src) / len(src)
        trg_avg = sum(len(x) for x in trg) / len(trg)
        
        src_avg_pass = (src_avg >= min_avg_length and src_avg <= max_avg_length)
        trg_avg_pass = (trg_avg >= min_avg_length and trg_avg <= max_avg_length)

        if src_avg_pass and trg_avg_pass:
            stdout.write(line)
        elif debug:
            stderr.write(f'WORD AVG. LENGTH\t{src}\t{trg}\n')

if __name__ == '__main__':
    args = parse_user_args()
    filter_avg_word_length(args.min_avg_length, args.max_avg_length, args.debug)
