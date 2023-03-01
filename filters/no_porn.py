#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
import argparse
import regex
from no_porn_tokenizer import Tokenizer

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filter segments containing explicit language")
    parser.add_argument("--src-lang", default="en", type=str)
    parser.add_argument("--trg-lang", default="en", type=str)
    parser.add_argument("--command", default="", type=str, nargs='?')
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def filter_porn_lang(src_lang: str, trg_lang: str, command: str, debug: bool=True) -> None:
    """Filter segments containing explicit language"""
    
    porn_tokenizer_lang1 = Tokenizer(command = command, l = args.src_lang)
    porn_tokenizer_lang2 = Tokenizer(command = command, l = args.trg_lang)
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        src_porn_pass = porn_tokenizer_lang1.tokenize(src.lower())
        trg_porn_pass = porn_tokenizer_lang2.tokenize(trg.lower())
        
        if src_porn_pass and trg_porn_pass:
            stdout.write(line)
        elif debug:
            stderr.write(f'PORN FILTER\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    filter_porn_lang(args.src_lang, args.trg_lang, args.command, args.debug)
