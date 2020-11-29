## Author: Kaustubh Bhalerao, Soil Diagnostics, Inc.


import os
import shutil
from contextlib import asynccontextmanager
import tempfile
import asyncio
from functools import wraps, partial

def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


@asynccontextmanager
async def managed_tempfolder(*args, **kwargs):
    prefix = kwargs.get('prefix', 'mgd')
    suffix = kwargs.get('suffix', '')
    resource = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
    try:
        yield resource
    finally:
        try:
            shutil.rmtree(resource)
        except OSError as e:
            print(f"Error {resource}-{repr(e)}")


def read_in_chunks(file_object, chunk_size=1024):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k."""
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data


@asynccontextmanager
async def tempfile_copy(file):
    async with managed_tempfolder(prefix="cpy") as folder:
        fname = os.path.basename(file.name)
        with open(f"{folder}/{fname}", "wb") as copied_file:
            for chunk in read_in_chunks(file):
                await async_wrap(copied_file.write)(chunk)
        try:
            yield f"{folder}/{fname}"
        finally:
            pass
            ## Let the managed tempfolder deal with cleanup.


