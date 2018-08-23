from shapely.geometry import Polygon, MultiPolygon
import geopandas as gpd
import numpy as np

LAKES_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
OUT_MATRIX_FILEPATH = 'D/dist matrix'

# Doesn't really make sense to use centroid to centroid distance for lakes, especially with close distances
# Using centroids, larger lakes will be defined as farther away than it really is
# I think logically it makes more sense to do shoreline to shoreline distance
# this is a computationally intensive task, so i only do it in close region. precision matters less the farther out
# so for lakes that are less than 20km centroid to centroid, calculate their edge to edge distance

lakes = gpd.read_file(LAKES_FILEPATH)

#functions that will calculate the shortest distance between two polygons
#in theory this is incorrect because we are only checking vertices, not edges, so we miss when a midpoint of an edge
#is the nearest point.
#But these lakes have so many vertices that precision is trivial in this case.
def dist(xy1,xy2):
    return np.sqrt((xy1[0]-xy2[0])**2 + (xy1[1]-xy2[1])**2)
def poly_dist(p1,p2):
    ds = [dist(xy1,xy2) for xy1 in p1.exterior.coords for xy2 in p2.exterior.coords]
    return np.min(ds)


dmat = np.empty((len(lakes),len(lakes)))
dmat.fill(np.nan)

ctds = lakes.centroid
assert lakes.index[-1] == (len(lakes)-1)
tempidx = list(lakes.index[:-1])
tempidx.reverse()
#for i in lakes.index[:-1]):
for i in tempidx:
    #first take lakes only where i<j so we don't compute the same distance twice
    this_lake = lakes.loc[i,'geometry']
    dists = ctds[(i+1):].apply(lambda x: x.distance(this_lake.centroid))

    if isinstance(this_lake, Polygon):  # convert all to multipoly for consistency
        this_lake = MultiPolygon([this_lake])
    print(i)
    #when the distance is less than 20km, calculate border to border distance
    for j in dists.index:
        if dists.loc[j] < 20000:
            to_polys = lakes.loc[j,'geometry']
            if isinstance(to_polys,Polygon): #convert all to multipoly for consistency
                to_polys = MultiPolygon([to_polys])

            dists.loc[j] = np.min([poly_dist(this_poly,to_poly) for this_poly in this_lake
                                                                    for to_poly in to_polys])

    dmat[i,(i+1):] = dists.values

#mirror the matrix over the diagonal so [i,j] == [j,i]
#the diagonal will remain nan
for i in range(len(lakes)):
    for j in range(i+1,len(lakes)):
            dmat[j,i] = dmat[i,j]

np.save(OUT_MATRIX_FILEPATH,dmat)
