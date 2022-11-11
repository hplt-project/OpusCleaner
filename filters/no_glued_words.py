#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
import argparse
import regex

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filter segments if lines have multiple glued words")
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()

def glued_words_filter(debug: bool=True) -> None:
    """Filter segments if lines have multiple glued words"""
    
    regex_glued_words = regex.compile("([[:alpha:]]*[[:upper:]]{1}[[:lower:]]+){3}")
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        src_glued_words_pass = (regex_glued_words.search(src) == None)
        trg_glued_words_pass = (regex_glued_words.search(trg) == None)
        
        if src_glued_words_pass and trg_glued_words_pass:
            stdout.write(line)
        elif debug:
            stderr.write(f'TERMINAL PUNCT. SCORE\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    glued_words_filter(args.debug)
