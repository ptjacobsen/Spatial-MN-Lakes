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
#1. Import and clean the lakes from DNR Hydrology shapefile
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

#we use rasterize to convert the shapes into numpy arrays
#since images cant handle more than 256 values per color band
#we have to split the lakes into sets of 255 (256 - 1) because one color needs to be not-lake

#import pandas as pd

#lakes = pd.read_pickle('D/lakerings.pickle')
#pairs = list(itertools.product(range(256),range(1,256)))[:len(lakes)] #first part is arbitrarily 256. could be more, depending on max number of bands in image

#lakes['band'] = [x[0] for x in pairs]
#lakes['hue'] = [x[1] for x in pairs]

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

#
# new_col_names = [lc_type_str + ' ' + ring_size + ' share ' + year
#                   for lc_type_str in land_cover_dict
#                     for ring_size in ['100ring','500ring','1kring','10kring']]
#initialize empty columns of share because we will need to insert them one by one
# for new_col_names in new_col_names:
#     lakes[new_col_names] = np.nan

#182000,5475010 is the top right corner. each cell is 30m
#lets try on 1/9 of the data

#raster is 22167,19733

#top right corner 1/9th is 5475010 - (22167/3 * 30) = 5253340
#                          182000 + (19733 /3 * 30) = 379330

from rasterio._features import _rasterize
from rasterio.transform import guard_transform
all_touched = False  # raster conversion method. True=polygon covers cell, False=cell center in poly
from rasterio.enums import MergeAlg
from time import time

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
        t = time()

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
            #modifies out matrix, returns nothing
            raster.fill(0)
            _rasterize([(gis[i],1)], raster,
                                  transform,
                                  all_touched,
                                  MergeAlg.replace)

            ring_lc = lc_arr[raster==1]


            ring_lc_dict = dict(zip(*np.unique(ring_lc, return_counts=True)))
            cell_ct = len(ring_lc)
            for lc_type_str, lc_type in land_cover_dict.items():
                lakes_results.loc[i,lc_type_str + ' ' + ring_size + ' share ' + year] = round(ring_lc_dict.get(lc_type, 0) / cell_ct,4)
        #
        # shapes = ((geom, value) for geom, value in zip(lakes['geo '+ring_size], range(1,len(lakes)+1)))
        # #rastered = bsr_matrix(features.rasterize(shapes=shapes, fill=0, out_shape=shape, transform=meta['affine']),dtype=np.int16)
        # rastered = features.rasterize(shapes=shapes, fill=0, out_shape=shape, transform=meta['affine'],dtype=np.int16)
        #
        # #rastered is a numpy array with the shape of the landcover files.
        # #nearly all of it 0 but will have 'hue' where the lake rings are, where hue is a sub id 1-255
        # #immediately convert to scipy sparse matrix to cut down on memory and increase speed
        # print('rastered')
        # print(time() - t)
        # t1 = time()
        # #big ugly function, but really increases speed over old method
        # #ring_lcs = [np.unique(lc_arr[(rastered == i).nonzero()],return_counts=True) for i in range(1,len(lakes)+1)]
        # ring_lcs = [np.unique(lc_arr[rastered==i],return_counts=True) for i in range(1,len(lakes)+1)]
        #
        # print('vals extracted')
        # print(time() - t1)
        # t1 = time()
        #
        # ring_lcs = pd.Series(ring_lcs).apply(lambda x: dict(zip(*x)))#takes no time
        # cell_cts = ring_lcs.apply(lambda x: np.sum(list(x.values())))
        #
        # for lc_type_str, lc_type in land_cover_dict.items():
        #     lakes_results[lc_type_str + ' ' + ring_size + ' share ' + year] = ring_lcs.apply(lambda x: x.get(lc_type,0)) / cell_cts
        #
        #
        # # i = 0
        # # for gdf_i in lakes.index:
        # #     cell_ct = np.sum(ring_lcs[i][1])
        #     ring_lc = dict(zip(*ring_lcs[i]))
        #     for lc_type_str,lc_type in land_cover_dict.items():
        #         try:
        #             lakes_results[gdf_i, lc_type_str + ' ' + ring_size + ' share ' + year] = ring_lc[lc_type] / cell_ct
        #         except KeyError:
        #             lakes_results[gdf_i, lc_type_str + ' ' + ring_size + ' share ' + year] = 0
        #     i+=1
        # print(time()-t1)
        print('vals inserted')
        lakes_results.to_csv('D/Land Cover/Land Cover Surrounding Lakes ' + ring_size + ' ' + year +'.csv', index=False)
        print('saved')
        print(time()-t)
#
# from time import time
#
# t = time()
# # get the shape and resolution and stuff of the image we are comparing to
# for LANDCOVER_FILEPATH in LANDCOVER_FILEPATHS:
#     year = LANDCOVER_FILEPATH[18:22]
#     rst = rasterio.open(LANDCOVER_FILEPATH)
#     lc_arr = rst.read(1)
#     # lc_arr = lc_arr[:7390,:6579]
#
#     meta = rst.meta.copy()
#     shape = (meta['height'], meta['width'])
#
#     for ring_size in ['100ring', '500ring', '1kring', '10kring']:
#
#         for band in list(lakes['band'].unique()):
#             print(year, ring_size, band)  # for progress tracking
#
#             lakes_mini = lakes[lakes['band'] == band]
#             shapes = ((geom, value) for geom, value in
#                       zip(lakes_mini['geo ' + ring_size], lakes_mini['hue']))
#             rastered = bsr_matrix(
#                 features.rasterize(shapes=shapes, fill=0, out_shape=shape, transform=meta['affine']),
#                 dtype=np.int32)
#             # rastered is a numpy array with the shape of the landcover files.
#             # nearly all of it 0 but will have 'hue' where the lake rings are, where hue is a sub id 1-255
#             # immediately convert to scipy sparse matrix to cut down on memory and increase speed
#
#             # big ugly function, but really increases speed over old method
#             ring_lcs = [np.unique(lc_arr[(rastered == hue).nonzero()], return_counts=True) for hue in
#                         lakes_mini['hue']]
#
#             i = 0
#             for gdf_i in lakes_mini.index:
#                 cell_ct = np.sum(ring_lcs[i][1])
#                 ring_lc = dict(zip(*ring_lcs[i]))
#                 for lc_type_str, lc_type in land_cover_dict.items():
#                     try:
#                         lakes[gdf_i, lc_type_str + ' ' + ring_size + ' share ' + year] = ring_lc[
#                                                                                              lc_type] / cell_ct
#                     except KeyError:
#                         lakes[gdf_i, lc_type_str + ' ' + ring_size + ' share ' + year] = 0
#                 i += 1

                        # for hue in lakes_mini['hue']:
            #     #find the pandas data frame index value that matches this hue/band for this lake
            #     i = lakes_mini[(lakes_mini['band']==band) & (lakes_mini['hue']==hue)].index[0]
            #
            #     #extract just the area in the land cover raster where this lake ring exists
            #     ring_lc = lc_arr[rastered == hue]
            #     cell_ct = len(ring_lc)
            #
            #     #loop through each land cover type
            #     for lc_type_str,lc_type in land_cover_dict.items():
            #         #count up the cells for each landcover type, divide by total ring cell size
            #         #insert into lakes dataframe
            #         print((ring_lc==lc_type).sum() / cell_ct)
            #         lakes[i,lc_type_str + ' ' + ring_size + ' share ' + year] = (ring_lc==lc_type).sum() / cell_ct


##4. Save to file

lakes[['dowlknum'] + new_col_names].to_csv(OUTPUT_FILEPATH)



#
#
#
# rst_fn = 'D/Land Cover/Lake Rings 1k.tif'
# template_raster_fn = 'D/Land Cover/NLCD 2011 - Land Cover1.tif'
# rst = rasterio.open(template_raster_fn)
# meta = rst.meta.copy()
# meta.update(compress='lzw')
#
# with rasterio.open(rst_fn, 'w', **meta) as out:
#     for band in list(lakes['band'].unique()):
#         lakes_mini = lakes[lakes['band'] == band]
#         out_arr = out.read(int(band))
#
#         # this is where we create a generator of geom, value pairs to use in rasterizing
#         shapes = ((geom,value) for geom, value in zip(lakes['geo 1kring'], range(len(lakes))))
#
#         burned = features.rasterize(shapes=shapes, fill=0, out=out_arr, transform=out.transform)
#         out.write_band(int(band), burned)
#
# #no we have that file. can we link it with the full tif?
# lakerast = rasterio.open(rst_fn)
#
# for band in list(lakes['band'].unique())
#
#
#
#
# #rasterize polygons
#
# def plot_polygon(p):
#     gpd.GeoDataFrame({'geometry':[p]}).plot()
#
# p1 = lakes['geo 1kring'][1000]
#
# from osgeo import gdal, ogr
# import sys
# # this allows GDAL to throw Python Exceptions
# gdal.UseExceptions()
#
# raster_fn = 'D/Land Cover/NLCD 2011 - Land Cover1.tif'
# src_ds = gdal.Open( raster_fn )
#
# srcband = src_ds.GetRasterBand(1)
#
#
# dst_layername = "D/Land Cover/POLYGONIZED_1_2011"
# #drv = ogr.GetDriverByName("ESRI Shapefile")
# drv = ogr.GetDriverByName('GeoJSON')
# dst_ds = drv.CreateDataSource( dst_layername + ".geojson" )
# dst_layer = dst_ds.CreateLayer(dst_layername, srs = None )
#
# gdal.Polygonize(srcband, None, dst_layer, -1, [], callback=None )
#
# ring1k_fn = 'D/Land Cover/Lake Rings 1k.tif'
#
# from osgeo import gdal, ogr
#
# # Define pixel_size and NoData value of new raster
# pixel_size = 30
# NoData_value = -9999
#
# # Filename of input OGR file
# vector_fn = 'test.shp'
#
# # Filename of the raster Tiff that will be created
#
# # Open the data source and read in the extent
# source_ds = ogr.Open(vector_fn)
# source_layer = source_ds.GetLayer()
# x_min, x_max, y_min, y_max = source_layer.GetExtent()
#
# # Create the destination data source
# x_res = int((x_max - x_min) / pixel_size)
# y_res = int((y_max - y_min) / pixel_size)
# target_ds = gdal.GetDriverByName('GTiff').Create(raster_fn, x_res, y_res, 1, gdal.GDT_Byte)
# target_ds.SetGeoTransform((x_min, pixel_size, 0, y_max, 0, -pixel_size))
# band = target_ds.GetRasterBand(1)
# band.SetNoDataValue(NoData_value)
#
# # Rasterize
# gdal.RasterizeLayer(target_ds, [1], source_layer, burn_values=[0])
#
#
#
#
#
#
# # combine rasters?
#
# #aggregate by lake
#
