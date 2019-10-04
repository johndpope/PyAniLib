import os
import logging
import re
import mmap
import time
from datetime import datetime
# need to import _strptime for multi-threading, a known python 2.7 bug
import _strptime
import pyani.core.appvars
import pyani.core.anivars
import pyani.core.ui
import pyani.core.util

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtCore, QtWidgets
from PyQt4.QtCore import pyqtSignal

logger = logging.getLogger()


class AniCoreMngr(QtCore.QObject):
    """
    Class to manage getting server data. Currently configured to connect to CGT and use
    pyqt. Could refactor to use other gui apis and data access. To change gui:

    Provides multi-threading access for downloads and file directory listings.

    Based off CGT's approved and work folder structure where approved assets have no version in file name, and store
    versions in approved/history. Work folders list all files with versions directly beneath the work folder.
    ex:
    root folder/approved/file.ext
    root folder/approved/history/file_v003.ext
    root folder/approved/history/file_v002.ext
    root folder/approved/history/file_v001.ext
    root folder/work/file_v001.ext
    """

    # general signal for successful tasks
    finished_signal = pyqtSignal(object)
    # signal that lets other objects know this class is done building local cache
    finished_cache_build_signal = pyqtSignal(object)
    # signal that lets other objects know this class is done syncing with cgt and downloading
    finished_sync_and_download_signal = pyqtSignal(object)
    # signal that lets other objects know this class is done checking for asset changes
    finished_tracking = pyqtSignal(object)
    # error message for other classes to receive when doing any local file operations
    error_thread_signal = pyqtSignal(object)

    def __init__(self):
        QtCore.QObject.__init__(self)

        self.app_vars = pyani.core.appvars.AppVars()
        self.ani_vars = pyani.core.anivars.AniVars()

        self.thread_pool = QtCore.QThreadPool()
        logger.info("Multi-threading with maximum %d threads" % self.thread_pool.maxThreadCount())
        self.thread_total = 0.0
        self.threads_done = 0.0
        self.thread_error_occurred = False

        # this allows the ui time to display info about this task. Some tasks/methods run very fast, and never
        # show in ui as being run. This is purely cosmetic, so user sees the task running. The time below is in
        # seconds
        self.time_to_pause_for_ui = 1.0

        # for reporting progress
        self.progress_win = QtWidgets.QProgressDialog()
        self.progress_win.hide()

    def set_number_of_concurrent_threads(self, thread_num=None):
        """
        Sets the pyqt thread count. Caps at the pyqt thread max count, which is number of cores on machine.
        :param thread_num: an integer number for the amount of threads to run concurrently
        """
        if not thread_num or thread_num > self.thread_pool.maxThreadCount():
            self.thread_pool.setMaxThreadCount(self.thread_pool.maxThreadCount())
            logger.info("Multi-threading with %d threads" % self.thread_pool.maxThreadCount())
        else:
            self.thread_pool.setMaxThreadCount(thread_num)

    def get_preference(self, app, category, pref_name):
        """
        Get's preference value if exists, otherwise creates preference file and gets default preference value
        :param app: the application the preference applies to, see pyani.core.appvars.AppVars for apps with pref
        :param category: the application category, see pyani.core.appvars.AppVars for app pref catgeories
        :param pref_name: name of the preference
        :return: dict if pref exists as {pref_name: pref_value} or error as string
        """
        pref = self._load_preferences()

        # if preferences didn't load, try to create
        if not pref:
            # check for creation errors
            error = self._create_preferences()
            if error:
                error_fmt = "Could not create preferences, error is: {0}".format(error)
                return error_fmt

            # if no errors creating then load preferences
            pref = self._load_preferences()
            # check for error loading
            if not pref:
                error_fmt = "Could not load preferences, error is: {0}".format(pref)
                return error_fmt

        return {pref_name: pyani.core.util.find_val_in_nested_dict(pref, [app, category, pref_name])}

    def save_preference(self, app, category, pref_name, pref_value):
        """
        Saves the preference value to the preferences file
        :param app: the application the preference applies to, see pyani.core.appvars.AppVars for apps with pref
        :param category: the application category, see pyani.core.appvars.AppVars for app pref catgeories
        :param pref_name: name of the preference
        :param pref_value: value to save for the preference
        :return: None if saved successfully, error as a string if can't save
        """
        # load so we can get current preferences data
        pref_data = self._load_preferences()
        # check for error loading
        if not pref_data:
            error_fmt = "Could not load preferences, error is: {0}".format(pref_data)
            return error_fmt

        # store new preference value, but first check preference exists
        if pyani.core.util.find_val_in_nested_dict(pref_data, [app, category, pref_name]) is None:
            error_fmt = "Preference, {0}, does not exist.".format(pref_name)
            return error_fmt
        pref_data[app][category][pref_name] = pref_value

        # save preference
        error = pyani.core.util.write_json(self.app_vars.preferences_filename, pref_data)

        if error:
            error_fmt = "Could not save preferences, error is: {0}".format(error)
            return error_fmt

        return None

    def _create_preferences(self):
        """
        Creates the preference file when it doesn't exist
        :return: None or the error as a string when can't create the file
        """
        if not os.path.exists(self.app_vars.preferences_filename):
            error = pyani.core.util.write_json(self.app_vars.preferences_filename, self.app_vars.preferences_template)
            if error:
                return error
        return None

    def _load_preferences(self):
        """
        Load preferences file
        :return: None if can't load, otherwise returns the dict of preferences
        """
        # load the preferences
        pref = pyani.core.util.load_json(self.app_vars.preferences_filename)
        # check if loaded, if not return none
        if not isinstance(pref, dict):
            return None

        return pref

    def create_setup_dependencies(self, setup_dir=None):
        """
        Install any files needed by setup. Looks for files in folder setup runs in first, then checks pyanitools folder,
        and shows error if can't find in either.
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # no directory provided, so use current working directory
        if not setup_dir:
            setup_dir = os.getcwd()

        # find app_bridge, check in setup folder first
        if self.app_vars.cgt_bridge_api_dir in os.listdir(setup_dir):
            # remove and recreate tool directory if exists
            if os.path.exists(self.app_vars.tools_dir):
                error = pyani.core.util.rm_dir(self.app_vars.tools_dir)
                if error:
                    error_fmt = (
                        "Error occurred deleting existing pyanitools folder. Error is {0}.".format(error)
                    )
                    self.send_thread_error(error_fmt)
                    logger.error(error_fmt)
                    return error_fmt
            # make directories
            error = pyani.core.util.make_all_dir_in_path(self.app_vars.cgt_bridge_api_path)
            if error:
                error_fmt = (
                    "Error occurred making app bridge folder. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
            # now copy app_bridge files to pyanitools dir
            src = os.path.join(setup_dir, self.app_vars.cgt_bridge_api_dir)
            error = pyani.core.util.copy_files(src, self.app_vars.cgt_bridge_api_path)
            if error:
                error_fmt = (
                    "Error occurred copying app bridge files. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        # check if app_bridge in local lib dir
        elif os.path.exists(self.app_vars.cgt_bridge_api_path):
            # copy to temp dir, so can recopy back.
            temp_loc = os.path.join(self.app_vars.tools_temp_dir, "temp_app_bridge")
            error = pyani.core.util.make_all_dir_in_path(temp_loc)
            if error:
                error_fmt = (
                    "Error occurred making temp app bridge folder for copy. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
            error = pyani.core.util.copy_files(self.app_vars.cgt_bridge_api_path, temp_loc)
            if error:
                error_fmt = (
                    "Error occurred copying app bridge files to temp dir. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
            # remove and recreate tool directory if exists
            if os.path.exists(self.app_vars.tools_dir):
                error = pyani.core.util.rm_dir(self.app_vars.tools_dir)
                if error:
                    error_fmt = (
                        "Error occurred deleting existing pyanitools folder. Error is {0}.".format(error)
                    )
                    self.send_thread_error(error_fmt)
                    logger.error(error_fmt)
                    return error_fmt
            # make directories
            error = pyani.core.util.make_all_dir_in_path(self.app_vars.cgt_bridge_api_path)
            if error:
                error_fmt = (
                    "Error occurred making app bridge folder. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
            # copy back from temp dir
            error = pyani.core.util.copy_files(temp_loc, self.app_vars.cgt_bridge_api_path)
            if error:
                error_fmt = (
                    "Error occurred copying app bridge files in temp dir to pyanitools dir. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        # doesn't exist, need to re-download install zip
        else:
            error_fmt = (
                "Could not find setup files needed. Please re-download the install package."
            )
            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        # remove persistent directory
        if  os.path.exists(self.app_vars.persistent_data_path):
            error = pyani.core.util.rm_dir(self.app_vars.persistent_data_path)
            if error:
                error_fmt = "Could not remove user preferences folder. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)
        return None

    def create_desktop_shortcut(self):
        """
        Movies the desktop shortcut the pyanitools tools directory to the desktop
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # remove if exists
        if os.path.exists(self.app_vars.pyanitools_desktop_shortcut_path):
            error = pyani.core.util.delete_file(self.app_vars.pyanitools_desktop_shortcut_path)
            if error:
                error_fmt = (
                    "Error occurred deleting old desktop shortcut. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        # copy the shortcut to desktop
        src = os.path.join(self.app_vars.local_pyanitools_shortcuts_dir, self.app_vars.pyanitools_desktop_shortcut_name)
        error = pyani.core.util.copy_file(src, self.app_vars.pyanitools_desktop_shortcut_path)
        if error:
            error_fmt = (
                "Error occurred moving new desktop shortcut. Error is {0}.".format(error)
            )
            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)
        return None

    def customize_nuke(self):
        """
        Creates custom init file in .nuke dir of user. Adds plugin path that points back to tools dir lib to access
        custom init and menu
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # setup nuke modifying .nuke/init.py to check c:\users\{user_name}\.nuke\pyanitools\ (create
        # directory if doesn't exist).

        # first check for .nuke folder in C:Users\username
        if not os.path.exists(self.ani_vars.nuke_user_dir):
            error = pyani.core.util.make_dir(self.ani_vars.nuke_user_dir)
            if error:
                error_fmt = (
                    "Error occurred creating .nuke in user directory. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        # check for init.py in C:Users\username\.nuke
        if not os.path.exists(os.path.join(self.ani_vars.nuke_user_dir, "init.py")):
            error = pyani.core.util.make_file(os.path.join(self.ani_vars.nuke_user_dir, "init.py"))
            if error:
                error_fmt = (
                    "Error occurred creating nuke .init file. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        # update the init.py - only append, don't want to lose existing code added by user
        try:
            # check if file empty, mmap won't work with empty files
            if os.stat(self.app_vars.nuke_init_file_path).st_size == 0:
                with open(self.app_vars.nuke_init_file_path, "w") as init_file:
                    init_file.write("\n" + self.app_vars.custom_plugin_path + "\n")
                    init_file.close()
            else:
                with open(self.app_vars.nuke_init_file_path, "a+") as init_file:
                    # use mmap just in case init.py is large, shouldn't be, just a precaution. Otherwise could just
                    # load into a string - note in python 3 mmap is like bytearray
                    file_in_mem = mmap.mmap(init_file.fileno(), 0, access=mmap.ACCESS_READ)
                    if file_in_mem.find(self.app_vars.custom_plugin_path) == -1:
                        init_file.write("\n" + self.app_vars.custom_plugin_path + "\n")
                        init_file.close()
        except (IOError, OSError, ValueError) as e:
            error = "Could not open {0}. Received error {1}".format(self.app_vars.nuke_init_file_path, e)
            self.send_thread_error(error)
            logger.error(error)
            return error

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)
        return None

    def create_windows_task_sched(self):
        """
        Create the daily update task
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # create a task scheduler object
        task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_update", r"'{0}' {1} {2}".format(
                self.app_vars.pyanitools_support_launcher_path,
                self.app_vars.local_pyanitools_core_dir,
                self.app_vars.pyanitools_update_app_name
            )
        )

        # remove existing task if there
        is_scheduled = task_scheduler.is_task_scheduled()
        # check for errors getting state
        if not isinstance(is_scheduled, bool):
            error_fmt = "Can't get Windows Task state. Error is: {0}".format(is_scheduled)
            self.send_thread_error(error_fmt)
            logging.error(error_fmt)
            return error_fmt

        if is_scheduled:
            error = task_scheduler.delete_task()
            if error:
                error_fmt = "Can't Delete Windows Task. Error is: {0}".format(error)
                self.send_thread_error(error_fmt)
                logging.error(error_fmt)
                return error_fmt

        # schedule tools update to run, if it is already scheduled skips. If scheduling errors then informs user
        # but try to install apps
        error = task_scheduler.setup_task(schedule_type="daily", start_time="14:00")
        if error:
            error_fmt = "Can't Setup Windows Task Scheduler. Error is: {0}".format(error)
            self.send_thread_error(error_fmt)
            logging.error(error_fmt)
            return error_fmt

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)

    def create_support_launcher(self):
        """
        Movies the support launcher from the pyanitools tools directory tp the persistent data location
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # remove if exists
        if os.path.exists(self.app_vars.pyanitools_support_launcher_path):
            error = pyani.core.util.delete_file(self.app_vars.pyanitools_support_launcher_path)
            if error:
                error_fmt = (
                    "Error occurred deleting old support launcher. Error is {0}.".format(error)
                )
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
        # doesn't exist, check if persistent dir exists, if not make it
        else:
            if not os.path.exists(self.app_vars.persistent_data_path):
                error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
                if error:
                    error_fmt = "Could not create user preferences folder. Error is {0}".format(error)
                    self.send_thread_error(error_fmt)
                    return error_fmt

        # copy the launcher to persistent data location
        src = os.path.join(self.app_vars.local_pyanitools_core_dir, self.app_vars.pyanitools_support_launcher_name)
        error = pyani.core.util.copy_file(src, self.app_vars.pyanitools_support_launcher_path)
        if error:
            error_fmt = (
                "Error occurred moving new support launcher. Error is {0}.".format(error)
            )
            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)
        return None

    def create_sequence_list(self):
        """
        Calls cgt api to update the list of show info - sequences, shots, frame start/end. Stores in the path defined
        by self.app_vars.sequence_list_json
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
          """
        # check if persistent folder exists, if not make it
        if not os.path.exists(self.app_vars.persistent_data_path):
            error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
            if error:
                error_fmt = "Could not create user preferences folder. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

        # download the file
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_show_info.py")
        dl_command = [
            py_script,
            self.ani_vars.sequence_shot_list_json,
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        try:
            output, error = pyani.core.util.call_ext_py_api(dl_command)
            # error from trying to open subprocess
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt
        except pyani.core.util.CGTError as error:
            error_fmt = (
                "Error occurred connecting to CGT. Error is {0}.".format(error)
            )
            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        self.finished_signal.emit(None)
        return None

    def create_update_config_file(self):
        """
        Creates the initial settings for the update config file. Initially all tools are set to auto update
        :return: None if no errors and succeeds. error returned as a string. Also fires a signal via
        send_thread_error() when in a multi-threaded mode and can't receive return values
        """
        # check if persistent folder exists, if not make it
        if not os.path.exists(self.app_vars.persistent_data_path):
            error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
            if error:
                error_fmt = "Could not create user preferences folder. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

        # create the init config for the file
        init_config = {
            "tools": dict()
        }

        tools_cache = self.load_server_local_cache(self.app_vars.cgt_tools_cache_path)
        # check for error
        if not isinstance(tools_cache, dict):
            error = "Could not create the update config file, error loading tools cache. " \
                    "Error is {0}".format(tools_cache)
            self.send_thread_error(error)
            return error

        # cache loaded so now make the init settings
        for tool_category in tools_cache:
            if tool_category not in init_config['tools']:
                init_config['tools'][tool_category] = dict()
            for tool_type in tools_cache[tool_category]:
                if tool_type not in init_config['tools'][tool_category]:
                    init_config['tools'][tool_category][tool_type] = list()
                for tool_name in tools_cache[tool_category][tool_type]:
                    init_config['tools'][tool_category][tool_type].append(tool_name)

        # write update config file to disk
        error = pyani.core.util.write_json(self.app_vars.update_config_file, init_config)
        if error:
            error = "Could not create the update config file, error writing file. " \
                    "Error is {0}".format(tools_cache)
            self.send_thread_error(error)
            return error

        # wait a short duration, otherwise completes too fast and gui never shows as run. This is purely for user so
        # they can see the task displayed in ui.
        time.sleep(self.time_to_pause_for_ui)

        self.finished_signal.emit(None)
        return None

    def read_update_config(self):
        """
        Reads the asset config file from disk.
        :return: the config json data or error if can't read the file
        """
        if os.path.exists(self.app_vars.update_config_file):
            json_data = pyani.core.util.load_json(self.app_vars.update_config_file)
            return json_data
        return "The update configuration file doesn't exist."

    def is_asset_in_update_config(self, asset_type, asset_component, asset_name, asset_subcomponent=None):
        """
        Checks for the existence of an asset in the update config file
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: name of the asset as a string
        :param asset_subcomponent: the sub component. Optional, only some assets have this, for ex tools
        :return: True if the asset exists, False if not
        """
        # pull the config data off disk - may have changed so we want the latest
        existing_config_data = pyani.core.util.load_json(self.app_vars.update_config_file)
        # make sure file was loaded
        if not isinstance(existing_config_data, dict):
            return False

        # check if the asset type, component, and name exist
        if asset_type in existing_config_data:
            if asset_component in existing_config_data[asset_type]:
                if asset_subcomponent:
                    if asset_subcomponent in existing_config_data[asset_type][asset_component]:
                        if asset_name in existing_config_data[asset_type][asset_component][asset_subcomponent]:
                            return True
                else:
                    if asset_name in existing_config_data[asset_type][asset_component]:
                        return True
        return False

    def sync_local_cache_with_server(self, update_data_dict=None):
        """
        Updates the cache on disk with the current server data. If no parameters are filled the entire cache will
        be rebuilt.
        :param update_data_dict: a dict of update data, see child class doc string
        """
        print ("virutal method, implement")

    def sync_local_cache_with_server_and_download_gui(self, update_data_dict):
        """
        used with gui asset mngr
        Updates the cache on disk with the current server data and downloads files.
        :param update_data_dict: a dict of update data, see child class doc string
        """
        print ("virutal method, implement")

    def server_download_no_sync(self, update_data_dict=None):
        """
        Updates the cache on disk with the current server data and downloads files.
        :param update_data_dict: a dict of update data, see child class doc string
        """
        print ("virutal method, implement")

    @staticmethod
    def load_server_local_cache(file_path):
        """
        reads the server info cache off disk
        :return: the data, note the load json will return a string error if there is an error
        """
        return pyani.core.util.load_json(file_path)

    def server_get_dir_list(self,
                            server_path,
                            dirs_only=True,
                            files_only=False,
                            files_and_dirs=False,
                            walk_dirs=False,
                            absolute_paths=False
                            ):
        """
        Called to get a list of files and/or directories for a given path where data resides
        :param server_path: the path to the data
        :param dirs_only: only return directories
        :param files_only: only return files
        :param files_and_dirs: return files and directories
        :param walk_dirs: whether to walk sub directories
        :param absolute_paths: whether to get absolute path or just file name
        :return: a list of files or directories, or an error string
        :exception: CGTError if can't connect or CGT returns an error
        """
        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        # the command that subprocess will execute
        command = [
            py_script,
            server_path,  # path to directory to get file list
            "",  # getting a file list so no download paths
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        # the actual parameter in app bridge file is get_file_list_no_walk, so we set to the opposite of the value
        # passed in
        if walk_dirs:
            command.append("False")
        else:
            command.append("True")
        # add optional parameters to indicate whether we want files, folders, or both
        if files_and_dirs:
            # tell cgt to only get files
            command.append("files_and_dirs")
        elif files_only:
            # tell cgt to only get files
            command.append("files")
        elif dirs_only:
            # tell cgt to only get files
            command.append("dirs")

        try:
            output, error = pyani.core.util.call_ext_py_api(command)

            # check for subprocess errors
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

            # check for output
            if output:
                file_list = output.split(",")
                if not absolute_paths:
                    file_paths = [
                        file_path.split("/")[-1].replace("\n", "").replace("\r", "") for file_path in file_list
                    ]
                else:
                    file_paths = [
                        file_path.replace("\n", "").replace("\r", "") for file_path in file_list
                    ]
                return file_paths
        # CGT errors
        except pyani.core.util.CGTError as error:
            error_fmt = "Error occurred connecting to CGT. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt

    def server_is_file(self, server_path):
        """
        Checks if the path on the server is a file or a directory
        :param server_path: the path on the server
        :return: True if a file, False if its a directory
        :exception: CGTError if can't connect or CGT returns an error
        """
        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        # the command that subprocess will execute
        command = [
            py_script,
            server_path,  # path to directory to get file list
            "",  # getting a file list so no download paths
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        # expects these optional parameters for recursion and files or directories for listing, not used but
        # since we didn't do keywords, have to provide
        command.append("False")
        command.append("files_and_dirs")
        # this says check if file or dir
        command.append("True")

        try:
            output, error = pyani.core.util.call_ext_py_api(command)

            # check for subprocess errors
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

            # check for output
            if output:
                if output.strip() == "True":
                    return True
                else:
                    return False
        # CGT errors
        except pyani.core.util.CGTError as error:
            error_fmt = "Error occurred connecting to CGT. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt

    def server_file_exists(self, server_path):
        """
        Checks if the file path on the server exists
        :param server_path: the path on the server
        :return: True if exists, False if not
        :exception: CGTError if can't connect or CGT returns an error
        """
        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        # the command that subprocess will execute
        command = [
            py_script,
            server_path,  # path to directory to get file
            "",  # getting a file list so no download paths
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        # expects these optional parameters for recursion and files or directories for listing, not used but
        # since we didn't do keywords, have to provide
        command.append("False")
        command.append("files_and_dirs")
        # this says check if file or dir - not interested in this so False
        command.append("False")
        # check if path exists
        command.append("True")

        try:
            output, error = pyani.core.util.call_ext_py_api(command)

            # check for subprocess errors
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

            # check for output
            if output:
                if output.strip() == "True":
                    return True
                else:
                    return False
        # CGT errors
        except pyani.core.util.CGTError as error:
            error_fmt = "Error occurred connecting to CGT. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt

    def server_file_modified_date(self, server_path):
        """
        Get the last modified date for file from server
        :param server_path: the path on the server
        :return: a date/time object or error as string if couldn't get time
        :exception: CGTError if can't connect or CGT returns an error
        """
        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        # the command that subprocess will execute
        command = [
            py_script,
            server_path,  # path to directory to get file
            "",  # getting a file list so no download paths
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        # expects these optional parameters for recursion and files or directories for listing, not used but
        # since we didn't do keywords, have to provide
        command.append("False")
        command.append("files_and_dirs")
        # this says check if file or dir - not interested in this so False
        command.append("False")
        # check if path exists
        command.append("False")
        # get modified date
        command.append("True")

        try:
            output, error = pyani.core.util.call_ext_py_api(command)

            # check for subprocess errors
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

            # check for output
            if output:
                try:
                    # remove newlines
                    date_str = output.strip("\n")
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    return e

        # CGT errors
        except pyani.core.util.CGTError as error:
            error_fmt = "Error occurred connecting to CGT. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt

    def server_file_download(self, server_file_paths, local_file_paths=None, update_local_version=False):
        """
        Downloads files from server
        :param server_file_paths: a list of server file paths
        :param local_file_paths: a list of the local file paths where cgt files stored
        :param update_local_version: a boolean indicating whether the version file on disk should be updated after
        a successful download
        :return: error as string or None
        :exception: CGTError if can't connect or CGT returns an error
        """

        # we need a list, if a single path was passed, then convert to a list
        if not isinstance(server_file_paths, list):
            server_file_paths = [server_file_paths]

        # we need a list, if a single path was passed, then convert to a list
        if not isinstance(local_file_paths, list):
            local_file_paths = [local_file_paths]

        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")

        # if paths provided use them
        if local_file_paths:
            local_dl_paths = local_file_paths
        # no paths provided so convert cgt path to a local path
        else:
            local_dl_paths = list()
            # download location for files - convert cgt path to local path
            for cgt_file_path in server_file_paths:
                # remove file name
                download_dir = "/".join(cgt_file_path.split("/")[:-1])
                local_dl_paths.append(self.convert_server_path_to_local_server_representation(download_dir))

        # download command - convert lists to strings separated by comma so that they can be passed as command
        # line arguments
        dl_command = [
            py_script,
            ",".join(server_file_paths),
            ",".join(local_dl_paths),
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]

        try:
            output, error = pyani.core.util.call_ext_py_api(dl_command)

            # error from trying to open subprocess
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                logger.error(error_fmt)
                return error_fmt

        except pyani.core.util.CGTError as error:
            error_str = str(error)
            # look for doesn't exist, so we can give a better error to user
            if not error_str.find("doesn't exist") == -1:
                error_fmt = (
                    "The file(s) {0} are missing. Please try running the update application to sync your local "
                    "CGT cache. If the problem persists, check CGT to see if the file was removed.".format(
                        server_file_paths
                    )
                )
            else:
                error_fmt = (
                    "Error occurred downloading from CGT. Error is: {0}. Attempted to download files {1} to {2}"
                    .format(error, ', '.join(server_file_paths), ', '.join(local_dl_paths))
                )

            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        # download successful, check if the local version file should be updated
        if update_local_version:
            errors = list()
            for index, cgt_file_path in enumerate(server_file_paths):
                error = self.update_local_version(cgt_file_path, local_file_paths[index])
                if error:
                    errors.append(error)
            if errors:
                error = "Error updating cgt metadata. The following errors occurred: {0}".format(", ".join(errors))
                self.send_thread_error(error)
                logger.error(error)
                return error

        return None

    def core_get_latest_version(self, server_path_to_files):
        """
        gets the latest file name and version of a file based off files having versions in their name
        :param server_path_to_files: the cgt cloud path to the asset component's files
        :return: the most recent file's name and version as a tuple (file name, version)
        """
        # get the list of files, these should be a bunch of files with versions in the file name
        file_list = self.server_get_dir_list(server_path_to_files, files_only=True)
        latest_version = ""
        version_num = ""
        # pattern to use to check for version in the file name
        version_pattern = "v\d{3,}"
        # make sure there are files in the folder
        if file_list:
            # files should be {asset_type}{asset_name}_{asset_component}_{version}_..., ex: charQian_rig_v003_high.mb
            # however its possible to get a charQian_rig_high.mb (i.e. no version) mixed in. So discard those. Also
            # discard any notes files
            cleaned_file_list = [
                file_name for file_name in file_list
                if re.search(version_pattern, file_name) and
                file_name.split(".")[-1] not in self.app_vars.notes_format_supported
            ]

            # make sure there are valid files with versions
            if cleaned_file_list:
                # next sort the list to get the latest, since it's sorted, the first element is the latest version.
                # uses natural sorting
                convert = lambda text: int(text) if text.isdigit() else text
                alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
                # this is the file name
                latest_version = sorted(cleaned_file_list, key=alphanum_key, reverse=True)[0]
                # grab the version from the file name
                version_num = re.search(version_pattern, latest_version).group()
        return latest_version, version_num

    def update_local_version(self, server_file_path, local_file_path_dir):
        """
        Updates the version in the local metadata file. Creates file if doesn't exist
        :param server_file_path: path to data files
        :param local_file_path_dir: the directory of the local file path of the downloaded file
        :return: None if no error, error as string if occurs
        """

        # split off path up to root directory of file, removing file name and approved or work folder
        cgt_path_to_version_history = '/'.join(server_file_path.split("/")[:-1])
        # check if approved or work, approved requires adding /history/ to end of path
        if "approved" in server_file_path:
            cgt_path_to_version_history = "{0}/history/".format(cgt_path_to_version_history)

        # get latest version
        file_name, version = self.core_get_latest_version(cgt_path_to_version_history)

        # open metadata file
        local_version_path = os.path.join(local_file_path_dir, self.app_vars.cgt_metadata_filename)

        json_data = pyani.core.util.load_json(local_version_path)

        # file exists, update
        if isinstance(json_data, dict):
            json_data["version"] = version
        # no meta data file yet, so add key and value
        else:
            json_data = {"version": version}
        # save version to metadata file
        error = pyani.core.util.write_json(local_version_path, json_data, indent=4)
        if error:
            error_fmt = "Error updating local version. The following errors occurred: {0}".format(error)
            self.send_thread_error(error_fmt)
            logger.error(error_fmt)
            return error_fmt

        return None

    def find_new_and_updated_assets(self, timestamp_before_dl, assets_before_sync, assets_after_sync):
        """

        :param timestamp_before_dl: a dictionary of assets with last modified timestamps. In format:
        {
            asset_type: {
                asset_category: [
                    asset name: last modified time using os.path.getmtime()
                ]
            }
        }
        :param assets_before_sync: a dictionary of assets before sync with CGT server in format:
        {
            asset_type: {
                asset_category: {
                    asset_name : {
                        metadata such as files associated with asset. this is the local cgt cache
                    },
                },
            }
        }
        :param assets_after_sync: a dictionary of assets after sync with CGT server in format:
        {
            asset_type: {
                asset_category: {
                    asset_name : {
                        metadata such as files associated with asset. this is the local cgt cache
                    },
                },
            }
        }
        :return: a dictionary of assets added, a dictionary of assets modified, a dictionary of assets removed. All
        dictionaries are in the format:

        format:
        {
            asset_type: {
                asset_category: [
                    list of assets
                ]
            }
        }
        """
        new_assets = dict()
        changed_assets = dict()
        removed_assets = dict()

        # check for updated assets - check if file got updated -
        # timestamp_before_dl is a list of all downloaded assets
        for asset_type in timestamp_before_dl:
            for asset_category in timestamp_before_dl[asset_type]:
                for asset_name in timestamp_before_dl[asset_type][asset_category]:
                    for file_name, modified_time_before_dl in timestamp_before_dl[asset_type][asset_category][asset_name].items():
                        # ignore metadata files
                        if self.app_vars.cgt_metadata_filename not in file_name:
                            modified_time_after_dl = os.path.getmtime(file_name)
                            if not modified_time_before_dl == modified_time_after_dl:
                                if asset_type not in changed_assets:
                                    changed_assets[asset_type] = dict()
                                if asset_category not in changed_assets[asset_type]:
                                    changed_assets[asset_type][asset_category] = list()
                                # get version if exists, returns {asset name: version} where version is string or none
                                asset_info = self._get_latest_version(assets_after_sync, asset_type, asset_category, asset_name)
                                changed_assets[asset_type][asset_category].append(asset_info)

        # check for removed assets and added or removed files from existing assets
        for asset_type in assets_before_sync:
            for asset_category in assets_before_sync[asset_type]:
                for asset_name in assets_before_sync[asset_type][asset_category]:
                    # first see if the asset still exists
                    if asset_name in assets_after_sync[asset_type][asset_category]:
                        # NOTE: key can be called files or file name so check for both
                        if 'files' in assets_after_sync[asset_type][asset_category][asset_name]:
                            files_before_sync = assets_before_sync[asset_type][asset_category][asset_name]['files']
                            files_after_sync = assets_after_sync[asset_type][asset_category][asset_name]['files']
                        else:
                            files_before_sync = assets_before_sync[asset_type][asset_category][asset_name]['file name']
                            files_after_sync = assets_after_sync[asset_type][asset_category][asset_name]['file name']

                        # sort so in same order, need to check though that there is a list because could be None
                        if files_before_sync:
                            files_before_sync = sorted(files_before_sync)
                        if files_after_sync:
                            files_after_sync = sorted(files_after_sync)

                        # see if any files were added or removed
                        if not files_after_sync == files_before_sync:
                            if asset_type not in changed_assets:
                                changed_assets[asset_type] = dict()
                            if asset_category not in changed_assets[asset_type]:
                                changed_assets[asset_type][asset_category] = list()
                            # asset may have already been added to the list from the timestamp check,
                            # don't add twice
                            if asset_name not in changed_assets[asset_type][asset_category]:
                                # get version if exists, returns {asset name: version} where version is string or none
                                asset_info = self._get_latest_version(assets_after_sync, asset_type, asset_category, asset_name)
                                changed_assets[asset_type][asset_category].append(asset_info)
                    # asset removed
                    else:
                        if asset_type not in removed_assets:
                            removed_assets[asset_type] = dict()
                        if asset_category not in removed_assets[asset_type]:
                            removed_assets[asset_type][asset_category] = list()
                        # get version if exists, returns {asset name: version} where version is string or none
                        asset_info = self._get_latest_version(assets_before_sync, asset_type, asset_category, asset_name)
                        removed_assets[asset_type][asset_category].append(asset_info)

        # check for new assets
        for asset_type in assets_after_sync:
            for asset_category in assets_after_sync[asset_type]:
                for asset_name in assets_after_sync[asset_type][asset_category]:
                    # first see if the asset still exists
                    if asset_name not in assets_before_sync[asset_type][asset_category]:
                        if asset_type not in new_assets:
                            new_assets[asset_type] = dict()
                        if asset_category not in new_assets[asset_type]:
                            new_assets[asset_type][asset_category] = list()
                        # get version if exists, returns {asset name: version} where version is string or none
                        asset_info = self._get_latest_version(assets_after_sync, asset_type, asset_category, asset_name)
                        new_assets[asset_type][asset_category].append(asset_info)

        return new_assets, changed_assets, removed_assets

    @staticmethod
    def _get_latest_version(assets_cache, asset_type, asset_category, asset_name):
        """
        Gets version if it exists from asset cache, works for both tool assets, shot assets, and show assets
        :param assets_cache: the local cgt server cache, see docstring in pyani.core.mngr.asset.py and tool.py
        for format
        :param asset_type: the type of asset to update - see pyani.core.appvars.py for asset types
        :param asset_category: the asset component/category to update- see pyani.core.appvars.py for asset components/
        categories
        :param asset_name: asset name
        :return: a dictionary with the asset name: version. dictionary used rather than tuple since more easily
        expandable to include other asset information if needed
        """
        # if 'version info' key is present it's a tool, otherwise asset
        if 'version info' in assets_cache[asset_type][asset_category][asset_name]:
            # make sure version exists
            if assets_cache[asset_type][asset_category][asset_name]['version info']:
                # it's the first element of 'version info' because that's the latest version always
                version = assets_cache[asset_type][asset_category][asset_name]['version info'][0]['version']
            else:
                version = None
        # other asset
        else:
            version = assets_cache[asset_type][asset_category][asset_name]['version']
        asset_info = {asset_name: version}
        return asset_info

    @staticmethod
    def convert_server_path_to_local_server_representation(server_path, directory_only=False):
        """
        converts a cgt path in cloud to a local path on the local representation of the server, i.e. Z drive
        :param server_path: the server path
        :param directory_only: whether to convert full path or path up to file name
        :return: the converted path on the local drive
        """
        local_path = "Z:"
        # split up the cgt path and rebuild with backslashes
        server_path_split = server_path.split("/")
        # check if we want the directory or the file name too
        if directory_only:
            server_path_split = server_path_split[:-1]
        for path_component in server_path_split:
            local_path = "{0}\\{1}".format(local_path, path_component)
        return os.path.normpath(local_path)

    def is_file_on_local_server_representation(self, server_dir, local_dir):
        """
        check if a file is stored locally on the server representation drive. For example, the cloud server is Z:...,
        so check if file is on a local Z:... drive or somewhere else
        :param server_dir: the server path of the directory holding file
        :param local_dir: the local path of the directory holding file
        :return: True if local and server are the same drive, False if not
        """
        # convert to a local path to compare server and local
        cloud_path_converted_to_local = self.convert_server_path_to_local_server_representation(server_dir)

        # if paths are the same for local and server - i.e. putting files in Z:\...., otherwise not
        if local_dir == cloud_path_converted_to_local:
            return True
        else:
            return False

    def convert_server_path_to_non_local_server(self, server_dir, local_dir, file_name, directory_only=False):
        """
        converts a cgt path in cloud to a local path on the local representation of the server, i.e. Z drive
        :param server_dir: the server path of the directory holding the file
        :param local_dir: the local path of the directory holding the file
        :param file_name: full path of the file
        :param directory_only: whether to convert full path or path up to file name
        :return: the converted path on the local drive
        """
        # convert to a local path to compare server and local
        cloud_path_converted_to_local = self.convert_server_path_to_local_server_representation(server_dir)

        path = self.convert_server_path_to_local_server_representation(file_name, directory_only=directory_only)
        local_path = path.replace(cloud_path_converted_to_local, local_dir)

        return os.path.normpath(local_path)

    def init_thread_error(self):
        """
        Resets thread error monitoring, typically called before starting up threads
        """
        self.thread_error_occurred = False

    def send_thread_error(self, error):
        """
        Sends thread error to listening objects and sets flag so threads don't continue to send errors. Prevents
        multiple threads from sending same message
        :param error: the string error
        """
        if not self.thread_error_occurred:
            self.error_thread_signal.emit(error)
            self.thread_error_occurred = True
            self.progress_win.close()

    def init_progress_window(self, title, label):
        self.progress_win.setWindowTitle(title)
        self.progress_win.setLabelText(label)
        self.progress_win.setValue(0)
        self.progress_win.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.progress_win.show()
        # makes sure progress shows over window, as windows os will place it under cursor behind other windows if
        # user moves mouse off off app
        pyani.core.ui.center(self.progress_win)
        QtWidgets.QApplication.processEvents()

    def _thread_server_download_complete(self):
        """
        Called when a thread that downloads files completes
        """
        # since managers handle, only run for the active tool or asset
        if not self.thread_error_occurred:
            # a thread finished, increment our count
            self.threads_done += 1.0
            if self.threads_done > self.thread_total:
                return
            else:
                # get the current progress percentage
                progress = (self.threads_done / self.thread_total) * 100.0

                self.progress_win.setValue(progress)
                # check if we are finished
                if progress >= 100.0:
                    # done, let any listening objects/classes know we are finished
                    self.finished_signal.emit(None)

    def _thread_server_sync_complete(self, page_id=None, save_method=None):
        """
        Called when a thread that updates cache and downloads files completes
        :param page_id: passed back to calling app so it can know what tool active_type or asset component called
        the sync.
        :param save_method: the function to call when the cache is complete to save it locally
        """
        # since managers handle, only run for the active tool or asset
        if page_id and save_method and not self.thread_error_occurred:
            # a thread finished, increment our count
            self.threads_done += 1.0
            if self.threads_done > self.thread_total:
                return
            else:
                # get the current progress percentage
                progress = (self.threads_done / self.thread_total) * 100.0

                self.progress_win.setValue(progress)
                # check if we are finished
                if progress >= 100.0:
                    # save the cache locally
                    error = save_method()
                    if error:
                        self.send_thread_error(error)
                    else:
                        # done, let any listening objects/classes know we are finished
                        self.finished_sync_and_download_signal.emit(page_id)

    def _thread_server_cache_complete(self, save_method=None):
        """
        Called when a thread that builds the cgt asset cache completes. Emits a signal, finished_cache_build_signal,
        that passes any errors that occur, or none if there are no errors.
        :param save_method: the function to call when the cache is complete to save it locally
        """
        # check for a save method and thread errors, otherwise don't execute
        if save_method and not self.thread_error_occurred:
            # a thread finished, increment our count
            self.threads_done += 1.0
            if self.threads_done > self.thread_total:
                return
            else:
                # get the current progress percentage
                progress = (self.threads_done / self.thread_total) * 100.0
                self.progress_win.setValue(progress)
                # check if we are finished
                if progress >= 100.0:
                    # save the cache locally
                    error = save_method()
                    if error:
                        self.send_thread_error(error)
                    else:
                        # done, let any listening objects/classes know we are finished
                        self.finished_cache_build_signal.emit(None)
