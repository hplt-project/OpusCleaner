#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
from unicodedata import category as cat
import argparse
import regex

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Removes lines with average word lengths between specified min and max values")
    parser.add_argument("scripts", default="", type=str, nargs="+")
    parser.add_argument("--threshold", default=1, type=float)
    parser.add_argument("--debug", action='store_true')
    return parser.parse_args()


def filter_script_score(scripts: list, threshold: float, debug: bool=True) -> None:
    """Removes lines with average word lengths between specified min and max values"""
    
    thresholds = [threshold] * len(scripts)
    
    re_not_alphas = regex.compile(r'\p{Alphabetic=No}')
    re_not_script = [regex.compile(fr'\p{{^Script={script}}}') for script in scripts]
    
    print(re_not_script)
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        for idx, _ in enumerate(re_not_script):
            print('script:  ', re_not_script[idx])
            scores = []
            for word in src.split():
                src_alphas = re_not_alphas.sub('', word)
                print('- alphas: ', src_alphas , ' - ')
                #src_alphas = re_not_alphas.sub('', 'test')
                #print('word: ', type(src_alphas) , ' - ', src_alphas, '.')
                
                if src_alphas != '':
                    script = re_not_script[idx].sub('', src_alphas)
                    print('--- script: ', script , ' - ')
                    scores.append(len(script) / len(src_alphas))
                else:
                    scores.append(1.0)
            print(scores)
        #trg_alphas = re_not_alphas.sub('', trg)
        
        
        
        # scripts_pass = all(ratio >= threshold for ratio, threshold in zip(scores?, thresholds))
        #if src_avg_pass and trg_avg_pass:
        stdout.write(line)
        #elif debug:
        #    stderr.write(f'WORD AVG. LENGTH\t{src}\t{trg}\n')


if __name__ == '__main__':
    args = parse_user_args()
    filter_script_score(args.scripts, args.threshold, args.debug)
