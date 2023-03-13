# Gather connector

Manage [fieldwork conducted with Gather](https://www.lowlandgeospatial.com/gather) using  [QGIS Desktop](https://www.qgis.org/en/site/)  via the **Gather Connector Plugin.**

* **Add layers to projects for access in the field**, automatically generate forms from attribute tables. _Add an area of interest (red line boundary) for a survey_.
* **Load projects from your mobile devices**, with real-time access to all features, photos and files. _Begin analysing data as soon as your surveyor logs a feature_.


_Rather be in the field than at your desk? Contact [Lowland Geospatial](mailto:info@lowlandgeospatial.solutions)_.


## Installation

### Production
1. Via QGIS
	```qgis
	Plugins > Manage and Install Plugins > Search "Gather Connector" > Install Plugin
### Development
1. Open plugins folder via QGIS
   ```qgis
   Settings > User Profiles > Open Active Profile Folder > python > plugins
   ```
2. Clone the repo
   ```sh
   git clone https://github.com/LowlandGeospatial/QGIS-Gather-Connector.git
   ```
3. _Restart QGIS_


4. Open Shell
   ```OSGeo4W 
   Start > OSGeo4W Shell
   ```
5. Run tests
   ```OSGeo4W 
   %PYTHONHOME%/python.exe C:/path/to/QGIS-Gather-Connector/test_connect.py
   ```

## License

[GPLv2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
