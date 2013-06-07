import tempfile, os, arcpy, shutil, time, re,settings
from glob import glob

class TemporaryWorkspace:
    """
    Manage a temporary workspace, including GDB
    """

    def __init__(self):
        self.tmpDir = tempfile.mkdtemp()#"d:/temp"#TODO
        print "Allocated temporary directory: ", self.tmpDir
        self.gdb = None

    def getDirectory(self):
        return self.tmpDir

    def getGDB(self):
        if not self.gdb:
            self.gdb = os.path.join(self.tmpDir, "temp.gdb")
            if not arcpy.Exists(self.gdb):
                path, gdbName = os.path.split(self.gdb)
                arcpy.CreateFileGDB_management(path, gdbName)
        return self.gdb

    def delete(self):
        """
        Attempt to remove directory.  ArcGIS may be holding a lock on files within the directory, so continue to try up to 30 seconds
        """

        if not os.path.exists(self.tmpDir):
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
                    print("Removing directory failed: " + self.tmpDir)
                    return False
                if i == 0:
                    arcpy.AddMessage("Error removing directory %s. Will retry for up to %d seconds." % (self.tmpDir,timeout))
                time.sleep(1)
                i += 1


def getMXDPathForService(serviceID):
    #return self.svcMXDs[serviceID]
    if settings.ARCGIS_VERSION=="10.0":
        configFilename=os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,"%s.MapServer.cfg"%(serviceID))
        if not os.path.exists(configFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configFilename))
        infile=open(configFilename)
        xml=infile.read()
        infile.close()
        return re.search("(?<=<FilePath>).*?(?=</FilePath>)",xml).group().strip()

    elif settings.ARCGIS_VERSION=="10.1": #Not yet tested!
        from xml.etree import ElementTree
        configFilename=os.path.join(settings.ARCGIS_SVC_CONFIG_DIR,"%s.MapServer/esriinfo/manifest/manifest.xml"%(serviceID))
        if not os.path.exists(configFilename):
            raise ReferenceError("Map service config file not found: %s, make sure the service is published and serviceID is valid"%(configFilename))
        xml = ElementTree.parse(configFilename)
        return xml.getroot().find("Resources/SVCResource/ServerPath").text.strip().replace(".msd",".mxd")

