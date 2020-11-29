import os
import shutil
from contextlib import asynccontextmanager
import tempfile
import subprocess
import uuid
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


class FileWrapper(object):
    def __init__(self, file):
        self.output = file
        self.failed = False

    def __rshift__(self, other):
        assert isinstance(other, GISUnitOperation), "Not a GIS Unit Operation"
        assert "gis_curried" in other.command_string, "Not a curried GIS Unit Operation"
        return other.deferred_input_call(self)


@asynccontextmanager
async def file_copier(file):
    with open(file, "rb") as f:
        async with tempfile_copy(f) as copied_file:
            resource = FileWrapper(copied_file)
            try:
                yield resource
            finally:
                pass


class GISUnitOperation(object):
    """
    Generic GIS unit operation object that handles cleanup of the destination file.
    :param: cmdstring - String that allows you to do a GIS process
    :param: source_files - String containing list of one or more input files for the operation,
        If you use the keyword "gis_curried" for source_files, you will instead get a curried-like function
    :param: **options dictionary that will be converted to string and added to the command.
    """

    def __init__(self, tempfolder, cmdstring, **options):
        src = options.pop('src')
        dst = options.pop('dst')
        optstring = " ".join([f"-{k} {v}" for k, v in options.items()])
        self.output = f"{tempfolder}/{dst}"
        self.command_string = f"{cmdstring} {optstring} {src} {self.output}"
        self.new_string = None
        self.failed = False

    def make_new_command_string(self, inputObj):
        self.new_string = self.command_string.replace("gis_curried", inputObj.output)
        return self.new_string

    def _shell_call(self, cmd):
        res = subprocess.call(cmd, shell=True)
        try:
            assert res == 0, f"Failed: {cmd}"
            return self
        except AssertionError as e:
            print(repr(e))
            self.failed = True
            return self

    def call(self, cs=None):
        cs = cs if cs is not None else self.command_string
        try:
            assert "gis_curried" not in cs, f"Curried function; \n{cs}\n needs more input"
            return self._shell_call(cs)
        except AssertionError:
            assert self.new_string is not None, "Incomplete command"
            cs = self.new_string
            return self._shell_call(cs)

    def deferred_input_call(self, inputObj):
        if inputObj.failed:
            self.failed = True
            return self
        return self.call(self.make_new_command_string(inputObj))

    def __rshift__(self, other):
        """
        :param: other should be a GIS Unit Operation with a gis_curried source file.
        Returns the result by piping self.output into the input of 'other' and evaluating the output from 'other'
        We override the ">>" operator so we can do something like
        "result = converter >> translator >> colorizer" to pipeline GIS operators
        """
        assert isinstance(other, GISUnitOperation), "Not a GIS Unit Operation"
        assert "gis_curried" in other.command_string, "Not a curried GIS Unit Operation"
        output = self.call()
        return other.deferred_input_call(output)


async def gis_operator_helper(*args, **kwargs):
    async with managed_tempfolder(prefix="gunit") as tempfolder:
        unit_operation = GISUnitOperation(tempfolder, *args, **kwargs)
        try:
            yield unit_operation
        finally:
            pass


@asynccontextmanager
def gis_operator(*args, **kwargs):
    """
    If you do not pass a 'dest_file' option, GDAL may not know the output format it needs.
    """
    kwargs.update({'src': kwargs.get('src', "gis_curried")})
    if kwargs.get('dst') is None:
        try:
            assert 'of' in kwargs.keys(), "Either 'dst' needs to be specified, or the output format option 'of' "
            kwargs['dst'] = str(uuid.uuid4())
            return gis_operator_helper(*args, **kwargs)
        finally:
            pass
    return gis_operator_helper(*args, **kwargs)


## GDAL functions

def gdal_translate(*args, **kwargs):
    return gis_operator("gdal_translate", *args, **kwargs)
