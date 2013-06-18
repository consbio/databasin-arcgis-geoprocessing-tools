.. Data Basin ArcGIS Geoprocessing Tools documentation master file, created by
   sphinx-quickstart on Sat Jun 15 21:39:57 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Data Basin ArcGIS Geoprocessing Tools
=================================================================

These geoprocessing tools were created to help support spatial analysis and other operations in `Data Basin <http://databasin.org/>`_.


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
* ArcGIS Server 10.0 to 10.1, including spatial analyst extension
* Published map services containing data to be operated against


Installation
============
ArcGIS 10.0
-----------
1. Place the source files in a directory for which ArcGIS Server has at least read access.
2. Update settings in settings.py
3. Publish the toolbox "tools.tbx" as a geoprocessing service with the name "databasin_arcgis_geoprocessing_tools"
    * set "Execution Type" to Asynchronous
    * enable the "Show Messages" checkbox
4. Clear the ArcGIS REST API cache (../rest/admin ->Clear Cache options ->  Clear Cache Now)


ArcGIS 10.1
-----------
TODO


Known Limitations
=================
* A limited range of spatial projections are supported for target calculations and source map services, due to the ArcGIS
  requirement of including a geographic transformation to project between many different projections.  Currently only continent-scale projections and geographic transformations
  are included with these tools.  Additional transformations can be added to utilities/ProjectionUtilities.py
* Tool execution times vary with the number of layers, complexity of geometries, and extent of analysis.  Expect analysis
  of several complex layers over larger areas to be slower.



Authors
=======
`Conservation Biology Institute <http://consbio.org/>`_ developers:

* `Mike Gough <http://consbio.org/people/staff/mike-gough>`_
* `Brendan Ward <http://consbio.org/people/staff/brendan-ward>`_

Contact: databasinadmin at consbio dot org


License
=======
Copyright (c) 2013, Conservation Biology Institute

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of the Conservation Biology Institute nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.



