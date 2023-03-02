#!/usr/bin/env python3
import sys
import os
import signal
from traceback import print_exc
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import Optional, TypeVar, List
from functools import wraps


queue = SimpleQueue() # type: SimpleQueue[list[bytes]]

T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    if optional is None:
        raise AssertionError(message)
    return optional


def split(column, queue, fin, fout):
	try:
		for line in fin:
			fields = line.rstrip(b'\n').split(b'\t')
			field = fields[column] # Doing column selection first so that if this fails, we haven't already written it to the queue
			queue.put(fields[:column] + fields[(column+1):])
			fout.write(field + b'\n')
		fout.close()
	except BrokenPipeError:
		pass
	finally:
		queue.put(None) # End indicator
		fin.close()

def merge(column, queue, fin, fout):
	try:
		for field in fin:
			fields = queue.get()
			if fields is None:
				raise RuntimeError('Subprcess produced more lines of output than it was given.')
			fout.write(b'\t'.join(fields[:column] + [field.rstrip(b'\n')] + fields[column:]) + b'\n')
		if queue.get() is not None:
			raise RuntimeError('Subprocess produced fewer lines than it was given.')
		fout.close()
	except BrokenPipeError:
		pass
	finally:
		fin.close()


def main():
	column = int(sys.argv[1])

	child = Popen(sys.argv[2:], stdin=PIPE, stdout=PIPE)

	try:
		feeder = Thread(target=split, args=[column, queue, sys.stdin.buffer, none_throws(child).stdin])
		feeder.start()

		consumer = Thread(target=merge, args=[column, queue, none_throws(child).stdout, sys.stdout.buffer])
		consumer.start()

		feeder.join()
		consumer.join()
	except:
		none_throws(child.stdin).close()
		raise
	finally:
		sys.stderr.close()
		# Whatever happens, make sure the child stops first otherwise we might
		# end up with a zombie
		retval = child.wait()
		sys.exit(retval)


if __name__ == '__main__':
	main()
