setwd('/home/ptjacobsen/Geocomputation/Dissertation/MN Lakes/')

library(GWmodel)
library(sp)
library(rgdal)
source('P/gwmodel_plotting.R')

read_lc_file <- function(ring_size,year) {
  lc <- read.csv(paste0('D/Land Cover/Land Cover Surrounding Lakes ',ring_size,'ring ',year,'.csv'))
  lc$wet <- (lc$OW.share + lc$WW.share + lc$EHW.share)
  lc$developed <-  (lc$D.OS.share + lc$D.LI.share + lc$D.MI.share + lc$D.HI.share)
  lc$natural <- (lc$DF.share + lc$EF.share + lc$MF.share + lc$S.share + lc$GL.share)
  lc$ag <- (lc$PH.share + lc$CC.share)
  return(lc)
}

read_lc_data <- function(ring_size) {
  
  lc2001 <- read_lc_file(ring_size,2001)
  lc2006 <- read_lc_file(ring_size,2006)
  lc2011 <- read_lc_file(ring_size,2011)
  
  lc <- data.frame(dowlknum = lc2001$dowlknum)
  for (v in names(lc2001)) {
    if (v=='dowlknum') {
      next
    }
    
    lc[,v] <- (lc2001[,v] + lc2006[,v] + lc2011[,v]) / 3
   
  }
  
  return(lc)

}


data <- read.csv('D/Water Samples/by lake.csv')

data<- merge(data,read_lc_data('1k'),by='dowlknum')

lakes <- readOGR(dsn="D/DNR HYDRO/lakes clean",layer="lakes clean", stringsAsFactors=F)
lakes@data$lakeidx <- 1:nrow(lakes)
lakes_subset <- cbind(coordinates(lakes),lakes@data[,c('dowlknum','shape_Area','lakeidx')])
names(lakes_subset)[1:2] <- c('X','Y')
data <- merge(data,lakes_subset,by='dowlknum')

data <- merge(data,read.csv('D/Land Cover/surrounding building count.csv'),by='dowlknum')

#significant drop in observations here. probably selection bias
data <- merge(data,read.csv('D/Bathymetry/Lake Depths.csv'),by='dowlknum')

adj_dmat_all <- readRDS('D/adjusted_dmat.rds')
lakes_used <- as.character(unique(data$dowlknum))
adj_dmat <- adj_dmat_all[lakes_used,lakes_used]

data_spdf0 <- SpatialPointsDataFrame(data[,c('X','Y')],data,proj4string = lakes@proj4string)

#convert dist to km. There somes to be some sort of interger overflow in gwmodel when working with UTM coordinates. No errors when using Km
adj_dmat <- adj_dmat / 1000
data_spdf <- SpatialPointsDataFrame(data[,c('X','Y')]/1000,data,proj4string = lakes@proj4string)


vrn_mn_carto <- gen_mn_cartogram(data_spdf0)


fm <- tsi ~  wet + developed + natural + ag + building.per.km.shore + log(shape_Area) + shallow.share + abs_depth

lm1 <- lm(fm,data_spdf)

myplot(lm1$residuals,vrn_mn_carto)

bw <- bw.gwr(fm,data_spdf,kernel='bisquare',dMat = adj_dmat,adaptive = T) #got the same doing AIC approach
bw_nodist <- bw.gwr(fm,data_spdf,kernel='bisquare',adaptive = T)


gwm1 <- gwr.basic(fm,data_spdf,bw=bw,kernel='bisquare',dMat=adj_dmat,adaptive = T)
gwm1_nodist <- gwr.basic(fm,data_spdf,bw=bw_nodist,kernel='bisquare',adaptive=T)

####wow look at how much better my distances are

myplot(gwm1$SDF@data$developed,vrn_mn_carto)

#show extreme cn numbers
coldiag <- gwr.collin.diagno(fm,data_spdf,bw=bw,kernel='bisquare',dMat=adj_dmat,adaptive=T)
myplot(coldiag$local_CN,vrn_mn_carto)
#show VIF summaries
colnames(coldiag$VIF) <- attr(terms(fm),'term.labels')
summary(coldiag$VIF)
#make PCA indexes

pca <- princomp(data_spdf@data[,14:28],cor=T)
pca$sdev^2 
vari_share <- pca$sdev^2/sum(pca$sdev^2)
sum(vari_share[1:4])

pca$loadings

data_spdf@data$pca_forest <- pca$scores[,1]
data_spdf@data$pca_ag <- pca$scores[,2]
data_spdf@data$pca_wood_crop <- pca$scores[,3]
data_spdf@data$pca_water_ef <- pca$scores[,4]
#data_spdf@data$pca_barren <- pca$scores[,5]
#new gwm.

#reasonable parameters, only slight decrease in r2
fm2 <- tsi ~  pca_forest + pca_ag + pca_wood_crop + pca_water_ef +  building.per.km.shore + log(shape_Area) + shallow.share + abs_depth

bw2 <- bw.gwr(fm2,data_spdf,kernel='bisquare',dMat = adj_dmat,adaptive = T)
gwm2 <- gwr.basic(fm2,data_spdf,bw=bw2,kernel='bisquare',dMat=adj_dmat,adaptive = T)



coldiag2 <- gwr.collin.diagno(fm2,data_spdf,bw=bw,kernel='bisquare',dMat=adj_dmat,adaptive=T)
#CN still kinda high
myplot(coldiag2$local_CN,vrn_mn_carto) #reigned in but generally high for us still

#check VIF. whats the problem now?
colnames(coldiag2$VIF) <- attr(terms(fm2),'term.labels')
summary(coldiag2$VIF)
#top two pca are high
#not enough local variation in land cover to effectively model
myplot(coldiag2$VIF[,'pca_forest'],vrn_mn_carto)

#such limited local variability
myplot(gwm2$SDF@data$Stud_residual,vrn_mn_carto)
myplot(gwm2$SDF@data$pca_ag,vrn_mn_carto)
myplot(gwm2$SDF@data$pca_ag,vrn_mn_carto)


#apply ridge?
bw3 <- bw.gwr.lcr(fm2,data_spdf,kernel='bisquare', adaptive=T, lambda.adjust=T,dMat=adj_dmat,cn.thresh=30)
gwm3 <- gwr.lcr(fm2,data_spdf, bw=bw3, kernel="bisquare",adaptive=T, lambda.adjust = T, dMat=adj_dmat,cn.thresh = 30)
#thats the best we can do

#now interpret.

#houses don't make sense but track something else

























