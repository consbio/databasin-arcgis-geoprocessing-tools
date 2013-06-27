"""
General utilities for helping deal with projection related information
"""

import re,arcpy,os
import settings



def getGCS(spatialReference):
    """
    Return the geographic coordinate system name for the spatial reference (e.g., GCS_North_American_1983).

    :param spatialReference: ArcGIS spatial reference object
    """
    wkt=spatialReference.exportToString()
    gcsMatch=re.search("(?<=GEOGCS\[').*?(?=')",wkt)
    if not gcsMatch:
        raise Exception("GCS_NOT_SUPPORTED: valid GCS not found in WKT: %s"%(wkt))
    return gcsMatch.group()    


def getProjUnitFactors(spatialReference):
    """
    Return the conversion factors for projection length to kilometers, projection area to hectares, and meters per projection unit for the spatial reference.
    Used to multiply the length and area calculated for features.

    :param spatialReference: ArcGIS spatial reference object

    .. note:: Limited to projections based on Meter and Foot_US
    """

    factors={
        "Meter":[0.001,0.0001,1],
        "Foot_US": [0.0003048,0.00003048,0.3048]
    }
    unit=spatialReference.linearUnitName
    if not factors.has_key(unit):
        raise Exception("UNITS_NOT_SUPPORTED: units not implemented for %s"%(unit))
    return factors[unit]


def getWGS84GeoTransform(gcs):
    """
    Find a general geographic transformation from one coordinate system to WGS 1984.  These transformations are based on the
    continent scale transformations listed by ESRI, and are not exact for local calculations.  Only the following source
    geographic coordinate systems are currently supported:

    * NAD 1983
    * NAD 1983 HARN
    * NAD 1983 CRS
    * SAD 1969
    * ED 1950

    :param gcs: the input geographic coordinate system name extracted from the source projection well-known text

    .. note:: Target geographic coordinate system is always WGS 1984
    """

    #lookup table of bidirectional transforms to WGS84, chained if necessary (may need to invert order of chaining);
    # semicolon delimited within chain
    #Note: these are approximate transformations, not locally ideal
    gcs_transform_WGS84={
        "GCS_North_American_1983":"NAD_1983_To_WGS_1984_1",
        "GCS_North_American_1983_CSRS":"NAD_1983_CSRS_To_WGS_1984_2",
        "GCS_South_American_1969":"SAD_1969_To_WGS_1984_1",
        "GCS_European_1950":"ED_1950_To_WGS_1984_1",
        "GCS_North_American_1983_HARN":"NAD_1983_To_WGS_1984_1",
        "GCS_WGS_1984_Major_Auxiliary_Sphere":"WGS_1984_Major_Auxiliary_Sphere_To_WGS_1984"
    }

    #if already based on WGS84, no transform required
    if gcs=="GCS_WGS_1984":
        return None
    elif gcs_transform_WGS84.has_key(gcs):
        return gcs_transform_WGS84[gcs]
    else:
        raise Exception("GCS_NOT_SUPPORTED: Geographic Transformation to WGS84 not found for projection with GCS: %s"%(gcs)) 



def getGeoTransform(srcSR,targetSR):
    """
    Return the geographic transformation required to project between two projections (passing through WGS 1984, if
    required), or empty string if not required.

    :param srcSR: source ArcGIS spatial reference object
    :param targetSR: target ArcGIS spatial reference object

    .. note:: limited to the geographic coordinate systems supported by getWGS84GeoTransform
    """

    if srcSR.factoryCode and srcSR.factoryCode==targetSR.factoryCode:
        return ""

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
    """
    Project the extent to the target spatial reference, and return the projected extent.  Creates a temporary feature
    class based on bounding box of source.

    :param extent: source extent
    :param tempGDB: temporary geodatabase to contain the projected feature class
    :param srcSR: source ArcGIS spatial reference object
    :param targetSR: target ArcGIS spatial reference object
    """
    array=arcpy.Array()
    array.add(arcpy.Point(extent.XMin,extent.YMin))
    array.add(arcpy.Point(extent.XMax,extent.YMax))
    fc=arcpy.Multipoint(array,srcSR)
    projFC=arcpy.Project_management(fc,os.path.join(tempGDB,"tempProj"),targetSR,getGeoTransform(srcSR,targetSR),srcSR).getOutput(0)
    return arcpy.Describe(projFC).extent


def getCellArea(grid,targetSR):
    """
    Returns the area (in hectares) of a grid cell.  If the grid is in a projection, use that projection to derive the
    area, assuming that it is the most accurate projection for the data.  If the grid is not projected (is geographic),
    this creates an extent polygon from the extent of the raster, projects that to the target projection, and divides it
    by the number of rows and columns in the grid to calculate the area.

    :param grid: grid to calculate cell area
    :param targetSR: target ArcGIS spatial reference object (only used if grid is not projected)
    """
    info=arcpy.Describe(grid)
    if info.spatialReference.type!="Projected":
        #project bounding box to targetProj
        print "Projecting bounding box to target projection"
        projExtent=projectExtent(info.extent,settings.TEMP_GDB,info.spatialReference,targetSR)
        xSize=(projExtent.XMax-projExtent.XMin)/float(info.width)
        ySize=(projExtent.YMax-projExtent.YMin)/float(info.height)
        areaFactor=getProjUnitFactors(targetSR)[1]
        cellArea=round(xSize*ySize*areaFactor,4)
        projType="target"
        print xSize,ySize,areaFactor,cellArea
    else:
        #use the native projection; assume it is the most correct for the dataset
        areaFactor=getProjUnitFactors(info.spatialReference)[1]
        cellArea=round(info.meanCellHeight*info.meanCellWidth * areaFactor,4)
        projType="native"
    return cellArea,projType
