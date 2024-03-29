"""
General utilities for helping deal with projection related information
"""

import re
import os
import arcpy
from tool_exceptions import GPToolError

# Names of projections that can be used for area calculations
VALID_AREA_PROJECTION_NAMES = ("Albers", "Transverse_Mercator", "Lambert_Azimuthal_Equal_Area")


def getGCS(spatialReference):
    """
    Return the geographic coordinate system name for the spatial reference (e.g., GCS_North_American_1983).

    :param spatialReference: ArcGIS spatial reference object
    """
    wkt=spatialReference.exportToString()
    gcsMatch=re.search("(?<=GEOGCS\[').*?(?=')",wkt)
    if not gcsMatch:
        raise GPToolError("GCS_NOT_SUPPORTED: valid GCS not found in WKT: %s"%(wkt))
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
        raise GPToolError("UNITS_NOT_SUPPORTED: units not implemented for %s"%(unit))
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
        raise GPToolError("GCS_NOT_SUPPORTED: Geographic Transformation to WGS84 not found for projection with GCS: %s"%(gcs))



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


def projectExtent(extent,srcSR,targetSR):
    """
    Project the extent to the target spatial reference, and return the projected extent.  Creates a temporary feature
    class based on bounding box of source.

    :param extent: source extent
    :param srcSR: source ArcGIS spatial reference object
    :param targetSR: target ArcGIS spatial reference object
    """

    array=arcpy.Array()
    array.add(arcpy.Point(extent.XMin,extent.YMin))
    array.add(arcpy.Point(extent.XMin,extent.YMax))
    array.add(arcpy.Point(extent.XMax,extent.YMin))
    array.add(arcpy.Point(extent.XMax,extent.YMax))
    fc=arcpy.Multipoint(array,srcSR)
    projFC=arcpy.Project_management(fc, os.path.join(arcpy.env.scratchWorkspace, "scratch.gdb","tempProj"),
                                    targetSR,getGeoTransform(srcSR,targetSR),srcSR).getOutput(0)
    extent = arcpy.mapping.Layer(projFC).getExtent()
    arcpy.Delete_management(projFC)
    return extent


def createCustomAlbers(extent):
    """
    Given an extent in geographic coordinates, create a custom Albers projection centered over the extent that minimizes
    area distortions.  Uses 1/6 inset from YMin and YMax to define latitude bounds, and centerline between XMin and XMax
    to define central meridian.

    :param extent: extent in geographic coordinates
    :return: custom Albers spatial reference
    """

    spatialReference=arcpy.SpatialReference()
    centralMeridian=((extent.XMax-extent.XMin)/2.0) + extent.XMin
    inset=(extent.YMax - extent.YMin) / 6.0
    lat1=extent.YMin + inset
    lat2=extent.YMax - inset
    assert centralMeridian>-180 and centralMeridian<180 and lat1>-90 and lat1<90 and lat2>-90 and lat2<90
    spatialReference.loadFromString(u"PROJCS['Custom_Albers_WGS84',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Albers'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',%.1f],PARAMETER['Standard_Parallel_1',%.1f],PARAMETER['Standard_Parallel_2',%.1f],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]];-22505900 -5535700 200107510.802523;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision"%(centralMeridian,lat1,lat2))
    return spatialReference


def getSpatialReferenceFromWKID(WKID):
    """
    Returns a spatial reference object for WKID

    :param WKID: ESRI Well Known ID
    :return: spatial reference object
    """
    spatialReference=arcpy.SpatialReference()
    spatialReference.factoryCode=4326
    spatialReference.create()
    return spatialReference


def isValidAreaProjection(spatialReference):
    """
    Determines if projection is valid for area calculations.

    :param spatialReference: spatial reference object
    :return: True if valid for area projections, False otherwise
    """

    return spatialReference.projectionName in VALID_AREA_PROJECTION_NAMES