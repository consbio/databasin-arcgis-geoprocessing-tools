#ArcGIS Version (if not set from Envr variable)
#Path to ArcGIS install (if not from Envr var)
#Temp dir & gdb

import os

#on 10.1, var in windows is AGSSERVER
#on 10.0, java this is :AGSSERVERJAVA

ARCGIS_VERSION="10.0" #Valid options are 10.0, 10.1 (prior versions not supported by tools)

#The directory that contains the configuration files for each map service
ARCGIS_SVC_CONFIG_DIR=r"C:\Program Files (x86)\ArcGIS\Server10.0\server\user\cfg" #Version 10.0
#ARCGIS_SVC_CONFIG_DIR=r"C:\arcgisserver\config-store\services" #Version 10.1