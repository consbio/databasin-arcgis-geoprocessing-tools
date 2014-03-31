import arcpy
import time
import traceback
import logging
from utilities.PathUtils import getDataPathsForService
from utils import getRegionsForDatasets, ProgressListener

logger = logging.getLogger("GetGeographicRegions_mapSvc")
progressListener=ProgressListener(arcpy)


def getRegionsForMapSvc(svcID,regions):
    try:
        start=time.time()
        layerID_LUT=dict()
        sources = set()  # get the unique data sources; some layers point at the same source
        for i, layer_path in enumerate(getDataPathsForService(svcID)):
            if layer_path:
                layer = arcpy.mapping.Layer(layer_path)
                if not layer.isGroupLayer:
                    sources.add(layer.dataSource)
                    layerID_LUT[i] = layer.dataSource
        logger.debug("Calculating Geographic Index: "+svcID)
        arcpy.AddMessage("Calculating Geographic Index: "+svcID)
        intersectedRegions,containedRegions=getRegionsForDatasets(sources,regions,progressListener)
        logger.debug("Calculated Geographic Index for Map Service: intersected %s regions, contained %s regions; took %.2f seconds"%(len(intersectedRegions),len(containedRegions),time.time()-start ))

        results=[]
        layerIDs=layerID_LUT.keys()
        layerIDs.sort()
        for layerID in layerIDs:
            results.append({"layerOrder":layerID,
            "intersectedRegions":list(intersectedRegions[layerID_LUT[layerID]]),
            "containedRegions":list(containedRegions[layerID_LUT[layerID]])})
        return results
    
    except:
        logger.error(traceback.format_exc())
        arcpy.AddError(traceback.format_exc())
        print traceback.format_exc()