"""
Tabulate feature or raster data using features contained in a FeatureSet

See test_tabulate for example usage.

TODO:
- add time support
check out recipe at: http://arcpy.wordpress.com/2012/07/02/retrieving-total-counts/ for counter example

"""
from tool_logging import ToolLogger
logger = ToolLogger.getLogger("tabulate")
logger.debug("Tabulate started")

import os,sys, tempfile, time, traceback, shutil, json, re, copy
if __name__ == "__main__":
    #Make sure we're using the ArcGIS server (as opposed to the Desktop) arcpy package.
    for path in filter(lambda x: os.path.normpath(x.lower()).replace("\\","/").count("arcgis/server"),sys.path):
        sys.path.insert(0, path)

import arcpy
from utilities import FeatureSetConverter, ProjectionUtilities
import settings
from utilities.PathUtils import TemporaryWorkspace,getMXDPathForService
#from tool_logging import ToolLogger
from messaging import MessageHandler


#Setup environment variables
arcpy.env.overwriteOutput = True
arcpy.env.pyramid="NONE"
arcpy.env.rasterStatistics="NONE" #we will calculate these manually as required

#Setup globals
#logger = ToolLogger.getLogger("tabulate")
TEMP_WORKSPACE=TemporaryWorkspace()

class FeatureClassWrapper:
    """
    convenience class to provide cached access to descriptive properties and projected variants of feature class
    """

    def __init__(self,featureClass):
        self.featureClass=featureClass
        self.name=os.path.split(self.featureClass)[1]
        #internal attributes, only fetch as necessary since initial lookup time may be slow
        self._info=None
        self._geometryType=None
        self._spatialReference=None
        self._numFeatures=None
        self._prjLUT=dict()
        self._prjCache=dict()


    def getCount(self):
        if self._numFeatures is None:
            self._numFeatures=int(arcpy.GetCount_management(self.featureClass).getOutput(0))
        return self._numFeatures

    #Can also get from cursor - what do we get first?
    def getGeometryType(self):
        if self._geometryType is None:
            self._geometryType=self._getInfo().shapeType
        return self._geometryType

    def getSpatialReference(self):
        if self._spatialReference is None:
            self._spatialReference = self._getInfo().spatialReference
        return self._spatialReference

    def _getInfo(self):
        if self._info is None:
            self._info=arcpy.Describe(self.featureClass)
        return self._info

    def _getProjID(self,spatialReference):
        key=spatialReference.factoryCode
        if not key:
            key="hash%s"%(hash(spatialReference.exporttostring()))
        if not self._prjLUT.has_key(key):
            self._prjLUT[key]=len(self._prjLUT.keys())
        return self._prjLUT[key]

    def project(self,targetSpatialReference):
        projKey = "%s_%s" % (self.name,self._getProjID(targetSpatialReference))

        if not self._prjCache.has_key(projKey):
            fcPath=str(self.featureClass)
            if fcPath.count("IN_MEMORY/"): #need to persist or it will fail during projection steps
                logger.debug("Persisting feature class to temporary geodatabase")
                newFCPath=os.path.normpath(fcPath.replace("IN_MEMORY",TEMP_WORKSPACE.getGDB()))
                if arcpy.Exists(newFCPath):
                    arcpy.Delete_management(newFCPath)
                arcpy.CopyFeatures_management(self.featureClass,newFCPath)
                self.featureClass=newFCPath

            if not self._prjCache:
                #cache current projection
                existingPrjKey="%s_%s" % (self.name,self._getProjID(self.getSpatialReference()))
                self._prjCache[existingPrjKey]=self.featureClass
                if projKey==existingPrjKey:
                    return self.featureClass

            targetProjLabel = targetSpatialReference.factoryCode or targetSpatialReference.exporttostring()
            projFCPath=os.path.join(TEMP_WORKSPACE.getGDB(),projKey)
            if arcpy.Exists(projFCPath):
                arcpy.Delete_management(projFCPath)
            geoTransform=ProjectionUtilities.getGeoTransform(self.getSpatialReference(), targetSpatialReference)
            logger.debug("Projecting %s to %s using transform %s"%(self.name,targetProjLabel,geoTransform))
            self._prjCache[projKey] = arcpy.Project_management(self.featureClass, projFCPath,targetSpatialReference,geoTransform).getOutput(0)
        return self._prjCache[projKey]

    def getQuantityAttribute(self):
        if self.getGeometryType()=="Polyline":
            return "length"
        elif self.getGeometryType()=="Polygon":
            return "area"
        return None

    def getGeometryConversionFactor(self,targetSpatialReference):
        """
        Return area / length multiplication factor to calculate hectares / kilometers for the specified projection
        """

        if self.getGeometryType()=="Polyline":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[0]
        elif self.getGeometryType()=="Polygon":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[1]
        return 0

    def getTotalAreaOrLength(self,targetSpatialReference=None):
        """
        Return total area or length, if geometry type supports it, in the target projection
        """
        if not self.getGeometryType() in ["Polygon","Polyline"]:
            return None
        if not targetSpatialReference:
            targetSpatialReference=self.getSpatialReference()
        projFC=self.project(targetSpatialReference)
        quantityAttribute=self.getQuantityAttribute()
        rows=arcpy.SearchCursor(projFC)
        total=sum([getattr(row.shape,quantityAttribute) for row in rows]) * self.getGeometryConversionFactor(targetSpatialReference)
        del rows
        return total


class SummaryResult:
    """
    convenience class wrapper of a summary record
    """
    def __init__(self):
        self.count=0
        self.quantity=0 #quantity is area / length if applicable
    def update(self,count,quantity=None):
        self.count+=count
        if quantity:
            self.quantity+=quantity


class SummaryField:
    '''
    convenience class wrapper of an attribute used for summarization of attribute values by unique, classes, or statistics
    '''

    def __init__(self,fieldJSON,hasGeometry=False):
        self.attribute=fieldJSON["attribute"]
        self.statistics=fieldJSON.get("statistics",[])
        self.results=dict()
        self.classes=fieldJSON.get("classes",[])
        self._classRanges=[]
        for i in range(0,len(self.classes)):
            classRange=self.classes[i]
            self._classRanges.append((float(classRange[0]),float(classRange[1])))
            self.results[i]=SummaryResult()

        self.hasGeometry=hasGeometry

    def addRecord(self,value,count,quantity=None): #quantity: area or length
        key=None
        if self.classes:
            key=self.getClass(value)
        else:
            key=value
        if key:
            if not self.results.has_key(key):
                self.results[key]=SummaryResult()
            self.results[key].update(count,quantity)

    def getClass(self,value):
        #>=lower value and <upper
        for classIndex in range(0,len(self._classRanges)):
            classRange=self._classRanges[classIndex]
            if value>=classRange[0] and value<classRange[1]: #TODO: may need to test for <= to last class upper value
                return classIndex
        return None

    def getStatistics(self,statisticsList):
        statistics=dict()
        statisticAttribute="count"
        if self.hasGeometry:
            statisticAttribute="quantity"
        for statistic in statisticsList:
            statisticName=statistic.upper()
            if statisticName=="SUM":
                #sum = count * value for each entry in results
                statistics[statistic]=sum([(self.results[key].count * key) for key in self.results.keys()])
            elif statisticName=="MIN":
                statistics[statistic]=min(self.results.keys())
            elif statisticName=="MAX":
                statistics[statistic]=max(self.results.keys())
            elif statisticName=="MEAN":
                #area/length/count weighted average
                total=float(sum([getattr(result,statisticAttribute) for result in self.results.values()]))
                if total:
                    statistics[statistic]=sum(map(lambda value: value*(float(getattr(self.results[value],statisticAttribute))/total),self.results))
                else:
                    statistics[statistic]=None
        return statistics

    def getResults(self):
        fieldResults={'attribute':self.attribute}
        if self.statistics:
            fieldResults["statistics"]=self.getStatistics(self.statistics)
        if self.classes:
            classResults=[]
            for i in range(0,len(self.classes)):
                classResult={"class":self.classes[i],"count":self.results[i].count}
                if self.hasGeometry:
                    classResult["quantity"]=self.results[i].quantity
                classResults.append(classResult)
            fieldResults.update({'classes':classResults})
        else:
            valueResults=[]
            for key in self.results:
                valueResult={"value":key,"count":self.results[key].count}
                if self.hasGeometry:
                    valueResult["quantity"]=self.results[key].quantity
                valueResults.append(valueResult)
            fieldResults.update({'values':valueResults})
        return fieldResults

#TODO: update to match usage below
def getGridClasses(grid, field, classBreaks):
    remapClasses=[]
    for i in range(0,len(classBreaks)):
        classBreak=classBreaks[i]
        remapClasses.append([classBreak[0],classBreak[1],i])
    arcpy.CalculateStatistics_management(grid)
    reclassGrid = arcpy.sa.Reclassify(grid, field, arcpy.sa.RemapRange(remapClasses), "NODATA")
    results = dict()
    rows = arcpy.SearchCursor(reclassGrid)
    for row in rows:
        results[row.getValue("Value")] = row.COUNT #value is the class index
    del row,rows
    return results


#Note: values is
def getNumpyClassQuantities(values,quantities,classBreaks):
    """
    :param values:  either original grid values, or attribute values transposed onto grid (numeric types only)
    :param quantities: quantities measured for each pixel
    :param classBreaks:
    :return: list with dictionary objects of class range, count, and quantity
    """

    import numpy
    class_results=[]
    classified_values=numpy.zeros(values.shape,numpy.int)
    for i in range(0,len(classBreaks)):
        class_range=classBreaks["classes"][i]
        class_range[0]=float(class_range[0])
        class_range[1]=float(class_range[1])
        classified_values = classified_values + i * numpy.logical_and(values >= class_range[0], values < class_range[1])
    flat_classes=classified_values.flatten()
    class_counts = numpy.bincount(flat_classes)
    class_quantities = numpy.bincount(flat_classes,weights=quantities.flatten())
    for i in range(0,len(classBreaks["classes"])):
        count=0
        quantity=0
        if i<len(class_counts):
            count=class_counts[i]
            quantity=class_quantities[i]
        class_results.append({"class":classBreaks["classes"][i],"count":count,"quantity":quantity})
    return class_results


def FishnetOIDToNumpy(OID,rows,cols):
    '''
    Return the row and column in grid coordinates that correspond to the given OID
    Fishnet numbers start at 1, in bottom left corner, and go columnwise from there.
    Grid coordinates start at 0, and start in upper left
    '''
    row,col=divmod(OID-1,cols)
    row=(rows-1) - row #invert row order
    return row,col



#TODO: use python Counter class if supported
def getGridCount(grid, summaryField):
    '''
    Return total count of pixels, and count by summary field if passed in
    '''

    totalCount = 0
    summary = dict()

    try:
        #this will fail if there is no attribute table (e.g., all pixels are NODATA)
        rows = arcpy.SearchCursor(grid)
        for row in rows:
            count=int(row.COUNT)
            totalCount += count
            if summaryField:
                summaryValue = row.getValue(summaryField)
                if not summary.has_key(summaryValue):
                    summary[summaryValue] = 0
                summary[summaryValue] += count
        del row, rows
    except:
        pass
    return totalCount, summary



def tabulateRasterLayer(srcFC,layer,layerConfig,spatialReference,messages):
    '''
    srcFC: source feature class wrapper
    layer: layer object
    layerConfig: subset of config for a single layer
    spatialReference: spatial reference object with target projection
    '''

    logger.debug("Processing %s"%(layer.name))
    arcpy.env.snapRaster = layer.dataSource
    arcpy.env.workspace=TEMP_WORKSPACE.getDirectory()
    try:
        arcpy.env.scratchWorkspace=TEMP_WORKSPACE.getDirectory() # this completely crashes the server container, somehow scratchWorkspace is getting corrupted and cannot be set
        logger.debug("Set scratch workspace")
    except:
        logger.debug("Could not set scratch workspace")

    #Pixel area is based on the projection: uses native projection of grid if it is a projected system, otherwise project cell area to target spatialReference
    pixelArea, projectionType = ProjectionUtilities.getCellArea(layer.dataSource, spatialReference)

    results={
        "geometryType":"pixel",
        "pixelArea":pixelArea,
        "projectionType":projectionType,
        "intersectionQuantity":0,
        "method":"approximate" #approximate, precise  TODO: document
    }

    try:
        #Convert the projected user defined feature class (projFC) to a temporary raster - which is in the same spatial reference as the target raster.
        lyrInfo = arcpy.Describe(layer.dataSource)
        projFC=srcFC.project(lyrInfo.spatialReference)
        projFCLyr=arcpy.mapping.Layer(projFC)
        extent=projFCLyr.getExtent()
        rasterExtent=lyrInfo.extent
        #TODO: project only extent, then do the rest in the target projection

        #have to do the comparison ourselves; the builtin geometric comparisons don't work properly (e.g., extent.overlaps)
        if extent.XMin > rasterExtent.XMax or extent.XMax < rasterExtent.XMin or extent.YMin > rasterExtent.YMax or extent.YMax < rasterExtent.YMin:
            logger.debug(extent)
            logger.debug(lyrInfo.extent)
            logger.debug("Source features do not overlap target raster")
            return results

        arcpy.env.extent=extent #this speeds up later processing
        arcpy.CheckOutExtension("Spatial")

        #extract
        clippedGrid="data"
        arcpy.Clip_management(layer.dataSource,"%f %f %f %f"%(extent.XMin,extent.YMin,extent.XMax,extent.YMax),clippedGrid,"#","#","NONE")
        clippedGrid = arcpy.Raster(clippedGrid)
        numPixels = clippedGrid.height * clippedGrid.width
        logger.debug("%i pixels within extent of source features"%(numPixels))
        logger.debug("Geometry type is %s"%(srcFC.getGeometryType()))

        if numPixels <= 50000 and srcFC.getGeometryType() in ["Polygon","Polyline"]: #arbitrary limit above which too big to use more exact fishnet-based area weighted methods
            import numpy
            results['method']="precise"
            logger.debug("Small input grid, using precise method")

            logger.debug("Creating fishnet")
            fishnet=os.path.join(TEMP_WORKSPACE.getGDB(),"fishnet")
            arcpy.CreateFishnet_management (fishnet, "%f %f"%(clippedGrid.extent.XMin,clippedGrid.extent.YMin), "%f %f"%(clippedGrid.extent.XMin,clippedGrid.extent.YMax), clippedGrid.meanCellWidth, clippedGrid.meanCellHeight, clippedGrid.height, clippedGrid.width, "#", False, clippedGrid, "POLYGON")

            logger.debug("Intersecting with area of interest")
            intersection = os.path.join(TEMP_WORKSPACE.getGDB(),"intersection")
            arcpy.Intersect_analysis("%s #;%s #"%(projFC,fishnet),intersection,"ONLY_FID","#","INPUT")

            logger.debug("Tabulating quantities")
            values = arcpy.RasterToNumPyArray(clippedGrid,nodata_to_value=numpy.nan)
            quantities=numpy.zeros(values.shape)
            quantityAttribute=srcFC.getQuantityAttribute()
            areaLengthFactor=0
            if srcFC.getGeometryType()=="Polyline":
                areaLengthFactor = ProjectionUtilities.getProjUnitFactors(lyrInfo.spatialReference)[0]
            elif srcFC.getGeometryType()=="Polygon":
                areaLengthFactor = ProjectionUtilities.getProjUnitFactors(lyrInfo.spatialReference)[1]
            rows=arcpy.SearchCursor(intersection)
            for row in rows:
                OID=row.getValue("FID_%s"%(os.path.split(fishnet)[1]))
                grid_row,grid_col=FishnetOIDToNumpy(OID,clippedGrid.height,clippedGrid.width)
                quantities[grid_row][grid_col]=getattr(row.shape,quantityAttribute) * areaLengthFactor
            del row,rows

            values = numpy.ma.masked_array(values,numpy.logical_or(numpy.isnan(values), quantities==0)) #mask out the original NoData values and areas outside AOI
            results["intersectionPixelCount"] = values.mask.sum()
            results["intersectionQuantity"] = (results["intersectionPixelCount"]) * pixelArea
            results["sourcePixelCount"] = (quantities!=0).sum()

            src_total_quantity=srcFC.getTotalAreaOrLength(lyrInfo.spatialReference)

            if layerConfig.has_key("statistics"):
                logger.debug("Calculating statistics")
                #straight statistics are easy
                results["statistics"]=dict()
                if "MIN" in layerConfig["statistics"]:
                    results["statistics"]["MIN"]=values.min()
                if "MAX" in layerConfig["statistics"]:
                    results["statistics"]["MAX"]=values.max()
                if "MEAN" in layerConfig["statistics"]:
                    results["statistics"]["MEAN"]=values.mean()
                if "STD" in layerConfig["statistics"]:
                    results["statistics"]["STD"]=values.std()
                if "SUM" in layerConfig["statistics"]:
                    results["statistics"]["SUM"]=values.sum()

                #weighted statistics are harder and only really applicable to polygons
                if srcFC.getGeometryType()=="polyline":
                    if "MEAN" in layerConfig["statistics"]:
                        weighted_values = values * quantities / src_total_quantity #weighted by proportion of srcFC
                        results["statistics"]["WEIGHTED_MEAN"]=weighted_values.sum()
                else:
                    pixel_proportion=quantities / pixelArea
                    weighted_values = values * pixel_proportion #weighted by proportion of each pixel occupied, assuming equal distribution within pixels
                    if "MIN" in layerConfig["statistics"]:
                        results["statistics"]["WEIGHTED_MIN"]=weighted_values.min()
                    if "MAX" in layerConfig["statistics"]:
                        results["statistics"]["WEIGHTED_MAX"]=weighted_values.max()
                    if "MEAN" in layerConfig["statistics"]:
                        results["statistics"]["WEIGHTED_MEAN"]=weighted_values.sum() / pixel_proportion.sum()
                    if "STD" in layerConfig["statistics"]:
                        results["statistics"]["WEIGHTED_STD"]=weighted_values.std()
                    if "SUM" in layerConfig["statistics"]:
                        results["statistics"]["WEIGHTED_SUM"]=weighted_values.sum()
            else:
                if not clippedGrid.isInteger:
                    #only option is classes of original values
                    if layerConfig.has_key("classes"):
                        logger.debug("Classifying input raster")
                        results.update({'classes':getNumpyClassQuantities(values,quantities,layerConfig["classes"])})
                else:
                    logger.debug("Tabulating unique values")
                    values=values.astype(int)
                    #tally quantities by value
                    flat_values=values.flatten()
                    flat_quantities=quantities.flatten()
                    count_by_value=dict()
                    quantity_by_value=dict()
                    for value in numpy.unique(flat_values):
                        equals_value = flat_values==value
                        count_by_value[value]=int(equals_value.sum())
                        quantity_by_value[value]=(equals_value * flat_quantities).sum()

                    if layerConfig.has_key("attributes") and len(layerConfig["attributes"]):
                        arcpy.BuildRasterAttributeTable_management(clippedGrid)
                        fields = [field.name for field in arcpy.ListFields(clippedGrid)]
                        summaryFields=dict([(summaryField["attribute"],SummaryField(summaryField,True)) for summaryField in layerConfig.get("attributes",[])])
                        diffFields = set(summaryFields.keys()).difference(fields)
                        if diffFields:
                            raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s"%(layer.name,",".join([str(fieldName) for fieldName in diffFields])))

                        rows = arcpy.SearchCursor(clippedGrid)
                        for row in rows:
                            value=row.getValue("VALUE")
                            count=0
                            quantity=0
                            if count_by_value.has_key(value):
                                count=count_by_value[value]
                                quantity=quantity_by_value[value]
                            for summaryField in summaryFields:
                                summaryFields[summaryField].addRecord(row.getValue(summaryField),count,quantity)
                        del rows
                        for summaryField in summaryFields:
                            results["attributes"].append(summaryFields[summaryField].getResults())

                    else:
                        if layerConfig.has_key("classes"):
                            results.update({'classes':getNumpyClassQuantities(values,quantities,layerConfig["classes"])})
                        else:
                            value_results=[]
                            unique_values=count_by_value.keys()
                            unique_values.sort()
                            for value in unique_values:
                                value_results.append({"value":value,"count":count_by_value[value],"quantity":quantity_by_value[value]})
                            results.update({'values':value_results})

        else:
            logger.debug("Large input grid, using approximate method")

            logger.debug("Creating area of interest raster")
            aoiGrid = os.path.join(TEMP_WORKSPACE.getGDB(),"aoiGrid")
            #arcpy.Describe(projFC).OIDFieldName  #we control this, not needed
            arcpy.FeatureToRaster_conversion(projFC, "OBJECTID", aoiGrid, lyrInfo.meanCellHeight)
            results["sourcePixelCount"] = getGridCount(aoiGrid, None)[0]

            if layerConfig.has_key("statistics"):
                results["statistics"]=dict()
                logger.debug("Creating zone grid for statistics from area of interest grid")
                zoneGrid= arcpy.Raster(aoiGrid) * 0
                statistics=dict()
                for statistic in layerConfig["statistics"]:
                    arcgisStatistic = statistic.upper()
                    statistics[statistic]=arcgisStatistic+"IMUM" if arcgisStatistic in ["MIN","MAX"] else arcgisStatistic
                zonalStatsTable="zonalStatsTable"
                if arcpy.Exists(zonalStatsTable):
                    arcpy.Delete_management(zonalStatsTable)
                #note: may need to make layer in to a Raster
                logger.debug("Executing zonal statistics: %s"%(",".join(statistics.values())))
                zonalStatsTable = arcpy.sa.ZonalStatisticsAsTable(zoneGrid, "VALUE", arcpy.Raster(layer.dataSource), zonalStatsTable, "DATA", "ALL")
                del zoneGrid

                totalCount=0
                rows=arcpy.SearchCursor(zonalStatsTable)
                if rows:
                    for row in rows:
                        totalCount+=row.COUNT
                        for statistic in statistics:
                            results["statistics"][statistic]=row.getValue(statistic.upper())
                        break #should only have one row
                    del row
                del rows,zonalStatsTable
                arcpy.Delete_management("zonalStatsTable")

            else:
                #clip the target using this grid, snapped to the original grid - watch for alignment issues in aoiGrid - snapRaster is not used there
                logger.debug("Extracting area of interest from %s"%(layer.name))
                clipGrid = arcpy.sa.ExtractByMask(layer, aoiGrid)

                if not clipGrid.isInteger:
                    #force to single bit data, since we can't build attribute tables of floating point data.
                    testGrid = arcpy.sa.Times(clipGrid,0)
                    arcpy.BuildRasterAttributeTable_management(testGrid)
                    results["intersectionPixelCount"] = getGridCount(testGrid, None)[0]
                    del testGrid

                    if layerConfig.has_key("classes"):
                        classCounts=getGridClasses(clipGrid, "VALUE", layerConfig["classes"])
                        classResults=[]
                        for classIndex in range(0,len(layerConfig["classes"])):
                            count=classCounts.get(classIndex,0)
                            classResults.append({"class":layerConfig["classes"][classIndex],"count":count,"quantity":(float(count)*pixelArea)})
                        results.update({'classes':classResults})

                else:
                    arcpy.BuildRasterAttributeTable_management(clipGrid)
                    promoteValueResults=False
                    if not layerConfig.has_key("attributes"):
                        promoteValueResults=True
                        layerConfig["attributes"]=[{'attribute':'VALUE'}]
                        if layerConfig.has_key("classes"):
                            layerConfig["attributes"][0]['classes']=layerConfig['classes']

                    summaryFields=dict([(summaryField["attribute"],SummaryField(summaryField,True)) for summaryField in layerConfig.get("attributes",[])])
                    if summaryFields:
                        fieldList = set([field.name for field in arcpy.ListFields(clipGrid)])
                        diffFields = set(summaryFields.keys()).difference(fieldList)
                        if diffFields:
                            raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s"%(layer.name,",".join([str(fieldName) for fieldName in diffFields])))
                        if not promoteValueResults:
                            results["attributes"]=[]

                    #TODO: use python Counter class if available (python > 2.7)
                    count=0
                    rows = arcpy.SearchCursor(clipGrid, "", "")
                    for row in rows:
                        count+=row.COUNT
                        for summaryField in summaryFields:
                            summaryFields[summaryField].addRecord(row.getValue(summaryField),row.COUNT,row.COUNT*pixelArea)
                    del rows
                    results["intersectionPixelCount"]=count

                    if promoteValueResults:
                        key = "classes" if layerConfig.has_key("classes") else "values"
                        results[key]=summaryFields["VALUE"].getResults()[key]
                    else:
                        for summaryField in summaryFields:
                            results["attributes"].append(summaryFields[summaryField].getResults())
                del clipGrid

                results["intersectionQuantity"] = float(results["intersectionPixelCount"]) * pixelArea

                arcpy.Delete_management(aoiGrid)
                del aoiGrid

            arcpy.Delete(clippedGrid)
            del clippedGrid

    finally:
        arcpy.env.extent=None
        arcpy.CheckInExtension("Spatial")

    return results



def tabulateFeatureLayer(srcFC,layer,layerConfig,spatialReference,messages):
    logger.debug("tabulateFeatureLayer: %s"%(layer.name))
    #arcpy.env.workspace = TEMP_WORKSPACE.getGDB()
    arcpy.env.cartographicCoordinateSystem = spatialReference
    arcpy.env.extent=None

    results=dict()

    #select features from layer using target projection and where clause (if provided)
    selLyr = arcpy.MakeFeatureLayer_management(layer, "selLyr", layerConfig.get("where","")).getOutput(0)
    logger.debug("Selected features from target layer given where clause")

    #select by location; this is done in the projection of the target FC
    arcpy.SelectLayerByLocation_management(selLyr, "INTERSECT", srcFC.featureClass)
    logger.debug("Selected features from target layer that intersect area of interest")
    featureCount = int(arcpy.GetCount_management(selLyr).getOutput(0))
    logger.debug("Found %s intersecting features"%(featureCount))

    if featureCount>0:
        selFC = "IN_MEMORY/selFC"
        #Selected features must be copied into new feature class for projection step, otherwise it uses the entire dataset (lame!)
        logger.debug("Copying selected features to in-memory feature class")
        arcpy.CopyFeatures_management(selLyr,selFC)

        #project the selection to target projection, and then intersect with source (in target projection)
        geoTransform=ProjectionUtilities.getGeoTransform(arcpy.Describe(layer.dataSource).spatialReference, spatialReference)
        logger.debug("Projecting selected features from %s"%(layer.name))
        projFC = FeatureClassWrapper(arcpy.Project_management(selFC, "projFC", spatialReference,geoTransform).getOutput(0))
        logger.debug("Intersecting selected features with area of interest")
        intFC = FeatureClassWrapper(arcpy.Intersect_analysis([srcFC.project(spatialReference), projFC.featureClass], "IN_MEMORY/" + "intFC").getOutput(0))

        featureCount = int(arcpy.GetCount_management(intFC.featureClass).getOutput(0))
        if featureCount>0:
            intersectionQuantityAttribute = intFC.getQuantityAttribute()
            intersectionConversionFactor=intFC.getGeometryConversionFactor(spatialReference)
            intersectionSummaryFields=dict([(summaryField["attribute"],SummaryField(summaryField,intersectionQuantityAttribute is not None)) for summaryField in layerConfig.get("attributes",[])])

            intersectedQuantityAttribute = projFC.getQuantityAttribute()
            intersectedConversionFactor=projFC.getGeometryConversionFactor(spatialReference)
            intersectedSummaryFields=copy.deepcopy(intersectionSummaryFields)

            if intersectionSummaryFields:
                fieldList = set([field.name for field in arcpy.ListFields(intFC.featureClass)])
                diffFields = set(intersectionSummaryFields.keys()).difference(fieldList)
                if diffFields:
                    raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s"%(layer.name,",".join([str(fieldName) for fieldName in diffFields])))
                results["attributes"]=[]

            logger.debug("Tallying intersection results")
            #tally results for intersection
            rows = arcpy.SearchCursor(intFC.featureClass) #TODO: may want to pare this down to SHAPE and summary fields only
            total=0
            count=0
            for row in rows:
                geometryCount=1 #row.shape.partCount #Note: this counts all geometries independently, is NOT number of features
                count+= geometryCount
                quantity = None
                if intersectionQuantityAttribute:
                    quantity = getattr(row.shape,intersectionQuantityAttribute) * intersectionConversionFactor
                    total+=quantity
                for summaryField in intersectionSummaryFields:
                    intersectionSummaryFields[summaryField].addRecord(row.getValue(summaryField),geometryCount,quantity)
            del row,rows

            results["intersectionGeometryType"]=intFC.getGeometryType().lower().replace("polyline","line")
            results["intersectionCount"]=count
            if intersectionQuantityAttribute:
                results["intersectionQuantity"]=total

            logger.debug("Tallying intersected feature results")
            #tally results for intersected features
            rows = arcpy.SearchCursor(projFC.featureClass)
            total=0
            count=0
            for row in rows:
                geometryCount=1 #row.shape.partCount
                count+= geometryCount
                quantity = None
                if intersectedQuantityAttribute:
                    quantity = getattr(row.shape,intersectedQuantityAttribute) * intersectedConversionFactor
                    total+=quantity
                for summaryField in intersectedSummaryFields:
                    intersectedSummaryFields[summaryField].addRecord(row.getValue(summaryField),geometryCount,quantity)
            del row,rows

            results["intersectedGeometryType"]=projFC.getGeometryType().lower().replace("polyline","line")
            results["intersectedCount"]=count
            if intersectedQuantityAttribute:
                results["intersectedQuantity"]=total

            #collate results of intersection and intersected
            for summaryField in intersectionSummaryFields:
                summaryFieldResult={"attribute":summaryField}
                if intersectionSummaryFields[summaryField].statistics:
                    summaryFieldResult["statistics"]=intersectionSummaryFields[summaryField].getStatistics(intersectionSummaryFields[summaryField].statistics)

                else:
                    collatedResults=[]
                    intersectionResults=intersectionSummaryFields[summaryField].results
                    intersectedResults=intersectedSummaryFields[summaryField].results

                    if intersectionSummaryFields[summaryField].classes:
                        classes=intersectionSummaryFields[summaryField].classes
                        for i in range(0,len(classes)):
                            result={"class":classes[i],"intersectionCount":intersectionResults[i].count,"intersectedCount":intersectedResults[i].count}
                            if intersectionQuantityAttribute:
                                result["intersectionQuantity"]=intersectionResults[i].quantity
                            if intersectedQuantityAttribute:
                                result["intersectedQuantity"]=intersectedResults[i].quantity
                            collatedResults.append(result)
                        summaryFieldResult["classes"]=collatedResults
                    else:
                        for key in intersectionResults:#key is class or value
                            result={"value":key,"intersectionCount":intersectionResults[key].count,"intersectedCount":intersectedResults[key].count}
                            if intersectionQuantityAttribute:
                                result["intersectionQuantity"]=intersectionResults[key].quantity
                            if intersectedQuantityAttribute:
                                result["intersectedQuantity"]=intersectedResults[key].quantity
                            collatedResults.append(result)
                        summaryFieldResult["values"]=collatedResults
                results["attributes"].append(summaryFieldResult)

            del selFC
            del projFC
            del intFC
            arcpy.Delete_management("projFC")

        else:
            logger.debug("No Features intersected for this layer: %s" % (layer.name))
            results["intersectionCount"]=0
            results["intersectedCount"]=0 #no point in tallying features we don't have from intersection

    else:
        logger.debug("No Features selected for this layer: %s" % (layer.name))
        results["intersectionCount"]=0
        results["intersectedCount"]=0

    del selLyr
    return results



def tabulateMapService(srcFC,serviceID,mapServiceConfig,spatialReference,messages):
    '''
    srcFC: source feature class wrapper
    mapDocPath: path to the map document behind the map service
    mapServiceConfig: subset of config for a single map service
    spatialReference: spatial reference object with target projection
    '''

    results=[]
    mapDocPath = getMXDPathForService(serviceID)
    logger.debug("Map document for service %s: %s"%(serviceID,mapDocPath))
    mapDoc = arcpy.mapping.MapDocument(mapDocPath)
    layers = arcpy.mapping.ListLayers(mapDoc, "*", arcpy.mapping.ListDataFrames(mapDoc)[0])
    messages.setMinorSteps(len(mapServiceConfig['layers']))
    for layerConfig in mapServiceConfig['layers']:
        lyrResults = dict()
        layerID = int(layerConfig["layerID"])
        if not (layerID >= 0 and layerID < len(layers)):
            raise ValueError("LAYER_NOT_FOUND: Layer not found for layerID: %s" % (layerID))
        layer = layers[layerID]
        try:
            logger.debug("Processing layer %s: %s"%(layerID,layer.name))
            result={"layerID":layerID}
            if layer.isRasterLayer:
                result.update(tabulateRasterLayer(srcFC,layer,layerConfig,spatialReference,messages))
            elif layer.isFeatureLayer:
                result.update(tabulateFeatureLayer(srcFC,layer,layerConfig,spatialReference,messages))
            else:
                logger.error("Layer type is unsupported %s: %s"%(layerID,layer.name))
                result["error"]="unsupported layer type"
            results.append(result)
        except:
            error=traceback.format_exc()
            logger.error("Error processing layer %s: %s\n%s"%(layerID,layer.name,error))
            results.append({"layerID":layerID,"error":error})

        messages.incrementMinorStep()

    del mapDoc
    return {"serviceID":serviceID,"layers":results}


def tabulateMapServices(srcFC,config,projectionWKID,messages):
    '''
    srcFC: instance of FeatureClass wrapper with the area of interest features
    config: TODO: operate on original list of map services
    projectionWKID: ESRI WKID representing the target projection to use for all calculations (e.g., 102003, which is USA_Contiguous_Albers_Equal_Area_Conic)
    '''

    logger.debug("Temporary Workspace: %s"%(TEMP_WORKSPACE.getDirectory()))
    arcpy.env.workspace=arcpy.env.scratchWorkspace=TEMP_WORKSPACE.getGDB()

    results=dict()
    if not config.has_key("services"):
        return results

    #setup target projection
    spatialReference = arcpy.SpatialReference()
    spatialReference.factoryCode = projectionWKID
    spatialReference.create()
    arcpy.env.cartographicCoordinateSystem = spatialReference #TODO: confirm we want this set everywhere

    if not srcFC.getCount():
        raise Exception("INVALID INPUT: no features in input")

    results["area_units"]="hectares" #always
    results["linear_units"]="kilometers" #always
    results["sourceGeometryType"]=srcFC.getGeometryType().lower().replace("polyline","line")
    results["sourceFeatureCount"]=srcFC.getCount()
    if results["sourceGeometryType"] != "point":
        results["sourceFeatureQuantity"]=srcFC.getTotalAreaOrLength(spatialReference)
    results["services"]=[]

    messages.setMajorSteps(len(config["services"]))
    for mapServiceConfig in config["services"]:
        serviceID = mapServiceConfig["serviceID"]
        try:
            logger.debug("Processing map service: %s"%(serviceID))
            results["services"].append(tabulateMapService(srcFC,serviceID,mapServiceConfig,spatialReference,messages))
        except:
            error=traceback.format_exc()
            logger.error("Error processing map service: %s\n%s"%(serviceID,error))
            results["services"].append({"error":error})
        messages.incrementMajorStep()

    #TEMP_WORKSPACE.delete() #TODO: FIXME
    return results




























