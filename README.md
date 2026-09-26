# Coastal zones −130 … +70 m

Vector zones for animating global coastlines under changing sea level, from
roughly the last glacial maximum (−130 m) to +70 m. Geometry is fixed; the
animation only changes styling.

Each polygon has one attribute, `flood_level`: the sea level (m) at which that
area becomes sea **via a connection to the ocean**. A slider at level `L`
paints `flood_level <= L` as water.

Plain contours are not used, because a contour at +60 m also "floods" closed
depressions the ocean can't reach (Caspian, Dead Sea, Qattara). Instead a
priority flood from the open ocean computes, per cell, the lowest sea level at
which water can get there over the lowest saddle. Examples (GEBCO_2026):

| area        | elevation | flood_level | via                     |
|-------------|-----------|-------------|-------------------------|
| Black Sea   | −2200 m   | −28 m       | Bosporus sill           |
| Sea of Azov | −13 m     | −3 m        | Kerch Strait            |
| Caspian Sea | −1000 m   | +25 m       | Manych depression       |
| Dead Sea    | −430 m    | +58 m       | Jezreel valley          |

## Source

GEBCO_2026 Grid, 15 arc-second (~460 m), land + bathymetry, ice-surface
variant, public domain with attribution:

> GEBCO Bathymetric Compilation Group 2026 (2026). The GEBCO_2026 Grid – a
> continuous terrain model for oceans and land at 15 arc-second intervals.
> NERC EDS British Oceanographic Data Centre NOC.
> doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa

Not for navigation. Coastal land heights come from SRTM15+ (≈ surface model:
buildings/vegetation included), so low-lying coasts are only indicative.

## Pipeline

Requires GDAL ≥ 3.8 (PMTiles driver) and a venv with numpy, numba, rasterio:

```bash
uv venv .venv && uv pip install --python .venv/bin/python numpy numba rasterio
```

| step | script | output |
|------|--------|--------|
| 1 | `./download_gebco.sh` | `data/gebco/*.tif` (8 × 890 MB) + `gebco_2026.vrt` |
| 2 | `.venv/bin/python flood_levels.py` | `data/flood_level.tif` (int16, −201…101) |
| 3 | `.venv/bin/python make_zones.py` | `data/zones.gpkg` (~440k polygons, 100 MB) |
| 4 | `./make_tiles.sh` | `data/tiles/coastal_zones.pmtiles` (z0–6, ~20 MB) |

`flood_levels.py` keeps the full −200…+100 m range and needs ~17 GB RAM for
the global grid (~5 min). `make_zones.py` picks the range and steps from it
(`MIN`, `MAX`, `STEP`, `FINE_MIN`, `FINE_MAX`, `FINE_STEP`, `FACTOR`).

### flood_level.tif values

| value      | meaning                                  |
|------------|------------------------------------------|
| −201       | sea at or below −200 m                   |
| −200 … 100 | sea level at which the cell becomes sea  |
| 101        | stays dry up to +100 m                   |

### Zone layer

The flood level is median-resampled to 4′ (~7 km), then rounded **up** to the
next zone level:

    −130, −125, …, −5, −1, 0, 1, …, 10, 15, 20, …, 70

1 m steps from −1 to +10 m, 5 m elsewhere. Today's sea is `flood_level <= -1`;
zone `0` is land at sea level (dry today), so today's coastline is the edge
between zones `-1` and `0`.
`flood_level = -130` is sea at every slider position (the oceans); land that
stays dry above +70 m has no polygon.

Styling at sea level `L`: `flood_level <= L` is water, `L < flood_level <= -1`
is dry sea floor (land colour), anything else transparent so the basemap
shows today's land and lakes (e.g. the Caspian below its +25 m overflow).

## MapLibre

```js
map.addSource('coast', { type: 'vector', url: 'pmtiles://coastal_zones.pmtiles' });
map.addLayer({
  id: 'coast-zones', type: 'fill', source: 'coast', 'source-layer': 'zones',
  paint: {
    'fill-color': ['case',
      ['<=', ['get', 'flood_level'], ['global-state', 'sea_level']], '#9cc3e6',
      'rgba(0,0,0,0)'],
    'fill-antialias': false
  }
});
// slider
map.setGlobalStateProperty('sea_level', 60);
```

(`global-state` needs MapLibre GL JS ≥ 5.6; otherwise rebuild the expression
with `map.setPaintProperty` on each slider change.)
