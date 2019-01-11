import pyani.core.ui
import pyani.core.util
import os
import sys
import mmap


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


class AniToolsSetup(QtWidgets.QDialog):

    def __init__(self, log_error):
        super(AniToolsSetup, self).__init__()

        self.win_utils = pyani.core.ui.QtWindowUtil(self)
        self.setWindowTitle('Py Ani Tools Setup')
        self.win_utils.set_win_icon("Resources\\setup.ico")
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # set default window size
        self.resize(450, 600)

        # the directory where the unzipped files are for installation
        self.setup_dir = "C:\Users\Patrick\Downloads\PyAniToolsPackage"
        self.setup_app_data_path = os.path.join(self.setup_dir, "PyAniTools\\app_data")
        self.setup_packages_path = os.path.join(self.setup_dir, "PyAniTools\\packages")
        self.setup_installed_path = os.path.join(self.setup_dir, "PyAniTools\\installed")
        self.setup_apps_shortcut_dir = os.path.join(self.setup_dir, "PyAniTools\\installed\\shortcuts")
        self.setup_nuke_scripts_path = os.path.join(self.setup_dir, "PyAniTools\\install_scripts\\")
        # directory where installed files go
        self.tools_dir = "C:\\PyAniTools"
        self.app_data_dir = self.tools_dir + "\\app_data"
        self.packages_dir = self.tools_dir + "\\packages"
        self.apps_dir = self.tools_dir + "\\installed"
        self.apps_shortcut_dir = self.apps_dir + "\\shortcuts"
        self.install_scripts_dir = self.tools_dir + "\\install_scripts"

        # gui vars
        self.ani_vars = pyani.core.util.AniVars()
        self.install_list = ["Creating Directories", "Copying Application Data", "Copying Packages", "Installing Apps",
                             "Install Complete"]

        self.progress_label = QtWidgets.QLabel("Starting Install")
        self.progress = QtWidgets.QProgressBar(self)
        self.close_btn = QtWidgets.QPushButton("Close", self)
        self.report_txt = QtWidgets.QTextEdit("")
        self.report_txt.setFixedWidth(400)
        self.report_txt.setFixedHeight(350)
        self.log = []

        self.create_layout()
        self.set_slots()
        self.report_txt.hide()

        # check if logging was setup correctly in main()
        if log_error:
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(log_error)
            )

        self.install()
        self.report_txt.show()
        self.report_txt.setHtml("<p>".join(self.log))

    def create_layout(self):

        # parent to this class, this is the top level layout (self)
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addStretch(1)
        h_layout_progress_label = QtWidgets.QHBoxLayout()
        h_layout_progress_label.addStretch(1)
        h_layout_progress_label.addWidget(self.progress_label)
        h_layout_progress_label.addStretch(1)
        main_layout.addLayout(h_layout_progress_label)
        h_layout_progress = QtWidgets.QHBoxLayout()
        h_layout_progress.addStretch(1)
        h_layout_progress.addWidget(self.progress)
        h_layout_progress.addStretch(1)
        main_layout.addLayout(h_layout_progress)
        h_layout_btn = QtWidgets.QHBoxLayout()
        h_layout_btn.addStretch(1)
        h_layout_btn.addWidget(self.close_btn)
        h_layout_btn.addStretch(1)
        main_layout.addLayout(h_layout_btn)
        main_layout.addItem(QtWidgets.QSpacerItem(5, 20))
        h_layout_report = QtWidgets.QHBoxLayout()
        h_layout_report.addStretch(1)
        h_layout_report.addWidget(self.report_txt)
        h_layout_report.addStretch(1)
        main_layout.addLayout(h_layout_report)
        main_layout.addStretch(1)

    def set_slots(self):
        self.close_btn.clicked.connect(self.close)

    def install(self):
        """Installs apps from the setup directory where the unzipped files are to the application directory
        Installs new apps if not installed, always updates app data, packages, .nuke/pyanitools folder and app
        Exist early if error encountered
        :return: a self.log of the activity including errors and success
        """

        progress_steps = 100.0 / float(len(self.install_list))
        install_steps = 0

        self.log = []

        # MAKE MAIN DIRECTORY ON C DRIVE --------------------------------------------
        # display install step in gui
        self.progress_label.setText(self.install_list[install_steps])
        # setup the tools directory - run first install only
        if not os.path.exists(self.tools_dir):
            error = pyani.core.util.make_dir(self.tools_dir)
            if error:
                return self._log_error(error)
            else:
                self.log.append("Created {0}".format(self.tools_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # APP DATA -------------------------------------------------------------------
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        # setup app_data - always update this
        if os.path.exists(self.app_data_dir):
            error = pyani.core.util.rm_dir(self.app_data_dir)
            if error:
                return self._log_error(error)
        # update app data
        error = pyani.core.util.move_file(self.setup_app_data_path, self.app_data_dir)
        if error:
            return self._log_error(error)
        else:
            self.log.append("Updated {0}".format(self.app_data_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP PACKAGES ------------------------------------------------------------
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        if os.path.exists(self.packages_dir):
            error = pyani.core.util.rm_dir(self.packages_dir)
            if error:
                return self._log_error(error)
        # update packages
        error = pyani.core.util.move_file(self.setup_packages_path, self.packages_dir)
        if error:
            return self._log_error(error)
        else:
            self.log.append("Updated {0}".format(self.packages_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP APPS ---------------------------------------------------------------
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        # first install
        if not os.path.exists(self.apps_dir):
            error = pyani.core.util.move_file(self.setup_installed_path, self.apps_dir)
            if error:
                return self._log_error(error)
            else:
                self.log.append("Installed Apps To {0}".format(self.apps_dir))
            # copy folder shortcut
            user_desktop = os.path.join("C:\\" + os.environ["HOMEPATH"], "Desktop")
            if not os.path.exists(os.path.join(user_desktop, "PyAniTools.lnk")):
                error = pyani.core.util.move_file(self.apps_dir + "\\PyAniTools.lnk", user_desktop)
                if error:
                    return self._log_error(error)
                else:
                    self.log.append("Created Shortcut On Desktop {0}".format(user_desktop + "\PyAniTools"))
        # installed, but new apps to install that user doesn't have
        else:
            # install any missing apps
            if self._missing_apps():
                for app in self._missing_apps():
                    # copy its shortcut
                    self._install_app_shortcut(app)
                    # install in directory - C:\PyAniTools\installed\appname
                    src = os.path.join(self.setup_installed_path, app)
                    error = pyani.core.util.move_file(src, self.apps_dir)
                    if error:
                        return self._log_error(error)
                    else:
                        self.log.append("Installed App {0} To {1}".format(app, self.apps_dir))

            # update app mngr - copy the app folder from the extracted zip to install location
            app_mngr_path = os.path.join(self.apps_dir, "PyAppMngr")
            error = pyani.core.util.rm_dir(app_mngr_path)
            if error:
                return self._log_error(error)
            setup_app_mngr_path = os.path.join(self.setup_dir, "PyAniTools\\installed\\PyAppMngr")
            error = pyani.core.util.move_file(setup_app_mngr_path, self.apps_dir)
            if error:
                return self._log_error(error)
            else:
                self.log.append("Updated App Manager {0}".format(app_mngr_path))
            # copy its shortcut
            self._install_app_shortcut("PyAppMngr")

        # NUKE --------------------------------------------------------------------

        # setup nuke modifying .nuke/init.py to check c:\users\{user_name}\.nuke\pyanitools\ (create
        # directory if doesn't exist).

        # first check for .nuke
        if not os.path.exists(self.ani_vars.nuke_user_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_user_dir)
            if error:
                return self._log_error(error)
            else:
                self.log.append("Created {0}".format(self.ani_vars.nuke_user_dir))

        # if the custom dir doesn't exist (.nuke/pyanitools), add it and append init.py with the custom nuke path
        if not os.path.exists(self.ani_vars.nuke_custom_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_custom_dir)
            if error:
                return self._log_error(error)
            else:
                self.log.append("Created {0}".format(self.ani_vars.nuke_custom_dir))

        # copy custom init.py, menu.py, and .py (script with python code to support menu and gizmos)
        # Note: remove the files first, copy utils seem to not like existing files
        error = pyani.core.util.delete_all(self.ani_vars.nuke_custom_dir)
        if error:
            self.log.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            return self.log
        error = pyani.core.util.copy_files(self.setup_nuke_scripts_path, self.ani_vars.nuke_custom_dir)
        if error:
            return self._log_error(error)
        else:
            self.log.append("Updated {0}".format(self.ani_vars.nuke_custom_dir))

        # finally update the init.py - only append, don't want to lose existing code added by user
        try:
            file_path = os.path.join(self.ani_vars.nuke_user_dir, "init.py")
            with open(file_path, "a+") as init_file:
                # the code to add to init.py
                custom_plugin_path = "nuke.pluginAddPath(\"./pyanitools\")"
                # use mmap just in case init.py is large, shouldn't be, just a precaution. Otherwise could just
                # load into a string - note in python 3 mmap is like bytearray
                file_in_mem = mmap.mmap(init_file.fileno(), 0, access=mmap.ACCESS_READ)
                if file_in_mem.find(custom_plugin_path) == -1:
                    init_file.write("\n" + custom_plugin_path + "\n")
                    init_file.close()
                    self.log.append("Added {0} to {1}".format(custom_plugin_path, file_path))
        except (IOError, OSError) as e:
            error = "Could not open {0}. Received error {1}".format(file_path, e)
            return self._log_error(error)

        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # FINISH -----------------------------------------------------------------------
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        self.progress.setValue(100)
        QtWidgets.QApplication.processEvents()

    def _install_app_shortcut(self, app_name):
        """
        Installs an app shortcut from the setup directory to the application directory -
        C:\PyAniTools\installed\shortcuts\appname.lnk
        :param app_name: the app name
        """
        src = os.path.join(self.setup_apps_shortcut_dir, "{0}.lnk".format(app_name))
        error = pyani.core.util.move_file(src, self.apps_shortcut_dir)
        if error:
            return self._log_error(error)
        else:
            self.log.append("Installed App Shortcut {0} To {1}".format(src, self.apps_shortcut_dir))

    def _missing_apps(self):
        """Look for any misisng apps in the install directory
        :return: None if no misisng apps, a list of apps if there are missing apps
        """
        app_list_json = os.path.join(self.app_data_dir, "Shared\\app_list.json")
        app_list = pyani.core.util.load_json(app_list_json)
        # see if we read the json data
        if not isinstance(app_list, list):
            return app_list
        # list of installed apps
        installed_list = os.listdir(self.apps_dir)
        # look for each app and see if it is installed
        missing_apps = [app for app in app_list if app not in installed_list]
        return missing_apps

    def _log_error(self, error):
        """
        Simple utility to format errors and append to a list
        :param error: the error as a string
        """
        self.log.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
