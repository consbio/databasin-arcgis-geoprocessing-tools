'''
Tabulate feature or raster data using features contained in a FeatureSet

------------------------------------------------
Examples:

feature layer:
layerConfig: {"attributes":[{"attribute":"HUC_10_NM"},{"attribute":"TS_Feature_Count","classes":[[0,4],[4,6],[6,25]]},{"attribute":"Total_CE","statistics":["MIN","MAX","MEAN"]}]}

results:
{"intersectedGeometryType": "polygon", "intersectionQuantity": 2184.4220716173904, "intersectedQuantity": 163191.1489418, "intersectedCount": 5, "attributes": [{"MIN": 11, "attribute": "Total_CE", "MEAN": 11.259328347566484, "MAX": 12}, {"attribute": "TS_Feature_Count", "classes": [{"intersectedQuantity": 0, "intersectedCount": 0, "intersectionQuantity": 0, "class": [0, 4], "intersectionCount": 0}, {"intersectedQuantity": 163191.1489418, "intersectedCount": 5, "intersectionQuantity": 2184.4220716173904, "class": [4, 6], "intersectionCount": 4}, {"intersectedQuantity": 0, "intersectedCount": 0, "intersectionQuantity": 0, "class": [6, 25], "intersectionCount": 0}]}, {"attribute": "HUC_10_NM", "values": [{"intersectedQuantity": 62672.645755559286, "intersectedCount": 2, "intersectionQuantity": 565.92190886362118, "intersectionCount": 2, "value": "Ehrenberg Wash-Colorado River"}, {"intersectedQuantity": 100518.50318624072, "intersectedCount": 3, "intersectionQuantity": 1618.5001627537692, "intersectionCount": 2, "value": "Palo Verde Valley"}]}], "intersectionGeometryType": "polygon", "intersectionCount": 4}



raster layer:
layerConfig: {"attributes":[{"attribute":"LABEL"}]}

results:
{"intersectionPixelCount": 24265, "sourcePixelCount": 24265, "intersectionQuantity": 2183.8499999999999, "pixelArea": 0.089999999999999997, "geometryType": "pixel", "projectionType": "Native", "attributes": [{"attribute": "LABEL", "values": [{"count": 24030, "value": " ", "quantity": 2162.6999999999998}, {"count": 25, "value": "LANDFIRE EVT and NatureServe Landcover", "quantity": 2.25}, {"count": 5, "value": "LANDFIRE EVT", "quantity": 0.44999999999999996}, {"count": 205, "value": "NatureServe Landcover", "quantity": 18.449999999999999}]}]}

------------------------------------------------


Notes to self:
- lots of assumptions hardwired to working with web mercator as source projection for features?

TODO:
- add logging and messaging back in
- add tests
- add time support

'''



if __name__ == "__main__":
    #Make sure we're using the ArcGIS server (as opposed to the Desktop) arcpy package.
    import sys,os
    for path in filter(lambda x: os.path.normpath(x.lower()).replace("\\","/").count("arcgis/server"),sys.path):
        sys.path.insert(0, path)

import arcpy, sys, tempfile, time, traceback, shutil, json, re, copy
#import numpy #May not be needed

from utilities import FeatureSetConverter, ProjectionUtilities
import settings
from utilities.PathUtils import TemporaryWorkspace,getMXDPathForService

#Setup environment variables
arcpy.env.overwriteOutput = True

#Setup globals
TEMP_WORKSPACE=TemporaryWorkspace()

class FeatureClassWrapper:
    """
    convenience class to provide cached access to descriptive properties and projected variants of feature class
    """

    def __init__(self,featureClass):
        self.featureClass=featureClass
        self.info=arcpy.Describe(featureClass)
        self.geometryType=self.info.shapeType
        self.spatialReference=self.info.spatialReference
        self.numFeatures=int(arcpy.GetCount_management(featureClass).getOutput(0))
        self.name=os.path.split(self.featureClass)[1]
        self._prjLUT=dict()
        self._prjCache={"%s_%s" % (self.name,self._getProjID(self.spatialReference)):featureClass}

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
            projFCPath=os.path.join(TEMP_WORKSPACE.getGDB(), projKey)
            if arcpy.Exists(projFCPath):
                arcpy.Delete_management(projFCPath)
            geoTransform=ProjectionUtilities.getGeoTransform(self.spatialReference, targetSpatialReference)
            self._prjCache[projKey] = arcpy.Project_management(self.featureClass, projFCPath,targetSpatialReference,geoTransform).getOutput(0)
        return self._prjCache[projKey]

    def getquantityAttribute(self):
        if self.geometryType=="Polyline":
            return "length"
        elif self.geometryType=="Polygon":
            return "area"
        return None

    def getGeometryConversionFactor(self,targetSpatialReference):
        """
        Return area / length multiplication factor to calculate hectares / kilometers for the specified projection
        """

        if self.geometryType=="Polyline":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[0]
        elif self.geometryType=="Polygon":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[1]
        return 0

    def getTotalAreaOrLength(self,targetSpatialReference=None):
        """
        Return total area or length, if geometry type supports it, in the target projection
        """
        if not self.geometryType in ["Polygon","Polyline"]:
            return None
        if not targetSpatialReference:
            targetSpatialReference=self.spatialReference
        projFC=self.project(targetSpatialReference)
        quantityAttribute=self.getquantityAttribute()
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
        self.quantity=0
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
            if value>=classRange[0] and value<classRange[1]:
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
            fieldResults.update(self.getStatistics(self.statistics))
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


def getGridClasses(grid, field, classBreaks):
    remapClasses=[]
    for i in range(0,len(classBreaks)):
        classBreak=classBreaks[i]
        remapClasses.append([classBreak[0],classBreak[1],i])
    reclassGrid = arcpy.sa.Reclassify(grid, field, arcpy.sa.RemapRange(remapClasses), "NODATA")
    results = dict()
    rows = arcpy.SearchCursor(reclassGrid)
    for row in rows:
        results[row.getValue("Value")] = row.COUNT #value is the class index
    del row,rows
    return results




def getGridStats(grid, statisticsList):
    '''
    return SUM, MIN, MAX, etc (TODO: other names)
    '''

    results = dict()
    arcpy.CalculateStatistics_management(grid)
    for statistic in statisticsList:
        statistic = statistic.upper()
        arcGIS_statistic=statistic+"IMUM" if statistic in ["MIN","MAX"] else statistic
        results[statistic] = arcpy.GetRasterProperties_management(grid, arcGIS_statistic).getOutput(0)
    return results


def getGridCount(grid, summaryField):
    '''
    Return total count of pixels, and count by summary field if passed in
    '''

    rows = arcpy.SearchCursor(grid)
    totalCount = 0
    summary = dict()
    for row in rows:
        totalCount += row.COUNT
        if summaryField:
            summaryValue = row.getValue(summaryField)
            if not summary.has_key(summaryValue):
                summary[summaryValue] = 0
            summary[summaryValue] += row.COUNT
    del row, rows
    return totalCount, summary



def tabulateRasterLayer(srcFC,layer,layerConfig,spatialReference):
    '''
    srcFC: source feature class wrapper
    layer: layer object
    layerConfig: subset of config for a single layer
    spatialReference: spatial reference object with target projection
    '''

    arcpy.CheckOutExtension("Spatial")
    arcpy.env.snapRaster = layer.dataSource
    arcpy.env.workspace=arcpy.env.scratchWorkspace=TEMP_WORKSPACE.getDirectory()

    results=dict()

    aoiGrid = "aoiGrid"
    if arcpy.Exists(aoiGrid):
        arcpy.Delete_management(aoiGrid)

    #Convert the projected user defined feature class (projFC) to a temporary raster - which is in the same spatial reference as the target raster.
    lyrInfo = arcpy.Describe(layer.dataSource)
    projFC=srcFC.project(lyrInfo.spatialReference)
    arcpy.FeatureToRaster_conversion(projFC, arcpy.Describe(projFC).OIDFieldName, aoiGrid, lyrInfo.meanCellHeight)
    #clip the target using this grid, snapped to the original grid - watch for alignment issues in aoiGrid - snapRaster is not used there
    arcpy.env.extent=arcpy.Describe(aoiGrid).extent #this dramatically speeds up processing
    clipGrid = arcpy.sa.ExtractByMask(layer, aoiGrid)

    #Cell area is based on the projection: uses native projection of clipGrid if it is a projected system, otherwise project cell area to target spatialReference
    cellArea, projectionType = ProjectionUtilities.getCellArea(clipGrid, spatialReference)

    if lyrInfo.pixelType.count("F"):
        #force to single bit data, since we can't build attribute tables of floating point data.
        #this preserves NODATA areas from clipGrid (don't use aoiGrid for this!)
        testGrid = clipGrid != lyrInfo.noDataValue
        arcpy.BuildRasterAttributeTable_management(testGrid)
        totalCount, summaryCount = getGridCount(testGrid, None)
        del testGrid

        if layerConfig.has_key("statistics"):
            results.update({'statistics':getGridStats(clipGrid, layerConfig["statistics"])})

        elif layerConfig.has_key("classes"):
            classCounts=getGridClasses(clipGrid, "VALUE", layerConfig["classes"])
            classResults=[]
            for classIndex in range(0,len(layerConfig["classes"])):
                count=classCounts.get(classIndex,0)
                classResults.append({"class":classIndex,"count":count,"quantity":(float(count)*cellArea)})
            results.update({'classes':classResults})

    else:
        #TODO: verify this works correctly against other data sources, e.g., GeoTiff
        if layerConfig.has_key("statistics"):
            results.update({'statistics':getGridStats(clipGrid, layerConfig["statistics"])})

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
                results["attributes"]=[]

            count=0
            rows = arcpy.SearchCursor(clipGrid, "", "")
            for row in rows:
                count+=row.COUNT
                for summaryField in summaryFields:
                    summaryFields[summaryField].addRecord(row.getValue(summaryField),row.COUNT,row.COUNT*cellArea)
            del row,rows
            results["intersectionPixelCount"]=count

            if promoteValueResults:
                key = "classes" if layerConfig.has_key("classes") else "values"
                results[key]=summaryFields["VALUE"].getResults()[key]
            else:
                for summaryField in summaryFields:
                    results["attributes"].append(summaryFields[summaryField].getResults())

    results["pixelArea"] = cellArea
    results["projectionType"] = projectionType
    results["sourcePixelCount"] = getGridCount(aoiGrid, None)[0]
    results["intersectionQuantity"] = float(results["sourcePixelCount"]) * cellArea
    results["geometryType"] = "pixel"

    arcpy.CheckInExtension("Spatial")
    #delete references in this order, otherwise does not delete cleanly
    del clipGrid,aoiGrid
    arcpy.Delete_management("aoiGrid")

    return results



def tabulateFeatureLayer(srcFC,layer,layerConfig,spatialReference):
    arcpy.env.workspace = arcpy.env.scratchWorkspace = TEMP_WORKSPACE.getGDB()
    arcpy.env.cartographicCoordinateSystem = spatialReference
    arcpy.env.extent=None

    results=dict()

    #select features from layer using target projection and where clause (if provided)
    selLyr = arcpy.MakeFeatureLayer_management(layer, "selLyr", layerConfig.get("where","")).getOutput(0)

    #select by location; this is done in the projection of the target FC
    arcpy.SelectLayerByLocation_management(selLyr, "INTERSECT", srcFC.featureClass)
    featureCount = int(arcpy.GetCount_management(selLyr).getOutput(0))

    if featureCount>0:
        selFC = "IN_MEMORY/selFC"
        #Selected features must be copied into new feature class for projection step, otherwise it uses the entire dataset (lame!)
        arcpy.CopyFeatures_management(selLyr,selFC)

        #project the selection to target projection, and then intersect with source (in target projection)
        geoTransform=ProjectionUtilities.getGeoTransform(arcpy.Describe(layer.dataSource).spatialReference, spatialReference)
        projFC = FeatureClassWrapper(arcpy.Project_management(selFC, "projFC", spatialReference,geoTransform).getOutput(0))
        intFC = FeatureClassWrapper(arcpy.Intersect_analysis([srcFC.project(spatialReference), projFC.featureClass], "IN_MEMORY/" + "intFC").getOutput(0))

        featureCount = int(arcpy.GetCount_management(intFC.featureClass).getOutput(0))
        if featureCount>0:
            intersectionQuantityAttribute = intFC.getquantityAttribute()
            intersectionConversionFactor=intFC.getGeometryConversionFactor(spatialReference)
            intersectionSummaryFields=dict([(summaryField["attribute"],SummaryField(summaryField,intersectionQuantityAttribute is not None)) for summaryField in layerConfig.get("attributes",[])])

            intersectedQuantityAttribute = projFC.getquantityAttribute()
            intersectedConversionFactor=projFC.getGeometryConversionFactor(spatialReference)
            intersectedSummaryFields=copy.deepcopy(intersectionSummaryFields)

            if intersectionSummaryFields:
                fieldList = set([field.name for field in arcpy.ListFields(intFC.featureClass)])
                diffFields = set(intersectionSummaryFields.keys()).difference(fieldList)
                if diffFields:
                    raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s"%(layer.name,",".join([str(fieldName) for fieldName in diffFields])))
                results["attributes"]=[]

            #tally results for intersection
            rows = arcpy.SearchCursor(intFC.featureClass) #TODO: may want to pare this down to SHAPE and summary fields only
            total=0
            count=0
            for row in rows:
                geometryCount=1#row.shape.partCount #Note: this counts all geometries independently, is NOT number of features
                count+= geometryCount
                quantity = None
                if intersectionQuantityAttribute:
                    quantity = getattr(row.shape,intersectionQuantityAttribute) * intersectionConversionFactor
                    total+=quantity
                for summaryField in intersectionSummaryFields:
                    intersectionSummaryFields[summaryField].addRecord(row.getValue(summaryField),geometryCount,quantity)
            del row,rows

            results["intersectionGeometryType"]=intFC.geometryType.lower() if intFC.geometryType in ["Polygon","Point"] else "line"
            results["intersectionCount"]=count
            if intersectionQuantityAttribute:
                results["intersectionQuantity"]=total

            #tally results for intersected features
            rows = arcpy.SearchCursor(projFC.featureClass)
            total=0
            count=0
            for row in rows:
                geometryCount=row.shape.partCount
                count+= geometryCount
                quantity = None
                if intersectedQuantityAttribute:
                    quantity = getattr(row.shape,intersectedQuantityAttribute) * intersectedConversionFactor
                    total+=quantity
                for summaryField in intersectedSummaryFields:
                    intersectedSummaryFields[summaryField].addRecord(row.getValue(summaryField),geometryCount,quantity)
            del row,rows

            results["intersectedGeometryType"]=projFC.geometryType.lower().replace("polyline","line")
            results["intersectedCount"]=count
            if intersectedQuantityAttribute:
                results["intersectedQuantity"]=total

            #collate results of intersection and intersected
            for summaryField in intersectionSummaryFields:
                summaryFieldResult={"attribute":summaryField}
                if intersectionSummaryFields[summaryField].statistics:
                    summaryFieldResult.update(intersectionSummaryFields[summaryField].getStatistics(intersectionSummaryFields[summaryField].statistics))

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
            print "No features intersected for this layer: %s"%(layer.name)
            results["intersectionFeatureCount"]=0
            results["intersectedFeatureCount"]=0 #no point in tallying features we don't have from intersection

        return results

    else:
        #TODO
        print "No Features selected for this layer: %s"%(layer.name)
        #messages.addMessage("No Features selected for this layer: %s" % (lyr.name))
        results["intersectedFeatureCount"]=0


    del selLyr


def tabulateMapService(srcFC,serviceID,mapServiceConfig,spatialReference):
    '''
    srcFC: source feature class wrapper
    mapDocPath: path to the map document behind the map service
    mapServiceConfig: subset of config for a single map service
    spatialReference: spatial reference object with target projection
    '''

    results=[]
    mapDocPath = getMXDPathForService(serviceID)
    mapDoc = arcpy.mapping.MapDocument(mapDocPath)
    layers = arcpy.mapping.ListLayers(mapDoc, "*", arcpy.mapping.ListDataFrames(mapDoc)[0])
    for layerConfig in mapServiceConfig['layers']:
        lyrResults = dict()
        layerID = int(layerConfig["layerID"])
        if not (layerID >= 0 and layerID < len(layers)):
            raise ValueError("LAYER_NOT_FOUND: Layer not found for layerID: %s" % (layerID))
        layer = layers[layerID]
        try:
            result={"layerID":layerID}
            if layer.isRasterLayer:
                result.update(tabulateRasterLayer(srcFC,layer,layerConfig,spatialReference))
            elif layer.isFeatureLayer:
                result.update(tabulateFeatureLayer(srcFC,layer,layerConfig,spatialReference))
            else:
                result["error"]="unsupported layer type"
            results.append(result)
        except:
            #TODO: log this
            results.append({"layerID":layerID,"error":traceback.format_exc()})

    del mapDoc
    return {"serviceID":serviceID,"layers":results}


def tabulateMapServices(srcFC,config,projectionWKID):
    '''
    srcFC: instance of FeatureClass wrapper with the area of interest features
    config: TODO: operate on original list of map services
    projectionWKID: ESRI WKID representing the target projection to use for all calculations (e.g., 102003, which is USA_Contiguous_Albers_Equal_Area_Conic)
    '''

    results=dict()
    if not config.has_key("services"):
        return results

    #setup target projection
    spatialReference = arcpy.SpatialReference()
    spatialReference.factoryCode = projectionWKID
    spatialReference.create()
    arcpy.env.cartographicCoordinateSystem = spatialReference #TODO: confirm we want this set everywhere

    if not srcFC.numFeatures:
        raise Exception("INVALID INPUT: no features in input")

    results["units"]="hectares" #always
    results["sourceGeometryType"]=srcFC.geometryType.lower().replace("polyline","line")
    results["sourceFeatureCount"]=srcFC.numFeatures
    if srcFC.geometryType in ["Polygon","Polyline"]:
        results["sourceFeatureQuantity"]=srcFC.getTotalAreaOrLength(spatialReference)
    results["services"]=[]

    for mapServiceConfig in config["services"]:
        serviceID = mapServiceConfig["serviceID"]
        try:

           results["services"].append(tabulateMapService(srcFC,serviceID,mapServiceConfig,spatialReference))
        except:
            #TODO: log error
            error=traceback.format_exc()
            results["services"].append({"error":error})

    TEMP_WORKSPACE.delete()
    return results


#Testing
if __name__=="__main__":
    start=time.time()

    # spatialReference = arcpy.SpatialReference()
    # spatialReference.factoryCode = 102003
    # spatialReference.create()

    #featureSetJSON='''{"displayFieldName":"","geometryType":"esriGeometryPolygon","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"},{"name":"SHAPE_Area","type":"esriFieldTypeDouble","alias":"SHAPE_Area"}],"features":[{"attributes":{"OBJECTID":1,"SHAPE_Length":903.47742081348633,"SHAPE_Area":52657.151961896809},"geometry":{"rings":[[[-12749182.316300001,3983403.194600001],[-12749009.746399999,3983330.2292999998],[-12749032.203200001,3983190.6643000022],[-12749208.489700001,3983156.1856999993],[-12749348.539999999,3983246.1792000011],[-12749182.316300001,3983403.194600001]]]}}]}'''
    featureSetJSON='''{"displayFieldName":"","geometryType":"esriGeometryPolygon","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"},{"name":"SHAPE_Area","type":"esriFieldTypeDouble","alias":"SHAPE_Area"}],"features":[{"attributes":{"OBJECTID":1,"SHAPE_Length":23286.161534325816,"SHAPE_Area":31607836.704571243},"geometry":{"rings":[[[-12754420.4892,3983627.7704000026],[-12753544.328499999,3985117.1664000005],[-12752845.3035,3985796.7431000024],[-12751042.6261,3986175.6309999973],[-12750311.6776,3985388.565700002],[-12750241.625799999,3985298.930399999],[-12750003.2579,3984234.6823000014],[-12750140.830600001,3983355.2833999991],[-12750478.8661,3982565.8571000025],[-12750655.4538,3982143.8426000029],[-12750676.4888,3981726.4562000036],[-12750788.282499999,3981110.5216000006],[-12750739.5836,3980474.3769999966],[-12751519.452399999,3979443.4860000014],[-12751501.209899999,3979392.0658000037],[-12752286.2476,3979732.4545999989],[-12752908.5514,3979584.6982000023],[-12753686.6029,3979303.0693000033],[-12754062.682700001,3979358.4636999965],[-12754719.2163,3979642.9319999963],[-12755631.4169,3980032.1739000008],[-12756002.561799999,3980062.6503999978],[-12757401.512499999,3980407.8849999979],[-12757652.2004,3980487.795599997],[-12756967.1229,3982146.3825000003],[-12754420.4892,3983627.7704000026]]]}}]}'''
    # srcFC = FeatureClassWrapper(FeatureSetConverter.createFeatureClass(featureSetJSON))

    # results=dict()
    # results["units"]="hectares" #always
    # results["sourceGeometryType"]=srcFC.geometryType.lower().replace("polyline","line")
    # results["sourceFeatureCount"]=srcFC.numFeatures
    # if srcFC.geometryType in ["Polygon","Polyline"]:
    #     results["sourceFeatureQuantity"]=srcFC.getTotalAreaOrLength(spatialReference)


    #layer=arcpy.mapping.Layer(r"D:\BLM_REA\Final_Deliverable\SOD_2011\Raster\Change_Agents\Invasives\Inv_Current\sod_iv_c_rip")
    #layer=arcpy.mapping.Layer(r"D:\BLM_REA\Final_Deliverable\SOD_2011\Raster\Change_Agents\Invasives\Inv_Current\sod_iv23064in")
    #raster=arcpy.mapping.Layer(r"D:\BLM_REA\Final_Deliverable\SOD_2011\Raster\Conservation_Elements\Terrestrial\Ecosystem\sod_c_smc_mg")
    #layerConfig=json.loads('''{"statistics":["MIN","MAX","MEAN"],"classes":[[0,1],[1,2],[2,3]]}''')
    #layerConfig=json.loads('''{"statistics":["MIN","MAX","MEAN"],"classes":[[0,0.001],[0.001,0.25],[0.25,1]]}''')
    #rasterLayerConfig=json.loads('''{"attributes":[{"attribute":"LABEL"}]}''')
    #layerConfig=json.loads('''{"classes":[[0,1],[1,2]]}''')

    #fc=arcpy.mapping.Layer(r"D:\BLM_REA\Final_Deliverable\SOD_2011\Vector\Conservation_Elements\Ecological_Integrity\SOD_EI_HUC5.gdb\SOD_EI_HUC5_poly")
    #fcLayerConfig = json.loads('''{"attributes":[{"attribute":"HUC_10_NM"},{"attribute":"TS_Feature_Count","classes":[[0,4],[4,6],[6,25]]},{"attribute":"Total_CE","statistics":["MIN","MAX","MEAN"]}]}''')

    #print results
    #print json.dumps(tabulateRasterLayer(srcFC,raster,rasterLayerConfig,spatialReference))
    #print json.dumps(tabulateFeatureLayer(srcFC,fc,fcLayerConfig,spatialReference))


    srcFC = FeatureClassWrapper(FeatureSetConverter.createFeatureClass(featureSetJSON))
    config=json.loads('''{"services":[{"serviceID":"smc","layers":[{"layerID":2,"attributes":[{"attribute":"STATE_NAME"}]},{"layerID":6},{"layerID":7,"attributes":[{"attribute":"LABEL"}]}]}]}''')# ##
    results = tabulateMapServices(srcFC,config,102003)
    print json.dumps(results,indent=1)
    outfile=open("c:/temp/results.json",'w')
    outfile.write(json.dumps(results,indent=1))
    outfile.close()

    #del srcFC
    #TEMP_WORKSPACE.delete()
    print "elapsed: %.2f"%(time.time()-start)





























