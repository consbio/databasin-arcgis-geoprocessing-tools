import re,arcpy,os
import settings


#lookup table of bidirectional transforms to WGS84, chained if necessary (may need to invert order of chaining); semicolon delimited within chain
#Note: these are approximate transformations, not locally ideal
GCS_TRANSFORM_WGS84=dict()
GCS_TRANSFORM_WGS84["GCS_North_American_1983"]="NAD_1983_To_WGS_1984_1"
GCS_TRANSFORM_WGS84["GCS_North_American_1983_CSRS"]="NAD_1983_CSRS_To_WGS_1984_2"
GCS_TRANSFORM_WGS84["GCS_South_American_1969"]="SAD_1969_To_WGS_1984_1"
GCS_TRANSFORM_WGS84["GCS_European_1950"]="ED_1950_To_WGS_1984_1"
GCS_TRANSFORM_WGS84["GCS_North_American_1983_HARN"]="NAD_1983_To_WGS_1984_1"
GCS_TRANSFORM_WGS84["GCS_WGS_1984_Major_Auxiliary_Sphere"]="WGS_1984_Major_Auxiliary_Sphere_To_WGS_1984"

#provide length,area,meters per projection unit conversion factors to kilometers,hectares for a projection based on following units
#used to multiply length,area calculated from features
PROJ_UNIT_FACTORS=dict()
PROJ_UNIT_FACTORS["Meter"]=[0.001,0.0001,1]
PROJ_UNIT_FACTORS["Foot_US"]=[0.0003048,0.00003048,0.3048]


def getGCS(spatialReference):
    wkt=spatialReference.exportToString()
    gcsMatch=re.search("(?<=GEOGCS\[').*?(?=')",wkt)
    if not gcsMatch:
        raise Exception("GCS_NOT_SUPPORTED: valid GCS not found in WKT: %s"%(wkt))
    return gcsMatch.group()    

def getProjUnitFactors(spatialReference):
    unit=spatialReference.linearUnitName
    if not PROJ_UNIT_FACTORS.has_key(unit):
        raise Exception("UNITS_NOT_SUPPORTED: units not implemented for %s"%(unit))
    return  PROJ_UNIT_FACTORS[unit]

def getWGS84GeoTransform(gcs):
    #if already based on WGS84, no transform required
    if gcs=="GCS_WGS_1984":
        return None
    elif GCS_TRANSFORM_WGS84.has_key(gcs):
        return GCS_TRANSFORM_WGS84[gcs]
    else:
        raise Exception("GCS_NOT_SUPPORTED: Geographic Transformation to WGS84 not found for projection with GCS: %s"%(gcs)) 

def getGeoTransform(srcSR,targetSR):
    srcGCS=getGCS(srcSR)
    targetGCS=getGCS(targetSR)
    if srcGCS==targetGCS:
        return ""
    
    srcGT=getWGS84GeoTransform(srcGCS)
    targetGT=getWGS84GeoTransform(targetGCS)
    
    if srcGT and targetGT:
        return "%s;%s"%(srcGT,targetGT)
    elif srcGT:
        return srcGT
    elif targetGT:
        return targetGT
    else:
        return ""

def projectExtent(extent,tempGDB,srcSR,targetSR):
    array=arcpy.Array()
    array.add(arcpy.Point(extent.XMin,extent.YMin))
    array.add(arcpy.Point(extent.XMax,extent.YMax))
    fc=arcpy.Multipoint(array,srcSR)
    
    #Error: NameError: global name 'ProjectionUtilities' is not defined
    #projFC=arcpy.Project_management(fc,os.path.join(tempGDB,"tempProj"),targetSR,ProjectionUtilities.getGeoTransform(srcSR,targetSR),srcSR).getOutput(0)
    
    projFC=arcpy.Project_management(fc,os.path.join(tempGDB,"tempProj"),targetSR,getGeoTransform(srcSR,targetSR),srcSR).getOutput(0)
    
    return arcpy.Describe(projFC).extent


#TODO: revisit this - using the original projection may not be the most appropriate in all cases (e.g., Web Mercator!)
#TODO: may have already pulled out info - don't do it again
def getCellArea(grid,targetSR):
    info=arcpy.Describe(grid)
    if info.spatialReference.type!="Projected":
        #project bounding box to targetProj
        print "Projecting bounding box to target projection"
        projExtent=projectExtent(info.extent,settings.TEMP_GDB,info.spatialReference,targetSR)
        xSize=(projExtent.XMax-projExtent.XMin)/float(info.width)
        ySize=(projExtent.YMax-projExtent.YMin)/float(info.height)
        areaFactor=getProjUnitFactors(targetSR)[1]
        cellArea=round(xSize*ySize*areaFactor,4)
        projType="Target"
        print xSize,ySize,areaFactor,cellArea
    else:
        #use the native projection; assume it is the most correct for the dataset
        areaFactor=getProjUnitFactors(info.spatialReference)[1]
        cellArea=round(info.meanCellHeight*info.meanCellWidth * areaFactor,4)
        projType="Native"
    return cellArea,projType
