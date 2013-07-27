"""
ArcGIS 10.1 Python Toolbox for geoprocessing tools
"""


import arcpy
from tabulate import *


class Toolbox(object):
    def __init__(self):
        self.label = "databasin_geoprocessing_tools"
        self.alias = "databasin_geoprocessing_tools"
        self.tools = [TabulateTool]


class TabulateTool(object):
    def __init__(self):
        self.label = "Tabulate Tool"
        self.description = "Tabulate intersection area, length, count for target feature and raster datasets in a published map service within area of interest (represented by featureSetJSON)"
        self.canRunInBackground = False

    def getParameterInfo(self):
        return [arcpy.Parameter(displayName="Area of Interest FeatureSet (JSON)",name="featureSetJSON",datatype="String",
                        parameterType="Required",direction="Input"),
        arcpy.Parameter(displayName="Target Configuration (JSON)",name="configJSON",datatype="String",parameterType="Required",
                        direction="Input"),
        arcpy.Parameter(displayName="Results (JSON)",name="resultsJSON",datatype="String",
                        parameterType="Derived",direction="Output")]


    def execute(self, parameters, messages):
        messageHandler = MessageHandler(logger=logger,messages=messages)
        srcFC=FeatureClassWrapper(FeatureSetConverter.createFeatureClass(parameters[0].valueAsText))
        config=json.loads(parameters[1].valueAsText)
        results = json.dumps(tabulateMapServices(srcFC,config,messageHandler))
        parameters[2].value=results
        return