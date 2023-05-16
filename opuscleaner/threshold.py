#!/usr/bin/env python3
"""Compute score and optionally threshold and cache per line of input.

It passes every line of input onto the scorer program (unless --cache is
specified and the line is already in the cache) that generates a score. If
--threshold is specified (optionally with an operator specified, default is 
greater or equal, c.f. --ge) then the line is printed if the threshold is met.
If no threshold is specified, the score is added as the first column to the
output.

Note on --cache: make sure that if you change the arguments to the scorer
program, you also change the path to the cache. Otherwise you'll get scores
from the scorer that was run with different arguments.
"""
import sys
import os
import signal
import argparse
import dbm
import operator
from xxhash import xxh32
from traceback import print_exc
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import Optional, TypeVar, Dict
from functools import wraps
import struct


class Entry:
	"""Cache entry. Only an object with single property so we can easily update
	it by reference, really.
	"""
	__slots__ = ['score']
	score: Optional[float]

	def __init__(self, score: Optional[float] = None):
		self.score = score


class Cache:
	"""Just a subset of dict[] really!"""
	def __init__(self):
		self.entries = {}

	def __contains__(self, key: bytes) -> bool:
		return key in self.entries
	
	def __getitem__(self, key: bytes) -> Entry:
		return self.entries[key]

	def __setitem__(self, key: bytes, value: Entry):
		self.entries[key] = value

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return


class PersistentEntry:
	"""Mimics Entry(), but with a setter that updates the persistent cache."""
	__slots__ = ['cache', 'key', '_score']
	cache: "PersistentCache"
	key: bytes

	def __init__(self, cache, key: bytes, score: Optional[float] = None):
		self.cache = cache
		self.key = key
		self._score = score

	@property
	def score(self) -> Optional[float]:
		return self._score

	@score.setter
	def score(self, score: float):
		self._score = score
		self.cache._write(self.key, score)


class PersistentCache(Cache):
	"""Similar to Cache, but will also look at the database file that's on disk
	when queried for known entries.
	"""
	__slots__ = ['entries', 'db', '_backing']

	def __init__(self, path: str):
		self.db = dbm.open(path, 'c') # was 'cfu' create, fast, unlocked (TODO unlocked?!) but that only works if the gnu backend is used
		self.entries: Dict[bytes,PersistentEntry] = {}

	def __enter__(self):
		self._backing = self.db.__enter__()
		return self

	def __exit__(self, *args):
		self._backing.__exit__(*args)

	def __contains__(self, key: bytes):
		return key in self.entries or key in self._backing

	def __getitem__(self, key: bytes) -> PersistentEntry:
		if key not in self.entries:
			score = self._decode(self._backing[key])
			self.entries[key] = PersistentEntry(self, key, score)
		return self.entries[key]

	def __setitem__(self, key: bytes, value: Entry):
		self.entries[key] = PersistentEntry(self, key, value.score)

	def _write(self, key: bytes, value: float):
		self._backing[key] = self._encode(value)

	def _encode(self, value: float) -> bytes:
		return struct.pack('<f', value)

	def _decode(self, data: bytes) -> float:
		return struct.unpack('<f', data)[0]


T = TypeVar("T")


def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
	"""Runtime cast of `Optional[T]` into `T`. Will raise an AssertionError if
	the argument was indeed `None`.
	"""
	if optional is None:
		raise ValueError(message)
	return optional


def exit_on_throw(fn):
	"""Wraps thread main function so that an exception thrown in the thread
	will terminate the entire process.
	"""
	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except:
			print_exc(file=sys.stderr)
			os.kill(os.getpid(), signal.SIGKILL)
	return wrapper


def feed_child(queue, fin, fchild, cache):
	"""Thread that reads each line from stream `fin`, and will put its score
	`Entry` onto queue `queue`. If a line is a duplicate, it will use the entry
	from the previous occurrence. If a line is new, it will also feed it to
	child process `fchild` so a score can be calculated. Because the order of
	the queue and the order of feeding fchild are the same, the
	`threshold_scores` thread will know how to link them back together.
	"""
	derive_key = lambda val: xxh32(val).digest()

	try:
		for line in fin:
			key = derive_key(line)
			# if key not in cache, we've never seen the sentence
			if key not in cache:
				fchild.write(line)
				cache[key] = Entry()

			queue.put((line, cache[key]))
		fchild.close()
	except BrokenPipeError:
		pass
	finally:
		queue.put(None) # End indicator
		fin.close()


def threshold_scores(queue, fchild, fout, threshold, operator):
	"""Thread that reads the queue and, depending on the threshold, will write
	the line to output. It will also read any missing scores from the child
	`fchild`. Because this is the only thread reading & writing to Entry objects
	no locks are necessary.
	"""
	try:
		while True:
			item = queue.get()

			# Poison
			if item is None:
				break

			# If no score yet, get it from the child
			if item[1].score is None:
				item[1].score = float(fchild.readline())

			# If no threshold is specified, print everything and prefix it with the score
			if threshold is None:
				fout.write(str(item[1].score).encode() + b'\t' + item[0])
			
			# Otherwise only print the actual line if threshold is met
			elif operator(item[1].score, threshold):
				fout.write(item[0])
		
		# TODO: test somehow that child has stopped producing? Reading from `fchild`
		# should at this point return EOF since its stdin is already closed.
		fout.close()
	except BrokenPipeError:
		pass
	finally:
		fchild.close()


def open_cache(path: Optional[str]) -> Cache:
	"""Instantiates a cache type based on the path (or None) given."""
	if path:
		return PersistentCache(path)
	else:
		return Cache()


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('threshold', type=float, help='Threshold (b) to compare score to.')
	parser.add_argument('scorer', type=str, nargs='+', help='Scorer program (a) and arguments.')
	parser.add_argument('--cache', '-c', type=str, help='Path to cache database.')
	
	ops = parser.add_mutually_exclusive_group()
	ops.set_defaults(operator=operator.ge) # default to --ge
	for name in ['lt', 'le', 'eq', 'ne', 'ge', 'gt']:
		ops.add_argument(f'--{name}', dest='operator', action='store_const', const=getattr(operator, name), help=getattr(operator, name).__doc__)

	args, scorer_args = parser.parse_known_args()

	# TODO: Make this Popen call only necessary if there was any need for it,
	# i.e. not all sentences could be scored by just the cache. I'm tempted to
	# add yet another wrapper program that only starts the process once input
	# is readable from stdin and then just re-attaches stdin to the child? Bit
	# like how inetd works. Or should this be a task for the downstream scorer
	# i.e. only load the model once input is received?
	child = Popen(args.scorer + scorer_args, stdin=PIPE, stdout=PIPE)

	queue = SimpleQueue() # type: SimpleQueue[tuple[bytes,Entry]]

	try:
		with open_cache(args.cache) as cache:
			# Reads stdin, writes it to queue, and possibly to child for scoring.
			feeder = Thread(target=exit_on_throw(feed_child), args=[queue, sys.stdin.buffer, child.stdin, cache])
			feeder.start()

			# Reads queue, writes to stdout, reading scores from child if necessary.
			consumer = Thread(target=exit_on_throw(threshold_scores), args=[queue, child.stdout, sys.stdout.buffer, args.threshold, args.operator])
			consumer.start()

			# Feeder will be done at this point
			feeder.join()

			# Consumer will be done once it read the last None from the queue.
			consumer.join()

			# Feeder will close child.stdin when all input is processed, which should
			# cause child to terminate.
	except:
		none_throws(child.stdin).close()
	finally:
		sys.stderr.close()
		retval = child.wait()
		sys.exit(retval)


if __name__ == '__main__':
	main()
