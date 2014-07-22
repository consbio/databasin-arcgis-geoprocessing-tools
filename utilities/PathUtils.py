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


logger = logging.getLogger(__name__)


DYNAMIC_DIR_RE = re.compile(r"\${\S+}")
CONFIG_STORE_RE = re.compile(r'(?<=<entry key="connectionString">)\S+(?=</entry>)')
DIRECTORIES = dict()
CONFIG_STORE_KEY = "@config-store@"
ARCGIS_INPUT_DIR_KEY = "@arcgisinput@"


def _get_server_config_store():
    """
    Uses the AGSSERVER environment variable to determine the route to the config xml file with location to config-store
    """

    if CONFIG_STORE_KEY not in DIRECTORIES:
        server_dir = os.environ.get("AGSSERVER")
        filename = os.path.join(server_dir, "framework/etc/config-store-connection.xml")
        if not os.path.exists(filename):
            raise Exception("Could not access arcgis server config xml at: %s" % filename)

        config_store_dir = CONFIG_STORE_RE.search(open(filename).read()).group()
        DIRECTORIES[CONFIG_STORE_KEY] = config_store_dir

    return DIRECTORIES[CONFIG_STORE_KEY]


def _get_server_input_directory():
    """
    Uses the arcgisinput.json config file to determine the path to the server's default arcgisinput directory location
    """
    if ARCGIS_INPUT_DIR_KEY not in DIRECTORIES:
        filename = os.path.join(_get_server_config_store(), "serverdirs", "arcgisinput.json")
        if not os.path.exists(filename):
            raise Exception("Could not access arcgis server input directory config file at: %s" % filename)

        config = json.loads(open(filename).read())
        DIRECTORIES[ARCGIS_INPUT_DIR_KEY] = config['physicalPath']
    return DIRECTORIES[ARCGIS_INPUT_DIR_KEY]


def get_scratch_GDB():
    return os.path.join(arcpy.env.scratchWorkspace, "scratch.gdb")


def extractLayerPathFromMSDLayerXML(msd,xmlPath):
    """
    Extracts layer data source from layer XML files stored in MSD.

    :param msd: MSD file opened via ZipFile
    :param xmlPath: path to XML file with layerInfo
    :return: list of layer paths, or None for each group layer; index in this list = layerID
    """

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
    """
    Extract paths for data layers in map service.  Returns cached lookup if possible.

    :param serviceID:
    :return: return list of layers paths (or None for group layers); order in this list = layerID
    """

    if serviceID not in DIRECTORIES:
        layers=[]

        servicePath=""
        if serviceID.count("/"):
            lastIndex=serviceID.rfind("/")
            servicePath=serviceID[:lastIndex]
            serviceID=serviceID[(lastIndex+1):]

        #json file contains pointer to MSD file
        configJSONFilename=os.path.join(_get_server_config_store(), "services", servicePath,
                                        "%s.MapServer/%s.MapServer.json" % (serviceID,serviceID))
        if not os.path.exists(configJSONFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is "
                                 "published and serviceID is valid" % (configJSONFilename))

        configJSON=json.loads(open(configJSONFilename).read())
        filePath = configJSON['properties']['filePath']
        dynamic_dir_match = DYNAMIC_DIR_RE.search(filePath)
        if dynamic_dir_match:
            # Real path is injected at runtime.
            filePath = filePath.replace(dynamic_dir_match.group(), _get_server_input_directory())

        msdPath=os.path.normpath(filePath)
        msd=ZipFile(msdPath)
        #doc info file contains pointer to layers XML file
        layersXMLPath=fromstring(msd.open("DocumentInfo.xml").read()).findtext("ActiveMapRepositoryPath").replace("CIMPATH=","")
        layers=extractLayerPathFromMSDLayerXML(msd,layersXMLPath)
        layers.pop(0) #remove the root node for the map document
        msd.close()

        DIRECTORIES[serviceID] = layers

    # return layers
    return DIRECTORIES[serviceID]