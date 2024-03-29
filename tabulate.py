"""
Tabulate feature or raster data using features contained in a FeatureSet

See test_tabulate for example usage.

TODO:
- add time support
check out recipe at: http://arcpy.wordpress.com/2012/07/02/retrieving-total-counts/ for counter example

TODOC:
- changed return values for raster
- area weighted stuff
- custom albers projection

"""

import os
import time
import traceback
import copy
import logging

import numpy
import arcpy

from utilities import ProjectionUtilities
from utilities.feature_class_wrapper import FeatureClassWrapper
from utilities.PathUtils import getDataPathsForService, get_scratch_GDB
from messaging import MessageHandler
from tool_exceptions import GPToolError

logger = logging.getLogger(__name__)

#Setup environment variables
arcpy.env.overwriteOutput = True
arcpy.env.pyramid = "NONE"
arcpy.env.rasterStatistics = "NONE"  #we will calculate these manually as required


class SummaryResult:
    """
    convenience class wrapper of a summary record
    """

    def __init__(self):
        self.count = 0
        self.quantity = 0  #quantity is area / length if applicable

    def update(self, count, quantity=0):
        self.count += count
        self.quantity += quantity


class SummaryField:
    """
    convenience class wrapper of an attribute used for summarization of attribute values by unique, classes, or statistics
    """

    def __init__(self, fieldJSON, hasGeometry=False):
        self.attribute = fieldJSON["attribute"]
        self.classes = fieldJSON.get("classes", [])
        self.statistics = fieldJSON.get("statistics", [])
        self.results = dict()
        self._classRanges = []
        for i in range(0, len(self.classes)):
            classRange = self.classes[i]
            self._classRanges.append((float(classRange[0]), float(classRange[1])))
            self.results[i] = SummaryResult()

        self.hasGeometry = hasGeometry

    def addRecord(self, value, count, quantity=0):  #quantity: area or length
        key = None
        if self.classes:
            key = self.getClass(value)
        else:
            key = value
        if key is not None:
            if not self.results.has_key(key):
                self.results[key] = SummaryResult()
            self.results[key].update(count, quantity)

    def getClass(self, value):
        #>=lower value and <upper
        for classIndex in range(0, len(self._classRanges)):
            classRange = self._classRanges[classIndex]
            if value >= classRange[0] and value < classRange[1]:
                return classIndex
        return None

    def getStatistics(self, statisticsList):
        statistics = dict()
        statisticAttribute = "count"
        if self.hasGeometry:
            statisticAttribute = "quantity"
        values_present = self.results.keys()
        for statistic in statisticsList:
            statisticName = statistic.upper()
            if statisticName == "SUM":
                #sum = count * value for each entry in results
                statistics[statistic] = sum([(self.results[key].count * key) for key in values_present])
            elif statisticName == "MIN":
                statistics[statistic] = min(values_present)
            elif statisticName == "MAX":
                statistics[statistic] = max(values_present)
            elif statisticName == "MEAN":
                #area/length/count weighted average
                total = float(sum([getattr(result, statisticAttribute) for result in self.results.values()]))
                if total:
                    statistics[statistic] = sum(
                        map(
                            lambda value: value * (float(getattr(self.results[value], statisticAttribute)) / total),
                            self.results
                        )
                    )
                else:
                    statistics[statistic] = None
            elif statisticName == "STD":
                #regular standard deviation, not weighted
                statistics[statistic] = float(numpy.std(values_present))

        return statistics

    def getResults(self):
        fieldResults = {'attribute': self.attribute}
        if self.statistics:
            fieldResults["statistics"] = self.getStatistics(self.statistics)
        elif self.classes:
            classResults = []
            for i in range(0, len(self.classes)):
                classResult = {
                    'class': self.classes[i],
                    'intersectionCount': self.results[i].count
                }
                if self.hasGeometry:
                    classResult["intersectionQuantity"] = self.results[i].quantity
                classResults.append(classResult)
            fieldResults.update({'classes': classResults})
        else:
            valueResults = []
            keys = self.results.keys()
            keys.sort()
            for key in keys:
                valueResult = {
                    'value': key,
                    'intersectionCount': self.results[key].count
                }
                if self.hasGeometry:
                    valueResult["intersectionQuantity"] = self.results[key].quantity
                valueResults.append(valueResult)
            fieldResults.update({'values': valueResults})
        return fieldResults



def getGridClasses(grid, field, classBreaks):
    remapClasses = []
    for i in range(0, len(classBreaks)):
        classBreak = classBreaks[i]
        #this translates to greater than or equal to lower bound and less than upper bound
        remapClasses.append([classBreak[0], float(classBreak[1]) - 0.0000001, i])

    arcpy.CalculateStatistics_management(grid)
    reclassGrid = arcpy.sa.Reclassify(grid, field, arcpy.sa.RemapRange(remapClasses), "NODATA")
    results = dict()
    rows = arcpy.SearchCursor(reclassGrid)
    for row in rows:
        results[row.getValue("Value")] = row.COUNT  #value is the class index
    del row, rows, reclassGrid
    return results


def getNumpyValueQuantities(values, quantities):
    """
    Tallys the quantities for each unique value found in values based on the amount within each pixel

    :param values:  pixel values
    :param quantities: quantities measured for each pixel
    :return: dictionary mapping value to count and quantity
    """

    flat_values = values.ravel()
    flat_quantities = quantities.ravel()
    results = dict()
    if str(flat_values.dtype).count("ui") or flat_values.min() > 0:
        logger.debug("Tallying unique values using bincount method")
        # Bincount is preferred, performant method but only works for positive integers
        if flat_values.mask.shape:
            # Remove masked values or they get into calculation
            valid = flat_values.mask == False
            flat_values = flat_values[valid]
            flat_quantities = flat_quantities[valid]

        b_quantity = numpy.bincount(flat_values, weights=flat_quantities)
        b_count = numpy.bincount(flat_values)
        nonzero_indices = numpy.flatnonzero(b_count)
        tally = numpy.vstack((nonzero_indices, b_count[nonzero_indices], b_quantity[nonzero_indices])).T
        for result in tally:
            results[int(result[0])] = {
                'intersectionCount': int(result[1]),
                'intersectionQuantity': float(result[2])
            }
    else:
        logger.debug("Tallying unique values using looping method")
        unique = numpy.ma.unique(flat_values)
        for value in unique[unique.mask == False]:
            equals_value = flat_values == value
            results[value] = {
                'intersectionCount': numpy.ma.sum(equals_value),
                'intersectionQuantity': numpy.ma.sum(flat_quantities[equals_value])
            }
    return results


def getNumpyClassQuantities(values, quantities, classBreaks):
    """
    Tally quantities by class, using quantities within each pixel.  Classes are tested on greater than or equal to lower
    value and less than upper value.

    :param values:  pixel values
    :param quantities: quantities measured for each pixel
    :param classBreaks:
    :return: list with dictionary objects of class range, count, and quantity
    """

    import numpy

    class_results = []
    for i in range(0, len(classBreaks)):
        class_range = classBreaks[i]
        in_class = numpy.logical_and(values >= float(class_range[0]), values < float(class_range[1]))
        class_results.append({
            'class': class_range,
            'intersectionCount': int(in_class.sum()),
            'intersectedQuantity': (in_class * quantities).sum()
        })
    return class_results


def FishnetOIDToNumpy(OID, rows, cols):
    """
    Return the row and column in grid coordinates that correspond to the given OID
    Fishnet numbers start at 1, in bottom left corner, and go columnwise from there.
    Grid coordinates start at 0, and start in upper left
    """
    row, col = divmod(OID - 1, cols)
    row = (rows - 1) - row  #invert row order
    return row, col


#TODO: use python Counter class when supported
def getGridCount(grid, summaryField):
    """
    Return total count of pixels, and count by summary field if passed in
    """

    totalCount = 0
    summary = dict()
    try:
        #this will fail if there is no attribute table (e.g., all pixels are NODATA)
        rows = arcpy.SearchCursor(grid)
        for row in rows:
            count = int(row.COUNT)
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


def getGridValueField(grid):
    """
    Return value field name for grid, because case changes based on format

    :param grid: input grid
    :return: name of value field in grid
    """

    for field in arcpy.ListFields(grid):
        if field.name.lower() == "value":
            return field.name
    return "VALUE"


def tabulateRasterLayer(srcFC, layer, layerConfig, spatialReference, messages):
    """
    srcFC: source feature class wrapper
    layer: layer object
    layerConfig: subset of config for a single layer
    spatialReference: spatial reference object with target projection
    """

    logger.debug("Processing %s" % (layer.name))
    arcpy.env.cartographicCoordinateSystem = None

    results = {
        "intersectionGeometryType": "pixel",
        "intersectionQuantity": 0,
        "method": "approximate"
    }

    try:
        #Convert the projected user defined feature class (projFC) to a temporary raster - which is in the same spatial reference as the target raster.
        lyrInfo = arcpy.Describe(layer.dataSource)
        rasterExtent = lyrInfo.extent
        extentInRasterProjection = srcFC.getExtent(lyrInfo.spatialReference, True)

        #have to do the comparison ourselves; the builtin geometric comparisons don't work properly (e.g., extent.overlaps)
        if (extentInRasterProjection.XMin > rasterExtent.XMax or extentInRasterProjection.XMax < rasterExtent.XMin or
                        extentInRasterProjection.YMin > rasterExtent.YMax or extentInRasterProjection.YMax < rasterExtent.YMin):
            logger.debug("Source features do not overlap target raster")
            return results

        arcpy.CheckOutExtension("Spatial")

        #TODO: if point type, branch here and use sample tool


        #extract using extent
        clippedGrid = os.path.join(arcpy.env.scratchWorkspace, "data.img")
        arcpy.Clip_management(layer.dataSource,
                              "%f %f %f %f" % (extentInRasterProjection.XMin, extentInRasterProjection.YMin,
                                               extentInRasterProjection.XMax, extentInRasterProjection.YMax),
                              clippedGrid, "#", "#", "NONE")

        messages.incrementMinorStep()

        logger.debug("Raster projection is: %s\n(%s)" % (lyrInfo.spatialReference.projectionName, lyrInfo.spatialReference.exporttostring()))

        projectedGrid = None
        if ProjectionUtilities.isValidAreaProjection(lyrInfo.spatialReference):
            logger.debug("Raster is in valid projection for calculating areas, using that instead of custom projection")
            results['projection'] = "native"
            spatialReference = lyrInfo.spatialReference
            arcpy.env.snapRaster = clippedGrid
            projectedGrid = arcpy.Raster(clippedGrid)

        else:
            #only project if necessary
            logger.debug("Projecting raster to target projection")
            results['projection'] = "custom"
            projectedGrid = os.path.join(arcpy.env.scratchWorkspace, "projData.img")
            geoTransform = ProjectionUtilities.getGeoTransform(lyrInfo.spatialReference, spatialReference)
            arcpy.ProjectRaster_management(clippedGrid, projectedGrid, spatialReference.exportToString(),
                                           geographic_transform=geoTransform)
            arcpy.env.snapRaster = projectedGrid
            projectedGrid = arcpy.Raster(projectedGrid)

        messages.incrementMinorStep()

        pixelArea = (projectedGrid.meanCellHeight * projectedGrid.meanCellWidth * ProjectionUtilities.getProjUnitFactors(spatialReference)[1])
        results['pixelArea'] = pixelArea

        #get projected features
        projFC = srcFC.project(spatialReference)

        numPixels = projectedGrid.height * projectedGrid.width
        logger.debug("%i pixels within extent of source features" % (numPixels))

        #arbitrary limit above which too big to use more exact fishnet-based area weighted methods
        if numPixels <= 50000 and srcFC.getGeometryType() in ["Polygon", "Polyline"]:
            import numpy

            results['method'] = "precise"
            logger.debug("Small input grid, using precise method")

            logger.debug("Creating fishnet")
            fishnet = os.path.join(get_scratch_GDB(), "fishnet")
            arcpy.CreateFishnet_management(fishnet, "%f %f" % (projectedGrid.extent.XMin, projectedGrid.extent.YMin),
                                           "%f %f" % (projectedGrid.extent.XMin, projectedGrid.extent.YMax),
                                           projectedGrid.meanCellWidth, projectedGrid.meanCellHeight,
                                           projectedGrid.height,
                                           projectedGrid.width, "#", False, projectedGrid, "POLYGON")

            messages.incrementMinorStep()

            logger.debug("Intersecting with area of interest")
            intersection = os.path.join(get_scratch_GDB(), "intersection")
            arcpy.Intersect_analysis("%s #;%s #" % (projFC, fishnet), intersection, "ONLY_FID", "#", "INPUT")

            messages.incrementMinorStep()

            logger.debug("Tabulating quantities")
            fix_nodata = False
            try:
                # This fails on ArcGIS server for integer grids, under certain circumstances.
                values = arcpy.RasterToNumPyArray(projectedGrid, nodata_to_value=numpy.nan)
            except ValueError:
                logger.debug("Could not apply nodata directly to numpy array as numpy.nan, masking later")
                values = arcpy.RasterToNumPyArray(projectedGrid)
                fix_nodata = True
            quantities = numpy.zeros(values.shape)
            quantityAttribute = srcFC.getQuantityAttribute()
            areaLengthFactor = 0
            totalQuantity = 0.0
            if srcFC.getGeometryType() == "Polyline":
                areaLengthFactor = ProjectionUtilities.getProjUnitFactors(spatialReference)[0]
            elif srcFC.getGeometryType() == "Polygon":
                areaLengthFactor = ProjectionUtilities.getProjUnitFactors(spatialReference)[1]
            rows = arcpy.SearchCursor(intersection)
            for row in rows:
                OID = row.getValue("FID_%s" % (os.path.split(fishnet)[1]))
                grid_row, grid_col = FishnetOIDToNumpy(OID, projectedGrid.height, projectedGrid.width)
                quantity = getattr(row.shape, quantityAttribute) * areaLengthFactor
                totalQuantity += quantity
                quantities[grid_row][grid_col] += quantity

            del row, rows
            arcpy.Delete_management(fishnet)
            del fishnet
            arcpy.Delete_management(intersection)
            del intersection

            #mask out the original NoData values and areas outside AOI
            if fix_nodata:
                d = arcpy.Describe(projectedGrid)
                if hasattr(d, 'nodataValue'):
                    # Sometimes missing, just to make this even more difficult
                    logger.debug("Masking out nodata value: %s" % d.nodataValue)
                    values = numpy.ma.masked_array(values, mask=numpy.logical_or(values == d.nodataValue, quantities == 0))
                else:
                    values = numpy.ma.masked_array(values, mask=quantities == 0)
            else:
                values = numpy.ma.masked_array(values, mask=numpy.logical_or(numpy.isnan(values), quantities == 0))
            results["intersectionCount"] = int((values.mask == False).sum())
            results["intersectionQuantity"] = totalQuantity
            results["sourcePixelCount"] = int((quantities != 0).sum())
            #Note: this will not be accurate if AOI falls outside extent of raster

            src_total_quantity = srcFC.getTotalAreaOrLength(spatialReference)

            if layerConfig.has_key("statistics"):
                logger.debug("Calculating statistics")
                #straight statistics are easy
                results["statistics"] = dict()
                if "MIN" in layerConfig["statistics"]:
                    results["statistics"]["MIN"] = round(values.min(), 2)
                if "MAX" in layerConfig["statistics"]:
                    results["statistics"]["MAX"] = round(values.max(), 2)
                if "MEAN" in layerConfig["statistics"]:
                    results["statistics"]["MEAN"] = round(values.mean(), 2)
                if "STD" in layerConfig["statistics"]:
                    results["statistics"]["STD"] = round(values.std(), 2)
                if "SUM" in layerConfig["statistics"]:
                    results["statistics"]["SUM"] = round(values.sum(), 2)

                #weighted statistics are harder
                if "MEAN" in layerConfig["statistics"]:
                    if srcFC.getGeometryType() == "Polyline":
                        weighted_values = values * quantities / src_total_quantity  #weighted by proportion of srcFC
                        results["statistics"]["MEAN"] = round(weighted_values.sum(), 2)
                    elif srcFC.getGeometryType() == "Polygon":
                        #calculate weighted by proportion of each pixel occupied, assuming equal distribution within pixels
                        pixel_proportion = quantities / pixelArea
                        weighted_values = values * pixel_proportion
                        results["statistics"]["MEAN"] = round(weighted_values.sum() / pixel_proportion.sum(), 2)
            else:
                if not projectedGrid.isInteger:
                    #only option is classes of original values
                    if layerConfig.has_key("classes"):
                        logger.debug("Classifying input raster")
                        results.update({'classes': getNumpyClassQuantities(values, quantities, layerConfig["classes"])})
                else:
                    logger.debug("Tabulating unique values")
                    values = values.astype(int)
                    by_value_results = getNumpyValueQuantities(values, quantities)

                    if layerConfig.has_key("attributes") and len(layerConfig["attributes"]):
                        arcpy.BuildRasterAttributeTable_management(projectedGrid)
                        fields = [field.name for field in arcpy.ListFields(projectedGrid)]
                        summaryFields = dict(
                            [(summaryField["attribute"], SummaryField(summaryField, True)) for summaryField in
                             layerConfig.get("attributes", [])])
                        diffFields = set(summaryFields.keys()).difference(fields)
                        if diffFields:
                            raise ValueError(
                                "FIELD_NOT_FOUND: Fields do not exist in layer %s: %s\nThese fields are present: %s"
                                % (layer.name, ",".join([str(fieldName) for fieldName in diffFields]), ",".join(fields))
                            )

                        rows = arcpy.SearchCursor(projectedGrid)
                        valueField = getGridValueField(projectedGrid)

                        for row in rows:
                            value = row.getValue(valueField)
                            if value in by_value_results:
                                #Values will be absent if outside the analysis area
                                count = by_value_results[value]['intersectionCount']
                                quantity = by_value_results[value]['intersectionQuantity']
                                for summaryField in summaryFields:
                                    summaryFields[summaryField].addRecord(row.getValue(summaryField), count, quantity)
                        del rows
                        results['attributes'] = []
                        for summaryField in summaryFields:
                            results["attributes"].append(summaryFields[summaryField].getResults())

                    else:
                        if layerConfig.has_key("classes"):
                            results.update(
                                {'classes': getNumpyClassQuantities(values, quantities, layerConfig["classes"])})
                        else:
                            unique_values = by_value_results.keys()
                            unique_values.sort()
                            value_results = []
                            for value in unique_values:
                                value_results.append(
                                    {
                                        'value': value,
                                        'intersectionCount': by_value_results[value]['intersectionCount'],
                                        'intersectionQuantity': by_value_results[value]['intersectionQuantity']
                                    }
                                )
                            results.update({'values': value_results})
        else:
            logger.debug("Large input grid or point input, using approximate method")

            logger.debug("Creating area of interest raster")
            aoiGrid = os.path.join(arcpy.env.scratchWorkspace, "aoiGrid.img")
            #arcpy.Describe(projFC).OIDFieldName  #we control this, not needed
            arcpy.FeatureToRaster_conversion(projFC, "OBJECTID", aoiGrid, projectedGrid.meanCellHeight)
            arcpy.BuildRasterAttributeTable_management(aoiGrid)
            results["sourcePixelCount"] = getGridCount(aoiGrid, None)[0]

            messages.incrementMinorStep()

            if layerConfig.has_key("statistics"):
                results["statistics"] = dict()
                logger.debug("Creating zone grid for statistics from area of interest grid")
                zoneGrid = arcpy.sa.Times(aoiGrid, 0)

                statistics = dict()
                for statistic in layerConfig["statistics"]:
                    arcgisStatistic = statistic.upper()
                    statistics[statistic] = (arcgisStatistic + "IMUM" if arcgisStatistic in ("MIN", "MAX")
                                             else arcgisStatistic)
                zonalStatsTable = "%s/zonalStatsTable" % (get_scratch_GDB())
                if arcpy.Exists(zonalStatsTable):
                    arcpy.Delete_management(zonalStatsTable)
                arcpy.BuildRasterAttributeTable_management(zoneGrid)
                logger.debug("Executing zonal statistics: %s" % (",".join(statistics.values())))
                zonalStatsTable = arcpy.sa.ZonalStatisticsAsTable(zoneGrid, getGridValueField(zoneGrid),
                                                                  arcpy.Raster(layer.dataSource), zonalStatsTable,
                                                                  "DATA", "ALL")
                del zoneGrid

                messages.incrementMinorStep()

                totalCount = 0
                rows = arcpy.SearchCursor(zonalStatsTable)
                if rows:
                    for row in rows:
                        totalCount += row.COUNT
                        for statistic in statistics:
                            results["statistics"][statistic] = row.getValue(statistic.upper())
                        break  #should only have one row
                    del row
                del rows, zonalStatsTable
                arcpy.Delete_management("%s/zonalStatsTable" % (get_scratch_GDB()))
                results["intersectionCount"] = totalCount

            else:
                #clip the target using this grid, snapped to the original grid - watch for alignment issues in aoiGrid - snapRaster is not used there
                logger.debug("Extracting area of interest from %s" % (layer.name))
                clipGrid = arcpy.sa.ExtractByMask(projectedGrid, aoiGrid)

                messages.incrementMinorStep()

                if not clipGrid.isInteger:
                    #force to single bit data, since we can't build attribute tables of floating point data.
                    testGrid = arcpy.sa.IsNull(clipGrid)
                    arcpy.BuildRasterAttributeTable_management(testGrid)
                    results["intersectionCount"] = getGridCount(testGrid, getGridValueField(testGrid))[1][0]
                    #testGrid.save(os.path.join(arcpy.env.scratchWorkspace,"isnull")) #for testing
                    del testGrid

                    if layerConfig.has_key("classes"):
                        classCounts = getGridClasses(clipGrid, getGridValueField(clipGrid), layerConfig["classes"])
                        classResults = []
                        for classIndex in range(0, len(layerConfig["classes"])):
                            count = classCounts.get(classIndex, 0)
                            classResults.append({
                                'class': layerConfig["classes"][classIndex],
                                'intersectionCount': count,
                                'intersectionQuantity': (float(count) * pixelArea)})
                        results.update({'classes': classResults})

                else:
                    arcpy.BuildRasterAttributeTable_management(clipGrid)
                    valueField = getGridValueField(clipGrid)
                    promoteValueResults = False
                    if not layerConfig.has_key("attributes"):
                        promoteValueResults = True
                        layerConfig["attributes"] = [{'attribute': valueField}]
                        if layerConfig.has_key("classes"):
                            layerConfig["attributes"][0]['classes'] = layerConfig['classes']

                    summaryFields = dict(
                        [
                            (summaryField["attribute"], SummaryField(summaryField, True)) for summaryField in layerConfig.get("attributes", [])
                        ]
                    )
                    if summaryFields:
                        fieldList = set([field.name for field in arcpy.ListFields(clipGrid)])
                        diffFields = set(summaryFields.keys()).difference(fieldList)
                        if diffFields:
                            raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s" % (
                            layer.name, ",".join([str(fieldName) for fieldName in diffFields])))
                        if not promoteValueResults:
                            results["attributes"] = []

                    #TODO: use python Counter class if available (python > 2.7)
                    totalCount = 0
                    rows = arcpy.SearchCursor(clipGrid, "", "")
                    for row in rows:
                        totalCount += row.COUNT
                        for summaryField in summaryFields:
                            summaryFields[summaryField].addRecord(row.getValue(summaryField), row.COUNT,
                                                                  row.COUNT * pixelArea)
                    del rows
                    results["intersectionCount"] = totalCount

                    if promoteValueResults:
                        key = "classes" if layerConfig.has_key("classes") else "values"
                        results[key] = summaryFields[valueField].getResults()[key]
                    else:
                        for summaryField in summaryFields:
                            results["attributes"].append(summaryFields[summaryField].getResults())

                arcpy.Delete_management(clipGrid)
                del clipGrid
            arcpy.Delete_management(aoiGrid)
            del aoiGrid

            results["intersectionQuantity"] = float(results["intersectionCount"]) * pixelArea

        try:
            arcpy.Delete_management(clippedGrid)
            #this is causing issues on server, maybe getting deleted too soon? TODO: create a delete tool that runs in a try-catch block
            if projectedGrid is not None:
                arcpy.Delete_management(projectedGrid)
        except:
            pass
    finally:
        arcpy.CheckInExtension("Spatial")

    return results


def tabulateFeatureLayer(srcFC, layer, layerConfig, spatialReference, messages):
    logger.debug("tabulateFeatureLayer: %s" % (layer.name))

    arcpy.env.extent = None
    arcpy.env.cartographicCoordinateSystem = None
    results = dict()

    lyrInfo = arcpy.Describe(layer.dataSource)
    #select features from layer using target projection and where clause (if provided)
    selLyr = arcpy.MakeFeatureLayer_management(layer, "selLyr", layerConfig.get("where", "")).getOutput(0)
    #must project source features into native projection of layer for selection to work properly
    projSrcFC = srcFC.project(lyrInfo.spatialReference)
    arcpy.SelectLayerByLocation_management(selLyr, "INTERSECT", projSrcFC)
    logger.debug("Selected features from target layer that intersect area of interest")
    featureCount = int(arcpy.GetCount_management(selLyr).getOutput(0))
    logger.debug("Found %s intersecting features" % (featureCount))

    messages.incrementMinorStep()

    if featureCount > 0:
        arcpy.env.cartographicCoordinateSystem = spatialReference
        selFC = "IN_MEMORY/selFC"
        #Selected features must be copied into new feature class for projection step, otherwise it uses the entire dataset (lame!)
        logger.debug("Copying selected features to in-memory feature class")
        arcpy.CopyFeatures_management(selLyr, selFC)

        messages.incrementMinorStep()

        #project the selection to target projection, and then intersect with source (in target projection)
        geoTransform = ProjectionUtilities.getGeoTransform(lyrInfo.spatialReference, spatialReference)
        logger.debug("Projecting selected features from %s" % (layer.name))
        projFC = FeatureClassWrapper(
            arcpy.Project_management(selFC, "projFC", spatialReference, geoTransform).getOutput(0))
        logger.debug("Intersecting selected features with area of interest")
        intFC = FeatureClassWrapper(arcpy.Intersect_analysis([srcFC.project(spatialReference), projFC.featureClass],
                                                             "IN_MEMORY/" + "intFC").getOutput(0))

        messages.incrementMinorStep()

        featureCount = int(arcpy.GetCount_management(intFC.featureClass).getOutput(0))
        if featureCount > 0:
            intersectionQuantityAttribute = intFC.getQuantityAttribute()
            intersectionConversionFactor = intFC.getGeometryConversionFactor(spatialReference)
            intersectionSummaryFields = dict(
                [(summaryField["attribute"], SummaryField(summaryField, intersectionQuantityAttribute is not None)) for
                 summaryField in layerConfig.get("attributes", [])])

            intersectedQuantityAttribute = projFC.getQuantityAttribute()
            intersectedConversionFactor = projFC.getGeometryConversionFactor(spatialReference)
            intersectedSummaryFields = copy.deepcopy(intersectionSummaryFields)

            if intersectionSummaryFields:
                fieldList = set([field.name for field in arcpy.ListFields(intFC.featureClass)])
                diffFields = set(intersectionSummaryFields.keys()).difference(fieldList)
                if diffFields:
                    raise ValueError("FIELD_NOT_FOUND: Fields do not exist in layer %s: %s" % (
                    layer.name, ",".join([str(fieldName) for fieldName in diffFields])))
                results["attributes"] = []

            logger.debug("Tallying intersection results")
            #tally results for intersection
            rows = arcpy.SearchCursor(intFC.featureClass)
                #TODO: may want to pare this down to SHAPE and summary fields only
            total = 0
            count = 0
            for row in rows:
                geometryCount = 1  #Note: NOT number of features within this record in case of multi-part features
                count += geometryCount
                quantity = 0
                if intersectionQuantityAttribute:
                    quantity = getattr(row.shape, intersectionQuantityAttribute) * intersectionConversionFactor
                    total += quantity
                for summaryField in intersectionSummaryFields:
                    intersectionSummaryFields[summaryField].addRecord(row.getValue(summaryField), geometryCount,
                                                                      quantity)
            del row, rows

            messages.incrementMinorStep()

            results["intersectionGeometryType"] = intFC.getGeometryType().lower().replace("polyline", "line")
            results["intersectionCount"] = count
            if intersectionQuantityAttribute:
                results["intersectionQuantity"] = total

            logger.debug("Tallying intersected feature results")
            #tally results for intersected features
            rows = arcpy.SearchCursor(projFC.featureClass)
            total = 0
            count = 0
            for row in rows:
                geometryCount = 1  #row.shape.partCount
                count += geometryCount
                quantity = 0
                if intersectedQuantityAttribute:
                    quantity = getattr(row.shape, intersectedQuantityAttribute) * intersectedConversionFactor
                    total += quantity
                for summaryField in intersectedSummaryFields:
                    intersectedSummaryFields[summaryField].addRecord(row.getValue(summaryField), geometryCount,
                                                                     quantity)
            del row, rows

            messages.incrementMinorStep()

            results["intersectedGeometryType"] = projFC.getGeometryType().lower().replace("polyline", "line")
            results["intersectedCount"] = count
            if intersectedQuantityAttribute:
                results["intersectedQuantity"] = total

            #collate results of intersection and intersected
            for summaryField in intersectionSummaryFields:
                summaryFieldResult = {"attribute": summaryField}
                if intersectionSummaryFields[summaryField].statistics:
                    summaryFieldResult["statistics"] = intersectionSummaryFields[summaryField].getStatistics(
                        intersectionSummaryFields[summaryField].statistics)

                else:
                    collatedResults = []
                    intersectionResults = intersectionSummaryFields[summaryField].results
                    intersectedResults = intersectedSummaryFields[summaryField].results

                    if intersectionSummaryFields[summaryField].classes:
                        classes = intersectionSummaryFields[summaryField].classes
                        for i in range(0, len(classes)):
                            result = {"class": classes[i], "intersectionCount": intersectionResults[i].count,
                                      "intersectedCount": intersectedResults[i].count}
                            if intersectionQuantityAttribute:
                                result["intersectionQuantity"] = intersectionResults[i].quantity
                            if intersectedQuantityAttribute:
                                result["intersectedQuantity"] = intersectedResults[i].quantity
                            collatedResults.append(result)
                        summaryFieldResult["classes"] = collatedResults
                    else:
                        for key in intersectionResults:  #key is class or value
                            result = {"value": key, "intersectionCount": intersectionResults[key].count,
                                      "intersectedCount": intersectedResults[key].count}
                            if intersectionQuantityAttribute:
                                result["intersectionQuantity"] = intersectionResults[key].quantity
                            if intersectedQuantityAttribute:
                                result["intersectedQuantity"] = intersectedResults[key].quantity
                            collatedResults.append(result)
                        summaryFieldResult["values"] = collatedResults
                results["attributes"].append(summaryFieldResult)

            del selFC
            del projFC
            del intFC
            arcpy.Delete_management("projFC")

        else:
            logger.debug("No Features intersected for this layer: %s" % (layer.name))
            results["intersectionCount"] = 0
            results["intersectedCount"] = 0  #no point in tallying features we don't have from intersection

    else:
        logger.debug("No Features selected for this layer: %s" % (layer.name))
        results["intersectionCount"] = 0
        results["intersectedCount"] = 0

    del selLyr
    return results


def tabulateMapService(srcFC, serviceID, mapServiceConfig, spatialReference, messages):
    """
    srcFC: source feature class wrapper
    mapDocPath: path to the map document behind the map service
    mapServiceConfig: subset of config for a single map service
    spatialReference: spatial reference object with target projection
    messages: instance of MessageHandler
    """

    results = []
    layerPaths = getDataPathsForService(serviceID)
    messages.setMinorSteps(len(mapServiceConfig['layers']) * 5)
    for layerConfig in mapServiceConfig['layers']:
        lyrResults = dict()
        layerID = int(layerConfig["layerID"])
        if not (layerID >= 0 and layerID < len(layerPaths)):
            raise ValueError("LAYER_NOT_FOUND: Layer not found for layerID: %s" % (layerID))
        logger.debug("Layer: %s ==> %s" % (layerID, layerPaths[layerID]))
        if not arcpy.Exists(layerPaths[layerID]):
            raise ValueError("LAYER_NOT_FOUND: Layer data source not found for layerID: %s" % (layerID))
        layer = arcpy.mapping.Layer(layerPaths[layerID])
        #TODO: handle layer definition specified in MXD / MSD
        try:
            logger.debug("Processing layer %s: %s" % (layerID, layer.name))
            result = {"layerID": layerID}
            if layer.isRasterLayer:
                result.update(tabulateRasterLayer(srcFC, layer, layerConfig, spatialReference, messages))
            elif layer.isFeatureLayer:
                result.update(tabulateFeatureLayer(srcFC, layer, layerConfig, spatialReference, messages))
            else:
                logger.error("Layer type is unsupported %s: %s" % (layerID, layer.name))
                result["error"] = "unsupported layer type"
            results.append(result)
        except GPToolError as ex:
            logger.error("Error processing layer %s: %s\n%s" % (layerID, layer.name, ex.message))
            results.append({"layerID": layerID, "error": ex.message})
        except:
            error = traceback.format_exc()
            logger.error("Error processing layer %s: %s\n%s" % (layerID, layer.name, error))
            results.append({"layerID": layerID, "error": error})

        messages.incrementMinorStep()

    return {"serviceID": serviceID, "layers": results}


def tabulateMapServices(srcFC, config, messages):
    """
    srcFC: instance of FeatureClass wrapper with the area of interest features
    config: TODO: operate on original list of map services
    projectionWKID: ESRI WKID representing the target projection to use for all calculations (e.g., 102003, which is USA_Contiguous_Albers_Equal_Area_Conic)
    """

    
    #Validate Inputs
    if not srcFC.getCount():
        raise GPToolError("INVALID INPUT: no features in input")

    if not len(config["services"]):
        raise GPToolError("INVALID INPUT: no map services specified")

    logger.debug("Starting tabulateMapServices")
    start = time.time()

    #wrap GP tool messages with logging
    messages = MessageHandler(logger=logger, messages=messages)
    messages.setMajorSteps(len(config["services"]) + 1)
    messages.setMinorSteps(2)

    logger.debug("Scratch Workspace: %s" % (arcpy.env.scratchWorkspace))
    #workspace must be pointing at GDB to prevent server object crashes when run as 10.0 geoprocessing service!
    arcpy.env.workspace = get_scratch_GDB()

    results = dict()
    if not config.has_key("services"):
        return results

    #setup target projection
    logger.debug("Setting up custom Albers projection")
    geoExtent = srcFC.getExtent(ProjectionUtilities.getSpatialReferenceFromWKID(4326))
    spatialReference = ProjectionUtilities.createCustomAlbers(geoExtent)
    messages.incrementMinorStep()

    results["area_units"] = "hectares"  #always
    results["linear_units"] = "kilometers"  #always
    results["sourceGeometryType"] = srcFC.getGeometryType().lower().replace("polyline", "line")
    results["sourceFeatureCount"] = srcFC.getCount()
    if results["sourceGeometryType"] != "point":
        results["sourceFeatureQuantity"] = srcFC.getTotalAreaOrLength(spatialReference)
    results["services"] = []
    messages.incrementMajorStep()

    for mapServiceConfig in config["services"]:
        serviceID = mapServiceConfig["serviceID"]
        try:
            logger.debug("Processing map service: %s" % (serviceID))
            results["services"].append(
                tabulateMapService(srcFC, serviceID, mapServiceConfig, spatialReference, messages))
        except:
            error = traceback.format_exc()
            logger.error("Error processing map service: %s\n%s" % (serviceID, error))
            results["services"].append({"serviceID": serviceID, "error": error})
        messages.incrementMajorStep()

    logger.debug("Elapsed time: %.2f" % (time.time() - start))
    return results




























