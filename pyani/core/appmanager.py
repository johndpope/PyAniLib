import zipfile
import os
import sys
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

    @property
    def user_version(self):
        """The version the user has installed
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
        features = ", ".join(self.__app_data["versions"][0]["features"])
        return "There is a newer version ({0}) of this app. The latest version offers: {1}. " \
               "Do you want to update now?".format(latest_version, features)

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


class AniAppMngrGui(QtWidgets.QMainWindow):
    def __init__(self, version):
        super(AniAppMngrGui, self).__init__()

        self.version = version

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

        # window helpers
        self.win_utils = pyani.core.ui.QtWindowUtil(self)
        self.msg_win = pyani.core.ui.QtMsgWindow(self)
        # setup main window
        self.setWindowTitle('Py Ani Tools App Manager')
        self.win_utils.set_win_icon("Resources\\app_update.png")
        # main widget for window
        self.main_win = QtWidgets.QWidget()
        # main ui elements - styling set in the create ui functions
        self.btn_update = QtWidgets.QPushButton("Update App")
        self.btn_install = QtWidgets.QPushButton("Install / Update App(s)")
        self.btn_launch = QtWidgets.QPushButton("Launch App(s)")
        # format for ui display
        app_ui_text, app_ui_colors = self._format_app_info()
        # build tree
        self.app_tree = pyani.core.ui.CheckboxTree(self.app_names,
                                                   formatted_categories=app_ui_text,
                                                   colors=app_ui_colors)

        self.build_ui()
        # set default window size
        self.resize(600, 400)

    def build_ui(self):
        """Builds the UI widgets, slots and layout
        """

        self.create_ui()
        self.set_slots()
        # set main window
        self.setCentralWidget(self.main_win)

    def create_ui(self):
        # set font size and style for title labels
        titles = QtGui.QFont()
        titles.setPointSize(14)
        titles.setBold(True)

        # spacer to use between sections
        v_spacer = QtWidgets.QSpacerItem(0, 35)
        empty_space = QtWidgets.QSpacerItem(1, 1)

        # begin layout
        main_layout = QtWidgets.QVBoxLayout()

        # add version to right side of screen
        vers_label = QtWidgets.QLabel("Version {0}".format(self.version))
        h_layout_vers = QtWidgets.QHBoxLayout()
        h_layout_vers.addStretch(1)
        h_layout_vers.addWidget(vers_label)
        main_layout.addLayout(h_layout_vers)
        main_layout.addItem(v_spacer)

        # APP HEADER SETUP -----------------------------------
        # |    label    |   space    |     btn     |      btn       |     space    |
        g_layout_header = QtWidgets.QGridLayout()
        header_label = QtWidgets.QLabel("Applications")
        header_label.setFont(titles)
        g_layout_header.addWidget(header_label, 0, 0)
        g_layout_header.addItem(empty_space, 0, 1)
        self.btn_launch.setMinimumSize(150, 30)
        g_layout_header.addWidget(self.btn_launch, 0, 2)
        self.btn_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_install.setMinimumSize(150, 30)
        g_layout_header.addWidget(self.btn_install, 0, 3)
        g_layout_header.addItem(empty_space, 0, 4)
        g_layout_header.setColumnStretch(1, 2)
        g_layout_header.setColumnStretch(4, 2)
        main_layout.addLayout(g_layout_header)
        main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # APPS TREE  -----------------------------------
        main_layout.addWidget(self.app_tree)

        # set main windows layout as the stacked layout
        self.main_win.setLayout(main_layout)

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_install.clicked.connect(self.install)
        self.btn_launch.clicked.connect(self.launch)

    def install(self):
        """Installs the app(s) and updates ui info
        """
        apps, tree_items = self._get_selection()
        for index, app in enumerate(apps):
            app.install()
            current_text = tree_items[index]
            new_text = ("{0}\t\t{1}".format(app.app_name, app.user_version))
            self.app_tree.update_item(current_text, new_text)

    def launch(self):
        """Launches the app(s)
        """
        apps, null = self._get_selection()
        for app in apps:
            exe_path = os.path.join(app.app_install_path, app.app_name)
            pyani.core.util.launch_app("{0}.exe".format(exe_path))

    def _get_selection(self):
        """
        Gets and parses the selected apps in the tree
        :return: a list of the selected tree items as AniAppMngr objects, and a list of the tree text items
        """
        selection = self.app_tree.get_tree_checked()
        # remove formatting '\t\tVersion'
        app_names = [item.split("\t")[0] for item in selection]
        apps = []
        for app_name in app_names:
            for app_mngr in self.app_mngrs:
                if app_name == app_mngr.app_name:
                    apps.append(app_mngr)
        return apps, selection

    def _format_app_info(self):
        """
        formats app information for the ui
        :return: a list of formatted app info, a list of corresponding colors for the info
        """
        formatted_info = []
        colors = {}

        for app in self.app_mngrs:
            # app not installed
            if app.user_version is None:
                formatted_info.append("{0}\t\tNot Installed".format(app.app_name))
                colors[app.app_name] = {"parent": pyani.core.ui.RED}
            # if users version is out of date color orange
            elif not app.user_version == app.latest_version:
                formatted_info.append("{0}\t\t{1}".format(app.app_name, app.user_version))
                colors[app.app_name] = {"parent": pyani.core.ui.YELLOW}
            # app up to date
            else:
                formatted_info.append("{0}\t\t{1}".format(app.app_name, app.user_version))
                colors[app.app_name] = {"parent": QtCore.Qt.white}

        return formatted_info, colors
