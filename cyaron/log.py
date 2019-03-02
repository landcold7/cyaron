from __future__ import print_function
from functools import partial
import sys
from threading import Lock
from .utils import make_unicode
try:
    import colorful
except ImportError:
    class colorful:
        def __getattr__(self, attr):
            return lambda st: st
    colorful = colorful()

__print = print
def _print(*args, **kwargs):
    flush = False
    if 'flush' in kwargs:
        flush = kwargs['flush']
        del kwargs['flush']
    __print(*args, **kwargs)
    if flush:
        kwargs.get('file', sys.stdout).flush()

def _join_dict(a, b):
    """join two dict"""
    c = a.copy()
    for k, v in b.items():
        c[k] = v
    return c

_log_funcs = {}
_log_lock = Lock()
def log(funcname, *args, **kwargs):
    """log with log function specified by ``funcname``"""
    _log_lock.acquire()
    default = lambda *args, **kwargs : None
    rv = _log_funcs.get(funcname, default)(*args, **kwargs)
    _log_lock.release()
    return rv

def register_logfunc(funcname, func):
    """register logfunc
    str funcname -> name of logfunc
    callable func -> logfunc
    """
    if func is not None:
        _log_funcs[funcname] = func
    else:
        try:
            del _log_funcs[funcname]
        except KeyError:
            pass

def _nb_print(*args, **kwargs):
    kwargs.update({'flush': True})
    _print(*args, **kwargs)

def _nb_print_e(*args, **kwargs):
    kwargs.update({'file': sys.stderr, 'flush': True})
    _print(*args, **kwargs)

def _cl_print(color, *args, **kwargs):
    if sys.stdout.isatty():
        _nb_print(*[color(make_unicode(item)) for item in args], **kwargs)
    else:
        _nb_print(*args, **kwargs)

def _cl_print_e(color, *args, **kwargs):
    if sys.stderr.isatty():
        _nb_print_e(*[color(make_unicode(item)) for item in args], **kwargs)
    else:
        _nb_print_e(*args, **kwargs)

_default_debug = partial(_cl_print, colorful.cyan)
_default_info = partial(_cl_print, colorful.blue)
_default_print = _nb_print
_default_warn = partial(_cl_print_e, colorful.yellow)
_default_error = partial(_cl_print_e, colorful.red)

def set_quiet():
    """set log mode to "quiet" """
    register_logfunc('debug', None)
    register_logfunc('info', None)
    register_logfunc('print', _default_print)
    register_logfunc('warn', None)
    register_logfunc('error', _default_error)

def set_normal():
    """set log mode to "normal" """
    register_logfunc('debug', None)
    register_logfunc('info', _default_info)
    register_logfunc('print', _default_print)
    register_logfunc('warn', _default_warn)
    register_logfunc('error', _default_error)

def set_verbose():
    """set log mode to "verbose" """
    register_logfunc('debug', _default_debug)
    register_logfunc('info', _default_info)
    register_logfunc('print', _default_print)
    register_logfunc('warn', _default_warn)
    register_logfunc('error', _default_error)


set_normal()

"""5 log levels
1. debug:   debug info
2. info:    common info
3. print:   print output
4. warn:    warnings
5. error:   errors
"""
debug = partial(log, 'debug')
info = partial(log, 'info')
print = partial(log, 'print')
warn = partial(log, 'warn')
error = partial(log, 'error')

