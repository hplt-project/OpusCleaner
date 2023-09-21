import sys
import time
from collections import deque
from functools import wraps
from itertools import count
from json import JSONEncoder
from threading import Thread, get_ident, main_thread
from queue import SimpleQueue
from typing import Protocol, Iterable, Optional, TextIO
from uuid import uuid1, UUID
from contextlib import ExitStack


def iter_queue(queue):
	while True:
		task = queue.get()
		if task is None:
			break
		yield task


class Span:
	def __init__(self, logger, name, extra=dict()):
		self.logger = logger
		self.name = name
		self.extra =extra
		self.span = None

	def __enter__(self) -> 'Span':
		self.span = self.logger.push(self.name, **self.extra, type='span', start=time.monotonic_ns())
		return self

	def __exit__(self, typ, value, traceback) -> None:
		span = self.logger.pop()
		assert self.span == span
		self.logger.update(self.span, end=time.monotonic_ns(), error=repr(value) if value is not None else None)

	def event(self, name, **kwargs) -> UUID:
		return self.logger.event(name, type='event', parent=self.span, **kwargs)


class Handler(Protocol):
	def emit(self, record:dict) -> None:
		pass


class FallbackJSONEncoder(JSONEncoder):
	def default(self, obj):
		return str(obj)


class NullHandler(Handler):
	def emit(self, record:dict) -> None:
		pass


class StreamHandler(Handler):
	def __init__(self, stream):
		self.stream = stream
		self.encoder = FallbackJSONEncoder()

	def emit(self, record:dict) -> None:
		for chunk in self.encoder.iterencode(record):
			self.stream.write(chunk)
		self.stream.write('\n')


def _queue_to_handler(queue: SimpleQueue, handler: Handler):
	for record in iter_queue(queue):
		handler.emit(record)


class ThreadEmitter(Handler):
	def __init__(self, queue):
		self.queue = queue

	def emit(self, record:dict):
		self.queue.put(record)


class ThreadReceiver(Handler):
	def __init__(self, handler:Handler):
		self.handler = handler
		self.queue = SimpleQueue()

	def __enter__(self):
		self.thread = Thread(target=_queue_to_handler, args=[self.queue, self.handler])
		self.thread.start()
		return self

	def __exit__(self, *args):
		self.queue.put(None)
		self.thread.join()

	def make_handler(self):
		return ThreadEmitter(self.queue)


class Logger:
	handler: Handler
	serial: Iterable[int]
	stack: deque[UUID]

	def __init__(self, handler:Handler):
		self.handler = handler
		self.serial = count()
		self.stack = deque()

	def span(self, name:str, **kwargs) -> Span:
		return Span(self, name, kwargs)

	def event(self, name:str, **kwargs) -> UUID:
		event_id = uuid1(get_ident(), next(self.serial))
		self.handler.emit({
			'id': event_id,
			'parent': self.stack[-1] if len(self.stack) > 0 else None,
			'name': name,
			**kwargs,
		})
		return event_id

	def update(self, event_id:UUID, **kwargs) -> None:
		self.handler.emit({
			'id': event_id,
			**kwargs
		})

	def push(self, name:str, **kwargs) -> UUID:
		event_id = self.event(name, **kwargs)
		self.stack.append(event_id)
		return event_id

	def pop(self) -> UUID:
		return self.stack.pop()


_main_thread_id = main_thread().ident

_context = None


class Context:
	def __init__(self, *, file:Optional[TextIO]=None):
		if file:
			self.handler = StreamHandler(file)
		else:
			self.handler = NullHandler()

		self.receiver = ThreadReceiver(self.handler)

		self.loggers = {
			_main_thread_id: Logger(self.handler)
		}


	def get_logger(self):
		thread_id = get_ident()

		if thread_id not in self.loggers:
			self.loggers[thread_id] = Logger(self.receiver.make_handler())
			self.loggers[thread_id].stack = deque(self.loggers[_main_thread_id].stack) # TODO what about threads starting threads?

		return self.loggers[thread_id]

	def __enter__(self):
		global _context
		assert _context is None
		self.receiver.__enter__()
		_context = self
		return self

	def __exit__(self, *args, **kwargs):
		global _context
		assert _context is self
		self.receiver.__exit__()
		_context = None


def get_logger():
	return _context.get_logger()


def event(name:str, **kwargs) -> UUID:
	return get_logger().event(name, **kwargs)


def span(name:str, **kwargs) -> Span:
	return get_logger().span(name, **kwargs)


def trace(fn, name=None):
	if name is None:
		name = fn.__name__
	@wraps(fn)
	def wrapper(*args, **kwargs):
		with get_logger().span(name):
			return fn(*args, **kwargs)
	return wrapper


def trace_context(cls, name=None):
	if name is None:
		name = cls.__name__

	class Wrapper(cls):
		__span: Span

		def __enter__(self):
			self.__span = get_logger().span(name).__enter__()
			super().__enter__()
			return self

		def __exit__(self, *args, **kwargs):
			self.__span.event('__exit__')
			try:
				super().__exit__(*args, **kwargs)
			finally:
				self.__span.__exit__(*args, **kwargs)

	return Wrapper


def update(**kwargs):
	logger = get_logger()
	event_id = logger.stack[-1]
	logger.update(event_id, **kwargs)
