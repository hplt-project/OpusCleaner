#!/usr/bin/env python3
import sys
import argparse
from typing import TextIO, List
from sentence_splitter import SentenceSplitter


def split_sentences_in_bitext(fin: TextIO, fout: TextIO, languages: List[str], keep_unbalanced: bool = False):
	splitters = [SentenceSplitter(language=lang) for lang in languages]
	
	for line in fin:
		cols = line.rstrip('\n').split('\t')

		assert len(cols) == len(splitters)

		splitted = [splitter.split(col) for splitter, col in zip(splitters, cols)]

		if any(len(col) != len(splitted[0]) for col in splitted[1:]):
			if keep_unbalanced:
				# Revert back to the input line
				splitted = [[col] for col in cols]
			else:
				# Skip line
				continue

		for cols in zip(*splitted):
			fout.write('\t'.join(cols) + '\n')


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--keep-unbalanced', action='store_true')
	parser.add_argument('languages', type=str, nargs='+')

	args = parser.parse_args()

	split_sentences_in_bitext(sys.stdin, sys.stdout, args.languages, args.keep_unbalanced)
