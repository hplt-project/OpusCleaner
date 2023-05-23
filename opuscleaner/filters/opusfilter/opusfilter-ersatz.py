#!/usr/bin/env python3
import argparse
import importlib
import itertools
import logging
import os
import sys
import warnings

# Prevent searching for modules in the filters/ directory (like langid)
del sys.path[0]

import opusfilter
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('--quiet', '-q', action='store_true')
parser.add_argument('filter', type=str)
parser.add_argument('config', type=str)

args = parser.parse_args()

if args.quiet:
	# Filter out warnings from opusfilter about missing env variables for like
	# word alignment.
	logging.getLogger().setLevel(logging.ERROR)

	# Filter warnings (especially MarkupResemblesLocatorWarning) from
	# BeautifulSoup (the HtmlTagFilter)
	warnings.filterwarnings('ignore', module='bs4')

module_path, class_name = args.filter.rsplit('.', maxsplit=1)

config = yaml.safe_load(args.config)

if not isinstance(config, dict):
	if config:
		raise ValueError('config has to be a mapping')

	config = dict()

mod = importlib.import_module(module_path)
filter_cls = getattr(mod, class_name)
filter_obj = filter_cls(**config)

if isinstance(filter_obj, opusfilter.FilterABC):
	def apply_filter(lines):
		# Duplicate the iterator into two, one goes into the scorer, one for output
		# because scorer could be eating them in chunks.
		lines1, lines2 = itertools.tee(lines)
		pairs = (line[0:2] for line in lines1)
		for line, score in zip(lines2, filter_obj.score(pairs)):
			if filter_obj.accept(score):
				yield line
elif isinstance(filter_obj, opusfilter.PreprocessorABC):
	def apply_filter(pairs):
		return filter_obj.process(pairs)
else:
	raise ValueError('filter class does not implement FilterABC or PreprocessorABC')

lines = (line.rstrip('\r\n').split('\t') for line in sys.stdin)

for line in apply_filter(lines):
	print("\t".join(line))
