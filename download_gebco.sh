#!/usr/bin/env bash
# Download the GEBCO_2026 global grid (15 arc-second, land + bathymetry) as
# the eight 90x90 degree GeoTIFF tiles published on the CEDA data server, and
# build a single global VRT over them.
#
#   ice_surface_elevation   (default) land/ice surface; ice shelves read as land
#   sub_ice_topo            bedrock under Greenland/Antarctic ice
#
# Usage:
#   ./download_gebco.sh                     # ice surface
#   VARIANT=sub_ice_topo ./download_gebco.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
YEAR="${YEAR:-2026}"
VARIANT="${VARIANT:-ice_surface_elevation}"
OUT_DIR="${OUT_DIR:-$HERE/data/gebco}"
BASE="https://dap.ceda.ac.uk/bodc/gebco/global/gebco_${YEAR}/${VARIANT}/geotiff"

mkdir -p "$OUT_DIR"

tiles=()
for ns in "n90.0_s0.0" "n0.0_s-90.0"; do
    for we in "w-180.0_e-90.0" "w-90.0_e0.0" "w0.0_e90.0" "w90.0_e180.0"; do
        tiles+=("gebco_${YEAR}_${ns}_${we}_geotiff.tif")
    done
done

for t in "${tiles[@]}"; do
    if [[ -f "$OUT_DIR/$t" ]]; then
        echo "have $t"
        continue
    fi
    echo "downloading $t"
    curl -fL --retry 5 --retry-delay 10 -C - -o "$OUT_DIR/$t.part" "$BASE/$t"
    mv "$OUT_DIR/$t.part" "$OUT_DIR/$t"
done

VRT="$OUT_DIR/gebco_${YEAR}.vrt"
gdalbuildvrt -overwrite "$VRT" "${tiles[@]/#/$OUT_DIR/}"
echo "-> $VRT"
