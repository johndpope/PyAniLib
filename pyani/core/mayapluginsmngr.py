import os
import shutil
import logging
import pyani.core.util
import pyani.core.appvars


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtCore, QtGui


logger = logging.getLogger()


class AniMayaPlugins:
    """
    Class for managing maya plugins

    There are two ways to refer to a plugins name, the display name and file name (just called name). Display name
    is a user friendly version (for example Eye Plugin vs eyeBallNode), while the file name is the name of the folder
    containing the plugin. We use a folder per plugin since some plugins have multiple files.

    REMOVED : The restore point to go back a version. Left mehtods to re-implement at a later date if desired.

    Format for data in tools list json file (app data shared dir of pyanitools, see app vars, self.tools_list property):

       "maya plugins": {
              "plugin display name" : {
                 "name" : name_of_folder,
                 "location" : "local" or "server", see pyani.core.appvars.py for the actual path under
                              # maya plugins in the __init__() method
              },...
       }

    Version info is in each maya plugin directory, see app vars for file name in self.maya_plugins_vers_json_name
    property. Format is:

    [
        {
          "version": "version number as string",
          "notes": [
            "notes as a list of strings"
          ]
        },...
    ]

    Both are combined to create the self.maya_plugin_data dict which is:

    {
          "plugin display name" : {
             "name": "the plugin directory - use the name of the plugin",
             "location": "local" or "server", see pyani.core.appvars.py for the actual path under
                          # maya plugins in the __init__() method
             "version data" : [
                    {
                        "version": "version number as a string"
                        "notes": [
                            "notes as a list of strings"
                        ]
                    },....
             ]
          },...
    }


    """
    def __init__(self):
        # app vars
        self.app_vars = pyani.core.appvars.AppVars()
        self.maya_plugin_data = None

    @property
    def maya_plugin_data(self):
        return self.__maya_plugin_data

    @maya_plugin_data.setter
    def maya_plugin_data(self, plugin_data):
        self.__maya_plugin_data = plugin_data

    def get_plugins(self):
        """Returns a list of plugins for maya. Returns the display name.
        """
        return self.maya_plugin_data.keys()

    def build_plugin_data(self):
        """
        Makes the dict of plugin data that contains the plugin's name, version, release notes and any other data for
        managing the plugins. Sets the member property self.maya_plugin_data
        :return: error if encountered, otherwise None
        """
        # list of maya plugins
        maya_plugin_json_data = pyani.core.util.load_json(self.app_vars.tools_list)
        if not isinstance(maya_plugin_json_data, dict):
            error = "Critical error loading list of maya plugins from {0}".format(self.app_vars.tools_list)
            logger.error(error)
            self.maya_plugin_data = None
            return error

        try:
            self.maya_plugin_data = maya_plugin_json_data["maya plugins"]
        except KeyError as e:
            error = "Critical error loading list of maya plugins from {0}. Error is missing Key: {1}".format(
                self.app_vars.tools_list,
                e
            )
            logger.error(error)
            return error

        # add version_data to maya plugin data under key 'version_data'. If no version can be loaded set to None.
        for plugin in self.maya_plugin_data:
            location = self.get_plugin_location(plugin)
            version_path = os.path.join(
                    os.path.join(location, self.maya_plugin_data[plugin]['name']),
                    self.app_vars.maya_plugins_vers_json_name
             )
            version_data = pyani.core.util.load_json(version_path)
            if isinstance(version_data, list):
                self.maya_plugin_data[plugin]['version data'] = version_data
            else:
                self.maya_plugin_data[plugin]['version data'] = None
        return None

    def get_version(self, plugin, version="latest"):
        """
        Get the version number for the plugin
        :param plugin: the name of the plugin (display name) as a string
        :param version: the version to get release notes for. defaults to latest version
        :return: the version number as a string
        """
        if version == "latest":
            return self.maya_plugin_data[plugin]["version data"][0]["version"]
        else:
            # this can be expanded to get previous versions, right now only store one prev version
            return self.maya_plugin_data[plugin]["version data"][1]["version"]

    def get_restore_path(self, plugin):
        """
        get the restore path location to revert plugin
        :param plugin: the name of the plugin (display name) as a string
        :return: the restore file path
        """
        loc = self.get_plugin_location(plugin)
        # get restore path and
        restore_path = os.path.join(
            loc, os.path.join(self.maya_plugin_data[plugin]["name"], self.app_vars.maya_plugins_restore_dir)
        )
        return restore_path

    def retore_path_exists(self, plugin):
        """
        Checks for existence of restore path
        :param plugin: the name of the plugin (display name) as a string
        :return: True if exists, False if doesn't. Returns False if folder is missing or exists but is empty
        """
        restore_path = self.get_restore_path(plugin)
        # check for restore point
        if not os.path.exists(restore_path) or not os.listdir(restore_path):
            return None
        else:
            return restore_path

    def get_plugin_path(self, plugin):
        """
        get the path location to the plugin
        :param plugin: the name of the plugin (display name) as a string
        :return: the file path or None if doesn't exist
        """
        loc = self.get_plugin_location(plugin)
        # get restore path and
        plugin_path = os.path.join(
            loc, os.path.join(self.maya_plugin_data[plugin]["name"])
        )
        # check for path
        if not os.path.exists(plugin_path) or not os.listdir(plugin_path):
            return None
        else:
            return plugin_path

    def get_plugin_location(self, plugin):
        """
        determine file path location of plugin - is it local in maya's plugin folder or on the server
        :param plugin: the name of the plugin (display name) as a string
        :return: the location file path as a string. returns the directory holding the plugin
        """
        # find where its located, local or server
        if self.maya_plugin_data[plugin]["location"] == "local":
            loc = self.app_vars.maya_plugins_local
        else:
            loc = self.app_vars.maya_plugins_server
        return loc

    def get_release_notes(self, plugin, version="latest", formatted=True):
        """
        Get the release notes for the plugin
        :param plugin: the name of the plugin (display name) as a string
        :param version: the version to get release notes for. defaults to latest version
        :param formatted: whether to format the notes as human readable (bulleted list). Default is to format
        :return: the release notes formatted as a bulleted list if format=True, otherwise a list of strings if
        formattted = False. Returns None if release notes can't be obtained
        """
        if version == "latest":
            version_num = 0
        else:
            # in future can expand this if needed to allow version selection
            version_num = int(version)
        # if ask for an index that isn't there, then means no version data, index must be less than the length of the
        # version data list if it exists
        if version_num < len(self.maya_plugin_data[plugin]["version data"]):
            release_notes = self.maya_plugin_data[plugin]["version data"][version_num]["notes"]
        else:
            return None
        if formatted:
            release_notes = self._format_release_notes(release_notes)

        return release_notes

    def open_confluence_page(self, plugin):
        """
        opens an html page in the web browser for help
        :param plugin: the name of the plugin (file name) as a string
        """
        link = QtCore.QUrl("http://172.18.10.11:8090/display/KB/{0}".format(plugin))
        QtGui.QDesktopServices.openUrl(link)

    def get_missing_plugins(self):
        """
        Gets a list of plugins as names that are missing on disk
        :return: a list of plugin names for missing plugins
        """
        plugins_missing = []
        for plugin in self.maya_plugin_data:
            # check if plugin doesn't exist
            if not self.get_plugin_location(plugin):
                plugins_missing.append(plugin)
        return plugins_missing

    def download_plugins(self, plugins, download_monitor, use_progress_monitor=True):
        """
        Downloads the plugins from the server. Updates the maya plugin data property as well to contain the updated
        plugin info
        :param plugins: a plugin as a string or a list of plugins on the server to download
        :param download_monitor: a pyani.core.ui.CGTDownloadMonitor object that executes a command via the
        subprocess module and polls subprocess for output. Sends that via slot/signals to main window.
        """

        download_list = []
        cgt_list = []

        # support one or more plugin downloads, convert single plugin string to a list
        if not isinstance(plugins, list):
            plugins = [plugins]

        # build the list of files to download and where to download to
        for plugin in plugins:
            cgt_list.append(self.maya_plugin_data[plugin]['server path'])
            download_list.append(
                self.get_plugin_location(plugin) + "\\{0}\\".format(self.maya_plugin_data[plugin]['name'])
            )

        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_download.py")
        # need to convert python lists to strings, separated by commas, so that it will pass through in the shell
        # so if there are multiple paths, the list [path1, path2] becomes 'path1,path2'
        dl_command = [
            py_script,
            ",".join(cgt_list),
            ",".join(download_list),
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass
        ]
        # use threading to display progress
        if use_progress_monitor:
            # set the command to execute and start download - runs in separate thread
            download_monitor.download_cmd = dl_command
            download_monitor.start()
        # no threading
        else:
            output, error = pyani.core.util.call_ext_py_api(dl_command)
            self.cleanup_old_files(output)
            if error:
                return error

    @staticmethod
    def cleanup_old_files(files):
        """
        Cleans up files not on CGT
        :param files: a string from CGT that has files to remove in the format:
        file_dirs_to_dl#{directory of plugin}@file_names#{list of files separated by comma}
        ex: (note all on one line, put on separate lines below for readability
        file_dirs_to_dl#C:\Users\Patrick\Documents\maya\plug-ins\eyeBallNode\@file_names#C:\Users\Patrick\
        Documents\maya\plug-ins\eyeBallNode\eyeBallNode.py,C:\Users\Patrick\Documents\maya\plug-ins\eyeBallNode\
        plugin_version.json
        """
        for line in files.split("\n"):
            logger.info("output from cgt in cleanup: {0}".format(line))
            # first get the download folders so we can get the local files
            if 'file_dirs_to_dl' in line:
                existing_files = []
                file_dirs_next_line = line.split("@")[0]
                file_names_next_line = line.split("@")[-1]

                # remove 'file_dirs_to_dl'
                temp = file_dirs_next_line.split("#")[-1]
                # the download folders
                dl_dirs = temp.split(",")
                dl_dirs = [dl_dir.replace("\n", "") for dl_dir in dl_dirs]
                # list of files locally in download folders
                for dl_dir in dl_dirs:
                    # make sure folder exists
                    if os.path.exists(dl_dir):
                        for root, directories, file_names in os.walk(dl_dir):
                            for directory in directories:
                                existing_files.append(os.path.join(root, directory))
                            for filename in file_names:
                                existing_files.append(os.path.join(root, filename))
                # now check if any local files aren't on CGT
                # remove 'file_list'
                temp = file_names_next_line.split("#")[-1]
                # list of files in CGT
                file_names = temp.split(",")

                # look for any "/" and remove
                file_names = [os.path.normpath(file_name) for file_name in file_names]

                logger.info("cgt files: {0}".format(", ".join(file_names)))
                for existing_file in existing_files:
                    logger.info("existing files: {0}".format(existing_file))
                    # look for any files that exist locally but are not in CGT
                    if existing_file not in file_names:
                        if os.path.isfile(existing_file):
                            os.remove(existing_file)
                        else:
                            # only remove directories if empty
                            if not os.listdir(existing_file):
                                shutil.rmtree(existing_file, ignore_errors=True)
                break

    def change_version(self, plugin):
        """
        Restores the previous version as the current version. Updates the maya plugin
        data property as well to contain the updated plugin info on a successful version change
        :param plugin: the name of the plugin (display name) as a string
        :return: Error as a string or None if no errors
        """
        plugin_path = self.get_plugin_path(plugin)
        # get a list of files to remove in plugin folder. We want all files except restore point dir
        file_list = [
            os.path.join(plugin_path, file_name) for file_name in os.listdir(plugin_path)
            if self.app_vars.maya_plugins_restore_dir not in file_name
        ]
        # remove files and directories
        for file_path in file_list:
            if os.path.isfile(file_path):
                error = pyani.core.util.delete_file(file_path)
            else:
                error = pyani.core.util.rm_dir(file_path)
            if error:
                return error

        # restore previous version as current version
        restore_path = self.get_restore_path(plugin)
        file_list = [os.path.join(restore_path, file_name) for file_name in os.listdir(restore_path)]
        error = pyani.core.util.move_files(file_list, plugin_path)
        if error:
            return error

        # refresh plugin info
        error = self.build_plugin_data()
        if not isinstance(error, dict):
            return error

        return None

    def create_restore_point(self, plugin):
        """
        Creates a backup of the current version in the restore folder defined in self.app_vars.maya_plugins_restore_dir.
        Handles a) no current restore data b) restore data already exists
        :param plugin: the name of the plugin (display name) as a string
        :return: Error as a string or None if no errors
        """
        restore_path = self.get_restore_path(plugin)
        # check if a restore point exists and if so remove
        if self.retore_path_exists(plugin):
            error = pyani.core.util.rm_dir(restore_path)
            if error:
                return error

        # make the restore folder
        error = pyani.core.util.make_all_dir_in_path(restore_path)
        if error:
            return error

        # move current version
        plugin_path = self.get_plugin_path(plugin)
        file_list = [os.path.join(plugin_path, file_name) for file_name in os.listdir(plugin_path)]
        error = pyani.core.util.move_files(file_list, restore_path)
        if error:
            return error

        return None

    @staticmethod
    def _format_release_notes(notes):
        """
        formats a list of notes as (adds a break <br> at end of each note for a newline):
        - note1 <br>
        - note2 <br>
        - .... <br>

        :param notes: the list of notes where each note is a string
        :return: formatted string of the notes
        """
        # show release notes for prior version
        release_notes = "".join(
            ["- {0}<br>".format(note) for note in notes]
        )
        return release_notes