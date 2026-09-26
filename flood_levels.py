#!/usr/bin/env python3
"""Compute, per GEBCO cell, the sea level at which it first connects to the ocean.

A plain contour at +60 m treats every cell below 60 m as sea, including closed
depressions (Caspian, Dead Sea, Qattara) that the ocean cannot reach. Instead
this runs a priority flood from a deep-ocean seed: a cell's flood level is the
lowest sea level at which water can reach it, i.e. the maximum of its own
elevation and the lowest spill point on any path from the ocean.

    flood_level = max(elevation, min over paths from ocean of max elevation on path)

Only -200..+100 m matters for the animation, so elevations are clamped to
[-201, 101] first; the flood is exact within that range. Output values:

    -201       floods at or below -200 m (always water in the animation)
    -200..100  sea level (m) at which the cell becomes sea
     101       does not flood below +100 m

Connectivity is 4-neighbour (water does not leak through diagonal gaps) and
wraps around the antimeridian.

Usage:
    ./flood_levels.py                                 # data/gebco/gebco_2026.vrt
    ./flood_levels.py IN.tif OUT.tif
"""

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from numba import njit
from numba.typed import List

HERE = Path(__file__).resolve().parent
LO, HI = -201, 101  # clamp range; LO = "always water", HI = "never floods"
# a deep Pacific cell (lon, lat) to start the flood from
SEED_LONLAT = (-140.0, 0.0)


@njit(cache=True)
def _push(bufs, sizes, b, idx):
    buf = bufs[b]
    n = sizes[b]
    if n == buf.shape[0]:
        grown = np.empty(buf.shape[0] * 2, dtype=np.uint32)
        grown[:n] = buf[:n]
        bufs[b] = grown
        buf = grown
    buf[n] = idx
    sizes[b] = n + 1


@njit(cache=True)
def priority_flood(z, seed_row, seed_col):
    """In place: z (clamped int16, flat row-major) becomes the flood level."""
    rows, cols = z.shape
    flat = z.reshape(-1)
    nlev = HI - LO + 1
    visited = np.zeros(rows * cols, dtype=np.uint8)

    bufs = List()
    for _ in range(nlev):
        bufs.append(np.empty(1024, dtype=np.uint32))
    sizes = np.zeros(nlev, dtype=np.int64)

    s = seed_row * cols + seed_col
    visited[s] = 1
    _push(bufs, sizes, flat[s] - LO, s)

    for b in range(nlev):
        level = b + LO
        head = 0
        while head < sizes[b]:
            idx = np.int64(bufs[b][head])
            head += 1
            r = idx // cols
            c = idx - r * cols
            for k in range(4):
                if k == 0:
                    if r == 0:
                        continue
                    n = idx - cols
                elif k == 1:
                    if r == rows - 1:
                        continue
                    n = idx + cols
                elif k == 2:
                    n = idx - 1 if c > 0 else idx + cols - 1
                else:
                    n = idx + 1 if c < cols - 1 else idx - cols + 1
                if visited[n]:
                    continue
                visited[n] = 1
                e = flat[n]
                if e >= HI:
                    continue  # never floods in range; no need to expand
                lv = e if e > level else level
                flat[n] = lv
                _push(bufs, sizes, lv - LO, n)
            # compact the FIFO so the (huge) deep-ocean bucket stays small
            if head >= 16777216 and head * 2 >= sizes[b]:
                buf = bufs[b]
                rest = sizes[b] - head
                buf[:rest] = buf[head:sizes[b]]
                sizes[b] = rest
                head = 0
        bufs[b] = np.empty(1, dtype=np.uint32)
        sizes[b] = 0

    # cells the ocean never reached (enclosed by >+100 m terrain)
    for i in range(rows * cols):
        if not visited[i]:
            flat[i] = HI


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data/gebco/gebco_2026.vrt"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "data/flood_level.tif"

    t0 = time.time()
    with rasterio.open(src) as ds:
        profile = ds.profile
        transform = ds.transform
        print(f"reading {src.name} {ds.width}x{ds.height}", flush=True)
        z = ds.read(1)
    np.clip(z, LO, HI, out=z)
    z = z.astype(np.int16, copy=False)

    col, row = ~transform * SEED_LONLAT
    row, col = int(row), int(col)
    if z[row, col] != LO:
        sys.exit(f"seed {SEED_LONLAT} is not deep ocean (z={z[row, col]})")
    print(f"read+clamp {time.time() - t0:.0f}s; flooding", flush=True)

    t1 = time.time()
    priority_flood(z, row, col)
    print(f"flood {time.time() - t1:.0f}s", flush=True)

    profile.update(
        driver="GTiff", dtype="int16", count=1, nodata=None,
        compress="deflate", predictor=2, tiled=True, blockxsize=512, blockysize=512,
        bigtiff="yes", num_threads="all_cpus",
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst, "w", **profile) as out:
        out.write(z, 1)
        out.update_tags(
            description="sea level (m) at which cell connects to the ocean; "
                        f"{LO}=at/below -200, {HI}=above +100",
            source=src.name,
        )
    print(f"-> {dst} ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()
