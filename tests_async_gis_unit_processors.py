import asyncio
from unittest import TestCase

from async_unit_processors import managed_tempfolder, tempfile_copy, file_copier, gis_operator
import os


async def try_managed_directory():
    async with managed_tempfolder() as folder:
        assert os.path.isdir(folder)
        with open(f"{folder}/tempfile.txt", "w") as wfile:
            wfile.write("Test")
        with open(f"{folder}/tempfile.txt", "r") as rfile:
            assert rfile.read() == "Test"
    assert not os.path.isdir(folder)


async def try_managed_copy(file):
    with open(file, "rb") as mediafile:
        async with tempfile_copy(mediafile) as copy:
            assert os.path.getsize("test_elev_raster.tif") == os.path.getsize(copy)
            assert os.path.basename(copy) == "test_elev_raster.tif"
        assert not os.path.exists(copy)


async def try_tandem_copy(n=4):
    corolist = list()
    for i in range(n):
        corolist.append(asyncio.create_task(try_managed_copy("test_elev_raster.tif")))

    await asyncio.gather(*corolist)


async def try_file_copier():
    async with file_copier("test_elev_raster.tif") as fc:
        assert os.path.getsize("test_elev_raster.tif") == os.path.getsize(fc.output)
    assert not os.path.exists(fc.output)


async def try_rshift_with_downloader_3ops():
    inputfile = "test_elev_raster.tif"
    cmd = "gdal_translate"
    options = {
        "ot": "Byte",
        "b": 1,
        "of": "GTiff",
        "co": "NUM_THREADS=ALL_CPUS"
    }
    options2 = {
        "ot": "UInt16",
        "b": 1,
        "of": "GTiff",
        "co": "NUM_THREADS=ALL_CPUS"
    }
    async with file_copier(inputfile) as fop, \
            gis_operator(cmd, **options) as translate_to_Byte, \
            gis_operator(cmd, **options2) as translate_to_UInt16:
        ## WooHoo!
        outfile1 = fop >> translate_to_Byte >> translate_to_UInt16
        outfile2 = fop >> translate_to_UInt16 >> translate_to_Byte >> translate_to_UInt16

    assert not os.path.exists(outfile1.output)
    assert not os.path.exists(outfile2.output)


class UnitProcTestCase(TestCase):

    def test_async_managed_directory(self):
        asyncio.run(try_managed_directory())

    def test_async_managed_copy(self):
        asyncio.run(try_managed_copy("test_elev_raster.tif"))

    def test_tandem_copy(self):
        asyncio.run(try_tandem_copy())

    def test_timings(self):
        import time
        start_time = time.time()
        for i in range(400):
            asyncio.run(try_managed_copy("test_elev_raster.tif"))
        single_avg = (time.time() - start_time) / 400
        start_time = time.time()
        asyncio.run(try_tandem_copy(400))
        tandem_avg = (time.time() - start_time) / 400
        speedup = (single_avg - tandem_avg) / single_avg * 100
        print(f"Speedup {round(speedup, 2)}%")

    def test_file_copier(self):
        asyncio.run(try_file_copier())

    def test_rshift_operation(self):
        asyncio.run(try_rshift_with_downloader_3ops())
