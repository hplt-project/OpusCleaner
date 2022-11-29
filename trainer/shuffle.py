#!/usr/bin/env python3
import subprocess
import sys
import os
from argparse import ArgumentParser, FileType
from itertools import islice, chain
from tempfile import mkstemp
from typing import TypeVar, Iterable, List, Optional
from queue import SimpleQueue
from threading import Thread
from dataclasses import dataclass
from random import Random

# Buffer size for reading files. Bufsize that Python assigns is generally too small?
BUFSIZE=2**16

T = TypeVar('T')

def chunked(iterable: Iterable[T], chunk_size:int) -> Iterable[Iterable[T]]:
	try:
		it = iter(iterable)
		while True:
			has_next = next(it)
			yield chain([has_next], islice(it, chunk_size - 1))
	except StopIteration:
		pass


def split(fh: Iterable[bytes], lines:int, dir=None) -> Iterable[str]:
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
	seed: float
	filename: str


def shuffle_chunk(queue:SimpleQueue[Optional[ShuffleTask]]):
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
	random = Random(seed)

	queue: SimpleQueue[Optional[ShuffleTask]] = SimpleQueue()

	chunks: List[str] = []

	try:
		shufflers = [
			Thread(target=shuffle_chunk, args=[queue])
			for _ in range(threads if threads is not None else 1)
		]

		try:
			for shuffler in shufflers:
				shuffler.start()

			for filename in split(fin, lines):
				chunks.append(filename)
				queue.put(ShuffleTask(random.random(), filename))
		finally:
			# Tell shufflers that they can stop waiting
			for _ in shufflers:
				queue.put(None)

			# Wait for them to finish shuffling the last files
			for shuffler in shufflers:
				shuffler.join()

		chunk_fds = [open(filename, 'rb', buffering=BUFSIZE) for filename in chunks]

		while chunk_fds:
			fd = random.choice(chunk_fds)
			line = fd.readline()
			if line == b'':
				fd.close()
				chunk_fds.remove(fd)
				continue
			yield line
	finally:
		for filename in chunks:
			if os.path.exists(filename):
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


if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument('--chunksize', type=int, default=1_000_000)
	parser.add_argument('--threads', '-j', type=int, default=os.cpu_count())
	parser.add_argument('seed', type=int)
	parser.add_argument('output', type=FileType('wb', bufsize=BUFSIZE), default='-')
	parser.add_argument('files', nargs='+')

	args = parser.parse_args()

	args.output.writelines(shuffle(
		chain.from_iterable(Reader(filename) for filename in args.files),
		lines=args.chunksize,
		seed=args.seed,
		threads=args.threads))
