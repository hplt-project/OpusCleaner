#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
import argparse
import regex

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filter segments if lines have space noise")
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def filter_space_noise(debug: bool=True) -> None:
    """Filter segments if lines have space noise"""
    
    regex_spaces_noise = regex.compile("([ ]\D){4,}[ ]")
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        src_space_pass = (len(regex_spaces_noise.findall(src)) == 0)
        trg_space_pass = (len(regex_spaces_noise.findall(trg)) == 0)
        
        if src_space_pass and trg_space_pass:
            stdout.write(line)
        elif debug:
            stderr.write(f'SPACE NOISE\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    filter_space_noise(args.debug)
