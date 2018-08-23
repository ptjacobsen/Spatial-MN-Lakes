#
library(GWmodel)
library(RcppCNPy)
library(rgdal)
library(spdep)
setwd('/home/ptjacobsen/Geocomputation/Dissertation/MN Lakes/')


#load the distance matrices we made in python
dmat <- npyLoad('D/dist matrix.npy') #large matrix. 11m, 3389x3389

sdmat <- npyLoad('D/updownstream dist matrix.npy')

#Load and generate watershed basin matrices
lakes <- readOGR(dsn="D/DNR HYDRO/lakes clean",layer="lakes clean", stringsAsFactors=F)
orig_dmat <- gw.dist(coordinates(lakes))
lakes <- lakes@data
lakes$lakeidx <- 1:nrow(lakes)

#build a binary matrix of major and minor catchments
major <- array(0,dim=dim(dmat)) #blank array matching the others
for (i in unique(lakes$ws.major)) {
  
  major[lakes$ws.major==i,lakes$ws.major==i] <- 1
  
}
diag(major) <- 0

minor <- array(0,dim=dim(dmat))
for (i in unique(lakes$ws.minor)) {
  
  minor[lakes$ws.minor==i,lakes$ws.minor==i] <- 1
  
}
diag(minor) <- 0


data <- read.csv('D/Water Samples/by lake.csv')
#match with lakes to reduce TSI number to just the lakes we have, and to provide a crosswalk to the order of the distance matrices
data <- merge(data,lakes[,c('dowlknum','lakeidx')],by='dowlknum')

build_adjusted_distance_matrix <- function(idx, dmat, sdmat, stream_discount, major, major_discount, minor, minor_discount) {
  
  dims <- c(length(idx),length(idx))
  
  major_adjust <- array(1,dim=dims)
  major_adjust <- major_adjust - (major[idx,idx] * major_discount)
  
  minor_adjust <- array(1,dim=dims)
  minor_adjust <- minor_adjust - (minor[idx,idx] * minor_discount)
  
  stream_adjust <- array(1,dim=dims)
  
  stream_effect <- dmat[idx,idx]/sdmat[idx,idx]
  #in theory the stream distance should be at least as long as the real distance
  #but since i only calculated lake edge to edge distance for lakes with centroid <20km,
  # in rare cases stream distance is greater than actual distance where lakes are very large or non-circular
  #we can cap it at one
  stream_effect[stream_effect > 1] <- 1
  
  stream_effect[is.na(stream_effect)] <- 0
  stream_adjust <- stream_adjust - (stream_effect * stream_discount)
  
  combined_mat <- dmat[idx,idx] * major_adjust * minor_adjust * stream_adjust
  
  # # #now adjust for lake sizes
  # # #make a matrix of relative root lake sizes
  # adj_ls <- sqrt(lake_sizes)
  # rel_size <- matrix(adj_ls,dims[1]) %*% (1/matrix(adj_ls,1))
  # #lake 1 has area 1.5m m^2. lake 2 has area 300k m^2.
  # #so rel size matrix [1,2] is 2.2 implying 1 is larger than 2 and the distance of 2 from 1 should be increase because its influence is relatively small
  # combined_mat <- combined_mat * ((array(1,dim=dims) * (1-lake_size_discount)) + (rel_size * lake_size_discount))

  diag(combined_mat) <- 0
  
  return(combined_mat)
}

row_normalize <- function(dmat) {
  rn_mat <- array(dim=dim(dmat))
  for (i in 1:dim(dmat)[1]) {
    rn_mat[i,] <- dmat[i,] / sum(dmat[i,],na.rm = T)
  }
  return(rn_mat)
}

mymat2lw <- function(dmat) {

  #make a fake lw nb object
  nblw = list()
  for (i in 1:dim(dmat)[1]) {
    
    nblw$neighbours[[i]] <- which(dmat[i,]!=0)
    nblw$weights[[i]] <- dmat[i, which(dmat[i,]!=0) ]
    
  }
  nblw$style='W' 
  class(nblw) <- 'listw'
  
  class(nblw$neighbours) <- 'nb'
  return(nblw)
}

moran_i_wrapper <- function(results,ajdmat,bw,kernel='gaussian',adaptive=F) {
  
  ajdmat.w <- t(gw.weight(t(ajdmat),bw,kernel,adaptive)) #this function actually works by column when there is adaptive kernel, not row. so transpose dmat
  #ajdmat.w <- gw.weight(ajdmat,bw,kernel,adaptive)
  diag(ajdmat.w)<-0
  rn_dmat <- row_normalize(ajdmat.w)
  
  nblw <- mymat2lw(rn_dmat)

  res <- moran(results, nblw, dim(ajdmat)[1], sum(rn_dmat))
  I <- res$I
  
  return(I)
  
}

moran_i_test_wrapper <- function(results,ajdmat,bw,kernel='gaussian',adaptive=F) {
  
  ajdmat.w <- t(gw.weight(t(ajdmat),bw,kernel,adaptive)) #this function actually works by column when there is adaptive kernel, not row. so transpose dmat
  #ajdmat.w <- gw.weight(ajdmat,bw,kernel,adaptive)
  diag(ajdmat.w)<-0
  rn_dmat <- row_normalize(ajdmat.w)
  
  nblw <- mymat2lw(rn_dmat)
  
  mt <- moran.test(results,nblw)
  return(mt)
  
}

#unadjusted
moran_i_wrapper(data$tsi,orig_dmat[data$lakeidx,data$lakeidx],10,'bisquare',adaptive = T) #centroid to centroid
moran_i_wrapper(data$tsi,dmat[data$lakeidx,data$lakeidx],10,'bisquare',adaptive = T) #edge to edge

stream_ws <- seq(0,.9,.1)
major_ws <- seq(0,0,.1)
minor_ws <- seq(0,.9,.1)

outgrid<- expand.grid(stream_ws,major_ws,minor_ws)
names(outgrid) <- c('sdist','major','minor')

outgrid$moran_i_tsi <- NaN

for (i in 1:nrow(outgrid)) {
  print(i/nrow(outgrid) * 100)
  adj_dmat <- build_adjusted_distance_matrix(data$lakeidx,
                                             orig_dmat,
                                             sdmat,outgrid[i,'sdist'],
                                             major,outgrid[i,'major'],
                                             minor,outgrid[i,'minor'])
  
  outgrid[i,'moran_i_tsi'] <- moran_i_wrapper(data$tsi,adj_dmat,10,'bisquare',adaptive = T)
  
}


#repeat with only robust lakes, by test
data_r <- data[data$robust==1,]
stream_ws <- seq(0,.9,.1)
major_ws <- seq(0,.9,.1)
minor_ws <- seq(0,.9,.1)

outgrid_r<- expand.grid(stream_ws,major_ws,minor_ws)
names(outgrid_r) <- c('sdist','major','minor')


outgrid_r$moran_i_phos <- NaN
outgrid_r$moran_i_chloro <- NaN
outgrid_r$moran_i_sech <- NaN

for (i in 1:nrow(outgrid_r)) {
  adj_dmat <- build_adjusted_distance_matrix(data_r$lakeidx,
                                             orig_dmat,
                                             sdmat,outgrid_r[i,'sdist'],
                                             major,outgrid_r[i,'major'],
                                             minor,outgrid_r[i,'minor'])
  
  outgrid_r[i,'moran_i_chloro'] <- moran_i_wrapper(data_r$result.chloro,adj_dmat,10,'bisquare',adaptive = T)
  outgrid_r[i,'moran_i_phos'] <- moran_i_wrapper(data_r$result.phos,adj_dmat,10,'bisquare',adaptive = T)
  outgrid_r[i,'moran_i_sech'] <- moran_i_wrapper(data_r$result.secchi,adj_dmat,10,'bisquare',adaptive = T)
  
}


library(lattice)

ma0 <- matrix(rep(0,100),ncol=10)

rownames(ma0) <- seq(0,.9,.1)
colnames(ma0) <- seq(0,.9,.1)

for (i in seq(0,.9,.1)) {
  for (j in seq(0,.9,.1)) {
    ma0[i*10 +1,j*10+1] <- outgrid[(outgrid$sdist==i & outgrid$minor==j & outgrid$major == 0),'moran_i_tsi']

  }
}
levelplot(ma0,col.regions=heat.colors(100),xlab='Stream Distance Parameter',ylab='Minor Watershed Parameter',main="Moran's I with Major Watershed Parameter at 0")
  
  
  
adj_dmat <- build_adjusted_distance_matrix(lakes$lakeidx,
                                           orig_dmat,
                                           sdmat,.5,
                                           major,.00,
                                           minor,.1)

colnames(adj_dmat) <- lakes$dowlknum
rownames(adj_dmat) <- lakes$dowlknum

saveRDS(adj_dmat,'D/adjusted_dmat.rds')





