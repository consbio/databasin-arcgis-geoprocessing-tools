"""
General path utilities for workspaces and routing to map documents behind map services
"""


import arcpy
import json
import os
import re
import logging
from xml.etree.ElementTree import fromstring
from zipfile import ZipFile

import settings

logger = logging.getLogger(__name__)


DYNAMIC_DIR_RE = re.compile(r"\${\S+}")


def get_scratch_GDB():
    return os.path.join(arcpy.env.scratchWorkspace, "scratch.gdb")


def extractLayerPathFromMSDLayerXML(msd,xmlPath):
    '''
    Extracts layer data source from layer XML files stored in MSD.

    :param msd: MSD file opened via ZipFile
    :param xmlPath: path to XML file with layerInfo
    :return: list of layer paths, or None for each group layer; index in this list = layerID
    '''

    from xml.etree.ElementTree import fromstring

    xml=fromstring(msd.open(xmlPath).read())
    layersNode=xml.find("Layers")
    layers=[]
    if layersNode is not None:
        layers.append(None) #no path
        layerXMLPaths=[node.text.replace("CIMPATH=","") for node in layersNode.findall('String')]
        for layerXMLPath in layerXMLPaths:
            layers.extend(extractLayerPathFromMSDLayerXML(msd,layerXMLPath))
    else:
        dataConnectionNode=xml.find("DataConnection")
        if dataConnectionNode is None:
            dataConnectionNode=xml.find("FeatureTable/DataConnection")
        if dataConnectionNode is not None:
            workspace=dataConnectionNode.findtext("WorkspaceConnectionString").replace("DATABASE=","")
            workspace_type=dataConnectionNode.findtext("WorkspaceFactory")
            dataset=dataConnectionNode.findtext("Dataset")
            path=os.path.join(os.path.dirname(msd.filename),workspace,dataset)
            if workspace_type=="Shapefile":
                path+=".shp"
            layers.append(os.path.normpath(path))
        else:
            raise ValueError("Could not extract layer data source from MSD XML file: %s"%(xmlPath))
    return layers


def getDataPathsForService(serviceID):
    '''
    Extract paths for data layers in map service..

    :param serviceID:
    :return: return list of layers paths (or None for group layers); order in this list = layerID
    '''

    layers=[]

    servicePath=""
    if serviceID.count("/"):
        lastIndex=serviceID.rfind("/")
        servicePath=serviceID[:lastIndex]
        serviceID=serviceID[(lastIndex+1):]

    #json file contains pointer to MSD file
    configJSONFilename=os.path.normpath(os.path.join(settings.ARCGIS_SVC_CONFIG_DIR, "services", servicePath,"%s.MapServer/%s.MapServer.json"%(serviceID,serviceID)))
    if not os.path.exists(configJSONFilename):
        raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configJSONFilename))

    configJSON=json.loads(open(configJSONFilename).read())

    filePath = configJSON['properties']['filePath']
    if DYNAMIC_DIR_RE.search(filePath):
        # Real path is injected at runtime.  Ugh!
        # Attempt to determine from server config
        dirConfig = json.loads(open(os.path.join(settings.ARCGIS_SVC_CONFIG_DIR, "serverdirs", "arcgisinput.json")).read())
        dataRootDir = dirConfig['physicalPath']
        filePath = filePath.replace(DYNAMIC_DIR_RE.search(filePath).group(), dataRootDir)


    msdPath=os.path.normpath(filePath)
    msd=ZipFile(msdPath)
    #doc info file contains pointer to layers XML file
    layersXMLPath=fromstring(msd.open("DocumentInfo.xml").read()).findtext("ActiveMapRepositoryPath").replace("CIMPATH=","")
    layers=extractLayerPathFromMSDLayerXML(msd,layersXMLPath)
    layers.pop(0) #remove the root node for the map document
    msd.close()

    return layers
