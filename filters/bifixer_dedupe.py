#!/usr/bin/env python3
import sys
from typing import NamedTuple, Dict


class SentencePair(NamedTuple):
	src: str
	trg: str
	rank: float

best: Dict[str,SentencePair] = {}

for line in sys.stdin:
	src, trg, checksum, rank = line.rstrip('\n').split('\t')

	if checksum not in best or best[checksum].rank < float(rank):
		best[checksum] = SentencePair(src, trg, float(rank))

for pair in best.values():
	print(f"{pair.src}\t{pair.trg}", file=sys.stdout)
