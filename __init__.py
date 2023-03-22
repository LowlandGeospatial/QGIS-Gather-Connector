# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GatherConnector             : Fieldwork GIS Solution (QGIS Plugin)
 Manage Gather projects      : http://LowlandGeospatial.com/Gather

        date                 : 2023-01-23
        copyright            : (C) 2023 by Lowland Geospatial
        email                : info@lowlandgeospatial.solutions
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

 This script initalises the plugin, making it known to QGIS
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load GatherConnector class from file GatherConnector.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .gather_connect import GatherConnector
    return GatherConnector(iface)
