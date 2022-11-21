#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
import argparse
import math

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filter segments based on penalty score with respecct to co-occurrence of terminal punctuation masrks ")
    parser.add_argument("--threshold", default=-2, type=float)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def filter_terminal_punct(threshold: float, debug: bool=True) -> None:
    """Filter segments based on penalty score with respecct to co-occurrence of terminal punctuation masrks """
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        src_punct = len([c for c in src if c in {'.', '?', '!', '…'}])
        trg_punct = len([c for c in trg if c in {'.', '?', '!', '…'}])
        
        score = abs(src_punct - trg_punct)
        
        if src_punct > 1:
            score += src_punct - 1
        if trg_punct > 1:
            score += trg_punct - 1
            
        score = -math.log(score + 1)
        
        terminal_score_pass = (score >= threshold)
        
        if not terminal_score_pass:
            print('score: ', score, '  -  th', threshold, '  | ', terminal_score_pass)
        
        if terminal_score_pass:
            stdout.write(line)
        elif debug:
            stderr.write(f'TERMINAL PUNCT. SCORE\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    filter_terminal_punct(args.threshold, args.debug)
