library(cartogram)
library(stringr)
library(RColorBrewer)
library(classInt)
#Voronoi driven plot
library(spatstat)
library(rgeos)

setwd('/home/ptjacobsen/Geocomputation/Dissertation/MN Lakes/')


gen_mn_cartogram <- function(spdf) {
  #now that we have which lakes we want to use, we can generate the polygons to display
  ##prepare special plot 
  #get minnesota border
  us_shp <- readOGR('D/Other/National/cb_2017_us_state_500k.shp')
  mn_shp <-us_shp[us_shp@data$STUSPS=='MN',]
  mn_shp <- spTransform(mn_shp,spdf@proj4string)
  
  #create voronoi bounded by MN bounds
  bb <- owin(bbox(mn_shp)['x',],bbox(mn_shp)['y',])
  coords_ppp <- ppp(coordinates(spdf)[,1],coordinates(spdf)[,2],bb)
  vrn0 <- dirichlet(coords_ppp)
  vrn_shp <- as(vrn0,'SpatialPolygons')
  vrn_shp@proj4string <- mn_shp@proj4string
  
  #clip the voronoi using MN
  vrn_mn <- gIntersection(mn_shp,vrn_shp,byid = T)
  
  #Cartogram partially towards equal sized units.
  vrn_mn_df <- SpatialPolygonsDataFrame(vrn_mn,spdf@data,match.ID = F)
  vrn_mn_df@data$const <- 1
  vrn_mn_carto <- cartogram_cont(vrn_mn_df,'const',3)
  
  return(vrn_mn_carto)
  
}

diverging_palette <- function(d = NULL, centered = FALSE, midpoint = 0,
                              colors = RColorBrewer::brewer.pal(7,"RdBu")){
  
  half <- length(colors)/2
  
  if(!length(colors)%%2) stop("requires odd number of colors")
  
  values <-  if(centered) {
    low <- seq(min(d), midpoint, length=half)
    high <- seq(midpoint, max(d), length=half)
    c(low[-length(low)], midpoint, high[-1])
  } else {
    mabs <- max(abs(d - midpoint))
    seq(midpoint-mabs, midpoint + mabs, length=length(colors))
  }
  
  scales::gradient_n_pal(colors, values = values)
  
}

gradient_palette <- function(d = NULL, colors = RColorBrewer::brewer.pal(7,"PuBu"), ...){
  
  values <-  seq(min(d), max(d), length=length(colors))
  if (max(d) <0 ) values <- rev(values)
  scales::gradient_n_pal(colors, values = values)
  
}

roundbreaks <- function(breaknames) {
  new_bn <- c()
  for (b in breaknames) {
    mid <- str_locate(b,',')[1]
    v1 <- as.numeric(substr(b,2,mid-1))
    if (abs(v1) >=10) {
      nv1 <- round(v1,0)
    } else if (abs(v1) >=1) {
      nv1 <- round(v1,1)
    } else {
      nv1 <- round(v1,2)
    }
    
    
    v2 <- as.numeric(substr(b,mid+1,nchar(b)-1))
    if (abs(v2) >=10) {
      nv2 <- round(v2,0)
    } else if (abs(v2) >=1) {
      nv2 <- round(v2,1)
    } else {
      nv2 <- round(v2,2)
    }
    
    new_bn <- c(new_bn,(paste0(nv1,' to ',nv2)))
    
  }
  
  return(new_bn)
  
}



myplot <- function(var,shp) {
  
  if ((min(var) < 0) & (max(var)>0)) {
    pal_func <- diverging_palette(var,centered=T,midpoint = 0)
  } else {
    pal_func <- gradient_palette(var)
  }
  
  colors <- pal_func(var)
  #get legend colors
  Class <- classIntervals(var, 7, style="equal")
  leg_colors <- pal_func(Class$brks)
  #cant get the break names now class interval object, for no good reason. make a dummy
  breaknames <- names(attr(findColours(Class, brewer.pal(7,'PuBu')),'table'))
  roundbreaknames <- roundbreaks(breaknames)
  
  plot(shp,pch=16,cex=1.1,col=colors)
  
  legend("topleft",
         legend=roundbreaknames,
         fill=leg_colors,
         cex=0.6, bty="n")
  
}