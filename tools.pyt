"""
ArcGIS 10.2.x Python Toolbox for geoprocessing tools
"""


import arcpy
import json
import logging

import tool_logging  # must be called early to init logging
from utilities import FeatureSetConverter
from utilities.feature_class_wrapper import FeatureClassWrapper
from tabulate import tabulateMapServices


logger = logging.getLogger(__name__)

class Toolbox(object):
    def __init__(self):
        self.label = "databasin_geoprocessing_tools"
        self.alias = "databasin_geoprocessing_tools"
        self.tools = [TabulateTool]


class TabulateTool(object):
    def __init__(self):
        self.label = "tabulate"
        self.description = """Tabulate intersection area, length, count for target feature and raster datasets in a
        published map service within area of interest (represented by featureSetJSON)"""
        self.canRunInBackground = False

    def getParameterInfo(self):
        return [arcpy.Parameter(displayName="Area of Interest FeatureSet (JSON)",name="featureSetJSON",datatype="String",
                        parameterType="Required",direction="Input"),
        arcpy.Parameter(displayName="Target Configuration (JSON)",name="configJSON",datatype="String",parameterType="Required",
                        direction="Input"),
        arcpy.Parameter(displayName="Results (JSON)",name="resultsJSON",datatype="String",
                        parameterType="Derived",direction="Output")]

    def execute(self, parameters, messages):
        srcFC=FeatureClassWrapper(FeatureSetConverter.createFeatureClass(parameters[0].valueAsText))
        config=json.loads(parameters[1].valueAsText)
        results = tabulateMapServices(srcFC,config,messages)
        parameters[2].value = json.dumps(results)
        return