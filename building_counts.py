import geopandas as gpd

LAKES_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
BUILDINGS_FILEPATH = 'D/Land Cover/Minnesota Buildings.geojson'
OUTPUT_FILEPATH = 'D/Land Cover/surrounding building count.csv'
SEARCH_DIST = 100

lakes = gpd.read_file(LAKES_FILEPATH)

#buildings = gpd.read_file(BUILDINGS_FILEPATH)
import json
with open(BUILDINGS_FILEPATH) as f:
    data = json.load(f)
from shapely.geometry import Polygon
polys = [Polygon(f['geometry']['coordinates'][0]) for f in data['features']]
del data

buildings = gpd.GeoDataFrame({'geometry':polys})
buildings.crs = {'init' :'epsg:4326'}
buildings.to_crs(lakes.crs,inplace=True)

#got 11 buildings that aren't valid. fuck um
buildings = buildings[buildings.geometry.apply(lambda x: x.is_valid)]
buildings.reset_index(drop=True,inplace=True)
bsindex = buildings.sindex

building_count = []

for i in lakes.index:
    possible_matches = list(bsindex.intersection(lakes.loc[i, 'geometry'].buffer(SEARCH_DIST).bounds))
    this_isect = buildings.iloc[possible_matches].geometry.intersection(lakes.loc[i, 'geometry'].buffer(SEARCH_DIST))

    building_count.append(this_isect.count())

import pandas as pd

out_df = pd.DataFrame(lakes[['dowlknum']])
out_df['building count'] = building_count
out_df['building per km shore'] = out_df['building count'] / (lakes['shape_Leng'] / 1000)
out_df['building per km2'] = out_df['building count'] / (lakes['shape_Area'] / 1000000)

out_df.to_csv('D/Land Cover/surrounding building count.csv')