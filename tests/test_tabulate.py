"""
Running tests:

ArcGIS 10.0:
publish data/10.0/test.mxd as a service called test

ArcGIS 10.1
TODO

"""

import pytest
import settings
from tabulate import *
from utilities.FeatureSetConverter import createFeatureClass
from messaging import MessageHandler



POLYGON_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPolygon","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"},{"name":"SHAPE_Area","type":"esriFieldTypeDouble","alias":"SHAPE_Area"}],"features":[{"attributes":{"OBJECTID":3,"SHAPE_Length":49763.191463275194,"SHAPE_Area":161738984.17682847},"geometry":{"rings":[[[-12510743.8804,3962356.0276999995],[-12500772.095800001,3955536.6137000024],[-12509264.1962,3945822.1655000001],[-12510936.8827,3944921.4880999997],[-12513381.578299999,3946015.1677000001],[-12517112.955699999,3957466.636500001],[-12514925.5965,3960040.0002999976],[-12510743.8804,3962356.0276999995]]]}}]}"""
LINE_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPolyline","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"}],"features":[{"attributes":{"OBJECTID":1,"SHAPE_Length":20271.902391560558},"geometry":{"paths":[[[-12515628.3368,3958632.1604000032],[-12509134.533199999,3956248.0033000037],[-12506537.328299999,3952727.7947999984],[-12505715.1676,3948924.8555999994],[-12509496.627900001,3945519.4327000007]]]}}]}"""
POINT_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPoint","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"}],"features":[{"attributes":{"OBJECTID":1},"geometry":{"x":-12511073.498500001,"y":3960698.4464000016}},{"attributes":{"OBJECTID":2},"geometry":{"x":-12508860.470800001,"y":3957728.3439000025}},{"attributes":{"OBJECTID":3},"geometry":{"x":-12512092.171799999,"y":3951813.8989000022}}]}"""


def test_tabulateMapServices_polygon_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POLYGON_JSON))
    config=json.loads('''{"services":[{"serviceID":"test","layers":[{"layerID":0,"attributes":[{"attribute":"NAME"}]},{"layerID":5},{"layerID":5,"classes":[[0,300],[300,310],[310,400]]}]}]}''')
    results = tabulateMapServices(srcFC,config,102003,messages)

    assert results['units']=="hectares"
    assert results['sourceGeometryType']=="polygon"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==0
    assert layerResults['intersectedGeometryType']=="point"
    assert layerResults['intersectedCount']==2
    assert layerResults['intersectionGeometryType']=="point"
    assert layerResults['intersectionCount']==2
    assert layerResults['attributes'][0]['attribute']=="NAME"
    assert layerResults['attributes'][0]['values'][0]['intersectedCount']==1
    assert layerResults['attributes'][0]['values'][0]['value']=="Avondale"

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['layerID']==5
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==124796
    assert layerResults['intersectionQuantity']==11231.639999999999

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['classes'][0]['count']==67863
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==6107.6700000000001


def test_tabulateMapServices_line_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(LINE_JSON))
    config=json.loads('''{"services":[{"serviceID":"test","layers":[{"layerID":0,"attributes":[{"attribute":"NAME"}]},{"layerID":5},{"layerID":5,"classes":[[0,300],[300,310],[310,400]]}]}]}''')
    results = tabulateMapServices(srcFC,config,102003,messages)

    assert results['units']=="hectares"
    assert results['sourceGeometryType']=="line"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==0
    assert layerResults['intersectedCount']==0
    assert layerResults['intersectionCount']==0

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['layerID']==5
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==734
    assert layerResults['intersectionQuantity']==66.060000000000002

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['classes'][0]['count']==362
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==32.579999999999998


def test_tabulateMapServices_point_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POINT_JSON))
    config=json.loads('''{"services":[{"serviceID":"test","layers":[{"layerID":4,"attributes":[{"attribute":"STATE_NAME"}]},{"layerID":5},{"layerID":5,"classes":[[0,300],[300,310],[310,400]]}]}]}''')
    results = tabulateMapServices(srcFC,config,102003,messages)

    assert results['units']=="hectares"
    assert results['sourceGeometryType']=="point"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==4
    assert layerResults['intersectedCount']==1
    assert layerResults['intersectedGeometryType']=="polygon"
    assert layerResults['intersectionCount']==3
    assert layerResults['intersectionGeometryType']=="point"
    assert layerResults['attributes'][0]['values'][0]['value']=="Arizona"
    assert layerResults['attributes'][0]['values'][0]['intersectedQuantity']==29451737.46291206

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['layerID']==5
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==3
    assert layerResults['intersectionQuantity']==0.27000000000000002

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['classes'][0]['count']==1
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==0.089999999999999997
