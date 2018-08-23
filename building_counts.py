import geopandas as gpd
import pandas as pd

LAKES_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
BUILDINGS_FILEPATH = 'D/Land Cover/Minnesota Buildings.geojson'
OUTPUT_FILEPATH = 'D/Land Cover/surrounding building count.csv'
SEARCH_DIST = 50

lakes = gpd.read_file(LAKES_FILEPATH)

#Using Microsoft's new public database of building footprints, find the number of buildings immediately surrounding
# each lake. This will be used as a proxy for human interation in the model



#buildings = gpd.read_file(BUILDINGS_FILEPATH) #ran through 24gb of ram/swap like it was nothing. wtf
#No problem at all doing it manually with json
import json
with open(BUILDINGS_FILEPATH) as f:
    data = json.load(f)
from shapely.geometry import Polygon
polys = [Polygon(f['geometry']['coordinates'][0]) for f in data['features']]
del data

buildings = gpd.GeoDataFrame({'geometry':polys})
buildings.crs = {'init' :'epsg:4326'}
buildings.to_crs(lakes.crs,inplace=True)

#got 11 buildings that aren't valid. fuck em
buildings = buildings[buildings.geometry.apply(lambda x: x.is_valid)]
buildings.reset_index(drop=True,inplace=True)

#using spatial index, loop find the intersection between the 100 meter buffer of the lake and the building footprints
#number of intersection polygons is our building count.
#note any part of the footprint within 100m of the lake
bsindex = buildings.sindex
building_count = []
for i in lakes.index:
    possible_matches = list(bsindex.intersection(lakes.loc[i, 'geometry'].buffer(SEARCH_DIST).bounds))
    this_isect = buildings.iloc[possible_matches].geometry.intersection(lakes.loc[i, 'geometry'].buffer(SEARCH_DIST))
    building_count.append(this_isect.count())



out_df = pd.DataFrame(lakes[['dowlknum']])
out_df['building count'] = building_count
out_df['building per km shore'] = out_df['building count'] / (lakes['shape_Leng'] / 1000)
out_df['building per km2'] = out_df['building count'] / (lakes['shape_Area'] / 1000000)

out_df.to_csv(OUTPUT_FILEPATH,index=False)