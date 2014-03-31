import json
import os
import arcpy
import sys
from geoindex.regions_for_service import getRegionsForMapSvc


class GetRegionsForServiceTool(object):
    def __init__(self):
        self.label = "GetRegionsForService"
        self.description = "Find regions for a given map service on this server"
        self.canRunInBackground = False

    def getParameterInfo(self):
        return [
            arcpy.Parameter(
                displayName="Service ID",
                name="service_id",
                datatype="GPString",
                parameterType="Required",
                direction="Input"
            ),
            arcpy.Parameter(
                displayName="Output Regions",
                name="out_regions",
                datatype="GPString",
                parameterType="Derived",
                direction="Output"
            )
        ]

    def execute(self, parameters, messages):
        sys.path.append(os.path.split(__file__))
        regions = getRegionsForMapSvc(parameters[0].valueAsText, None)
        parameters[1].value = json.dumps(regions)


class Toolbox(object):
    def __init__(self):
        self.label = "GeoindexingToolbox"
        self.alias = "Geoindexing Toolbox"
        self.tools = [GetRegionsForServiceTool]
