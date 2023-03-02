#!/usr/bin/env python3
import argparse
import random
import subprocess
import sys

from contextlib import ExitStack, contextmanager
from itertools import count
from math import exp, log, floor
from typing import IO, Iterator
from typing import TypeVar, Iterable, Iterator, Generic, List, Tuple


T = TypeVar('T')


def reservoir_sample(k:int, it:Iterable[T], *, rand: random.Random = random._inst, sort=False) -> List[T]:
	"""Take k samples from iterable by reading from start to end. If sort is
	True, it will return the selected samples in the order they appeared in.
	"""
	sample: List[Tuple[int,T]] = []

	numbered_it = enumerate(it)

	i = 0

	for i, (_, line) in zip(range(k), numbered_it):
		sample.append((i, line))

	w = exp(log(rand.random())/k)

	try:
		while True:
				next_i = i + floor(log(rand.random()) / log(1 - w)) + 1

				# Skip forward
				while i < next_i:
					i, line = next(numbered_it)

				sample[rand.randrange(k)] = (i, line)
				w = w * exp(log(rand.random()) / k)
	except StopIteration:
		pass

	if sort:
		return [line for _, line in sorted(sample)]
	else:
		return [line for _, line in sample]


class Tailer(Iterable[T]):
	"""Functions as an iterator that returns all but the last K lines. Those lines
	you can read from `tail`."""

	def __init__(self, k:int, it:Iterable[T]):
		self.sample: List[T] = [] # ring buffer of (at maximum) length k
		self.k = k
		self.i = 0
		self.it = iter(it)

	def __iter__(self) -> Iterator[T]:
		try:
			while self.i < self.k:
				self.sample.append(next(self.it))
				self.i += 1
		except StopIteration:
			# Oh less than k samples in iterable? :(
			return

		for line in self.it:
			yield self.sample[self.i % len(self.sample)]
			self.sample[self.i % len(self.sample)] = line
			self.i += 1

	@property
	def tail(self) -> List[T]:
		# In the scenario where we read less than our tail of data, we just return
		# the entire buffer in one go.
		if len(self.sample) < self.k:
			return self.sample

		return self.sample[(self.i % len(self.sample)):] + self.sample[0:(self.i % len(self.sample))]


def sample(k:int, iterable:Iterable[T], sort=False) -> Iterable[Iterable[T]]:
	"""Take `k` items from the start, the end and the middle from `iterable`. If
	`sort` is True, the items in the middle will be in the order they appeared
	in."""
	it = iter(iterable)

	yield (val for _, val in zip(range(k), it))

	tailer = Tailer(k, it)

	yield reservoir_sample(k, tailer, sort=sort)

	yield tailer.tail


@contextmanager
def gunzip(path):
	"""Like gzip.open(), but using external gzip process which for some reason
	is a lot faster on macOS."""
	with subprocess.Popen(['gzip', '-cd', path], stdout=subprocess.PIPE) as proc:
		assert proc.stdout is not None
		yield proc.stdout
		if proc.wait() != 0:
			raise RuntimeError(f'gzip returned error code {proc.returncode}')


def magic_open_or_stdin(ctx:ExitStack, path:str) -> IO[bytes]:
	# TODO ideally we would look at the magic bytes, but that would entail
	# consuming the input file partially and then I can't pass the complete
	# file onto gzip afterwards
	if path.endswith('.gz'):
		return ctx.enter_context(gunzip(path))
	elif path == '-':
		return sys.stdin.buffer
	else:
		return ctx.enter_context(open(path, 'rb'))


def main():
	parser = argparse.ArgumentParser(description="Take a file's head, tail and a random sample from the rest.")
	parser.add_argument('-n', dest='lines', type=int, default=10, help="number of lines for each section of the sample")
	parser.add_argument('-d', dest='delimiter', type=str, default="\\t", help="column delimiter. Defaults to \\t.")
	parser.add_argument('-N', '--line-numbers', action='store_true', help="print line numbers")
	parser.add_argument('files', metavar='file', type=str, nargs='*', default=['-'], help="files to sample. Multiple files for multiple columns. Use '-' for stdin. If none, reads from stdin.")
	args = parser.parse_args()

	with ExitStack() as ctx:
		columns:List[Iterator[bytes]] = [magic_open_or_stdin(ctx, file) for file in args.files]

		if args.line_numbers:
			columns.insert(0, (str(i).encode() for i in count()))

		pairs = zip(*columns)

		delimiter = args.delimiter.replace("\\t", "\t").replace("\\n", "\n").encode()

		for section in sample(args.lines, pairs, sort=True):
			for pair in section:
				for col, entry in enumerate(pair):
					if col > 0:
						sys.stdout.buffer.write(delimiter)
					sys.stdout.buffer.write(entry.rstrip(b"\n"))
				sys.stdout.buffer.write(b"\n")
			sys.stdout.buffer.flush()


if __name__ == '__main__':
	main()
