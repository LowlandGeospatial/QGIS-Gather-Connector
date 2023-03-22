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
"""
import json
import os.path
import unittest
import tempfile

from gather_connect import Fetch
from gather_connect import GatherCloud

PROJECT_IDX = os.environ["PROJECT_IDX"]
PROJECT_ID = os.environ["PROJECT_ID"]
NUM_FEATS = os.environ["NUM_FEATS"]
EMAIL = os.environ['EMAIL']
PASSWORD = os.environ['PASSWORD']

class Testing(unittest.TestCase):
    def test_fetch(self):
        res = Fetch.request(host="swapi.dev", url="/api/planets/1/", headers={})
        planet = json.load(res)
        self.assertEqual(planet['name'], "Tatooine")

    def test_cloud(self):
        # get all projects
        cloud = GatherCloud(EMAIL, PASSWORD)
        projects = cloud.fetch_project_list()
        with self.subTest():
            self.assertEqual(projects[PROJECT_IDX]['id'], PROJECT_ID)

        # get project by name
        project_name = projects[PROJECT_IDX]['name']
        project = cloud.fetch_project(selected_project=project_name)
        with self.subTest():
            self.assertEqual(len(project['features']), NUM_FEATS)

        # download project by name
        folder = tempfile.gettempdir()
        dwnld_path = os.path.join(folder, project_name + ".geojson")
        downloaded_project_name, result_file = cloud.download_project(selected_project=project_name, dwnld_path=dwnld_path)
        with self.subTest():
            self.assertTrue(os.path.exists(result_file))

        # download project files
        result = cloud.download_project_files(selected_project=project_name, folder=folder)
        files = os.listdir(os.path.join(folder, project_name))

        with self.subTest():
            self.assertEqual(result.title, "Success")
        with self.subTest():
            self.assertTrue(files[0].endswith(".jpg"))


if __name__ == '__main__':
    unittest.main()