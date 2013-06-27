"""
Running tests:

ArcGIS 10.0:
publish data/10.0/test.mxd as a service called test

ArcGIS 10.1
TODO
{"layerID":0},
{"layerID":0,"attributes":[{"attribute":"NAME"}]},
        {"layerID":0,"attributes":[{"attribute":"POP2000", "statistics":["MIN","MAX"]}]},
        {"layerID":2,"attributes":[{"attribute":"POP2000","classes":[[0,1000],[1000,10000],[10000,1000000]]}]},
        {"layerID":3},
        {"layerID":5},
        {"layerID":5,"classes":[[0,300],[300,310],[310,400]]},
        {"layerID":5,"statistics":["MIN","MAX","MEAN","SUM"]}
"""

import settings
from tabulate import *
from utilities.FeatureSetConverter import createFeatureClass
from messaging import MessageHandler


POLYGON_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPolygon","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"},{"name":"SHAPE_Area","type":"esriFieldTypeDouble","alias":"SHAPE_Area"}],"features":[{"attributes":{"OBJECTID":3,"SHAPE_Length":49763.191463275194,"SHAPE_Area":161738984.17682847},"geometry":{"rings":[[[-12510743.8804,3962356.0276999995],[-12500772.095800001,3955536.6137000024],[-12509264.1962,3945822.1655000001],[-12510936.8827,3944921.4880999997],[-12513381.578299999,3946015.1677000001],[-12517112.955699999,3957466.636500001],[-12514925.5965,3960040.0002999976],[-12510743.8804,3962356.0276999995]]]}}]}"""
LINE_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPolyline","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"}],"features":[{"attributes":{"OBJECTID":1,"SHAPE_Length":20271.902391560558},"geometry":{"paths":[[[-12515628.3368,3958632.1604000032],[-12509134.533199999,3956248.0033000037],[-12506537.328299999,3952727.7947999984],[-12505715.1676,3948924.8555999994],[-12509496.627900001,3945519.4327000007]]]}}]}"""
POINT_JSON="""{"displayFieldName":"","geometryType":"esriGeometryPoint","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"}],"features":[{"attributes":{"OBJECTID":1},"geometry":{"x":-12511073.498500001,"y":3960698.4464000016}},{"attributes":{"OBJECTID":2},"geometry":{"x":-12508860.470800001,"y":3957728.3439000025}},{"attributes":{"OBJECTID":3},"geometry":{"x":-12512092.171799999,"y":3951813.8989000022}}]}"""

CONFIG_JSON="""
{"services":[
    {"serviceID":"test","layers":[
        {"layerID":0},
        {"layerID":0,"attributes":[{"attribute":"NAME"}]},
        {"layerID":0,"attributes":[{"attribute":"POP2000", "statistics":["MIN","MAX"]}]},
        {"layerID":2,"attributes":[{"attribute":"POP2000","classes":[[0,1000],[1000,10000],[10000,1000000]]}]},
        {"layerID":3},
        {"layerID":5},
        {"layerID":5,"classes":[[0,300],[300,310],[310,400]]},
        {"layerID":5,"statistics":["MIN","MAX","MEAN","SUM"]}

    ]}
]}
"""


def test_tabulateMapServices_polygon_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POLYGON_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,102003,messages)
    #print json.dumps(results,indent=1)

    assert results['area_units']=="hectares"
    assert results['sourceGeometryType']=="polygon"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==8

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['layerID']==0
    assert layerResults['intersectedGeometryType']=="point"
    assert layerResults['intersectedCount']==2
    assert layerResults['intersectionGeometryType']=="point"
    assert layerResults['intersectionCount']==2
    assert layerResults['attributes'][0]['attribute']=="NAME"
    assert layerResults['attributes'][0]['values'][0]['intersectedCount']==1
    assert layerResults['attributes'][0]['values'][0]['value']=="Avondale"

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['layerID']==0
    assert layerResults['attributes'][0]['attribute']=="POP2000"
    assert layerResults['attributes'][0]['statistics']["MIN"]==18911
    assert layerResults['attributes'][0]['statistics']["MAX"]==35883

    layerResults=results['services'][0]['layers'][3]
    assert layerResults['layerID']==2
    assert layerResults['attributes'][0]['attribute']=="POP2000"
    assert layerResults['attributes'][0]['classes'][0]['class']==[0,1000]
    assert layerResults['attributes'][0]['classes'][0]['intersectedCount']==0
    assert layerResults['attributes'][0]['classes'][2]['intersectedCount']==1
    assert layerResults['attributes'][0]['classes'][2]['intersectionQuantity']==3774.3558016523793

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==124796
    assert layerResults['intersectionQuantity']==11231.639999999999
    assert layerResults['values'][0]['value']==1
    assert layerResults['values'][0]['count']==24090
    assert layerResults['values'][0]['quantity']==2168.0999999999999

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==67863
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==6107.6700000000001

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==378.656494140625
    assert layerResults['statistics']['MIN']==271.205322265625
    assert layerResults['statistics']['MEAN']==297.65512084960937


def test_tabulateMapServices_line_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(LINE_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,102003,messages)
    #print json.dumps(results,indent=1)

    assert results['linear_units']=="kilometers"
    assert results['sourceGeometryType']=="line"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==8

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['layerID']==0
    assert layerResults['intersectionCount']==0
    assert layerResults['intersectedCount']==0

    layerResults=results['services'][0]['layers'][3]
    assert layerResults['layerID']==2
    assert layerResults['attributes'][0]['attribute']=="POP2000"
    assert layerResults['attributes'][0]['classes'][0]['class']==[0,1000]
    assert layerResults['attributes'][0]['classes'][0]['intersectedCount']==0
    assert layerResults['attributes'][0]['classes'][2]['intersectedCount']==1
    assert layerResults['attributes'][0]['classes'][2]['intersectedQuantity']==7670.2729527175416
    assert layerResults['attributes'][0]['classes'][2]['intersectionQuantity']==6.5561350046642879

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==734
    assert layerResults['intersectionQuantity']==66.060000000000002
    assert layerResults['values'][0]['value']==1
    assert layerResults['values'][0]['count']==200
    assert layerResults['values'][0]['quantity']==18.0

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==362
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==32.579999999999998

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==347.89703369140625
    assert layerResults['statistics']['MIN']==276.43701171875
    assert layerResults['statistics']['MEAN']==298.198486328125


def test_tabulateMapServices_point_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POINT_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,102003,messages)
    #print json.dumps(results,indent=1)

    assert results['sourceGeometryType']=="point"
    assert results['services'][0]['serviceID']=="test"
    assert len(results['services'][0]['layers'])==8

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['layerID']==0
    assert layerResults['intersectionCount']==0
    assert layerResults['intersectedCount']==0

    layerResults=results['services'][0]['layers'][3]
    assert layerResults['layerID']==2
    assert layerResults['attributes'][0]['attribute']=="POP2000"
    assert layerResults['attributes'][0]['classes'][0]['class']==[0,1000]
    assert layerResults['attributes'][0]['classes'][0]['intersectedCount']==0
    assert layerResults['attributes'][0]['classes'][2]['intersectedCount']==1
    assert layerResults['attributes'][0]['classes'][2]['intersectedQuantity']==7670.2729527175416

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.089999999999999997
    assert layerResults['geometryType']=="pixel"
    assert layerResults['projectionType']=="native"
    assert layerResults['sourcePixelCount']==3
    assert layerResults['intersectionQuantity']==0.27000000000000002
    assert layerResults['values'][0]['value']==2
    assert layerResults['values'][0]['count']==1
    assert layerResults['values'][0]['quantity']==0.089999999999999997

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==1
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==0.089999999999999997

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==313.635009765625
    assert layerResults['statistics']['MIN']==292.135009765625
    assert layerResults['statistics']['MEAN']==303.468994140625




test_tabulateMapServices_polygon_aoi()
test_tabulateMapServices_line_aoi()