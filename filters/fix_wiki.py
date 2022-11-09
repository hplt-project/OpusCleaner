#!/usr/bin/env python3
import sys
import re
import argparse
from enum import Enum
from typing import Set, List, Tuple


class MatchType(Enum):
	EXACT = 'exact'
	COUNT = 'count'


Pattern = Tuple[str,str, MatchType]

# Footnote pattern needs to have the exact same matches on both sides. They're
# just things like `[3]` at the end of a word.
FOOTNOTE_PATTERN: Pattern = r'\[[0-9]+\]', r'', MatchType.EXACT

# URL match needs to be an exact match on both sides. If not, we teach the MT
# system to translate urls for us and that's not good.
URL_PATTERN: Pattern = r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)', r'', MatchType.EXACT

# If wiki links, e.g. `[[pagename|Link Label]]` or ``[[pagename]]` don't appear
# in equal amount on both sides, replace them with just their label. Not
# comparing the links themselves since they may link to translated page names.
WIKILINKS_PATTERN: Pattern = r'\[\[(?:.+?\|)?(.+?)\]\]', r'\1', MatchType.COUNT

# If header does not appear on both sides, remove it entirely. We only compare
# counts because the headers themselves are probably translated.
HEADINGS_PATTERN: Pattern = r'(==+)(.+?)\1', r'', MatchType.COUNT

CODE_PATTERN = r'\.mw-parser-output' # Very specific for OPUS-wikimedia


def find_matches(pattern:Pattern, text:str) -> Set[str]:
	return set(match[0] for match in re.finditer(pattern[0], text))


def filter_matches(pattern:Pattern, text:str) -> str:
	return re.sub(pattern[0], pattern[1], text)


def is_mismatch(pattern:Pattern, fields: List[str]) -> bool:
	matches = [find_matches(pattern, field) for field in fields[:2]]
	if pattern[2] == MatchType.EXACT:
		return len(matches[0] & matches[1]) < len(matches[0] ^ matches[1])
	elif pattern[2] == MatchType.COUNT:
		return len(matches[0]) != len(matches[1])
	else:
		raise NotImplementedError()


def is_code(field: str) -> bool:
	return re.search(CODE_PATTERN, field) is not None


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Remove common wiki patterns from sentence pair if they don't match on both sides")
	parser.add_argument("--always", action="store_true", help="Always remove patterns")
	parser.add_argument("--footnotes", action="store_true", help="Remove footnotes, e.g. [1], [2]")
	parser.add_argument("--urls", action="store_true", help="Remove url`s")
	parser.add_argument("--wikilinks", action="store_true", help="Remove [[wikilinks]]")
	parser.add_argument("--code", action="store_true", help="Remove lines that contain code")
	parser.add_argument("--headings", action="store_true", help="Remove ==headings==")
	parser.add_argument("--remove-empty-lines", action="store_true", help="Remove sentence pairs when one side is empty after filtering")
	args = parser.parse_args()

	patterns: List[Pattern] = []

	if args.footnotes:
		patterns.append(FOOTNOTE_PATTERN)

	if args.urls:
		patterns.append(URL_PATTERN)

	if args.wikilinks:
		patterns.append(WIKILINKS_PATTERN)

	if args.headings:
		patterns.append(HEADINGS_PATTERN)

	for n, line in enumerate(sys.stdin, start=1):
		fields = line.rstrip("\n").split("\t")

		if args.code and any(is_code(field) for field in fields):
			continue

		for pattern in patterns:
			if args.always or is_mismatch(pattern, fields[:2]):
				fields[:2] = [filter_matches(pattern, field) for field in fields[:2]]

		# Make sure we didn't add padding after all that replacing
		fields = [field.strip() for field in fields]

		if args.remove_empty_lines and all(len(field) > 0 for field in fields):
			print("\t".join(fields))
