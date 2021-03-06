"""
Simple pickle based caching

Functions using this wrapper should be simple and pure. No closures, no using
global variables, no mutating state. Note that we don't check if you violate
any of the above constraints.
"""

import os
import cPickle
import hashlib
import inspect
from datetime import datetime
from functools import wraps

# Cache directory to store results
CACHEDIR = "/var/tmp/{}/pypb/cache/".format(os.environ["LOGNAME"])

from logbook import Logger
log = Logger(__name__)

def fnhash(fn):
    """
    Given a function return a hash string version.
    """

    # Get the function source
    source = inspect.getsourcelines(fn)[0]

    # Remove any line comments
    source = [l for l in source if l.strip() and l.strip()[0] != "#"]

    # Create a single string
    source = "".join(source)

    # Replace the docstring with an empty string
    if fn.__doc__ is not None:
        source = source.replace(fn.__doc__, "", 1)

    # Replace the function name with an empty string
    source = source.replace(fn.__name__, "", 1)

    # Remove all whitespace
    source = (c for c in source if not c.isspace())
    source = "".join(source)

    return source

def diskcache(origfn):
    """
    Return a function which memoizes the result of the original function.
    """

    # If cachedir doesn't exist, create it
    if not os.path.exists(CACHEDIR):
        log.notice("Creating cache folder at {} ...", CACHEDIR)
        os.makedirs(CACHEDIR)

    # Get the function hash
    fhash = fnhash(origfn)

    @wraps(origfn)
    def newfn(*args, **kwargs):
        """
        Return result from cache if possible.
        """

        # Steal some parameters
        force_miss   = kwargs.get("_force_miss", False)
        force_before = kwargs.get("_force_before", datetime.utcnow())

        # Remove stolen parameters
        if "_force_miss" in kwargs:
            del kwargs["_force_miss"]
        if "_force_before" in kwargs:
            del kwargs["_force_before"]

        # Compute the function code and argument hash
        runhash = cPickle.dumps((fhash, args, kwargs))
        runhash = hashlib.sha1(runhash).hexdigest()
        fname = CACHEDIR + runhash + ".pickle"

        # Cache hit
        if os.path.exists(fname) and not force_miss:
            log.info("Cache hit for {} in {} ...", origfn.__name__, origfn.func_code.co_filename)
            with open(fname, "rb") as fobj:
                ret = cPickle.load(fobj)
            if ret["at"] < force_before:
                return ret["result"]
            log.info("Cache result too old skipping ...")

        # Cache miss
        log.info("Cache miss for {} in {} ...", origfn.__name__, origfn.func_code.co_filename)
        ret = {
            "at"            : datetime.utcnow(),
            "func_name"     : origfn.__name__,
            "func_filename" : origfn.func_code.co_filename,
            "func_source"   : inspect.getsource(origfn),
            "args"          : args,
            "kwargs"        : kwargs,
            "runhash"       : runhash,
            "result"        : origfn(*args, **kwargs),
        }
        with open(fname, "wb") as fobj:
            cPickle.dump(ret, fobj, -1)
        return ret["result"]

    return newfn

