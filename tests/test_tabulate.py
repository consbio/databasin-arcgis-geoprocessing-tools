"""
Running tests:

ArcGIS 10.0:
publish data/10.0/test.mxd as a service called test

ArcGIS 10.1
TODO

"""

import settings
from tabulate import *
from utilities.FeatureSetConverter import createFeatureClass
from messaging import MessageHandler

#Test in US - tests approximate raster method
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
        {"layerID":5,"statistics":["MIN","MAX","MEAN","STD","SUM"]}
    ]}
]}
"""

# Test in Central America - this tests different projection and precise raster method
POLYGON_JSON_CENTRAL_AMERICA="""{"displayFieldName":"","geometryType":"esriGeometryPolygon","spatialReference":{"wkid":102100,"latestWkid":3857},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"Shape_Length","type":"esriFieldTypeDouble","alias":"Shape_Length"},{"name":"Shape_Area","type":"esriFieldTypeDouble","alias":"Shape_Area"}],"features":[{"attributes":{"OBJECTID":1,"Shape_Length":215246.30346339761,"Shape_Area":1489688992.6291437},"geometry":{"rings":[[[-9735208.3022000007,1746713.7391000018],[-9721875.4946999997,1744214.0918000005],[-9698428.3741999995,1740249.945700001],[-9690119.5023999996,1750277.5940999985],[-9670426.4793999996,1751466.4142999984],[-9656584.1029000003,1741917.1530999988],[-9656015.2338999994,1725425.9221000001],[-9677159.9499999993,1733075.4968000017],[-9703988.4594000001,1721449.3372999988],[-9716296.5018000007,1728082.0058000013],[-9731974.6559999995,1719027.7270999998],[-9731974.6559999995,1731256.7595000006],[-9735208.3022000007,1746713.7391000018]]]}}]}"""
LINE_JSON_CENTRAL_AMERICA="""{"displayFieldName":"","geometryType":"esriGeometryPolyline","spatialReference":{"wkid":102033,"latestWkid":102033},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"},{"name":"SHAPE_Length","type":"esriFieldTypeDouble","alias":"SHAPE_Length"}],"features":[{"attributes":{"OBJECTID":1,"SHAPE_Length":84177.067914374973},"geometry":{"paths":[[[-3391149.9389000013,4913830.2019999996],[-3384958.5658,4916334.7218999993],[-3382584.8099999987,4917225.5085000005],[-3379504.1721000001,4916433.4428000003],[-3376717.1950000003,4915087.7374000009],[-3369745.2096999995,4912739.0683999993],[-3366966.9791000001,4915105.0449000001],[-3363892.9838999994,4918021.5453999992],[-3361246.0921999998,4919273.0624000002],[-3358304.6173,4919218.2638000008],[-3355680.6156000011,4918425.4746000003],[-3355024.7289000005,4918227.1114000008],[-3345587.3581999987,4921198.2136000004],[-3344087.0163999982,4924139.1423000004],[-3339288.6999000013,4924411.2075999994],[-3332134.7259999998,4925372.2638000008],[-3327935.631099999,4928065.2427999992],[-3324554.6570999995,4929660.4204999991],[-3319254.5373000018,4930281.4574999996],[-3314715.7274999991,4932031.4629999995]]]}}]}"""
POINT_JSON_CENTRAL_AMERICA="""{"displayFieldName":"","geometryType":"esriGeometryPoint","spatialReference":{"wkid":102033,"latestWkid":102033},"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID","alias":"OBJECTID"}],"features":[{"attributes":{"OBJECTID":1},"geometry":{"x":-3318663.6875,"y":4906461.2636999991}}]}"""

CONFIG_JSON_CENTRAL_AMERICA="""
{"services":[
    {"serviceID":"test_central_america","layers":[
        {"layerID":0,"attributes":[{"attribute":"GEZ_TERM"}]},
        {"layerID":1,"classes":[[0,50],[50,100],[100,150],[150,200]]},
        {"layerID":1,"statistics":["MIN","MAX","MEAN","STD","SUM"]}
    ]}
]}

"""



def test_tabulateMapServices_polygon_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POLYGON_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,messages)
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
    assert layerResults['attributes'][0]['classes'][2]['intersectionQuantity']==3774.306667613756
    assert layerResults['attributes'][0]['classes'][2]['intersectedQuantity']==7670.2750505796675

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.090000000000000011
    assert layerResults['geometryType']=="pixel"
    assert layerResults['sourcePixelCount']==124798
    assert layerResults['intersectionQuantity']==11231.820000000002
    assert layerResults['values'][0]['value']==1
    assert layerResults['values'][0]['count']==24085
    assert layerResults['values'][0]['quantity']==2167.6500000000001

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==67753
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==6097.7700000000004

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==378.656494140625
    assert layerResults['statistics']['MIN']==271.205322265625
    assert layerResults['statistics']['MEAN']==297.65594482421875
    assert layerResults['statistics']['STD']==11.514897346496582
    assert layerResults['statistics']['SUM']==37146864.0


def test_tabulateMapServices_line_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(LINE_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,messages)
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
    assert layerResults['intersectionQuantity']==6.5353340459248344
    assert layerResults["intersectedQuantity"]==7670.2750505796675
    assert layerResults['attributes'][0]['attribute']=="POP2000"
    assert layerResults['attributes'][0]['classes'][0]['class']==[0,1000]
    assert layerResults['attributes'][0]['classes'][0]['intersectedCount']==0
    assert layerResults['attributes'][0]['classes'][2]['intersectedCount']==1
    assert layerResults['attributes'][0]['classes'][2]['intersectedQuantity']==7670.2750505796675
    assert layerResults['attributes'][0]['classes'][2]['intersectionQuantity']==6.5353340459248344

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.090000000000000011
    assert layerResults['geometryType']=="pixel"
    assert layerResults['sourcePixelCount']==746
    assert layerResults['intersectionQuantity']==67.230000000000004
    assert layerResults['values'][0]['value']==1
    assert layerResults['values'][0]['count']==209
    assert layerResults['values'][0]['quantity']==18.810000000000002

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==387
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==34.830000000000005

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==347.89703369140625
    assert layerResults['statistics']['MIN']==276.43701171875
    assert layerResults['statistics']['MEAN']==297.72662353515625
    assert layerResults['statistics']['STD']==12.37867259979248
    assert layerResults['statistics']['SUM']==222401.78125


def test_tabulateMapServices_point_aoi():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POINT_JSON))
    config=json.loads(CONFIG_JSON)
    results = tabulateMapServices(srcFC,config,messages)
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
    assert layerResults['attributes'][0]['classes'][2]['intersectedQuantity']==7670.2750505796675

    layerResults=results['services'][0]['layers'][4]
    assert layerResults['layerID']==3
    assert layerResults['pixelArea']==0.090000000000000011
    assert layerResults['geometryType']=="pixel"
    assert layerResults['sourcePixelCount']==3
    assert layerResults['intersectionCount']==3
    assert layerResults['intersectionQuantity']==0.18000000000000002
    assert layerResults['values'][0]['value']==2
    assert layerResults['values'][0]['count']==1
    assert layerResults['values'][0]['quantity']==0.090000000000000011

    layerResults=results['services'][0]['layers'][6]
    assert layerResults['classes'][0]['count']==1
    assert layerResults['classes'][0]['class']==[0,300]
    assert layerResults['classes'][0]['quantity']==0.090000000000000011

    layerResults=results['services'][0]['layers'][7]
    assert layerResults['statistics']['MAX']==313.635009765625
    assert layerResults['statistics']['MIN']==292.23501586914062
    assert layerResults['statistics']['MEAN']==303.50234985351562
    assert layerResults['statistics']['STD']==8.7732744216918945
    assert layerResults['statistics']['SUM']==910.50701904296875


def test_tabulateMapServices_polygon_aoi_central_america():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POLYGON_JSON_CENTRAL_AMERICA))
    config=json.loads(CONFIG_JSON_CENTRAL_AMERICA)
    results = tabulateMapServices(srcFC,config,messages)
    #print json.dumps(results,indent=1)

    assert results['sourceGeometryType']=="polygon"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==0
    assert layerResults['intersectedGeometryType']=="polygon"
    assert layerResults['intersectedCount']==9
    assert layerResults['intersectionGeometryType']=="polygon"
    assert layerResults['intersectionCount']==9
    assert layerResults['attributes'][0]['attribute']=="GEZ_TERM"
    assert layerResults['attributes'][0]['values'][0]['intersectedCount']==4
    assert layerResults['attributes'][0]['values'][0]['intersectionQuantity']==19246.689564213193
    assert layerResults['attributes'][0]['values'][0]['value']=="Tropical mountain system"

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['sourcePixelCount']==6690
    assert layerResults['intersectionCount']==6690
    assert layerResults['intersectionQuantity']== 143628.12
    assert layerResults['classes'][0]['count']==1258
    assert layerResults['classes'][0]['class']==[0,50]
    assert layerResults['classes'][0]['quantity']==26327.594158200533

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['statistics']['MAX']==183.0
    assert layerResults['statistics']['MIN']==12.5
    assert layerResults['statistics']['MEAN']==80.069999999999993
    assert layerResults['statistics']['STD']==37.490000000000002
    assert layerResults['statistics']['SUM']==535765.0
    assert layerResults['statistics']['WEIGHTED_MEAN']==79.469999999999999
    assert layerResults['statistics']['WEIGHTED_STD']==38.149999999999999
    assert layerResults['statistics']['WEIGHTED_MIN']==0
    assert layerResults['statistics']['WEIGHTED_MAX']==179.5
    assert layerResults['statistics']['WEIGHTED_SUM']==509571.08000000002


def test_tabulateMapServices_line_aoi_central_america():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(LINE_JSON_CENTRAL_AMERICA))
    config=json.loads(CONFIG_JSON_CENTRAL_AMERICA)
    results = tabulateMapServices(srcFC,config,messages)
    #print json.dumps(results,indent=1)

    assert results['sourceGeometryType']=="line"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==0
    assert layerResults['intersectedGeometryType']=="polygon"
    assert layerResults['intersectedCount']==5
    assert layerResults['intersectionGeometryType']=="line"
    assert layerResults['intersectionCount']==5
    assert layerResults['attributes'][0]['attribute']=="GEZ_TERM"
    assert layerResults['attributes'][0]['values'][0]['intersectedCount']==1
    assert layerResults['attributes'][0]['values'][0]['intersectionQuantity']==16.155867114599076
    assert layerResults['attributes'][0]['values'][0]['value']=="Tropical mountain system"

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['sourcePixelCount']==209
    assert layerResults['intersectionCount']==209
    assert layerResults['intersectionQuantity']== 4464.8999999999996
    assert layerResults['classes'][0]['count']==56
    assert layerResults['classes'][0]['class']==[0,50]
    assert layerResults['classes'][0]['quantity']==21.863926123641736

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['statistics']['MAX']==163.5
    assert layerResults['statistics']['MIN']==22.0
    assert layerResults['statistics']['MEAN']==74.319999999999993
    assert layerResults['statistics']['STD']==37.539999999999999
    assert layerResults['statistics']['SUM']==15458.5
    assert layerResults['statistics']['WEIGHTED_MEAN']==64.989999999999995


def test_tabulateMapServices_point_aoi_central_america():
    messages = MessageHandler(logger=logger)
    arcpy.Delete_management("IN_MEMORY/")
    srcFC = FeatureClassWrapper(createFeatureClass(POINT_JSON_CENTRAL_AMERICA))
    config=json.loads(CONFIG_JSON_CENTRAL_AMERICA)
    results = tabulateMapServices(srcFC,config,messages)
    print json.dumps(results,indent=1)

    assert results['sourceGeometryType']=="point"
    assert results['services'][0]['serviceID']=="test_central_america"
    assert len(results['services'][0]['layers'])==3

    layerResults=results['services'][0]['layers'][0]
    assert layerResults['layerID']==0
    assert layerResults['intersectedCount']==1
    assert layerResults['intersectedQuantity']==25787.598236210717
    assert layerResults['intersectionCount']==1
    assert layerResults['attributes'][0]['attribute']=="GEZ_TERM"
    assert layerResults['attributes'][0]['value']=="Tropical mountain system"

    layerResults=results['services'][0]['layers'][1]
    assert layerResults['layerID']==1
    assert layerResults['pixelArea']==21.465867327051889
    assert layerResults['geometryType']=="pixel"
    assert layerResults['sourcePixelCount']==1
    assert layerResults['intersectionCount']==1
    assert layerResults['intersectionQuantity']==layerResults['pixelArea']
    assert layerResults['method']=="approximate"
    assert len(layerResults['classes'])==4
    assert layerResults['classes'][3]['count']==1
    assert layerResults['classes'][3]['class']==[100,150]
    assert layerResults['classes'][3]['quantity']==layerResults['pixelArea']

    layerResults=results['services'][0]['layers'][2]
    assert layerResults['statistics']['MAX']==137.5
    assert layerResults['statistics']['MIN']==137.5
    assert layerResults['statistics']['MEAN']==137.5
    assert layerResults['statistics']['STD']==0.0
    assert layerResults['statistics']['SUM']==137.5



messages = MessageHandler(logger=logger)
arcpy.Delete_management("IN_MEMORY/")
srcFC = FeatureClassWrapper(createFeatureClass(POINT_JSON_CENTRAL_AMERICA))
config=json.loads("""
{"services":[
    {"serviceID":"test_central_america","layers":[
        {"layerID":1,"classes":[[0,50],[50,100],[100,150],[150,200]]}
    ]}
]}

""")
results = tabulateMapServices(srcFC,config,messages)
print json.dumps(results,indent=1)
