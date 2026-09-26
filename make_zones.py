#!/usr/bin/env python3
"""Turn the flood-level raster into coastline zone polygons.

Each polygon carries `flood_level`: the sea level (m) at which it becomes sea,
rounded up to the next zone level. A slider at level L paints
`flood_level <= L` as water.

Zone levels run MIN..MAX (default -134..+70 m: the lowest sea level of the
last glacial maximum, ~21 ka, up to beyond any melt scenario) at multiples of
STEP metres, with finer FINE_STEP steps between FINE_MIN and FINE_MAX around
the present coastline:

    -134, -130, -125, ..., -5, -1, 0, 1, ..., 10, 15, 20, ..., 70

    flood_level = MIN        sea at every slider position
    flood_level = level      becomes sea at that level
    (no polygon)             stays dry up to MAX -> map background

The native 15" GEBCO grid is median-resampled by FACTOR first (default 16,
i.e. 4' ~ 7 km), which is plenty for a global animation.

Low zooms get coarser layers of their own (OVERVIEWS): at z0 one screen pixel
is ~40', so 4' zones are sub-pixel slivers, and a world tile holding all of
them (340k polygons, 8 MB) exceeds the tiler's size limit, which then drops
features silently — holes through which today's sea shows. `zones_z0_1` (16')
and `zones_z2` (8') are tiled at those zooms under the same layer name
(`make_tiles.sh`).

Usage:
    ./make_zones.py
    STEP=10 FINE_MAX=20 ./make_zones.py
    MIN=-200 MAX=100 FACTOR=4 ./make_zones.py
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SRC = DATA / "flood_level.tif"
MIN = int(os.environ.get("MIN", "-134"))
MAX = int(os.environ.get("MAX", "70"))
STEP = int(os.environ.get("STEP", "5"))
FINE_MIN = int(os.environ.get("FINE_MIN", "-1"))
FINE_MAX = int(os.environ.get("FINE_MAX", "10"))
FINE_STEP = int(os.environ.get("FINE_STEP", "1"))
FACTOR = int(os.environ.get("FACTOR", "16"))
NODATA = -32768
OUT = DATA / "zones.gpkg"
# Coarser layers for low zooms: layer name -> resample factor. The name says
# which zooms it is tiled at (zones_z<min>[_<max>]); make_tiles.sh reads it.
OVERVIEWS = {"zones_z0_1": 64, "zones_z2": 32}


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def zone_levels():
    coarse = np.arange(-(-MIN // STEP) * STEP, MAX + 1, STEP)
    coarse = np.union1d([MIN, MAX], coarse)
    fine = np.arange(FINE_MIN, FINE_MAX + 1, FINE_STEP)
    return np.union1d(coarse, fine).astype(np.int16)


def quantise(a, levels):
    """flood level -> first zone level >= it; NODATA above MAX."""
    idx = np.searchsorted(levels, a, side="left")
    q = levels[np.minimum(idx, len(levels) - 1)]
    q[a > levels[-1]] = NODATA
    return q


def resample(work, factor):
    if factor <= 1:
        return SRC
    resampled = work / f"flood_level_x{factor}.tif"
    if not resampled.exists():
        with rasterio.open(SRC) as ds:
            res = ds.res[0] * factor
        run("gdalwarp", "-q", "-overwrite", "-r", "med", "-tr", res, res,
            "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
            "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES",
            SRC, resampled)
    return resampled


def polygonize(work, factor, levels, layer):
    raster = work / f"zones_x{factor}.tif"
    with rasterio.open(resample(work, factor)) as ds:
        profile = ds.profile
        profile.update(dtype="int16", nodata=NODATA, compress="deflate",
                       tiled=True, blockxsize=512, blockysize=512)
        with rasterio.open(raster, "w", **profile) as out:
            out.write(quantise(ds.read(1), levels), 1)
    # A second layer is added to the existing GeoPackage.
    run("gdal_polygonize.py", "-q", raster, "-f", "GPKG", OUT, layer, "flood_level")
    print(f"  {layer}: {factor * 15 / 60:g}'", flush=True)


def main():
    if not SRC.exists():
        sys.exit(f"missing {SRC}; run ./flood_levels.py first")
    work = DATA / "work"
    work.mkdir(parents=True, exist_ok=True)

    levels = zone_levels()
    print("levels:", " ".join(map(str, levels)), flush=True)

    OUT.unlink(missing_ok=True)
    polygonize(work, FACTOR, levels, "zones")
    for layer, factor in OVERVIEWS.items():
        polygonize(work, factor, levels, layer)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
