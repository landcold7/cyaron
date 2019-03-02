from __future__ import absolute_import, print_function
from cyaron import IO, log
from cyaron.utils import *
from cyaron.consts import *
from cyaron.graders import CYaRonGraders
import subprocess
import multiprocessing
import sys
from io import open
import os


class CompareMismatch(ValueError):
    def __init__(self, name, mismatch):
        super(CompareMismatch, self).__init__(name, mismatch)
        self.name = name
        self.mismatch = mismatch

    def __str__(self):
        return "In program: `{}`: {}".format(self.name, self.mismatch)


class Compare(object):
    @staticmethod
    def _compare_two(name, content, std, grader):
        (result, info) = CYaRonGraders.invoke(grader, content, std)
        status = "Correct" if result else "!!!INCORRECT!!!"
        info = info if info is not None else ""
        log.debug("{}: {} {}".format(name, status, info))
        if not result:
            raise CompareMismatch(name, info)

    @staticmethod
    def _process_file(file):
        if isinstance(file, IO):
            file.flush_buffer()
            file.output_file.seek(0)
            return file.output_filename, file.output_file.read()
        else:
            with open(file, 'r', newline='\n') as f:
                return file, f.read()

    @staticmethod
    def _do_execute(program_name, input, timeout=None):
        fd = os.dup(input.input_file.fileno())
        with open(fd, 'r', newline='\n') as input_file:
            content = make_unicode(
                        subprocess.check_output(
                            program_name,
                            shell=(not list_like(program_name)),
                            stdin=input_file,
                            universal_newlines=True,
                            timeout=timeout))
            input_file.seek(0)
            return content

    @staticmethod
    def _do_tasks(job_pool, task, *args):
        # log.error(job_pool, task, args)
        if job_pool is not None:
            if len(args) > 0:
                job_pool.map(task, args)
                return None
            else:
                return job_pool.submit(task).result()
        else:
            if len(args) > 0:
                [x for x in map(task, args)]
                return None
            else:
                return task()

    @staticmethod
    def _normal_max_workers(workers):
        if workers is None:
            if sys.version_info < (3, 5):
                cpu = multiprocessing.cpu_count()
                return cpu * 5 if cpu is not None else 1
        return workers

    @staticmethod
    def _thread_pool_executor(prog, args, kwargs):
        job_pool = kwargs['job_pool']
        max_workers = kwargs['max_workers']
        if max_workers is None and job_pool is None:
            max_workers = Compare._normal_max_workers(max_workers)
            try:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=max_workers) as job_pool:
                    kwargs['job_pool'] = job_pool
                    kwargs['max_workers'] = max_workers
                    prog(*args, **kwargs)
            except ImportError:
                pass

    @classmethod
    def output(cls, *files, **kwargs):
        arg_pattern = ('std',
                       ('grader', DEFAULT_GRADER),
                       ('max_workers', -1),
                       ('job_pool', None),
                       ('stop_on_incorrect', None))
        kwargs = unpack_kwargs('output', kwargs, arg_pattern)

        std = kwargs['std']
        grader = kwargs['grader']
        job_pool = kwargs['job_pool']
        if kwargs['stop_on_incorrect'] is not None:
            log.warn("parameter stop_on_incorrect "
                     "is deprecated and has no effect.")

        cls._thread_pool_executor(cls.output, files, kwargs)

        def get_std():
            return cls._process_file(std)[1]

        std = cls._do_tasks(job_pool, get_std)

        def do(file):
            (file_name, content) = cls._process_file(file)
            cls._compare_two(file_name, content, std, grader)

        cls._do_tasks(job_pool, do, *files)

    @classmethod
    def program(cls, *programs, **kwargs):
        arg_pattern = ('input',
                       ('std', None),
                       ('std_program', None),
                       ('grader', DEFAULT_GRADER),
                       ('max_workers', -1),
                       ('job_pool', None),
                       ('stop_on_incorrect', None))
        kwargs = unpack_kwargs('program', kwargs, arg_pattern)

        input = kwargs['input']
        std = kwargs['std']
        std_program = kwargs['std_program']
        grader = kwargs['grader']
        job_pool = kwargs['job_pool']
        if kwargs['stop_on_incorrect'] is not None:
            log.warn("parameter stop_on_incorrect is "
                     "deprecated and has no effect.")

        cls._thread_pool_executor(cls.program, programs, kwargs)

        if not isinstance(input, IO):
            raise TypeError("expect {}, got {}".format(
                        type(IO).__name__, type(input).__name__))

        input.flush_buffer()
        input.input_file.seek(0)

        if std_program is not None:
            def get_std():
                return cls._do_execute(std_program, input)
            std = cls._do_tasks(job_pool, get_std)

        elif std is not None:
            def get_std():
                return cls._process_file(std)[1]
            std = cls._do_tasks(job_pool, get_std)

        else:
            raise TypeError("program() missing 1 required non-None"
                            " keyword-only argument: `std` or `std_program`")

        def do(program_name):
            timeout = None
            if (list_like(program_name) and
                len(program_name) == 2 and
                int_like(program_name[-1])):
                program_name, timeout = program_name

            content = cls._do_execute(program_name, input, timeout=timeout)

            cls._compare_two(program_name, content, std, grader)

        cls._do_tasks(job_pool, do, *programs)
