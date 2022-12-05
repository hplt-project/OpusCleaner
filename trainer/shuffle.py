#!/usr/bin/env python3
import subprocess
import sys
import os
from argparse import ArgumentParser, FileType
from itertools import islice, chain
from tempfile import mkstemp
from typing import TypeVar, Iterable, List, Optional, Union, Set
from queue import SimpleQueue
from threading import Thread
from dataclasses import dataclass
from random import Random
from xxhash import xxh32


# Buffer size for reading files. Bufsize that Python assigns is generally too small?
BUFSIZE=2**16

T = TypeVar('T')

def chunked(iterable: Iterable[T], chunk_size:int) -> Iterable[Iterable[T]]:
	"""Splits an iterable into shorter iterables of a fixed length. Note that
	these are still iterables so please do just read them sequentially, and only
	request the next chunk when you've exhausted the current one."""
	try:
		it = iter(iterable)
		while True:
			has_next = next(it)
			yield chain([has_next], islice(it, chunk_size - 1))
	except StopIteration:
		pass


def split_into_tempfiles(fh: Iterable[bytes], lines:int, dir=None) -> Iterable[str]:
	"""Split an iterable into a number of (temporary) files. Returns the
	filenames. Note that you're responsible for deleting the tempfiles when
	you're done with them."""
	for chunk in chunked(fh, lines):
		fd, name = mkstemp(dir=dir)
		try:
			with os.fdopen(fd, 'wb') as fh:
				fh.writelines(chunk)
			yield name
		except:
			os.unlink(name)
			raise


@dataclass(frozen=True)
class ShuffleTask:
	"""Job that describes to shuffle a file to the shuffle_chunk_worker thread.
	Passing along the seed created by the main thread because those
	random.random() calls are predictable. The order in which Shuffling tasks
	are picked up and finished may not be."""
	seed: float
	filename: str


def shuffle_chunk_worker(queue:"SimpleQueue[Optional[ShuffleTask]]"):
	"""Worker thread that takes a queue of filenames and seeds, and shuffles them
	in memory. Put a None in the queue to make it stop."""
	while True:
		task = queue.get()

		if task is None:
			break

		random = Random(task.seed)

		with open(task.filename, 'rb+', buffering=BUFSIZE) as fh:
			lines = fh.readlines()
			random.shuffle(lines)
			fh.seek(0)
			fh.writelines(lines)


def shuffle(fin: Iterable[bytes], lines:int, *, seed: Optional[int] = None, threads: Optional[int] = os.cpu_count()) -> Iterable[bytes]:
	"""Shuffle a list by reading it into a bunch of files (of `lines` length)
	and shuffling all of these with `threads` in-memory shufflers."""
	random = Random(seed)

	queue: "SimpleQueue[Optional[ShuffleTask]]" = SimpleQueue()

	chunks: List[str] = []

	try:
		# Prepare shuffle workers to start shuffling chunks as soon as we've
		# finished writing them.
		shufflers = [
			Thread(target=shuffle_chunk_worker, args=[queue])
			for _ in range(threads if threads is not None else 1)
		]

		try:
			for shuffler in shufflers:
				shuffler.start()

			# Split the input file into separate temporary chunks
			for filename in split_into_tempfiles(fin, lines):
				# Remember the chunk's filename for later
				chunks.append(filename)
				# And immediately start shuffling that chunk in another thread
				# TODO: Maybe multiprocess is more effective here because GIL?
				queue.put(ShuffleTask(random.random(), filename))
		finally:
			# Tell shufflers that they can stop waiting
			for _ in shufflers:
				queue.put(None)

			# Wait for them to finish shuffling the last files
			for shuffler in shufflers:
				shuffler.join()

		# Open all chunks. We'll be reading the next line from a random one of them.
		chunk_fds = [open(filename, 'rb', buffering=BUFSIZE) for filename in chunks]

		# While we still have chunks to read from...
		while chunk_fds:
			# Pick a random chunk, read the line
			fd = random.choice(chunk_fds)
			line = fd.readline()
			# If the line was empty, the chunk has reached EOF and we close it.
			if line == b'':
				fd.close()
				chunk_fds.remove(fd)
				continue
			yield line
	finally:
		# Whatever happened, if a filename of a temporary file made it into the
		# `chunks` list, we are responsible for cleaning it up.
		for filename in chunks:
			os.unlink(filename)


class Reader(Iterable[bytes]):
	"""Lazily opens a file only once you start trying to read it. Also magically
	reads gzipped files."""
	def __init__(self, filename:str):
		self.filename = filename

	def _read_gzip(self, filename:str) -> Iterable[bytes]:
		child = subprocess.Popen(['gzip', '-cd', filename], stdout=subprocess.PIPE, bufsize=BUFSIZE)
		assert child.stdout is not None
		yield from child.stdout
		if child.wait() != 0:
			raise RuntimeError(f'`gzip -cd {filename}` failed with return code {child.returncode}')		

	def _read_plain(self, filename:str) -> Iterable[bytes]:
		with open(filename, 'rb') as fh:
			yield from fh

	def __iter__(self) -> Iterable[bytes]:
		if self.filename.endswith('.gz'):
			return self._read_gzip(self.filename)			
		else:
			return self._read_plain(self.filename)


LineType = TypeVar('LineType', bound=Union[str,bytes])

def deduplicate(lines:Iterable[LineType], delimiter:LineType, columns:List[int]) -> Iterable[LineType]:
	seen: Set[bytes] = set()
	for line in lines:
		fields = line.split(delimiter)
		key = xxh32(delimiter.join(fields[col - 1] for col in columns)).digest()
		if key in seen:
			continue
		seen.add(key)
		yield line


def intlist(desc:str) -> List[int]:
	"""Turns '1-3,5' into [1,2,3,5]"""
	ints = []
	for rangedesc in desc.split(','):
		if '-' in rangedesc:
			first, last = rangedesc.split('-', 1)
			ints.extend(range(int(first), int(last) + 1))
		else:
			ints.append(int(rangedesc))
	return ints


if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument('--chunksize', type=int, default=1_000_000, help='number of lines per chunk. Note that these chunks are read into memory when being shuffled')
	parser.add_argument('--threads', '-j', type=int, default=os.cpu_count(), help=f'number of concurrent shuffle threads. Defaults to {os.cpu_count()}')

	parser.add_argument('--unique', '-u', type=intlist, default=[], action='append', help='deduplicate output based on these columns. Eg. `1` means no src-trg pair will have the same src side, but trg side can occur more than once. Can be specified multiple times to deduplicate separately. E.g. -u 1 -u 2 will make both source and target sides always be unique')
	parser.add_argument('--delimiter', '-d', type=str, default='\t', help='delimiter for deduplication')
	  
	parser.add_argument('seed', type=int)
	parser.add_argument('output', type=FileType('wb', bufsize=BUFSIZE), default='-')
	parser.add_argument('files', nargs='+')

	args = parser.parse_args()

	# Read the lines
	it = chain.from_iterable(Reader(filename) for filename in args.files)

	# Deduplicate lines before shuffling to make sure the deduplication is
	# consistent regardless of the seed. Otherwise you might get different pairs
	# when the shuffled order changed.
	for column_list in args.unique:
		it = deduplicate(it, delimiter=args.delimiter.encode(), columns=column_list)
	
	# Shuffle the lines
	it = shuffle(it, lines=args.chunksize, seed=args.seed, threads=args.threads)

	args.output.writelines(it)
