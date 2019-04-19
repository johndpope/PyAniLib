import zipfile
import os
import signal
import pyani.core.util
import logging
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.mayapluginsmngr
from pyani.core.toolsinstall import AniToolsSetup

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore


logger = logging.getLogger()


class AniAppMngr(object):
    """
    Class to manage an app. Does installs and updates
    """
    def __init__(self, app_name):
        self.__log = []

        # used to update app data and apps, and get any new apps.
        self.tools_setup = AniToolsSetup()
        # just using show vars, no sequence or shot vars
        self.ani_vars = pyani.core.anivars.AniVars()

        # these are the same for all apps
        self.__app_data_path = "C:\\PyAniTools\\app_data\\"
        self.__updater_app = "C:\\PyAniTools\\installed\\PyAppMngr\\PyAppMngr.exe"
        # per app variables
        self.__app_name = app_name
        self.__app_doc_page = "http://172.18.10.11:8090/display/KB/{0}".format(self.app_name)
        self.__tools_install_dir = "C:\\PyAniTools\\installed"
        self.__app_install_path = "{0}\\{1}".format(self.tools_install_dir, app_name)
        self.__app_exe = "{0}.exe".format(self.app_name)
        self.__app_package = "C:\\PyAniTools\\packages\\{0}.zip".format(self.app_name)
        self.__user_config = os.path.abspath("{0}\\app_pref.json".format(self.app_install_path))
        self.__app_config = os.path.abspath("{0}{1}\\app_data.json".format(self.app_data_path, self.app_name))
        # load data from json files and log error if one occurs
        self.__user_data = pyani.core.util.load_json(self.user_config)
        if not isinstance(self.__user_data, dict):
            self.__log.append(self.__user_data)
            logger.error(self.__user_data)
            self.__user_data = None
        self.__app_data = pyani.core.util.load_json(self.app_config)
        if not isinstance(self.__app_data, dict):
            self.__log.append(self.__app_data)
            logger.error(self.__app_data)
            self.__app_data = None

        # try to set user version
        if self.__user_data:
            self.__user_version = self.__user_data["version"]
        else:
            self.__user_version = None
        # try to get latest version
        if self.__app_data:
            self.__latest_version = self.__app_data["versions"][0]["version"]
        else:
            self.__latest_version = None
        # try to get release notes
        if self.__app_data:
            self.__features = ", ".join(self.__app_data["versions"][0]["features"])
        else:
            self.__features = None

    @property
    def log(self):
        """Log of errors as list
        """
        return self.__log

    @property
    def app_doc_page(self):
        """Address Url of application documentation
        """
        return self.__app_doc_page

    @property
    def user_version(self):
        """The version the user has installed.
        """
        return self.__user_version

    @property
    def tools_install_dir(self):
        """Location where tools are installed
        """
        return self.__tools_install_dir

    @property
    def latest_version(self):
        """The version on the server
        """
        return self.__latest_version

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
        """The apps features or release notes list
        """
        return self.__features

    def install(self):
        """Installs the latest version of the app
        :return Error if encountered, None if no errors
        """
        # remove the existing app
        if os.path.exists(self.app_package) and zipfile.is_zipfile(self.app_package):
            error = pyani.core.util.rm_dir(self.app_install_path)
            if error:
                return error
            # unzip new app files
            error = self.unpack_app(self.app_package, self.app_install_path)
            if error:
                return error

            self._update_user_version()

            return None
        else:
            error = "The zip file {0} is invalid or does not exist, cannot install_apps.".format(self.app_package)
            logging.error(error)
            return error

    @staticmethod
    def unpack_app(package, install_path):
        """
        Unzip a zip file with an application  inside
        :param package: the zip file containing the package
        :param install_path: the place to unzip
        :return error if encountered, otherwise None

        """
        try:
            with zipfile.ZipFile(file=package) as zipped:
                zipped.extractall(path=install_path)
            return None
        except (zipfile.BadZipfile, zipfile.LargeZipFile, IOError, OSError) as e:
            error = "{0} update file is corrupt. Error is {1}".format(package, e)
            logger.exception(error)
            return error

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

    def is_latest(self):
        """Checks if user has the latest version
        :return False if there is a new version, True if on the latest version. Returns None if the app data isn't
        loaded
        """
        if isinstance(self.__app_data, dict):
            latest_version = self.__app_data["versions"][0]["version"]
            if not self.__user_data["version"] == latest_version:
                return False
            else:
                return True
        else:
            return None

    def _update_user_version(self):
        """Updates the user version - call after updating an app
        """
        self.__user_data = pyani.core.util.load_json(self.user_config)
        self.__user_version = self.__user_data["version"]

    def download_update(self, skip_update_check=False):
        """
        Downloads the files from cgt.
        :param skip_update_check: whether to only download the update if its newer.
        :return True if downloaded, False if no updates to download, error if encountered.
        """
        # update
        return self.tools_setup.download_updates(skip_update_check=skip_update_check)

    def install_update(self):
        """
        Installs downloaded files from cgt.
        :return If successful returns None, otherwise returns error
        """
        # MAKE MAIN DIRECTORY ON C DRIVE --------------------------------------------
        error, created = self.tools_setup.make_install_dirs()
        if error:
            return error

        # APP DATA -------------------------------------------------------------------
        error = self.tools_setup.update_app_data()
        if error:
            return error

        # SETUP PACKAGES ------------------------------------------------------------
        error = self.tools_setup.update_packages()
        if error:
            return error

        # SETUP APPS ---------------------------------------------------------------
        # first install_apps
        if not os.path.exists(self.tools_setup.app_vars.apps_dir):
            error, created_shortcuts = self.tools_setup.add_all_apps()
            if error:
                return error
        # already installed
        else:
            error, new_apps = self.tools_setup.add_new_apps()
            if error:
                return error

        # NUKE --------------------------------------------------------------------
        # first check for .nuke  folder in C:Users\username
        error, created = self.tools_setup.make_nuke_dir()
        if error:
            return error

        # check for  custom nuke folder in .nuke
        error, created = self.tools_setup.make_custom_nuke_dir()
        if error:
            return error

        # copy custom init.py, menu.py, and .py (script with python code to support menu and gizmos)
        # Note: remove the files first, copy utils seem to not like existing files
        error = self.tools_setup.copy_custom_nuke_init_and_menu_files()
        if error:
            return error
        # finally update the init.py - only append, don't want to lose existing code added by user
        error, added_plugin_path = self.tools_setup.add_custom_nuke_path_to_init()
        if error:
            return error

        # update sequence list
        error = self.tools_setup.update_show_info()
        if error:
            return "Sequence List Update Failed. Error is {0}".format(error)

        # update install_apps date
        error = self.tools_setup.set_install_date()
        if error:
            return error


class AniAppMngrGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for app manager. Shows installed apps, versions, and updates if available.
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """
    def __init__(self, error_logging):
        self.log = []

        # build main window structure
        self.app_name = "PyAppMngr"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniAppMngrGui, self).__init__(
            "Py App Manager",
            "Resources\\pyappmngr_icon.ico",
            self.app_mngr,
            800,
            400,
            error_logging
        )

        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # save the setup class for error logging to use later
        self.error_logging = error_logging

        # tabs class object
        self.tabs = pyani.core.ui.TabsWidget(tab_name="PyAniTools", tabs_can_close=False)

        self.task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_update",
            os.path.join(self.app_mngr.tools_install_dir, "PyAniToolsUpdate.exe")
        )

        # app vars
        self.app_vars = pyani.core.appvars.AppVars()

        # path to json file containing list of py ani tool apps and maya plugins
        tools_list_json_path = self.app_vars.tools_list

        # INIT FOR PYANITOOLS
        # ---------------------------------------------------------------------
        # list of apps and app mngrs
        self.app_mngrs = self._create_app_mngrs(tools_list_json_path)
        # main ui elements for pyanitools - styling set in the create ui functions
        self.btn_update = QtWidgets.QPushButton("Update App")
        self.btn_install = QtWidgets.QPushButton("Install / Update App(s)")
        self.btn_launch = QtWidgets.QPushButton("Launch App(s)")
        self.btn_manual_update = QtWidgets.QPushButton("Update Core Data Only")
        self.btn_clean_install = QtWidgets.QPushButton("Re-Install Tools To Latest Version")
        self.auto_dl_label = QtWidgets.QLabel("")
        self.menu_toggle_auto_dl = QtWidgets.QComboBox()
        self.menu_toggle_auto_dl.addItem("-------")
        self.menu_toggle_auto_dl.addItem("Enabled")
        self.menu_toggle_auto_dl.addItem("Disabled")
        # tree app version information
        self.app_tree = pyani.core.ui.CheckboxTreeWidget(self._format_app_info(), 3)

        # INIT FOR MAYA PLUGINS
        # ---------------------------------------------------------------------
        # list of maya plugins
        self.maya_plugins = pyani.core.mayapluginsmngr.AniMayaPlugins()
        self.maya_plugins.build_plugin_data()

        self.create_layout()
        self.set_slots()

    def create_layout(self):

        self.main_layout.addWidget(self.tabs)

        pyanitools_layout = self.create_layout_pyanitools()
        self.tabs.update_tab(pyanitools_layout)

        maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
        self.tabs.add_tab("Maya Plugins", layout=maya_plugins_layout)

        self.add_layout_to_win()

    def create_layout_and_slots_maya_plugins(self):
        """
        Create the layout for the maya plugins. Lets user know if plugin not found or version not found via ui.
        :return: a pyqt layout object containing the maya plugins app management interface
        """
        maya_plugins_layout = QtWidgets.QVBoxLayout()

        header_label = QtWidgets.QLabel("Plugins")
        header_label.setFont(self.titles)
        maya_plugins_layout.addWidget(header_label)
        maya_plugins_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # make the buttons and labels for each plugin
        for plugin in sorted(self.maya_plugins.maya_plugin_data):
            # common ui elements whether plugin exists locally or not
            #
            plugin_layout = QtWidgets.QHBoxLayout()
            # add name of plugin - this is the user friendly display name
            name_label = QtWidgets.QLabel(plugin)
            plugin_layout.addWidget(name_label)
            # space between name and vers or missing plugin label
            plugin_layout.addItem(QtWidgets.QSpacerItem(50, 0))
            # download plugin button
            maya_plugins_dl_btn = pyani.core.ui.ImageButton(
                "images\download_off.png",
                "images\download_on.png",
                "images\download_off.png",
                size=(32, 32)
            )
            maya_plugins_dl_btn.setObjectName(
                "dl_{0}".format(self.maya_plugins.maya_plugin_data[plugin]["name"]))
            maya_plugins_dl_btn.clicked.connect(self.maya_plugins_download)
            # get version_data
            if self.maya_plugins.maya_plugin_data[plugin]["version data"]:
                # first element is the latest version
                version = self.maya_plugins.get_version(plugin, version="latest")
            else:
                version = "N/A"
            vers_label = QtWidgets.QLabel(version)
            plugin_layout.addWidget(vers_label)
            # space between vers and buttons
            plugin_layout.addItem(QtWidgets.QSpacerItem(150, 0))
            plugin_layout.addWidget(maya_plugins_dl_btn)

            # find where its located, local or server
            loc = self.maya_plugins.get_plugin_location(plugin)

            # check for existence
            if not os.path.exists(os.path.join(loc, self.maya_plugins.maya_plugin_data[plugin]["name"])):
                missing_label = QtWidgets.QLabel(
                    "<font color={0}>( Plugin missing )</font>".format(pyani.core.ui.RED.name())
                )
                plugin_layout.addWidget(missing_label)

            else:
                maya_plugins_vers_btn = pyani.core.ui.ImageButton(
                    "images\change_vers_off.png",
                    "images\change_vers_on.png",
                    "images\change_vers_off.png",
                    size=(24, 24)
                )
                maya_plugins_vers_btn.setObjectName("vers_{0}".format(self.maya_plugins.maya_plugin_data[plugin]["name"]))
                maya_plugins_vers_btn.clicked.connect(self.maya_plugins_change_version)

                maya_plugins_notes_btn = pyani.core.ui.ImageButton(
                    "images\\release_notes_off.png",
                    "images\\release_notes_on.png",
                    "images\\release_notes_off.png",
                    size=(24, 24)
                )
                maya_plugins_notes_btn.setObjectName(
                    "notes_{0}".format(self.maya_plugins.maya_plugin_data[plugin]["name"])
                )
                maya_plugins_notes_btn.clicked.connect(self.maya_plugins_view_release_notes)

                maya_plugins_confluence_btn = pyani.core.ui.ImageButton(
                    "images\\html_off.png",
                    "images\\html_on.png",
                    "images\\html_off.png",
                    size=(24, 24)
                )
                maya_plugins_confluence_btn.setObjectName("confluence_{0}".format(
                    self.maya_plugins.maya_plugin_data[plugin]["name"])
                )
                maya_plugins_confluence_btn.clicked.connect(self.maya_plugins_open_confluence_page)

                plugin_layout.addWidget(maya_plugins_vers_btn)
                plugin_layout.addWidget(maya_plugins_notes_btn)
                plugin_layout.addWidget(maya_plugins_confluence_btn)

            plugin_layout.addStretch(1)
            maya_plugins_layout.addLayout(plugin_layout)
            # space between rows of plugins
            maya_plugins_layout.addItem(QtWidgets.QSpacerItem(0, 20))

        maya_plugins_layout.addStretch(1)

        return maya_plugins_layout

    def create_layout_pyanitools(self):
        """
        Create the layout for the pyanitools
        :return: a pyqt layout object containing the pyanitools app management interface
        """
        pyanitools_layout = QtWidgets.QVBoxLayout()

        # APP HEADER SETUP -----------------------------------
        # |    label    |   space    |     btn     |      btn       |     space    |
        g_layout_header = QtWidgets.QGridLayout()
        header_label = QtWidgets.QLabel("Applications")
        header_label.setFont(self.titles)
        g_layout_header.addWidget(header_label, 0, 0)
        g_layout_header.addItem(self.empty_space, 0, 1)
        self.btn_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_install.setMinimumSize(175, 30)
        g_layout_header.addWidget(self.btn_install, 0, 2)
        self.btn_launch.setMinimumSize(175, 30)
        self.btn_launch.setStyleSheet("background-color:{0};".format(pyani.core.ui.CYAN))
        g_layout_header.addWidget(self.btn_launch, 0, 3)
        g_layout_header.setColumnStretch(1, 2)
        pyanitools_layout.addLayout(g_layout_header)
        pyanitools_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # APPS TREE  -----------------------------------
        pyanitools_layout.addWidget(self.app_tree)

        pyanitools_layout.addItem(self.v_spacer)

        # MANUAL DOWNLOAD OPTIONS
        g_layout_options = QtWidgets.QGridLayout()
        options_label = QtWidgets.QLabel("Tools Update Options")
        options_label.setFont(self.titles)
        g_layout_options.addWidget(options_label, 0, 0)
        g_layout_options.addItem(self.empty_space, 0, 1)
        g_layout_options.addWidget(self.btn_manual_update, 0, 2)
        self.btn_manual_update.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_manual_update.setMinimumSize(175, 30)
        g_layout_options.addWidget(self.btn_clean_install, 0, 3)
        self.btn_clean_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GOLD))
        self.btn_clean_install.setMinimumSize(175, 30)
        g_layout_options.addItem(self.empty_space, 0, 4)
        g_layout_options.setColumnStretch(1, 2)
        pyanitools_layout.addLayout(g_layout_options)
        pyanitools_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # set initial state of auto download based reset whether
        state = self.task_scheduler.is_task_enabled()
        if not isinstance(state, bool):
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not get state of task {0}. You can continue but you will not be "
                "able to enable or disable the windows task. Error is {1}".format(self.task_scheduler.task_name, state)
            )
        if state:
            state_label = "Enabled"
        else:
            state_label = "Disabled"
        self.auto_dl_label.setText(
            "Auto-download of updates from server <i>(Currently: {0})</i>".format(state_label)
        )
        h_options_layout = QtWidgets.QHBoxLayout()
        h_options_layout.addWidget(self.auto_dl_label)
        h_options_layout.addWidget(self.menu_toggle_auto_dl)
        h_options_layout.addStretch(1)
        pyanitools_layout.addLayout(h_options_layout)
        pyanitools_layout.addItem(self.v_spacer)

        return pyanitools_layout

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_install.clicked.connect(self.install_apps)
        self.btn_launch.clicked.connect(self.launch)
        self.menu_toggle_auto_dl.currentIndexChanged.connect(self.update_auto_dl_state)
        self.btn_manual_update.clicked.connect(self.update_core_files)
        self.btn_clean_install.clicked.connect(self.reinstall)

    def maya_plugins_download(self):
        """
        Downloads the plugin based off the button pressed
        """
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            # move current version to restore folder before downloading
            error = self.maya_plugins.create_restore_point(plugin)
            if error:
                self.msg_win.show_error_msg("Restore Point Error", "Could not create restore point for plugin {0}."
                                                                   "Error is {1}".format(plugin, error))
            # get the latest version
            errors = self.maya_plugins.download_plugins(plugin)
            if errors:
                logger.error("Could not download plugin {0} from CGT. Error is: {1}".format(plugin, ', '.join(errors)))
                self.msg_win.show_error_msg("Download Error", "Could not download plugin {0} from CGT".format(plugin))
            else:
                self.msg_win.show_info_msg(
                    "Plugin Downloaded", "Successfully downloaded the plugin: {0}".format(plugin)
                )
            # refresh version info in gui, a bit overkill to rebuild ui, but lightweight enough doesn't matter
            # and don't need to keep track of each plugins ui elements to update
            maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
            self.tabs.update_tab(maya_plugins_layout)
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to download".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def maya_plugins_change_version(self):
        """
        changes to a previous version. currently just support rolling back to the previous version. if previous version
        not found returns returns without doing any actions. Also returns without action if user declines the change.
        If the files can't be removed, or restored also returns but displays message to user.
        """
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            if not self.maya_plugins.retore_path_exists(plugin):
                self.msg_win.show_error_msg(
                    "Critical Error", "No restore point found for {0}.".format(plugin)
                )
                return
            release_notes = self.maya_plugins.get_release_notes(plugin, version="1")
            version = self.maya_plugins.get_version(plugin, version="1")
            response = self.msg_win.show_question_msg(
                "Version Change", "You are about to change versions to {0}. The release notes are: <br><br>{1}"
                                  "<br>Click yes to continue."
                                  .format(version, release_notes)
            )
            if response:
                error = self.maya_plugins.change_version(plugin)
                if error:
                    self.msg_win.show_error_msg(
                        "Critical Error", "Could not revert plugin to version {0}. Plugin may not function. Please "
                                          "re-download the latest version. Error is: {1}".format(version, error)
                    )
                    return
                # refresh version info in gui, a bit overkill to rebuild ui, but lightweight enough doesn't matter
                # and don't need to keep track of each plugins ui elements to update
                maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
                self.tabs.update_tab(maya_plugins_layout)
            # user canceled version change
            else:
                return
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to change version".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def get_maya_plugin_from_button_press(self, btn_pressed):
        """
        gets the plugin based off the button pressed
        :param btn_pressed: the name of the button set via setObjectName when created
        :return: the name of the plugin for that button, or None if can't be found
        """
        # find which plugin to revert
        for plugin in self.maya_plugins.maya_plugin_data:
            # find the plugin clicked
            if self.maya_plugins.maya_plugin_data[plugin]["name"] in btn_pressed:
                return plugin
        return None

    def maya_plugins_view_release_notes(self):
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            release_notes = self.maya_plugins.get_release_notes(plugin)
            # show release notes for prior version
            self.msg_win.show_info_msg(
                "Version Notes", "<b>Release Notes:</b><br><br> {0}".format(release_notes)
            )
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to view release notes".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def maya_plugins_open_confluence_page(self):
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            self.maya_plugins.open_confluence_page(plugin)
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to open confluence page".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def update_auto_dl_state(self):
        """
        Updates a windows task in the windows task scheduler to be enabled or disabled. Informs user if can't
        set the task state
        """
        if not self.menu_toggle_auto_dl.currentIndex() == 0:
            state = self.menu_toggle_auto_dl.currentText()
            if state == "Enabled":
                error = self.task_scheduler.set_task_enabled(True)
            else:
                error = self.task_scheduler.set_task_enabled(False)
            if error:
                self.msg_win.show_warning_msg(
                    "Task Scheduling Error",
                    "Could not set state of task {0}. You can continue but you will not be "
                    "able to enable or disable the windows task. Error is {1}".format(self.task_scheduler.task_name,
                                                                                      state)
                )
                self.auto_dl_label.setText(
                    "Auto-download of updates from server <i>(Currently: Unknown)</i>"
                )
            else:
                self.auto_dl_label.setText(
                    "Auto-download of updates from server <i>(Currently: {0})</i>".format(state)
                )

    def reinstall(self):
        """
        Removes the existing PyAniTools installation - shortcuts, nuke modifications, and main tools dir. Then
        downloads the tools from the CG Teamworks, and re-installs. Uses the Install Update Assistant
        (PyAniToolsIUAssist.exe) to launch PyAniToolsSetup.exe and close this app so it can get re=installed.
        See toolsinstallassist.py in pyani package for more details
        """

        # let user know windows will open and to close all existing tools, display process, and ask if they want
        # to continue
        response = self.msg_win.show_question_msg(
            "Continue Re-install Prompt",
            "<i>WARNING: This removes all existing tools and re-installs with the latest version.</i><br><br>"
            "<b>Please close any PyAniTool Apps besides this one and any Windows Explorer "
            "windows that show folders/files from C:\PyAniTools (a windows resource bug)</b><br><br> "
            "The re-installation will error if: <br><br>"
            "(a) any tools are running.<br>"
            "(b) windows explorer is showing files/folders from any folder in C:\PyAniTools. This includes "
            "the shortcuts window.<br><br>"
            "<b>Re-installation Process</b>:<br> "
            "A new window will open, and the app manager will close. The new window stages files for installation and "
            "opens the tool setup app. Once the tool setup finishes, hit close and the app manager will re-open."
        )
        # if the user selected 'yes' (True), proceed
        if response:
            # remove temp dir if exists
            if os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.rm_dir(self.app_vars.download_path_pyanitools)
                if error:
                    self.msg_win.show_error_msg("Install Staging Error", error)
                    return

            # setup directories that need to be removed, exe files to run, stage files in temp dir
            #
            # this is the exe (absolute path) to execute the setup tool in the iu assistant
            app_to_run = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.setup_exe)
            # exe (absolute path) calling assistant
            calling_app = self.app_vars.app_mngr_exe
            # path in temp dir of the assistant
            iu_assistant_app_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.iu_assist_exe)
            # path of the assistant in tools dir
            iu_assistant_app_in_tools = self.app_vars.iu_assist_path
            # what to remove
            files_and_dirs_to_remove = [
                self.app_vars.tools_dir,
                self.app_vars.tools_shortcuts,
                self.app_mngr.ani_vars.nuke_user_dir
            ]

            # download latest from cgt - will unzip to temp dir
            #
            self.progress_win.show_msg("Install in Progress", "Downloading Updates from Server. This file is several "
                                       "hundred megabytes (mb), please be patient.")
            QtWidgets.QApplication.processEvents()
            error = self.app_mngr.download_update(skip_update_check=True)
            # done loading hide window
            self.progress_win.hide()
            # not true or false, so an error occurred
            if not isinstance(error, bool):
                QtWidgets.QApplication.processEvents()
                self.msg_win.show_error_msg("Update Failed", "Could not download update. Error is :{0}.".format(error))
                return

            # copy assistant program to temp - can't run it out of C:PyAniTools since that will get removed
            if not os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.make_dir(self.app_vars.download_path_pyanitools)
                if error:
                    msg_append = "Problem staging install file. " + error
                    self.msg_win.show_error_msg("Install Staging Error", msg_append)
                    return
            error = pyani.core.util.copy_file(iu_assistant_app_in_tools, self.app_vars.download_path_pyanitools)
            if error:
                msg_append = "Problem staging install file. " + error
                self.msg_win.show_error_msg("Install Staging Error", msg_append)
                return

            # open assistant passing:
            #       path to assistant in temp dir,
            #       assist type - update core or re-install
            #       the calling app,
            #       app to run,
            #       the directories/files to remove
            #
            # assist type - update or re-install
            args = ["reinstall"]
            # the exe calling this app
            args.append(calling_app)
            # app to run - tools setup
            args.append(app_to_run)
            # files and directories to remove - a list so extend current list
            args.extend(files_and_dirs_to_remove)
            # launch assistant with the parameters
            error = pyani.core.util.launch_app(iu_assistant_app_in_temp, args, open_as_new_process=True)
            if error:
                self.msg_win.show_error_msg("Install Error", error)

    def update_core_files(self):
        """
        Update the existing PyAniTools core app files - the lib files used by nuke and cgt bridge, app packages,
        app data, Install Update assistant (PyAniToolsIUAssist.exe ) and Tools Updater (PyAniToolsUpdate.exe),
        and app manager.

        Uses the Install Update Assistant(PyAniToolsIUAssist.exe) to launch PyAniToolsUpdate.exe, which downloads the
        latest tools from the server, runs the update, then returns here. See toolsinstallassist.py in pyani package
        for more details
        """
        # let user know windows will open and to close all existing tools, display process, and ask if they want
        # to continue
        response = self.msg_win.show_question_msg(
            "Continue Update Prompt",
            "<i>This will not update the apps, only the core tool data. It will get the latest app packages and you"
            "can update using app manager once this completes.</i><br><br>"
            "<b>Please close any PyAniTool Apps besides this one and any Windows Explorer "
            "windows that show folders/files from C:\PyAniTools (a windows resource bug)</b><br><br> "
            "The update will error if: <br><br>"
            "(a) any tools are running.<br>"
            "(b) windows explorer is showing files/folders from any folder in C:\PyAniTools. This includes "
            "the shortcuts window.<br><br>"
            "<b>Update Process</b>:<br> "
            "A new window will open, and the app manager will close. The new window stages files for update and "
            "opens the tool update app. Once the tool update finishes, hit close and the app manager will re-open."
        )
        # if user pressed 'yes' (True) then proceed
        if response:
            # remove temp dir if exists
            if os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.rm_dir(self.app_vars.download_path_pyanitools)
                if error:
                    self.msg_win.show_error_msg("Update Staging Error", error)
                    return

            # setup directories that need to be removed, exe files to run, stage files in temp dir
            #
            # exe (absolute path) calling assistant
            calling_app = self.app_vars.app_mngr_exe

            # copy install / update assist tool
            #
            # copy assistant program to temp - can't run it out of C:PyAniTools since that will get removed
            if not os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.make_dir(self.app_vars.download_path_pyanitools)
                if error:
                    msg_append = "Problem staging update file. " + error
                    self.msg_win.show_error_msg("Update Staging Error", msg_append)
                    return

            # path in temp dir of the assistant
            iu_assistant_app_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.iu_assist_exe)
            # path of the assistant in tools dir
            iu_assistant_app_in_tools = self.app_vars.iu_assist_path
            error = pyani.core.util.move_file(iu_assistant_app_in_tools, self.app_vars.download_path_pyanitools)
            if error:
                msg_append = "Problem staging update file. " + error
                self.msg_win.show_error_msg("Update Staging Error", msg_append)
                return

            # copy update tool
            #
            # path in temp dir of the tool
            update_tool_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.update_exe)
            # path of the tool in tools dir
            update_tool_in_tools = os.path.join(self.app_vars.apps_dir, self.app_vars.update_exe)
            error = pyani.core.util.move_file(update_tool_in_tools, update_tool_in_temp)
            if error:
                msg_append = "Problem staging update file. " + error
                self.msg_win.show_error_msg("Update Staging Error", msg_append)
                return

            app_to_run = update_tool_in_temp

            # open assistant passing:
            #       path to assistant in temp dir,
            #       assist type - update core or re-install
            #       the calling app,
            #       app to run,
            #       the directories/files to remove
            #
            # assist type - update or re-install
            args = ["update"]
            # the exe calling this app
            args.append(calling_app)
            # app to run - tools setup
            args.append(app_to_run)
            # files and directories to remove - a list so extend current list
            args.extend([])
            # launch assistant with the parameters
            error = pyani.core.util.launch_app(iu_assistant_app_in_temp, args, open_as_new_process=True)
            if error:
                self.msg_win.show_error_msg("Update Staging Error", error)

    def install_apps(self):
        """Installs the app(s) and updates ui info. Displays install_apps errors to user.
        """
        apps = self._get_selection()
        error_log = []
        # try to install_apps selected apps, log and display error if can't and skip to next app
        for index, app in enumerate(apps):
            error = app.install()
            if error:
                error_log.append(error)
                continue
            item = [app.app_name, app.user_version, ""]
            item_color = [None, None, None]
            updated_item = pyani.core.ui.CheckboxTreeWidgetItem(item, item_color)
            self.app_tree.update_item(app.app_name, updated_item)

        if error_log:
            self.msg_win.show_error_msg("Install Error", (', '.join(error_log)))

    def launch(self):
        """Launches the app(s). Displays launch error to user
        """
        apps = self._get_selection()
        error_log = []
        for app in apps:
            # set directory, so that app runs from where the exe is, in case it uses relative paths to find resources
            os.chdir(app.app_install_path)
            exe_path = os.path.join(app.app_install_path, app.app_name)
            # pass application path and arguments, in this case none
            error = pyani.core.util.launch_app("{0}.exe".format(exe_path), [])
            if error:
                error_log.append(error)
                continue
        if error_log:
            self.msg_win.show_error_msg("App Launch Error", (', '.join(error_log)))

    def _create_app_mngrs(self, tools_list_json_path):
        """
        Creates the app managers for all py ani tool apps and makes a list of the app names
        :param: the path to the json file that contains the lists of pyanitool apps
        :return: a list of the app names, and a list of the app mngrs
        """
        # list of apps
        app_names = pyani.core.util.load_json(tools_list_json_path)["pyanitools"]
        # list of app managers for each app
        app_mngrs = []
        if not isinstance(app_names, list):
            error = "Critical error loading list of applications from {0}".format(tools_list_json_path)
            logger.error(error)
            self.msg_win.show_error_msg("Critical Error", error)
        else:
            for name in app_names:
                app_mngr = AniAppMngr(name)
                if app_mngr.log:
                    self.msg_win.show_warning_msg(
                        "Warning",
                        "Could not correctly load data for {0}. This application will not be available to update"
                        "until the error is resolved. Error is {1}".format(name, ", ".join(app_mngr.log))
                    )
                else:
                    app_mngrs.append(AniAppMngr(name))
        return app_mngrs

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

        if self.app_mngrs:
            # display app names, versions, and release notes if a new version is available
            for app in self.app_mngrs:
                # if users version is out of date color orange
                if not app.user_version == app.latest_version:
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
        # problems loading app information
        else:
            text = [
                "Could not find application data. Please see log in {0}".format(self.error_logging.log_file_name), ""
            ]
            color = [pyani.core.ui.RED, pyani.core.ui.RED]
            row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
            tree_info.append({"root": row})

        return tree_info
