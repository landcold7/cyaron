from __future__ import absolute_import
from .utils import *
from . import log
from io import open, IOBase
import subprocess
import tempfile
import os
import re


class IO(object):
    """Class IO: IO tool class. It will process the input and output files.

    # Arguments:
        input_file, output_file:
            None: make a temp file (if file_prefix is None)
            file object: treat the file-like object as in/output file
            int: open file by file descriptor
            str: a filename or filename template like 'awd{}.in'.
                 ``{}`` will be replaced by ``data_id``
        data_id: the id of the data. if it's None,
                 the file names will not contain the id.
        legacy argumants:
            file_prefix: the prefix for the input and output files
            input_suffix = ".in": the suffix of the input file
            output_suffix = ".out": the suffix of the output file
        disable_output: set to True to disable output

    # Examples:
        IO("a","b")
        IO("a.in","b.out")
        IO(file_prefix="data")
        IO(file_prefix="data", data_id=1)
        IO(file_prefix="data", input_suffix=".input")
        IO(file_prefix="data", output_suffix=".output")
        IO(file_prefix="data", data_id=2, input_suffix=".input")
        IO("data{}.in", "data{}.out", data_id=2)
        IO(open('data.in', 'w+'), open('data.out', 'w+'))
    """
    def __init__(self,
                 input_file=None,
                 output_file=None,
                 data_id=None,
                 file_prefix=None,
                 input_suffix='.in',
                 output_suffix='.out',
                 disable_output=False):
        if file_prefix is not None:
            # legacy mode
            input_file = (
                '{}{{}}{}'.format(self._escape_format(file_prefix),
                                  self._escape_format(input_suffix)))
            output_file = (
                '{}{{}}{}'.format(self._escape_format(file_prefix),
                                  self._escape_format(output_suffix)))
        self.input_filename = None
        self.output_filename = None
        self._input_temp = False
        self._output_temp = False
        self._input_file(input_file, data_id, 'i')
        if not disable_output:
            self._input_file(output_file, data_id, 'o')
        else:
            self.output_file = None
        self._closed = False
        self._is_first_char = {}

    def _input_file(self, f, data_id, file_type):
        try:
            is_file = isinstance(f, file)
        except NameError:
            is_file = False

        if isinstance(f, IOBase) or is_file:
            # consider ``f`` as a file object
            if file_type == 'i':
                self.input_file = f
            else:
                self.output_file = f
        elif isinstance(f, int):
            # consider ``f`` as a file descriptor
            self._input_file(open(f, 'w+', newline='\n'), data_id, file_type)
        elif f is None:
            # consider wanna temp file
            fd, self.input_filename = tempfile.mkstemp()
            self._input_file(fd, data_id, file_type)
            if file_type == 'i':
                self._input_temp = True
            else:
                self._output_temp = True
        else:
            # consider ``f`` as filename template
            filename = f.format(data_id or '')
            if file_type == 'i':
                self.input_filename = filename
                log.debug("Processing %s" % self.input_filename)
            else:
                self.output_filename = filename
            self._input_file(open(filename, 'w+', newline='\n'), data_id, file_type)

    def _escape_format(self, st):
        """replace "{}" to "{{}}" """
        return re.sub(r'\{', '{{', re.sub(r'\}', '}}', st))

    def _delete_files(self):
        """delete files"""
        if self._input_temp and self.input_filename is not None:
            os.remove(self.input_filename)
        if self._output_temp and self.output_filename is not None:
            os.remove(self.output_filename)

    def close(self):
        """Delete the IO object and close the input file and the output file"""
        if self._closed:
            # avoid double close
            return
        deleted = False
        try:
            # on posix, one can remove a file while it's opend by a process.
            # the file then will be not visable to others, but process still
            # have the file descriptor, it is recommand to remove temp file
            # before close it on posix to avoid race on nt, it will just fail
            # and raise OSError so that after closing remove it again
            self._delete_files()
            deleted = True
        except OSError:
            pass
        if isinstance(self.input_file, IOBase):
            self.input_file.close()
        if isinstance(self.output_file, IOBase):
            self.output_file.close()
        if not deleted:
            self._delete_files()
        self._closed = True

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _write(self, file, *args, **kwargs):
        """_write(self, file, *args, **kwargs) -> None
        Write every element in *args into file. If the element isn't "\n",
        insert a space. It will convert every element into str

        # Arguments:
            file: the file object to write
            **kwargs: separator = " ": a string used to separate every element
        """
        separator = kwargs.get("separator", " ")
        for arg in args:
            if list_like(arg):
                self._write(file, *arg, **kwargs)
            else:
                if arg != "\n" and not self._is_first_char.get(file, True):
                    file.write(make_unicode(separator))
                self._is_first_char[file] = False
                file.write(make_unicode(arg))
                if arg == "\n":
                    self._is_first_char[file] = True

    def input_write(self, *args, **kwargs):
        """input_write(self, *args, **kwargs) -> None
        Write every element in *args into the input file.
        Splits with spaces. It will convert every element into string

        # Arguments:
            **kwargs: separator = " ": a string used to separate every element
        """
        self._write(self.input_file, *args, **kwargs)

    def input_writeln(self, *args, **kwargs):
        """input_writeln(self, *args, **kwargs) -> None
        Write every element in *args into the input file and turn to a new line.
        Splits with spaces. It will convert every element into string.

        # Arguments:
            **kwargs: separator = " "  a string used to separate every element
        """
        args = list(args)
        args.append("\n")
        self.input_write(*args, **kwargs)

    def output_gen(self, shell_cmd):
        """output_gen(self, shell_cmd) -> None
        Run the command shell_cmd(usually the std programme) and send it the
        input file as stdin. Write its output to the output file.

        # Arguments:
            shell_cmd: the command to run, usually the std program
        """
        self.flush_buffer()
        origin_pos = self.input_file.tell()
        self.input_file.seek(0)
        subprocess.check_call(shell_cmd,
                              shell=True,
                              stdin=self.input_file,
                              stdout=self.output_file,
                              universal_newlines=True)
        self.input_file.seek(origin_pos)

        log.debug(self.output_filename, " done")

    def output_write(self, *args, **kwargs):
        """output_write(self, *args, **kwargs) -> None
        Write every element in *args into the output file. Splits with spaces.
        It will convert every element into string

        # Arguments:
            **kwargs: separator = " " a string used to separate every element
        """
        self._write(self.output_file, *args, **kwargs)

    def output_writeln(self, *args, **kwargs):
        """output_writeln(self, *args, **kwargs) -> None
        Write every element in *args into the output file and turn to a new
        line. Splits with spaces. It will convert every element into string

        # Arguments:
            **kwargs: separator = " " a string used to separate every element
        """
        args = list(args)
        args.append("\n")
        self.output_write(*args, **kwargs)

    def flush_buffer(self):
        self.input_file.flush()

