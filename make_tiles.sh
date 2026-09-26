#!/usr/bin/env bash
# Build a PMTiles file with one vector layer `zones` from the zone polygons,
# for a MapLibre sea-level slider:
#
#   fill-color: flood_level <= slider ? water : transparent (land background)
#
# Uses the GDAL PMTiles/MVT driver (GDAL >= 3.8, no tippecanoe needed).
# The 4' source holds up to ~z6; MapLibre overzooms beyond MAXZOOM.
#
# Low zooms are tiled from coarser layers (`zones_z0_1`, `zones_z2`, see
# make_zones.py) under the same layer name `zones`, so a world tile is not
# 340k sub-pixel slivers. MAX_SIZE is set far above what a tile needs: when a
# tile exceeds it, GDAL drops features without a word, and a dropped zone is a
# hole through which today's sea shows. The largest tile per zoom is printed
# afterwards to keep an eye on that.
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

# One entry per GeoPackage layer: `zones` from the first zoom no overview
# covers, `zones_z<a>[_<b>]` at zooms a..b, all written as layer `zones`.
CONF=$(ogrinfo -ro -q "$SRC" | sed -n 's/^[0-9]*: \([a-z0-9_]*\).*/\1/p' | python3 -c '
import json, re, sys
layers = sys.stdin.read().split()
conf, first = {}, 0
for name in layers:
    m = re.fullmatch(r"zones_z(\d+)(?:_(\d+))?", name)
    if m:
        lo, hi = int(m[1]), int(m[2] or m[1])
        conf[name] = {"target_name": "zones", "minzoom": lo, "maxzoom": hi}
        first = max(first, hi + 1)
conf["zones"] = {"target_name": "zones", "minzoom": first, "maxzoom": int(sys.argv[1])}
print(json.dumps(conf))' "$MAXZOOM")
LAYERS=$(python3 -c 'import json,sys; print(" ".join(json.loads(sys.argv[1])))' "$CONF")
echo "layers: $CONF"

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
echo "tiling $(basename "$SRC") -> $OUT (z0-$MAXZOOM)"
# shellcheck disable=SC2086
ogr2ogr -f PMTiles "$OUT" "$SRC" $LAYERS \
    -dsco "MINZOOM=0" -dsco "MAXZOOM=$MAXZOOM" \
    -dsco "NAME=Coastal zones" \
    -dsco "DESCRIPTION=flood_level: sea level (m) at which the area connects to the ocean (GEBCO_2026)" \
    -dsco "TYPE=overlay" \
    -dsco "CONF=$CONF" \
    -dsco "MAX_SIZE=20000000" \
    -dsco "MAX_FEATURES=5000000" \
    -dsco "SIMPLIFICATION=${SIMPLIFICATION:-1}"

echo "  -> $OUT ($(du -h "$OUT" | cut -f1))"
"$HERE/.venv/bin/python" "$HERE/tile_stats.py" "$OUT"
