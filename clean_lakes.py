import geopandas as gpd

LAKES_FILEPATH = 'D/DNR HYDRO/lakes.geojson'
LAKES_CLEAN_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'

lakes = gpd.read_file(LAKES_FILEPATH)

# bad_classes = ['Riverine island','Island or Land']
# lakes = lakes[~lakes['wb_class'].isin(bad_classes)]

good_classes = ['Lake or Pond','Reservoir','Mine or Gravel Pit','Artificial Basin']
lakes = lakes[lakes['wb_class'].isin(good_classes)]

bad_lake_fids = [84323, 82458,
                 74280,74424, #sub basins of cedar lake near mille lacs. no main basin and samples match to main basin
                 109255,109663,109321,109122, #weird tiny subbasin of Whiteface Reservoir. Samples match up to whole lake
                 31678, #Cenaiko near MPLS tiny mini basin
                 92821,116858,82252,22499,23944,93829,97042,13000,110278 #some duplicate dowlknums. mos
                 ]
lakes = lakes[~lakes['fid'].isin(bad_lake_fids)]

# Mud lake is invalid but there's a quick fix, i guess
#lakes.geometry[125707] = lakes.loc[125707, 'geometry'].buffer(0)
# removed already because it's a wetland

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

# keep only those with dowlknum
lakes = lakes[lakes['dowlknum']!='']

lakes['dowlknum'] = lakes['dowlknum'].apply(int)

lakes = lakes[~(lakes['outside_mn']=='Y')]


useless_columns = ['fw_id','lake_class', 'acres', 'shore_mi','center_utm','center_u_1','dnr_region','fsh_office',
                   'outside_mn','delineated','delineatio','delineat_1','delineat_2','approved_b','approval_d',
                   'approval_n','has_flag','publish_da','has_wld_fl','unique_id','created_us','pw_sub_nam',
                   'created_da','last_edite','last_edi_1','ow_use','map_displa','INSIDE_X','INSIDE_Y']

lakes.drop(useless_columns,axis=1,inplace=True)

#drop lake superior
lakes = lakes[lakes['dowlknum']!=16000100]

#only lakes greater than 100000 sqaure meters, about 25 acres
lakes = lakes[lakes['shape_Area']>100000]

#attach water basins
#DNR level 8 the smalles
l8 = gpd.read_file('D/DNR WATERSHED/DNR_Level_8.shp')
l8 = l8[['AREA','MAJOR','MINOR5','CATCH_ID','geometry']]
l8.columns = ['watershed 8 area','watershed major','watershed minor','watershed 8','geometry']




#8847 before
lakes = gpd.sjoin(lakes,l8,how='left',op='intersects')

lakes.reset_index(drop=True,inplace=True)
#9726 after. I think this is because there are some that are in both
#lets check it out
dups = lakes[lakes.duplicated('dowlknum',keep=False)]
overlaps = []
for i in range(len(dups)):
    lake_poly = dups.iloc[i]['geometry']
    l8_index = dups.iloc[i]['index_right']
    watershed_poly = l8.loc[l8_index,'geometry']
    overlaps.append(lake_poly.intersection(watershed_poly).area)
dups['overlap area'] = overlaps
dups.sort_values(['dowlknum','overlap area'],ascending=[True,False],inplace=True)
dups['bad'] = dups.duplicated('dowlknum',keep='first')

lakes = lakes.drop(dups[dups['bad']].index)


lakes.to_file(LAKES_CLEAN_FILEPATH,driver='GeoJSON')
