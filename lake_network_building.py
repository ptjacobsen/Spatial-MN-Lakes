
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from numpy import nan

LAKES_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
STREAMS_FILEPATH = 'D/DNR HYDRO/streams.geojson'
OUTPUT_FILEPATH = 'D/DNR HYDRO/corrected streams.geojson'
BUFFER = 15 #allow lakes to match with streams with X meters


#Goal of this is to create a traceable network of lakes through rivers and streams and other lakes
# The main problem with the current hydrological data is that streams do not indicate which lakes they go into or run out of
# we want to be able to select a lake and determine the lakes that are upstream and their distances

lakes = gpd.read_file(LAKES_FILEPATH)
streams = gpd.read_file(STREAMS_FILEPATH)

## 1. Clean Lake Data
# remove river polygons
lakes = lakes[lakes['wb_class'] != 'Riverine polygon']
lakes = lakes[lakes['wb_class'] != 'Riverine island']
lakes = lakes[lakes['wb_class'] != 'Island or Land']
# clean up some weird lakes
bad_lake_fids = [84323, 82458]
lakes = lakes[~lakes['fid'].isin(bad_lake_fids)]

# Mud lake is invalid but there's a quick fix, i guess
lakes.geometry[125707] = lakes.loc[125707, 'geometry'].buffer(0)

#remove '<Null>' and 00000000 and 0 from dowlknums
def cleandowlknum(dowlknum):
    if dowlknum in ['<Null>','']:
        return ''
    elif int(dowlknum)==0:
        return ''
    else:
        return dowlknum
lakes['dowlknum'] = lakes['dowlknum'].apply(cleandowlknum)

##remove full lakes and only keep the sub basin
# theres no main basin variables. (sub_flag=N for all lakes, not just those with subbasin)
# so we have to find all the subbasins, get their parent dowlknum from their dowlknum
sublakes = lakes[lakes['sub_flag'] == 'Y']
full_basin_dowlknums = sublakes['dowlknum'].apply(lambda x: x[:-2] + '00' if len(x) > 0 else x).unique()
lakes = lakes[~lakes['dowlknum'].isin(full_basin_dowlknums)]

## 2. Clean Stream data
# going to remove intermittent streams to simplify and speed. Might be useful to try with these included
unimportant_stream_types = ['Stream (Intermittent)', 'Drainage Ditch (Intermittent)']
streams = streams[~streams['Strm_type_'].isin(unimportant_stream_types)]
# clean up some weird streams
bad_stream_fids = [88915, 88382, 77181, 41905, 116915, 116916, 116913, 88382]
streams = streams[~streams['fid'].isin(bad_stream_fids)]


## 3. Remove lake connector streams inside of lakes
# often times these lake connector streams expand outside the lake boundaries.
# so what we want to do is keep the little segments outside the lake and redefine them as perennial streams

connectors = streams[streams['Strm_type_'].isin(['Connector (Lake)', 'Connector (Wetland)'])]
# 20k
lsindex = lakes.sindex

print('Processing lake connecting streams...')

counter = 0
tenpct = int(len(connectors)/10)

for c in connectors.index:
    counter += 1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct * 10)) + '%')

    # first have to find the lake that this connector is connecting under
    possible_matches = list(lsindex.intersection(connectors.loc[c].geometry.bounds))
    isect = lakes.iloc[possible_matches].intersection(connectors.loc[c].geometry)
    lakes_connections = isect[~isect.isna()]
    if len(lakes_connections) == 0:  # then this lake connector is just out in the open somewhere
        streams.loc[c, 'Strm_type_'] = 'Stream (Perennial)'
        continue
    # get the lake that it overlaps most. 99% of the time it will just be one lake, but occasionally an edge will overlap with another
    lake_connected = lakes_connections.apply(lambda x: x.length).sort_values(ascending=False).index[0]

    outside_the_lake = connectors.loc[c].geometry.difference(lakes.loc[lake_connected].geometry)

    if outside_the_lake.length < BUFFER:
        continue
    else:
        streams.loc[c, 'Strm_type_'] = 'Stream (Perennial)'
        # streams.loc[lakes_connected[0], 'geometry'] = MultiLineString([outside_the_lake])
        try:
            # "improper" way to set values in pandas, but this way works and the proper way doesn't
            streams.geometry[c] = MultiLineString([outside_the_lake])
        except NotImplementedError:
            # in rare cases we'll get extensions on both ends of the connector. so type(outside_the_lake)=multilinestring so the above fails
            # ideally we would add a new feature, but this is getting too deep so I will just take one of them
            streams.geometry[c] = MultiLineString([outside_the_lake[0]])

#remove the rest of the connectors
streams = streams[streams['Strm_type_'] != 'Connector (Lake)']
streams = streams[streams['Strm_type_'] != 'Connector (Wetland)']




## 4. Check which streams run into each lake and which runout
# do this by looping through each lake, seeing which streams intersect it,
# of the streams that intersect, check which way they going and note in the stream table its source/deposit

streams['deposit lake id'] = ''
streams['source lake id'] = ''
streams['deposit lake'] = ''
streams['source lake'] = ''

# build the spatial indices
ssindex = streams.sindex  # 5 seconds to generate

counter = 0
tenpct = int(len(lakes) / 10)
print('Finding  stream/lake intersections...')

for i in lakes.index:
    counter += 1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct * 10)) + '%')


    # t=time()
    # this_isect = streams.geometry.intersection(lakes.loc[i,'geometry'].buffer(1)) #with or without geometry is fine
    # print(time()-t) #this takes 5.6 seconds so I figured out spatial indices in geopandas to make it faster

    possible_matches = list(ssindex.intersection(lakes.loc[i, 'geometry'].buffer(BUFFER).bounds))
    this_isect = streams.iloc[possible_matches].geometry.intersection(lakes.loc[i, 'geometry'].buffer(BUFFER))
    streams_connected = this_isect[~this_isect.isna()]

    for j in streams_connected.index:
        # originally excluded lakes that intersected twice, usually tiny streams that went from part of the lake
        # to another
        # but there were some instances of stream connections being missed because of this
        # so there are now a lot of weird lake connector streams because they go to a tiny stream that just deposits
        # back into the lake. They do not affect the end result of finding the shortest route between lakes
        # because these loops in the final graph

        # if isinstance(streams_connected[j], MultiLineString):
        #     #continue  # the stream hits the lake at more than one point. probably a weirld lake to same lake stream that should be ignore
        # elif isinstance(streams_connected[j], LineString):
        #     # get the first point of the stream, is it in the over lap?
        #     fpoint = list(streams.geometry[j])[0].coords[0]
        #     lpoint = list(streams.geometry[j])[0].coords[-1]

        fpoint = list(streams.geometry[j])[0].coords[0]
        lpoint = list(streams.geometry[j])[0].coords[-1]

        if isinstance(streams_connected[j], MultiLineString):
            coord_list = list(streams_connected[j][0].coords)
        elif isinstance(streams_connected[j], LineString):
            coord_list = list(streams_connected[j].coords)
        else:
            coord_list = None

        if fpoint in coord_list:  # this stream ends at this lake
            streams.loc[j, 'deposit lake id'] = i
            streams.loc[j, 'deposit lake'] = lakes.loc[i, 'dowlknum']
        if lpoint in coord_list:  # this stream begins at this lake
            streams.loc[j, 'source lake id'] = i
            streams.loc[j, 'source lake'] = lakes.loc[i, 'dowlknum']

## 5. Since we decided to use only lake sub-basins, we need to create new stream features that connect each basin to the others

new_geos = []
deposit_lakes_ids = []
deposit_lakes = []
source_lakes = []
source_lakes_ids = []

counter = 0
print('Creating inter-basin links...')

for i in lakes.index:
    counter += 1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct * 10)) + '%')

    #find the other lakes this lake touchs, usually subbasins, but not always
    possible_matches = list(lsindex.intersection(lakes.loc[i, 'geometry'].bounds))
    this_isect = lakes.iloc[possible_matches].geometry.intersection(lakes.loc[i, 'geometry'])
    lakes_connected = this_isect[~this_isect.isna()]

    for lc in lakes_connected.index:
        p = Point()

        if i <= lc:  # only need one point per connections, eg, not (5,6) just (6,5). and of course not when (6,6)
            continue
        elif isinstance(lakes_connected[lc], MultiLineString):
            p = lakes_connected[lc][0].representative_point()
        elif isinstance(lakes_connected[lc], LineString):
            p = lakes_connected[lc].representative_point()
        elif isinstance(lakes_connected[lc], Polygon):
            p = lakes_connected[lc].representative_point()
        else:
            continue
        p = Point(p.x, p.y, 0)
        new_geos.append(MultiLineString([LineString([p, p])]))
        deposit_lakes_ids.append(lc)
        deposit_lakes.append(lakes.loc[lc, 'dowlknum'])
        source_lakes_ids.append(i)
        source_lakes.append(lakes.loc[i, 'dowlknum'])
        # flow going both directions in same lake basins
        new_geos.append(MultiLineString([LineString([p, p])]))
        deposit_lakes_ids.append(lc)
        deposit_lakes.append(lakes.loc[i, 'dowlknum'])
        source_lakes_ids.append(i)
        source_lakes.append(lakes.loc[lc, 'dowlknum'])

starting_fid = int(streams['fid'].max() + 1)
my_generated_streams1 = gpd.GeoDataFrame({'geometry': new_geos,
                                          'Shape_Leng': 0,
                                          'deposit lake id': deposit_lakes_ids,
                                          'deposit lake': deposit_lakes,
                                          'source lake id': source_lakes_ids,
                                          'source lake': source_lakes,
                                          'Strm_type_': 'Basin Connector',
                                          'Strm_type': 69,
                                          'fid': range(starting_fid, starting_fid + len(new_geos))})
streams = streams.append(my_generated_streams1).reset_index()

## 6. construct new stream features connecting deposit points to source points in each lake
# currently just a straight-line but could be upgraded to be a linestring contained inside polygon to better
# represent distance

new_geos = []
lengths = []

counter = 0
print('Creating intra-lake links...')

for i in lakes.index:

    counter += 1
    if counter % tenpct == 0:
        print(str(counter / tenpct) + '%')

    entering_streams = streams[streams['deposit lake id'] == i].index
    leaving_streams = streams[streams['source lake id'] == i].index

    if (len(entering_streams) == 0) | (len(leaving_streams) == 0):
        continue
    else:
        for j in leaving_streams:
            for k in entering_streams:
                # the last point of the leaving stream, becomes the first point of the in-lake stream
                fpoint = list(streams.geometry[j])[0].coords[-1]
                # the first point of the entering stream, becomes the last point of the in-lake stream
                lpoint = list(streams.geometry[k])[0].coords[0]
                linestream = LineString((fpoint, lpoint))
                # will be a multilinestring containing a single line to match the rest of the streams
                new_geos.append(MultiLineString([linestream]))
                lengths.append(linestream.length)

starting_fid = int(streams['fid'].max() + 1)
my_generated_streams2 = gpd.GeoDataFrame({'geometry': new_geos,
                                          'Shape_Leng': lengths,
                                          'Strm_type_': 'Connector (Lake)',
                                          'Strm_type': 60,
                                          'fid': range(starting_fid, starting_fid + len(new_geos))})

streams = streams.append(my_generated_streams2).reset_index()
streams.drop(['source lake id', 'deposit lake id'], axis=1, inplace=True)

##7. Save new streams to file
print('Saving new stream network to file...')

streams.to_file(OUTPUT_FILEPATH,driver='GeoJSON')

#Using igraph because of it's query capabilities, even though it is slow to build

import igraph as g
import json

with open(OUTPUT_FILEPATH) as f:
    data = json.load(f)

def coord_to_str(xyz):
    return str(round(xyz[0])) + ', ' + str(round(xyz[1]))


G = g.Graph(directed=True)
# oddly have to initialize name attribute
G.add_vertex('xxx')

counter = 0
tenpct = int(len(data['features'])/10)

for f in data['features']:
    counter +=1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct)* 10) + '%')

    fpoint = coord_to_str(f['geometry']['coordinates'][0][0])
    lpoint = coord_to_str(f['geometry']['coordinates'][0][-1])
    if fpoint not in G.vs['name']:
        G.add_vertex(fpoint)
    if lpoint not in G.vs['name']:
        G.add_vertex(lpoint)
    G.add_edge(fpoint, lpoint,
               length=f['properties']['Shape_Leng'],
               deposit_lake=f['properties']['deposit lake'],
               source_lake=f['properties']['source lake'])

g.save(G, 'D/DNR HYDRO/corrected streams igraph.pickle')

G = g.read('D/DNR HYDRO/corrected streams igraph.pickle')

import pandas as pd
import numpy as np

def upstream_lakes(G,dowlknum):
    df = pd.DataFrame(index=range(len(G.vs)))
    dep_es = G.es.select(deposit_lake_eq=dowlknum)
    for i in range(len(dep_es)):
        df[str(i)] = G.shortest_paths_dijkstra(source=dep_es[i].source, weights='length')[0]
    df['short dist'] = df.apply(min, axis=1)
    df = df[df['short dist'] < np.inf]
    df = df[df['short dist'] > 0]
    #now we have all attached vertices and the shortest difference to them
    src_lakes = []
    dists = []
    for v in df.index:
        for e in G.es(_target = v):
            if e['source_lake'] is not None:
                src_lakes.append(e['source_lake'])
                dists.append(df.loc[v,'short dist'])
                break #once we get on source lake there cant be any more
    ld = pd.DataFrame({'lake':src_lakes,
                       'distance':dists})
    #in a rare case we can get two streams that go form one lake to another.
    # that would result in two dists to the same lake
    ld = pd.DataFrame(ld.groupby('lake').min()).reset_index()
    return ld

