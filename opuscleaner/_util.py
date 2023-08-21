from typing import TypeVar, Optional
from threading import Thread

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

    def join(self, timeout:float=None):
        super().join(timeout=timeout)
        if self.exception is not None:
            raise self.exception
