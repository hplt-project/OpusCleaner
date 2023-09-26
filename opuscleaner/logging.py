import time
from collections import deque
from functools import wraps
from itertools import count
from json import JSONEncoder
from threading import Thread, get_ident, main_thread
from queue import SimpleQueue
from typing import Callable, Protocol, Iterator, Optional, IO, Type, TypeVar
from uuid import uuid1, UUID


def iter_queue(queue):
	while True:
		task = queue.get()
		if task is None:
			break
		yield task


class Span:
	"""Log the duration (enter and exit) of a set of instructions"""

	def __init__(self, logger:'Logger', name:str, extra:dict=dict()):
		self.logger = logger
		self.name = name
		self.extra = extra
		self.span = None

	def __enter__(self) -> 'Span':
		self.span = self.logger.push(self.name, **self.extra, type='span', start=time.monotonic_ns())
		return self

	def __exit__(self, typ, value, traceback):
		assert self.span is not None
		span = self.logger.pop()
		assert self.span == span
		self.logger.update(self.span, end=time.monotonic_ns(), error=repr(value) if value is not None else None)

	def event(self, name, **kwargs) -> UUID:
		return self.logger.event(name, type='event', parent=self.span, **kwargs)


class Handler(Protocol):
	"""Handler receives log records to handle. For example, by writing them as
	JSON to a file, or putting them on a queue to be processed in another thread.
	"""
	def emit(self, record:dict) -> None:
		pass


class FallbackJSONEncoder(JSONEncoder):
	"""JSONEncoder that just calls `str(obj)` in case it has no built-in
	conversion for the type."""
	def default(self, obj):
		return str(obj)


class NullHandler(Handler):
	"""Handler that does nothing, like printing to /dev/null."""
	def emit(self, record:dict) -> None:
		pass


class StreamHandler(Handler):
	"""Writes log records as JSON lines to a file."""
	def __init__(self, stream:IO[str]):
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
	"""Handler that puts log records onto a queue"""
	def __init__(self, queue):
		self.queue = queue

	def emit(self, record:dict):
		self.queue.put(record)


class ThreadReceiver:
	"""Context manager that will run a thread in the background to capture log
	records emitted by ThreadEmitter handlers, and forward them to a single
	handler. Make these emitters through `make_hander()`.
	Note that the handler is run in another thread, so if your handler is writing
	to say stderr and you're also writing to stderr on the main thread, you will
	need to do some coordination through locking.
	"""
	def __init__(self, handler:Handler):
		self.handler = handler
		self.queue = SimpleQueue()

	def __enter__(self):
		self.thread = Thread(target=_queue_to_handler, args=[self.queue, self.handler])
		self.thread.start()
		return self

	def __exit__(self, typ, value, traceback):
		self.queue.put(None)
		self.thread.join()

	def make_handler(self) -> Handler:
		return ThreadEmitter(self.queue)


class Logger:
	"""Logger object that tracks the stack when using spans."""
	handler: Handler
	serial: Iterator[int]
	stack: deque[UUID]

	def __init__(self, handler:Handler):
		self.handler = handler
		self.serial = count()
		self.stack = deque()

	def span(self, name:str, **kwargs) -> Span:
		"""Start recording a span. Use as context `with logger.span('name'):`"""
		return Span(self, name, kwargs)

	def event(self, name:str, **kwargs) -> UUID:
		"""Record a singular event. If inside the context of a span, the event will
		be associated with that span."""
		event_id = uuid1(get_ident(), next(self.serial))
		self.handler.emit({
			'id': event_id,
			'parent': self.stack[-1] if len(self.stack) > 0 else None,
			'name': name,
			**kwargs,
		})
		return event_id

	def update(self, event_id:UUID, **kwargs) -> None:
		"""Update a particular event, e.g. to add more context."""
		self.handler.emit({
			'id': event_id,
			**kwargs
		})

	def push(self, name:str, **kwargs) -> UUID:
		"""Emit an event and put it onto the stack. Same a `span().__enter__()`, it
		is better to use `with span():` in most cases."""
		event_id = self.event(name, **kwargs)
		self.stack.append(event_id)
		return event_id

	def pop(self) -> UUID:
		"""Pops event of the stack."""
		return self.stack.pop()


_main_thread_id = main_thread().ident

_context = None


class Context:
	"""Logging context. This deals with having multiple loggers on multiple 
	threads all combine into the same event stream.
	Generally you'd have something like `with logger.Context() as ctx: main()`
	in your app. You can access the current context's logger through
	`logger.get_logger()` as well as `ctx.get_logger()`.
	"""
	def __init__(self, *, file:Optional[IO[str]]=None):
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

	def __exit__(self, typ, value, traceback):
		global _context
		assert _context is self
		self.receiver.__exit__(typ, value, traceback)
		_context = None


def get_logger() -> Logger:
	"""Shortcut for Context().get_logger()"""
	if _context is None:
		raise RuntimeError('called get_logger() outside logging context')
	return _context.get_logger()


def event(name:str, **kwargs) -> UUID:
	"""Shortcut for get_logger().event()"""
	return get_logger().event(name, **kwargs)


def update(**kwargs):
	"""Shortcut for get_logger().update(current_span, ...)"""
	logger = get_logger()
	event_id = logger.stack[-1]
	logger.update(event_id, **kwargs)


def span(name:str, **kwargs) -> Span:
	"""Shortcut for get_logger().span()"""
	return get_logger().span(name, **kwargs)


# TODO: once Python3.11:
# P = ParamSpec('P')
# R = TypeVar('R')
# def trace(fn:Callable[P,R]) -> Callable[P,R]

T = TypeVar('T', bound=Callable)

def trace(fn:T) -> T:
	"""Decorator for wrapping each call to this function with
	```
	with get_logger().span(__name__):
    fn()
	```
	"""
	@wraps(fn)
	def wrapper(*args, **kwargs):
		with get_logger().span(fn.__name__):
			return fn(*args, **kwargs)
	return wrapper # type:ignore


T = TypeVar('T')

def trace_context(cls:Type[T]) -> Type[T]:
	"""Similar to `@trace`, but for a class with __enter__ and __exit__."""
	class Wrapper(cls):
		__span: Span

		def __enter__(self):
			self.__span = get_logger().span(cls.__name__).__enter__()
			return super().__enter__()

		def __exit__(self, typ, value, traceback):
			# add an __exit__ event to make it possible to measure how long the
			# wrapped __exit__ actually takes.
			self.__span.event('__exit__')
			try:
				super().__exit__(typ, value, traceback)
			finally:
				self.__span.__exit__(typ, value, traceback)

	return Wrapper
