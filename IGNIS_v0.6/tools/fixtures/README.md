# Land mask used only by backend tests

`ne_110m_land.geojson` comes from the [Natural Earth vector repository](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson). Natural Earth publishes its map data in the public domain. This fixture is independent of IGNIS's curated demo centers and lets the offline regression test reject synthetic markers or grid cells placed at sea. Runtime NASA FIRMS observations are never filtered with it.
