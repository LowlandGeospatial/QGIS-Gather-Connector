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
from dataclasses import dataclass

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QObject, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import QgsProject, QgsVectorLayer, QgsJsonExporter, QgsProcessingFeedback, Qgis
import json
import http.client
import base64

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .gather_connect_dialog import GatherConnectorDialog
import os.path

HOST = "eu-west-1.aws.data.mongodb-api.com"
LIST_PROJECTS_URL = "/app/gatherapplication-mgejo/endpoint/listprojects"
PROJECT_URL = "/app/gatherapplication-mgejo/endpoint/project?id="
FEATURE_URL = "/app/gatherapplication-mgejo/endpoint/feature?id="
GET_FILE_URL = "/app/gatherapplication-mgejo/endpoint/file?name="


@dataclass
class Message:
    """
    A message to be handled by GatherConnector.msg_user
    properties are the parameters accepted by:
    https://api.qgis.org/api/classQgsMessageBar.html#ab018174e31107764e654d50292ef1f3a
    TODO pass Message direct to QgsMessageBar.pushMessage?

    @param title: gist of it
    @param text:  main message content
    @param level: one of:
        1. Info
        2. Warning
        3. Critical
        4. Success
    """
    title: str
    text: str
    level: int = Qgis.Info
    duration: int = None

    def __post_init__(self):
        if self.duration is None:
            self.duration = 5

    def as_list(self):
        return [self.title, self.text, self.level, self.duration]


class Fetch:
    """ Request data return response """
    @staticmethod
    def request(host, url, headers, payload='', verb="GET"):
        conn = http.client.HTTPSConnection(host)
        conn.request(verb, url, payload, headers)
        res = conn.getresponse()
        return res


class Worker(QObject):
    """A worker will complete a task and return the result"""

    finished = pyqtSignal(object)

    def __init__(self, task):
        super().__init__()
        self.task = task

    def run(self):
        result = self.task()
        self.finished.emit(result)


class TaskManager:
    """Manages workers: gives them a task and thread to work in. Connects the result to handler on complete"""

    def __init__(self, set_btns_enabled):
        self.thread = None
        self.worker = None
        self.set_btns_enabled = lambda: set_btns_enabled(True)

    def run_thread(self, task, handle_result):
        # Instantiates thread & worker
        self.thread = QThread()
        self.worker = Worker(task)
        self.worker.moveToThread(self.thread)

        # Sets task ago, awaits finish
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)

        # Kills thread & worker (don't tell HR)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Handles result
        self.thread.finished.connect(self.set_btns_enabled)
        self.worker.finished.connect(handle_result)
        self.thread.start()


class GatherCloud:
    """ Manages calls to the API """

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.project_list = []

    def fetch_project_list(self):
        """
        lists Gather projects available to user

        @return: [projects]
        """
        headers = {
            'email': self.email,
            'password': self.password
        }
        res = Fetch.request(host=HOST, url=LIST_PROJECTS_URL, headers=headers)
        self.project_list = json.loads(res.read().decode())
        return self.project_list

    def fetch_project(self, selected_project):
        """
        Fetches project geojson

        @param selected_project: Project to fetch
        @return: project geojson
        """
        id = [p['id'] for p in self.project_list if p['name'] == selected_project][0]
        res = Fetch.request(
            host=HOST,
            url=PROJECT_URL + id,
            headers={
                'email': self.email,
                'password': self.password
            }
        )
        project_data = json.loads(res.read().decode())

        return project_data

    def download_project_files(self, selected_project, folder):
        """
        Downloads files associated with features in a project

        @param selected_project: project name
        @param folder: download path
        @return: Success/Fail Message
        """
        # get project
        if not folder:
            return Message("Error", "Project folder doesn't exist!", Qgis.Warning)
        project_local_folder = folder + "/" + selected_project

        project_data = self.fetch_project(selected_project)
        fc = 0
        for feature in project_data['features']:
            if "files" not in feature['properties']:
                continue
            for file in feature['properties']['files']:
                fc += 1
                res = Fetch.request(
                    host=HOST,
                    url=GET_FILE_URL + file['name'],
                    headers={
                        'email': self.email,
                        'password': self.password
                    }
                )
                data = res.read()
                if not os.path.exists(project_local_folder):
                    os.makedirs(project_local_folder)
                with open(project_local_folder + "/" + file['name'], "wb") as f:
                    f.write(base64.b64decode(data))

        return Message("Success", f"{str(fc)} files downloaded", Qgis.Success)

    def download_project(self, selected_project, dwnld_path):
        """
        Downloads a project as geojson

        @param selected_project: project name
        @param dwnld_path: path to geojson file
        @return: (project name, download path)
        """
        project_data = self.fetch_project(selected_project)
        with open(dwnld_path, 'w') as f:
            json.dump(project_data, f)
        return selected_project, dwnld_path

    def add_fc_to_project(self, project_name, layer_name, project_id, fc):
        """
        Adds a featureclass to a project

        @param project_name: project to which you wish to add a layer
        @param layer_name: name of layer to add
        @param project_id: id of project to add layer to
        @param fc: geojson featureclass of the layer being added
        @return: Success/fail Message
        """
        try:
            payload = json.dumps({"name": layer_name, "geojson": fc})
            res = Fetch.request(verb="POST", host=HOST, url=FEATURE_URL + project_id, payload=payload, headers={
                'email': self.email,
                'password': self.password,
                'Content-Type': 'application/json'
            })
            result = json.loads(res.read().decode())
        except Exception as ex:
            return Message('Failed', str(ex), Qgis.Critical)
        if result['success']:
            return Message(
                "Success",
                f"Added {str(result['featureCount'])} features and {str(result['formCount'])} forms to {project_name}",
                Qgis.Success
            )
        else:
            return Message("Failed", str(result['error']), Qgis.Critical)


class GatherConnector:
    """ The QGIS Plugin UI"""

    def __init__(self, iface):
        """Constructor.

        @param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        @type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # Initialise plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # Initialise locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GatherConnector_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Gather Connector')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        # attributes
        self.dlg = None
        self.gather_cloud = None
        self.logger = QgsProcessingFeedback()
        self.push_msg = self.iface.messageBar().pushMessage
        self.task_manager = TaskManager(self.set_btns_enabled)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        @param message: String for translation.
        @type message: str, QString

        @return: Translated version of message.
        @rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GatherConnector', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        @param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        @type icon_path: str

        @param text: Text that should be shown in menu items for this action.
        @type text: str

        @param callback: Function to be called when the action is triggered.
        @type callback: function

        @param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        @type enabled_flag: bool

        @param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        @type add_to_menu: bool

        @param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        @type add_to_toolbar: bool

        @param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        @type status_tip: str

        @param parent: Parent widget for the new action. Defaults None.
        @type parent: QWidget

        @param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        @return: The action that was created. Note that the action is also
            added to self.actions list.
        @rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/gather_connect/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Connect to Gather'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Gather Connector'),
                action)
            self.iface.removeToolBarIcon(action)

    def next_tab(self):
        """ Moves screen to next tab on the UI """

        cur_index = self.dlg.tabWidget.currentIndex()
        if cur_index < len(self.dlg.tabWidget)-1:
            self.dlg.tabWidget.setCurrentIndex(cur_index+1)

    def prev_tab(self):
        """ Moves screen to previous tab on the UI """

        cur_index = self.dlg.tabWidget.currentIndex()
        if cur_index > 0:
            self.dlg.tabWidget.setCurrentIndex(cur_index-1)

    def log(self, msg):
        """ Logs to QGIS console (QgsProcessingFeedback) """

        self.logger.pushConsoleInfo(msg)

    def msg_user(self, msg):
        """
        Alerts user (iface.messageBar)
        TODO not required if Message can be passed direct to messageBar().pushMessage
         """

        self.push_msg(msg.title, msg.text, msg.level, msg.duration)

    def login(self):
        """
        Instantiates Cloud Handler class with login deets
        then fetches project list
        then enables btns on login

        @return: success/fail message
        """

        try:
            self.gather_cloud = GatherCloud(
                self.dlg.emailInput.toPlainText(),
                self.dlg.passwordInput.toPlainText()
            )
            project_list = self.gather_cloud.fetch_project_list()
            names = [p['name'] for p in project_list]
            self.dlg.projectDropdown.clear()
            self.dlg.projectDropdown.addItems(names)
            self.next_tab()
            self.set_btns_enabled(True)
            return Message("Welcome", str(self.dlg.emailInput.toPlainText()), Qgis.Success)
        except:
            self.set_btns_enabled(False, include_login_btn=True)
            return Message("Error", "Login failed: "+str(project_list['error']), Qgis.Warning)

    def get_local_project_folder(self):
        """
        Gets the user inputted local project folder path & validates

        @return the folder path
        """

        project_local_folder = str(self.dlg.projectFolderInput.toPlainText())
        if not os.path.exists(project_local_folder):
            return False
        return project_local_folder

    def refresh_qgis_layers(self):
        """ Fetch the currently loaded layers """

        layers = QgsProject.instance().mapLayers().values()

        project_names = []
        if len(self.gather_cloud.project_list) > 0:
            project_names = [p['name'] for p in self.gather_cloud.project_list]
        self.dlg.layerDropdown.clear()
        vector_layer_names = [l.name()
                              for l in layers
                              if l.type() == QgsVectorLayer.VectorLayer and not l.name() in project_names]
        self.dlg.layerDropdown.addItems(vector_layer_names)

    @staticmethod
    def add_to_qgis(layer_name, file):
        """
        Load layer into QGIS, removes outdated layer by layer_name

        @param layer_name: name for new layer
        @param file: local path to GIS file
        """

        # remove old layers
        for layer in QgsProject.instance().mapLayersByName(layer_name):
            QgsProject.instance().removeMapLayer(layer.id())

        # load to qgis
        geom_types = ['|geometrytype=LineString', '|geometrytype=Polygon', '|geometrytype=Point']
        for gtype in geom_types:
            vlayer = QgsVectorLayer(file+gtype, layer_name, "ogr")
            QgsProject.instance().addMapLayer(vlayer)

    def handle_load_project(self):
        """ Fetches project selected in the dropdown and loads into QGIS """

        selected_project = str(self.dlg.projectDropdown.currentText())
        project_local_folder = self.get_local_project_folder()
        if not project_local_folder:
            self.msg_user(Message("Error", "Project folder doesn't exist!", Qgis.Warning))
            return
        project_file_path = project_local_folder + '/' + selected_project + '.geojson'
        self.log(f"loading project {selected_project} to {project_file_path}")
        self.set_btns_enabled(False)
        self.task_manager.run_thread(
            task=lambda: self.gather_cloud.download_project(
                selected_project=selected_project,
                dwnld_path=project_file_path
            ),
            handle_result=lambda result: self.add_to_qgis(*result)
        )

        self.msg_user(Message("Loading", selected_project, Qgis.Success))

    def handle_add_layer_to_project(self):
        """ Adds selected (dropdown) layer to selected (dropdown) project """

        if self.dlg.layerDropdown.currentText() == "" or self.dlg.layerDropdown.currentText() == None:
            self.msg_user(Message("Error", "no layer selected", Qgis.Warning))
            self.set_btns_enabled(True)
            return

        self.msg_user(Message(
            "Uploading",
            f"{str(self.dlg.layerDropdown.currentText())} to {str(self.dlg.projectDropdown.currentText())}",
            Qgis.Info
        ))
        self.set_btns_enabled(False)

        project_id = [p['id'] for p in self.gather_cloud.project_list if p['name'] == str(self.dlg.projectDropdown.currentText())][0]
        layers = QgsProject.instance().mapLayersByName(str(self.dlg.layerDropdown.currentText()))
        if layers:
            layer = layers[0]
        else:
            self.msg_user(Message("Oops", f"{str(self.dlg.layerDropdown.currentText())} not found", Qgis.Warning))
            self.set_btns_enabled(True)
            return

        exp = QgsJsonExporter(layer)
        fc = json.loads(exp.exportFeatures(layer.getFeatures()))
        self.task_manager.run_thread(
            task=lambda: self.gather_cloud.add_fc_to_project(
                project_name=str(self.dlg.projectDropdown.currentText()),
                project_id=project_id,
                layer_name=str(self.dlg.layerDropdown.currentText()),
                fc=fc
            ),
            handle_result=lambda message: self.msg_user(message)
        )

    def select_folder(self):
        """ Folder path selection dialog """
        folderpath = QFileDialog.getExistingDirectory(self.dlg, 'Select Local Project Folder')
        self.dlg.projectFolderInput.setPlainText(folderpath)

    def set_btns_enabled(self, state=True, include_login_btn=True):
        """ Prevents user meddling whilst they should be waiting """

        if include_login_btn:
            self.dlg.loginButton.setEnabled(state)
        self.dlg.syncButton.setEnabled(state)
        self.dlg.loadProjectButton.setEnabled(state)
        self.dlg.downloadButton.setEnabled(state)
        self.dlg.refreshLayersButton.setEnabled(state)
        self.dlg.refreshProjectButton.setEnabled(state)
        self.dlg.addLayerButton.setEnabled(state)
        self.dlg.folderButton.setEnabled(state)
        self.dlg.projectDropdown.setEnabled(state)
        self.dlg.layerDropdown.setEnabled(state)

    def handle_download_files(self):
        """ Downloads files associated with selected (dropdown) project """

        selected_project = str(self.dlg.projectDropdown.currentText())
        folder = self.get_local_project_folder()
        self.msg_user(Message("Downloading files", selected_project))
        self.set_btns_enabled(False)
        self.task_manager.run_thread(
            task=lambda: self.gather_cloud.download_project_files(
                selected_project=selected_project,
                folder=folder
            ),
            handle_result=lambda msg: self.msg_user(msg)
        )

    def run(self):
        """Creates UI, handles clicks"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = GatherConnectorDialog()
            self.set_btns_enabled(state=False, include_login_btn=False)

        # show the dialog
        self.dlg.show()

        if self.dlg.emailInput.toPlainText() == "" or self.dlg.emailInput.toPlainText() == "":
            self.prev_tab()

        self.dlg.loginButton.clicked.connect(lambda: self.task_manager.run_thread(
            task=self.login,
            handle_result=lambda msg: self.msg_user(msg)
        ))
        self.dlg.loadProjectButton.clicked.connect(self.handle_load_project)
        self.dlg.downloadButton.clicked.connect(self.handle_download_files)
        self.dlg.addLayerButton.clicked.connect(self.handle_add_layer_to_project)
        self.dlg.refreshLayersButton.clicked.connect(self.refresh_qgis_layers)
        self.dlg.folderButton.clicked.connect(self.select_folder)
        self.dlg.syncButton.clicked.connect(lambda: self.msg_user(Message("Hold on", "yet to implement")))

