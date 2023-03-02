#!/usr/bin/env python3
import sys
import argparse
from collections import deque, Counter
from typing import Iterable, TypeVar
from itertools import takewhile


def common_suffix(buffer: Iterable[str]) -> str:
	iters = [iter(line[::-1]) for line in buffer]
	assert len(iters) > 1
	suffix = takewhile(identical, zip(*iters))
	return "".join(t[0] for t in suffix)[::-1]


T = TypeVar('T')

def identical(elements: Iterable[T]) -> bool:
	it = iter(elements)
	first = next(it)
	return all(first == el for el in it)


def strip_suffix(lines: Iterable[str], *, minlen: int = 2, minocc: int = 5, counter: Counter=None) -> Iterable[str]:
	buffer = deque()

	suffix = ""

	for line in lines:
		if suffix and line.endswith(suffix):
			assert not buffer, "buffer should been empty"
			if counter is not None:
				counter[suffix] += 1
			yield line[:-1 * len(suffix)]

		elif suffix: # and not line ends with suffix
			assert not buffer, "buffer should been empty"
			suffix = ""
			buffer.append(line)

		else: # suffix is None
			# Make space in the buffer
			if len(buffer) == minocc:
				yield buffer.popleft()
			
			buffer.append(line)

			# If our buffer is too small to identify a suffix, don't bother
			if len(buffer) < minocc:
				continue

			# Try to identify a new common suffix
			suffix = common_suffix(buffer)

			# If the suffix is too short, it might as well be nothing
			if len(suffix) < minlen:
				suffix = ""

			# if found, empty buffer, stripping that suffix
			if suffix:
				if counter is not None:
					counter[suffix] += len(buffer)
				while buffer:
					line = buffer.popleft()
					yield line[:-1 * len(suffix)]

	# Empty buffer
	yield from buffer


if __name__  == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--minlen", type=int, default=4)
	parser.add_argument("--minocc", type=int, default=5)
	parser.add_argument("--count", action="store_true")
	args = parser.parse_args()

	lines = (line.rstrip("\n") for line in sys.stdin)

	if args.count:
		counter = Counter()
	else:
		counter = None

	for line in strip_suffix(lines, minlen=args.minlen, minocc=args.minocc, counter=counter):
		print(line, file=sys.stdout)

	if counter:
		for suffix, count in counter.most_common():
			print(f"{suffix}\t{count}", file=sys.stderr)
