import zipfile
import os
import signal
import psutil
import pyani.core.util


class AppManager(object):
    """
    Class to manage an app. Does installs and updates
    """
    def __init__(self, app_update_script, app_name, app_dl_path, app_install_path, app_dist_path, app_data_path):
        self.__updater_script = app_update_script
        self.__app_name = app_name
        self.__app_exe = "{0}.exe".format(self.app_name)
        self.__app_package = app_dl_path
        self.__app_install_path = app_install_path
        self.__app_dist_path = app_dist_path
        self.__app_data_path = app_data_path
        self.__user_config = os.path.abspath(os.path.join(self.app_install_path, "app_pref.json"))
        self.__app_config = os.path.abspath("{0}{1}\\app_data.json".format(self.app_data_path, self.app_name))

    @classmethod
    def version_manager(cls, app_name, install_path, app_data_path):
        return cls(None, app_name, None, install_path, None, app_data_path)

    @property
    def updater_script(self):
        """The file path to the python updater script
        """
        return self.__updater_script

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
    def app_dist_path(self):
        """The path to where applications distribution files are
        """
        return self.__app_dist_path

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
        # stop app
        pids = self.find_processes_by_name(self.app_exe)

        for pid in pids:
            exc = self.kill_process(pid)
            if exc:
                return "Could not kill process id {0} for app {1}. Error: {2}".format(pid, self.app_exe, exc)

        self.unpack_app(self.app_package, self.app_install_path)

        # create user preference file
        if has_pref:
            self._create_user_preferences()

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

    def version_check(self):
        """Checks for the latest version
        :return msg if there is a new version, None otherwise
        """
        user_data = pyani.core.util.load_json(self.user_config)
        app_data = pyani.core.util.load_json(self.app_config)

        latest_version = app_data["versions"][0]["version"]
        features = ", ".join(app_data["versions"][0]["features"])
        if not user_data["version"] == latest_version:
            return "There is a newer version of this app. The latest version offers: {0}".format(features)
        return None

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
