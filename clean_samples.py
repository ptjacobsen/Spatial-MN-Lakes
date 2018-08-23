import pandas as pd
import os
from datetime import date

files = os.listdir('D/Water Samples/County')
files.remove('.directory')

list_of_dataframes = [pd.read_csv('D/Water Samples/County/'+file, dtype={'comments': str, 'statisticType': str, 'result': str}) for file in files]
data= pd.concat(list_of_dataframes)
data.drop_duplicates(inplace=True)

useless_columns = ['analysisDate', #not consistent. sample date is the important one

                   'comments', # Minimal usage. Applicable in rare cases, but not time efficient to sort through
                   'county', # doesn't matter. I have them geocoded throught station Id
                   'gtlt', # not useful. mostly used on orthophosphate, DO, secchi (when secchi really high)
                   'resultUnit', # consistent in 3 main parameters, but not for all tests
                   'sampleTime', # not used consistently. not really a use anyway
                   'sampleDepthUnit', # nearly all m, a couple mm but it think theyre typos
                   'stationName', # all i want are Ids
                   'sampleLowerDepth', # rarely used
                   'labNameCode', 'labCompanyName', 'collectingOrg', 'sampleType', 'sampleFractionType',
                   'statisticType','testMethodId','testMethodName' # irrelevant in this analysis
                  ]
data.drop(useless_columns,axis=1,inplace=True)


#extract date
def str_to_dt(dstr):
    return date(int(dstr[:4]),int(dstr[5:7]),int(dstr[8:10]))
data['date'] = data['sampleDate'].apply(str_to_dt)
data['year'] = data['date'].apply(lambda x: x.year)
data['month'] = data['date'].apply(lambda x: x.month)
data['day'] = data['date'].apply(lambda x: x.day)


#reduce to only useful tests
my_params = ['Depth, Secchi disk depth','Phosphorus as P','Chlorophyll a, corrected for pheophytin']
data = data[data['parameter'].isin(my_params)]

#more readable parameters
def replace_prm(p):
    if p =='Depth, Secchi disk depth':
        return 'secchi'
    elif p == 'Phosphorus as P':
        return 'phos'
    else:
        return 'chloro'

data['variable'] = data['parameter'].apply(replace_prm)


#Annual test count plot
# dy = data[['year','variable','result']]
# dy = dy.groupby(['year','variable']).count()
# ct_by_year = dy.reset_index().pivot('year','variable','result')
# all_years = [i for i in range(ct_by_year.index.min(),ct_by_year.index.max()+1)]
# ct_by_year = ct_by_year.reindex(all_years)
# ct_by_year = ct_by_year.fillna(0)
# ct_by_year.index.name = 'Year'
# ct_by_year.columns = ['Chlorophyll-a','Phosphorus','Secchi Depth']
# ct_by_year.plot(colormap='Accent',title='Water Sample Tests by Year')
#
# #now by month
# dm = data[['month','variable','result']]
# dm = dm.groupby(['month','variable']).count()
# ct_by_month = dm.reset_index().pivot('month','variable','result')
# ct_by_month = ct_by_month.fillna(0)
# ct_by_month.index.name = 'Month'
# ct_by_month.columns = ['Chlorophyll-a','Phosphorus','Secchi Depth']
# ct_by_month.plot(colormap='Accent',title='Water Sample Tests by Month')


#reduce to 1990+
data = data[data['year']>=1990]
data = data[data['month'].isin([5,6,7,8,9])]

def getsubbasinid(x):
    try:
        return int(x[:10].replace('-', ''))
    except:
        return 0

data['dowlknum'] = data['stationId'].apply(getsubbasinid)

data = data[~(data['dowlknum']==0)] # a few with weird station ids ~500 out of 872k

data['stationId'] = data['stationId'].apply(lambda x: int(x[-3:]))

data['result'] = data['result'].apply(float)

#fix some dowlknums that have a significant amount of tests but dont match up to lake
#many of these are attributed to the main basin when only subbasin exist, or vice versa

replacement_pairs = [(10004800, 10004801),
                     (62006702, 62006700),
                     (62006701, 62006700),
                     (11023200, 11023201),
                     (1020901, 1020900),
                     (82009000, 82009002),
                     (18030800, 18030802),
                     (56037802, 56037800),
                     (27009500, 27009501),
                     (16022800, 16022801),
                     (31062400, 31062401),
                     (86012000, 86012001)
                     ]

removal_lakes = [56037801]

for old, new in replacement_pairs:
    data.loc[data['dowlknum']==old,'dowlknum'] = new

for removal_lake in removal_lakes:
    data = data[data['dowlknum'] !=removal_lake]

data.drop('sampleDate',axis=1,inplace=True)

data.sort_values(['dowlknum','stationId','variable','date'],inplace=True)

data = data[['dowlknum','stationId','parameter','variable','date','year','month','day','result','sampleUpperDepth']]
data.reset_index(drop=True,inplace=True)

data['sampleId'] = range(len(data))

#remove NAs and extreme values
data = data[~data['result'].isna()]

#a few odd negatives
data = data[data['result']>=0]

#seek out the extreme values
# data[data['variable']=='secchi']['result'].plot.hist(30) #this doesn't even look like anything
# data[data['variable']=='secchi']['result'].quantile([.9,.95,.98,.99,.999]) #.999 is still just 11. 11m visibility is pretty wild
# data[data['variable']=='secchi']['result'].sort_values(ascending=False).head(40)
#based on some investigation there are some really unlikely values here. appears some mines can get to 20m
p999 = data[data['variable']=='secchi']['result'].quantile(.999)
data = data[~((data['variable']=='secchi') & (data['result'] > p999))]
data[data['variable']=='secchi']['result'].describe()

# data[data['variable']=='phos']['result'].plot.hist(30) #this doesn't even look like anything
# data[data['variable']=='phos']['result'].describe() #median .038, 75p .09 mean .11
# data[data['variable']=='phos']['result'].quantile([.9,.95,.98,.99,.999,.9999,.99999]) #.999 is 5.9,10.9,49.89
# data[data['variable']=='phos']['result'].sort_values(ascending=False).head(40)
p995 = data[data['variable']=='phos']['result'].quantile(.995)
data = data[~((data['variable']=='phos') & (data['result'] > p995))]
data[data['variable']=='phos']['result'].describe()

# data[data['variable']=='chloro']['result'].plot.hist(30) #this doesn't even look like anything
# data[data['variable']=='chloro']['result'].describe() #median 8, 75p 22 mean 24 (theres a fucking 94k)
# data[data['variable']=='chloro']['result'].quantile([.9,.95,.98,.99,.999,.9999,.99999]) #
# data[data['variable']=='chloro']['result'].sort_values(ascending=False).head(40)
p995 = data[data['variable']=='chloro']['result'].quantile(.995)
data = data[~((data['variable']=='chloro') & (data['result'] > p995))]
data[data['variable']=='chloro']['result'].describe()

data.to_csv('D/Water Samples/Samples Clean.csv',index=False)

data['yday'] = data['date'].apply(lambda x: int(x.strftime('%j')))
data_aggm = data.groupby(['dowlknum','variable']).mean()[['result','yday']]
data_aggc = data.groupby(['dowlknum','variable']).count()[['result']]
data_aggc.columns = ['count']

data_agg = data_aggm.join(data_aggc)
data_agg = data_agg.reset_index().pivot(index='dowlknum',columns='variable',values=['count','result'])
data_agg['total'] = data_agg['count'].sum(axis=1)
data_agg = data_agg[data_agg['total'] >= 5]
data_agg['robust'] =data_agg['count'].apply(lambda x: 1 if all([i >=5 for i in x]) else 0, axis=1)

import numpy as np
data_agg['result'] = data_agg['result'].applymap(lambda x: np.nan if x==0 else x)
data_agg['stsi'] = 60 - 14.41 * np.log(data_agg['result']['secchi'])
data_agg['ctsi'] = 9.81 * np.log(data_agg['result']['chloro']) + 30.6
data_agg['ptsi'] = 14.42 * np.log(data_agg['result']['phos'] * 1000) + 4.15


#No easy way to take an average while dealing with nan
data_agg['tsi'] = np.nan
for i in data_agg.index:
    wt = []
    v = []
    if not np.isnan(data_agg['stsi'][i]):
        wt.append(1)
        v.append(data_agg['stsi'][i])
    if not np.isnan(data_agg['ptsi'][i]):
        wt.append(1)
        v.append(data_agg['ptsi'][i])
    if not np.isnan(data_agg['ctsi'][i]):
        wt.append(2)
        v.append(data_agg['ctsi'][i])
    w_ave = np.average(v,weights=wt)
    data_agg.loc[i, 'tsi'] = w_ave

#simplify the indices
data_agg.reset_index(inplace=True)
data_agg.columns = [' '.join(col).strip() for col in data_agg.columns.values]

data_agg = data_agg[data_agg['tsi']<100] #removes one weird lake where secchi was measured as 1 and 2cm and thats it

data_agg.to_csv('D/Water Samples/by lake.csv',index=False)

from matplotlib import pyplot

pyplot.hist(data_agg['tsi'],bins=range(15,100,5),rwidth=.9)
pyplot.ylabel('Frequency')
pyplot.xlabel('Trophic State Index')
pyplot.title('Distribution of TSI in Minnesota Lakes')
pyplot.show()