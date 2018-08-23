import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, LineString,MultiLineString
import numpy as np


bathy = gpd.read_file('D/Bathymetry/lake_bathymetric_contours.shp')
bathy['dowlknum'] = bathy['DOWLKNUM'].apply(int)
bathy = bathy[~bathy.geometry.isnull()]
bathy = bathy[bathy.geometry.is_valid]
depths = bathy.groupby('dowlknum').max()['abs_depth']
#convert to meters
depths = depths * 0.305

def get_area_from_linestring(ls):
    if isinstance(ls,LineString):
        if len((ls.coords)) > 3:
            return Polygon(ls).area
        else:
            return 0
    if isinstance(ls,MultiLineString):
        areas = []
        for ls0 in ls:
            if len((ls0.coords)) > 3:
                areas.append(Polygon(ls0).area)
        return sum(areas)

bathy['area'] = bathy.geometry.apply(get_area_from_linestring)
bathy2 = pd.DataFrame(bathy[bathy['abs_depth'].isin([0,5,6,10,20])])
bathy2 = bathy2.groupby(['dowlknum','abs_depth']).sum()['area']
bathy2 = bathy2.apply(lambda x: np.nan if x==0 else x)
bathy2 = bathy2.reset_index().pivot('dowlknum',columns='abs_depth',values='area')

bathy2['shallow share'] = 1.0
for i in bathy2.index:
    if not np.isnan(bathy2.loc[i,5]):
        bathy2.loc[i,'shallow share'] = 1 - (bathy2.loc[i,5] / bathy2.loc[i,0])
    elif not np.isnan(bathy2.loc[i,6]):
        bathy2.loc[i, 'shallow share'] = (1 - (bathy2.loc[i, 6] / bathy2.loc[i, 0])) * (5/6)
    elif not np.isnan(bathy2.loc[i,10]):
        bathy2.loc[i, 'shallow share'] = (1 - (bathy2.loc[i, 10] / bathy2.loc[i, 0])) * (5/10)
    elif not np.isnan(bathy2.loc[i,20]):
        bathy2.loc[i, 'shallow share'] = (1 - (bathy2.loc[i, 20] / bathy2.loc[i, 0])) * (5/20)



out = pd.concat([bathy2,depths],axis=1).drop([0,5,6,10,20],axis=1)
out.reset_index(inplace=True)
out = out[out['shallow share'] >=0]
out= out[~out['shallow share'].isna()]


out.to_csv('D/Bathymetry/Lake Depths.csv',index=False)


#for more lakes can get depth
#https://cf.pca.state.mn.us/water/watershedweb/wdip/waterunit.cfm?wid=10-0095-00