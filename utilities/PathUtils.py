"""
General path utilities for workspaces and routing to map documents behind map services
"""


import tempfile, os, arcpy, shutil, time, re,settings
from glob import glob


class TemporaryWorkspace:
    """
    Wrapper for scratch workspace and scratch geodatabase, if available (e.g., when executed as a geoprocessing service).
    Otherwise, creates a temporary directory and geodatabase.
    """

    def __init__(self):
        """
        Set the temporary directory, creating it if necessary.
        """

        self._managed=True
        self.gdb = None
        self.tmpDir = None
        if arcpy.env.scratchWorkspace:
            self._managed=False
            scratchDir,extension=os.path.splitext(arcpy.env.scratchWorkspace)
            scratchGDB=os.path.join(scratchDir,"scratch.gdb")
            if extension.lower()==".gdb":
                self.gdb=arcpy.env.scratchWorkspace
            elif os.path.exists(scratchGDB):
                self.gdb=scratchGDB
            self.tmpDir=scratchDir
        else:
            self.tmpDir = os.path.normpath(tempfile.mkdtemp())

    def getDirectory(self):
        """
        Return the temporary directory.
        """

        return self.tmpDir

    def getGDB(self):
        """
        Return the temporary geodatabase, creating it if necessary.
        """

        if not self.gdb:
            self.gdb = os.path.join(self.tmpDir, "temp.gdb")
            if not arcpy.Exists(self.gdb):
                path, gdbName = os.path.split(self.gdb)
                arcpy.CreateFileGDB_management(path, gdbName)
        return self.gdb

    def delete(self):
        """
        Attempt to remove directory.  ArcGIS may be holding a lock on files within the directory, so continue to try up to 30 seconds.
        If lock files are a persistent problem, make sure that all appropriate references to arcpy objects are being deleted within code
        """

        if not (self._managed and os.path.exists(self.tmpDir)):
            return True
        startTime = time.time()
        timeout=10 #timeout is 10 seconds
        i = 0
        while True:
            try:
                shutil.rmtree(self.tmpDir)
                return True
            except OSError, e:
                if (time.time() - startTime) > timeout:
                    arcpy.AddMessage("Error removing temporary directory : %s" % (str(e)))
                    return False
                if i == 0:
                    arcpy.AddMessage("Error removing directory %s. Will retry for up to %d seconds." % (self.tmpDir,timeout))
                time.sleep(1)
                i += 1
        self.gdb=None
        self.tmpDir=None


#Deprecated
def getMXDPathForService(serviceID):
    """
    Find the path to the map document behind a running map service.  Assumes that services are local.  Location to base directory
    for finding map service configuration file is in settings.py: ARCGIS_SVC_CONFIG_DIR

    Note: this is deprecated; use getDataPathsForService() instead.

    :param serviceID: from URL: /arcgis/rest/services/<serviceID>/MapServer
    """

    if settings.ARCGIS_VERSION=="10.0":
        configFilename=os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,"%s.MapServer.cfg"%(serviceID))
        if not os.path.exists(configFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configFilename))
        infile=open(configFilename)
        xml=infile.read()
        infile.close()
        return os.path.normpath(re.search("(?<=<FilePath>).*?(?=</FilePath>)",xml).group().strip())

    elif settings.ARCGIS_VERSION=="10.1":
        import json
        configJSONFilename=os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,"%s.MapServer/%s.MapServer.json"%(serviceID,serviceID))
        if not os.path.exists(configJSONFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configJSONFilename))
        configJSON=json.loads(open(configJSONFilename))
        return os.path.normpath(configJSON['properties']['filePath'])


def extractLayerPathFromMSDLayerXML(msd,xmlPath):
    '''
    Extracts layer data source from layer XML files stored in MSD.

    Note: only tested with ArcGIS 10.1 MSDs

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
    configJSONFilename=os.path.normpath(os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,servicePath,"%s.MapServer/%s.MapServer.json"%(serviceID,serviceID)))

    if settings.ARCGIS_VERSION=="10.0":
        configFilename=os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,servicePath,"%s.MapServer.cfg"%(serviceID))
        if not os.path.exists(configFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configFilename))
        infile=open(configFilename)
        xml=infile.read()
        infile.close()
        mapDocPath = os.path.normpath(re.search("(?<=<FilePath>).*?(?=</FilePath>)",xml).group().strip())
        mapDoc = arcpy.mapping.MapDocument(mapDocPath)
        for layer in arcpy.mapping.ListLayers(mapDoc, "*", arcpy.mapping.ListDataFrames(mapDoc)[0]):
            if layer.isGroupLayer:
                layers.append(None)
            else:
                layers.append(layer.dataSource)
        del mapDoc


    elif settings.ARCGIS_VERSION=="10.1": #Not yet tested!
        import json
        from xml.etree.ElementTree import fromstring
        from zipfile import ZipFile

        #json file contains pointer to MSD file
        configJSONFilename=os.path.normpath(os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,"%s.MapServer/%s.MapServer.json"%(serviceID,serviceID)))
        if not os.path.exists(configJSONFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configJSONFilename))

        configJSON=json.loads(open(configJSONFilename).read())
        msdPath=os.path.normpath(configJSON['properties']['filePath'])
        msd=ZipFile(msdPath)
        #doc info file contains pointer to layers XML file
        layersXMLPath=fromstring(msd.open("DocumentInfo.xml").read()).findtext("ActiveMapRepositoryPath").replace("CIMPATH=","")
        layers=extractLayerPathFromMSDLayerXML(msd,layersXMLPath)
        layers.pop(0) #remove the root node for the map document
        msd.close()

    return layers
