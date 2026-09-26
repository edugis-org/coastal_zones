#!/usr/bin/env python3
"""Turn the flood-level raster into coastline zone polygons.

Each polygon carries `flood_level`: the sea level (m) at which it becomes sea,
rounded up to STEP. A slider at level L paints `flood_level <= L` as water.

    flood_level = -195, -190, ..., 100   (STEP=5)
    flood_level = 101                     land that stays dry up to +100 m
    (no polygon)                          sea at/below -200 m -> map background

Zone polygons are built at three resolutions so vector tiles stay light at
low zoom (median-resampled flood level, then quantised):

    r0  15"  native GEBCO   zoom 7+
    r1  1'   4x coarser     zoom 4-6
    r2  4'  16x coarser     zoom 0-3

Polygonising the full 86400x43200 grid is split into chunks run in parallel;
polygons are cut at chunk edges, which is invisible for filled rendering.

Usage:
    ./make_zones.py                  # STEP=5
    STEP=10 ./make_zones.py
    LEVELS=r2,r1 ./make_zones.py     # only some resolutions
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SRC = DATA / "flood_level.tif"
STEP = int(os.environ.get("STEP", "5"))
NODATA = -32768
CHUNK = 5400
JOBS = int(os.environ.get("JOBS", os.cpu_count() or 4))
RESOLUTIONS = {"r0": 1, "r1": 4, "r2": 16}  # name -> downsample factor


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def quantise(a):
    """flood level (-201..101) -> zone value, NODATA for always-sea."""
    q = (np.ceil(a / STEP) * STEP).astype(np.int16)
    q[a > 100] = 101
    q[a <= -200] = NODATA
    return q


def build_zone_raster(name, factor, work):
    src = SRC
    if factor > 1:
        src = work / f"flood_level_{name}.tif"
        if not src.exists():
            with rasterio.open(SRC) as ds:
                res = ds.res[0] * factor
            run("gdalwarp", "-q", "-overwrite", "-r", "med", "-tr", res, res,
                "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
                "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES", "-co", "BIGTIFF=YES",
                SRC, src)
    dst = work / f"zones_{name}_{STEP}m.tif"
    with rasterio.open(src) as ds:
        profile = ds.profile
        profile.update(dtype="int16", nodata=NODATA, compress="deflate",
                       tiled=True, blockxsize=512, blockysize=512, bigtiff="yes")
        with rasterio.open(dst, "w", **profile) as out:
            for _, win in ds.block_windows(1):
                out.write(quantise(ds.read(1, window=win)), 1, window=win)
    return dst


def polygonise_chunk(args):
    raster, xoff, yoff, w, h, out = args
    vrt = out.with_suffix(".vrt")
    run("gdal_translate", "-q", "-of", "VRT", "-srcwin", xoff, yoff, w, h, raster, vrt)
    out.unlink(missing_ok=True)
    run("gdal_polygonize.py", "-q", vrt, "-f", "GPKG", out, "zones", "flood_level")
    vrt.unlink()
    return out


def polygonise(name, raster, work):
    with rasterio.open(raster) as ds:
        width, height = ds.width, ds.height
    chunk_dir = work / f"chunks_{name}_{STEP}m"
    chunk_dir.mkdir(exist_ok=True)
    jobs = []
    for yoff in range(0, height, CHUNK):
        for xoff in range(0, width, CHUNK):
            out = chunk_dir / f"{yoff:05d}_{xoff:05d}.gpkg"
            jobs.append((raster, xoff, yoff, min(CHUNK, width - xoff),
                         min(CHUNK, height - yoff), out))
    print(f"  polygonising {len(jobs)} chunk(s) with {JOBS} jobs", flush=True)
    with ProcessPoolExecutor(JOBS) as pool:
        parts = list(pool.map(polygonise_chunk, jobs))

    dst = DATA / f"zones_{name}_{STEP}m.gpkg"
    dst.unlink(missing_ok=True)
    for i, part in enumerate(parts):
        run("ogr2ogr", "-f", "GPKG", *(["-append"] if i else []), "-nln", "zones",
            "-nlt", "PROMOTE_TO_MULTI", "-gt", "65536", dst, part)
    return dst


def main():
    if not SRC.exists():
        sys.exit(f"missing {SRC}; run ./flood_levels.py first")
    work = DATA / "work"
    work.mkdir(parents=True, exist_ok=True)
    wanted = os.environ.get("LEVELS", ",".join(RESOLUTIONS)).split(",")
    for name in wanted:
        t0 = time.time()
        print(f"{name}: step {STEP} m, factor {RESOLUTIONS[name]}", flush=True)
        raster = build_zone_raster(name, RESOLUTIONS[name], work)
        dst = polygonise(name, raster, work)
        print(f"  -> {dst} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
