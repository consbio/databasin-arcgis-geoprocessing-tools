.. _tabulate:

=============
Tabulate Tool
=============

This tool tabulates various summary values for feature or raster datasets within an area of interest.  The area of
interest can be represented as one or more points, lines, or polygons (limited to one type of geometry per analysis).

For raster analysis, the area of interest is converted to a raster dataset with the same resolution as the target raster
(pixel calculations are not based on partial pixels); thus it is necessary to compare the area of interest in pixels against the
summary area returned for the target raster.  Pixel areas are based on the native projection area of the target raster (assumed to be more accurate), if
it is in a projected spatial reference; otherwise pixel areas are based on the area of a pixel within the target projection.


**Available summaries include:**

*Feature layers*

* area or length and count of features inside area of interest
* area or length of features that intersected area of interest (the total area or length of the original feature both inside and outside area of interest)
* area or length and count of features by unique attribute values
* area or length and count of features by classes of a continuous attribute
* statistics of a continuous attribute inside area of interest: MIN, MAX, SUM, MEAN

*Faster layers*

* area and pixel count of area of interest in resolution of target raster
* area and pixel count of raster inside area of interest
* area and pixel count of unique values of a raster or raster attribute inside area of interest
* area and pixel count of classes of a continuous raster or raster attribute inside area of interest
* statistics of raster or continuous attribute inside area of interest. Valid statistics are: MIN, MAX, SUM, MEAN, STD (standard deviation)


Inputs
======
**featureSetJSON:**
    Area of interest represented as an ArcGIS FeatureSet in JSON format::

        {
            "fields": [{"alias": "OBJECTID", "type": "esriFieldTypeOID", "name": "OBJECTID"}],
            "geometryType": "esriGeometryPolygon",
            "features": [
                {
                    "geometry": {
                        "rings": [
                            [
                                [-12510743.8804,3962356.0276999995],
                                [-12500772.095800001,3955536.6137000024],
                                [-12509264.1962,3945822.1655000001],
                                [-12510936.8827,3944921.4880999997],
                                [-12513381.578299999,3946015.1677000001],
                                [-12517112.955699999,3957466.636500001],
                                [-12514925.5965,3960040.0002999976],
                                [-12510743.8804,3962356.0276999995]
                            ]
                        ]
                    },
                    "attributes": {"OBJECTID": 3}
                }
            ],
            "spatialReference": {"wkid": 102100,"latestWkid": 3857}
        }



**configJSON:**
    The list of map services, layers, and summary methods::

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


    For each map service, provide the serviceID (from the map service URL, this is /arcgis/rest/services/<serviceID>/MapServer), and the layer configuration.

    For each layer, provide the layerID (this can be determined from looking at the list of layers for the map service in ArcGIS REST API).
    If no other parameters are given for layer, only the total area or length and count of features inside area of interest,
    and total area or length and count of features intersecting the area of interest will be returned.

    *Feature layers:*

    * To summarize by unique values of an attribute, simply include that attribute in the list of attributes::

        {"layerID":0, "attributes":[{"attribute":"NAME"}]}
    * To summarize by classes of an attribute, include the attribute and list of class value ranges (greater than or equal to first value, and less than second value)::

        {"layerID":0, "attributes":[{"attribute":"NAME", "classes":[ [0,10], [10,20], [20,30] ]}]}
    * To return summary statistics of an attribute, list the desired statistics::

        {"layerID":0,"attributes":[{"attribute":"POP2000","statistics":["MIN","MAX","MEAN","SUM"] }]}


      .. note:: statistics option is mutually exclusive of above options


    *Raster layers:*

    * Categorical rasters will be summarized by unique value if no additional parameters are provided, continuous ones will not::

        {"layerID":3}
    * To summarize by classes of the raster, simply include class ranges at layer level::

        {"layerID":5, "classes":[ [0,300],[300,310],[310,400] ]}
    * To return summary statistics of raster, simply include statistics at layer level::

        {"layerID":5, "statistics":["MIN","MAX","MEAN","SUM"]}
    * Attribute-level summaries are same as above



**targetProjectionWKID:**
    The target projection ESRI Well-Known ID (WKID).

    :Example: 102003

    .. note:: only limited projections are supported due to ArcGIS requirement for geographic transformations between
     the source and target projections (see utilities/ProjectionUtilities.py for supported geographic transformations)



Outputs
=======
During execution, the tool will add a progress message for each completed layer and service.  The format is: PROGRESS [PERCENT_COMPLETE]


**resultsJSON:**
    JSON results follow similar format as configJSON above.

    *Key concepts:*

    * Very little is returned if no intersection is found.  Generally only count properties will be returned in this case.
    * Areas and lengths are returned using the general "quantity" properties.
      Use the geometryType properties to determine what units these represent.  Quantities will not be returned for points.
    * An important distinction is made between intersected and intersection results for features:

        **Intersection:** the portion of the features *WITHIN* the area of interest.  This will be in the units of the intersection.

        **Intersected:** the original features that intersected the area of interest, *INCLUDING* the area of length inside and
        outside the area of interest.  This will be in the units of the original intersected features.
        This is useful for calculating the percentage of the original features that are within the area of interest.


    Results for examples above::

        {
            "area_units": "hectares", #area values are always in hectares
            "linear_units": "kilometers", #linear values are always in kilometers
            "sourceGeometryType": "polygon", #point, line, or polygon
            "services": [{"serviceID": "test",
                    "layers": [
                        {
                            #a point feature layer
                            "layerID": 0,
                            "intersectionGeometryType": "point", #will be point, line, polygon, or pixel (raster)
                            "intersectedCount": 2,  #number of features that INTERSECTED area of interest
                            "intersectedGeometryType": "point",
                            "intersectionCount": 2  #number of featues WITHIN area of interest
                        },
                        {
                            "layerID": 0,
                            "intersectedGeometryType": "point",
                            "intersectedCount": 2,
                            "attributes": [
                                {
                                    #a categorical attribute
                                    "attribute": "NAME",
                                    "values": [
                                        {"intersectedCount": 1,"intersectionCount": 1,"value": "Avondale"},
                                        {"intersectedCount": 1,"intersectionCount": 1,"value": "Goodyear"}
                                    ]
                                }
                            ],
                            "intersectionGeometryType": "point",
                            "intersectionCount": 2
                        },
                        {
                            "layerID": 0,
                            "intersectedGeometryType": "point",
                            "intersectedCount": 2,
                            "attributes": [
                                {
                                    #a continuous attribute
                                    "attribute": "POP2000",
                                    "statistics": {
                                        "MAX": 35883,
                                        "MIN": 18911
                                    }
                                }
                             ],
                            "intersectionGeometryType": "point",
                            "intersectionCount": 2
                        },
                        {
                            #a polygon feature layer
                            "layerID": 2,
                            "intersectionGeometryType": "polygon",
                            "intersectedGeometryType": "polygon",
                            #quantities are hectares for polygon geometry type, kilometers for line, and not present for point
                            "intersectionQuantity": 3774.3558016523793,
                            "intersectedQuantity": 7670.2729527175416,
                            "intersectedCount": 1,
                            "attributes": [
                                {
                                    #a continuous attribute
                                    "attribute": "POP2000",
                                    "classes": [
                                        {
                                            "class": [0,1000],
                                            "intersectedQuantity": 0,
                                            "intersectedCount": 0,
                                            "intersectionQuantity": 0,
                                            "intersectionCount": 0
                                        },
                                        {
                                            "class": [1000,10000],
                                            "intersectedQuantity": 0,
                                            "intersectedCount": 0,
                                            "intersectionQuantity": 0,
                                            "intersectionCount": 0
                                        },
                                        {
                                            "class": [10000,1000000],
                                            "intersectedQuantity": 7670.2729527175416,
                                            "intersectedCount": 1,
                                            "intersectionQuantity": 3774.3558016523793,
                                            "intersectionCount": 1
                                        }
                                    ]
                                }
                            ],
                            "intersectionCount": 1
                        },
                        {
                            #a categorical raster, will be summarized on unique values
                            "layerID": 3,
                            "projectionType": "native",
                            #native=areas are based on the native projection of target raster, target=areas are based on target projection
                            "intersectionPixelCount": 124796,
                            "sourcePixelCount": 124796,
                            "intersectionQuantity": 11231.639999999999,
                            "pixelArea": 0.089999999999999997,
                            "geometryType": "pixel",
                            "values": [
                                {
                                    "value": 1,
                                    "count": 24090,
                                    "quantity": 2168.0999999999999
                                },
                                {
                                    "value": 2,
                                    "count": 38736,
                                    "quantity": 3486.2399999999998
                                },
                                {
                                    "value": 3,
                                    "count": 44753,
                                    "quantity": 4027.77
                                },
                                {
                                    "value": 4,
                                    "count": 17088,
                                    "quantity": 1537.9199999999998
                                },
                                {
                                    "value": 5,
                                    "count": 129,
                                    "quantity": 11.609999999999999
                                }
                            ]
                        },
                        {
                            #a continuous raster, will only be summarized for intersection area
                            "layerID": 5,
                            "pixelArea": 0.089999999999999997,
                            "geometryType": "pixel",
                            "projectionType": "native",
                            "sourcePixelCount": 124796,
                            "intersectionQuantity": 11231.639999999999
                        },
                        {
                            "layerID": 5,
                            "pixelArea": 0.089999999999999997, #area in hectares
                            "classes": [
                                {
                                    "class": [0,300],
                                    "count": 67863,
                                    "quantity": 6107.6700000000001
                                },
                                {
                                    "class": [300,310],
                                    "count": 38677,
                                    "quantity": 3480.9299999999998
                                },
                                {
                                    "class": [310,400],
                                    "count": 18256,
                                    "quantity": 1643.04
                                }
                            ],
                            "geometryType": "pixel",
                            "projectionType": "native",
                            "sourcePixelCount": 124796,
                            "intersectionQuantity": 11231.639999999999
                        },
                        {
                            "layerID": 5,
                            "pixelArea": 0.089999999999999997,
                            "statistics": {
                                "MAX": 378.656494140625,
                                "SUM": 37146168.0,
                                "MIN": 271.205322265625,
                                "MEAN": 297.65512084960937
                            },
                            "geometryType": "pixel",
                            "projectionType": "native",
                            "sourcePixelCount": 124796,
                            "intersectionQuantity": 11231.639999999999
                        }
                    ]
                }
            ],
            "sourceFeatureQuantity": 11231.81217300969,  #area or length of area interest, if polygon or line
            "sourceFeatureCount": 1
        }



Error Handling
==============
This tool will almost always return successfully, because it is trapping and returning errors if encountered for each service and layer.
These will be include the python stacktrace of the error to assist debugging.  Additional information may be present in the
logs to indicate the problem.



