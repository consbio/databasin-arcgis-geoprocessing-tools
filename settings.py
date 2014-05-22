"""
Environment settings
"""

ARCGIS_VERSION="10.0" #Valid options are 10.0, 10.1, 10.2 (prior versions not supported by tools)
#ARCGIS_VERSION="10.1"

#The directory that contains the configuration files for each map service
ARCGIS_SVC_CONFIG_DIR=r"C:\Program Files (x86)\ArcGIS\Server10.0\server\user\cfg" #Version 10.0
#ARCGIS_SVC_CONFIG_DIR=r"C:\arcgisserver\config-store\services" #Version 10.1

LOG_FILENAME = "C:/arcgisserver/logs/tool_log.log"
LOG_LEVEL = "DEBUG" #Valid options are DEBUG, INFO, ERROR (or any other level supported by logging package)

