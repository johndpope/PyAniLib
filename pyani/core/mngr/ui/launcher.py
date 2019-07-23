import os
import sys
import logging
import pyani.core.ui
import pyani.core.util
import pyani.core.appvars

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets


logger = logging.getLogger()


class AniAppRoamingLauncher(QtWidgets.QDialog):
    """
    Takes an application, copies to the temp directory, then runs the application. Allows applications to run
    outside install directory so they can update or re-install without problems (i.e. can't copy or replace a file
    that is in use)
    """

    def __init__(self, error_logging, application_dir, application_filename):
        """
        :param error_logging: error logging object
        :param application_dir: absolute path of the directory the app is located in
        :param application_filename: name of the application plus extension, i.e. app.exe
        """
        super(AniAppRoamingLauncher, self).__init__()
        self.setWindowTitle("Launching Application...")
        self.resize(400, 600)

        self.app_vars = pyani.core.appvars.AppVars()
        self.msg_win = pyani.core.ui.QtMsgWindow(self)
        self.error_logging = error_logging

        self.app_file_name = application_filename
        self.app_file_name_no_ext = application_filename.split(".")[0]
        self.app_dir = application_dir
        self.temp_dir = os.path.join(
            self.app_vars.local_temp_dir,
            "pyanitools_roaming_{0}".format(self.app_file_name_no_ext)
        )

        self.app_path = os.path.join(application_dir, application_filename)
        self.app_path_in_temp_dir = os.path.join(self.temp_dir, self.app_file_name)

    def run(self):
        """
        Copies and runs the application. Displays any errors, and exits after user presses ok. Also exist after
        successfully running the provided application
        """

        # check if logging was setup correctly in main()
        if self.error_logging.error_log_list:
            errors = ', '.join(self.error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # make sure path exists
        if not os.path.exists(self.app_path):
            error = "Could not find the application: {0}".format(self.app_path)
            self.msg_win.show_error_msg("Launch Error", error)
            logger.error(error)
            self.close()
            return

        # try to copy the application to temp dir
        if os.path.exists(self.temp_dir):
            error = pyani.core.util.rm_dir(self.temp_dir)
            if error:
                self.msg_win.show_error_msg(
                    "Launch Error",
                    "Could not remove existing roaming temp directory for the application. Error is {0}".format(error)
                )
                logger.error(error)
                self.close()
                return

        error = pyani.core.util.make_dir(self.temp_dir)
        if error:
            self.msg_win.show_error_msg(
                "Launch Error",
                "Could not create roaming directory for the application. Error is {0}".format(error)
            )
            logger.error(error)
            self.close()
            return

        error = pyani.core.util.copy_file(self.app_path, self.temp_dir)
        if error:
            self.msg_win.show_error_msg(
                "Launch Error",
                "Could not copy application to roaming directory. Error is {0}".format(error)
            )
            logger.error(error)
            self.close()
            return

        # next copy any images
        images_path_src = os.path.join(self.app_dir, "images")
        if os.path.exists(images_path_src):
            images_path_dst = os.path.join(self.temp_dir, "images")
            error = pyani.core.util.make_dir(images_path_dst)
            if error:
                self.msg_win.show_error_msg(
                    "Launch Error",
                    "Could not create roaming image directory for the application. Error is {0}".format(error)
                )
                logger.error(error)
                self.close()
                return
            error = pyani.core.util.copy_files(images_path_src, images_path_dst)
            if error:
                self.msg_win.show_error_msg(
                    "Launch Error",
                    "Could not copy application images to roaming directory. Error is {0}".format(error)
                )
                logger.error(error)
                self.close()
                return

        # launch app - need to change to the directory where app is launching so images can be found
        os.chdir(self.temp_dir)
        error = pyani.core.util.launch_app(
            self.app_path_in_temp_dir,
            [],
            open_as_new_process=True
        )
        if error:
            self.msg_win.show_error_msg(
                "Launch Error",
                "Could not open application. Error is {0}".format(error)
            )
            logger.error(error)
            self.close()
            return

        sys.exit()
