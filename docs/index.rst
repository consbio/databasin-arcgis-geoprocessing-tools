.. Data Basin ArcGIS Geoprocessing Tools documentation master file, created by
   sphinx-quickstart on Sat Jun 15 21:39:57 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Data Basin ArcGIS Geoprocessing Tools
=================================================================

These geoprocessing tools were created to help support spatial analysis and other operations in `Data Basin <http://databasin.org/>`_.

Source code available in `Bitbucket <https://bitbucket.org/databasin/databasin_arcgis_geoprocessing_tools/>`_.


These tools are intended to be deployed as geoprocessing services on an ArcGIS Server that also hosts map services (their data must be hosted locally).
Within Data Basin, these services are accessed via server middleware to route to and control the number of jobs per
ArcGIS server.  Custom-built client code (HTML/JS/CSS) is used to provide the user interface to these tools, and manages
generation of input parameters, and display of output results.

However, most of the internal functions only rely on arcpy and access to the input data, and thus could be executed from
other environments.

Refer to the specific tools below for more information:

.. toctree::
   :maxdepth: 1

   tabulate



Supporting modules:

.. toctree::
    :maxdepth: 1

    logging_messaging
    utilities


Requirements
============
* ArcGIS Server 10.2.x, including spatial analyst extension
* Published map services containing data to be operated against


Installation - ArcGIS 10.2.x
============================

.. note::
   This tool must be deployed to the root folder, with the name "databasin_arcgis_geoprocessing_tools" to properly
   work with Data Basin.


Pre-packaged versions
---------------------

These easiest way to install this tool is to deploy the latest service definition file from the `downloads page <https://bitbucket.org/databasin/databasin_arcgis_geoprocessing_tools/downloads/>`_

Simply download, and then upload to your ArcGIS server.  This version comes with a pointer back to the source Mercurial
repository - develop branch (see below).


Packaging and deploying yourself
--------------------------------

Use the ArcGIS server command line tool `ags_tool_deploy <https://bitbucket.org/databasin/ags_tool_deploy/>`_ to help
manage the deployment process.  Install per the instructions in that repository.

Download the latest development snapshot from `develop branch <https://bitbucket.org/databasin/databasin_arcgis_geoprocessing_tools/get/develop.zip/>`_
or the latest stable version from `master branch <https://bitbucket.org/databasin/databasin_arcgis_geoprocessing_tools/get/master.zip/>`_

Then, from a command within the directory containing tools.pyt::

<python_packages_dir>/arcgis_tool_deploy/deploy.py publish tools.pyt databasin_arcgis_geoprocessing_tools <hostname> <admin_username> --password=<admin_password>


use ``--overwrite`` if you want to delete and replace and existing service of the same name.


**Managing with Mercurial:**

.. note:: This assumes Mercurial is installed on your server.

Given the active development and bugfixes on this tool, and the challenges in deploying to ArcGIS server, you can also
clone this repository to your local machine using mercurial, and include basic repository information when you deploy
the tool to ArcGIS server.  This allows you to pull new updates directly to the ArcGIS server instead of having to
redeploy the tool.

Use the ``--hg`` option above to include Mercurial repository information.

Then from within the installed location on the ArcGIS server reported using the publish command above, simply run
``hg pull --update`` to update to the latest changes in the branch you used above (make sure you are on ``develop`` for
the latest changes or ``master`` for the latest stable changes.

.. note:: this will overwrite your settings file.  Make sure to update it (below).

Once you have pulled and updated to the latest changes, simply restart the geoprocessing service.


Configuration
=============

Once you have installed this package, you will need to configure ``settings.py`` to point to the correct folder locations
on your server.  Please make sure that the ArcGIS server process has write permissions on the location of the log file.

Unless you are editing the source code and packaging yourself (above), you will need to edit the this file from its
installed location on ArcGIS server.  For us, this is:
``/opt/arcgis/server/usr/directories/arcgissystem/arcgisinput/databasin_arcgis_geoprocessing_tools.GPServer/extracted/v101/settings.py``

This will need to be done each time you deploy a new version of the tool because the ArcGIS deployment process deletes
the previously deployed files.


Testing
=======

Because this set of tools is built to run on ArcGIS server against running map services, it is necessary to execute the
tests in the same environment.

First, deploy this tool and make sure it is properly installed.

Second, deploy the test data from the `downloads page <https://bitbucket.org/databasin/databasin_arcgis_geoprocessing_tools/downloads/>`_
as a map service called ``arcgis_geoprocessing_tools_test_data``

Next, execute the tool at ``http://<server_hostname>/arcgis/rest/services/databasin_arcgis_geoprocessing_tools/GPServer/test_tabulate``

This will run the test suite as if it were a stand-alone geoprocessing tool.  It will run through a variety of tests.
If those tests fail, make sure to check your configuration in ``settings.py``





Known Limitations
=================
* Tabulate tool is very slow due primarily to the implementation of the projection function in ArcGIS (arcpy).  Work is
  underway to refactor out as many steps where tool is reprojecting data as is possible.
* A limited range of spatial projections are supported for target calculations and source map services, due to the ArcGIS
  requirement of including a geographic transformation to project between many different projections.  Currently only
  continent-scale geographic transformations are included with these tools.  Additional transformations can be added to
  utilities/ProjectionUtilities.py
* Tool execution times vary with the number of layers, complexity of geometries, and extent of analysis.  Expect analysis
  of several complex layers over larger areas to be slower.
* Path routing to ArcGIS layer data sources will not work for enterprise geodatabases.




Authors
=======
`Conservation Biology Institute <http://consbio.org/>`_ developers:

* `Mike Gough <http://consbio.org/people/staff/mike-gough>`_
* `Brendan Ward <http://consbio.org/people/staff/brendan-ward>`_

Contact: databasinadmin at consbio dot org


License
=======
Copyright (c) 2014, Conservation Biology Institute

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of the Conservation Biology Institute nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.



