import geopandas as gpd
import pandas as pd
LAKES_FILEPATH = 'D/DNR HYDRO/lakes.geojson'
LAKES_CLEAN_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
LAKES_CLEAN_SHP_FILEPATH = 'D/DNR HYDRO/lakes clean'
SAMPLES_FILEPATH = 'D/Water Samples/by lake.csv'

lakes = gpd.read_file(LAKES_FILEPATH)

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

lakes['dowlknum'] = lakes['dowlknum'].apply(int)
#drop lake superior
lakes = lakes[lakes['dowlknum']!=16000100]

#mostly on the border and have instate/outstate representations
lakes = lakes[lakes['outside_mn']!='Y']

#some odd duplicates exist for "alternative geometries".
#see metadata ftp://ftp.gisdata.mn.gov/pub/gdrs/data/pub/us_mn_state_dnr/water_dnr_hydrography/metadata/metadata.html
dups = lakes.duplicated('dowlknum',keep=False)
lakes = lakes[~(dups & lakes['fw_id'].isin([88888,0]))]

#one more duplicate that has no logic
lakes = lakes[lakes['fid']!=61584]

#Keep only those in the the samples
lakes_w_tsi = pd.read_csv(SAMPLES_FILEPATH,usecols=['dowlknum'])

lakes = lakes[lakes['dowlknum'].isin(lakes_w_tsi['dowlknum'])]
#loss of 29 lakes not bad

useless_columns = ['fw_id','lake_class', 'acres', 'shore_mi','center_utm','center_u_1','dnr_region','fsh_office',
                   'outside_mn','delineated','delineatio','delineat_1','delineat_2','approved_b','approval_d',
                   'approval_n','has_flag','publish_da','has_wld_fl','unique_id','created_us','pw_sub_nam',
                   'created_da','last_edite','last_edi_1','ow_use','map_displa','INSIDE_X','INSIDE_Y']

lakes.drop(useless_columns,axis=1,inplace=True)



#attach water basins
#DNR level 8 the smalles
l8 = gpd.read_file('D/DNR WATERSHED/DNR_Level_8.shp')
l8 = l8[['AREA','MAJOR','MINOR5','CATCH_ID','geometry']]
l8.columns = ['ws 8 area','ws major','ws minor','ws 8','geometry']


#3389 before
lakes = gpd.sjoin(lakes,l8,how='left',op='intersects')
#3966 after. I think this is because there are some that are in both
#index_right column has been added. its is the index from l8

lakes.reset_index(drop=True,inplace=True)

#lets check it out
dups = lakes[lakes.duplicated('dowlknum',keep=False)]
overlaps = []
#for each lake that has been duplicated by the spatial join.
# these lakes exist in two watersheds, usually right on the edge
for i in range(len(dups)):
    # get the polygon of the lake
    lake_poly = dups.iloc[i]['geometry']

    #get the polgon of the watershed using the index column added in the spatial join
    l8_index = dups.iloc[i]['index_right']
    watershed_poly = l8.loc[l8_index,'geometry']

    #calculate the overlap area between each
    overlaps.append(lake_poly.intersection(watershed_poly).area)

# in the dataframe of the duplicates sort by lake and overlaps size.
# the ones with the small overlap are labelled as bad and will be removed
dups['overlap area'] = overlaps
dups.sort_values(['dowlknum','overlap area'],ascending=[True,False],inplace=True)
dups['bad'] = dups.duplicated('dowlknum',keep='first')

#back to 3389
lakes = lakes.drop(dups[dups['bad']].index)
lakes = lakes.drop('index_right',1)

lakes.to_file(LAKES_CLEAN_FILEPATH,driver='GeoJSON')

lakes.to_file(LAKES_CLEAN_SHP_FILEPATH) #for easier viewing
