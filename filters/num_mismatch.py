#!/usr/bin/env python3
import argparse
import re
import sys
from typing import Match, TextIO


def normalize(numstr:Match) -> str:
	return re.sub(r'[^\d]+', '*', numstr[0])


def filter_numerical_mismatch(fin: TextIO, fout: TextIO, ratio: float, *, debug: bool = False):
	for line in fin:
		cols = line.rstrip('\n').split('\t')

		assert len(cols) >= 2

		nums_left, nums_right = (set(map(normalize, re.finditer(r'\d+(?:[\.,]\d+)*', col))) for col in cols[:2])

		# Only bother calculating the ratio if there were any numbers to begin with
		if nums_left and nums_right:
			overlap = nums_left & nums_right
			difference = nums_left ^ nums_right

			# Big > 1.0 number if lots of overlap, small < 1.0 number if lots of differences
			line_ratio = (len(overlap) + 1) / (len(difference) + 1)

			if line_ratio < ratio:
				if debug:
					print(f"{len(overlap)} / {len(difference)} : {overlap!r} | {difference!r}", file=sys.stderr)
				continue

		fout.write(line)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--ratio', type=float, default=1.0)
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()

	filter_numerical_mismatch(sys.stdin, sys.stdout, args.ratio, debug=args.debug)
