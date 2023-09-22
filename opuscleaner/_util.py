from typing import TypeVar, Optional, Generic
from threading import Thread, Condition
from collections import deque
from queue import SimpleQueue


T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    if optional is None:
        raise AssertionError(message)
    return optional


def _thread_pool_worker(id:int, exc_queue:SimpleQueue, target, args, kwargs):
    try:
        target(*args, **kwargs)
        exc_queue.put((id, None))
    except Exception as exc:
        exc_queue.put((id, exc))


class ThreadPool:
    """Threadpool that can join() all started threads at the same time, but if
    any of those threads got caught in an exception, join() will reraise that
    exception as soon as it is received. It is then up to you to stop any other
    threads. This pool will wait for them when it exits the context.
    """
    def __init__(self):
        self.threads = {}
        self.queue = SimpleQueue()

    def start(self, func, *args, **kwargs):
        thread_id = len(self.threads)
        self.threads[thread_id] = Thread(
            target=_thread_pool_worker,
            kwargs={
                "id": thread_id,
                "exc_queue": self.queue,
                "target": func,
                "args": args,
                "kwargs": kwargs,
            },
            name=func.__name__)
        self.threads[thread_id].start()

    def join(self):
        while len(self.threads) > 0:
            thread_id, exc = self.queue.get()
            self.threads[thread_id].join()
            del self.threads[thread_id]
            if exc is not None:
                raise exc

    def __enter__(self):
        return self
    
    def __exit__(self, *args, **kwargs):
        for thread in self.threads.values():
            thread.join()
        self.threads = {}


class Cancelled(Exception):
    """Error raised by CancelableQueue's `put()` or `get()` when `cancel()` was
    called.
    """
    pass


T = TypeVar('T')

class CancelableQueue(Generic[T]):
    """SimpleQueue, but when cancel() is called it will release all blocking
    put() and get() calls and raise `Cancelled`. Also much worse performance
    than SimpleQueue so don't use for heavy workloads plz.
    """
    def __init__(self, capacity:Optional[int]=None):
        self.capacity = capacity
        self.size = 0
        self.queue = deque()
        self.cv = Condition()
        self.cancelled = False

    def put(self, item: T):
        """put() blocks until there's space on the queue. Can raise `Cancelled`
        when `cancel()` was called.
        """
        with self.cv:
            self.cv.wait_for(lambda: self.cancelled or self.capacity is None or self.size < self.capacity)
            if self.cancelled:
                raise Cancelled()
            self.queue.append(item)
            self.size += 1
            self.cv.notify()

    def get(self) -> T:
        """blocking get(). Either returns an item from the queue, or raises
        `Cancelled`.
        """
        with self.cv:
            self.cv.wait_for(lambda: self.cancelled or self.size > 0)
            if self.cancelled:
                raise Cancelled()
            self.size -= 1
            item = self.queue.popleft()
            self.cv.notify()
        return item
    
    def cancel(self):
        """Makes all calls to `get()` and `put()` raise `Cancelled()`."""
        with self.cv:
            self.cancelled = True
            self.cv.notify_all()    
