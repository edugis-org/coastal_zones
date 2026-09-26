#!/usr/bin/env python3
"""Tile count and largest tile per zoom of a PMTiles archive.

make_tiles.sh runs this after tiling: GDAL drops features from a tile that
exceeds MAX_SIZE without a word, so the largest tile per zoom is the number to
watch.

Usage:
    .venv/bin/python tile_stats.py [data/tiles/coastal_zones.pmtiles]
"""

import sys
from collections import defaultdict
from pathlib import Path

from pmtiles.reader import MmapSource, Reader, all_tiles

HERE = Path(__file__).resolve().parent
PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data" / "tiles" / "coastal_zones.pmtiles"


def main():
    count = defaultdict(int)
    largest = defaultdict(lambda: (0, None))
    with open(PATH, "rb") as f:
        for (z, x, y), data in all_tiles(MmapSource(f)):
            count[z] += 1
            if len(data) > largest[z][0]:
                largest[z] = (len(data), (x, y))
    print(" z  tiles  largest (compressed)")
    for z in sorted(count):
        size, (x, y) = largest[z]
        print(f"{z:2} {count[z]:6}  {size / 1e6:6.2f} MB  {z}/{x}/{y}")


if __name__ == "__main__":
    main()
