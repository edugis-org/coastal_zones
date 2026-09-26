# Coastal zones −134 … +70 m

Vector zones for animating global coastlines under changing sea level, from
the lowest sea level of the last glacial maximum (−134 m, ~21 ka) to +70 m. Geometry is fixed; the
animation only changes styling.

## Goal

The goal of this dataset is an animation of sea-level rise since the last
glacial maximum up to now, and of the maximum possible rise in the future (up
to +70 m). Sea level was lowest, about −134 m, at ~21 ka, after a slow fall
from ~29 ka; the main rise started ~16.5 ka (Lambeck et al. 2014,
[doi:10.1073/pnas.1411762111](https://doi.org/10.1073/pnas.1411762111)).

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
uv venv .venv && uv pip install --python .venv/bin/python numpy numba rasterio pmtiles
```

| step | script | output |
|------|--------|--------|
| 1 | `./download_gebco.sh` | `data/gebco/*.tif` (8 × 890 MB) + `gebco_2026.vrt` |
| 2 | `.venv/bin/python flood_levels.py` | `data/flood_level.tif` (int16, −201…101) |
| 3 | `.venv/bin/python make_zones.py` | `data/zones.gpkg`: `zones` (4′, ~450k polygons) plus `zones_z0_1` (16′) and `zones_z2` (8′) |
| 4 | `./make_tiles.sh` | `data/tiles/coastal_zones.pmtiles` (z0–6, ~15 MB), then `tile_stats.py` |

Low zooms are tiled from the coarser layers, all under the one source layer
`zones`. At z0 a screen pixel is ~40′, so 4′ zones are sub-pixel slivers, and a
world tile holding all of them (340k polygons) exceeded the tiler's size limit
— GDAL then drops features without a word, and every dropped zone is a hole
through which the basemap's sea shows (the Bering land bridge at −134 m, on
small maps only). `MAX_SIZE` is now far above what any tile needs, and
`tile_stats.py` prints the largest tile per zoom after every build.

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

    −134, −130, −125, …, −5, −1, 0, 1, …, 10, 15, 20, …, 70

1 m steps from −1 to +10 m, 5 m elsewhere. Today's sea is `flood_level <= -1`;
zone `0` is land at sea level (dry today), so today's coastline is the edge
between zones `-1` and `0`.
`flood_level = -134` is sea at every slider position (the oceans); land that
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

## Download

The tile archive is published as a release asset, so it needs no build:

```bash
gh release download --repo edugis-org/coastal_zones --pattern coastal_zones.pmtiles
# or
curl -LO https://github.com/edugis-org/coastal_zones/releases/latest/download/coastal_zones.pmtiles
```

Release assets are not served with CORS headers, so a browser cannot read
them directly: copy the archive to your own static host (any host that
answers HTTP range requests, GitHub Pages included).

## Licence

- **Scripts**: MIT.
- **Data products** (`flood_level.tif`, `zones.gpkg`, `coastal_zones.pmtiles`):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

These data exist thanks to GEBCO, whose grid is in the public domain and may
be copied, adapted and used commercially, on condition that the source is
acknowledged (GEBCO terms of use). The attribution for these data therefore
names both:

> Coastal zones: EduGIS (github.com/edugis-org/coastal_zones), derived from
> the GEBCO_2026 Grid, GEBCO Bathymetric Compilation Group 2026,
> doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa

A short form for a map's attribution control is
`Coastal zones: EduGIS, from GEBCO_2026 Grid`.

These data are not endorsed by GEBCO, the IHO or the IOC, and — like the
GEBCO Grid — must not be used for navigation or safety at sea.

## Used by

The [webmapx](https://github.com/edugis-org/webmapx) sea level tool
(`type: "sealevel"`) drives this layer with a slider from −134 m to +70 m,
optionally through time along a sea level curve. Configuration and behaviour:
[docs/user/components/webmapx-sealevel-tool.md](https://github.com/edugis-org/webmapx/blob/main/docs/user/components/webmapx-sealevel-tool.md).

## Todo

- Figure out how inland seas (Caspian, Black Sea, Baltic) behaved before they
  connected to the oceans; the model now treats them as flooding only once the
  ocean spills over their sill.
- The Mediterranean disconnection (Messinian, ~5 Ma ago) is not included.
- A more precise model for the Netherlands, Belgium and Bangladesh would be
  nice.
- Check whether land ice cover (extent of the ice sheets) is known for the
  last 21,000 years, to show it alongside the sea level.
