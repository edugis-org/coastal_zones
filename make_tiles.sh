#!/usr/bin/env bash
# Build a PMTiles file with one vector layer `zones` from the zone polygons,
# for a MapLibre sea-level slider:
#
#   fill-color: flood_level <= slider ? water : transparent (land background)
#
# Uses the GDAL PMTiles/MVT driver (GDAL >= 3.8, no tippecanoe needed).
# The 4' source holds up to ~z6; MapLibre overzooms beyond MAXZOOM.
#
# Usage:
#   ./make_tiles.sh
#   MAXZOOM=7 ./make_tiles.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MAXZOOM="${MAXZOOM:-6}"
SRC="$HERE/data/zones.gpkg"
OUT="${OUT:-$HERE/data/tiles/coastal_zones.pmtiles}"

[[ -f "$SRC" ]] || { echo "missing $SRC; run ./make_zones.py" >&2; exit 1; }

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
echo "tiling $(basename "$SRC") -> $OUT (z0-$MAXZOOM)"
ogr2ogr -f PMTiles "$OUT" "$SRC" zones \
    -dsco "MINZOOM=0" -dsco "MAXZOOM=$MAXZOOM" \
    -dsco "NAME=Coastal zones" \
    -dsco "DESCRIPTION=flood_level: sea level (m) at which the area connects to the ocean (GEBCO_2026)" \
    -dsco "TYPE=overlay" \
    -dsco "MAX_SIZE=1500000" \
    -dsco "MAX_FEATURES=500000" \
    -dsco "SIMPLIFICATION=${SIMPLIFICATION:-1}"

echo "  -> $OUT ($(du -h "$OUT" | cut -f1))"
