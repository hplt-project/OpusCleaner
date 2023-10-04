#!/usr/bin/env python3
import sys
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import Optional, TypeVar


queue = SimpleQueue() # type: SimpleQueue[list[bytes]]

T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
	if optional is None:
		raise AssertionError(message)
	return optional


class RaisingThread(Thread):
	"""Thread that will raise any uncaught exceptions in the thread in the
	parent once it joins again."""

	exception: Optional[Exception]

	def run(self):
		self.exception = None
		try:
			super().run()
		except Exception as exc:
			self.exception = exc

	def join(self, timeout:Optional[float]=None):
		super().join(timeout=timeout)
		if self.exception is not None:
			raise self.exception


def split(column, queue, fin, fout):
	try:
		field_count = None
		for line in fin:
			fields = line.rstrip(b'\r\n').split(b'\t')
			if field_count is None:
				field_count = len(fields)
			elif field_count != len(fields):
				raise RuntimeError(f'line contains a different number of fields: {len(fields)} vs {field_count}')
			field = fields[column] # Doing column selection first so that if this fails, we haven't already written it to the queue
			queue.put(fields[:column] + fields[(column+1):])
			fout.write(field + b'\n')
	except BrokenPipeError:
		pass
	finally:
		try:
			fout.close() # might fail if BrokenPipeError
		except:
			pass
		queue.put(None) # End indicator
		fin.close()

def merge(column, queue, fin, fout):
	try:
		for field in fin:
			fields = queue.get()
			if fields is None:
				raise RuntimeError('subprocess produced more lines of output than it was given')
			fout.write(b'\t'.join(fields[:column] + [field.rstrip(b'\n')] + fields[column:]) + b'\n')
		if queue.get() is not None:
			raise RuntimeError('subprocess produced fewer lines than it was given')
		fout.close()
	except BrokenPipeError:
		pass
	finally:
		fin.close()


def main():
	retval = 0

	try:
		column = int(sys.argv[1])

		child = Popen(sys.argv[2:], stdin=PIPE, stdout=PIPE)

		feeder = RaisingThread(target=split, args=[column, queue, sys.stdin.buffer, none_throws(child).stdin])
		feeder.start()

		consumer = RaisingThread(target=merge, args=[column, queue, none_throws(child).stdout, sys.stdout.buffer])
		consumer.start()

		retval = child.wait()
		
		if retval != 0:
			raise RuntimeError(f'subprocess exited with status code {retval}')

		feeder.join()
		consumer.join()
	except Exception as e:
		print(f'Error: {e}', file=sys.stderr)
		sys.exit(retval or 1)


if __name__ == '__main__':
	main()
