"""
ArcGIS 10.2.x Python Toolbox for geoprocessing tools
"""


import arcpy
import json
import logging
import os
import shutil


import tool_logging  # must be called early to init logging
from utilities import FeatureSetConverter
from utilities.feature_class_wrapper import FeatureClassWrapper
from tabulate import tabulateMapServices


logger = logging.getLogger(__name__)


class Toolbox(object):
    def __init__(self):
        self.label = "databasin_geoprocessing_tools"
        self.alias = "databasin_geoprocessing_tools"
        self.tools = [TabulateTool, TestTabulateTool, GetLog]


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


class TestTabulateTool(object):
    def __init__(self):
        self.label = "test_tabulate"
        self.description = """Test the tabulate tool.  Test data must be deployed as a map service:
        arcgis_geoprocessing_tools_test_data"""
        self.canRunInBackground = False

    def getParameterInfo(self):
        pass

    def execute(self, parameters, messages):
        from tests.test_tabulate import test_poly_aoi
        messages.addMessage("Beginning tests...")
        messages.addMessage("TESTING: polygon AOI")
        test_poly_aoi(messages)
        messages.addMessage("PASSED: polygon AOI")

        logger.info("Tests completed successfully")
        messages.addMessage("All tests completed successfully")
        return


class GetLog(object):
    def __init__(self):
        self.label = "get_log"
        self.description = "Get the log file"
        self.canRunInBackground = False
        # Semi-private key, used for controlling access to log files in case they contain anything sort of sensitive
        self._key = "920d6f8190a302ccab7a768d13e5da46"

    def getParameterInfo(self):
        return [
            arcpy.Parameter(displayName="Key",name="key",datatype="String",
                            parameterType="Required",direction="Input"),
            arcpy.Parameter(displayName="Date (year-month-day)",name="datestamp",datatype="String",
                            parameterType="Optional",direction="Input"),
            arcpy.Parameter(displayName="Log",name="log",datatype="DEFile",
                            parameterType="Derived",direction="Output")
        ]

    def execute(self, parameters, messages):
        if not parameters[0].valueAsText == self._key:
            raise Exception("Invalid key")

        log_filename = os.path.realpath(tool_logging.LOG_FILENAME)
        datestamp = parameters[1].valueAsText
        if datestamp and datestamp.strip():
            log_filename += ".{0}".format(datestamp.strip())

        if not os.path.exists(log_filename):
            raise Exception("Log file does not exist at: {0}".format(log_filename))

        filename = os.path.split(log_filename)[1]
        # Have to copy file to scratch directory or it will not be available to client
        shutil.copy(log_filename, os.path.join(arcpy.env.scratchWorkspace, filename))
        parameters[2].value = filename
        return


