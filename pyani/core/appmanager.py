import zipfile
import os
import signal
import psutil
import pyani.core.util
import pyani.core.ui

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


class AniAppMngr(object):
    """
    Class to manage an app. Does installs and updates
    """
    def __init__(self, app_name):
        # these are the same for all apps
        self.__app_data_path = "C:\\PyAniTools\\app_data\\"
        self.__updater_app = "C:\\PyAniTools\\installed\\PyAppMngr.exe"
        # per app variables
        self.__app_name = app_name
        self.__app_install_path = "C:\\PyAniTools\\installed\\{0}".format(app_name)
        self.__app_exe = "{0}.exe".format(self.app_name)
        self.__app_package = "C:\\PyAniTools\\packages\\{0}.zip".format(self.app_name)
        self.__user_config = os.path.abspath("{0}\\app_pref.json".format(self.app_install_path))
        self.__app_config = os.path.abspath("{0}{1}\\app_data.json".format(self.app_data_path, self.app_name))
        self.__user_data = pyani.core.util.load_json(self.user_config)
        self.__app_data = pyani.core.util.load_json(self.app_config)
        self.__user_version = self.user_version
        self.__latest_version = self.latest_version
        self.__features = ", ".join(self.__app_data["versions"][0]["features"])

    @property
    def user_version(self):
        """The version the user has installed.
        """
        # user may not have app, check
        if self.__user_data:
            return self.__user_data["version"]
        else:
            return None

    @property
    def latest_version(self):
        """The version on the server
        """
        return self.__app_data["versions"][0]["version"]

    @property
    def updater_app(self):
        """The file path to the python updater script
        """
        return self.__updater_app

    @property
    def app_exe(self):
        """The app executable name
        """
        return self.__app_exe

    @property
    def app_package(self):
        """The app zip file
        """
        return self.__app_package

    @property
    def app_data_path(self):
        """The path to where application data lives - non user specific
        """
        return self.__app_data_path

    @property
    def app_name(self):
        """The name of the app
        """
        return self.__app_name

    @property
    def app_install_path(self):
        """The file path to the app.exe on the users computer
        """
        return self.__app_install_path

    @property
    def user_config(self):
        """The user's preference file
        """
        return self.__user_config

    @property
    def app_config(self):
        """The app config file
        """
        return self.__app_config

    @property
    def features(self):
        """The feature release list
        """
        return self.__features

    def verify_paths(self):
        """Verify app exists and install path exists
        :return Error if encountered, None if no errors
        """
        if not os.path.exists(self.app_package):
            return "Application package could not be found: {0}".format(self.app_package)
        if not os.path.exists(self.app_install_path):
            return "Application install could not be found: {0}".format(self.app_install_path)
        return None

    def install(self, has_pref=False):
        """Installs the latest version of the app
        :param has_pref : boolean whether app has preferences
        :return Error if encountered, None if no errors
        """
        error = self.unpack_app(self.app_package, self.app_install_path)

        if error:
            return error

        # create user preference file
        if has_pref:
            self._create_user_preferences()

        # update the user version, in case it has changed
        self._update_user_version()

        return None

    @staticmethod
    def unpack_app(package, install_path):
        """
        Unzip a zip file with an application  inside
        :param package: the zip file containing the package
        :param install_path: the place to unzip

        """
        try:
            with zipfile.ZipFile(file=package) as zipped:
                zipped.extractall(path=install_path)
                print package, install_path
        except zipfile.BadZipfile:
            return "{0} update file is corrupt.".format(package)

    @staticmethod
    def kill_process(pid):
        """
        Stop a running process
        :param pid: the process id
        :return: exception if there is one, None otherwise
        """
        try:
            os.kill(pid, signal.SIGINT)
        except Exception as exc:
            return exc
        return None

    @staticmethod
    def find_processes_by_name(name):
        """
        Find a list of processes matching 'name'.
        :param name: the name of the process to find
        :return: the list of process ids
        """
        assert name, name
        process_list = []
        for process in psutil.process_iter():
            name_, exe, cmdline = "", "", []
            try:
                name_ = process.name()
                exe = process.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except psutil.NoSuchProcess:
                continue
            if name == name_ or os.path.basename(exe) == name:
                process_list.append(process.pid)
        return process_list

    def latest_version_info(self):
        """Returns the latest version release notes
        :return the feature list as a string
        """
        latest_version = self.__app_data["versions"][0]["version"]
        return "There is a newer version ({0}) of this app. The latest version offers: {1}. " \
               "Do you want to update now?".format(latest_version, self.features)

    def is_latest(self):
        """Checks if user has the latest version
        :return False if there is a new version, TRue if on the latest version
        """
        latest_version = self.__app_data["versions"][0]["version"]
        if not self.__user_data["version"] == latest_version:
            return False
        else:
            return True

    def _update_user_version(self):
        """Updates the user version - call after updating an app
        """
        self.__user_data = pyani.core.util.load_json(self.user_config)

    def _create_user_preferences(self):
        """Create the user preference file
        """
        app_data = pyani.core.util.load_json(self.app_config)
        latest_version = app_data["versions"][0]["version"]
        # create the user config file
        user_data = {
            "version": latest_version
        }
        pyani.core.util.write_json(self.user_config, user_data)


class AniAppMngrGui(pyani.core.ui.AniQMainWindow):
    def __init__(self):
        # build main window structure
        self.app_name = "PyAppMngr"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniAppMngrGui, self).__init__("Py Ani Tools App Manager", "Resources\\app_update.png",
                                            self.app_mngr, 800, 400)

        # list of apps
        self.app_names = pyani.core.util.load_json(
            os.path.normpath("C:\\PyAniTools\\app_data\\Shared\\app_list.json")
        )
        # list of app managers for each app
        self.app_mngrs = []
        for name in self.app_names:
            self.app_mngrs.append(
                AniAppMngr(name)
            )

        # main ui elements - styling set in the create ui functions
        self.btn_update = QtWidgets.QPushButton("Update App")
        self.btn_install = QtWidgets.QPushButton("Install / Update App(s)")
        self.btn_launch = QtWidgets.QPushButton("Launch App(s)")
        # tree app version information
        self.app_tree = pyani.core.ui.CheckboxTreeWidget(self._format_app_info(), 3)

        self.create_layout()
        self.set_slots()

    def create_layout(self):

        # APP HEADER SETUP -----------------------------------
        # |    label    |   space    |     btn     |      btn       |     space    |
        g_layout_header = QtWidgets.QGridLayout()
        header_label = QtWidgets.QLabel("Applications")
        header_label.setFont(self.titles)
        g_layout_header.addWidget(header_label, 0, 0)
        g_layout_header.addItem(self.empty_space, 0, 1)
        self.btn_launch.setMinimumSize(150, 30)
        g_layout_header.addWidget(self.btn_launch, 0, 2)
        self.btn_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_install.setMinimumSize(150, 30)
        g_layout_header.addWidget(self.btn_install, 0, 3)
        g_layout_header.addItem(self.empty_space, 0, 4)
        g_layout_header.setColumnStretch(1, 2)
        g_layout_header.setColumnStretch(4, 2)
        self.main_layout.addLayout(g_layout_header)
        self.main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # APPS TREE  -----------------------------------
        self.main_layout.addWidget(self.app_tree)

        # set main windows layout as the stacked layout
        self.add_layout_to_win()

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_install.clicked.connect(self.install)
        self.btn_launch.clicked.connect(self.launch)

    def install(self):
        """Installs the app(s) and updates ui info
        """
        apps = self._get_selection()
        for index, app in enumerate(apps):
            app.install()
            item = [app.app_name, app.user_version]
            item_color = [None, None]
            updated_item = pyani.core.ui.CheckboxTreeWidgetItem(item, item_color)
            self.app_tree.update_item(app.app_name, updated_item)

    def launch(self):
        """Launches the app(s)
        """
        apps = self._get_selection()
        for app in apps:
            exe_path = os.path.join(app.app_install_path, app.app_name)
            # pass application path and arguments, in this case none
            pyani.core.util.launch_app("{0}.exe".format(exe_path), [])

    def _get_selection(self):
        """
        Gets and parses the selected apps in the tree
        :return: a list of the selected tree items as AniAppMngr objects
        """
        selection = self.app_tree.get_tree_checked()
        apps = []
        # using selection, finds the app in app_mngr and adds to list
        for app_name in selection:
            for app_mngr in self.app_mngrs:
                if app_name == app_mngr.app_name:
                    apps.append(app_mngr)
        return apps

    def _format_app_info(self):
        """
        formats app information for the ui
        :return: a list of the tree information as a list of CheckboxTreeWidgetItems
        """
        tree_info = []
        for app in self.app_mngrs:
            # app not installed
            if app.user_version is None:
                text = [app.app_name, "Not Installed"]
                color = [pyani.core.ui.RED, pyani.core.ui.RED]
                row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
                tree_info.append({"root": row})
            # if users version is out of date color orange
            elif not app.user_version == app.latest_version:
                version_text = "{0}     ({1})".format(app.user_version, app.latest_version)
                text = [app.app_name, version_text, app.features]
                color = [pyani.core.ui.YELLOW, pyani.core.ui.YELLOW, QtCore.Qt.gray]
                row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
                tree_info.append({"root": row})
            # app up to date
            else:
                text = [app.app_name, app.user_version]
                color = None
                row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
                tree_info.append({"root": row})

        return tree_info
