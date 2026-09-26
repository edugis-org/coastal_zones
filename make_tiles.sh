#!/usr/bin/env bash
# Build one PMTiles file from the three zone resolutions. All three go into a
# single vector layer `zones`, each over its own zoom range, so the client
# styles one layer:
#
#   fill-color: flood_level <= slider ? water : land
#
# Uses the GDAL PMTiles/MVT driver (GDAL >= 3.8, no tippecanoe needed).
#
# Usage:
#   ./make_tiles.sh               # STEP=5
#   STEP=10 MAXZOOM=10 ./make_tiles.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
STEP="${STEP:-5}"
MAXZOOM="${MAXZOOM:-9}"
DATA="$HERE/data"
OUT="${OUT:-$DATA/tiles/coastal_zones_${STEP}m.pmtiles}"

for r in r0 r1 r2; do
    f="$DATA/zones_${r}_${STEP}m.gpkg"
    [[ -f "$f" ]] || { echo "missing $f; run ./make_zones.py" >&2; exit 1; }
done

# one VRT exposing the three resolutions as separate source layers
VRT="$DATA/work/zones_${STEP}m.vrt"
cat > "$VRT" <<EOF
<OGRVRTDataSource>
  <OGRVRTLayer name="zones_r2"><SrcDataSource>$DATA/zones_r2_${STEP}m.gpkg</SrcDataSource><SrcLayer>zones</SrcLayer></OGRVRTLayer>
  <OGRVRTLayer name="zones_r1"><SrcDataSource>$DATA/zones_r1_${STEP}m.gpkg</SrcDataSource><SrcLayer>zones</SrcLayer></OGRVRTLayer>
  <OGRVRTLayer name="zones_r0"><SrcDataSource>$DATA/zones_r0_${STEP}m.gpkg</SrcDataSource><SrcLayer>zones</SrcLayer></OGRVRTLayer>
</OGRVRTDataSource>
EOF

CONF=$(cat <<EOF
{
  "zones_r2": {"target_name": "zones", "minzoom": 0, "maxzoom": 3},
  "zones_r1": {"target_name": "zones", "minzoom": 4, "maxzoom": 6},
  "zones_r0": {"target_name": "zones", "minzoom": 7, "maxzoom": $MAXZOOM,
               "description": "flood_level: sea level (m) at which the area connects to the ocean, step ${STEP} m; 101 = above +100 m"}
}
EOF
)

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
echo "tiling -> $OUT (z0-$MAXZOOM)"
ogr2ogr -f PMTiles "$OUT" "$VRT" \
    -dsco "CONF=$CONF" \
    -dsco "MINZOOM=0" -dsco "MAXZOOM=$MAXZOOM" \
    -dsco "NAME=Coastal zones -200..+100 m (${STEP} m)" \
    -dsco "DESCRIPTION=Ocean-connected flood levels from GEBCO_2026" \
    -dsco "TYPE=overlay" \
    -dsco "MAX_SIZE=1500000" \
    -dsco "MAX_FEATURES=500000" \
    -dsco "SIMPLIFICATION=${SIMPLIFICATION:-1}"

echo "  -> $OUT ($(du -h "$OUT" | cut -f1))"
