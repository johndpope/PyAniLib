import pyani.core.ui
import pyani.core.util
import os
import mmap

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


class AniToolsSetup(QtWidgets.QDialog):

    def __init__(self):
        super(AniToolsSetup, self).__init__()

        self.win_utils = pyani.core.ui.QtWindowUtil(self)
        self.setWindowTitle('Py Ani Tools Setup')
        self.win_utils.set_win_icon("Resources\\setup.ico")

        # set default window size
        self.resize(450, 600)

        self.setup_dir = ""
        self.setup_app_data_path = os.path.join(self.setup_dir, "PyAniTools\\app_data")
        self.setup_packages_path = os.path.join(self.setup_dir, "PyAniTools\\packages")
        self.setup_installed_path = os.path.join(self.setup_dir, "PyAniTools\\installed")
        self.setup_nuke_scripts_path = os.path.join(self.setup_dir, "PyAniTools\\install_scripts\\")
        self.tools_dir = "C:\\PyAniTools"
        self.app_data_dir = self.tools_dir + "\\app_data"
        self.packages_dir = self.tools_dir + "\\packages"
        self.apps_dir = self.tools_dir + "\\installed"
        self.install_scripts_dir = self.tools_dir + "\\install_scripts"
        self.ani_vars = pyani.core.util.AniVars()
        self.install_list = ["Creating Directories", "Copying Application Data", "Copying Packages", "Installing Apps",
                             "Install Complete"]

        self.progress_label = QtWidgets.QLabel("Starting Install")
        self.progress = QtWidgets.QProgressBar(self)
        self.close_btn = QtWidgets.QPushButton("Close", self)
        self.report_txt = QtWidgets.QTextEdit("")
        self.report_txt.setFixedWidth(400)
        self.report_txt.setFixedHeight(350)

        self.create_layout()
        self.set_slots()
        self.report_txt.hide()
        self.install()

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

        progress_steps = 100.0 / float(len(self.install_list))
        install_steps = 0

        report = []

        # MAKE MAIN DIRECTORY
        # display install step in gui
        self.progress_label.setText(self.install_list[install_steps])
        # setup the tools directory - run first install only
        if not os.path.exists(self.tools_dir):
            error = pyani.core.util.make_dir(self.tools_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            else:
                report.append("Created {0}".format(self.tools_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # APP DATA
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        # setup app_data - always update this
        if os.path.exists(self.app_data_dir):
            error = pyani.core.util.rm_dir(self.app_data_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        # update app data
        error = pyani.core.util.move_file(self.setup_app_data_path, self.app_data_dir)
        if error:
            report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        else:
            report.append("Updated {0}".format(self.app_data_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP PACKAGES
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        if os.path.exists(self.packages_dir):
            error = pyani.core.util.rm_dir(self.packages_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        # update packages
        error = pyani.core.util.move_file(self.setup_packages_path, self.packages_dir)
        if error:
            report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        else:
            report.append("Updated {0}".format(self.packages_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP APPS
        # update install step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        # first install
        if not os.path.exists(self.apps_dir):
            error = pyani.core.util.move_file(self.setup_installed_path, self.apps_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            else:
                report.append("Installed Apps To {0}".format(self.apps_dir))
            # copy folder shortcut
            user_desktop = os.path.join(os.environ["HOMEPATH"], "Desktop")
            if not os.path.exists(os.path.join(user_desktop, "PyAniTools.lnk")):
                error = pyani.core.util.move_file(self.apps_dir + "\\PyAniTools.lnk", user_desktop)
                if error:
                    report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
                else:
                    report.append("Created Shortcut On Desktop {0}".format(user_desktop + "\PyAniTools"))
        else:
            # just update app mngr - copy the exe from the extracted zip to install location
            app_mngr_path = os.path.join(self.apps_dir, "PyAppMngr\\PyAppMngr.exe")
            error = pyani.core.util.delete_file(app_mngr_path)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            setup_app_mngr_path = os.path.join(self.setup_dir, "PyAniTools\\installed\\PyAppMngr\\PyAppMngr.exe")
            error = pyani.core.util.move_file(setup_app_mngr_path, app_mngr_path)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            else:
                report.append("Updated App Manager {0}".format(app_mngr_path))
        # setup nuke modifying .nuke/init.py to check c:\users\{user_name}\.nuke\pyanitools\ (create
        # directory if doesn't exist).

        # check for .nuke
        if not os.path.exists(self.ani_vars.nuke_user_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_user_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            else:
                report.append("Created {0}".format(self.ani_vars.nuke_user_dir))

        # if the custom dir doesn't exist (.nuke/pyanitools), add it and append init.py with the custom nuke path
        if not os.path.exists(self.ani_vars.nuke_custom_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_custom_dir)
            if error:
                report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
            else:
                report.append("Created {0}".format(self.ani_vars.nuke_custom_dir))
        # update the init.py - only append, don't want to lose existing code added by user
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
                    report.append("Added {0} to {1}".format(custom_plugin_path, file_path))
        except (IOError, OSError) as e:
            error = "Could not open {0}. Received error {1}".format(file_path, e)
            report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))

        # copy custom init.py, menu.py, and .py (script with python code to support menu and gizmos)

        # remove the files, copy utils seem to not like existing files
        error = pyani.core.util.delete_all(self.ani_vars.nuke_custom_dir)
        if error:
            report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        error = pyani.core.util.copy_files(self.setup_nuke_scripts_path, self.ani_vars.nuke_custom_dir)
        if error:
            report.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))
        else:
            report.append("Updated {0}".format(self.ani_vars.nuke_custom_dir))

        self.progress.setValue(self.progress.value() + progress_steps)
        QtWidgets.QApplication.processEvents()

        # FINISH
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        self.progress.setValue(100)
        QtWidgets.QApplication.processEvents()

        self.report_txt.show()
        self.report_txt.setHtml("<p>".join(report))
