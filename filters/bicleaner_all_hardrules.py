#!/usr/bin/env python3
import sys
from sys import stdin, stdout, stderr
import argparse
import regex
from collections import OrderedDict
from hardrules.hardrules import Hardrules
from hardrules.bicleaner_hardrules import initialization
from types import SimpleNamespace
import copy

def parse_user_args():
    """Parse the arguments necessary for this filter"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--not_too_short", default=-1, type=float)
    parser.add_argument("--not_too_long", default=-1, type=float)
    parser.add_argument("--no_empty", action='store_true')
    parser.add_argument("--length_ratio", default=-1, type=float)
    parser.add_argument("--no_identical", action='store_true')
    parser.add_argument("--no_literals", default='', type=str, nargs='*')
    parser.add_argument("--no_only_symbols", action='store_true')
    parser.add_argument("--no_only_numbers", action='store_true')
    parser.add_argument("--no_urls", action='store_true')
    parser.add_argument("--no_breadcrumbs", action='store_true')
    parser.add_argument("--no_glued_words", action='store_true')
    parser.add_argument("--no_repeated_words", action='store_true')
    parser.add_argument("--no_unicode_noise", action='store_true')
    parser.add_argument("--no_space_noise", action='store_true')
    parser.add_argument("--no_paren", action='store_true')
    parser.add_argument("--no_escaped_unicode", action='store_true')
    parser.add_argument("--no_bad_encoding", action='store_true')
    parser.add_argument("--no_titles", action='store_true')
    parser.add_argument("--no_number_inconsistencies", action='store_true')
    parser.add_argument("--no_script_inconsistencies", action='store_true')
    parser.add_argument("--no_wrong_language", action='store_true')
    
    
    parser.add_argument("--no_porn", action='store_true')
    parser.add_argument("--lm_threshold", default=-1, type=float)
    parser.add_argument("--lm_filter", default=False, type=bool)
    
    parser.add_argument("--debug", action='store_true')
    
        
    # Some wacky things are done here to combine the json sys.argv with 
    # those of the bicleaner initialization() parser
    
    # Get hardrules UI parameters
    args_1, unk_args = parser.parse_known_args()
    args_1 = args_1.__dict__
    
    # Get hardrules initialization parameters
    sys.argv = sys.argv[:1] + unk_args
    args_2 = initialization().__dict__
    
    args_2_keys = list(args_2.keys())
    for key in args_2_keys:
        if key in args_1:
            args_2.pop(key)
    
    # Combine both parameters
    args = SimpleNamespace(**args_1, **args_2)
    
    # Dealing with some weird flags
    if args.no_porn:
        args.disable_porn_removal = False
    else:
        args.disable_porn_removal = True
        
    if args.not_too_short > 0:
        args.disable_minimal_length = False
    else:
        args.disable_minimal_length = True
        
    if args.lm_threshold > 0:
        args.disable_lm_filter = False
    else:
        args.disable_lm_filter = True

    if args.no_wrong_language:
        args.disable_lang_ident = False
    else:
        args.disable_lang_ident = True

    return args


def filter_hardrules() -> None:
    """Filter segments based on specified Bicleaner hardrules"""
    
    args = parse_user_args()
    
    rule_pipeline = OrderedDict()
    rule_pipeline['no_empty'] = args.no_empty # Done!
    rule_pipeline['not_too_long'] = args.not_too_long # Done!
    rule_pipeline['not_too_short'] = args.not_too_short # Done!
    rule_pipeline['length_ratio'] = args.length_ratio # Done!
    rule_pipeline['no_identical'] = args.no_identical # Done!
    rule_pipeline['no_literals'] = args.no_literals # Done!
    rule_pipeline['no_only_symbols'] = args.no_only_symbols # Done!
    rule_pipeline['no_only_numbers'] = args.no_only_numbers # Done!
    rule_pipeline['no_urls'] = args.no_urls # Done!
    rule_pipeline['no_breadcrumbs'] = args.no_breadcrumbs # Done!
    rule_pipeline['no_glued_words'] = args.no_glued_words # Done!
    rule_pipeline['no_repeated_words'] = args.no_repeated_words # Done!
    rule_pipeline['no_unicode_noise'] = args.no_unicode_noise # Done!
    rule_pipeline['no_space_noise'] = args.no_space_noise # Done!
    rule_pipeline['no_paren'] = args.no_paren # Done!
    rule_pipeline['no_escaped_unicode'] = args.no_escaped_unicode # Done!
    rule_pipeline['no_bad_encoding'] = args.no_bad_encoding  # Done!
    rule_pipeline['no_titles'] = args.no_titles # Done!
    rule_pipeline['no_number_inconsistencies'] = args.no_number_inconsistencies # Done!
    rule_pipeline['no_script_inconsistencies'] = args.no_script_inconsistencies # Done!
    rule_pipeline['no_wrong_language'] = args.no_wrong_language # Done!
    rule_pipeline['no_porn'] = args.no_porn # Done!
    
    rule_pipeline['lm_filter'] = False
    if args.lm_threshold > 0:
        rule_pipeline['lm_filter'] = True # Done!
        
    args.rules_config = rule_pipeline
    
    hardrules = Hardrules(args)
    
    for line in stdin:
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
        
        boolean_results = []
        
        # NO EMPTY
        if args.no_empty:
            boolean_results.append(hardrules.c_no_empty(src, 'left'))
            boolean_results.append(hardrules.c_no_empty(trg, 'right'))
            
        # MIN LENGTH
        if not args.disable_minimal_length:
            boolean_results.append(hardrules.c_not_too_short(src, 'left'))
            boolean_results.append(hardrules.c_not_too_short(trg, 'right'))
            
        # MAX LENGTH
        if args.not_too_long > 0:
            boolean_results.append(hardrules.c_not_too_long(src, 'left'))
            boolean_results.append(hardrules.c_not_too_long(trg, 'right'))
            
        # LENGTH RATIO
        if args.length_ratio > 0:
            boolean_results.append(hardrules.c_length_ratio(src, trg))
        
        # NO IDENTICAL
        if args.no_identical:
            boolean_results.append(hardrules.c_no_identical(src, trg))
            
        # NO LITERALS
        if len(args.no_literals) != 0:
            boolean_results.append(hardrules.c_no_literals(src, 'left'))
            boolean_results.append(hardrules.c_no_literals(trg, 'right'))
            
        # NO ONLY SYMBOLS
        if args.no_only_symbols:
            boolean_results.append(hardrules.c_no_only_symbols(src, 'left'))
            boolean_results.append(hardrules.c_no_only_symbols(trg, 'right'))
        
        # NO ONLY NUMBERS
        if args.no_only_numbers:
            boolean_results.append(hardrules.c_no_only_numbers(src, 'left'))
            boolean_results.append(hardrules.c_no_only_numbers(trg, 'right'))
        
        # NO URLS
        if args.no_urls:
            boolean_results.append(hardrules.c_no_urls(src, 'left'))
            boolean_results.append(hardrules.c_no_urls(trg, 'right'))
        
        # NO BREADCRUMBS
        if args.no_breadcrumbs:
            boolean_results.append(hardrules.c_no_breadcrumbs(src, 'left'))
            boolean_results.append(hardrules.c_no_breadcrumbs(trg, 'right'))
        
        # NO GLUED WORDS
        if args.no_glued_words:
            boolean_results.append(hardrules.c_no_glued_words(src, 'left'))
            boolean_results.append(hardrules.c_no_glued_words(trg, 'right'))
            
        # NO REPEATED WORDS
        if args.no_repeated_words:
            boolean_results.append(hardrules.c_no_repeated_words(src, 'left'))
            boolean_results.append(hardrules.c_no_repeated_words(trg, 'right'))
        
        # NO UNICODE NOISE
        if args.no_unicode_noise:
            boolean_results.append(hardrules.c_no_unicode_noise(src, 'left'))
            boolean_results.append(hardrules.c_no_unicode_noise(trg, 'right'))
        
        # NO SPACE NOISE
        if args.no_space_noise:
            boolean_results.append(hardrules.c_no_space_noise(src, 'left'))
            boolean_results.append(hardrules.c_no_space_noise(trg, 'right'))
        
        # NO PAREN
        if args.no_paren:
            boolean_results.append(hardrules.c_no_paren(src, trg))
        
        # NO ESCAPED UNICODE
        if args.no_escaped_unicode:
            boolean_results.append(hardrules.c_no_escaped_unicode(src, 'left'))
            boolean_results.append(hardrules.c_no_escaped_unicode(trg, 'right'))
        
        # NO BAD ENCODING
        if args.no_bad_encoding:
            boolean_results.append(hardrules.c_no_bad_encoding(src, 'left'))
            boolean_results.append(hardrules.c_no_bad_encoding(trg, 'right'))
        
        # NO TITLES
        if args.no_titles:
            boolean_results.append(hardrules.c_no_titles(src, trg))
        
        # NO NUMBER INCONSISTENCIES
        if args.no_number_inconsistencies:
            boolean_results.append(hardrules.c_no_number_inconsistencies(src, trg))
        
        # NO SCRIPT INCONSISTENCIES
        if args.no_script_inconsistencies:
            boolean_results.append(hardrules.c_no_script_inconsistencies(src, 'left'))
            boolean_results.append(hardrules.c_no_script_inconsistencies(trg, 'right'))
        
        # NO WRONG LANGUAGE
        if args.no_wrong_language:
            boolean_results.append(hardrules.c_no_wrong_language(src, 'left'))
            boolean_results.append(hardrules.c_no_wrong_language(trg, 'right'))
            
        # LM FILTER
        if not args.disable_lm_filter:
            boolean_results.append(hardrules.c_lm_filter(src, trg))
            
        # NO PORN
        if args.no_porn:
            boolean_results.append(hardrules.c_no_porn(src, trg))
            
        
        if all(boolean_results):
            stdout.write(line)
        elif args.debug:
            stderr.write(f'BICLEANER HARDRULES\t{src}\t{trg}\n')


if __name__ == '__main__':
    filter_hardrules()



'''
https://github.com/bitextor/bicleaner-hardrules

-c CONFIG.yml or --config CONFIG.yml: Rules configuration file (default: None)

from hardrules.hardrules import Hardrules
'''