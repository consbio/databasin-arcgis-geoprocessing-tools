import arcpy
import time
import os
import math

#Need location of this package, so we can use it to get regions
PKG_DIR=os.path.split(__file__)[0]

#NOTE: regions must have RegionID, and if a subregion, must also have ParentIDs
REGIONS_GDB="%s/geographic_regions.gdb"%(PKG_DIR)
REGIONS={"admin":["admin0","admin1"],"continents":["physical0"],"marine":["marine0"]}
TIMEOUT=600 #seconds

VALID_EXTENTS={3857:[-20037507.0671618,-19971868.8804086,20037507.0671618,19971868.8804086]}


class ProgressListener(object):
    '''Helper class to track progress in operation.'''
    def __init__(self,arcpy=None):
        self.progress=0
        self.messages=[]
        self.operation=""
        self.arcpy=arcpy
    def updateProgress(self,operation,progress,message=None):
        self.operation=operation
        self.progress=progress
        if message:
            self.messages.append(message)
        progressMessage="PROGRESS (%s): %.0f"%(self.operation,self.progress)
        print progressMessage
        if self.arcpy:
            self.arcpy.AddMessage(progressMessage)
    def reset(self):
        self.progress=0
        self.operation=""
        self.messages=[]


class Dataset:
    '''Basic class to encapsulate core properties of a dataset'''
    def __init__(self,src):
        self.src=src
        self.srcInfo=arcpy.Describe(src)
        self.getValidExtent()
        self.features=src
        if self.srcInfo.dataType=="RasterDataset":
            self.features=None
            self.geomType="Polygon"
        else:
            self.geomType=self.srcInfo.shapeType

    def getValidExtent(self):
        print self.srcInfo.extent
        lowerLeft=self.srcInfo.extent.lowerLeft
        upperLeft=self.srcInfo.extent.upperLeft
        lowerRight=self.srcInfo.extent.lowerRight
        upperRight=self.srcInfo.extent.upperRight
        projCode=self.srcInfo.spatialReference.factoryCode
        if VALID_EXTENTS.has_key(projCode):
            #need to make sure we are within valid world coordinates, apparently
            #which are xmin,ymin,xmax,ymax: -20037507.0671618,-19971868.8804086,20037507.0671618,19971868.8804086
            valid_xmin,valid_ymin,valid_xmax,valid_ymax=VALID_EXTENTS[projCode]
            xmin=max(valid_xmin,lowerLeft.X)
            ymin=max(valid_ymin,lowerLeft.Y)
            xmax=min(valid_xmax,upperRight.X)
            ymax=min(valid_ymax,upperRight.Y)
            lowerLeft=arcpy.Point(xmin,ymin)
            lowerRight=arcpy.Point(xmax,ymin)
            uppperLeft=arcpy.Point(xmin,ymax)
            upperRight=arcpy.Point(xmax,ymax)

        self.extent=arcpy.Polygon(arcpy.Array([lowerLeft, upperLeft, upperRight, lowerRight, lowerLeft]),self.srcInfo.spatialReference)
            
    def getFeatures(self):
        if not self.features:
            self.generateRasterBoundary()
        return self.features
            
    def generateRasterBoundary(self):
        arcpy.CheckOutExtension("spatial")
        scratchDir="c:/temp"
        if not os.path.exists(scratchDir):
            os.makedirs(scratchDir)
        arcpy.env.scratchWorkspace=scratchDir
        maxCells=1000000 #Tune This - right now this seems to take a reasonable amount of time
        prevCellsize=arcpy.env.cellSize
        cellSize=self.srcInfo.meanCellWidth
        arcpy.env.cellSize=cellSize
        cellCount=self.srcInfo.height*self.srcInfo.width
        if (cellCount)>maxCells: 
            arcpy.env.cellSize=int(math.floor(cellSize/(math.sqrt(maxCells)/math.sqrt(cellCount))))
        print "Converting raster to mask and extracting polygon boundary..."
        self.features=arcpy.RasterToPolygon_conversion (arcpy.sa.Con(self.src,1), "IN_MEMORY/rasterBoundary","NO_SIMPLIFY").getOutput(0)
        #reset cellsize
        arcpy.env.cellSize=prevCellsize


def getIDs(lyr,IDField):
    '''Iterate over records and return unique set of IDs'''
    IDs=set()
    if countFeatures(lyr):
        rows = arcpy.SearchCursor(lyr,"","",IDField)
        for row in rows:
            IDs.add(row.getValue(IDField))
        del row,rows
    return IDs


def countFeatures(lyr):
    return int(arcpy.GetCount_management(lyr).getOutput(0))


def getContainedByRegion(srcExtent,regionsLyr):
    '''Get the region that completely contains the source extent'''
    #by definition, there can only be one region that completely contains the extent of this dataset
    arcpy.SelectLayerByLocation_management(regionsLyr,"COMPLETELY_CONTAINS",srcExtent,"","NEW_SELECTION")
    return getIDs(regionsLyr,"RegionID")         


def getExtentPoly(srcInfo):
    '''Get extent polygon for srcInfo (results of arcpy.Describe()'''
    extent=srcInfo.extent
    return arcpy.Polygon(arcpy.Array([extent.lowerLeft, extent.upperLeft, extent.upperRight, extent.lowerRight, extent.lowerLeft]),srcInfo.spatialReference)


def getRegions(dataset,regionsFC,parentIDs=None):
    '''Get the regions that intersect and are completely contained by the (simplified) boundary of the raster'''
    intersectedRegions=set()
    containedRegions=set()
    whereClause=""
    if parentIDs:
        whereClause="\"ParentID\" in ('%s')"%("','".join(parentIDs))
    regionsLyr=arcpy.MakeFeatureLayer_management(regionsFC,"regionsLyr",whereClause).getOutput(0)

    containedByRegion=getContainedByRegion(dataset.extent,regionsLyr)
    intersectedRegions.update(containedByRegion)
    #only proceed if extent is not completely contained by region
    if not len(containedByRegion):
        #Select using extent of dataset
        arcpy.SelectLayerByLocation_management(regionsLyr,"INTERSECT",dataset.extent,"","NEW_SELECTION")
        if countFeatures(regionsLyr) > 0:    
            #Select using the source features
            arcpy.SelectLayerByLocation_management(regionsLyr,"INTERSECT",dataset.getFeatures(),"","SUBSET_SELECTION")
            intersectedRegions.update(getIDs(regionsLyr,"RegionID"))
            #get regions completely contained by dataset - but only if source is a polygon!
            if dataset.geomType=="Polygon":
                arcpy.SelectLayerByLocation_management(regionsLyr,"COMPLETELY_WITHIN",dataset.getFeatures(),"","SUBSET_SELECTION")
                containedRegions.update(getIDs(regionsLyr,"RegionID"))
    arcpy.Delete_management(regionsLyr)
    del regionsLyr
    return intersectedRegions,containedRegions


def getRegionsForDatasets(dataSources,regions=None,progressListener=None):
    '''Iterate over all unique data sources, and return list of unique intersected regions and contained regions '''
    if progressListener:
        progressListener.updateProgress("evaluating_regions",0)

    if not regions:
        regions=REGIONS.keys()
    numRegions=sum([len(REGIONS[item]) for item in regions])

    intersectedRegions=dict()
    containedRegions=dict()
    counter=0.0
    start=time.time()
    numDataSources=float(len(dataSources))
    for src in dataSources:
        if time.time()-start>TIMEOUT:
            raise Exception("Processing time is greater than timeout; stopping now...")
        print "Processing %s"%(src)
        dataset=Dataset(src)
        regionCounter=0.0
        intersectedRegions[src]=set()
        containedRegions[src]=set()
        
        for region in regions:
            regionsFC=REGIONS[region][0]
            print "Evaluating against %s"%(regionsFC)
            intersected,contained = getRegions(dataset,os.path.join(REGIONS_GDB,regionsFC))
            intersectedRegions[src].update(intersected)
            containedRegions[src].update(contained)
            regionCounter+=1
            if progressListener:
                progressListener.updateProgress("evaluating_regions",100.0 * ((counter/numDataSources) + ((1/numDataSources) * (regionCounter/numRegions))))

            for subRegionFC in REGIONS[region][1:]:
                intersectedNotContained=intersected.difference(contained)
                intersected=contained=set()
                if len(intersectedNotContained):
                    print "Evaluating against %s"%(subRegionFC)
                    intersected,contained = getRegions(dataset,os.path.join(REGIONS_GDB,subRegionFC),intersectedNotContained)
                    intersectedRegions[src].update(intersected)
                    containedRegions[src].update(contained)
                regionCounter+=1
                if progressListener:
                    progressListener.updateProgress("evaluating_regions",100.0 * ((counter/numDataSources) + ((1/numDataSources) * (regionCounter/numRegions))))
        counter+=1       
    return intersectedRegions, containedRegions