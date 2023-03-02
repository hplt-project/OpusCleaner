import sys
import os
import json
from collections import deque
from opusfilter import FilterABC, PreprocessorABC, ConfigurationError
from queue import SimpleQueue
from shlex import quote
from subprocess import Popen, PIPE
from threading import Thread
from typing import Optional, Dict, Any
from xxhash import xxh32


def encode_env(type_name: str, value: Any) -> str:
    if type_name == 'bool':
        return '1' if value else ''
    else:
        return str(value)


def load_filter_definition(filter_name:str) -> Dict:
    with open('filters/{filter_name}.json') as fh:
            return json.load(fh)


def generate_filter_command(filter_definition:Dict, parameters:Dict) -> str:
    filter_definition = filters[step['filter']]

    # List of k=v shell variable definitions
    filter_params = [
            '{}={}'.format(name, quote(encode_env(props['type'], parameters.get(name, props.get('default', None)))))
            for name, props in filter_definition['parameters'].items()
    ]

    # Command, prefixed by variable definitions so they get expanded
    # correctly in the command bit.
    return '; '.join(filter_params + [filter_definition['command']])


def patch_environ() -> Optional[Dict[str,str]]:
    # Make sure the path to the python binary (and the installed utils)
    # is in the PATH variable. If you load a virtualenv this happens by
    # default, but if you call it with the virtualenv's python binary 
    # directly it wont.
    pyenv_bin_path = os.path.dirname(sys.executable)
    os_env_bin_paths = os.environ.get('PATH', '').split(os.pathsep)
    return {
            **os.environ,
            'PATH': os.pathsep.join([pyenv_bin_path] + os_env_bin_paths)
    } if pyenv_bin_path not in os_env_bin_paths else None


def feed_child_worker(input_queue:SimpleQueue, stdin):
    while True:
        line = input_queue.pop()
        if line is None:
            break
        stdin.write(line.encode() + b'\n')
    stdin.close()


def read_child_worker(stdout, output_queue:SimpleQueue):
    for line in stdout:
        output_queue.put(line.rstrip(b'\r\n').decode())
    output_queue.put(None)


class OpusCleanerPreprocessor(PreprocessorABC):
    def __init__(self, filter:str, parameters:Dict[str,Any], column:int, **kwargs):
        filter_definition = load_filter_definition(filter)
        if filter_definition['type'] != 'monolingual':
            raise ConfigurationError()

        self.command = generate_filter_command(filter_definition, parameters)
        self.column = column
        super().__init__(**kwargs)

    def process(self, pairs):
        # Single column python -> child
        input_queue = SimpleQueue()
        # Single column child -> python
        output_queue = SimpleQueue()
        # Remainder of the columns python -> python
        column_queue = deque()

        child = Popen(self.command, cwd=basedir, stdin=PIPE, stdout=PIPE, env=patch_environ())

        feeder = Thread(target=feed_child_worker, args=[input_queue, child.stdin])
        feeder.start()

        reader = Thread(target=read_child_worker, args=[child.stdout, output_queue])
        reader.start()

        def split(pair):
            column_queue.append(pair[:self.column] + pair[self.column+1:])
            return pair[self.column]

        def merge(val):
            rest = column_queue.popleft()
            return rest[:self.column] + [val] + rest[self.column:]

        for pair in pairs:
            # Push input pair
            input_queue.put(split(pair))

            # Yield any available output pairs
            while True:
                try:
                    yield merge(output_queue.get_nowait())
                except Empty:
                    break
        
        # Signal worker to stop
        input_queue.put(None)
        feeder.join()

        # Yield remaining output pairs
        while True:
            pair = output_queue.get()
            if pair is not None:
                yield merge(pair)
            else:
                break

        retval = child.wait()
        reader.join()

        if retval != 0:
            raise Exception(f'Child process {command} exited with non-zero exit code: {retval}')

        assert len(column_queue) == 0


class OpusCleanerFilter(FilterABC):
    """One Big Hack (Tm)"""

    def __init__(self, filter:str, parameters:Dict[str,Any], **kwargs):
        filter_definition = load_filter_definition(filter)
        if filter_definition['type'] != 'bilingual':
            raise ConfigurationError()

        self.command = generate_filter_command(filter_definition, parameters)
        super().__init__(**kwargs)

    def accept(self, score):
        return bool(score)

    def score(self, pairs):
        input_queue = SimpleQueue()
        output_queue = SimpleQueue()
        
        input_log = deque()
        
        child = Popen(self.command, cwd=basedir, stdin=PIPE, stdout=PIPE, env=patch_environ())

        feeder = Thread(target=feed_child_worker, args=[input_queue, child.stdin])
        feeder.start()

        reader = Thread(target=read_child_worker, args=[child.stdout, output_queue])
        reader.start()

        def record(pair):
            """Record the hash of the line so we know whether it makes it through the filter"""
            line = '\t'.join(pair)
            input_log.append(xxh32(line).digest())
            return line

        def catch_up(line):
            """Yield 0 for all the lines that got skipped by the filter"""
            key = xxh32(line).digest()
            while column_queue.popleft() != key:
                yield 0
            yield 1

        for pair in pairs:
            # Push input pair
            input_queue.put(record(pair))

            # Yield any available output pairs
            while True:
                try:
                    yield from catch_up(output_queue.get_nowait())
                except Empty:
                    break
        
        # Signal worker to stop
        input_queue.put(None)
        feeder.join()

        # Yield remaining output pairs
        while True:
            pair = output_queue.get()
            if pair is not None:
                yield from catch_up(pair)
            else:
                break

        retval = child.wait()
        reader.join()

        if retval != 0:
            raise Exception(f'Child process {command} exited with non-zero exit code: {retval}')

        assert len(column_queue) == 0
