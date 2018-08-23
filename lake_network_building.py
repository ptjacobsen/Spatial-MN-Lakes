import pandas as pd
import numpy as np
import igraph as g
import json
from time import time
import geopandas as gpd

STREAM_FILEPATH = 'D/DNR HYDRO/corrected streams.geojson'
LAKES_CLEAN_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'

with open(STREAM_FILEPATH) as f:
    data = json.load(f)

def coord_to_str(xyz):
    return str(round(xyz[0])) + ', ' + str(round(xyz[1]))


G = g.Graph(directed=True)
# oddly have to initialize name attribute
G.add_vertex('xxx')

counter = 0
tenpct = int(len(data['features'])/10)
t = time()
for f in data['features']:
    counter +=1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct)* 10) + '%')
        print(time()-t)
        t = time()

    fpoint = coord_to_str(f['geometry']['coordinates'][0][0])
    lpoint = coord_to_str(f['geometry']['coordinates'][0][-1])
    if fpoint not in G.vs['name']:
        G.add_vertex(fpoint)
    if lpoint not in G.vs['name']:
        G.add_vertex(lpoint)
    G.add_edge(fpoint, lpoint,
               length=f['properties']['Shape_Leng'],
               deposit_lake=f['properties'].get('deposit lake'),
               source_lake=f['properties'].get('source lake'))

g.save(G, 'D/DNR HYDRO/corrected streams igraph.pickle')
G = g.read('D/DNR HYDRO/corrected streams igraph.pickle')


def upstream_lakes(G,dowlknum):
    df = pd.DataFrame(index=range(len(G.vs)))
    dep_es = G.es.select(deposit_lake_eq=dowlknum)
    if len(dep_es) == 0:
        return pd.DataFrame(columns=['lake','distance'])
    for i in range(len(dep_es)):
        df[str(i)] = G.shortest_paths_dijkstra(source=dep_es[i].source, weights='length')[0]
    df['short dist'] = df.apply(min, axis=1)
    df = df[df['short dist'] < np.inf]
    df = df[df['short dist'] >= 0]
    #now we have all attached vertices and the shortest difference to them
    src_lakes = []
    dists = []
    for v in df.index:
        for e in G.es(_target = v):
            if e['source_lake'] != '':
                src_lakes.append(e['source_lake'])
                dists.append(df.loc[v,'short dist'])
                break #once we get on source lake there cant be any more
    ld = pd.DataFrame({'lake':src_lakes,
                       'distance':dists})
    #in a rare case we can get two streams that go form one lake to another.
    # that would result in two dists to the same lake
    ld = pd.DataFrame(ld.groupby('lake').min()).reset_index()
    return ld




lakes = gpd.read_file(LAKES_CLEAN_FILEPATH)

dowlknums_str = lakes['dowlknum'].apply(lambda x: str(x).zfill(8))

sdmat = np.empty((len(lakes),len(lakes)))
sdmat.fill(np.nan)


tenpct = int(len(lakes) / 10)
counter = 0
t= time()
for i in dowlknums_str.index: #the index is 0,1,2,3,4...

    counter +=1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct)* 10) + '%')
        print(time()-t)
        t = time()

    up_lakes = upstream_lakes(G,dowlknums_str[i])

    for i2 in up_lakes.index:

        #get the location of this lake in the distance matrix
        #some lakes will be in the network, but not the cleaned lakes file
        # they can be ignored

        try:
            j = dowlknums_str[dowlknums_str == up_lakes['lake'][i2]].index[0]
        except IndexError:
            continue

        if j != i:
            sdmat[i,j] = up_lakes['distance'][i2]

np.save('D/upstream dist matrix',sdmat)

#essentially reflect the matrix over the diagonal to get the down stream.
#in rare cases there will be a stream loop and there will be nonmissing distances in both directions.
#  in that case choose the shorter distance
for i in range(sdmat.shape[0]):
    for j in range(sdmat.shape[1]):
        if i >= j:
            continue
        if (sdmat[i,j] >= 0) & (np.isnan(sdmat[j,i])):
            sdmat[j, i] = sdmat[i,j]
        elif (sdmat[j, i] >= 0) & (np.isnan(sdmat[i, j])):
            sdmat[i, j] = sdmat[j, i]
        elif (sdmat[j, i] >= 0) & (sdmat[i, j] >=0 ):
            print('whoa',i,j)
            if sdmat[i,j] > sdmat[j,i]:
                sdmat[i,j] = sdmat[j,i]

np.save('D/updownstream dist matrix',sdmat)

#matrix stats
