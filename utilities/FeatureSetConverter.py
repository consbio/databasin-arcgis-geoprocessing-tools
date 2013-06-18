"""
Converts a featureset in JSON into a feature class in memory
"""


import arcpy,os,json
arcpy.env.overwriteOutput =True


################# Globals ###########################
esriFieldTypesMap=dict()
esriFieldTypesMap["esriFieldTypeString"]="TEXT"
esriFieldTypesMap["esriFieldTypeGlobalID"]="GUID"
esriFieldTypesMap["esriFieldTypeGUID"]="GUID"
esriFieldTypesMap["esriFieldTypeSmallInteger"]="SHORT"
esriFieldTypesMap["esriFieldTypeInteger"]="LONG"
esriFieldTypesMap["esriFieldTypeSingle"]="FLOAT"
esriFieldTypesMap["esriFieldTypeDouble"]="DOUBLE"
esriFieldTypesMap["esriFieldTypeDate"]="DATE"
esriFieldTypesMap["esriFieldTypeOID"]="LONG"



def getFeatureGeometry(geomType,geometry):
    """
    Extract geometry from featureset JSON, and convert into geometry representation required for feature class.

    :param geomType: ArcGIS JSON geometry type: esriGeometryPoint, esriGeometryMultipoint, esriGeometryPolyline, esriGeometryPolygon
    :param geometry: the geometry object extracted from JSON
    """

    if geomType=="esriGeometryPoint":
        return arcpy.Point(geometry["x"],geometry["y"])
    elif geomType=="esriGeometryMultipoint":
        array=arcpy.Array()
        for coordinate in geometry["points"]:
            array.add(arcpy.Point(coordinate[0],coordinate[1]))
        return arcpy.Multipoint(array)
    elif geomType=="esriGeometryPolyline":
        arrays=arcpy.Array()
        for path in geometry["paths"]:
            array=arcpy.Array()
            for coordinate in path:
                array.add(arcpy.Point(coordinate[0],coordinate[1]))
            arrays.add(array)
        return arcpy.Polyline(arrays)
    elif geomType=="esriGeometryPolygon":
        #make sure that inner rings are handled correctly
        arrays=arcpy.Array()
        for path in geometry["rings"]:
            array=arcpy.Array()
            for coordinate in path:
                array.add(arcpy.Point(coordinate[0],coordinate[1]))
            arrays.add(array)
        return arcpy.Polygon(arrays)
    else:
        raise Exception("GEOMETRY_TYPE_NOT_IMPLEMENTED: This geometry type is not implemented %s"%(geomType))



def createFeatureClass(featureSet,name="drawingFC"):
    """
    Create an in-memory feature class from a featureset JSON.

    :param featureSet: the featureset JSON string.
    :param name: name of output feature class (always in memory)

    .. note:: the original feature IDs (FID / OBJECTID) are not preserved in feature class, as they are built up fresh
        during construction of feature class.
    """

    srcFeatureJSON=json.loads(featureSet)
    geomType=srcFeatureJSON["geometryType"]
    srcFeatures=srcFeatureJSON["features"]
    fieldsJSON=srcFeatureJSON["fields"]

    #set the projection to be web mercator?  want to create the return dataset in WGS84
    sr = arcpy.SpatialReference()
    sr.factoryCode = int(srcFeatureJSON["spatialReference"]["wkid"])
    sr.create()

    drawingFC="IN_MEMORY/%s"%(name)

    #create dataset
    if arcpy.Exists(drawingFC):
        arcpy.Delete_management(drawingFC)
    path,fcName=os.path.split(drawingFC)
    arcpy.CreateFeatureclass_management(path,fcName, geomType.replace("esriGeometry",""),"","","",sr)

    #add fields
    fields=[]
    for fieldJSON in fieldsJSON:              
        fieldType=esriFieldTypesMap[fieldJSON["type"]]               
        name=fieldJSON["name"]
        alias=fieldJSON["alias"]
        fieldLength=""
        fieldPrecision=""
        fieldScale=""
        if fieldJSON.has_key("length"):
            fieldLength=int(fieldJSON["length"])

        if not name in ("FID","OBJECTID"):
            arcpy.AddField_management(drawingFC,name,fieldType,fieldPrecision,fieldScale,fieldLength,alias)
            fields.append(name)
                                   
    rows=arcpy.InsertCursor(drawingFC)
    ID=1
    for feature in srcFeatures:
        row=rows.newRow()
        row.shape=getFeatureGeometry(geomType,feature["geometry"])
        for name in fields:
            row.setValue(name,feature["attributes"][name])
        rows.insertRow(row)
        ID+=1
    del row,rows

    return drawingFC

