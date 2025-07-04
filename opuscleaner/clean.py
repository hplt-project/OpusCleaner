#!/usr/bin/env python3
"""Stand-alone filter pipeline runner. Executes all of the filters defined in
a dataset filtering pipeline created by empty-train in their own process and
links them together through pipes. Can read from stdin but by default reads
the dataset from the same folder as the pipeline configuration file.
"""
import argparse
import json
import os
import re
import signal
import sys
import traceback
from queue import SimpleQueue
from shlex import quote
from shutil import copyfileobj
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Thread
from typing import Dict, List, IO, Optional, TypeVar, Iterable, Tuple, NamedTuple, Union
from io import TextIOWrapper

from pydantic import parse_obj_as

from opuscleaner import logging
from opuscleaner.config import FILTER_PATH
from opuscleaner.filtering import list_filters, set_global_filters, filter_format_command, Filter, FilterPipeline, quote, format_shell
from opuscleaner._util import none_throws, ThreadPool, CancelableQueue, Cancelled


# Queue for printing lines to stdout or stderr. None means end of input.
PrintQueue = SimpleQueue[Union[None,bytes]]

# Control queue for communicating the return code of a child back to the parent.
ControlQueue = SimpleQueue[Tuple[int,int]]

# Batches to be processed. tuple[batch index,batch path]. None means end of input.
# Using a Queue here to limit the maximum capacity.
BatchQueue = CancelableQueue[Union[None,Tuple[int,str]]]

# Batches to be merged. Same format as BatchQueue
MergeQueue = CancelableQueue[Union[None,Tuple[int,str]]]


def load_time(fh:IO[str]) -> Dict[str,float]:
    time = {}
    for line in fh:
        match = re.match(r'^(real|user|sys)\s+(\d+\.\d+)$', line.rstrip('\r\n'))
        if match:
            time[match[1]] = float(match[2])
    return time


@logging.trace
def babysit_child(n: int, child: Popen, name: str, print_queue: PrintQueue, ctrl_queue: ControlQueue, time_read_fd:Optional[int]=None) -> None:
    """Thread that looks after a child process and passes (and prefixes) all of
    its stderr to a queue. It will tell the parent thread about the end of the
    child through the ctrl_queue.
    """
    try:
        logging.update(n=n, pid=child.pid, args=child.args)

        prefix = f'[{name}] '.encode()

        for line in none_throws(child.stderr):
            print_queue.put(prefix + line)

        child.wait()

        logging.event('child_exited', retval=child.returncode)

        # If the command was wrapped by `time`, we want to read its output as
        # well. It's written to a separate pipe as to not end up in the stderr
        # of the main command.
        if time_read_fd is not None:
            with os.fdopen(time_read_fd, 'r') as fh:
                logging.update(time=load_time(fh))
    finally:
        ctrl_queue.put((n, child.returncode))


def print_lines(queue: PrintQueue, fout: IO[bytes]) -> None:
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


@logging.trace_context
class ProcessPool:
    """Context manager for spawning and babysitting child processes that are
    siblings connected by their pipes. Exiting the context will cause it to
    block and wait for the children to finish.
    If any of the children exits early or with an error, or there was an
    uncaught exception inside the context, it will terminate all the other
    processes in the pool and raise an exception on exit. SIGPIPE errors, and
    errors caused by the pool terminating the process, are ignored.
    """
    print_prefix: str

    ctrl_queue: ControlQueue

    print_queue: PrintQueue

    environ: Dict[str,str]

    children: List[Child]

    def __init__(self, print_queue: PrintQueue, *, env:Dict[str,str]={}, print_prefix:str=''):
        self.print_prefix = print_prefix
        self.ctrl_queue = SimpleQueue()
        self.print_queue = print_queue
        self.environ = dict(env)
        self.children = []

    def start(self, name:str, cmd: Union[str,List[str]], *, shell:bool=False, time:bool=False, **kwargs) -> Popen:
        """Set up a process in the pool. Similar to Popen. `name` is used for
        identifying the process in log messages and exceptions. `time` can be
        set to True to wrap the process in `/usr/bin/time`. Furthermore all
        arguments to `Popen` are accepted.
        """
        time_read_fd, time_write_fd = None, None

        args = ([cmd] if isinstance(cmd, str) else cmd)
        
        if shell:
            args = ['/bin/sh', '-c', *args] # TODO: sorry Windows, Andriod

        # If we're measuring time, prepend `/usr/bin/time` and let it write to
        # a pipe we will read out later. Massive assumption: that pipe's buffer
        # will be sufficient for time's output.
        if time:
            time_read_fd, time_write_fd = os.pipe()
            os.set_inheritable(time_write_fd, True) # TODO is this necessary?
            args = ['/usr/bin/time', '-p', '-o', f'/dev/fd/{time_write_fd}', *args]
            kwargs['pass_fds'] = (time_write_fd, *kwargs.get('pass_fds', tuple()))
        
        child = Popen(args, **{
            **kwargs,
            'env': {
                **os.environ,
                **self.environ,
                **(kwargs.get('env') or dict())
            }
        })

        # If we have a time pipe, make sure we release our handle of the write
        # side. We just keep the read side.
        if time_write_fd:
            os.close(time_write_fd)

        n = len(self.children)
        thread = Thread(target=babysit_child, args=[n, child, name, self.print_queue, self.ctrl_queue, time_read_fd])
        thread.start()
        self.children.append(Child(name, child, thread))
        return child

    def __enter__(self) -> 'ProcessPool':
        return self

    def __exit__(self, err_type, err_inst, _) -> None:
        # Wait for the children to exit, and depending on their retval exit early
        running_children = len(self.children)

        # If we hit __exit__ due to an exception, just terminate everything
        if err_type:
            for child in self.children:
                child.process.terminate()

        # Place to store a non-zero child exit
        problem_child: Optional[Child] = None

        # Wait for all children to signal their exit
        try:
            while running_children > 0:
                child_i, retval = self.ctrl_queue.get()
                running_children -= 1

                logging.event('child_exit_received', n=child_i, retval=retval)

                # Early exit when a process errored out. SIGPIPE is retuned by
                # processes that can no longer write to the next one. E.g. when
                # `head -n 10` stops reading because it has read its 10 lines.
                if retval not in (0, -signal.SIGPIPE):
                    problem_child = self.children[child_i]
                    break
        except KeyboardInterrupt:
            # Oh user doesn't want to wait? Okay, then we terminate.
            for child in self.children:
                child.process.terminate()
            pass

        # Wait for all the processes to exit to prevent zombies
        for child in self.children:
            if child.process.returncode is None:
                child.process.wait()

        # Wait for the babysitters to exit, which happens when their process has stopped
        for child in self.children:
            child.babysitter.join()

        # If we broke out of our ctrl_queue loop we did so because there was an issue
        # with one of the children. Let's raise that to the parent.
        if not err_inst and problem_child:
            raise RuntimeError(f"Child {problem_child.name} (pid {problem_child.process.pid}) exited with {problem_child.process.returncode}")


class PipelineStep(NamedTuple):
    name: str
    command: str
    basedir: str


class Pipeline:
    """Description of a set of filter steps with all their variables filled in
    set up to execute in a certain environment. A Pipeline can either be dumped
    as a bash script, or executed on a ProcessPool.
    """
    def __init__(self, filters:Dict[str,Filter], languages: List[str], pipeline: FilterPipeline):
        self.steps: List[PipelineStep] = []

        # Make sure the path to the python binary (and the installed utils)
        # is in the PATH variable. If you load a virtualenv this happens by
        # default, but if you call it with the virtualenv's python binary 
        # directly it wont.
        pyenv_bin_path = os.path.dirname(sys.executable)
        os_env_bin_paths = os.environ.get('PATH', '').split(os.pathsep)
        self.env: Optional[Dict[str,str]] = {
            **os.environ,
            'PATH': os.pathsep.join([pyenv_bin_path] + os_env_bin_paths)
        } if pyenv_bin_path not in os_env_bin_paths else None

        # Assert we have all filters we need
        assert set(step.filter for step in pipeline.filters) - set(filters.keys()) == set()

        # Make sure the path to the python binary (and the installed utils)
        # is in the PATH variable. If you load a virtualenv this happens by
        # default, but if you call it with the virtualenv's python binary 
        # directly it wont.
        pyenv_bin_path = os.path.dirname(sys.executable)
        os_env_bin_paths = os.environ.get('PATH', '').split(os.pathsep)
        self.env: Optional[Dict[str,str]] = {
            **os.environ,
            'PATH': os.pathsep.join([pyenv_bin_path] + os_env_bin_paths)
        } if pyenv_bin_path not in os_env_bin_paths else None

        for step in pipeline.filters:
            filter_def = filters[step.filter]
            command_str = filter_format_command(filter_def, step, languages)
            self.steps.append(PipelineStep(step.filter, command_str, filter_def.basedir))

    def run(self, pool:ProcessPool, stdin:IO[bytes], stdout:IO[bytes], *, tee:bool=False, basename:str="", time:bool=False) -> None:
        """Set up all the processes on `pool`, processing `stdin` to `stdout`.
        Note that this function will return as soon as the processes have been
        set up. You will have to use the ProcessPool to wait for them to finish.
        Optionally you can `tee` the output of each filter step to a separate
        file for debugging (with the name "{basename}.step-{i}.tsv". You can 
        use `time` two wrap every filter step command in `/usr/bin/time` and
        the baby sitter will measure how much processing time the filter process
        used."""
        if not self.steps:
            copyfileobj(stdin, stdout)
            return

        for i, (is_last_step, step) in enumerate(mark_last(self.steps)):
            child = pool.start(f'{pool.print_prefix}{i}:{step.name}', step.command,
                stdin=stdin,
                stdout=stdout if is_last_step and not tee else PIPE,
                stderr=PIPE,
                cwd=step.basedir,
                env=self.env,
                shell=True,
                time=time)

            # Close our reference to the previous child, now taken over by the next child
            stdin.close()
            
            # Set stdin for next step (unless there is none, then child.stdout is None)
            if not is_last_step and not tee:
                stdin = none_throws(child.stdout)

            # If we are tee-ing for debug, shunt the output to a separate file
            # TODO: uncompressed at the moment. Might be trouble.
            if tee:
                tee_child = pool.start(f'{pool.print_prefix}{i}:tee',
                    ['tee', f'{basename}.step-{i}.tsv'],
                    stdin=stdin,
                    stdout=stdout if is_last_step else PIPE,
                    stderr=PIPE)

                stdin.close()
                stdin = none_throws(tee_child.stdout)

    def dump(self, out:IO[str]) -> None:
        """Write this pipeline as a bash script."""
        if self.env:
            for key, val in self.env:
                out.write(f'export {key}={quote(format_shell(val))}\n')

        for is_last_step, step in mark_last(self.steps):
            out.write(f'(cd {quote(format_shell(step.basedir))} && ({step.command}))')
            out.write('\n' if is_last_step else ' |\n')



def split_input(parallel: int, batch_queue: BatchQueue, batch_size:int, stdin:IO[bytes]) -> None:
    """Reads data from `stdin` and splits it into chunks of `batch_size` lines.
    These chunks are stored in temporary files, whose filenames are put onto
    `batch_queue`.
    """
    more = True

    batch_index = 0

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

        try:    
            if lines > 0:
                batch_queue.put((batch_index, fh.name))
            else:
                # Empty chunk because `len(stdin) % batch_size == 0`. No need
                # to process it further.
                os.unlink(fh.name)
        except Cancelled:
            # batch_queue got interrupted, so fn.name never made it into the
            # queue. Let's clean that up.
            os.unlink(fh.name)
            raise

        batch_index += 1

    # Tell all the runners there will be no more batches coming.
    for _ in range(parallel):
        batch_queue.put(None)


@logging.trace
def run_pipeline(print_queue:PrintQueue, batch_queue:BatchQueue, merge_queue:MergeQueue, pipeline:Pipeline, *, time:bool=False) -> None:
    """Receives an input filename from `batch_queue`, and once that has been processed
    with `pipeline`, it will post the output filename to `merge_queue`.
    stderr from any of the filter processes will be forwarded to `print_queue`.

    TODO: This could also instead run ./run.py on the input and output files
    directly as opposed to using `ProcessPool` + `pipeline.run()`.

    TODO: We can rewrite this to call `srun` on SLUM clusters so that the
    actual filtering pipeline is executed on a different node. Since input
    and output are just files on the same filesystem (depends on TMPDIR) this
    should pretty much work out of the box :O
    """
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

                try:
                    # Open chunk file and process pool and run the pipeline with it.
                    # The pool's __exit__() will make us wait till the pipeline is done.
                    with logging.span('run_pipeline_batch', batch_index=batch_index), \
                        open(filename, 'rb') as stdin, \
                        ProcessPool(print_queue, env={'TMPDIR': tmpdir}, print_prefix=f'{batch_index}/') as pool:
                        pipeline.run(pool, stdin, stdout, time=time)

                    stdout.close()

                    # Tell merger that they can process this batch when the time comes
                    merge_queue.put((batch_index, stdout.name))
                except Exception as exc:
                    # Didn't get to put it on the queue, delete it.
                    os.unlink(stdout.name)
                    raise
            except Exception as exc:
                # Add a bit more info, and re-raise
                raise RuntimeError(f'Error while processing batch {batch_index}') from exc
            finally:
                # Delete the input file from disk.
                os.unlink(filename)
        
        # Tell the merger that they should not be expecting more input from you.
        merge_queue.put(None)


def merge_output(parallel:int, merge_queue:MergeQueue, stdout:IO[bytes]) -> None:
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

            try:
                with logging.span(f'merge_output_batch', batch_index=batch_index), open(filename, 'rb') as fh:
                    copyfileobj(fh, stdout)
            except Exception as exc:
                raise RuntimeError(f'Error while merging batch {batch_index}') from exc
            finally:
                os.unlink(filename)

            next_batch_index += 1
        # If not yet, we wait on the queue to come through with (hopefully) the next batch
        elif parallel > 0:
            entry = merge_queue.get()

            # Another batch processor finished
            if entry is None:
                parallel -= 1
            else:
                batch_index, filename = entry
                assert batch_index not in pending_batches
                pending_batches[batch_index] = filename
        # next_batch_index is not in pending_batches, and there are no more batches coming from
        # any batch processors. So let's stop.
        else:
            break

    if len(pending_batches) and next_batch_index <= max(pending_batches.keys()):
        raise RuntimeError(f'Not all batches got merged: {next_batch_index=} <= {max(pending_batches.keys())=}')


@logging.trace
def run_parallel(pipeline:Pipeline, stdin:IO[bytes], stdout:IO[bytes], *, parallel:int, batch_size:int, print_queue: PrintQueue, time:bool=False) -> None:
    """Run `parallel` copies of the processing pipeline in parallel, each
    working on a batch of `batch_size` lines at a time. Batches will be cut
    from `stdin` and printed to `stdout`, in order. stderr from the filter
    processes will be forwarded to `print_queue`. `time` is forwarded to
    ProcessPool.
    """
    batch_queue: BatchQueue = CancelableQueue(parallel * 2)

    merge_queue: MergeQueue = CancelableQueue()

    with ThreadPool() as pool:
        # Splits stdin into files of `batch_size` lines, and puts those on `batch_queue`
        pool.start(split_input, parallel, batch_queue, batch_size, stdin)

        # Read `batch_queue` for batch filenames, and process them. Put output files
        # on `merge_queue`.
        for _ in range(parallel):
            pool.start(run_pipeline, print_queue, batch_queue, merge_queue, pipeline, time=time)

        # Read from `merge_queue` and combine files in order.
        pool.start(merge_output, parallel, merge_queue, stdout)

        try:
            pool.join()
        except BaseException: # Note: also catches KeyboardInterrupt
            batch_queue.cancel()
            merge_queue.cancel()
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--filters', '-f', type=str, default=FILTER_PATH, help='Path to directory with filter specifications')
    parser.add_argument('--input', '-i', type=argparse.FileType('rb'), help='Input tsv. If unspecified input files are read from filter json; use - to read from stdin')
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'), default=sys.stdout.buffer, help='Output tsv (defaults to stdout)')
    parser.add_argument('--basedir', '-b', type=str, help='Directory to look for data files when --input is not used (defaults to same as input pipeline file)')
    parser.add_argument('--tee', action='store_true', help='Write output after each step to a separate file')
    parser.add_argument('--parallel', type=int, default=1, help='Run N parallel copies of the pipeline processing batches')
    parser.add_argument('--batch-size', type=int, default=1_000_000, help='Batch size in lines that each parallel copy processes (only if --parallel > 1)')
    parser.add_argument('--first', type=int, default=0, help='Limit reading input to the N first lines')
    parser.add_argument('--dump', action='store_true', help='Print shell script instead')
    parser.add_argument('--trace', type=argparse.FileType('a'), nargs='?', const='/dev/stderr', help='Write tracing JSON to file (defaults to stderr)')
    parser.add_argument('--time', action='store_true', help='Measure real/user/sys times for each filter step')
    parser.add_argument('pipeline', metavar='PIPELINE', type=argparse.FileType('r'), help='Pipeline steps specification file, e.g. *.filters.json')
    parser.add_argument('languages', metavar='LANG', type=str, nargs='*', help='Language codes of the columns in the input TSV. Only used when --input is set')

    args = parser.parse_args()

    with logging.Context(file=args.trace), logging.span('main'):
        # default search path for the data files is next to the configuration file
        # which is the default save location for empty-train.
        if not args.basedir:
            args.basedir = os.path.dirname(args.pipeline.name) or os.getcwd()

        if args.input is not None and not args.languages:
            parser.error('When --input is specified, each column\'s LANG has to be specified as well')

        if args.tee and args.parallel > 1:
            parser.error('Using --tee is not supported when using --parallel')

        if args.time and not args.trace:
            parser.error('You need to use --trace to see the output of --time')

        # load all filter definitions (we need to, to get their name)
        filters = {
            definition.name: definition
            for definition in list_filters(args.filters)
        }

        # set_global_filters() provides the filters to the validators in FilterPipeline
        set_global_filters(filters.values())
        pipeline_config = parse_obj_as(FilterPipeline, json.load(args.pipeline))

        # Order of columns. Matches datasets.py:list_datasets(path)
        languages: List[str] = args.languages if args.input else [filename.rsplit('.', 2)[1] for filename in pipeline_config.files]

        # Directory plus basename to write debug (`--tee`) files to
        basename: str = 'stdin' if args.input else os.path.commonprefix(pipeline_config.files).rstrip('.')

        pipeline = Pipeline(filters, languages, pipeline_config)

        # Input for next child
        stdin: IO[bytes]

        # Output of this program
        stdout:IO[bytes] = args.output

        # If we're just dumping the pipeline, do so to the specified output
        if args.dump:
            pipeline.dump(TextIOWrapper(stdout))
            sys.exit(0)

        # Queue filled by the babysitters with the stderr of the children, consumed
        # by `print_lines()` to prevent racing on stderr.
        print_queue = SimpleQueue() # type: SimpleQueue[Optional[bytes]]

        # First start the print thread so that we get immediate feedback from the
        # children even if all of them haven't started yet.
        print_thread = Thread(target=print_lines, args=[print_queue, sys.stderr.buffer])
        print_thread.start()

        # Start child processes, each reading the output from the previous sibling
        try:
            with ProcessPool(print_queue) as pool:
                # If we're not reading from stdin, read from files and paste them together
                if args.input:
                    stdin = args.input
                else:
                    # Open `gzunip` for each language file
                    gunzips = [
                        pool.start(f'gunzip {filename}',
                            ['gzip', '-cd', filename],
                            stdout=PIPE,
                            stderr=PIPE,
                            cwd=args.basedir)
                        for filename in pipeline_config.files
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
                    run_parallel(pipeline, stdin, stdout, print_queue=print_queue, parallel=args.parallel, batch_size=args.batch_size, time=args.time)
                else:
                    pipeline.run(pool, stdin, stdout, tee=args.tee, basename=basename, time=args.time)
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
