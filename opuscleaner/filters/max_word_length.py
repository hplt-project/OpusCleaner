#!/usr/bin/env python3
import sys
import argparse
from typing import TextIO


def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filters a parallel dataset based on max word length")
    parser.add_argument("--max-word-length", default=150, type=int)
    return parser.parse_args()


def clean_parallel(max_word_length: float, fin: TextIO, fout: TextIO) -> None:
    """Cleans the parallel or mono dataset based on line lengths"""
    for line in fin:
        fields = line.strip().split('\t')

        if any(len(token) > max_word_length
            for field in fields
            for token in field.split(' ')):
            continue

        fout.write(line)


if __name__ == '__main__':
    args = parse_user_args()
    clean_parallel(args.max_word_length, sys.stdin, sys.stdout)
