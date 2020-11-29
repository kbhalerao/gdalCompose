# gdalCompose
*An experiment in creating composable GDAL operations*

## The Why? 

[GDAL](https://gdal.org) provides a powerful set of tools for 
manipulating geospatial vector and raster files. 

These tools have a very consistent argument interface of the form:

```bash
>>> gdal_command -option1 value -option2 value srcfiles dstfile
```
where `srcfiles` and `dstfile` are filepaths for the input file(s)
and the target location of the output file respectively. 

Inspired by Haskell's powerful function composability,
and UNIX's pipe operators, 
I thought it would be nice to have an interface to the GDAL
toolchain that would enable a *pipelining* of GDAL commands
so we can create standardized processing workflows. 

## Wouldn't it be lovely ....

... if we could take a series of individual GDAL operations 
like this, 

```
>>> gdal_rasterize -q -tr 0.005 0.005 -a "Band1" -l "layer" "input.shp" "output.tif" -a_nodata -9999
>>> gdaldem color-relief -q -of PNG -b 1 -nearest_color_entry -alpha "output.tif" "./color.txt" "colored_output.png" 
```
... configure individual compute blocks such as `gdal_translate` 
and `gdaldem` with the right options, and turn them into 
reusable and (re)composable workers like so?

```
pngfile = inputfile >> gdal_translate_block >> gdaldem_block
```

... and furthermore, wouldn't it be great if the compute blocks
abstracted away the process of intermediate output files, 

... and cleaned up all the temporary files after themselves 
when the workflow was completed?

... and it exploited concurrency and parallelism where possible?

## The idea

The `async_unit_processors.py` library provides a few useful 
building blocks:

0. The ability to run GIS computations within a `managedcontext`
in Python (i.e. by using the `with` keyword), so we can clean up 
after ourselves

1. The ability to create an asynchronous file copier that can 
be used to copy files from a location (such as an S3 bucket)
to a temporary location for processing

2. The ability to configure a GIS operation e.g `gdal_translate`
along with its options while leaving out the source and 
destination file names and 

3. The ability to compose and *reuse* the GIS operations using 
Python's (>>) operator. i.e. by overloading the `__rshift__` 
method. In theory, you can store these GIS procedures
in a database and string them together as Lego blocks
to accommodate complex workflows. 

## Does it work?

Do check out the test suite, but here's an example from the 
test suite:

```python
async def try_rshift_with_downloader_3ops():
    inputfile = "test_elev_raster.tif"
    cmd = "gdal_translate"
    
    # One set of configurations, converting a tiff to Bytes
    options = {
        "ot": "Byte",
        "b": 1,
        "of": "GTiff",
        "co": "NUM_THREADS=ALL_CPUS"
    }
    
    # Another set of operations, converting a tiff to UInt16
    options2 = {
        "ot": "UInt16",
        "b": 1,
        "of": "GTiff",
        "co": "NUM_THREADS=ALL_CPUS"
    }

    # We open an Async managed environment
    async with file_copier(inputfile) as fop, \ 
            ## First copy the file into a managed temp folder
            gis_operator(cmd, **options) as translate_to_Byte, \
            ## Configure one GISUnitOperation
            gis_operator(cmd, **options2) as translate_to_UInt16:
            ## Configure the second GISUnitOperation        
        
        ## And now we compose:
        outfile1 = fop >> translate_to_Byte >> translate_to_UInt16
        ## Take the file, translate it to Byte, then to UInt16, and 
        ## and return the output filepath
        
        outfile2 = fop >> translate_to_UInt16 >> translate_to_Byte >> translate_to_UInt16
        ## This shows we can reuse the GISUnitOperations in
        ## the same workflow

    assert not os.path.exists(outfile1.output)
    assert not os.path.exists(outfile2.output)
    ## Look ma - we cleaned up! No tempfiles outside the context

asyncio.run(try_rshift_with_downloader_3ops())
```

## What next?
Operators that can take multiple files, so we can build
computation trees rather than trains. Feedback welcome!
 

