#!/usr/bin/env python3
import sys
import re
import argparse
from typing import Set, List, Tuple


FOOTNOTE_PATTERN = r'\[[0-9]+\]', r''

URL_PATTERN = r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)', r''

WIKILINKS_PATTERN = r'\[\[(?:.+?\|)?(.+?)\]\]', r'\1'

CODE_PATTERN = r'\.mw-parser-output' # Very specific for OPUS-wikimedia


Pattern = Tuple[str,str]


def find_matches(pattern, text:str) -> Set[str]:
	return set(match[0] for match in re.finditer(pattern[0], text))


def filter_matches(pattern, text:str) -> str:
	return re.sub(*pattern, text)


def is_mismatch(pattern, fields: List[str]) -> bool:
	matches = [find_matches(pattern, field) for field in fields[:2]]
	return len(matches[0] & matches[1]) < len(matches[0] ^ matches[1])


def is_code(field: str) -> bool:
	return re.search(CODE_PATTERN, field) is not None


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Remove common wiki patterns from sentence pair if they don't match on both sides")
	parser.add_argument("--always", action="store_true", help="Always remove patterns")
	parser.add_argument("--footnotes", action="store_true", help="Remove footnotes, e.g. [1], [2]")
	parser.add_argument("--urls", action="store_true", help="Remove url`s")
	parser.add_argument("--wikilinks", action="store_true", help="Remove [[wikilinks]]")
	parser.add_argument("--code", action="store_true", help="Remove lines that contain code")
	parser.add_argument("--remove-empty-lines", action="store_true", help="Remove sentence pairs when one side is empty after filtering")
	args = parser.parse_args()

	patterns = []

	if args.footnotes:
		patterns.append(FOOTNOTE_PATTERN)

	if args.urls:
		patterns.append(URL_PATTERN)

	if args.wikilinks:
		patterns.append(WIKILINKS_PATTERN)

	for n, line in enumerate(sys.stdin, start=1):
		fields = line.rstrip("\n").split("\t")

		if args.code and any(is_code(field) for field in fields):
			continue

		for pattern in patterns:
			if args.always or is_mismatch(pattern, fields[:2]):
				fields[:2] = [filter_matches(pattern, field) for field in fields[:2]]

		if args.remove_empty_lines and all(len(field.strip()) > 0 for field in fields):
			print("\t".join(fields))
