"""
Environment settings
"""

#The directory that contains the configuration files for each map service
ARCGIS_SVC_CONFIG_DIR="/opt/arcgis/server/usr/config-store"

#Location of the log file.  Server process needs to have file system permissions to write to that directory.
LOG_FILENAME = "/var/log/databasin/databasin_gp_tools/databasin_gp_tools.log"
LOG_LEVEL = "DEBUG" #Valid options are DEBUG, INFO, ERROR (or any other level supported by logging package)

