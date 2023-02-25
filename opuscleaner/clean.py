#!/usr/bin/env python3
"""Stand-alone filter pipeline runner. Executes all of the filters defined in
a dataset filtering pipeline created by empty-train in their own process and
links them together through pipes. Can read from stdin but by default reads
the dataset from the same folder as the pipeline configuration file.
"""
import argparse
import json
import os
import shlex
import signal
import sys
import traceback
from glob import glob
from pprint import pprint
from queue import Queue, SimpleQueue
from shlex import quote
from shutil import copyfileobj
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Thread
from typing import Dict, List, Any, BinaryIO, Optional, TypeVar, Iterable, Tuple, NamedTuple, Union

from .config import COL_PY


T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    if optional is None:
        raise AssertionError(message)
    return optional


def encode_env(type_name: str, value: Any) -> str:
    if type_name == 'bool':
        return '1' if value else ''
    else:
        return str(value)


def list_filters(path: str) -> Iterable[dict]:
    """Scans all files matching the path pattern and attempts to parse them as
    filter json definitions.
    """
    for filename in glob(path, recursive=True):
        try:
            with open(filename) as fh:
                defaults = {
                    "name": os.path.splitext(os.path.basename(filename))[0],
                    "basedir": os.path.dirname(filename)
                }
                yield {**defaults, **json.load(fh)}
        except Exception as e:
            print(f"Could not parse {filename}: {e}", file=sys.stderr)


def babysit_child(n: int, child: Popen, name: str, print_queue: SimpleQueue, ctrl_queue: SimpleQueue):
    """Thread that looks after a child process and passes (and prefixes) all of
    its stderr to a queue. It will tell the parent thread about the end of the
    child through the ctrl_queue.
    """
    prefix = f'[{name}] '.encode()

    for line in none_throws(child.stderr):
        print_queue.put(prefix + line)

    child.wait()

    print_queue.put(f'[run.py] {name} exited with status code {child.returncode}\n'.encode())

    ctrl_queue.put((n, child.returncode))


def print_lines(queue: SimpleQueue, fout: BinaryIO):
    """Thread that prints stderr lines from all the children to stderr in an
    orderly fashion.
    """
    while True:
        line = queue.get()
        if line is None:
            break
        fout.write(line)

        # Since we're writing stderr, we flush after each line to make it more
        # useful for debugging
        fout.flush()


T = TypeVar('T')

def mark_last(iterable: Iterable[T]) -> Iterable[Tuple[bool,T]]:
    it = iter(iterable)
    curr_el = next(it)
    while True:
        try:
            next_el = next(it)
            yield False, curr_el
            curr_el = next_el
        except StopIteration:
            break
    yield True, curr_el



class Child(NamedTuple):
    name: str
    process: Popen
    babysitter: Thread


class ProcessPipeline:
    """Context manager for spawning and babysitting child processes that are
    siblings connected by their pipes.
    """
    ctrl_queue: SimpleQueue

    print_queue: SimpleQueue

    environ: Dict[str,str]

    children: List[Child]

    def __init__(self, print_queue: SimpleQueue, *, env:Dict[str,str]={}):
        self.ctrl_queue = SimpleQueue()
        self.print_queue = print_queue
        self.environ = dict(env)
        self.children = []

    def start(self, name:str, cmd: Union[str,List[str]], **kwargs) -> Popen:
        child = Popen(cmd, **{
            **kwargs,
            'env': {
                **os.environ,
                **self.environ,
                **kwargs.get('env', dict())
            }
        })
        n = len(self.children)
        thread = Thread(target=babysit_child, args=[n, child, name, self.print_queue, self.ctrl_queue])
        thread.start()
        self.children.append(Child(name, child, thread))
        return child

    def __enter__(self):
        return self

    def __exit__(self, err_type, err_inst, err_trace):
        # Wait for the children to exit, and depending on their retval exit early
        running_children = len(self.children)

        print(f"Waiting for {running_children} subprocesses to finish...", file=sys.stderr)

        if err_type:
            for child in self.children:
                child.process.terminate()

        try:
            while running_children > 0:
                child_i, retval = self.ctrl_queue.get()
                running_children -= 1

                # Early exit when a process errored out. SIGPIPE is retuned by
                # processes that can no longer write to the next one. E.g. when
                # `head -n 10` stops reading because it has read its 10 lines.
                if retval not in (0, -signal.SIGPIPE):
                    break
        except KeyboardInterrupt:
            # TODO: Wait, how does the interrupt stop the children?
            print('[run.py] KeyboardInterrupt', file=sys.stderr)
            pass

        # If supported, print usage for each child?
        if False and os.path.isdir('/proc'):
            for child in children:
                with open(f'/proc/{child.process.pid}/stat', 'r') as fh:
                    sys.stderr.write(child.name + "\t")
                    sys.stderr.write(fh.readline())

        # Wait for all the processes to prevent zombies
        for child in self.children:
            if child.process.returncode is None:
                child.process.wait()

        # Wait for the babysitters to exit, which happens when their process stops
        for child in self.children:
            child.babysitter.join()

        # If we broke out of our ctrl_queue loop be clearly exited with an
        # issue, so let's mark that occasion by throwing.
        if running_children > 0 and not err_inst:
            raise Exception(f"Child {(child_i + 1)} {self.children[child_i].name} exited with {retval}")



class PipelineStep(NamedTuple):
    command: str
    basedir: str


class Pipeline:
    def __init__(self, filters: Dict[str,Dict], languages: List[str], pipeline: List[Dict]):
        self.steps: List[PipelineStep] = []

        # Assert we have all filters we need
        assert set(step['filter'] for step in pipeline['filters']) - set(filters.keys()) == set()

        for step in pipeline['filters']:
            filter_definition = filters[step['filter']]
            
            if filter_definition['type'] == 'bilingual':
                command = filter_definition['command']
            elif filter_definition['type'] == 'monolingual':
                column = languages.index(step['language'])
                command = f'{" ".join(map(shlex.quote, COL_PY))} {column} {filter_definition["command"]}'
            else:
                raise NotImplementedError()

            # List of k=v shell variable definitions
            filter_params = [
                '{}={}'.format(name, quote(encode_env(props['type'], step['parameters'].get(name, props.get('default', None)))))
                for name, props in filter_definition['parameters'].items()
            ]

            # Command, prefixed by variable definitions so they get expanded
            # correctly in the command bit.
            command_str = '; '.join(filter_params + [command])

            self.steps.append(PipelineStep(command_str, filter_definition['basedir']))

    def run(self, pool:ProcessPipeline, stdin:BinaryIO, stdout:BinaryIO, *, tee:bool=False, basename:str=""):
        for i, (is_last_step, step) in enumerate(mark_last(self.steps)):
        
            child = pool.start(f'step {i}', step.command,
                stdin=stdin,
                stdout=stdout if is_last_step and not tee else PIPE,
                stderr=PIPE,
                cwd=step.basedir,
                shell=True)

            # Close our reference to the previous child, now taken over by the next child
            stdin.close()
            
            # Set stdin for next step (unless there is none, then child.stdout is None)
            if not is_last_step and not tee:
                stdin = none_throws(child.stdout)

            pool.print_queue.put(f'[run.py] step {i}: Started {step.command}\n'.encode())

            # If we are tee-ing for debug, shunt the output to a separate file
            # TODO: uncompressed at the moment. Might be trouble.
            if tee:
                tee_child = pool.start(f'tee {i}',
                    ['tee', f'{basename}.step-{i}.tsv'],
                    stdin=stdin,
                    stdout=stdout if is_last_step else PIPE,
                    stderr=PIPE)

                stdin.close()
                stdin = none_throws(tee_child.stdout)


def split_input(print_queue:SimpleQueue, parallel: int, batch_queue: Queue, batch_size:int, stdin:BinaryIO):
    """Reads data from `stdin` and splits it into chunks of `batch_size` lines.
    These chunks are stored in temporary files, whose filenames are put onto
    `batch_queue`.
    """
    more = True

    batch_index = 0

    try:
        while more:
            fh = NamedTemporaryFile(delete=False)
            
            lines = 0

            while lines < batch_size:
                line = stdin.readline()
                if line == b'':
                    more = False
                    break
                fh.write(line)
                lines += 1
            
            fh.close()

            print_queue.put(f'[run.py] Wrote {lines} lines to batch {batch_index}: {fh.name}\n'.encode())
                
            if lines > 0:
                batch_queue.put((batch_index, fh.name))
            else:
                # Empty chunk because `len(stdin) % batch_size == 0`. No need
                # to process it further.
                os.unlink(fh.name)

            batch_index += 1
    finally:
        # In any scenario, tell all the runners there will be no more batches coming.
        for _ in range(parallel):
            batch_queue.put(None)


def run_pipeline(print_queue:SimpleQueue, batch_queue: Queue, merge_queue: SimpleQueue, pipeline: Pipeline):
    """Receives an input filename from `batch_queue`, and once that has been processed
    with `pipeline`, it will post the output filename to `merge_queue`.

    TODO: This could also instead run ./run.py on the input and output files
    directly as opposed to using `ProcessPipeline` + `pipeline.run()`.

    TODO: We can rewrite this to call `srun` on SLUM clusters so that the
    actual filtering pipeline is executed on a different node. Since input
    and output are just files on the same filesystem (depends on TMPDIR) this
    should pretty much work out of the box :O
    """
    try:
        with TemporaryDirectory() as tmpdir:
            while True:
                entry = batch_queue.get()

                # If the batcher told us they're out of batches, stop.
                if entry is None:
                    break

                batch_index, filename = entry

                try:
                    # Write pipeline output to tempfile that is then passed on to merger.
                    stdout = NamedTemporaryFile(delete=False)

                    print_queue.put(f'[run.py] Filtering chunk {filename} to {stdout.name}\n'.encode())

                    # Open chunk file and process pool and run the pipeline with it.
                    with open(filename, 'rb') as stdin, ProcessPipeline(print_queue, env={'TMPDIR': tmpdir}) as pool:
                        pipeline.run(pool, stdin, stdout)

                    stdout.close()

                    # Tell merger that they can process this batch when the time comes
                    merge_queue.put((batch_index, stdout.name))
                finally:
                    # Delete the input file from disk.
                    os.unlink(filename)
    finally:
        # In any case, tell the merger that they should not be expecting more
        # input from you.
        merge_queue.put(None)


def merge_output(print_queue:SimpleQueue, parallel: int, merge_queue: SimpleQueue, stdout:BinaryIO):
    """Takes batch filenames and numbers from `merge_queue` and will concatenate
    files in the order of the batches. If batches arrive out of order, it will
    wait for the next in order batch to arrive before continuing to concatenate.
    """
    next_batch_index = 0

    pending_batches: Dict[int, str] = {}

    while True:
        # If we have the next batch, start processing it into the final output
        if next_batch_index in pending_batches:
            batch_index, filename = next_batch_index, pending_batches[next_batch_index]

            print_queue.put(f'[run.py] Merging {filename} into output\n'.encode())
            
            with open(filename, 'rb') as fh:
                copyfileobj(fh, stdout)

            os.unlink(filename)

            next_batch_index += 1
        # If not yet, we wait on the queue to come through with (hopefully) the next batch
        else:
            entry = merge_queue.get()

            if entry is None:
                parallel -= 1

                if parallel == 0:
                    break
                else:
                    continue

            batch_index, filename = entry

            assert batch_index not in pending_batches
            pending_batches[batch_index] = filename


def run_parallel(pipeline:Pipeline, stdin:BinaryIO, stdout:BinaryIO, *, parallel:int, batch_size:int, print_queue: SimpleQueue):
    batch_queue = Queue(parallel * 2)

    merge_queue = SimpleQueue()

    # Splits stdin into files of `batch_size` lines, and puts those on `batch_queue`
    splitter = Thread(target=split_input, args=[print_queue, parallel, batch_queue, batch_size, stdin])
    splitter.start();

    # Read `batch_queue` for batch filenames, and process them. Put output files
    # on `merge_queue`.
    runners = [
        Thread(target=run_pipeline, args=[print_queue, batch_queue, merge_queue, pipeline])
        for _ in range(parallel)
    ]

    for runner in runners:
        runner.start()

    # Read from `merge_queue` and combine files in order.
    merger = Thread(target=merge_output, args=[print_queue, parallel, merge_queue, stdout])
    merger.start()

    # TODO: problem. Say the runners crash. The splitter is then stuck blocking
    # on Queue.put (because of size limit) and doesn't know that it should stop.
    # We then block on the splitter.join() call here. Maybe I should not be
    # using a blocking size-limited Queue() to control the splitter's progress
    # but a SimpleQueue() that sends messages.

    print_queue.put(f'[run.py] Waiting for splitter to finish\n'.encode())
    splitter.join()

    print_queue.put(f'[run.py] Waiting for pipelines to finish\n'.encode())
    for runner in runners:
        runner.join()

    print_queue.put(f'[run.py] Waiting for merger to finish\n'.encode())
    merger.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--filters', '-f', type=str, default='./filters', help='Path to directory with filter specifications')
    parser.add_argument('--input', '-i', type=argparse.FileType('rb'), help='Input tsv. If unspecified input files are read from filter json; use - to read from stdin')
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'), default=sys.stdout.buffer, help='Output tsv (defaults to stdout)')
    parser.add_argument('--basedir', '-b', type=str, help='Directory to look for data files when --input is not used (defaults to same as input pipeline file)')
    parser.add_argument('--tee', action='store_true', help='Write output after each step to a separate file')
    parser.add_argument('--parallel', type=int, default=1, help='Run N parallel copies of the pipeline processing batches')
    parser.add_argument('--batch-size', type=int, default=1_000_000, help='Batch size in lines that each parallel copy processes (only if --parallel > 1)')
    parser.add_argument('--first', type=int, default=0, help='Limit reading input to the N first lines')
    parser.add_argument('pipeline', metavar='PIPELINE', type=argparse.FileType('r'), help='Pipeline steps specification file, e.g. *.filters.json')
    parser.add_argument('languages', metavar='LANG', type=str, nargs='*', help='Language codes of the columns in the input TSV. Only used when --input is set')

    args = parser.parse_args()

    # default search path for the data files is next to the configuration file
    # which is the default save location for empty-train.
    if not args.basedir:
        args.basedir = os.path.dirname(args.pipeline.name)

    if args.input is not None and not args.languages:
        parser.error('When --input is specified, each colum\'s LANG has to be specified as well.')

    pipeline_config = json.load(args.pipeline)

    # load all filter definitions (we need to, to get their name)
    FILTERS = {
        definition['name']: definition
        for definition in list_filters(os.path.join(args.filters, '*.json'))
    }

    # Queue filled by the babysitters with the stderr of the children, consumed
    # by `print_lines()` to prevent racing on stderr.
    print_queue = SimpleQueue() # type: SimpleQueue[Optional[bytes]]

    # First start the print thread so that we get immediate feedback from the
    # children even if all of them haven't started yet.
    print_thread = Thread(target=print_lines, args=[print_queue, sys.stderr.buffer])
    print_thread.start()

    # Order of columns. Matches datasets.py:list_datasets(path)
    languages: List[str] = args.languages if args.input else [filename.rsplit('.', 2)[1] for filename in pipeline_config['files']]

    # Directory plus basename to write debug (`--tee`) files to
    basename: str = 'stdin' if args.input else os.path.commonprefix(pipeline_config['files']).rstrip('.')

    pipeline = Pipeline(FILTERS, languages, pipeline_config)

    # Input for next child
    stdin: BinaryIO

    # Output of this program
    stdout:BinaryIO = args.output

    # Start child processes, each reading the output from the previous sibling
    try:
        with ProcessPipeline(print_queue) as pool:
            # If we're not reading from stdin, read from files and paste them together
            if args.input:
                stdin = sys.stdin.buffer
            else:
                # Open `gzunip` for each language file
                gunzips = [
                    pool.start(f'gunzip {filename}',
                        ['gzip', '-cd', filename],
                        stdout=PIPE,
                        stderr=PIPE,
                        cwd=args.basedir)
                    for filename in pipeline_config['files']
                ]

                fds = [none_throws(gunzip.stdout).fileno() for gunzip in gunzips]

                # .. and a `paste` to combine them into columns
                paste = pool.start('paste',
                    ['paste'] + [f'/dev/fd/{fd}' for fd in fds],
                    stdout=PIPE,
                    stderr=PIPE,
                    pass_fds=fds)

                # Now that `paste` has inherited all the children, close our connection to them
                for gunzip in gunzips:
                    none_throws(gunzip.stdout).close()

                stdin = none_throws(paste.stdout)

                # If we only want the first N lines processed, use `head` to chop those off.
                if args.first > 0:
                    head = pool.start('head',
                        ['head', '-n', str(args.first)],
                        stdin=stdin,
                        stdout=PIPE,
                        stderr=PIPE)

                    stdin.close() # now taken over by `head`.
                    stdin = none_throws(head.stdout)

                if args.parallel > 1:
                    run_parallel(pipeline, stdin, stdout, print_queue=print_queue, parallel=args.parallel, batch_size=args.batch_size)
                else:
                    pipeline.run(pool, stdin, stdout, tee=args.tee, basename=basename)
    except:
        # If we didn't cleanly exit all processes, we err as well
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        # Tell print thread to stop (there are no more babysitters now to produce printable stuff)
        print_queue.put(None)
        print_thread.join()


if __name__ == '__main__':
    main()
