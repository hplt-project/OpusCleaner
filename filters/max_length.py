#!/usr/bin/env python3
from sys import stdin, stdout, stderr
import argparse
import re

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Filters a parallel or mono dataset based on line lengths")
    parser.add_argument("--max-length", default=150, type=float)
    parser.add_argument("--min-length", default=1, type=float)
    parser.add_argument("--count-type", default='words', choices=['chars', 'words', 'bytes'], type=str)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()

def passes_lengths_filter(sequence: str, max_length: float, min_length: float, 
                          count_type: str, debug: bool=True) -> bool:
    """Handles the checking of lengths for the clean_parallel function"""
    passes: bool
    
    if count_type == 'chars':
                passes = (len(sequence) <= max_length and len(sequence) >= min_length)
                
    elif count_type == 'words':
        seqtok = sequence.split() # For 'words' type the sequence should be List of words
        passes = (len(seqtok) <= max_length and len(seqtok) >= min_length)
        
    elif count_type == 'bytes':
        passes = (len(sequence.encode('utf-8')) <= max_length 
                    and len(sequence.encode('utf-8')) >= min_length)
    
    return passes

def clean_parallel(max_length: float, min_length: float, count_type: str, debug: bool=True) -> None:
    """Cleans the parallel or mono dataset based on line lengths"""
    for line in stdin:
        fields = line.strip().split('\t')
        if len(fields) == 1:
            src = fields[-1].strip()
            trg = None
        else: # Assumes that the multiline filter already run
            src = fields[-2].strip()
            trg = fields[-1].strip()
        
        # Check if src column passes length filter
        srcpass: bool = passes_lengths_filter(sequence = src, max_length = max_length, 
                                        min_length = min_length, count_type = count_type)

        trgpass: bool

        # Check if trg column passes length filter
        if trg is None:
            trgpass = True
        else:
            trgpass = passes_lengths_filter(sequence = trg, max_length = max_length, 
                                            min_length = min_length, count_type = count_type)

        # write
        if srcpass and trgpass:
            stdout.write(line)
        elif debug:
            stderr.write(f'LENGTH\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    clean_parallel(args.max_length, args.min_length, args.count_type, args.debug)
