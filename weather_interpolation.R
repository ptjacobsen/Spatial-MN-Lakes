# Title     : TODO
# Objective : TODO
# Created by: ptjacobsen
# Created on: 02/07/18
library(sp)
library(rgdal)
library(RColorBrewer)
library(akima)
library(raster)
library(classInt)

setwd('/home/ptjacobsen/Geocomputation/Dissertation/MN Lakes/')

myplot <- function(stations,var,ras,state=FALSE) {
  plotvar <- stations@data[,var]
  Colours <- 8
  Palette <- brewer.pal(Colours,"PuBu")
  Class <- classIntervals(plotvar, Colours, style="quantile")
  Colcode <- findColours(Class, Palette)
  plot(ras)

  plot(stations,pch=16,cex=1.1,col=Colcode,add=T)
  if (state) {
    plot(mn,col='lightgrey',border='darkgrey',add=T)
  }
  legend("topleft",
         legend=names(attr(Colcode, "table")),
         fill=attr(Colcode, "palette"),
         cex=0.6, bty="n")

}

mn_stations <- read.csv('D/Weather/mn_station_locations.csv')
mn_region_stations <- read.csv('D/Weather/mn_region_station_locations.csv')
mn <- readOGR(dsn="D/Other/shp_bdry_counties_in_minnesota/",layer="mn_county_boundaries_500",
              stringsAsFactors=F)

##build a grid of 5km squares that completely cover mn
#round up and down to 5km from bounds of MN
mnbbox <- bbox(mn)
start_x <- mnbbox['x','min'] - (mnbbox['x','min'] %% 1000)
end_x <- mnbbox['x','max'] + 5000
raster_xo <- seq(start_x,end_x,5000)
start_y <- mnbbox['y','min'] - (mnbbox['y','min'] %% 1000)
end_y <- mnbbox['y','max'] + 5000
raster_yo <- seq(start_y,end_y,5000)
cell_ct_x <- length(raster_xo)
cell_ct_y <- length(raster_yo)

match_lake_centroid <- function(x,y,bicub) { 
  return(bicub$z[which.min(abs(bicub$y - y)),which.min(abs(bicub$x - x))])
}


precip <- read.csv('D/Weather/precipitation.csv')

precip$date <- as.Date(paste(precip$year,precip$month,precip$day,sep='-'))
precip <- precip[!is.na(precip$date),] #since all the Feb 30 etc were included
precip <- precip[(precip$date >= as.Date('1990-1-1')),] 
precip <- precip[(precip$value != -9999),] 
precip <- precip[(precip$id !='CA00503B1ER'),]
precip <- precip[(precip$Qflag==''),]


precip <- merge(precip,mn_region_stations[,c('stationId','lat','long')],by.x='id',by.y='stationId')
p4s <- '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
spatpoints <- SpatialPoints(precip[,c('long','lat')],proj4string = CRS(p4s))
precip <- SpatialPointsDataFrame(spatpoints,precip)
precip <- spTransform(precip,mn@proj4string)

#as.Date('2017-12-31') - as.Date('1990-1-1') = 10226
rain_day_ct <- 10226
#rain_array = array(dim=c(10226,100,111))
rain_array = array(dim=c(cell_ct_x,cell_ct_y,rain_day_ct))
d <- as.Date('1990-1-2')
counter <- 1 
while (d <= as.Date('2017-12-31')) {
  print(d)
  my_date_rain <- precip[precip$date == d,]
  x <- coordinates(my_date_rain)[,1]
  y <- coordinates(my_date_rain)[,2]
  
  bicub <- interp(x, y, my_date_rain$value,
                  xo=raster_xo,
                  yo=raster_yo,
                  linear = FALSE
  )
  
  rain_array[,,counter] <- bicub$z
  
  counter <- counter + 1
  d <- d + 1
  
}

week_rain_array <- array(dim=c(208,211,rain_day_ct))
for (i in 7:dim(rain_array)[2]) {
  week_rain_array[,,i] <- rowSums(rain_array[,,(i-6):i])
}


#now lets get temps

temperature <- read.csv('D/Weather/temperature.csv')

temperature <- temperature[(temperature$value != -9999),] #remove missing

temperature <- temperature[(temperature$id !='CA00503B1ER'),] #the problem station
temperature$date <- as.Date(paste(temperature$year,temperature$month,temperature$day,sep='-'))
temperature <- temperature[!is.na(temperature$date),] 
temperature$value <- temperature$value/ 10
temperature <- temperature[(temperature$Qflag==''),]

#get mean temp for the day
tmin <- temperature[temperature$element=='TMIN',c('id','date','value')]
names(tmin) <- c('id','date','tmin')
tmax <- temperature[temperature$element=='TMAX',c('id','date','value')]
names(tmax) <- c('id','date','tmax')
temperature <- merge(tmin,tmax,on=c('id','date'))

temperature$tmid <- (temperature$tmax + temperature$tmin)/2

temperature <- merge(temperature,mn_region_stations[,c('stationId','lat','long')],by.x='id',by.y='stationId')
p4s <- '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
spatpoints <- SpatialPoints(temperature[,c('long','lat')],proj4string = CRS(p4s))
temperature <- SpatialPointsDataFrame(spatpoints,temperature)
temperature <- spTransform(temperature,mn@proj4string)

d<- as.Date('1991-4-30')
my_date_temp <- temperature[temperature$date == d,]
x <- coordinates(my_date_temp)[,1]
y <- coordinates(my_date_temp)[,2]

bicub <- interp(x, y, my_date_temp$tmid,
                xo=raster_xo,
                yo=raster_yo,
                linear = FALSE
)

myplot(my_date_temp,'tmid',raster(bicub))

library(fields)
tps_model <- Tps(coordinates(my_date_temp), my_date_temp$tmid)
empty_ras <- raster(ncol=cell_ct_x,nrow=cell_ct_y, xmn=start_x,xmx,end_x,)


#idfk... we'll do a thin plate spline

library(fields)

tps_model <- Tps(coordinates(my_bday_rain), my_bday_rain$value)
empty_r <- raster(mn,res=1000)
tps <- interpolate(empty_r,tps_model)
#eww. way too smoothed out


x <- coordinates(my_bday_rain1)[,1]
y <- coordinates(my_bday_rain1)[,2]

bilin <- interp(x, y, my_bday_rain$value,
                xo=seq(min(x),max(x),length=1000),yo=seq(min(y), max(y), length = 1000)
                )

bicub <- interp(x, y, my_bday_rain$value,
                xo=seq(min(x),max(x),length=100),yo=seq(min(y), max(y), length = 111),
                linear = FALSE
                )
#no negative rains
bicub$z[bicub$z < 0] <- 0


ras <- raster(bicub) #i like this

#krig for temp because there can be some measurement error in temps


match_lake_centroid <- function(x,y,bicub) { 
  return(bicub$z[which.min(abs(bicub$y - y)),which.min(abs(bicub$x - x))])
}


#wind?
#lets try it quick
wind <- read.csv('D/Weather/wind.csv')
stations <- read.csv('D/Weather/mn_station_locations.csv')
mn <- readOGR(dsn="D/Other/shp_bdry_counties_in_minnesota/",layer="mn_county_boundaries_500",
              stringsAsFactors=F)
#check flags for anything weird. i already did

wind$date <- as.Date(paste(wind$year,wind$month,wind$day,sep='-'))
wind <- wind[!is.na(wind$date),] #since all the Feb 30 etc were included
wind <- wind[(wind$date > as.Date('1990-1-1')),] 
wind <- merge(wind,stations[,c('stationId','lat','long')],by.x='id',by.y='stationId')
p4s <- '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
spatpoints <- SpatialPoints(wind[,c('long','lat')],proj4string = CRS(p4s))
wind <- SpatialPointsDataFrame(spatpoints,wind)
wind <- spTransform(wind,mn@proj4string)

my_bday_wind <- wind[wind$date == as.Date('1991-4-30'),] #only 5 points for this date at the 5 major airpors
my_bday_wind2 <- wind[wind$date == as.Date('2003-4-30'),] 

plotvar <- my_bday_wind$value
Colours <- 8
Palette <- brewer.pal(Colours,"PuBu")
Class <- classIntervals(plotvar, Colours, style="quantile")
Colcode <- findColours(Class, Palette)
plot(mn,col='lightgrey',border='darkgrey')
plot(my_bday_wind,pch=16,cex=1.1,col=Colcode,add=T)
legend("topleft",
       legend=names(attr(Colcode, "table")),
       fill=attr(Colcode, "palette"),
       cex=0.6, bty="n")

x <- coordinates(my_bday_wind)[,1]
y <- coordinates(my_bday_wind)[,2]

bicub2 <- interp(x, y, my_bday_wind$value,
                xo=seq(min(x),max(x),length=100),yo=seq(min(y), max(y), length = 100),
                linear = FALSE
)

ras2 <- raster(bicub2)  #this didnot work. Need more points.
#maybe idw is best then because that can work on any number of points
