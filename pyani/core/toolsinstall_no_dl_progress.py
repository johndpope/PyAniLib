import mmap
import logging
import os
import sys
import datetime
import zipfile
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.util
import pyani.core.mayatoolsmngr

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore, QtGui

logger = logging.getLogger()


class AniToolsSetup:
    def __init__(self):
        self.app_vars = pyani.core.appvars.AppVars()
        # just using show vars, no sequence or shot vars
        self.ani_vars = pyani.core.anivars.AniVars()

    def cleanup(self):
        """
        Removes files and directories created during updating in the tmep directory
        :return: None if removed without errors, or an error as a string if an error occurs
        """
        # clean up any temp files related to downloading of files from cgt
        if os.path.exists(self.app_vars.download_path_cgt):
            error = pyani.core.util.rm_dir(self.app_vars.download_path_cgt)
            if error:
                return error
        # clean up any temp files from updating pyanitools
        if os.path.exists(self.app_vars.download_path_pyanitools):
            error = pyani.core.util.rm_dir(self.app_vars.download_path_pyanitools)
            if error:
                return error

    @staticmethod
    def updates_exist(server_data, client_data):
        """
        Checks for updates on the server by downloading the modified json
        :param server_data - the server upload date, format of date is "%Y-%m-%d_%H-%M"
        :param client_data - the client install_apps date, format of date is "%Y-%m-%d_%H-%M"
        :return: True if updates available, False if not.
        """
        # convert string date to python date objects for comparison
        server_date_str = server_data["last_update"]
        split_date_time = server_date_str.split("_")
        split_hours_min = split_date_time[-1].split("-")
        split_date = split_date_time[0].split("-")
        server_date = datetime.datetime(
            int(split_date[0]),
            int(split_date[1]),
            int(split_date[2]),
            hour=int(split_hours_min[0]),
            minute=int(split_hours_min[1])
        )
        client_date_str = client_data["last_update"]
        split_date_time = client_date_str.split("_")
        split_hours_min = split_date_time[-1].split("-")
        split_date = split_date_time[0].split("-")
        client_date = datetime.datetime(
            int(split_date[0]),
            int(split_date[1]),
            int(split_date[2]),
            hour=int(split_hours_min[0]),
            minute=int(split_hours_min[1])
        )
        # if client date is before server date then there is an update
        if client_date < server_date:
            return True
        else:
            return False

    def download_updates(self, skip_update_check=False):
        """
        Downloads the files from the server.
        :param skip_update_check: whether to only download the update if its newer.
        :returns: True if downloaded, False if no updates to download, error if encountered.
        """
        # download json file
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        dl_command = [
            py_script,
            self.app_vars.server_update_json_path,
            self.app_vars.download_path_cgt,
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]

        output, error = pyani.core.util.call_ext_py_api(dl_command)
        if error:
            logging.error(error)
            return self.log_error(error)

        # open json file downloaded from the server
        server_data = pyani.core.util.load_json(self.app_vars.server_update_json_download_path)
        if not isinstance(server_data, dict):
            return self.log_error(server_data)
        # open client json
        client_data = pyani.core.util.load_json(self.app_vars.client_install_data_json)
        if not isinstance(client_data, dict):
            return self.log_error(client_data)

        if self.updates_exist(server_data, client_data) or skip_update_check:
            logging.info("Running Update")
            # download the file
            py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
            dl_command = [
                py_script,
                self.app_vars.cgt_path_pyanitools,
                self.app_vars.download_path_cgt,
                self.app_vars.cgt_ip,
                self.app_vars.cgt_user,
                self.app_vars.cgt_pass
            ]
            output, error = pyani.core.util.call_ext_py_api(dl_command)
            if error:
                logging.error(error)
                return self.log_error(error)
            return True
        return False

    def stage_updates(self):
        """
        Stage the updates that were downloaded
        :returns: None if installed, errors if encountered
        """
        # move file to tempdir
        src = os.path.join(self.app_vars.download_path_cgt, self.app_vars.tools_package)
        dest = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.tools_package)
        # check if directory exists
        if not os.path.exists(self.app_vars.download_path_pyanitools):
            error = pyani.core.util.make_dir(self.app_vars.download_path_pyanitools)
            if error:
                return self.log_error(error)
        error = pyani.core.util.move_file(src, dest)
        if error:
            return self.log_error(error)
        # try unzipping
        try:
            with zipfile.ZipFile(file=dest) as zipped:
                zipped.extractall(path=self.app_vars.download_path_pyanitools)
        except (zipfile.BadZipfile, zipfile.LargeZipFile, IOError, OSError) as e:
            error = "{0} update file is corrupt. Error is {1}".format(dest, e)
            logger.exception(error)
            return self.log_error(error)
        # set the install_apps path
        self.app_vars.update_setup_dir(self.app_vars.download_path_pyanitools)
        return None

    def set_install_date(self):
        """
        Updates the install_data.json in shared app data with the install_apps date as format "%Y-%m-%d_%H-%M"
        example:
        2019-01-16_14-22
        :return: Error if encountered formatted red, otherwise None
        """
        data = pyani.core.util.load_json(self.app_vars.client_install_data_json)
        if not isinstance(data, dict):
            return data
        now = datetime.datetime.now()
        install_date = now.strftime("%Y-%m-%d_%H-%M")
        data["last_update"] = install_date
        error = pyani.core.util.write_json(self.app_vars.client_install_data_json, data)
        if error:
            return self.log_error(error)
        logging.info("Updated install_apps data to {0}".format(install_date))
        return None

    def update_show_info(self):
        """
        Calls cgt api to update the list of show info - sequences, shots, frame start/end
        :return: error if encountered, otherwise None
        """
        # download the file
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_show_info.py")
        dl_command = [
            py_script,
            self.app_vars.sequence_list_json,
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        output, error = pyani.core.util.call_ext_py_api(dl_command)

        if error:
            logging.error(error)
            return self.log_error(error)
        return None

    def make_install_dirs(self):
        """
        Makes the root directory for the tools.
        :return: error as a formatted string using log_error function or None, also return if created directory as bool
        since it only creates if doesn't exist
        """
        # root directory containing the tools
        if not os.path.exists(self.app_vars.tools_dir):
            error = pyani.core.util.make_dir(self.app_vars.tools_dir)
            if error:
                return self.log_error(error), False
            # no error, created successfully
            else:
                logging.info("Step: Created {0}".format(self.app_vars.tools_dir))
                return None, True
        # already exists
        return None, False

    def update_app_data(self):
        """
        Updates the app data directory with the new app data from downloaded zip
        :return: error as a formatted string using log_error function or None
        """
        # remove dir if exists so can move app data from zip to here
        if os.path.exists(self.app_vars.app_data_dir):
            error = pyani.core.util.rm_dir(self.app_vars.app_data_dir)
            if error:
                return self.log_error(error)
            logging.info("Step: Removed: {0}".format(self.app_vars.app_data_dir))
        # update app data
        error = pyani.core.util.move_file(self.app_vars.setup_app_data_path, self.app_vars.tools_dir)
        if error:
            return self.log_error(error)
        logging.info("Step: Moving: {0} to {1}".format(self.app_vars.setup_app_data_path, self.app_vars.tools_dir))
        return None

    def update_packages(self):
        """
        Updates the packages (zips for each app containing exe and app_pref.json) with the new packages
        from downloaded zip
        :return: error as a formatted string using log_error function or None
        """
        if os.path.exists(self.app_vars.packages_dir):
            error = pyani.core.util.rm_dir(self.app_vars.packages_dir)
            if error:
                return self.log_error(error)
            logging.info("Step: Removed: {0}".format(self.app_vars.packages_dir))
        # update packages
        error = pyani.core.util.move_file(self.app_vars.setup_packages_path, self.app_vars.packages_dir)
        if error:
            return self.log_error(error)
        logging.info("Step: Moving: {0} to {1}".format(self.app_vars.setup_packages_path, self.app_vars.packages_dir))

        return None

    def add_all_apps(self):
        """
        Copies everything in installed folder from the downloaded zip to tools directory install_apps folder.
        Includes apps, shortcuts to apps, and 3rd party support programs
        :return: error as a formatted string using log_error function or None
        """
        error = pyani.core.util.move_file(self.app_vars.setup_installed_path, self.app_vars.apps_dir)
        if error:
            return self.log_error(error), False
        logging.info("Step: Moving: {0} to {1}".format(self.app_vars.setup_installed_path, self.app_vars.app_data_dir))
        return None

    def add_new_apps(self):
        """
        installs new apps as become available. Does not update/replace any of the existing apps. That is handled by
        app_manager program - see appmanager.py
        :return: error as a formatted string using log_error function or None, also returns list of new apps installed
        """
        # installed, but new apps to install_apps that user doesn't have
        if os.path.exists(self.app_vars.apps_dir):
            # get missing apps, check for valid list
            missing_apps = self.missing_apps()
            # exit if an error - ie not a list of apps or None
            if not isinstance(missing_apps, list) and missing_apps is not None:
                return missing_apps
            # install_apps any missing apps
            if missing_apps:
                for app in missing_apps:
                    # copy its shortcut
                    self.install_app_shortcut(app)
                    # install_apps in directory - C:\PyAniTools\installed\appname
                    src = os.path.join(self.app_vars.setup_installed_path, app)
                    error = pyani.core.util.move_file(src, self.app_vars.apps_dir)
                    logging.info("Step: Moving: {0} to {1}".format(src, self.app_vars.apps_dir))
                    if error:
                        return self.log_error(error), None

            # update app mngr - copy the app folder from the extracted zip to install_apps location
            error = pyani.core.util.rm_dir(self.app_vars.app_mngr_path)
            if error:
                return self.log_error(error), None
            logging.info("Step: Removed: {0}".format(self.app_vars.app_mngr_path))
            app_mngr_path_from_zip = os.path.join(self.app_vars.setup_dir, "PyAniTools\\installed\\PyAppMngr")
            # check if app manager folder exists, could be a re-install, which has issues removing the folder. The
            # folder contents get removed, but C:\\PyAniTools\\installed\\PyAppMngr doesn't. If the folder is there,
            # move the folder contents not the folder
            if os.path.exists(self.app_vars.app_mngr_path):
                for app_mngr_file in os.listdir(app_mngr_path_from_zip):
                    file_to_move = os.path.join(app_mngr_path_from_zip, app_mngr_file)
                    pyani.core.util.move_file(file_to_move, self.app_vars.app_mngr_path)
            else:
                error = pyani.core.util.move_file(app_mngr_path_from_zip, self.app_vars.apps_dir)
                if error:
                    return self.log_error(error), None
                logging.info("Step: Moving: {0} to {1}".format(app_mngr_path_from_zip, self.app_vars.apps_dir))
            # copy its shortcut
            self.install_app_shortcut("PyAppMngr")
            # no errors, return any missing apps
            return None, missing_apps
        # no errors, but no new apps since directory doesn't exist
        return None, None

    def make_nuke_dir(self):
        """
        make .nuke and init.py if they don't exist
        :return error if encountered or None, also returns if directory and file created since if exists we skip
        """
        if not os.path.exists(self.ani_vars.nuke_user_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_user_dir)
            if error:
                return self.log_error(error), False
            error = pyani.core.util.make_file(os.path.join(self.ani_vars.nuke_user_dir, "init.py"))
            if error:
                return self.log_error(error), False
            # no error, created both
            logging.info("Step: made dir: {0}".format(self.ani_vars.nuke_user_dir))
            return None, True
        # no error but didn't create
        return None, False

    def make_custom_nuke_dir(self):
        """
        make custom folder in C:PyAniTools\
        :return error if encountered or None, also returns if directory created since if exists we skip
        """
        # if the custom dir doesn't exist (C:PyAniTools\lib), add it and append init.py with the custom nuke path
        if not os.path.exists(self.ani_vars.nuke_custom_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_custom_dir)
            if error:
                return self.log_error(error), False
            # no error, but created
            else:
                logging.info("Step: made dir: {0}".format(self.ani_vars.nuke_custom_dir))
                return None, True
        # no error but didn't create
        return None, False

    def copy_custom_nuke_init_and_menu_files(self):
        """
        copy custom init.py, menu.py, and support python scripts
        :return error if encountered or None
        """
        # Note: remove the files first, copy utils seem to not like existing files
        error = pyani.core.util.delete_all(self.ani_vars.nuke_custom_dir)
        if error:
            return self.log_error(error)
        error = pyani.core.util.copy_files(self.app_vars.setup_nuke_scripts_path, self.ani_vars.nuke_custom_dir)
        if error:
            return self.log_error(error)
        logging.info("Step: copied nuke scripts to custom folder: {0}".format(self.ani_vars.nuke_custom_dir))
        return None

    def add_custom_nuke_path_to_init(self):
        """
        update the .nuke\init.py - only append, don't want to lose existing code added by user
        :return error if encountered or None, also true if added to init, false if didn't
        """
        try:
            # check if file empty, mmap won't work with empty files
            if os.stat(self.app_vars.nuke_init_file_path).st_size == 0:
                with open(self.app_vars.nuke_init_file_path, "w") as init_file:
                    init_file.write("\n" + self.app_vars.custom_plugin_path + "\n")
                    init_file.close()
                    logging.info("Step: added custom path to .nuke\init.py")
                    return None, True
            else:
                with open(self.app_vars.nuke_init_file_path, "a+") as init_file:
                    # use mmap just in case init.py is large, shouldn't be, just a precaution. Otherwise could just
                    # load into a string - note in python 3 mmap is like bytearray
                    file_in_mem = mmap.mmap(init_file.fileno(), 0, access=mmap.ACCESS_READ)
                    if file_in_mem.find(self.app_vars.custom_plugin_path) == -1:
                        init_file.write("\n" + self.app_vars.custom_plugin_path + "\n")
                        init_file.close()
                        logging.info("Step: added custom path to .nuke\init.py")
                        return None, True
                    return None, False
        except (IOError, OSError, ValueError) as e:
            error = "Could not open {0}. Received error {1}".format(self.app_vars.nuke_init_file_path, e)
            logger.exception(error)
            return self.log_error(error), False

    def install_app_shortcut(self, app_name):
        """
        Installs an app shortcut from the setup directory to the application directory -
        C:\PyAniTools\installed\shortcuts\appname.lnk
        :param app_name: the app name
        :return error if encountered or None
        """
        # move shortcut from setup dir to tools dir
        shortcut_to_move = os.path.join(self.app_vars.setup_apps_shortcut_dir, "{0}.lnk".format(app_name))
        existing_shortcut = os.path.join(self.app_vars.apps_shortcut_dir, "{0}.lnk".format(app_name))
        if not os.path.exists(existing_shortcut):
            error = pyani.core.util.move_file(shortcut_to_move, self.app_vars.apps_shortcut_dir)
            logging.info("Step: Moving: {0} to {1}".format(shortcut_to_move, self.app_vars.apps_shortcut_dir))
            if error:
                return self.log_error(error)
        return None

    def missing_apps(self):
        """Look for any misisng apps in the install_apps directory
        :return: None if no misisng apps, a list of apps if there are missing apps, or an error string if errored
        loding the apps list
        """
        app_list_json = os.path.join(self.app_vars.app_data_dir, "Shared\\app_list.json")
        app_list_json_data = pyani.core.util.load_json(app_list_json)
        # see if we read the json data
        if not isinstance(app_list_json_data, dict):
            return app_list_json_data
        app_list = app_list_json_data['pyanitools']
        # list of installed apps
        installed_list = os.listdir(self.app_vars.apps_dir)
        # look for each app and see if it is installed
        missing_apps = [app for app in app_list if app not in installed_list]
        if missing_apps:
            logging.info("missing apps are: {0}".format(', '.join(missing_apps)))
        return missing_apps

    @staticmethod
    def log_error(error):
        """
        Simple utility to format errors
        :param error: the error as a string
        :return a string set to color red using html
        """
        return "<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error)


class AniToolsSetupGui(QtWidgets.QDialog):
    """
    Class to install_apps tools. Creates directories, moves install_apps files and app data, and updates nuke config.
    Also creates a windows scheduling task to download future updates
    :param run_type : "setup" or "update"
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    :param close_on_success: close after a successful install or update, defaults to false
    :param testing: set to True to run without actually downloading data, useful for testing since data download takes
    a while and have to actually move and copy files
    to create logging in main program
    """

    def __init__(self, run_type, error_logging, close_on_success=False, testing=False):
        super(AniToolsSetupGui, self).__init__()

        # functionality to install apps and update tools
        self.tools_setup = AniToolsSetup()
        # functionality to install maya plugins
        self.maya_plugins = pyani.core.mayatoolsmngr.AniMayaTools()

        # create a task scheduler object
        self.task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_update", os.path.join(self.tools_setup.app_vars.apps_dir, "PyAniToolsUpdate.exe")
        )
        self.run_type = run_type
        self.close_on_success = close_on_success

        self.win_utils = pyani.core.ui.QtWindowUtil(self)
        self.setWindowTitle('Py Ani Tools Setup')
        self.win_utils.set_win_icon("Resources\\setup.ico")
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # set default window size
        self.resize(450, 600)

        # gui vars
        self.ani_vars = pyani.core.anivars.AniVars()
        self.install_list = ["Creating Directories", "Copying Application Data", "Copying Packages", "Installing Apps",
                             "Installing Maya Plugins", "Install Complete"]

        self.progress_label = QtWidgets.QLabel("Starting Install")
        self.progress = QtWidgets.QProgressBar(self)
        self.close_btn = QtWidgets.QPushButton("Close", self)
        self.report_txt = QtWidgets.QTextEdit("")
        self.report_txt.setFixedWidth(400)
        self.report_txt.setFixedHeight(350)
        # a log of errors and what installed or updated
        self.log = []
        # indicates if an error occured
        self.error_occurred = False
        self.progress_steps = 0

        self.create_layout()
        self.set_slots()
        self.report_txt.hide()

        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # allows the app to run without downloading data or copying moving files
        self.testing = testing
        if self.testing:
            logging.info("TEST MODE ENABLED")

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

    def progress_received_maya_plugins_update(self, data):
        """
        Gets progress from CGTDownloadMonitor class via slot/signals
        :param data: a string or int
        """
        # check for string message or download progress (int)
        if isinstance(data, basestring):
            # get the total number of files being downloaded - only get this data if downloading multiple files
            if "file_total" in data:
                self.progress_download_label.setText("Downloading {0} files.".format(data.split(":")[1]))
            # get the total file size of the download - only get this data if downloading one file
            elif "file_size" in data:
                self.progress_download_label.setText("Downloading {0}.".format(data.split(":")[1]))
            elif "done" in data or "no_updates" in data:
                self.progress_download_label.hide()
                self.progress_download_bar.hide()
                self.progress_download_bar.setValue(0)

                logging.info("Maya plugins update ran with success")
                self.log.append("Maya plugins are at the latest versions")

                # show errors or success message
                if not self.error_occurred:
                    logging.info("-----------> Completed Update Successfully.")
                    self.log.append(
                        "<font color={0}>Update Process Completed Successfully!</font>".format(pyani.core.ui.GREEN)
                    )

                # finish
                self.finish_install(completion_msg="Updates Complete")
        else:
            # update progress
            self.progress_download_bar.setValue(data)

    def run(self, force_update=False):
        """
        starts the install or update process.
        NOTE: exits on a successful installation or update if the flag
        'close_on_success was passed'. Otherwise shows report of the install or update via the finish_install method
        :param force_update: optional flag to force an update regardless of user version
        """
        # determine if this is an install_apps or update
        if self.run_type == "setup":
            self.run_install()
        else:
            self.run_update(force_update=force_update)

    def run_install(self):
        """
        Does the complete installation of the tools
        """
        # schedule tools update to run, if it is already scheduled skips. If scheduling errors then informs user
        # but try to install apps
        error = self.task_scheduler.setup_task(schedule_type="daily", start_time="14:00")
        if error:
            msg = "Can't Setup Windows Task Scheduler. Error is: {0}".format(error)
            logging.error(msg)
            self.log.append(self.format_error(msg))
            self.error_occurred = True

        # install_apps
        # set the directory the exe file is in
        path = pyani.core.util.get_script_dir()
        self.tools_setup.app_vars.update_setup_dir(path)
        logger.info("setup_dir is {0}".format(path))

        self.progress_steps = 100.0 / float(len(self.install_list))
        log = self.install()
        # if its a list its the success log, otherwise its an error
        if isinstance(log, list):
            self.log.extend(log)
        else:
            self.log.append(log)
            self.error_occurred = True

        # run maya plugins install - will run regardless of whether pyanitools installs successfully
        self.progress_label.setText("Adding Maya Plugins")
        QtWidgets.QApplication.processEvents()
        self.progress.setValue(90)
        # run this here, because we need the app data installed first. plugin data is in app_data/shared/app_list.json
        error = self.maya_plugins.build_tool_data()
        if error:
            self.log.append(self.format_error(error))
            # at end of installation, couldn't install maya plugins
            self.error_occurred = True
        else:
            # download from CGT
            error = self.maya_plugins.download_tools(
                self.maya_plugins.get_tools_list(), None, use_progress_monitor=False
            )
            if error:
                self.log.append(self.format_error(error))
                # at end of installation, couldn't install maya plugins
                self.error_occurred = True
            else:
                self.log.append("Added maya plugins: {0}".format(', '.join(self.maya_plugins.get_tools_list())))

                # update install_apps date
                if not self.testing:
                    error = self.tools_setup.set_install_date()
                else:
                    error = None
                if error:
                    self.log.append(self.format_error(error))

        # if no errors show success message in green
        if not self.error_occurred:
            self.log.append(
                "<font color={0}>Installation Completed Successfully!</font>".format(pyani.core.ui.GREEN)
            )
        else:
            self.log.append(
                self.format_error("Installation Completed With Errors. See Above Log.")
            )

        # finish
        self.finish_install()

    def run_update(self, force_update=False):
        """
        Runs the update process
        :param force_update: optional flag to force an update regardless of user version
        :return: exits early if can't download the tools from cgt or the sequence / shot list from cgt
        """
        # number of install_apps steps is the installation of files plus 2
        # (update seq shot list, download zip)
        self.progress_steps = 100.0 / float(len(self.install_list) + 2)

        # set the directory the exe file is in
        path = pyani.core.util.get_script_dir()
        self.tools_setup.app_vars.update_setup_dir(path)

        # ----------------------------------------------------------------
        # update sequence list - note records if fails but doesn't exit update process. Tries to update
        # the tools and maya plugins
        self.progress_label.setText("Updating list of Sequences and Shots")
        # update progress bar
        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()
        if not self.testing:
            error = self.tools_setup.update_show_info()
        else:
            error = None
        if error:
            msg = "Sequence List Update Failed. Error is {0}".format(error)
            self.error_occurred = True
            self.log.append(self.format_error(msg))
        else:
            self.log.append("Sequence update ran with success")
            logging.info("Sequence update ran with success")

        # ----------------------------------------------------------------
        # update tools - doesn't exit if fails, just record and try to download maya plugins
        self.progress_label.setText("Checking and downloading tool updates. Package is 495 MB, this may take "
                                    "several minutes....")
        # update progress bar
        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()

        if not self.testing:
            error = self.tools_setup.download_updates(skip_update_check=force_update)
        else:
            error = False
        # not true or false, so an error occurred getting the timestamp
        if not isinstance(error, bool):
            msg = "PyAniTools Update Failed. Error is {0}".format(error)
            self.log.append(self.format_error(msg))
            logging.error(msg)
            self.error_occurred = True
        # returned False, means nothing downloaded
        elif not error:
            self.log.append("No updates to download.")
            logging.info("No updates to download.")
        # returned true so pyanitools downloaded
        else:
            # unzips and sets directory where the unzipped files are
            error = self.tools_setup.stage_updates()
            if error:
                self.log.append(error)
                self.error_occurred = True
            else:
                # install apps
                log = self.install()
                # if its a list its the success log, otherwise its an error
                if isinstance(log, list):
                    self.log.extend(log)
                else:
                    self.log.append(log)
                    self.error_occurred = True

        # Update Maya Plugins
        error = self.maya_plugins.build_tool_data()
        if error:
            self.log.append(self.format_error(error))
            # at end of installation, couldn't install maya plugins
            self.error_occurred = True
        else:
            # download from CGT
            error = self.maya_plugins.download_tools(
                self.maya_plugins.get_tools_list(), None, use_progress_monitor=False
            )
            if error:
                self.log.append(self.format_error(error))
                # at end of installation, couldn't install maya plugins
                self.error_occurred = True
            else:
                self.log.append("Added maya plugins: {0}".format(', '.join(self.maya_plugins.get_tools_list())))

                # update install_apps date
                if not self.testing:
                    # only set date if no errors installing
                    if not self.error_occurred:
                        error = self.tools_setup.set_install_date()
                else:
                    error = None
                if error:
                    self.log.append(self.format_error(error))
                    self.error_occurred = True
                else:
                    logging.info("Apps update ran with success")

        # if no errors show success message in green
        if not self.error_occurred:
            self.log.append(
                "<font color={0}>Update Completed Successfully!</font>".format(pyani.core.ui.GREEN)
            )
        else:
            self.log.append(
                self.format_error("Update Completed With Errors. See Above Log.")
            )

        # finish install
        self.finish_install(completion_msg="Updates Complete")

    def finish_install(self, completion_msg="Installation Complete"):
        """
        :param completion_msg: a string containing the message to display above the progress bar for installation
        complete. Defaults to Installation Complete
        Finishes the installation regardless of success or error. Shows messages and cleans up temp dirs
        """
        self.progress_label.setText(completion_msg)
        self.progress.setValue(100)
        QtWidgets.QApplication.processEvents()

        # check if the flag was passed to close after a successful install or update
        if self.close_on_success:
            sys.exit()
        # no flag passed to close, so show report
        else:
            self.report_txt.show()
            self.report_txt.setHtml("<p>".join(self.log))

        # remove temp files
        self.tools_setup.cleanup()

    def update_maya_plugins(self):
        """
        Runs the maya plugin update
        :return: False if can't build plugin data, True otherwise - means attempting download
        """
        error = self.maya_plugins.build_tool_data()
        if error:
            self.log.append(self.format_error(error))
            # at end of installation, couldn't install maya plugins
            self.error_occurred = True
            return False

        self.progress.setValue(90)
        self.progress_label.setText(
            "Updating Maya Plugins: {0}".format(', '.join(self.maya_plugins.get_tools_list()))
        )

        if not self.testing:
            self.maya_plugins.download_tools(
                self.maya_plugins.get_tools_list(),
                self.download_monitor_maya_update
            )
        else:
            # testing so want to return false so we can exit - otherwise waits on
            # progress_recieved_maya_plugin_updates()
            return False

        return True

    def install(self):
        """Installs apps from the setup directory where the unzipped files are to the application directory
        Installs new apps if not installed, always updates app data, packages, app mngr, install update assistant,
        pyanitools lib for nuke. Handles 3 types of installs:
        1. First time install
        2. Re-install
        3. Installing core files only - means updating everything but the apps, but will install new apps. Call
           this install type 'updating' since it is only installing core data files that handle app management
        Exits early if errors are encountered, otherwise returns a log of the steps installed.
        :return: if an error encountered, returns a string of the error. if no errors returns a list of the install
                 steps that ran
        """
        install_steps = 0

        log_success = []

        # MAKE MAIN DIRECTORY ON C DRIVE --------------------------------------------
        # display install_apps step in gui
        self.progress_label.setText(self.install_list[install_steps])
        if not self.testing:
            # setup the tools directories - run first install_apps only
            error, created = self.tools_setup.make_install_dirs()
        else:
            error = None
            created = True
        if error:
            return self.format_error(error)
        else:
            if created:
                log_success.append("Created {0}".format(self.tools_setup.app_vars.tools_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()

        # APP DATA -------------------------------------------------------------------
        # update install_apps step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        if not self.testing:
            error = self.tools_setup.update_app_data()
        else:
            error = None
        if error:
            return self.format_error(error)
        else:
            log_success.append("Updated {0}".format(self.tools_setup.app_vars.app_data_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP PACKAGES ------------------------------------------------------------
        # update install_apps step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])
        if not self.testing:
            error = self.tools_setup.update_packages()
        else:
            error = None
        if error:
            return self.format_error(error)
        else:
            log_success.append("Updated {0}".format(self.tools_setup.app_vars.packages_dir))
        # update progress bar
        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()

        # SETUP APPS ---------------------------------------------------------------
        # update install_apps step in gui
        install_steps = install_steps + 1
        self.progress_label.setText(self.install_list[install_steps])

        if not self.testing:
            # ----> make sure shortcut link is on desktop, if not copy
            if not os.path.exists(self.tools_setup.app_vars.tools_shortcuts):
                shortcut_to_move = os.path.join(self.tools_setup.app_vars.setup_installed_path, "PyAniTools.lnk")
                logging.info(
                    "Step: Moving: {0} to {1}".format(self.tools_setup.app_vars.setup_installed_path + "\\PyAniTools.lnk",
                                                      self.tools_setup.app_vars.user_desktop)
                )
                error = pyani.core.util.move_file(shortcut_to_move, self.tools_setup.app_vars.user_desktop)
                if error:
                    return self.format_error(error)

        # first time tools installed
        if not os.path.exists(self.tools_setup.app_vars.apps_dir):
            if not self.testing:
                error = self.tools_setup.add_all_apps()
            else:
                error = None
            if error:
                return self.format_error(error)
            else:
                log_success.append("Installed Apps To {0}".format(self.tools_setup.app_vars.apps_dir))
        # already installed, doing a re-installation or update of core files
        else:
            # REINSTALL ONLY SECTION --------------------------------------------------------------------------------
            # if run type is setup, and we are here, then its a re-install. fresh installs don't get here since the
            # apps dir wouldn't exist. Due to windows resource management, the app mananger, which initiates the
            # re-install, can't delete the folder containing the app mngr exe. This leaves
            # C:\PyAniTools\installed\PyAppMngr\ around. A new install sees an app folder exists, and comes here instead
            # of the first install section above.
            # copies ffmpeg, icons, apps, and shortcuts, and tools updater
            if self.run_type == "setup":
                # ----> create shortcuts folder - add new apps will add the actual shortcut
                if not self.testing:
                    error = pyani.core.util.make_dir(self.tools_setup.app_vars.apps_shortcut_dir)
                else:
                    error = None
                logging.info("Creating shortcut directory: {0}".format(self.tools_setup.app_vars.apps_shortcut_dir))
                if error:
                    return self.format_error(error)
                else:
                    log_success.append(
                        "Created shortcuts folder: {0}".format(self.tools_setup.app_vars.apps_shortcut_dir)
                    )

                # ----> move icons
                if not os.path.exists(os.path.join(self.tools_setup.app_vars.apps_dir, "icons")):
                    # move the icons since don't exist
                    dir_to_move = os.path.join(self.tools_setup.app_vars.setup_installed_path, "icons")
                    logger.info(
                        "Step: Moving icons from {0} to {1}".format(dir_to_move, self.tools_setup.app_vars.apps_dir)
                    )
                    if not self.testing:
                        error = pyani.core.util.move_file(dir_to_move, self.tools_setup.app_vars.apps_dir)
                    else:
                        error = None
                    if error:
                        return self.format_error(error)
                    else:
                        log_success.append("Added Icons folder")

                # ----> copy ffmpeg
                if not os.path.exists(os.path.join(self.tools_setup.app_vars.apps_dir, "ffmpeg")):
                    # move ffmpeg since it doesn't exist
                    dir_to_move = os.path.join(self.tools_setup.app_vars.setup_installed_path, "ffmpeg")
                    logger.info(
                        "Step: Moving ffmpeg from {0} to {1}".format(dir_to_move, self.tools_setup.app_vars.apps_dir)
                    )
                    if not self.testing:
                        error = pyani.core.util.move_file(dir_to_move, self.tools_setup.app_vars.apps_dir)
                    else:
                        None
                    if error:
                        return self.format_error(error)
                    else:
                        log_success.append("Added ffmpeg")
            # END REINSTALL ONLY SECTION -----------------------------------------------------------------------------

            # REINSTALL AND UPDATE SECTION ---------------------------------------------------------------------------
            # ----> move the install update assistant
            file_to_move = os.path.join(
                self.tools_setup.app_vars.setup_installed_path, self.tools_setup.app_vars.iu_assist_exe
            )
            logger.info(
                "Step: Moving update / install assist exe from {0} to {1}".format(
                    file_to_move, self.tools_setup.app_vars.apps_dir
                )
            )
            if not self.testing:
                # check if iuassist.exe exists, if so remove from tools dir
                if os.path.exists(self.tools_setup.app_vars.iu_assist_path):
                    error = pyani.core.util.delete_file(self.tools_setup.app_vars.iu_assist_path)
                    if error:
                        return self.format_error(error)
            # move iuassist.exe from newly downloaded tools in temp dir to existing tools dir
            if not self.testing:
                error = pyani.core.util.move_file(file_to_move, self.tools_setup.app_vars.apps_dir)
            else:
                error = None
            if error:
                return self.format_error(error)
            else:
                log_success.append("Updated Install Update Assistant")

            # ----> update the updater, only happens if update tool exe doesn't exist in tools installed folder.
            #        Happens during a re-install or update of core files from app manager. Doesn't happen during
            #        automated updates
            existing_update_tool_path = os.path.join(
                self.tools_setup.app_vars.apps_dir,
                self.tools_setup.app_vars.update_exe
            )
            if not os.path.exists(existing_update_tool_path):
                file_to_move = os.path.join(
                    self.tools_setup.app_vars.setup_installed_path, self.tools_setup.app_vars.update_exe
                )
                logger.info(
                    "Step: Moving update exe from {0} to {1}".format(file_to_move, self.tools_setup.app_vars.apps_dir)
                )
                if not self.testing:
                    error = pyani.core.util.move_file(file_to_move, self.tools_setup.app_vars.apps_dir)
                else:
                    error = None
                if error:
                    return self.format_error(error)
                else:
                    log_success.append("Updated Tools Updater")

            # ----> move missing apps - returns either a list or none for new_apps
            if not self.testing:
                error, new_apps = self.tools_setup.add_new_apps()
            else:
                error = None
                new_apps = ["Testing Mode - Added Foo App"]
            if error:
                return self.format_error(error)
            else:
                log_success.append(
                    "Updated App Manager {0}".format(self.tools_setup.app_vars.app_mngr_path)
                )
                if new_apps:
                    log_success.append(
                        "Added the following apps: {0}".format(", ".join(new_apps))
                    )

        # NUKE --------------------------------------------------------------------

        # setup nuke modifying .nuke/init.py to check c:\users\{user_name}\.nuke\pyanitools\ (create
        # directory if doesn't exist).

        # first check for .nuke  folder in C:Users\username
        if not self.testing:
            error, created = self.tools_setup.make_nuke_dir()
        else:
            error = None
            created = True
        if error:
            return self.format_error(error)
        else:
            if created:
                log_success.append("Created {0}".format(self.ani_vars.nuke_user_dir))

        # check for custom nuke folder in C:PyAniTools\
        if not self.testing:
            error, created = self.tools_setup.make_custom_nuke_dir()
        else:
            error = None
            created = True
        if error:
            return self.format_error(error)
        else:
            if created:
                log_success.append("Created {0}".format(self.ani_vars.nuke_custom_dir))

        # copy custom init.py, menu.py, and .py (script with python code to support menu and gizmos)
        # Note: remove the files first, copy utils seem to not like existing files
        if not self.testing:
            error = self.tools_setup.copy_custom_nuke_init_and_menu_files()
        else:
            error = None
        if error:
            return self.format_error(error)
        else:
            log_success.append("Updated {0}".format(self.ani_vars.nuke_custom_dir))

        # finally update the init.py - only append, don't want to lose existing code added by user
        if not self.testing:
            error, added_plugin_path = self.tools_setup.add_custom_nuke_path_to_init()
        else:
            error = None
            added_plugin_path = True
        if error:
            return self.format_error(error)
        else:
            if added_plugin_path:
                log_success.append("Added {0} to {1}".format(
                    self.tools_setup.app_vars.custom_plugin_path, self.tools_setup.app_vars.nuke_init_file_path)
                )

        self.progress.setValue(self.progress.value() + self.progress_steps)
        QtWidgets.QApplication.processEvents()

        return log_success

    @staticmethod
    def format_error(error):
        """
        Simple utility to format errors
        :param error: the error as a string
        :return a string set to color red using html
        """
        return "<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error)