#!/usr/bin/env python3
import sys
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import BinaryIO, Optional, TypeVar, List


queue = SimpleQueue() # type: SimpleQueue[None|list[bytes]]

T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
	if optional is None:
		raise AssertionError(message)
	return optional


def parse_columns(text:str) -> List[int]:
	return sorted(int(col) for col in text.split(','))


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


def split(columns:List[int], queue:'SimpleQueue[None|list[bytes]]', fin:BinaryIO, fout:BinaryIO):
	try:
		field_count = None
		passthru_columns = []
		for line in fin:
			fields = line.rstrip(b'\r\n').split(b'\t')
			if field_count is None:
				field_count = len(fields)
				passthru_columns = [n for n in range(field_count) if n not in columns]
			elif field_count != len(fields):
				raise RuntimeError(f'line contains a different number of fields: {len(fields)} vs {field_count}')
			queue.put([fields[column] for column in passthru_columns])
			for column in columns:
				fout.write(fields[column] + b'\n')
	except BrokenPipeError:
		pass
	finally:
		try:
			fout.close() # might fail if BrokenPipeError
		except:
			pass
		queue.put(None) # End indicator
		fin.close()


def merge(columns:List[int], queue:'SimpleQueue[None|list[bytes]]', fin:BinaryIO, fout:BinaryIO):
	try:
		while True:
			passthru_fields = queue.get()
			if passthru_fields is None:
				if fin.readline() != b'':
					raise RuntimeError('subprocess produced more lines of output than it was given')
				break

			passthru_it = iter(passthru_fields)
			for column in range(len(passthru_fields) + len(columns)):
				if column in columns:
					field = fin.readline()
					if field == b'':
						raise RuntimeError('subprocess produced fewer lines than it was given')
					field = field.rstrip(b'\r\n')
				else:
					field = next(passthru_it)

				if column > 0:
					fout.write(b'\t')
				fout.write(field)
			fout.write(b'\n')
	except BrokenPipeError:
		pass
	finally:
		fout.close()
		fin.close()


def main():
	retval = 0

	try:
		columns = parse_columns(sys.argv[1])

		child = Popen(sys.argv[2:], stdin=PIPE, stdout=PIPE)

		feeder = RaisingThread(target=split, args=[columns, queue, sys.stdin.buffer, none_throws(child).stdin])
		feeder.start()

		consumer = RaisingThread(target=merge, args=[columns, queue, none_throws(child).stdout, sys.stdout.buffer])
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
