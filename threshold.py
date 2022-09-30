#!/usr/bin/env python3
import sys
import os
import signal
import argparse
import pickle
import dbm
from pyhash import murmur3_32
from traceback import print_exc
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import Callable, Optional, Type, TypeVar, Dict
from functools import wraps
import struct


class Entry:
	"""Cache entry. Only an object with single property so we can easily update
	it by reference, really.
	"""
	__slots__ = ['score']
	score: Optional[float]

	def __init__(self, score: Optional[float]):
		self.score = score


class Cache:
	def __init__(self):
		self.entries = {}

	def __contains__(self, key: int) -> bool:
		return key in self.entries
	
	def __getitem__(self, key: int) -> Entry:
		return self.entries[key]

	def __setitem__(self, key: int, value: Entry):
		self.entries[key] = value

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return


class PersistentEntry:
	__slots__ = ['cache', 'key', '_score']

	def __init__(self, cache, key: int, score: Optional[float] = None):
		self.cache = cache
		self.key = key
		self._score = score

	@property
	def score(self):
		return self._score

	@score.setter
	def score(self, score):
		self._score = score
		self.cache._write(self.key, score)


class PersistentCache(Cache):
	__slots__ = ['entries', 'db', '_backing']

	def __init__(self, path: str):
		self.db = dbm.open(path, 'cf')
		self.entries: Dict[int,PersistentEntry] = {}

	def __enter__(self):
		self._backing = self.db.__enter__()
		return self

	def __exit__(self, *args):
		self._backing.__exit__(*args)

	def __contains__(self, key: int):
		return key in self.entries or self._key(key) in self._backing

	def __getitem__(self, key: int) -> PersistentEntry:
		if key not in self.entries:
			score = self._decode(self._backing[self._key(key)])
			self.entries[key] = PersistentEntry(self, key, score)
		return self.entries[key]

	def __setitem__(self, key: int, value: Entry):
		self.entries[key] = PersistentEntry(self, key, value.score)

	def _write(self, key: int, value: float):
		self._backing[self._key(key)] = self._encode(value)

	def _key(self, key: int) -> bytes:
		return struct.pack('<L', key)

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
	derive_key = murmur3_32()

	for line in fin:
		key = derive_key(line)
		# if key not in cache, we've never seen the sentence
		if key not in cache:
			fchild.write(line)
			cache[key] = Entry()

		queue.put((line, cache[key]))
	queue.put(None) # End indicator
	fchild.close()


def threshold_scores(queue, fchild, fout, threshold):
	"""Thread that reads the queue and, depending on the threshold, will write
	the line to output. It will also read any missing scores from the child
	`fchild`. Because this is the only thread reading & writing to Entry objects
	no locks are necessary.
	"""
	while True:
		item = queue.get()

		# Poison
		if item is None:
			break

		# If no score yet, get it from the child
		if item[1].score is None:
			item[1].score = float(fchild.readline())

		# Only print the actual line if threshold is met
		if item[1].score >= threshold:
			fout.write(item[0])
	
	# TODO: test somehow that child has stopped producing? Reading from `fchild`
	# should at this point return EOF since its stdin is already closed.
	fout.close()


def open_cache(path: Optional[str]) -> Cache:
	if path:
		return PersistentCache(path)
	else:
		return Cache()

try:
	parser = argparse.ArgumentParser()
	parser.add_argument('--cache', '-c', type=str)
	parser.add_argument('threshold', type=float)
	parser.add_argument('scorer', type=str, nargs='+')

	args, scorer_args = parser.parse_known_args()

	# TODO: Make this Popen call only necessary if there was any need for it,
	# i.e. not all sentences could be scored by just the cache. I'm tempted to
	# add yet another wrapper program that only starts the process once input
	# is readable from stdin and then just re-attaches stdin to the child? Bit
	# like how inetd works.
	child = Popen(args.scorer + scorer_args, stdin=PIPE, stdout=PIPE)

	queue = SimpleQueue() # type: SimpleQueue[tuple[bytes,Entry]]

	with open_cache(args.cache) as cache:
		# Reads stdin, writes it to queue, and possibly to child for scoring.
		feeder = Thread(target=exit_on_throw(feed_child), args=[queue, sys.stdin.buffer, child.stdin, cache])
		feeder.start()

		# Reads queue, writes to stdout, reading scores from child if necessary.
		consumer = Thread(target=exit_on_throw(threshold_scores), args=[queue, child.stdout, sys.stdout.buffer, args.threshold])
		consumer.start()

		# Feeder will be done at this point
		feeder.join()

		# Consumer will be done once it read the last None from the queue.
		consumer.join()

		# Feeder will close child.stdin when all input is processed, which should
		# cause child to terminate.
		retval = child.wait()

	sys.exit(retval)
except SystemExit:
	pass
except FileNotFoundError as e:
	print(e, file=sys.stderr)
	sys.exit(2)
except:
	print_exc(file=sys.stderr)
	sys.exit(127)
