import os
import logging
import re
import functools
import pyani.core.appvars
import pyani.core.anivars
import pyani.core.ui
import pyani.core.util
from pyani.core.mngrcore import AniCoreMngr

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtCore, QtWidgets
from PyQt4.QtCore import pyqtSlot, pyqtSignal

logger = logging.getLogger()


class AniAssetMngr(AniCoreMngr):
    """
    A class object that manages asset information. To build a local asset cache,
    simply call server_build_local_cache() and connect to the signal finished_cache_build_signal
    to find out when it finishes.

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

    Methods prefixed with 'cgt' are methods that contact CGT's cloud.
    """

    # signal that lets other objects know this class is done building local cache
    finished_cache_build_signal = pyqtSignal()
    # signal that lets other objects know this class is done syncing with cgt and downloading
    finished_sync_and_download_signal = pyqtSignal(object)

    def __init__(self):
        AniCoreMngr.__init__(self)
        self.app_vars = pyani.core.appvars.AppVars()
        self.ani_vars = pyani.core.anivars.AniVars()

        self._cgt_asset_info = dict()

        self.thread_pool = QtCore.QThreadPool()
        logger.info("Multi-threading with maximum %d threads" % self.thread_pool.maxThreadCount())
        self.thread_total = 0.0
        self.threads_done = 0.0
        self.thread_error_list = list()

        # identifies which component this mngr is currently responsible for
        self.active_asset_component = None

        # for reporting progress
        self.progress_win = QtWidgets.QProgressDialog()

    @property
    def active_asset_component(self):
        return self._active_asset_component

    @active_asset_component.setter
    def active_asset_component(self, component_name):
        self._active_asset_component = component_name

    def load_cgt_asset_info_cache(self):
        """
        reads the cgt asset info cache off disk
        :return: None if the file was read successfully, the error as a string if reading is unsuccessful.
        """
        json_data = pyani.core.util.load_json(self.app_vars.cgt_asset_info_cache_path)
        if isinstance(json_data, dict):
            self._cgt_asset_info = json_data
            return None
        else:
            return json_data

    def save_cgt_asset_info_cache(self):
        """
        Saves the cgt asset info to a json file
        :return: None if the file was written successfully, the error as a string if writing is unsuccessful.
        """
        # check if folder exists, if not make it
        if not os.path.exists(self.app_vars.persistent_data_path):
            pyani.core.util.make_dir(self.app_vars.persistent_data_path)

        # creates or overwrites the existing cgt asset cache json file
        error = pyani.core.util.write_json(self.app_vars.cgt_asset_info_cache_path, self._cgt_asset_info, indent=4)
        if error:
            return error
        else:
            return None

    def read_asset_update_config(self):
        """
        Reads the asset config file from disk.
        :return: the config json data or None if can't read the file
        """
        if os.path.exists(self.app_vars.update_config_file):
            json_data = pyani.core.util.load_json(self.app_vars.update_config_file)
            if isinstance(json_data, dict):
                return json_data
        return None

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
        for asset_type in self._cgt_asset_info:
            if asset_component in self._cgt_asset_info[asset_type]:
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
                self._cgt_asset_info[asset_type][asset_component][asset_name]
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
            return self._cgt_asset_info[asset_type][asset_component]
        except KeyError:
            return None

    def get_release_notes(self, asset_type, asset_component, asset_name):
        """
        Gets the release notes for the asset from the notes file
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: the asset name as a string
        :return: a tuple of the notes (string or None ) and error if any (string or None)
        """
        # try to get notes path
        try:
            cgt_file_path = self._cgt_asset_info[asset_type][asset_component][asset_name]['notes path']
            local_file_path = self._cgt_asset_info[asset_type][asset_component][asset_name]['local path']
        # no key for notes path, so asset doesn't have notes
        except KeyError:
            # no notes exist, so no error either
            return None, None

        error = self.server_download(cgt_file_path, local_file_path)
        if error:
            # couldn't download notes, return error
            return None, error

        # get notes on disk
        text_data, error = pyani.core.util.read_file(self._convert_cgt_path_to_local(cgt_file_path))

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

    def is_asset_in_asset_update_config(self, asset_type, asset_component, asset_name):
        """
        Checks for the existence of an asset in the asset update config file
        :param asset_type: the asset type - see pyani.core.appvars.py for asset components
        :param asset_component: the asset component - see pyani.core.appvars.py for asset components
        :param asset_name: name of the asset as a string
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
                if asset_name in existing_config_data[asset_type][asset_component]:
                    return True
        return False

    def update_asset_config_file_by_component_name(self, selected_asset_component, config_data):
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

            # check if config data is an empty file, so set to a empty dict object
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
        Updates the cache on disk with data provided. Doe snot connect to CGT. Only uses the asset info passed in
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
                self._cgt_asset_info[asset_type][asset_component][asset_name][key] = value
        except (KeyError, ValueError) as e:
            return "Could not update the local cache. Error is {0}".format(e)

    def sync_local_cache_with_server_and_download(self, assets_dict):
        """
             Updates the cache on disk with the current cgt data. If no parameters are filled the entire cache will
             be rebuilt.
             :param assets_dict: a dict in format:
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
        if not assets_dict:
            return "At least one asset must be provided."

        # reset progress
        self.progress_win.setWindowTitle("Sync Progress")
        self.progress_win.setLabelText("Updating Assets...")
        self.progress_win.setValue(0)
        # makes sure progress shows over window, as windows os will place it under cursor behind other windows if
        # user moves mouse off off app
        pyani.core.ui.center(self.progress_win)
        self.progress_win.show()

        # update the local cache for the assets given
        self.build_local_asset_info_cache(assets_dict=assets_dict, thread_callback=self._thread_server_sync_complete)
        # download and update local meta data such as version
        self.cgt_download_and_update_local_metadata(assets_dict)

    def sync_local_cache_with_server(self, assets_dict=None):
        """
        Updates the cache on disk with the current cgt data. If no parameters are filled the entire cache will
        be rebuilt.
        :param assets_dict: a dict in format:
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
        if not assets_dict:
            self.build_local_asset_info_cache()

        self.build_local_asset_info_cache(assets_dict=assets_dict, thread_callback=self._thread_server_sync_complete)

    def build_local_asset_info_cache(self, assets_dict=None, thread_callback=None):
        """
        Creates a asset data struct using cgt data. Uses multi-threading to gather data and store it locally.
        Stored in the persistent data location. This cache has version info and paths so apps don't have to
        access cgt for this info. Uses multi-threading. Either builds entire cache or updates based off a assets
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
        """

        # reset progress
        self.progress_win.setWindowTitle("Cache Progress")
        self.progress_win.setLabelText("Creating cache...")
        self.progress_win.setValue(0)
        # makes sure progress shows over window, as windows os will place it under cursor behind other windows if
        # user moves mouse off off app
        pyani.core.ui.center(self.progress_win)
        self.progress_win.show()

        # if no method is passed in, use the default cache complete callback
        if not thread_callback:
            thread_callback = self._thread_server_cache_complete

        # if no asset type was provided, rebuild cache for all asset types
        if not assets_dict:
            asset_types = self.app_vars.asset_types
        else:
            asset_types = assets_dict.keys()

        for asset_type in asset_types:
            if asset_type not in self._cgt_asset_info:
                self._cgt_asset_info[asset_type] = dict()
            # if no asset components were provided, rebuild for all components, otherwise rebuild for the
            # asset type's component that was provided
            if not pyani.core.util.find_val_in_nested_dict(assets_dict, [asset_type]):
                asset_components = self.app_vars.asset_types[asset_type]
            else:
                asset_components = assets_dict[asset_type].keys()

            for asset_component in asset_components:
                if asset_component not in self._cgt_asset_info[asset_type]:
                    self._cgt_asset_info[asset_type][asset_component] = dict()

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
                            self.thread_error_list.append(error)
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
                        asset_names = self._cgt_get_dir_list(asset_type_root_path)
                # asset names given so only update these assets
                else:
                    # grab the assets corresponding to the asset type
                    asset_names = assets_dict[asset_type][asset_component]

                # now use multi-threading to check each asset for version, components, and files
                for asset_name in asset_names:
                    worker = pyani.core.ui.Worker(
                        self.cgt_get_asset_info,
                        False,
                        asset_type_root_path,
                        asset_type,
                        asset_name,
                        asset_component
                    )
                    self.thread_total += 1.0
                    self.thread_pool.start(worker)
                    # reset error list
                    self.thread_error_list = list()
                    # slot that is called when a thread finishes
                    worker.signals.finished.connect(thread_callback)
                    worker.signals.error.connect(self._thread_error)

    def cgt_get_asset_info(self, root_path, asset_type, asset_name, asset_component):
        """
        Gets a single asset's version, cgt_path, local path, notes path, and files from CGT.
        Handles both shot and show assets. Also handles multiple files for an asset.
        :param root_path: the path up to the asset name
        :param asset_type: the type of asset, see pyani.core.appvars for asset types
        :param asset_name: the name of the asset as a string. In the case of shot assets, this is always Seq###_Shot###
        :param asset_component: the asset component, see pyani.core.appvars for asset components
        """
        cgt_asset_path = "{0}/{1}".format(root_path, asset_name)
        cgt_asset_component_path = "{0}/{1}".format(cgt_asset_path, asset_component)

        if self.cgt_asset_has_component(cgt_asset_path, asset_component):
            self._cgt_asset_info[asset_type][asset_component][asset_name] = dict()

            # check if asset is published and goes through approval. Some asset components like rigs get approved
            # and have approved and work folders. Others like gpu caches don't.
            if self.is_asset_publishable(asset_type, asset_component):

                # check if this asset has an approved folder
                if self.cgt_is_asset_component_approved(cgt_asset_component_path):
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["approved"] = True
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"] = \
                        "{0}/approved".format(cgt_asset_component_path)
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["local path"] = \
                        self._convert_cgt_path_to_local(
                            self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"]
                        )

                    file_names = self.cgt_get_file_names("{0}/approved".format(cgt_asset_component_path))

                    # check if the asset is versioned. A publishable asset may not be versioned, like audio
                    if self.is_asset_versioned(asset_type, asset_component):
                        _, version = self.core_get_latest_version(
                            "{0}/approved/history".format(cgt_asset_component_path)
                        )
                    # asset not versioned but is approved - ex: audio files
                    else:
                        version = ""

                # no approved folder, only a work folder. work folders are always versioned
                else:
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["approved"] = False
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"] = \
                        "{0}/work/".format(cgt_asset_component_path)
                    self._cgt_asset_info[asset_type][asset_component][asset_name]["local path"] = \
                        self._convert_cgt_path_to_local(
                            self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"]
                        )
                    _, version = self.core_get_latest_version(
                        "{0}/work".format(cgt_asset_component_path)
                    )
                    # get all file names that have this version
                    all_file_names = self.cgt_get_file_names("{0}/work".format(cgt_asset_component_path))
                    # filter for the files that have the version we want
                    if all_file_names:
                        file_names = [file_name for file_name in all_file_names if version in file_name]
                    else:
                        file_names = list()

                # save the version and file name
                self._cgt_asset_info[asset_type][asset_component][asset_name]["version"] = version
                self._cgt_asset_info[asset_type][asset_component][asset_name]["file name"] = file_names

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
                        if self._cgt_asset_info[asset_type][asset_component][asset_name]["approved"]:
                            # make notes name, its the file name with the version in it, insert version between
                            # asset_component and _high, ex: charAnglerFish_rig_high becomes charAnglerFish_
                            # rig_v026_high
                            notes_file_name = "{0}_{1}{2}.txt".format(
                                file_name_no_ext[:index],
                                version,
                                file_name_no_ext[index:]
                            )
                            notes_path = "{0}/approved/history/{1}".format(cgt_asset_component_path, notes_file_name)
                        else:
                            # make notes name, since work folder already has version name in it, just replace extension
                            notes_file_name = "{0}.txt".format(file_name_no_ext)
                            notes_path = "{0}/work/{1}".format(cgt_asset_component_path, notes_file_name)
                        # check if the notes exist on cgt, if so save path
                        if self.cgt_asset_component_has_notes(notes_path):
                            self._cgt_asset_info[asset_type][asset_component][asset_name]["notes path"] = notes_path

            # asset isn't publishable meaning it doesn't have approved or work folders. Note that we don't check for
            # notes for un-publishable assets
            else:
                self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"] = cgt_asset_component_path
                self._cgt_asset_info[asset_type][asset_component][asset_name]["local path"] = \
                    self._convert_cgt_path_to_local(
                        self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"]
                    )
                self._cgt_asset_info[asset_type][asset_component][asset_name]["version"] = ""
                self._cgt_asset_info[asset_type][asset_component][asset_name]["file name"] = \
                    self.cgt_get_file_names(cgt_asset_component_path)

    def cgt_download_and_update_local_metadata(self, assets_dict):
        """
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
        # now use multi-threading to download
        for asset_type in assets_dict:
            for asset_component in assets_dict[asset_type]:
                for asset_name in assets_dict[asset_type][asset_component]:
                    # could be more than one file
                    for file_name in self._cgt_asset_info[asset_type][asset_component][asset_name]["file name"]:
                        cgt_path = "{0}/{1}".format(
                            self._cgt_asset_info[asset_type][asset_component][asset_name]["cgt path"],
                            file_name
                        )
                        local_path = self._cgt_asset_info[asset_type][asset_component][asset_name]["local path"]
                        # server_download expects a list of files, so pass list even though just one file
                        worker = pyani.core.ui.Worker(
                            self.server_download,
                            False,
                            [cgt_path],
                            local_file_paths=[local_path],
                            update_local_version=True
                        )
                        self.thread_total += 1.0
                        self.thread_pool.start(worker)
                        # reset error list
                        self.thread_error_list = list()
                        # slot that is called when a thread finishes
                        worker.signals.finished.connect(self._thread_server_sync_complete)
                        worker.signals.error.connect(self._thread_error)

    def server_download(self, server_file_paths, local_file_paths=None, update_local_version=False):
        """
        Downloads files from CGT
        :param server_file_paths: a list of cgt cloud paths
        :param local_file_paths: a list of the local file paths where cgt files stored
        :param update_local_version: a boolean indicating whether the version file on disk should be updated after
        a successful download
        :return: error as string or None
        """

        # we need a list, if a single path was passed, then convert to a list
        if not isinstance(server_file_paths, list):
            server_file_paths = [server_file_paths]

        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "server_download.py")

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
                local_dl_paths.append(self._convert_cgt_path_to_local(download_dir))

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
                logger.error(error)
                return error

        except pyani.core.util.CGTError as e:
            logger.exception(e)
            return e

        # download successful, check if the local version file should be updated
        if update_local_version:
            errors = list()
            for index, cgt_file_path in enumerate(server_file_paths):
                error = self._update_local_version(cgt_file_path, local_file_paths[index])
                if error:
                    errors.append(error)
            if errors:
                return "Error updating cgt metadata. The following errors occurred: {0}".format(
                    ", ".join(errors)
                )

        return None

    def cgt_asset_component_has_notes(self, notes_path):
        """
        Checks if an asset component has notes, for example does the rig have notes
        :param notes_path: a string containing the cgt path to the notes,
        ex: /LongGong/assets/set/setGarageInside/rig/approved/history/setGarageInside_rig_v004_high.txt or
        /LongGong/assets/set/setGarageInside/rig/work/setGarageInside_rig_v004_high.txt
        :return: True if notes exist or False if not
        """
        if notes_path:
            # split off notes file name to get the directory
            notes_dir = "/".join(notes_path.split("/")[:-1])
            # compare file name of notes to the directory listing. if notes in the listing then exists
            if notes_path.split("/")[-1] in self._cgt_get_dir_list(notes_dir, files_only=True):
                return True
            else:
                return False

    def cgt_get_file_names(self, cgt_path_to_files):
        """
        gets a list of files from the CGT cloud (online area) given a cgt path
        :param cgt_path_to_files: the absolute path for the directory listing
        :return: the file list. if no files, returns None
        """
        return self._cgt_get_dir_list(cgt_path_to_files, dirs_only=False, files_only=True)

    def core_get_latest_version(self, server_path_to_files):
        """
        gets the latest file name and version of an asset's component
        :param server_path_to_files: the cgt cloud path to the asset component's files
        :return: the most recent file's name and version as a tuple (file name, version)
        """
        # get the list of files, these should be a bunch of files with versions in the file name
        file_list = self.cgt_get_file_names(server_path_to_files)
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

    def cgt_asset_has_component(self, cgt_asset_path, asset_component):
        """
        Check if an asset has the component. A component is a directory under the asset name on CGT. For example:
        if "rig" is a component and we have a character asset 'Hei', then we are looking for
        /Longong/asset/char/Hei/rig. If "model/cache" is the component and we have a
        :param cgt_asset_path: path on cgt cloud to the asset
        :param asset_component: the asset component to check for
        :return: True if found, False if doesn't exist or an asset has no components
        """
        # need to check if the asset component is a path, i.e. the component isn't directly under the asset name. This
        # happens for example with gpu cache, which is under asset name/model/cache
        for component in asset_component.split("/"):
            # get directory listing
            asset_components = self._cgt_get_dir_list(cgt_asset_path)
            # check if a listing was returned, if not then the asset is missing all components
            if not asset_components:
                return False
            # check if the component, which is a directory, is in the listing. If it is continue, if not exit
            if component in asset_components:
                # add directory to the path and continue search
                cgt_asset_path = "{0}/{1}".format(cgt_asset_path, component)
            # didn't find the component/directory, so exit, no need to continue search
            else:
                return False
        # component / directories exist
        return True

    def cgt_is_asset_component_approved(self, cgt_asset_component_path):
        """
        Checks if an asset has an approved folder, meaning it was published.
        :param cgt_asset_component_path: the cgt cloud path to the asset's component
        :return: True if asset's component has an approved folder, False if not
        """
        if self._cgt_get_dir_list("{0}/{1}".format(cgt_asset_component_path, "approved"), files_and_dirs=True):
            return True
        else:
            return False

    def _cgt_get_dir_list(self, cgt_path, dirs_only=True, files_only=False, files_and_dirs=False):
        """
        Called to get a list of files and/or directories for a given path in CGT
        :param cgt_path: the path in the online area of CGT
        :param dirs_only: only return directories
        :param files_only: only return files
        :param files_and_dirs: return files and directories
        :return: a list of files or directories, or an error styring
        """

        # the python script to call that connects to cgt
        py_script = os.path.join(self.app_vars.cgt_bridge_api_path, "server_download.py")
        # the command that subprocess will execute
        command = [
            py_script,
            cgt_path,                   # path to directory to get file list
            "",                         # getting a file list so no download paths
            self.app_vars.cgt_ip,
            self.app_vars.cgt_user,
            self.app_vars.cgt_pass,
            "True"                      # tell cgt to not walk folder structure
        ]
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
                return error
            # check for output
            if output:
                file_list = output.split(",")
                file_paths = [
                    file_path.split("/")[-1].replace("\n", "").replace("\r", "") for file_path in file_list
                ]
                return file_paths
        # CGT errors
        except pyani.core.util.CGTError as e:
            return e

    def _update_local_version(self, cgt_file_path, local_file_path_dir):
        """
        Updates the asset version in the local metadata file
        :param cgt_file_path: path to file in cgt cloud
        :param local_file_path_dir: the directory of the local file path of the downloaded file
        :return:
        """

        # split off path up to component, removing file name and approved or work folder
        cgt_path_to_version_history = '/'.join(cgt_file_path.split("/")[:-1])
        # check if approved or work, approved requires adding /history/ to end of path
        if "approved" in cgt_file_path:
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
            return error

    @staticmethod
    def _convert_cgt_path_to_local(cgt_path):
        """
        converts a cgt path to a local path on the z drive
        :param cgt_path: the cgt path
        :return: the converted path on the z drive
        """
        local_path = "Z:"
        # split up the cgt path and rebuild with backslashes
        for path_component in cgt_path.split("/"):
            local_path = "{0}\\{1}".format(local_path, path_component)
        return os.path.normpath(local_path)

    @pyqtSlot()
    def _thread_server_sync_complete(self):
        """
        Called when a thread that builds the cgt asset cache completes
        """
        # a thread finished, increment our count
        self.threads_done += 1.0
        # get the current progress percentage
        progress = (self.threads_done / self.thread_total) * 100.0
        self.progress_win.setValue(progress)
        # check if we are finished
        if progress >= 100.0:
            # done, let any listening objects/classes know we are finished
            self.finished_sync_and_download_signal.emit(self.active_asset_component)
            # reset threads counters
            self.thread_total = 0.0
            self.threads_done = 0.0

    @pyqtSlot()
    def _thread_server_cache_complete(self):
        """
        Called when a thread that builds the cgt asset cache completes
        """
        # a thread finished, increment our count
        self.threads_done += 1.0
        # get the current progress percentage
        progress = (self.threads_done / self.thread_total) * 100.0
        self.progress_win.setValue(progress)
        # check if we are finished
        if progress >= 100.0:
            # save the cache locally
            self.save_cgt_asset_info_cache()
            # done, let any listening objects/classes know we are finished
            self.finished_cache_build_signal.emit()
            # reset threads counters
            self.thread_total = 0.0
            self.threads_done = 0.0

    def _thread_error(self, error):
        """
        Called when an error occurs in the thread
        :param error: a tuple containing the exception type, the exception value/msg, and traceback. Note the
        exeception value is of type Exception.exception and must be casted to a string. The signal is in
        pyani.core.ui.Worker
        """
        exec_type, error_msg, traceback_msg = error
        # record error in a list, when all threads complete can use this to inform user
        self.thread_error_list.append(str(error_msg))
