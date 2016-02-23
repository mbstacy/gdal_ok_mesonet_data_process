#!/usr/bin/env python
'''
Created on Feb 2, 2016

@author: ledapsTwo
'''
from osgeo import gdal,osr
from os import path
from csv import DictReader
import shlex,sys
import pandas as pd
import numpy as np

class raster:
    
    def __init__(self,inFile):
        gf = gdal.Open(inFile)
        self.raster = gf
        self.grid = gf.ReadAsArray()
        
        #get number of rows and columns in the shape
        self.numGrids = 1
        if len(self.grid.shape) == 3:
            self.numGrids,self.numRows,self.numCols = self.grid.shape
        else:
            self.numRows,self.numCols = self.grid.shape
        
        #get projection and spatial reference infomation
        srs = osr.SpatialReference()
        srs.ImportFromWkt(gf.GetProjection())
        srsLatLong = srs.CloneGeogCS()
        self.srs = srs ; self.srsLatLong = srsLatLong
        
        #create coordinate transform object for sample/line to lon/lat conversion
        self.ct = osr.CoordinateTransformation(srs, srsLatLong)
        #create coordinate transform object for lon/lat to sample/line conversion
        self.ctInv = osr.CoordinateTransformation(srsLatLong, srs)
        
        #get geographic transform information in cartesian space
        self.geoMatrix = gf.GetGeoTransform()
        
        #with no north correction this is equal to (pixel height * pixel width) = -900
        dev = (self.geoMatrix[1] * self.geoMatrix[5]) - (self.geoMatrix[2] * self.geoMatrix[4])
        #divide height/width components by this -900 to get a decimal degrees value
        self.gtinv = (self.geoMatrix[0], self.geoMatrix[5]/dev, -1 * self.geoMatrix[2]/dev, self.geoMatrix[3], -1 * self.geoMatrix[4]/dev, self.geoMatrix[1]/dev)

def parseMesonetFile():
    mesoCSV = "{0}.csv".format(mesoFile.split('.')[0])  #path.join(curDir,'%s.csv'%path.basename(mesoFile).split('.')[0])
    if not path.exists(mesoCSV):
        with open(mesoFile,'r') as f1:
            data = f1.read()
            data_list=data.split('\n')
            table = []
            for line in data_list[2:-1]:
                table.append(shlex.split(line))
            headers = table.pop(0)
            df = pd.DataFrame(table,columns=headers)
            outFile = path.basename(mesoFile).split('.')[0]
            df.to_csv("%s.csv" % (outFile),index=False)
    f = open(mesoCSV,'r')
    aSites = DictReader(f)
    
    return aSites

def convertLatLontoPixelLine(inGrid,lat,lon): 
    #convert lon/lat to cartesian coordinates
    x,y,z =  inGrid.ctInv.TransformPoint(lon,lat,0)
    
    #subtract out upper left pixel coordinates to move origin to upper-left corner of the grid
    u = x - inGrid.gtinv[0]
    v = y - inGrid.gtinv[3]
    #print lon,lat,x,y,u,v
    #multiply u & v by 0.333333 or -0.333333 to convert cartesian to pixel/line combo
    col = (inGrid.gtinv[1] * u) + (inGrid.gtinv[2] * v)
    row = (inGrid.gtinv[4] * u) + (inGrid.gtinv[5] * v)
    #print lon,lat,x,y,u,v,col,row
    return row,col

def convertPixelLinetoLatLong(inGrid,row,col):

    X = (inGrid.geoMatrix[0] + (inGrid.geoMatrix[1] * col) + (inGrid.geoMatrix[2] * row)) + inGrid.geoMatrix[1]/2.0
    Y = (inGrid.geoMatrix[3] + (inGrid.geoMatrix[4] * col) + (inGrid.geoMatrix[5] * row)) + inGrid.geoMatrix[5]/2.0
    (lon, lat, height) = inGrid.ct.TransformPoint(X,Y)
    lon = round(lon,11) ; lat = round(lat,11)
    return lat,lon

def main():
    
    #read in TIF file as a raster object
    tif = raster(tifFile)

    #read in mesonet data and break at each new line
    aSites = parseMesonetFile()
    #print(aSites)
    aOut = []
    #walk through each site, pull the lat/lon and determine point on raster grid
    for mesoSite in aSites:
        #print (mesoSite)
        siteID = mesoSite["STID"] #the site ID from the CSV
        stNum = mesoSite["STNM"] #station number
        stTime = mesoSite["TIME"] #station time
        lat = float(mesoSite["LATT"]) #the latitude from the CSV
        lon = float(mesoSite["LONG"]) #the longitude from the CSV
        
        #the row and column on the raster above this mesonet site
        rasterRow,rasterColumn = convertLatLontoPixelLine(tif, lat, lon)
        #the value on the raster at this grid point
        rasterValue = tif.grid[rasterRow,rasterColumn]
        
        #build skeleton for header and station lines
        header = "STID,STNM,TIME,LATT,LONG,RASTERVAL"
        strOut = "%s,%s,%s,%s,%s,%s"%(siteID,stNum,stTime,lat,lon,rasterValue)
        
        #walk through all attributes and place into above strings
        for param in sorted(mesoSite.keys()):
            #skip any of these as they have already been defined above
            if param in ["STID","STNM","TIME","LATT","LONG"]: continue
            header += ",%s"%param
            strOut += ",%s"%mesoSite[param]
        
        #add header first so it will be at the top of the output file
        if header not in aOut: aOut.append(header)
        #append station attributes to list
        aOut.append(strOut)
    
    
    #convert list to block of text and write to file
    outFile = open("summary%s.csv"%ext,'w')
    outFile.write("\n".join(aOut))
    outFile.close()
    
    print ("DONE")
if __name__ == "__main__":
    
    #global curDir ; curDir = path.dirname(path.realpath(__file__))
    global tifFile ; tifFile = sys.argv[1] #path.join(curDir,'y12.modisSSEBopET.tif')
    global mesoFile ; mesoFile = sys.argv[2] #path.join(curDir,'2012_annual.mdf')
    global ext; ext = ""
    main()
