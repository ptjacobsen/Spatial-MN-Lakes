import geopandas as gpd
import rasterio
from rasterio import features
import numpy as np
import itertools
from scipy.sparse import bsr_matrix

LAKES_FILEPATH = 'D/DNR HYDRO/lakes clean.geojson'
LANDCOVER_FILEPATHS = ['D/Land Cover/NLCD 2001 - Land Cover1.tif',
                       'D/Land Cover/NLCD 2006 - Land Cover1.tif',
                       'D/Land Cover/NLCD 2011 - Land Cover1.tif'
                       ]

OUTPUT_FILEPATH = 'D/Land Cover/Land Cover Surrounding Lakes.csv'

#####PROCESS#####
#1. Import the cleaned lake geometries
#2. Generate Rings of difference widths around each lake
#3. Rasterize rings, calculate share of each land cover type within each ring
#4. Save to file
#################

#1. Import lakes and do the same cleaning that we did in network building
lakes = gpd.read_file(LAKES_FILEPATH)

##2. Generate rings of different sizes around lakes

# buffer lakes 100 meter, 500, 1km, 10km
lakes['geo b100'] = lakes['geometry'].buffer(100)
lakes['geo b500'] = lakes['geometry'].buffer(500)
lakes['geo b1k'] = lakes['geometry'].buffer(1000)
lakes['geo b10k'] = lakes['geometry'].buffer(10000)

lakes['geo 100ring'] = ''
lakes['geo 500ring'] = ''
lakes['geo 1kring'] = ''
lakes['geo 10kring'] = ''

counter = 0
tenpct = int(len(lakes)/10)

# exclude actual lake so you only have the ring
for i in lakes.index:

    counter += 1
    if counter % tenpct == 0:
        print(str(int(counter / tenpct * 10)) + '%')

    lakes['geo 100ring'][i] = lakes.loc[i, 'geo b100'].difference(lakes.loc[i, 'geometry'])
    lakes['geo 500ring'][i] = lakes.loc[i, 'geo b500'].difference(lakes.loc[i, 'geometry'])
    lakes['geo 1kring'][i] = lakes.loc[i, 'geo b1k'].difference(lakes.loc[i, 'geometry'])
    lakes['geo 10kring'][i] = lakes.loc[i, 'geo b10k'].difference(lakes.loc[i, 'geometry'])


lakes.drop(['geo b100','geo b500','geo b1k','geo b10k'],axis=1,inplace=True)
#lakes.to_pickle('D/lakerings.pickle')


##3. Rasterize Rings and compare to landcover

#codes from  ftp://ftp.gisdata.mn.gov/pub/gdrs/data/pub/us_mn_state_dnr/biota_landcover_nlcd_mn_2011/metadata/metadata.html
land_cover_dict = {'OW':11,
                   'D OS':21,
                   'D LI':22,
                   'D MI': 23,
                   'D HI':24,
                   'BL':31,
                   'DF':41,
                   'EF':42,
                   'MF':43,
                   'S':52,
                   'GL':71,
                   'PH':81,
                   'CC':82,
                   'WW':90,
                   'EHW':95}

#some deep rasterio imports to enable the use of the hidden _rasterize function
from rasterio._features import _rasterize
from rasterio.transform import guard_transform
all_touched = False  # raster conversion method. True=polygon covers cell, False=cell center in poly
from rasterio.enums import MergeAlg

#get the shape and resolution and stuff of the image we are comparing to
for LANDCOVER_FILEPATH in LANDCOVER_FILEPATHS:

    year = LANDCOVER_FILEPATH[18:22]
    rst = rasterio.open(LANDCOVER_FILEPATH)
    lc_arr = rst.read(1)
    #lc_arr = lc_arr[:7390,:6579]

    meta = rst.meta.copy()
    shape = (meta['height'],meta['width'])
    raster = np.empty(shape,np.uint8)

    transform = guard_transform(meta['transform'])

    for ring_size in ['10kring','100ring','500ring','1kring']:

        print(year,ring_size) #for progress tracking

        gis = lakes['geo '+ ring_size].apply(lambda x: getattr(x, '__geo_interface__')) #takes 3 seconds

        new_col_names = [lc_type_str + ' ' + ring_size + ' share ' + year
                         for lc_type_str in land_cover_dict]

        lakes_results = lakes[['dowlknum']].copy()

        for new_col_names in new_col_names:
            lakes_results[new_col_names] = np.nan


        for i in lakes.index:
            if i % 1000 == 0:
                print(i)

            #using hidden rasterize function to skip validation an speed up the function up to 40%
            #modifies raster matrix, returns nothing
            raster.fill(0)
            _rasterize([(gis[i],1)], raster,
                                  transform,
                                  all_touched,
                                  MergeAlg.replace)

            #extract the section of the land cover raster where this lake ring exists

            ring_lc = lc_arr[raster==1]

            #extract the counts of each land cover type in the overlap
            ring_lc_dict = dict(zip(*np.unique(ring_lc, return_counts=True)))
            cell_ct = len(ring_lc)
            for lc_type_str, lc_type in land_cover_dict.items():
                lakes_results.loc[i,lc_type_str + ' ' + ring_size + ' share ' + year] = round(ring_lc_dict.get(lc_type, 0) / cell_ct,4)

        print('vals inserted')
        lakes_results.to_csv('D/Land Cover/Land Cover Surrounding Lakes ' + ring_size + ' ' + year +'.csv', index=False)
        print('saved')
