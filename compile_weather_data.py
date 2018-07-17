import requests
from io import StringIO
import pandas as pd

#first get a list of all minnesota stations
#might do ND,SD, , MT, ON, too later
r = requests.get('https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt')


cs = [(0,12),(12,21),(21,30),(30,37),(37,40),(41,80)]
all_stations = pd.read_fwf(StringIO(r.text),colspecs= cs, header=None, names=['stationId','lat','long','alt','state','name'])


mn_stations = all_stations[all_stations['state']=='MN']
mn_stations.to_csv('D/Weather/mn_station_locations.csv',index=False)

#I also want to get the locations outside Minnesota so we don't have to extrapolate on the edges
mn_region_stations = all_stations[all_stations['state'].isin(['MN','SD','IA','WI','ND','MB','ON'])]
#reduce the number of stations
mn_region_stations = mn_region_stations[mn_region_stations['long'] > -100] #western two thirds of SD ND
mn_region_stations = mn_region_stations[mn_region_stations['lat'] > 42] #top half of iowa
mn_region_stations = mn_region_stations[mn_region_stations['long'] < -86] #pretty much the nose of mn, 2/3 of wisc
mn_region_stations = mn_region_stations[mn_region_stations['lat'] < 52] #Winnipeg and below

mn_region_stations.to_csv('D/Weather/mn_region_station_locations.csv',index=False)


def get_station_data(stationId,min_year = 1990):
    r = requests.get('https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/all/' + stationId + '.dly')
    cs = [(0,11),(11,15),(15,17),(17,21)]
    id_names = ['id', 'year','month','element']
    dv_names = ['value'+str(i) for i in range(1,32)]
    dm_names = ['mflag'+str(i) for i in range(1,32)]
    dq_names = ['qflag'+str(i) for i in range(1,32)]
    ds_names = ['sflag'+str(i) for i in range(1,32)]
    csV = [(21+(i*8),26+(i*8))for i in range(31)]
    csM = [(26 + (i * 8), 27 + (i * 8)) for i in range(31)]
    csQ = [(27 + (i * 8), 28 + (i * 8)) for i in range(31)]
    csS = [(28 + (i * 8), 29 + (i * 8)) for i in range(31)]


    dV = pd.read_fwf(StringIO(r.text), colspecs=cs+ csV, header=None,names=id_names+dv_names)
    dV = dV.melt(id_vars=id_names)
    dV['day'] = dV['variable'].apply(lambda x: int(x[5:]))
    dV.drop('variable', axis=1, inplace=True)

    dM = pd.read_fwf(StringIO(r.text), colspecs=cs+ csM, header=None,names=id_names+dm_names)
    dM = dM.melt(id_vars=id_names)
    dM['day'] = dM['variable'].apply(lambda x: int(x[5:]))
    dM.rename(columns={'value':'Mflag'},inplace=True)
    dM.drop('variable',axis=1,inplace=True)

    dQ = pd.read_fwf(StringIO(r.text), colspecs=cs+ csQ, header=None,names=id_names+dq_names)
    dQ = dQ.melt(id_vars=id_names)
    dQ['day'] = dQ['variable'].apply(lambda x: int(x[5:]))
    dQ.rename(columns={'value':'Qflag'},inplace=True)
    dQ.drop('variable',axis=1,inplace=True)

    dS = pd.read_fwf(StringIO(r.text), colspecs=cs+ csS, header=None,names=id_names+ds_names)
    dS = dS.melt(id_vars=id_names)
    dS['day'] = dS['variable'].apply(lambda x: int(x[5:]))
    dS.rename(columns={'value':'Sflag'},inplace=True)
    dS.drop('variable',axis=1,inplace=True)

    id_names.append('day')
    data = dV.merge(dM,on=id_names).merge(dQ,on=id_names).merge(dS,on=id_names)
    data = data[data['year']>= min_year]

    data = data.sort_values(['element', 'year', 'month', 'day']).reset_index(drop=True)
    return data

#we want to see which stations have regular coverage. I don't want to included random stations that just have a periodic
# data collection
new_cols = []
es = []
for stationId in mn_region_stations.stationId:
    data = get_station_data(stationId)

    e = data[data['year']>=1980]['element'].value_counts()
    for ei in e.index:
        if ei not in new_cols:
            new_cols.append(ei)
    e.name = stationId
    es.append(e)

df = pd.DataFrame(columns = new_cols)
for e in es:
    df = df.append(e)


df['all'] = df.sum(1)
df.sort_values('all',ascending=False,inplace=True)

#this table shows how many observations of each variable each sample has
df.to_csv('D/Weather/MN region weather sample coverage.csv')

#I want to now pull all the data from the locations that have consistent data
df = pd.read_csv('D/Weather/MN region weather sample coverage.csv', index_col=0)
df.reset_index(inplace=True)
good_precip_locs = df[df['PRCP'] > 8000]['index'] #8000 is a arbitrary number i selected for the cutoff of the top tier
precip_table = [get_station_data(id) for id in good_precip_locs]
precipitation = pd.concat(precip_table)
precipitation = precipitation[precipitation['element']=='PRCP']
precipitation.to_csv('D/Weather/precipitation.csv')

good_temp_locs = df[df['TMAX'] > 8000]['index']
temp_table = [get_station_data(id) for id in good_temp_locs]
temp = pd.concat(temp_table)
temp = temp[temp['element'].isin(['TMAX','TMIN'])]
temp.to_csv('D/Weather/temperature.csv')

good_wind_locs = df[df['AWND'] > 5000]['index']
wind_table = [get_station_data(id) for id in good_wind_locs]
wind = pd.concat(temp_table)
wind = wind[wind['element']=='AWND']
wind.to_csv('D/Weather/wind.csv')