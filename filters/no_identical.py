#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
from unicodedata import category as cat
import argparse

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Removes identical lines between src and trg")
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()

def filter_identical(debug: bool=True) -> None:
    """Removes identical lines between src and trg"""
    tbl_non_alpha = [chr(i) for i in range(sys.maxunicode) if not cat(chr(i)).startswith('L')]
    tbl_non_alpha = str.maketrans('', '', ''.join(tbl_non_alpha))
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
    
        left = src.translate(tbl_non_alpha)
        right = trg.translate(tbl_non_alpha)
        is_identical = (left.casefold() == right.casefold())

        if not is_identical:
            stdout.write(line)
        elif debug:
            stderr.write(f'IDENTICAL\t{src}\t{trg}\n')

if __name__ == '__main__':
    args = parse_user_args()
    filter_identical(args.debug)
