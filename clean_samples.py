import pandas as pd
import os
from datetime import date

files = os.listdir('D/Water Samples/County')
files.remove('.directory')

list_of_dataframes = [pd.read_csv('D/Water Samples/County/'+file, dtype={'comments': str, 'statisticType': str, 'result': str}) for file in files]
data= pd.concat(list_of_dataframes)
data.drop_duplicates(inplace=True)

useless_columns = ['analysisDate', #not consistent. sample date is the important one
                   'collectingOrg', # I dont care
                   'comments', # I don't usually care. Not good use of time to sort through them
                   'county', # doesn't matter. I have them geocoded throught station Id
                   'gtlt', # not useful. mostly used on orthophosphate, DO, secchi (when secchi really high)
                   'resultUnit', # consistent in my parameters of interest but not consistent for all, SO BE CAREFUL
                   'sampleTime', # not used consistently. not really a use anyway
                   'labNameCode', 'labCompanyName', # i dont care
                   'sampleDepthUnit', # nearly all m, a couple mm but it think theyre typos
                   'sampleLowerDepth', # rarely used
                   'sampleType', # not usefull
                   'sampleFractionType', #usually not helpful, i think. (almost) consistent by parameter
                   'stationName', # all i want are Ids
                   'statisticType','testMethodId','testMethodName' # boooooring
                  ]
data.drop(useless_columns,axis=1,inplace=True)


my_params = ['Depth, Secchi disk depth','Phosphorus as P','Chlorophyll a, corrected for pheophytin']
##add temp and conduct??

#consider in the future keeping water temp and conductivity
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



def str_to_dt(dstr):
    return date(int(dstr[:4]),int(dstr[5:7]),int(dstr[8:10]))
data['date'] = data['sampleDate'].apply(str_to_dt)
data['year'] = data['date'].apply(lambda x: x.year)
data['month'] = data['date'].apply(lambda x: x.month)
data['day'] = data['date'].apply(lambda x: x.day)

data = data[data['year']>=1990]

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

data.to_csv('D/Water Samples/Samples Clean.csv',index=False)

