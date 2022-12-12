#!/usr/bin/env python3
import subprocess
import os
from shutil import which
from argparse import ArgumentParser, FileType
from itertools import islice, chain
from tempfile import mkstemp
from typing import TypeVar, Iterable, List, Optional
from queue import Queue
from threading import Thread
from dataclasses import dataclass
from random import Random


# Buffer size for reading files. Bufsize that Python assigns is generally too small?
BUFSIZE=2**16

# Prefer pigz if available, but fall back to calling gzip
PATH_TO_GZIP = which("pigz") or which("gzip")


T = TypeVar('T')

def chunked(iterable: Iterable[T], chunk_size:int) -> Iterable[List[T]]:
	"""Splits an iterable into shorter lists of a fixed length."""
	it = iter(iterable)
	while True:
		chunk = list(islice(it, chunk_size))
		if not chunk:
			break
		yield chunk


@dataclass(frozen=True)
class ShuffleTask:
	"""Job that describes to shuffle a chunk to the shuffle_chunk_worker thread.
	Passing along the seed created by the main thread because those
	random.random() calls are predictable. The order in which Shuffling tasks
	are picked up and finished may not be."""
	fileno: int
	seed: float
	chunk: List[bytes]


def shuffle_chunk_worker(queue:"Queue[Optional[ShuffleTask]]"):
	"""Worker thread that takes a queue of filenames and seeds, and shuffles them
	in memory. Put a None in the queue to make it stop."""
	while True:
		task = queue.get()

		if task is None:
			break

		random = Random(task.seed)

		with os.fdopen(task.fileno, 'wb', buffering=BUFSIZE) as fh:
			random.shuffle(task.chunk)
			fh.writelines(task.chunk)


def shuffle(fin: Iterable[bytes], lines:int, *, seed:Optional[int]=None, threads:int=1, tmpdir:Optional[str]=None) -> Iterable[bytes]:
	"""Shuffle a list by reading it into a bunch of files (of `lines` length)
	and shuffling all of these with `threads` in-memory shufflers."""
	random = Random(seed)

	# Limiting queue to 1 pending chunk otherwise we'll run out of memory quickly.
	queue: "Queue[Optional[ShuffleTask]]" = Queue(maxsize=threads)

	chunks: List[str] = []

	try:
		# Prepare shuffle workers to start shuffling chunks as soon as we've
		# finished writing them.
		shufflers = [
			Thread(target=shuffle_chunk_worker, args=[queue])
			for _ in range(threads)
		]

		try:
			for shuffler in shufflers:
				shuffler.start()

			# Split the input file into separate temporary chunks
			for chunk in chunked(fin, lines):
				fileno, filename = mkstemp(dir=tmpdir)
				# Remember the chunk's filename for later
				chunks.append(filename)
				# And immediately start shuffling & writing that chunk in another thread
				# so we can use this thread to continue ingesting chunks
				queue.put(ShuffleTask(fileno, random.random(), chunk))
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
		"""Open gzipped files through gzip subprocess. It is faster than Python's
		gzip submodule, and you get a bit of multiprocessing for free as the
		external gzip process can decompress up to BUFSIZE while python is doing
		other things."""
		assert PATH_TO_GZIP is not None, 'No gzip executable found on system'
		child = subprocess.Popen([PATH_TO_GZIP, '-cd', filename], stdout=subprocess.PIPE, bufsize=BUFSIZE)
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


if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument('--batch-size', type=int, default=1_000_000, help='number of lines per chunk. Note that these chunks are read into memory when being shuffled')
	parser.add_argument('--threads', '-j', type=int, default=2, help=f'number of concurrent shuffle threads. Defaults to 2')
	parser.add_argument('--temporary-directory', '-T', type=str, help='temporary directory for shuffling batches')
	parser.add_argument('seed', type=int)
	parser.add_argument('output', type=FileType('wb', bufsize=BUFSIZE), default='-')
	parser.add_argument('files', nargs='+')

	args = parser.parse_args()

	# Read the lines
	it = chain.from_iterable(Reader(filename) for filename in args.files)

	# Shuffle the lines
	it = shuffle(it, lines=args.batch_size, seed=args.seed, threads=args.threads, tmpdir=args.temporary_directory)

	args.output.writelines(it)
