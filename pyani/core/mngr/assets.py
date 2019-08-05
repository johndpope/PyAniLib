import os
import logging
import functools
import pyani.core.appvars
import pyani.core.anivars
import pyani.core.ui
import pyani.core.util
from pyani.core.mngr.core import AniCoreMngr


logger = logging.getLogger()


class AniAssetMngr(AniCoreMngr):
    """
    A class object that manages asset information.

    Requirements:
        - show assest are in /LongGong/assets/
        - the folders beneath the above assets/ folder are called asset types, ex: /LongGong/assets/char
        - the folders beneath the asset types are the asset names, ex: /LongGong/assets/char/charAnglerFish
        - which each asset's folder are asset components, ex: /LongGong/assets/char/charAnglerFish/rigs
        - asset files are either in approved/ or work/ folders,
          for example, /LongGong/assets/char/charAnglerFish/rigs/approved or
          /LongGong/assets/char/charAnglerFish/rigs/work
        - approved asset files have no version in file name and versions live in approved/history
        - work files have versions in file names and all work files live beneath the work/ folder, i.e. no history
          folder like approved
        - notes live directly under approved/history or work/ and have version name in them
        - shot assets live in /LongGong/sequence/Seq###/Shot###/

    Methods prefixed with 'server' are methods that contact CGT's cloud.


    USAGE:

    Create one instance to handle multiple tools. Set the active component to control what assets are being managed
    EX: We have Rigs and Audio
    When I want to manage Rigs, I do asset_mngr_instance.active_asset_component = "Rigs" - set to user friendly name
    see pyani.core.appvars.AppVars asset types 'name' for user friendly name

    Updating / Building Caches:
    To build a local cache,
    simply call sync_local_cache_with_server() (optionally pass a dict to update specific assets, see method
    doc string for format) and connect to the signal _thread_server_sync_complete (inherited from AniCoreMngr)
    to find out when it finishes.

    Download Files and Sync Cache:
    call sync_local_cache_with_server_and_download and pass a dict to update, see method
    doc string for format). connect to _thread_server_sync_complete (inherited from AniCoreMngr)
    to find out when it finishes.

    Reports errors using signals from pyani.core.mngrcore.AniCoreMngr:
    error_thread_signal, connect to this signal as:
    asset_mngr_instance.error_thread_signal.connect(method_that_receives_error)

    method_that_receives_error(error):
        print error

    emits these, and listening class can receive and display.

    """

    def __init__(self):
        AniCoreMngr.__init__(self)
        self._asset_info = dict()

        # identifies which component this mngr is currently responsible for
        self.active_asset_component = None

    @property
    def active_asset_component(self):
        return self._active_asset_component

    @active_asset_component.setter
    def active_asset_component(self, component_name):
        self._active_asset_component = component_name

    def load_server_asset_info_cache(self):
        """
        reads the server asset info cache off disk
        :return: None if the file was read successfully, the error as a string if reading is unsuccessful.
        """
        json_data = self.load_server_local_cache(self.app_vars.cgt_asset_info_cache_path)
        if isinstance(json_data, dict):
            self._asset_info = json_data
            return None
        else:
            return json_data

    def get_asset_component_names(self):
        """
        Gets a list of all possible asset components using user friendly name - see pyani.core.appvars.AppVars
        :return: list of asset components
        """
        components = []
        for asset_type in self.app_vars.asset_types:
            for component in self.app_vars.asset_types[asset_type]:
                if self.app_vars.asset_types[asset_type][component]['name'] not in components:
                    components.append(self.app_vars.asset_types[asset_type][component]['name'])
        return components

    def get_asset_type_by_asset_component_name(self, asset_component):
        """
        Given an asset component, finds all asset types that have this component
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :return: the asset type(s) as a list, or None if no asset types were found
        """
        asset_types_list = []
        for asset_type in self._asset_info:
            if asset_component in self._asset_info[asset_type]:
                asset_types_list.append(asset_type)
        return asset_types_list

    def get_asset_info_by_asset_name(self, asset_type, asset_component, asset_name):
        """
        Gets all assets and their info given a asset_component name
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: the name of the asset as a string
        :return: a tuple in format:
        {
            asset type,
            asset component,
            asset name,
            { asset properties - file and version info as key/value pairs }
        }

        or returns none if the asset_type or asset_component or asset name doesn't exist
        """
        try:
            asset_info = (
                asset_type,
                asset_component,
                asset_name,
                self._asset_info[asset_type][asset_component][asset_name]
            )
            return asset_info
        except KeyError:
            return None

    def get_asset_info_by_asset_component(self, asset_type, asset_component):
        """
        Gets all assets and their info given a asset_component name
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :return: a nested dict in format:
        {
            asset_name : { asset information as key/value pairs }
        }

        or returns none if the asset_type or asset_component doesn't exist
        """
        try:
            return self._asset_info[asset_type][asset_component]
        except KeyError:
            return None

    def get_release_notes(self, asset_component, asset_name):
        """
        Gets the release notes for the asset from CGT
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: the asset name as a string
        :return: a tuple of the notes (string or None ) and error if any (string or None)
        """
        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "cgt_get_notes.py")

        # capitalize the component first letter for CGT
        asset_component = asset_component[0].upper() + asset_component[1:]

        # the command that subprocess will execute
        command = [
            py_script,
            asset_component,
            asset_name,
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass,
        ]

        try:
            output, error = pyani.core.util.call_ext_py_api(command)

            # check for subprocess errors
            if error:
                error_fmt = "Error occurred launching subprocess. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return None, error_fmt

            # check for output and return
            if output:
                return output, None

        # CGT errors
        except pyani.core.util.CGTError as error:
            error_fmt = "Error occurred connecting to CGT. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return None, error_fmt

    def get_release_notes_depr(self, asset_type, asset_component, asset_name):
        """
        Gets the release notes for the asset from the notes file
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: the asset name as a string
        :return: a tuple of the notes (string or None ) and error if any (string or None)
        """
        # try to get notes path
        try:
            server_file_path = self._asset_info[asset_type][asset_component][asset_name]['notes path']
            # get file name
            server_file_path_no_filename = "/".join(server_file_path.split("/")[:-1])
            notes_filename = server_file_path.split("/")[-1]
            local_file_path = self.convert_server_path_to_local_server_representation(server_file_path_no_filename)
        # no key for notes path, so asset doesn't have notes
        except KeyError:
            # no notes exist, so no error either
            return None, None

        error = self.server_download(server_file_path, local_file_path)
        if error:
            # couldn't download notes, return error
            return None, error

        # get notes on disk
        text_data, error = pyani.core.util.read_file(os.path.join(local_file_path, notes_filename))

        if error:
            # couldn't read notes off disk, return error
            return None, error

        return text_data, None

    def is_asset_publishable(self, asset_type, asset_component):
        """
        checks if an asset is publishable, meaning it has an approved folder and possibly a work folder
        :param asset_type: the type of asset - see pyani.core.appvars.py for asset types
        :param asset_component: the asset component to check - see pyani.core.appvars.py for asset components
        :return: True if it can be published, False if not
        """
        if self.app_vars.asset_types[asset_type][asset_component]['is publishable']:
            return True
        else:
            return False

    def is_asset_versioned(self, asset_type, asset_component):
        """
        checks if an asset is versioned
        :param asset_type: the type of asset - see pyani.core.appvars.py for asset types
        :param asset_component: the asset component to check - see pyani.core.appvars.py for asset components
        :return: True if it is versioned, False if not
        """
        if self.app_vars.asset_types[asset_type][asset_component]['is versioned']:
            return True
        else:
            return False

    def asset_component_supports_release_notes(self, asset_component):
        """
        checks if an asset's component can have release notes
        :param asset_component: the asset component to check - see pyani.core.appvars.py for asset components
        :return: True if it can have release notes, False if not:
        """
        for asset_type in self.app_vars.asset_types:
            if asset_component in self.app_vars.asset_types[asset_type]:
                # doesn't matter which asset type the component belongs to. components have the same properties
                # regardless of asset type. For example, set rigs and char rigs both support notes, because rigs
                # which is an asset component supports notes
                if self.app_vars.asset_types[asset_type][asset_component]['supports notes']:
                    return True
        return False

    def update_config_file_by_component_name(self, selected_asset_component, config_data):
        """
        Updates the asset update config file with new assets and removes assets that are de-selected (not in
        selection)
        :param selected_asset_component: the asset component we are updating
        :param config_data: a dict of the asset type, asset component and asset names we want to add to the config
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

            # first check for assets whose type and component don't exist yet in the config file
            for asset_type in config_data:
                # when the asset type doesn't yet exist, but other asset types do in the file, so can just add.
                if asset_type not in existing_config_data:
                    existing_config_data[asset_type] = dict()
                    existing_config_data[asset_type] = config_data[asset_type]

                # when asset component doesn't exist but the type does, so can just add
                elif selected_asset_component not in existing_config_data[asset_type]:
                    existing_config_data[asset_type][selected_asset_component] = dict()
                    existing_config_data[asset_type][selected_asset_component] = \
                        config_data[asset_type][selected_asset_component]
                # just replace since type and component exist
                else:
                    existing_config_data[asset_type][selected_asset_component] = \
                        config_data[asset_type][selected_asset_component]

            # check for assets that got deselected for the active component
            for existing_asset_type in existing_config_data:
                for existing_asset_component in existing_config_data[existing_asset_type]:
                    # check if the component from the existing config is in the selection. Otherwise it will delete
                    # assets from other components. For example if we pass only audio (i.e. on audio tab), it would
                    # delete rigs. This check prevents that
                    if selected_asset_component == existing_asset_component:
                        # if don't find the key, means doesn't exist in the selected assets passed in, so remove from
                        # our existing config file
                        if not pyani.core.util.find_val_in_nested_dict(
                                config_data,
                                [existing_asset_type, existing_asset_component]
                        ):
                            existing_config_data[existing_asset_type][existing_asset_component] = dict()

            error = pyani.core.util.write_json(self.app_vars.update_config_file, existing_config_data, indent=4)
            if error:
                return error
            return None

    def update_local_cache(self, asset_type, asset_component, asset_name, asset_update_info):
        """
        Updates the cache on disk with data provided. Does not connect to server. Only uses the asset info passed in
        through asset_update_info
        :param asset_type: a list of the type of asset(s) to update - see pyani.core.appvars.py for asset types
        :param asset_component: a list of the asset component to update- see pyani.core.appvars.py for asset components
        :param asset_name: a list of asset names
        :param asset_update_info: a tuple in format:
            ( asset type as string, asset component as string, asset name as string, asset info as dict )
            asset info is a dict in format:
            {
                "local path": string path,
                "file name": string file name,
                "cgt path": string path,
                "version": string version,
                "approved": boolean,
                "notes path": string path
            }
            one or more of the above can be provided, for example these are acceptable:
            {
                 "local path": string path,
                "file name": string file name
            }
            -or-
            {
                 "local path": string path
            }
            -or-
            {
                "file name": string file name,
                "cgt path": string path,
                "version": string version,
                "approved": boolean,
                "notes path": string path
            }
            etc...
        :return: None if updated cache, an error string if couldn't update. Note for an entire cache rebuild, use
        the signal finished to check for errors, since its multi-threaded
        """
        try:
            # update the asset info based off the provided data
            for key, value in asset_update_info.items():
                self._asset_info[asset_type][asset_component][asset_name][key] = value
        except (KeyError, ValueError) as e:
            return "Could not update the local cache. Error is {0}".format(e)

    def sync_local_cache_with_server_and_download_gui(self, update_data_dict):
        """
        used with gui asset mngr
        Updates the cache on disk with the current server data. If no parameters are filled the entire cache will
        be rebuilt.
        :param update_data_dict: a dict in format:
        {
         asset type: {
             asset component(s): [
                 asset name(s)
             ]
             }, more asset types...
        }

        There can be one or more asset types. Asset components and asset names are optional.
        Asset components require an asset type. Asset Names require both an asset type and asset component.
        a list of the type of asset(s) to update - see pyani.core.appvars.py for asset types and asset components

        :return: None if updated cache, an error string if couldn't update. Note for an entire cache rebuild, use
        the signal finished to check for errors, since its multi-threaded
        """
        # no asset types, so can't set any other values in data struct, so rebuild entire cache
        if not update_data_dict:
            return "At least one asset must be provided to update."

        # reset progress
        self.init_progress_window("Sync Progress", "Updating Assets...")

        # update the local cache for the assets given
        self.server_build_local_cache(
            assets_dict=update_data_dict,
            thread_callback=self._thread_server_sync_complete,
            thread_callback_args=[self.active_asset_component, self.server_save_local_cache]
        )

        # downloads from the gui, which requires knowing which asset component was run
        self.server_download_from_gui(update_data_dict)

    def sync_local_cache_with_server(self, update_data_dict=None):
        """
        Updates the cache on disk with the current server data. If no parameters are filled the entire cache will
        be rebuilt.
        :param update_data_dict: a dict in format:
        {
            asset type: {
                asset component(s): [
                    asset name(s)
                ]
                }, more asset types...
        }

        There can be one or more asset types. Asset components and asset names are optional.
        Asset components require an asset type. Asset Names require both an asset type and asset component.
        a list of the type of asset(s) to update - see pyani.core.appvars.py for asset types and asset components

        :return: None if updated cache, an error string if couldn't update. Note for an entire cache rebuild, use
        the signal finished to check for errors, since its multi-threaded
        """

        # reset threads counters
        self.thread_total = 0.0
        self.threads_done = 0.0

        # no asset types, so can't set any other values in data struct, so rebuild entire cache
        if not update_data_dict:
            self.server_build_local_cache()
        else:
            self.server_build_local_cache(
                assets_dict=update_data_dict,
                thread_callback=self._thread_server_sync_complete,
                thread_callback_args=[self.active_asset_component, self.server_save_local_cache]
            )

    def server_download_from_gui(self, assets_dict):
        """
        used with gui asset mngr
        downloads files for the assets in the asset dict, and updates the meta data on disk for that file. Uses
        multi-threading.
        :param assets_dict: a dict in format:
        {
             asset type: {
                 asset component(s): [
                     asset name(s)
                 ]
                 }, more asset types...
        }
        """
        # set number of threads to max - can do this since running per asset
        self.set_number_of_concurrent_threads()

        self._reset_thread_counters()

        # if not visible then no other function called this, so we can show progress window
        if not self.progress_win.isVisible():
            # reset progress
            self.init_progress_window("Sync Progress", "Updating tools...")

        # now use multi-threading to download
        for asset_type in assets_dict:
            for asset_component in assets_dict[asset_type]:
                for asset_name in assets_dict[asset_type][asset_component]:
                    # could be more than one file
                    for file_name in self._asset_info[asset_type][asset_component][asset_name]["file name"]:
                        server_path = "{0}/{1}".format(
                            self._asset_info[asset_type][asset_component][asset_name]["cgt path"],
                            file_name
                        )
                        local_path = self._asset_info[asset_type][asset_component][asset_name]["local path"]
                        # server_download expects a list of files, so pass list even though just one file
                        worker = pyani.core.ui.Worker(
                            self.server_download,
                            False,
                            [server_path],
                            local_file_paths=[local_path],
                            update_local_version=True
                        )
                        self.thread_total += 1.0
                        self.thread_pool.start(worker)
                        # reset error list
                        self.init_thread_error()
                        # slot that is called when a thread finishes
                        worker.signals.finished.connect(
                            functools.partial(
                                self._thread_server_sync_complete,
                                self.active_asset_component,
                                self.server_save_local_cache
                            )
                        )
                        worker.signals.error.connect(self.send_thread_error)

    def server_download_no_sync(self, assets_dict=None):
        """
        downloads files for the assets in the asset dict, but does not sync cache. Uses
        multi-threading.
        :param assets_dict: a dict in format:
        {
             asset type: {
                 asset component(s): [
                     asset name(s)
                 ]
                 }, more asset types...
        }
        """
        # set number of threads to max - can do this since running per asset
        self.set_number_of_concurrent_threads()

        self._reset_thread_counters()

        # if not visible then no other function called this, so we can show progress window
        if not self.progress_win.isVisible():
            # reset progress
            self.init_progress_window("Sync Progress", "Updating tools...")

        # now use multi-threading to download
        for asset_type in assets_dict:
            for asset_component in assets_dict[asset_type]:
                for asset_name in assets_dict[asset_type][asset_component]:
                    # could be more than one file
                    for file_name in self._asset_info[asset_type][asset_component][asset_name]["file name"]:
                        server_path = "{0}/{1}".format(
                            self._asset_info[asset_type][asset_component][asset_name]["cgt path"],
                            file_name
                        )
                        local_path = self._asset_info[asset_type][asset_component][asset_name]["local path"]
                        # server_download expects a list of files, so pass list even though just one file
                        worker = pyani.core.ui.Worker(
                            self.server_download,
                            False,
                            [server_path],
                            local_file_paths=[local_path],
                            update_local_version=True
                        )
                        self.thread_total += 1.0
                        self.thread_pool.start(worker)
                        # reset error list
                        self.init_thread_error()
                        # slot that is called when a thread finishes
                        worker.signals.finished.connect(self._thread_server_download_complete)
                        worker.signals.error.connect(self.send_thread_error)

    def server_build_local_cache(self, assets_dict=None, thread_callback=None, thread_callback_args=None):
        """
        Creates a asset data struct using server data. Uses multi-threading to gather data and store it locally.
        Stored in the persistent data location. This cache has version info and paths so apps don't have to
        access server for this info. Uses multi-threading. Either builds entire cache or updates based off a assets
        in the asset_dict parameter.
        :param assets_dict: a dict in format:
        {
            asset type: {
                asset component(s): [
                    asset name(s)
                ]
                }, more asset types...
        }
         corresponding to the asset type in asset types list. ex:
        :param thread_callback: a method to call as threads complete
        :param thread_callback_args: any args to pass to thread callback
        """
        # set number of threads to max
        self.set_number_of_concurrent_threads()

        self._reset_thread_counters()

        # if no thread callback then normal server cache creation so show progress, otherwise there should be
        # a progress window already running
        if not thread_callback:
            # reset progress
            self.init_progress_window("Cache Progress", "Creating cache...")

        # if no asset type was provided, rebuild cache for all asset types
        if not assets_dict:
            asset_types = self.app_vars.asset_types
        else:
            asset_types = assets_dict.keys()

        for asset_type in asset_types:
            if asset_type not in self._asset_info:
                self._asset_info[asset_type] = dict()
            # if no asset components were provided, rebuild for all components, otherwise rebuild for the
            # asset type's component that was provided
            if not pyani.core.util.find_val_in_nested_dict(assets_dict, [asset_type]):
                asset_components = self.app_vars.asset_types[asset_type]
            else:
                asset_components = assets_dict[asset_type].keys()

            for asset_component in asset_components:
                if asset_component not in self._asset_info[asset_type]:
                    self._asset_info[asset_type][asset_component] = dict()

                # build path to asset types directory, ex /LongGong/asset/set
                asset_type_root_path = self.app_vars.asset_types[asset_type][asset_component]["root path"]

                # if no asset names provided, rebuild all assets for asset component
                if not pyani.core.util.find_val_in_nested_dict(assets_dict, [asset_type, asset_component]):
                    asset_names = list()
                    # handle shot assets' asset name differently than show assets' asset names
                    if asset_type == "shot":
                        # make sure the sequence shot list loads
                        error = self.ani_vars.load_seq_shot_list()
                        if error:

                            return error
                        else:
                            # build a list of asset names as Seq###_Shot###
                            for seq in self.ani_vars.get_sequence_list():
                                self.ani_vars.update(seq_name=seq)
                                # fire off method in thread per sequence to get audio for shots
                                for shot in self.ani_vars.get_shot_list():
                                    asset_names.append("{0}/{1}".format(seq, shot))

                    # show assets
                    else:
                        # get all assets in the directory
                        asset_names = self.server_get_dir_list(asset_type_root_path)

                # asset names given so only update these assets
                else:
                    # grab the assets corresponding to the asset type
                    asset_names = assets_dict[asset_type][asset_component]
                
                # now use multi-threading to check each asset for version, components, and files
                for asset_name in asset_names:
                    worker = pyani.core.ui.Worker(
                        self.server_get_asset_info,
                        False,
                        asset_type_root_path,
                        asset_type,
                        asset_name,
                        asset_component
                    )
                    self.thread_total += 1.0
                    self.thread_pool.start(worker)
                    # reset error list
                    self.init_thread_error()
                    # slot that is called when a thread finishes, pass the call back function to call when its done
                    # check if thread callback is cache update or cache update with download, if no callback,
                    # use the default cache complete callback
                    if not thread_callback:
                        worker.signals.finished.connect(
                            functools.partial(self._thread_server_cache_complete, self.server_save_local_cache)
                        )
                    else:
                        active_asset_component = thread_callback_args[0]
                        save_method = thread_callback_args[1]
                        worker.signals.finished.connect(
                            functools.partial(self._thread_server_sync_complete, active_asset_component, save_method)
                        )
                    worker.signals.error.connect(self.error_thread_signal)

    def server_get_asset_info(self, root_path, asset_type, asset_name, asset_component):
        """
        Gets a single asset's version, server path, local path, notes path, and files from server.
        Handles both shot and show assets. Also handles multiple files for an asset.
        :param root_path: the path up to the asset name
        :param asset_type: the type of asset, see pyani.core.appvars for asset types
        :param asset_name: the name of the asset as a string. In the case of shot assets, this is always Seq###_Shot###
        :param asset_component: the asset component, see pyani.core.appvars for asset components
        """
        server_asset_path = "{0}/{1}".format(root_path, asset_name)
        server_asset_component_path = "{0}/{1}".format(server_asset_path, asset_component)

        if self.server_asset_has_component(server_asset_path, asset_component):
            self._asset_info[asset_type][asset_component][asset_name] = dict()

            # check if asset is published and goes through approval. Some asset components like rigs get approved
            # and have approved and work folders. Others like gpu caches don't.
            if self.is_asset_publishable(asset_type, asset_component):

                # check if this asset has an approved folder
                if self.server_is_asset_component_approved(server_asset_component_path):
                    self._asset_info[asset_type][asset_component][asset_name]["approved"] = True
                    self._asset_info[asset_type][asset_component][asset_name]["cgt path"] = \
                        "{0}/approved".format(server_asset_component_path)
                    self._asset_info[asset_type][asset_component][asset_name]["local path"] = \
                        self.convert_server_path_to_local_server_representation(
                            self._asset_info[asset_type][asset_component][asset_name]["cgt path"]
                        )

                    file_names = self.server_get_file_names("{0}/approved".format(server_asset_component_path))

                    # check if the asset is versioned. A publishable asset may not be versioned, like audio
                    if self.is_asset_versioned(asset_type, asset_component):
                        _, version = self.core_get_latest_version(
                            "{0}/approved/history".format(server_asset_component_path)
                        )
                    # asset not versioned but is approved - ex: audio files
                    else:
                        version = ""

                # no approved folder, only a work folder. work folders are always versioned
                else:
                    self._asset_info[asset_type][asset_component][asset_name]["approved"] = False
                    self._asset_info[asset_type][asset_component][asset_name]["cgt path"] = \
                        "{0}/work/".format(server_asset_component_path)
                    self._asset_info[asset_type][asset_component][asset_name]["local path"] = \
                        self.convert_server_path_to_local_server_representation(
                            self._asset_info[asset_type][asset_component][asset_name]["cgt path"]
                        )
                    _, version = self.core_get_latest_version(
                        "{0}/work".format(server_asset_component_path)
                    )
                    # get all file names that have this version
                    all_file_names = self.server_get_file_names("{0}/work".format(server_asset_component_path))
                    # filter for the files that have the version we want
                    if all_file_names:
                        file_names = [file_name for file_name in all_file_names if version in file_name]
                    else:
                        file_names = list()

                # save the version and file name
                self._asset_info[asset_type][asset_component][asset_name]["version"] = version
                self._asset_info[asset_type][asset_component][asset_name]["file name"] = file_names

                # check if notes file exists for current version of asset component. if it does save the path
                # check if asset supports notes
                if self.asset_component_supports_release_notes(asset_component):
                    # notes only exist if there is a version
                    if version:
                        # remove .mb or .ma from file name - this is the name for the notes
                        file_name_no_ext = file_names[0].split(".")[0]
                        # all approved file names are {asset}_{asset component}_high.ext
                        index = file_name_no_ext.find("_high")
                        # format the path to notes based off if asset is approved
                        if self._asset_info[asset_type][asset_component][asset_name]["approved"]:
                            # make notes name, its the file name with the version in it, insert version between
                            # asset_component and _high, ex: charAnglerFish_rig_high becomes charAnglerFish_
                            # rig_v026_high
                            notes_file_name = "{0}_{1}{2}.txt".format(
                                file_name_no_ext[:index],
                                version,
                                file_name_no_ext[index:]
                            )
                            notes_path = "{0}/approved/history/{1}".format(server_asset_component_path, notes_file_name)
                        else:
                            # make notes name, since work folder already has version name in it, just replace extension
                            notes_file_name = "{0}.txt".format(file_name_no_ext)
                            notes_path = "{0}/work/{1}".format(server_asset_component_path, notes_file_name)
                        # check if the notes exist on cgt, if so save path
                        if self.server_asset_component_has_notes(notes_path):
                            self._asset_info[asset_type][asset_component][asset_name]["notes path"] = notes_path

            # asset isn't publishable meaning it doesn't have approved or work folders. Note that we don't check for
            # notes for un-publishable assets
            else:
                self._asset_info[asset_type][asset_component][asset_name]["cgt path"] = server_asset_component_path
                self._asset_info[asset_type][asset_component][asset_name]["local path"] = \
                    self.convert_server_path_to_local_server_representation(
                        self._asset_info[asset_type][asset_component][asset_name]["cgt path"]
                    )
                self._asset_info[asset_type][asset_component][asset_name]["version"] = ""
                self._asset_info[asset_type][asset_component][asset_name]["file name"] = \
                    self.server_get_file_names(server_asset_component_path)

    def server_asset_component_has_notes(self, notes_path):
        """
        Checks if an asset component has notes, for example does the rig have notes
        :param notes_path: a string containing the server path to the notes,
        ex: /LongGong/assets/set/setGarageInside/rig/approved/history/setGarageInside_rig_v004_high.txt or
        /LongGong/assets/set/setGarageInside/rig/work/setGarageInside_rig_v004_high.txt
        :return: True if notes exist or False if not
        """
        if notes_path:
            # split off notes file name to get the directory
            notes_dir = "/".join(notes_path.split("/")[:-1])
            # compare file name of notes to the directory listing. if notes in the listing then exists
            if notes_path.split("/")[-1] in self.server_get_dir_list(notes_dir, files_only=True):
                return True
            else:
                return False

    def server_get_file_names(self, server_path_to_files):
        """
        gets a list of files from the server given a server path
        :param server_path_to_files: the absolute path for the directory listing
        :return: the file list. if no files, returns None
        """
        return self.server_get_dir_list(server_path_to_files, dirs_only=False, files_only=True)

    def server_asset_has_component(self, server_asset_path, asset_component):
        """
        Check if an asset has the component. A component is a directory under the asset name on server. For example:
        if "rig" is a component and we have a character asset 'Hei', then we are looking for
        /Longong/asset/char/Hei/rig. If "model/cache" is the component and we have a
        :param server_asset_path: path on server to the asset
        :param asset_component: the asset component to check for
        :return: True if found, False if doesn't exist or an asset has no components
        """
        # need to check if the asset component is a path, i.e. the component isn't directly under the asset name. This
        # happens for example with gpu cache, which is under asset name/model/cache
        for component in asset_component.split("/"):
            # get directory listing
            asset_components = self.server_get_dir_list(server_asset_path)
            # check if a listing was returned, if not then the asset is missing all components
            if not asset_components:
                return False
            # check if the component, which is a directory, is in the listing. If it is continue, if not exit
            if component in asset_components:
                # add directory to the path and continue search
                server_asset_path = "{0}/{1}".format(server_asset_path, component)
            # didn't find the component/directory, so exit, no need to continue search
            else:
                return False
        # component / directories exist
        return True

    def server_is_asset_component_approved(self, server_asset_component_path):
        """
        Checks if an asset has an approved folder, meaning it was published.
        :param server_asset_component_path: the server path to the asset's component
        :return: True if asset's component has an approved folder, False if not
        """
        if self.server_get_dir_list("{0}/{1}".format(server_asset_component_path, "approved"), files_and_dirs=True):
            return True
        else:
            return False

    def server_save_local_cache(self):
        """
        Saves the server asset info to a json file
        :return: None if the file was written successfully, the error as a string if writing is unsuccessful.
        If this function is called in a threaded environment, connect to the
        pyani.core.mngrcore thread error signal to get the error
        """
        # check if folder exists, if not make it
        if not os.path.exists(self.app_vars.persistent_data_path):
            error = pyani.core.util.make_dir(self.app_vars.persistent_data_path)
            if error:
                error_fmt = "Could not save local assets cache. Error is {0}".format(error)
                self.send_thread_error(error_fmt)
                return error_fmt

        # creates or overwrites the existing server asset cache json file
        error = pyani.core.util.write_json(self.app_vars.cgt_asset_info_cache_path, self._asset_info, indent=4)
        if error:
            error_fmt = "Could not save local assets cache. Error is {0}".format(error)
            self.send_thread_error(error_fmt)
            return error_fmt
        else:
            return None

    def _reset_thread_counters(self):
        # reset threads counters
        self.thread_total = 0.0
        self.threads_done = 0.0