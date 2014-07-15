import arcpy
import os
import logging
from utilities import ProjectionUtilities
from utilities.PathUtils import get_scratch_GDB


logger = logging.getLogger(__name__)


class FeatureClassWrapper:
    """
    convenience class to provide cached access to descriptive properties and projected variants of feature class
    """

    def __init__(self, featureClass):
        self.featureClass = featureClass
        self.name = os.path.split(self.featureClass)[1]
        #internal attributes, only fetch as necessary since initial lookup time may be slow
        self._info = None
        self._geometryType = None
        self._spatialReference = None
        self._numFeatures = None
        self._prjLUT = dict()
        self._prjCache = dict()
        self._extentPrjCache = dict()

    def getCount(self):
        if self._numFeatures is None:
            self._numFeatures = int(arcpy.GetCount_management(self.featureClass).getOutput(0))
        return self._numFeatures

    #Can also get from cursor - what do we get first?
    def getGeometryType(self):
        if self._geometryType is None:
            self._geometryType = self._getInfo().shapeType
        return self._geometryType

    def getSpatialReference(self):
        if self._spatialReference is None:
            self._spatialReference = self._getInfo().spatialReference
        return self._spatialReference

    def getExtent(self, targetSpatialReference=None, projectFeaturesFirst=False):
        if targetSpatialReference is None:
            return self._getInfo().extent
        projKey = self._getProjID(targetSpatialReference)
        if not self._extentPrjCache.has_key(projKey):
            #cache existing
            projectionKey = "%s_%s" % (self.name, projKey)
            if self._prjCache.has_key(projectionKey):
                #use previously projected version
                self._extentPrjCache[projKey] = arcpy.mapping.Layer(self._prjCache[projectionKey]).getExtent()
            elif projectFeaturesFirst:
                self.project(targetSpatialReference)
                self._extentPrjCache[projKey] = arcpy.mapping.Layer(self._prjCache[projectionKey]).getExtent()
            else:
                self._extentPrjCache[projKey] = ProjectionUtilities.projectExtent(self._getInfo().extent,
                                                                                  self.getSpatialReference(),
                                                                                  targetSpatialReference)
        return self._extentPrjCache[projKey]


    def _getInfo(self):
        if self._info is None:
            self._info = arcpy.Describe(self.featureClass)
        return self._info

    def _getProjID(self, spatialReference):
        key = spatialReference.factoryCode
        if not key:
            key = "hash%s" % (hash(spatialReference.exportToString()))
        if not self._prjLUT.has_key(key):
            self._prjLUT[key] = len(self._prjLUT.keys())
        return self._prjLUT[key]

    def project(self, targetSpatialReference):
        projKey = "%s_%s" % (self.name, self._getProjID(targetSpatialReference))

        if not self._prjCache.has_key(projKey):
            fcPath = str(self.featureClass)
            if fcPath.count("IN_MEMORY/"):  #need to persist or it will fail during projection steps
                logger.debug("Persisting feature class to temporary geodatabase")
                newFCPath = os.path.normpath(fcPath.replace("IN_MEMORY", get_scratch_GDB()))
                if arcpy.Exists(newFCPath):
                    arcpy.Delete_management(newFCPath)
                arcpy.CopyFeatures_management(self.featureClass, newFCPath)
                self.featureClass = newFCPath

            if not self._prjCache:
                #cache current projection
                existingPrjKey = "%s_%s" % (self.name, self._getProjID(self.getSpatialReference()))
                self._prjCache[existingPrjKey] = self.featureClass
                if projKey == existingPrjKey:
                    return self.featureClass

            projFCPath = os.path.join(get_scratch_GDB(), projKey)
            if arcpy.Exists(projFCPath):
                arcpy.Delete_management(projFCPath)
            geoTransform = ProjectionUtilities.getGeoTransform(self.getSpatialReference(), targetSpatialReference)
            logger.debug(
                "Projecting %s to %s using transform %s" % (self.name, targetSpatialReference.name, geoTransform))
            self._prjCache[projKey] = arcpy.Project_management(self.featureClass, projFCPath, targetSpatialReference,
                                                               geoTransform).getOutput(0)
        return self._prjCache[projKey]

    def getQuantityAttribute(self):
        if self.getGeometryType() == "Polyline":
            return "length"
        elif self.getGeometryType() == "Polygon":
            return "area"
        return None

    def getGeometryConversionFactor(self, targetSpatialReference):
        """
        Return area / length multiplication factor to calculate hectares / kilometers for the specified projection
        """

        if self.getGeometryType() == "Polyline":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[0]
        elif self.getGeometryType() == "Polygon":
            return ProjectionUtilities.getProjUnitFactors(targetSpatialReference)[1]
        return 0

    def getTotalAreaOrLength(self, targetSpatialReference=None):
        """
        Return total area or length, if geometry type supports it, in the target projection
        """
        if not self.getGeometryType() in ["Polygon", "Polyline"]:
            return None
        if not targetSpatialReference:
            targetSpatialReference = self.getSpatialReference()
        projFC = self.project(targetSpatialReference)
        quantityAttribute = self.getQuantityAttribute()
        rows = arcpy.SearchCursor(projFC)
        total = sum([getattr(row.shape, quantityAttribute) for row in rows]) * self.getGeometryConversionFactor(
            targetSpatialReference)
        del rows
        return total