import logging
import os
import sys
import psutil
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.util


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


logger = logging.getLogger()


class AniToolsIUAssist(QtWidgets.QDialog):
    """
    This creates an object that acts as a middle man between app calling this class and an app to run. The typical use
    is to handle updating software while the software is running. This class:
    a. shuts down the app calling this class,
    b. launches the app to run and wait for it to finish
    c. relaunch the app calling this class.
    In practice the app calling this is the app manager and the app to run is either tools setup or tools updater. This
    allows the app manager to provide manual updating and re-installation (which requires being able to update the
    app manager)

    :param parameters: a list of variables
    [
        application or exe that called this class, referred to as calling app,
        application to run from this class,
        1st directory or file to remove,
        2nd directory or file to remove,
        ....
        nth directory or file to remove
    ]

    """

    def __init__(self, error_logging, parameters):
        super(AniToolsIUAssist, self).__init__()

        self.win_utils = pyani.core.ui.QtWindowUtil(self)
        self.setWindowTitle('Py Ani Tools Install and Update Assistant')
        self.win_utils.set_win_icon("Resources\\setup.ico")
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # set default window size
        self.resize(450, 600)

        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # ui elements
        self.progress_label = QtWidgets.QLabel("Starting Install or Update")
        # progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.progress_label)
        self.progress_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addItem(QtWidgets.QSpacerItem(0, 10))
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)
        self.setLayout(layout)

        # gui vars
        self.ani_vars = pyani.core.anivars.AniVars()
        self.app_vars = pyani.core.appvars.AppVars()
        # is this an update or re-install - currently not used, but left for future functionality
        self.assist_type = parameters[0]
        # path to the application that launched the app built on this class
        self.calling_app = parameters[1]
        # the path to the application to run
        self.app_to_run = parameters[2]
        # check for directories to remove
        if len(parameters) > 3:
            self.files_and_dirs_to_rm = parameters[3:]
        else:
            self.files_and_dirs_to_rm = ""

    def run_install_or_update(self):
        """
        Handles the closing of the calling app and launching of the app to run. If successful it will relaunch the
        calling app (app that launched this) and exit. Otherwise it will display any errors.
        :return:
        """

        self.progress_label.setText("Removing existing tools.")
        self.progress_bar.setValue(33)
        QtWidgets.QApplication.processEvents()

        # split off path and get just exe name
        exe_name = self.calling_app.split("\\")[-1]
        logger.info(exe_name)
        # find the application's pid, uses the name, and shut it down
        pids = self._find_processes_by_name(exe_name)
        for pid in pids:
            p = psutil.Process(pid)
            logger.info("pid: " + str(pid))
            p.kill()

        # remove any files or directories - handles .nuke specially
        errors = []
        for item in self.files_and_dirs_to_rm:
            logger.info("Removing: {0}".format(item))
            if ".nuke" in item:
                # open the file and get contents
                f = open("C:\\Users\\Patrick\\.nuke\\init.py", "r+")
                contents = f.readlines()
                # restart file marker at beginning
                f.seek(0)
                # look for any lines not matching plugin path, and save those
                for line_num, line in enumerate(contents):
                    # check if the plugin path is in line, if it is skip, otherwise continue checks
                    if "nuke.pluginAddPath(\"C:\\PyAniTools\\lib\")" not in line:
                        # now check for extra newlines and don't write a line if its a newline only and previous
                        # line was a newline only. Note we first check that its not the first line which
                        # would not have a previous line before it.Then we see if the current line is a newline,
                        # if so check if previous line was a newline, if not write the line.
                        if line_num > 0:
                            if contents[line_num] == "\n":
                                # current line is a newline, check if previous line is also a newline
                                if not contents[line_num - 1] == "\n":
                                    # current line is a newline, but previous line is not a newline so write it
                                    f.write(line)
                            # not the plugin path to remove and not a newline so write it
                            else:
                                f.write(line)
                        # first line so write it
                        else:
                            f.write(line)
                f.truncate()
                f.close()
            else:
                # its a file so delete file
                if os.path.isfile(item):
                    error = pyani.core.util.delete_file(item)
                    if error:
                        errors.append(error)
                # its a directory
                else:
                    error = pyani.core.util.rm_dir(item)
                    if error:
                        errors.append(error)

        if errors:
            msg = "Problem removing PyAniTools for re-install or update. Errors: {0}".format(', '.join(errors))
            logger.error(msg)
            self.msg_win.show_error_msg("Removal Error", msg)
            return

        self.progress_label.setText("Running setup, will open in another window and return here when complete.")
        self.progress_bar.setValue(52)
        QtWidgets.QApplication.processEvents()
        # call the app to run
        error = pyani.core.util.launch_app(
            self.app_to_run, ["force_update"], wait_to_complete=True, open_as_new_process=True
        )
        if error:
            msg = "Problem launching {0}. Errors: {1}".format(self.app_to_run, error)
            logger.error(msg)
            self.msg_win.show_error_msg("Launch App Error", msg)
            return

        self.progress_label.setText("Complete.")
        self.progress_bar.setValue(100)
        QtWidgets.QApplication.processEvents()

        # reopen calling app
        error = pyani.core.util.launch_app(
            self.calling_app, [], open_as_new_process=True
        )
        if error:
            msg = "Problem launching {0}. Errors: {1}".format(self.app_to_run, error)
            logger.error(msg)
            self.msg_win.show_error_msg("Launch App Error", msg)
            return
        else:
            sys.exit()

    @staticmethod
    def _find_processes_by_name(name):
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
