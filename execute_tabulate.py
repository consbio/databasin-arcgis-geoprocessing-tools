"""
This script is used by the ArcGIS 10.0 toolbox
"""

from tabulate import *


messages = MessageHandler(logger=logger)
srcFC=FeatureClassWrapper(FeatureSetConverter.createFeatureClass(arcpy.GetParameterAsText(0)))
config=json.loads(arcpy.GetParameterAsText(1))
targetProjectionWKID=arcpy.GetParameter(2)
results = json.dumps(tabulateMapServices(srcFC,config,targetProjectionWKID,messages))
arcpy.SetParameter(3,results)