import os
import logging
import functools
import scandir
import requests
import copy
import pyani.core.appvars
import pyani.core.anivars
import pyani.core.ui
import pyani.core.util
import pyani.core.mngr.core

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtCore, QtGui

logger = logging.getLogger()


class AniToolsMngr(pyani.core.mngr.core.AniCoreMngr):

    """
    Requirements:
        Plugins on cgt are in /LongGong/tools/maya/plugins in a flat structure, no folders
        Scripts on cgt are in /LongGong/tools/maya/scripts in a folder with the script name as the folder name

        Methods prefixed with 'server' are methods that contact CGT's cloud.

    Tool types are things like 'maya', pyanitools'
    Tool categories are things like 'scripts', 'plugins', 'apps'
    see pyani.core.appvars.AppVars's member variable self.tool_types for available types and categories

    So for example:

    "pyanitools": {
        "shortcuts": { data}
    }

    "pyanitools": {
        "apps": { data}
    }

    "maya": {
        "plugins": { data}
    }


    USAGE:

    Create one instance to handle multiple tools. Set the active category to control what tools are being managed
    EX: We have Maya Tools and Custom Show tools called PyAniTools.
    When I want to manage Maya Tools, I do tools_mngr_instance.active_type = "Maya" - set to user friendly name
    see pyani.core.appvars.AppVars tool_types_display_names for user friendly name

    Updating / Building Caches:
    To build a local cache,
    simply call sync_local_cache_with_server() (optionally pass a dict to update specific tools, see method
    doc string for format) and connect to the signal _thread_server_sync_complete (inherited from AniCoreMngr)
    to find out when it finishes.

    Download Files and Sync Cache:
    call sync_local_cache_with_server_and_download and pass a dict to update, see method
    doc string for format). connect to _thread_server_sync_complete (inherited from AniCoreMngr)
    to find out when it finishes.

    Reports errors using signals from pyani.core.mngrcore.AniCoreMngr:
    error_thread_signal, connect to this signal as:
    tools_mngr_instance.error_thread_signal.connect(method_that_receives_error)

    method_that_receives_error(error):
        print error

    emits and listening class can receive and display.
    """

    def __init__(self):
        super(AniToolsMngr, self).__init__()
        # private because this shouldn't be modified by outside classes
        self._tools_info = dict()
        # what active_type is this manager managing
        self.active_type = None
        # list of files to ignore when cleaning up old tool files
        self.exclude_removal = [
            "cgt_metadata.json"
        ]
        # list of existing tools so we can compare after a sync for newly added tools
        self._existing_tools_before_sync = dict()

    @property
    def active_type(self):
        return self._active_type

    @active_type.setter
    def active_type(self, tool_type):
        self._active_type = tool_type

    def load_local_tool_cache_data(self):
        """
        calls parent class method load_server_local_cache to load the cache from disk, if can't load data sets to none
        :return: None if the data if loaded successfully, otherwise the error
        """
        data = self.load_server_local_cache(self.app_vars.cgt_tools_cache_path)
        if isinstance(data, dict):
            self._tools_info = data
            return None
        else:
            self._tools_info = None
            return data

    def open_help_doc(self, tool_name):
        """
        opens an html page in the web browser for help. Returns error if page(s) can't be opened.
        :param tool_name: the name of the tool
        :return None if opened or error as string if can't open
        """

        url = r"http://172.18.10.11:8090/display/KB/{0}".format(tool_name)
        # check if page exists
        response = requests.get(
            url,
            headers={'Content-Type': 'application/json'},
            auth=(self.app_vars.wiki_user, self.app_vars.wiki_pass)
        )
        if response:
            link = QtCore.QUrl(url)
            QtGui.QDesktopServices.openUrl(link)
        else:
            return "The {0} tool does not have a confluence page".format(tool_name)

    def get_tool_categories(self, display_name=False):
        """
        Returns a list of tool categories, see class doctsring for more information
        :param display_name: show the user friendly version of the category name
        :return: a list of tool categories or None if can't get categories
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None

        if display_name:
            return self.app_vars.tool_types_display_names.values()
        else:
            return self._tools_info.keys()

    def get_tool_types(self, tool_type):
        """
        :param tool_type: the tool_type, see class doctsring for more information
        :return: a list of tool types or None if can't get types
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        return self._tools_info[tool_type].keys()

    def get_tool_names(self, tool_type, tool_category):
        """
        Gets the tool names for the given type and category, for ex: maya scripts
        :param tool_type: the type of tool as a string, see class doctsring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class doctsring for more information
        :return: a list of tool names or none if can't get names
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        return self._tools_info[tool_type][tool_category].keys()

    def get_tool_file_list(self, tool_type, tool_category, tool_name):
        """
        Gets directory or all files for this tool.
        :param tool_type: the type of tool as a string, see class doctsring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class doctsring for more information
        :param tool_name: the name of the tool as a string
        :return: a list of files or the directory for the tool (as a list as well) or None if no files
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        # tool may not have files
        try:
            return self._tools_info[tool_type][tool_category][tool_name]['files']
        except (KeyError, TypeError):
            return None

    def is_directory(self, tool_type, tool_category, tool_name):
        """
        Gets all versions as a list of strings for the tool specified
        :param tool_type: the type of tool as a string, see class doctsring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class doctsring for more information
        :param tool_name: the name of the tool as a string
        :return True if a directory, False if not
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        # tool may not have directory info
        try:
            return self._tools_info[tool_type][tool_category][tool_name]['is dir']
        except (KeyError, TypeError):
            return None

    def get_tool_local_version(self, tool_directory, tool_name):
        """
        Get local version for the tool specified
        :param tool_directory: the directory holding the tool or tool folder.
        for ex: if the tool is pyShoot, its C:\PyAniTools\apps\
        :param tool_name: the name of the tool as a string
        :return: the version number as a string, or none if can't get version
        """
        local_cgt_metadata = pyani.core.util.load_json(
            os.path.join(tool_directory, self.app_vars.cgt_metadata_filename)
        )

        # if can't load set to None
        if not isinstance(local_cgt_metadata, dict):
            return None
        else:
            return local_cgt_metadata[tool_name][0]["version"]

    def get_tool_versions(self, tool_type, tool_category, tool_name):
        """
        Gets all versions as a list of strings for the tool specified
        :param tool_type: the type of tool as a string, see class doctsring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class doctsring for more information
        :param tool_name: the name of the tool as a string
        :return: a list of versions, or none if can't get versions
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        # tool may not have version
        try:
            return [
                metadata['version'] for metadata in
                self._tools_info[tool_type][tool_category][tool_name]['version info']
            ]
        except (KeyError, TypeError):
            return None

    def get_tool_newest_version(self, tool_type, tool_category, tool_name):
        """
        Gets the newest version of the tool specified
        :param tool_type: the type of tool as a string, see class docstring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class docstring for more information
        :param tool_name: the name of the tool as a string
        :return: the version as a string, or none if can't get version
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        try:
            return self._tools_info[tool_type][tool_category][tool_name]['version info'][0]["version"]
        except (KeyError, TypeError):
            return None

    def get_tool_description(self, tool_type, tool_category, tool_name):
        """
        Gets the tools description
        :param tool_type: the type of tool as a string, see class docstring for more information
        or run method get_tool_types
        :param tool_category: the category of tool, see class docstring for more information
        :param tool_name: the name of the tool as a string
        :return: the description as a string, or none if no description
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        try:
            return self._tools_info[tool_type][tool_category][tool_name]['version info'][0]["desc"]
        except (KeyError, TypeError):
            return None

    def get_tool_release_notes(self, tool_type, tool_category, tool_name, version="latest"):
        """
        Gets release notes for the tool
        :param tool_type: the type of tool as a string, see pyani.core.appvars.AppVars tool types
        or run method get_tool_types
        :param tool_category: the category, see pyani.core.appavrs.AppVars for tool categories in self.tool_types
        :param tool_name: the name of the tool as a string
        :param version: the version to get notes for, defaults to the newest version
        :return: the notes as a list, or None if can't get notes
        """
        # load cache off disk if it hasn't been loaded
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                return None
        try:
            if version == "latest":
                return self._tools_info[tool_type][tool_category][tool_name]['version info'][0]["notes"]
            else:
                for metadata in self._tools_info[tool_type][tool_category][tool_name]['version info']:
                    if metadata["version"] == version:
                        return metadata["notes"]
        except (KeyError, TypeError):
            return None

    def get_tool_info_by_tool_name(self, tool_type, tool_category, tool_name):
        """
        Gets all assets and their info given a asset_component name
        :param tool_type: the type of tool as a string, see pyani.core.appvars.AppVars tool types
        or run method get_tool_types
        :param tool_category: the category, see pyani.core.appavrs.AppVars for tool categories in self.tool_types
        :param tool_name: the name of the tool as a string
        :return: a tuple in format:
        {
            tool type,
            tool category,
            tool name,
            { tool properties - file and version info as key/value pairs }
        }

        or returns none if the tool type or tool category or tool name doesn't exist
        """
        try:
            tool_info = (
                tool_type,
                tool_category,
                tool_name,
                self._tools_info[tool_type][tool_category][tool_name]
            )
            return tool_info
        except KeyError:
            return None

    def update_config_file_after_sync(self, debug=False):
        """
        Adds new tools added to the server to the update config. Removes tools from update config if they are
        removed off the server. If the user removes a tool(s) from being auto updated, the behavior is the following:
        ( NOTE: includes if user removes all tools from being updated):
        - if a new tool type is added on server, gets added to update config
        - if a new tool category is added on server, gets added to update config
        - if a new tool name (i.e. a tool) is added on server, gets added to update config (even if all tools were
          removed for a given type and category)
        - doesn't re-add existing tools removed from update config
        :param debug: doesn't save auto update config file, just prints to screen
        :return error as string if can't load or write update config, otherwise returns None. Also emits a finished
        signal to indicate complete if being threaded.
        """
        # pull the config data off disk
        existing_config_data = pyani.core.util.load_json(self.app_vars.update_config_file)
        # check if config data loaded
        if not isinstance(existing_config_data, dict):
            error = "Error loading update config file from disk. Error is: {0}".format(existing_config_data)
            self.send_thread_error(error)
            return error

        # check for new tools
        for tool_type in self._tools_info:
            # find new tool types
            if not pyani.core.util.find_val_in_nested_dict(self._existing_tools_before_sync, [tool_type]):
                # add type to update config
                if debug:
                    print "add type: {0} ".format(tool_type)
                # get categories and their tools
                categories_and_tools = {
                    category: pyani.core.util.find_val_in_nested_dict(self._tools_info, [tool_type, category])
                    for category in pyani.core.util.find_val_in_nested_dict(self._tools_info, [tool_type])
                }
                existing_config_data['tools'][tool_type] = categories_and_tools
            else:
                for tool_cat in self._tools_info[tool_type]:
                    # first make sure the tool type and category exist in old tools list, possible got added
                    if not pyani.core.util.find_val_in_nested_dict(
                            self._existing_tools_before_sync,
                            [tool_type, tool_cat]
                    ):
                        # add type and cat to update config
                        if debug:
                            print "add type: {0} and cat: {1}".format(tool_type, tool_cat)

                        existing_config_data['tools'][tool_type][tool_cat] = \
                            pyani.core.util.find_val_in_nested_dict(self._tools_info, [tool_type, tool_cat])
                    else:
                        # check all tool names in sync'd tools list against tools list before sync to find new tools
                        for tool_name in self._tools_info[tool_type][tool_cat]:
                            if tool_name not in self._existing_tools_before_sync[tool_type][tool_cat]:
                                # new tool, add to config file
                                if debug:
                                    print "add tool: {0}".format(tool_name)

                                # check if the category exists in config
                                if tool_cat not in existing_config_data['tools'][tool_type]:
                                    existing_config_data['tools'][tool_type][tool_cat] = list()
                                existing_config_data['tools'][tool_type][tool_cat].append(tool_name)

        # check for tools removed
        for tool_type in self._existing_tools_before_sync:
            # first make sure the tool type exists in new tools list, possible got removed
            if not pyani.core.util.find_val_in_nested_dict(self._tools_info, [tool_type]):
                # type removed, remove from update config
                if debug:
                    print "remove type: {0}".format(tool_type)
                existing_config_data['tools'].pop(tool_type, None)
            else:
                for tool_cat in self._existing_tools_before_sync[tool_type]:
                    #  make sure the tool category exist in new tools list, possible got removed
                    if not pyani.core.util.find_val_in_nested_dict(self._tools_info, [tool_type, tool_cat]):
                        # type and cat removed, remove from update config
                        if debug:
                            print "remove type: {0} and cat: {1}".format(tool_type, tool_cat)
                        # category may not be in existing config data, user could have removed, so check
                        if pyani.core.util.find_val_in_nested_dict(
                                existing_config_data,
                                ['tools', tool_type, tool_cat]
                        ):
                            existing_config_data['tools'][tool_type].pop(tool_cat, None)
                    else:
                        # check all tool names in old tools list against tools list after sync to find tools removed
                        for tool_name in self._existing_tools_before_sync[tool_type][tool_cat]:
                            if tool_name not in self._tools_info[tool_type][tool_cat]:
                                # tool removed, remove from config file
                                if debug:
                                    print "remove tool: {0}".format(tool_name)
                                # category may not be in existing config data, user could have removed, so check before
                                # removing
                                if pyani.core.util.find_val_in_nested_dict(
                                        existing_config_data,
                                        ['tools', tool_type, tool_cat]
                                ):
                                    # tool name may not be in existing config data, user could have removed,
                                    # so check before removing
                                    if tool_name in existing_config_data['tools'][tool_type][tool_cat]:
                                        existing_config_data['tools'][tool_type][tool_cat].remove(tool_name)
        if debug:
            print "Updated Config Data Is Now:"
            print existing_config_data
        else:
            error = pyani.core.util.write_json(self.app_vars.update_config_file, existing_config_data, indent=4)
            if error:
                error_fmt = "Could not save sync'd update config file. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

        self.finished_signal.emit(None)
        return None

    def update_config_file_by_tool_type(self, config_data):
        """
        Updates the update config file with new tools and removes tools that are de-selected (not in
        selection)
        :param config_data: a dict of the tools type, tools category and tools names we want to add to the config
        :return: error if occurs, otherwise None
        """
        # if the config file doesn't exist, just save the data
        if not os.path.exists(self.app_vars.update_config_file):
            if not os.path.exists(self.app_vars.persistent_data_path):
                error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
                if error:
                    return error
            error = pyani.core.util.write_json(
                self.app_vars.update_config_file,
                config_data,
                indent=4
            )
            if error:
                return error
            return None
        # file exists
        else:
            # pull the config data off disk
            existing_config_data = pyani.core.util.load_json(self.app_vars.update_config_file)
            # check if config data is an empty file, if so set to a empty dict object
            if not isinstance(existing_config_data, dict):
                existing_config_data = dict()

            # file has assets, but no tools
            if 'tools' not in existing_config_data:
                existing_config_data['tools'] = config_data
            # tools exist in file
            else:
                # first check for assets whose type and component don't exist yet in the config file
                for tool_type in config_data:
                    # when the tool type doesn't yet exist, but other tool types do in the file, so can just add.
                    if tool_type not in existing_config_data['tools']:
                        existing_config_data['tools'][tool_type] = dict()
                        existing_config_data['tools'][tool_type] = config_data[tool_type]
                        continue

                    # check if tool category removed in updated config data, if so remove from config file, use
                    # list for python 3 compatibility. allows us to remove dict keys during iteration
                    for tool_category in list(existing_config_data['tools'][tool_type].keys()):
                        if tool_category not in config_data[tool_type]:
                            existing_config_data['tools'][tool_type].pop(tool_category, None)

                    # when tool category doesn't exist but the type does, so can just add
                    for tool_category in config_data[tool_type]:
                        if tool_category not in existing_config_data['tools'][tool_type]:
                            existing_config_data['tools'][tool_type][tool_category] = dict()
                            existing_config_data['tools'][tool_type][tool_category] = \
                                config_data[tool_type][tool_category]
                            continue

                    # just replace since type and component exist, only get here if the above statements aren't true
                    # this does both what is de-selected and selected since it does assignment by type and category
                    # i.e. all items of the category are passed.
                    for tool_category in config_data[tool_type]:
                        existing_config_data['tools'][tool_type][tool_category] = config_data[tool_type][tool_category]

            error = pyani.core.util.write_json(self.app_vars.update_config_file, existing_config_data, indent=4)
            if error:
                return error
            return None

    def sync_local_cache_with_server(self, update_data_dict=None):
        """
        Updates the cache on disk with the current cgt data. If no parameters are filled the entire cache will
        be rebuilt.
        :param update_data_dict: a dict in format:
        {
         tool active_type: {
             tool type(s): [
                 tool name(s)
             ]
             }, more tool types...
        }

        There can be one or more tool categories. Tool types and tool names are optional.
        Tool types require a tool active_type. Tool names require both a tool active_type and tool type.
        a list of the type of tool(s) to update - see pyani.core.appvars.py
        """
        # no tool types, so can't set any other values in data struct, so rebuild entire cache
        if not update_data_dict:
            self.server_build_local_cache()
        else:
            self.server_build_local_cache(
                tools_dict=update_data_dict,
                thread_callback=self._thread_server_sync_complete,
                thread_callback_args=[self.active_type, self.server_save_local_cache]
            )

    def sync_local_cache_with_server_and_download_gui(self, update_data_dict):
        """
        Updates the cache on disk with the current server data. Also downloads latest tools. used with gui asset mngr
        :param update_data_dict: a dict in format:
        {
         tool active_type: {
             tool type(s): [
                 tool name(s)
             ]
             }, more tool types...
        }

        There can be one or more tool categories. tool types and tool names are optional.
        tool types require a tool active_type. Tool Names require both a tool type and tool active_type.
        a list of the type of tool(s) to update - see pyani.core.appvars.py for tool types and tool components

        :return: None if updated cache, an error string if couldn't update.
        """
        # no tool types,
        if not update_data_dict:
            return "At least one tool must be provided to update."

        # reset progress
        self.init_progress_window("Sync Progress", "Updating tools...")

        # update the local cache for the tools given - done by type
        self.server_build_local_cache(
            tools_dict=update_data_dict,
            thread_callback=self._thread_server_sync_complete,
            thread_callback_args=[self.active_type, self.server_save_local_cache]
        )
        # download files
        self.server_download_from_gui(update_data_dict)

    def server_download_from_gui(self, tools_dict=None):
        """
        used with gui asset mngr
        downloads files for the tools in the tools dict, and updates the meta data on disk for that tool. Uses
        multi-threading.
        :param tools_dict: a dict in format:
             {
                 tool type: {
                     tool category(s): [
                         tool name(s)
                     ]
                     }, more tool types...
             }
             If not provided downloads all tools
        :return error if occurs before threading starts.
        """
        # set number of threads to one. have issues otherwise
        self.set_number_of_concurrent_threads(1)

        self._reset_thread_counters()

        # if not visible then no other function called this, so we can show progress window
        if not self.progress_win.isVisible():
            # reset progress
            self.init_progress_window("Sync Progress", "Updating tools...")

        # check if tools to download were provided, if not load cache off disk.
        if not tools_dict:
            error = self.load_local_tool_cache_data()
            if error:
                error_msg = "No tools provided to download and could not load tool info off disk." \
                            " Error is {0}".format(error)
                self.send_thread_error(error_msg)
                return error_msg
            else:
                tools_dict = self._tools_info

        # now use multi-threading to download
        for tool_type in tools_dict:
            for tool_category in tools_dict[tool_type]:
                for tool_name in tools_dict[tool_type][tool_category]:
                    # only process tools that exist - need to check in case server data changed from local cache
                    # first get the folder or file to check, then check with server

                    if self._tools_info[tool_type][tool_category][tool_name]["is dir"]:
                        cgt_path = "{0}/{1}".format(
                            self._tools_info[tool_type][tool_category][tool_name]["cgt cloud dir"],
                            tool_name
                        )
                    else:
                        cgt_path = self._tools_info[tool_type][tool_category][tool_name]["files"][0]

                    if not self.server_file_exists(cgt_path):
                        continue

                    # some tools are folders, some are multiple files, so get folder or files
                    files_to_download = [
                        file_name for file_name in self._tools_info[tool_type][tool_category][tool_name]["files"]
                    ]

                    # need to download the cgt metadata as well
                    files_to_download.append(self.app_vars.cgt_metadata_filename)

                    for file_name in files_to_download:
                        # make path in cloud - dirs and files already have full path. metadata does not so make full
                        # file name for cgt metadata
                        if self.app_vars.cgt_metadata_filename in file_name:
                            cgt_path = "{0}/{1}".format(
                                self._tools_info[tool_type][tool_category][tool_name]["cgt cloud dir"],
                                file_name
                            )
                        else:
                            cgt_path = file_name

                        # make download path - this is the root directory holding the files or folder downloaded above
                        # if its a folder need to add that to the end of the download path, otherwise its a flat
                        # structure so no need. also check for the cgt metadata, that is always beneath the tool type,
                        # ie the root directory for the tool's type, such as script or plugin

                        # server metadata
                        if self.app_vars.cgt_metadata_filename in file_name:
                            local_path = self._tools_info[tool_type][tool_category][tool_name]["local path"]
                        # tools in their own folder
                        elif self._tools_info[tool_type][tool_category][tool_name]['is dir']:
                            # get local tool directory from server cache
                            tool_local_dir = self._tools_info[tool_type][tool_category][tool_name]["local path"]
                            cloud_dir = self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir']

                            if self.is_file_on_local_server_representation(cloud_dir, tool_local_dir):
                                local_path = self.convert_server_path_to_local_server_representation(
                                    file_name,
                                    directory_only=True
                                )
                            else:
                                local_path = self.convert_server_path_to_non_local_server(
                                    cloud_dir,
                                    tool_local_dir,
                                    file_name,
                                    directory_only=True
                                )

                        # single dir structure - all tools in same dir
                        else:
                            local_path = self._tools_info[tool_type][tool_category][tool_name]["local path"]

                        # server_download expects a list of files, so pass list even though just one file
                        worker = pyani.core.ui.Worker(
                            self.server_download,
                            False,
                            [cgt_path],
                            local_file_paths=[local_path],
                        )

                        self.thread_total += 1.0
                        self.thread_pool.start(worker)
                        # reset error list
                        self.init_thread_error()
                        # slot that is called when a thread finishes, passes the active_type so calling classes can
                        # know what was updated and the save cache method so that when cache gets updated it can be
                        # saved
                        worker.signals.finished.connect(
                            functools.partial(
                                self._thread_server_sync_complete,
                                self.active_type,
                                self.server_save_local_cache
                            )
                        )
                        worker.signals.error.connect(self.send_thread_error)

    def server_download_no_sync(self, tools_dict=None):
        """
        downloads files for the tools in the tools dict, but doesn't sync cache. Uses
        multi-threading.
        :param tools_dict: a dict in format:
             {
                 tool type: {
                     tool category(s): [
                         tool name(s)
                     ]
                     }, more tool types...
             }
             If not provided downloads all tools
        :return error if occurs before threading starts.
        """
        # set number of threads to one. have issues otherwise
        self.set_number_of_concurrent_threads(3)

        # if not visible then no other function called this, so we can show progress window
        if not self.progress_win.isVisible():
            # reset progress
            self.init_progress_window("Sync Progress", "Updating tools...")

        # check if tools to download were provided, if not load cache off disk.
        if not tools_dict:
            error = self.load_local_tool_cache_data()
            if error:
                error_msg = "No tools provided to download and could not load tool info off disk." \
                            " Error is {0}".format(error)
                self.send_thread_error(error_msg)
                return error_msg
            else:
                tools_dict = self._tools_info

        # reset error list
        self.init_thread_error()

        # reset threads counters
        self._reset_thread_counters()

        # now use multi-threading to download
        for tool_type in tools_dict:
            for tool_category in tools_dict[tool_type]:
                for tool_name in tools_dict[tool_type][tool_category]:
                    # some tools are folders, some are multiple files, so get folder or files
                    files_to_download = [
                        file_name for file_name in self._tools_info[tool_type][tool_category][tool_name]["files"]
                    ]
                    # need to download the cgt metadata as well
                    files_to_download.append(self.app_vars.cgt_metadata_filename)

                    for file_name in files_to_download:
                        # make path in cloud - dirs and files already have full path. metadata does not so make full
                        # file name for cgt metadata
                        if self.app_vars.cgt_metadata_filename in file_name:
                            cgt_path = "{0}/{1}".format(
                                self._tools_info[tool_type][tool_category][tool_name]["cgt cloud dir"],
                                file_name
                            )
                        else:
                            cgt_path = file_name

                        # make download path - this is the root directory holding the files or folder downloaded above
                        # if its a folder need to add that to the end of the download path, otherwise its a flat
                        # structure so no need. also check for the cgt metadata, that is always beneath the tool type,
                        # ie the root directory for the tool's type, such as script or plugin

                        # server metadata
                        if self.app_vars.cgt_metadata_filename in file_name:
                            local_path = self._tools_info[tool_type][tool_category][tool_name]["local path"]
                        # tools in their own folder
                        elif self._tools_info[tool_type][tool_category][tool_name]['is dir']:
                            # get local tool directory from server cache
                            tool_local_dir = self._tools_info[tool_type][tool_category][tool_name]["local path"]
                            cloud_dir = self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir']

                            if self.is_file_on_local_server_representation(cloud_dir, tool_local_dir):
                                local_path = self.convert_server_path_to_local_server_representation(
                                    file_name,
                                    directory_only=True
                                )
                            else:
                                local_path = self.convert_server_path_to_non_local_server(
                                    cloud_dir,
                                    tool_local_dir,
                                    file_name,
                                    directory_only=True
                                )
                        # single dir structure - all tools in same dir
                        else:
                            local_path = self._tools_info[tool_type][tool_category][tool_name]["local path"]

                        # server_download expects a list of files, so pass list even though just one file
                        worker = pyani.core.ui.Worker(
                            self.server_download,
                            False,
                            [cgt_path],
                            local_file_paths=[local_path]
                        )
                        self.thread_total += 1.0
                        self.thread_pool.start(worker)

                        # slot that is called when a thread finishes
                        worker.signals.finished.connect(self._thread_server_download_complete)
                        worker.signals.error.connect(self.send_thread_error)

    def server_build_local_cache(self, tools_dict=None, thread_callback=None, thread_callback_args=None):
        """
        Creates a local cache representation of the server tools directories along with each tools metadata such as
        version and release notes. Runs a tool category per thread. Ex: maya scripts runs in a thread, maya plugins
        runs another thread. Creates the cache data in format:
        {
            "tool type" - this is maya, pyanitools, etc...
                "tool category": { - scripts, plugins, etc...
                    "tool_name": { - actual name of tool, such as rig_picker
                        metadata as metadata_name: value, value can be any type such as list or string
                    }, ...
                }, ...
        }
        :param tools_dict: a dict in format:
        {
         tool type: {
             tool category(s): [
                 tool name(s)
             ]
             }, more tool types...
        }
        :param thread_callback: a method to call as threads complete
        :param thread_callback_args: any args to pass to thread callback
        """
        # set number of threads to max
        self.set_number_of_concurrent_threads()

        # dict of names per tool active_type and type with the files associated with them,
        # ex: names of all maya scripts for tool type = scripts, stores as:
        '''
        {
            tool type: {
                tool category: {
                    tool name: {
                        "is dir": whether tool is in a directory or flat folder as a file or files, ex maya plugins
                        "files": the directory name or file(s) for the tool as a list
                    }
                }
            }
        }
        '''

        self._reset_thread_counters()

        # load existing cache if exists. Note if it can't be loaded and tools dict is provided, ignore tools dict
        # and rebuild entire cache to avoid cache being incomplete. i.e. can't build cache for certain tools if
        # don't have rest of the cache info, otherwise only certain tools get updated
        error = self.load_local_tool_cache_data()
        if error:
            tools_dict = None
            self._tools_info = dict()

        # get a list of existing tools
        self._existing_tools_before_sync = copy.deepcopy(self._tools_info)

        # if no thread callback then normal cgt cache creation so show progress, otherwise there should be
        # a progress window already running
        if not thread_callback:
            # reset progress
            self.init_progress_window("Cache Progress", "Creating cache...")

        if not tools_dict:
            tool_types = self.app_vars.tool_types
        else:
            tool_types = tools_dict.keys()

        # make the tool names and build directories for downloading of metadata
        for tool_type in tool_types:

            # if no tool types were provided, rebuild for all types, otherwise rebuild for the
            # tool types that were provided
            if not pyani.core.util.find_val_in_nested_dict(tools_dict, [tool_type]):
                tool_categories = self.app_vars.tool_types[tool_type]
            else:
                tool_categories = tools_dict[tool_type].keys()

            for tool_category in tool_categories:
                # check if we have tool names, if not don't pass any, otherwise pass the tools to be updated
                if not pyani.core.util.find_val_in_nested_dict(tools_dict, [tool_type, tool_category]):
                    tool_names = None
                else:
                    tool_names = tools_dict[tool_type][tool_category]

                worker = pyani.core.ui.Worker(
                    self.server_get_tool_info,
                    False,
                    tool_type,
                    tool_category,
                    tool_names_to_update=tool_names
                )
                self.thread_total += 1.0
                self.thread_pool.start(worker)
                # reset thread errors
                self.init_thread_error()

                # slot that is called when a thread finishes, pass the call back function to call when its done
                # check if thread callback is cache update or cache update with download, if no callback,
                # use the default cache complete callback
                if not thread_callback:
                    worker.signals.finished.connect(
                        functools.partial(self._thread_server_cache_complete, self.server_save_local_cache)
                    )
                else:
                    category = thread_callback_args[0]
                    save_method = thread_callback_args[1]
                    worker.signals.finished.connect(
                        functools.partial(thread_callback, category, save_method)
                    )
                worker.signals.error.connect(self.send_thread_error)

    def server_get_tool_info(self, tool_type, tool_category, tool_names_to_update=None):
        """
        Gets tool info from server where data stored
        :param tool_type: the type of tool as a string, see pyani.core.appvars.AppVars tool types
        or run method get_tool_types
        :param tool_category: the category, see pyani.core.appavrs.AppVars for tool categories in self.tool_types
        :param tool_names_to_update: a list of tool names where the name of the tool is a string
        :return: None or error if occurred. If this function is called in a threaded environment, connect to the
        pyani.core.mngr.core thread error signal to get the error
        """

        '''
        Get Server Information
        '''

        server_tool_names_and_files = {
            tool_type: dict()
        }

        server_tool_names_and_files[tool_type][tool_category] = dict()

        # this removes the existing dir if it exists before making
        error = pyani.core.util.make_all_dir_in_path(
            self.app_vars.tool_types[tool_type][tool_category]['local temp path']
        )
        if error:
            error_fmt = "Could not remove temp folder for cgt tool metadata. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt

        # make the list of names per type
        tools_found = self.server_get_dir_list(
            self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'],
            files_and_dirs=True
        )

        tools_no_extension = []
        # remove any extensions and non tool files
        for tool in tools_found:
            # only get extension if the name is a file
            server_path = "{0}/{1}".format(self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'], tool)

            # check if path is a file or directory
            if self.server_is_file(server_path):
                tool_name_parts = tool.split(".")
                tool_ext = tool_name_parts[-1]
                tool_no_ext = '.'.join(tool_name_parts[:-1])
            else:
                tool_ext = None
                tool_no_ext = tool

            # only include tools, not metadata or something else
            if tool_ext not in self.app_vars.tool_ignore_list or not tool_ext:
                tools_no_extension.append(tool_no_ext)

        # remove any duplicate names, can happen when plugins for instance have multiple names
        # since its in a flat structure
        tools_no_duplicates = list(set(tools_no_extension))

        for tool_name in tools_no_duplicates:
            file_list = [file_name for file_name in tools_found if tool_name in file_name]

            # confirm whether this is a file list or directory, the obvious case when not a directory is
            # when we have more than one element in file list. However for single elements, we need to check,
            # could be a file or directory. We try to get a file listing off the element, and since only directories
            # would return a result, we know then whether its a file or directory. We can't check for extensions
            # because folders could have a dot in them. So have to check cgt.

            # multiple files
            if len(file_list) > 1:
                is_dir = False
                # make file names absolute
                file_list = [
                    self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'] + "/" + file_name
                    for file_name in file_list
                ]
            # single element, so either a single file or a directory
            else:
                server_path = "{0}/{1}".format(
                    self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'],
                    file_list[0]
                )
                # a directory
                if self.server_get_dir_list(server_path, files_only=True):
                    is_dir = True
                    file_list = self.server_get_dir_list(
                        self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'] + "/" + tool_name,
                        files_only=True,
                        walk_dirs=True,
                        absolute_paths=True
                    )
                # single file
                else:
                    is_dir = False
                    file_list[0] = self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'] + "/" + \
                                   file_list[0]

            server_tool_names_and_files[tool_type][tool_category][tool_name] = {
                "is dir": is_dir,
                "files": file_list
            }

        # paths to download metadata, need to be a list for cgt to download
        server_metadata_paths = [self.app_vars.tool_types[tool_type][tool_category]['cgt cloud metadata path']]
        local_temp_metadata_dir = [self.app_vars.tool_types[tool_type][tool_category]['local temp path']]

        # download the metadata which has version and release notes
        error = self.server_download(server_metadata_paths, local_temp_metadata_dir)

        if error:
            error_fmt = "Could not read cgt tool metadata. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            # couldn't download, return error
            return error_fmt

        '''
        metadata format is:
        {
            tool name = [list of dicts where each dict is metadata per version],
            ...
        '''
        metadata = pyani.core.util.load_json(
            os.path.join(
                self.app_vars.tool_types[tool_type][tool_category]['local temp path'],
                self.app_vars.cgt_metadata_filename
            )
        )
        if not isinstance(metadata, dict):
            error = "Could not read cgt tool metadata. Error is {0}".format(metadata)
            self.send_thread_error(error)
            return error

        '''
        Build Cache Locally -- Note that self._tools_info will have been loaded prior to this function call,
        so it represents whats on disk
        '''

        # build local cache, make keys if don't exist for active_type and type
        if tool_type not in self._tools_info:
            self._tools_info[tool_type] = dict()
        if tool_category not in self._tools_info[tool_type]:
            self._tools_info[tool_type][tool_category] = dict()

        # if tool names were provided then process only those tools, otherwise update all
        if tool_names_to_update:
            tool_names = tool_names_to_update
        else:
            tool_names = server_tool_names_and_files[tool_type][tool_category]

        # these are the tools on the server
        server_tool_names = server_tool_names_and_files[tool_type][tool_category].keys()

        # adds new server tool info
        for tool_name in tool_names:
            # check if tool name exists on server. Possible user is updating via gui, and server tools changed from
            # local cache. If the tool is not in server info, i.e. server_tool_names_and_files, then skip adding
            if tool_name in server_tool_names_and_files[tool_type][tool_category]:
                # tool is in metadata file, capture metadata such as version
                if tool_name in metadata:
                    metadata_info = metadata[tool_name]
                # tool doesn't have metadata, so set to empty
                else:
                    metadata_info = None
                # add metadata
                tool_metadata = {
                    "version info": metadata_info,
                    "is dir": server_tool_names_and_files[tool_type][tool_category][tool_name]["is dir"],
                    "files": server_tool_names_and_files[tool_type][tool_category][tool_name]["files"],
                    "cgt cloud dir": self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'],
                    "local path": self.app_vars.tool_types[tool_type][tool_category]['local dir']
                }
                self._tools_info[tool_type][tool_category][tool_name] = tool_metadata

        # if tool names were provided then only check those
        if tool_names_to_update:
            local_tool_names = tool_names_to_update
        else:
            local_tool_names = self._tools_info[tool_type][tool_category].keys()

        # cleanup old tools. Checks either tools provided or if no tools provided checks all tools on disk
        # against the server tool names. if tool not in server list, remove
        for tool_name in local_tool_names:
            if tool_name not in server_tool_names:
                del self._tools_info[tool_type][tool_category][tool_name]

        '''
        # if no tool names were provided then process all tools
        if not tool_names:
            tool_names = server_tool_names_and_files[tool_type][tool_category]

        # adds new server tool info
        for tool_name in tool_names:
            # check if tool name exists on server. Possible user is updating via gui, and server tools changed from
            # local cache. If the tool is not in server info, i.e. server_tool_names_and_files, then skip adding
            if tool_name not in server_tool_names_and_files[tool_type][tool_category]:
                continue
            # tool is in metadata file, capture metadata such as version
            if tool_name in metadata:
                metadata_info = metadata[tool_name]
            # tool doesn't have metadata, so set to empty
            else:
                metadata_info = None
            # add metadata
            tool_metadata = {
                "version info": metadata_info,
                "is dir": server_tool_names_and_files[tool_type][tool_category][tool_name]["is dir"],
                "files": server_tool_names_and_files[tool_type][tool_category][tool_name]["files"],
                "cgt cloud dir": self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir'],
                "local path": self.app_vars.tool_types[tool_type][tool_category]['local dir']
            }
            self._tools_info[tool_type][tool_category][tool_name] = tool_metadata
    
        # cleanup any old tools - note use list below for python 3 compatibility
        for tool_name in list(self._tools_info[tool_type][tool_category].keys()):
            if tool_name not in tool_names:
                del self._tools_info[tool_type][tool_category][tool_name]
        '''

    def server_save_local_cache(self):
        """
        Saves the cache created from server's file structure to disk and cleans up any temp files and folders
        :return: None or error if occurred. If this function is called in a threaded environment, connect to the
        pyani.core.mngrcore thread error signal to get the error
        """
        errors = list()
        # cleanup temp dirs for maya tools
        for tool_type in self.app_vars.tool_types:
            for tool_category in self.app_vars.tool_types[tool_type]:
                error = pyani.core.util.rm_dir(self.app_vars.tool_types[tool_type][tool_category]['local temp path'])
                if error:
                    errors.append(error)
        if errors:
            error = "Could not save local tools cache. Error is {0}".format(', '.join(errors))
            self.send_thread_error(error)
            return error

        # remove root tools dir from temp
        error = pyani.core.util.rm_dir(self.app_vars.tools_temp_dir)
        if error:
            self.send_thread_error("Could not save local tools cache. Error is {0}".format(error))
            return "Could not save local tools cache. Error is {0}".format(error)

        # check for errors

        # check if folder exists, if not make it
        if not os.path.exists(self.app_vars.persistent_data_path):
            error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
            if error:
                self.send_thread_error("Could not save local tools cache. Error is {0}".format(error))
                return "Could not save local tools cache. Error is {0}".format(error)

        # creates or overwrites the existing cgt cache json file
        error = pyani.core.util.write_json(self.app_vars.cgt_tools_cache_path, self._tools_info, indent=4)
        if error:
            self.send_thread_error("Could not save local tools cache. Error is {0}".format(error))
            return "Could not save local tools cache. Error is {0}".format(error)
        else:
            return None

    def remove_files_not_on_server(self, debug=False):
        """
        Removes files locally that are not on server.
        :param debug: disables actual file deletion and prints the files removed
        :return: any errors removing files, or None. Also sends a finished signal in case this is threaded.
        """
        # a list of files that can't be removed
        errors_removing_files = list()
        # local and server files
        local_file_paths = list()
        server_files = list()
        # list of files removed
        files_removed = list()

        # load cgt cache to see what is on server
        if not self._tools_info:
            error = self.load_local_tool_cache_data()
            if error:
                self.send_thread_error("Could not load local tools cache. Error is {0}".format(error))
                return "Could not load local tools cache. Error is {0}".format(error)

        # build list of all server paths and all local files for all tools
        for tool_type in self._tools_info:
            for tool_category in self._tools_info[tool_type]:
                for tool_name in self._tools_info[tool_type][tool_category]:

                    # get local tool directory from server cache
                    tool_local_dir = self._tools_info[tool_type][tool_category][tool_name]["local path"]
                    cloud_dir = self.app_vars.tool_types[tool_type][tool_category]['cgt cloud dir']

                    # paths are the same for local and server, so putting files in Z:\.....
                    if self.is_file_on_local_server_representation(cloud_dir, tool_local_dir):
                        # convert server paths in server cache to local paths
                        server_files.extend(
                            self.convert_server_path_to_local_server_representation(path)
                            for path in self._tools_info[tool_type][tool_category][tool_name]["files"]
                        )
                    # paths aren't the same for local and server - i.e. not putting files in Z:\....
                    else:
                        for path in self._tools_info[tool_type][tool_category][tool_name]["files"]:
                            server_files.append(self.convert_server_path_to_non_local_server(
                                    cloud_dir,
                                    tool_local_dir,
                                    path
                                )
                            )

                    # get local files
                    for path, directories, files in scandir.walk(tool_local_dir):
                        for file_name in files:
                            local_file_path = os.path.join(path, file_name)
                            if local_file_path not in local_file_paths:
                                local_file_paths.append(local_file_path)

        # remove any files not on server but present locally
        for file_path in local_file_paths:

            if os.path.exists(file_path) and file_path not in server_files:
                # check for exclusion
                exclusion_found = False
                for exclusion in self.exclude_removal:
                    if exclusion in file_path:
                        exclusion_found = True
                        break

                if not exclusion_found:
                    if debug:
                        files_removed.append(file_path)
                    else:
                        logger.info("Removing file not on server: {0}".format(file_path))
                        error = pyani.core.util.delete_file(file_path)
                        if error:
                            errors_removing_files.append(file_path)
                        logger.error(error)

        if debug:
            self.finished_signal.emit(None)
            return files_removed

        self.finished_signal.emit(None)
        return errors_removing_files

    def _reset_thread_counters(self):
        # reset threads counters
        self.thread_total = 0.0
        self.threads_done = 0.0
