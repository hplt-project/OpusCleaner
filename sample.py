import random
from math import exp, log, floor


def reservoir_sample(k, it, *, rand: random.Random = random._inst):
	sample = []

	numbered_it = enumerate(it)

	for i, (_, line) in zip(range(k), numbered_it):
		sample.append(line)

	w = exp(log(rand.random())/k)

	try:
		while True:
				next_i = i + floor(log(rand.random()) / log(1 - w)) + 1
				
				# Skip forward
				while i < next_i:
					i, line = next(numbered_it)
					
				sample[rand.randrange(k)] = line
				w = w * exp(log(rand.random()) / k)
	except StopIteration:
		pass

	return sample


class Tailer:
	"""Functions as an iterator that returns all but the last K lines. Those lines
	you can read from `tail`."""

	def __init__(self, k, it):
		self.sample = []
		self.k = k
		self.i = 0
		self.it = iter(it)

	def __iter__(self):
		while self.i < self.k:
			self.sample.append(next(self.it))
			self.i += 1

		for line in self.it:
			yield self.sample[self.i % len(self.sample)]
			self.sample[self.i % len(self.sample)] = line
			self.i += 1

	@property
	def tail(self):
		return self.sample[(self.i % len(self.sample)):] + self.sample[0:(self.i % len(self.sample))]


def sample(k, items):
	it = iter(items)

	head = [next(it) for _ in range(k)]

	tailer = Tailer(k, it)

	middle = reservoir_sample(k, tailer)

	return head, middle, tailer.tail


if __name__ == '__main__':
	import sys
	import gzip
	from contextlib import ExitStack, contextmanager
	from itertools import count, chain
	from io import BufferedReader

	@contextmanager
	def magic_open(filename):
		with open(filename, 'rb') as fh:
			buffered = BufferedReader(fh)

			# Check for gzip header
			if buffered.peek(2).startswith(b'\x1f\x8b'):
				buffered = gzip.open(buffered)
			
			yield buffered

	k = int(sys.argv[1])

	with ExitStack() as ctx:
		files = [ctx.enter_context(magic_open(file)) for file in sys.argv[2:]]

		# TODO: It would be good to have strict=True here but that's only
		# Python 3.10 and won't work with the count()-based generator.
		pairs = zip(
			(str(i).encode() + b":\n" for i in count()), # Line numbers
			*files
		)

		head, middle, tail = sample(10, pairs)

		for pair in chain(head, middle, tail):
			for entry in pair:
				sys.stdout.buffer.write(entry)
			sys.stdout.buffer.write(b'\n')

