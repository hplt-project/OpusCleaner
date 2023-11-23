#!/usr/bin/env python3
import argparse
import re
import sys
from typing import Match, TextIO


NUM_EXPR = re.compile(r"""
	(?:
		(?P<sign>(?:(?<=\s)|^)[-+])  # start with a sign if it is not attached to a word, i.e. not - in tid-30
		|\b                          # or start with a word boundary, i.e. not just30
	)
	(?:0*)                         # allow for 0 prefixes which we then ignore when comparing
	(?P<value>\d+                  # digits before the first comma or dot
		(?:[\.,:]\d+)*                # allow commas or dots, i.e. 300,000.0 but not 3,,,5
	)
	\b                             # disallow 30beep, but also 30th and 1st #TODO
""", re.X)


def normalize(numstr:Match) -> str:
	return (numstr['sign'] or '') + re.sub(r'[^\d]+', '*', numstr['value']) # ignore the decimal and digit separators


def filter_numerical_mismatch(fin: TextIO, fout: TextIO, ratio: float, *, debug: bool = False):
	for line in fin:
		cols = line.rstrip('\r').split('\t')

		assert len(cols) >= 2

		nums_left, nums_right = (set(map(normalize, re.finditer(NUM_EXPR, col))) for col in cols[:2])

		# Only bother calculating the ratio if there were any numbers to begin with
		if nums_left or nums_right:
			overlap = nums_left & nums_right
			difference = nums_left ^ nums_right

			# Big > 1.0 number if lots of overlap, small < 1.0 number if lots of differences
			line_ratio = (len(overlap) + 1) / (len(difference) + 1)

			if debug:
				print(f"{len(overlap)} / {len(difference)} : {overlap!r} | {difference!r}", file=sys.stderr)

			if line_ratio < ratio:
				continue

		fout.write(line)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--ratio', type=float, default=1.0)
	parser.add_argument('--debug', action='store_true')
	args = parser.parse_args()

	filter_numerical_mismatch(sys.stdin, sys.stdout, args.ratio, debug=args.debug)
