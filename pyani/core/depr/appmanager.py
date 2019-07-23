import zipfile
import os
import signal
import datetime
import pyani.core.util
import logging
import requests
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.mayatoolsmngr_depr
import pyani.core.mngr.assets
import pyani.core.mngr.tools

from pyani.core.toolsinstall_depr import AniToolsSetup

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore, QtGui


logger = logging.getLogger()


class AniAppMngr(object):
    """
    Class to manage an app. Does installs and updates
    """
    def __init__(self, app_name):
        self.__log = []

        # used to update app data and apps, and get any new apps.
        self.tools_setup = AniToolsSetup()
        # just using show vars, no sequence or shot vars
        self.ani_vars = pyani.core.anivars.AniVars()

        # these are the same for all apps
        self.__app_data_path = "C:\\PyAniTools\\app_data\\"
        self.__updater_app = "C:\\PyAniTools\\installed\\PyAppMngr\\PyAppMngr.exe"
        # per app variables
        self.__app_name = app_name
        self.__app_doc_page = "http://172.18.10.11:8090/display/KB/{0}".format(self.app_name)
        self.__tools_install_dir = "C:\\PyAniTools\\installed"
        self.__app_install_path = "{0}\\{1}".format(self.tools_install_dir, app_name)
        self.__app_exe = "{0}.exe".format(self.app_name)
        self.__app_package = "C:\\PyAniTools\\packages\\{0}.zip".format(self.app_name)
        self.__user_config = os.path.abspath("{0}\\app_pref.json".format(self.app_install_path))
        self.__app_config = os.path.abspath("{0}{1}\\app_data.json".format(self.app_data_path, self.app_name))
        # load data from json files and log error if one occurs
        self.__user_data = pyani.core.util.load_json(self.user_config)
        if not isinstance(self.__user_data, dict):
            self.__log.append(self.__user_data)
            logger.error(self.__user_data)
            self.__user_data = None
        self.__app_data = pyani.core.util.load_json(self.app_config)
        if not isinstance(self.__app_data, dict):
            self.__log.append(self.__app_data)
            logger.error(self.__app_data)
            self.__app_data = None

        # try to set user version
        if self.__user_data:
            self.__user_version = self.__user_data["version"]
        else:
            self.__user_version = None
        # try to get latest version
        if self.__app_data:
            self.__latest_version = self.__app_data["versions"][0]["version"]
        else:
            self.__latest_version = None
        # try to get release notes
        if self.__app_data:
            self.__features = ", ".join(self.__app_data["versions"][0]["features"])
        else:
            self.__features = None

    @property
    def log(self):
        """Log of errors as list
        """
        return self.__log

    @property
    def app_doc_page(self):
        """Address Url of application documentation
        """
        return self.__app_doc_page

    @property
    def user_version(self):
        """The version the user has installed.
        """
        return self.__user_version

    @property
    def tools_install_dir(self):
        """Location where tools are installed
        """
        return self.__tools_install_dir

    @property
    def latest_version(self):
        """The version on the server
        """
        return self.__latest_version

    @property
    def updater_app(self):
        """The file path to the python updater script
        """
        return self.__updater_app

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

    @property
    def features(self):
        """The apps features or release notes list
        """
        return self.__features

    def install(self):
        """Installs the latest version of the app
        :return Error if encountered, None if no errors
        """
        # remove the existing app
        if os.path.exists(self.app_package) and zipfile.is_zipfile(self.app_package):
            error = pyani.core.util.rm_dir(self.app_install_path)
            if error:
                return error
            # unzip new app files
            error = self.unpack_app(self.app_package, self.app_install_path)
            if error:
                return error

            self._update_user_version()

            return None
        else:
            error = "The zip file {0} is invalid or does not exist, cannot install_apps.".format(self.app_package)
            logging.error(error)
            return error

    @staticmethod
    def unpack_app(package, install_path):
        """
        Unzip a zip file with an application  inside
        :param package: the zip file containing the package
        :param install_path: the place to unzip
        :return error if encountered, otherwise None

        """
        try:
            with zipfile.ZipFile(file=package) as zipped:
                zipped.extractall(path=install_path)
            return None
        except (zipfile.BadZipfile, zipfile.LargeZipFile, IOError, OSError) as e:
            error = "{0} update file is corrupt. Error is {1}".format(package, e)
            logger.exception(error)
            return error

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

    def is_latest(self):
        """Checks if user has the latest version
        :return False if there is a new version, True if on the latest version. Returns None if the app data isn't
        loaded
        """
        if isinstance(self.__app_data, dict):
            latest_version = self.__app_data["versions"][0]["version"]
            if not self.__user_data["version"] == latest_version:
                return False
            else:
                return True
        else:
            return None

    def _update_user_version(self):
        """Updates the user version - call after updating an app
        """
        self.__user_data = pyani.core.util.load_json(self.user_config)
        self.__user_version = self.__user_data["version"]

    def download_update(self, skip_update_check=False):
        """
        Downloads the files from cgt.
        :param skip_update_check: whether to only download the update if its newer.
        :return True if downloaded, False if no updates to download, error if encountered.
        """
        # update
        return self.tools_setup.download_updates(skip_update_check=skip_update_check)

    def install_update(self):
        """
        Installs downloaded files from cgt.
        :return If successful returns None, otherwise returns error
        """
        # MAKE MAIN DIRECTORY ON C DRIVE --------------------------------------------
        error, created = self.tools_setup.make_install_dirs()
        if error:
            return error

        # APP DATA -------------------------------------------------------------------
        error = self.tools_setup.update_app_data()
        if error:
            return error

        # SETUP PACKAGES ------------------------------------------------------------
        error = self.tools_setup.update_packages()
        if error:
            return error

        # SETUP APPS ---------------------------------------------------------------
        # first install_apps
        if not os.path.exists(self.tools_setup.app_vars.apps_dir):
            error, created_shortcuts = self.tools_setup.add_all_apps()
            if error:
                return error
        # already installed
        else:
            error, new_apps = self.tools_setup.add_new_apps()
            if error:
                return error

        # NUKE --------------------------------------------------------------------
        # first check for .nuke  folder in C:Users\username
        error, created = self.tools_setup.make_nuke_dir()
        if error:
            return error

        # check for  custom nuke folder in .nuke
        error, created = self.tools_setup.make_custom_nuke_dir()
        if error:
            return error

        # copy custom init.py, menu.py, and .py (script with python code to support menu and gizmos)
        # Note: remove the files first, copy utils seem to not like existing files
        error = self.tools_setup.copy_custom_nuke_init_and_menu_files()
        if error:
            return error
        # finally update the init.py - only append, don't want to lose existing code added by user
        error, added_plugin_path = self.tools_setup.add_custom_nuke_path_to_init()
        if error:
            return error

        # update sequence list
        error = self.tools_setup.update_show_info()
        if error:
            return "Sequence List Update Failed. Error is {0}".format(error)

        # update install_apps date
        error = self.tools_setup.set_install_date()
        if error:
            return error




''''

-----------------------------------------------------------------------------------------


'''





class AssetComponentTab(QtWidgets.QWidget):
    def __init__(self, name, asset_mngr, tab_desc=None, asset_component=None):
        super(AssetComponentTab, self).__init__()

        # variables for asset (non-ui)
        self.app_vars = pyani.core.appvars.AppVars()
        self.asset_mngr = asset_mngr
        self._name = name
        self.assets_with_versions = ["rig"]
        # if asset component specified set it, otherwise use the name
        if asset_component:
            self.asset_component = asset_component
        else:
            self.asset_component = self.name

        # make a msg window class for communicating with user
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # text font to use for ui
        self.font_family = "Century Gothic"
        self.font_size = 10
        self.font_size_notes_title = 14
        self.font_size_notes_text = 10

        # ui variables
        self.asset_tree = None
        self.tab_description = tab_desc
        self.btn_sync_cgt = pyani.core.ui.ImageButton(
            "images\sync_cache_off.png",
            "images\sync_cache_on.png",
            "images\sync_cache_on.png",
            size=(86, 86)
        )
        self.btn_save_config = pyani.core.ui.ImageButton(
            "images\\auto_dl_off.png",
            "images\\auto_dl_on.png",
            "images\\auto_dl_on.png",
            size=(86, 86)
        )
        self.show_only_auto_update_assets_label, self.show_only_auto_update_assets_cbox = pyani.core.ui.build_checkbox(
            "Show Only Assets that are Auto-Updated.",
            False,
            "Shows assets that are in the auto update config file. These are the green colored assets below."
        )

        # window to display notes
        self.notes_window = QtWidgets.QDialog(parent=self)
        self.notes_window.setMinimumSize(725, 500)
        layout = QtWidgets.QVBoxLayout()
        self.notes_display = QtWidgets.QTextEdit()
        self.notes_display.setReadOnly(True)
        layout.addWidget(self.notes_display)
        self.notes_window.setLayout(layout)

        # this widgets layout
        self.layout = QtWidgets.QVBoxLayout()

        self.build_layout()
        self.set_slots()

    @property
    def name(self):
        """
        The tab name
        """
        return self._name

    def get_layout(self):
        """
        The main layout object
        """
        return self.layout

    def build_layout(self):
        header = QtWidgets.QHBoxLayout()

        # optional description
        desc = QtWidgets.QLabel(self.tab_description)
        desc.setWordWrap(True)
        desc.setMinimumWidth(700)
        header.addWidget(desc)
        header.addStretch(1)

        # buttons
        header.addWidget(self.btn_sync_cgt)
        header.addItem(QtWidgets.QSpacerItem(10, 0))
        header.addWidget(self.btn_save_config)

        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(self.show_only_auto_update_assets_cbox)
        options_layout.addWidget(self.show_only_auto_update_assets_label)
        options_layout.addStretch(1)

        self.build_asset_tree()

        self.layout.addLayout(header)
        self.layout.addItem(QtWidgets.QSpacerItem(1, 20))
        self.layout.addLayout(options_layout)
        self.layout.addWidget(self.asset_tree)

    def set_slots(self):
        self.asset_tree.itemDoubleClicked.connect(self.get_notes)
        self.btn_save_config.clicked.connect(self.save_asset_update_config)
        self.btn_sync_cgt.clicked.connect(self.sync_assets_with_cgt)
        self.show_only_auto_update_assets_cbox.clicked.connect(self._set_asset_tree_display_mode)
        self.asset_mngr.finished_sync_and_download_signal.connect(self.sync_finished)

    def sync_finished(self, asset_component):
        """
        Runs when the cgt sync finishes. the asset manager class send the signal and name of the asset component that
        was sync'd. It compares the asset component to the name of the tab so other tabs don't get this signal.
        :param asset_component: user friendly name of the asset component
        """
        if str(asset_component) == self.name:
            self.msg_win.show_info_msg(
                "Sync Complete", "The selected assets were updated."
            )
            self.build_asset_tree()

    def sync_assets_with_cgt(self):
        """
        Syncs the selected assets in the ui with the data on CGT
        """
        # converts the tree selection to the format {asset type: [list of asset names]}
        assets_by_type = self._convert_tree_selection_to_assets_list_by_type(self.asset_tree.get_tree_checked())

        # paths in the cgt cloud to the files
        asset_info_list = list()

        # get asset info for selected assets, its a list of tuples (asset type, asset component, asset name, info as
        # dict()
        for asset_type in assets_by_type:
            for asset_name in assets_by_type[asset_type]:
                asset_info_list.append(
                    self.asset_mngr.get_asset_info_by_asset_name(asset_type, self.asset_component, asset_name)
                )
        # make a dict of format {asset type: {asset component(s): {asset name(s)}}, more asset types...}
        assets_dict = dict()

        for asset in asset_info_list:
            asset_type, asset_component, asset_name, _ = asset  
            if asset_type not in assets_dict:
                assets_dict[asset_type] = dict()
            if asset_component not in assets_dict[asset_type]:
                assets_dict[asset_type][asset_component] = list()
            assets_dict[asset_type][asset_component].append(asset_name)

        self.asset_mngr.sync_local_cache_with_server_and_download(update_data_dict=assets_dict)

    def save_asset_update_config(self):
        """
        Saves the selection to the asset update config file
        :return:
        """
        updated_config_data = dict()
        # converts the tree selection to the format {asset type: [list of asset names]}
        assets_by_type = self._convert_tree_selection_to_assets_list_by_type(self.asset_tree.get_tree_checked())

        for asset_type in assets_by_type:
            if asset_type not in updated_config_data:
                updated_config_data[asset_type] = dict()

            if self.asset_component not in updated_config_data[asset_type]:
                updated_config_data[asset_type][self.asset_component] = list()

            for asset_name in assets_by_type[asset_type]:
                updated_config_data[asset_type][self.asset_component].append(asset_name)

        error = self.asset_mngr.update_config_file_by_tool_type(self.asset_component, updated_config_data)
        if error:
            self.msg_win.show_error_msg(
                "Save Error",
                "Could not save asset update config file. Error is: {0}".format(error)
            )
        else:
            self.msg_win.show_info_msg("Saved", "The asset update config file was saved.")
        # finished saving, refresh ui
        self.build_asset_tree()

    def build_asset_tree(self):
        """
        Calls _build_tools_tree_data to get the tree data (i.e. rows of text). Calling this method with no exisitng
        tree creates a pyani.core.ui.CheckboxTreeWidget tree object. Calling this method on an existing tree
        rebuilds the tree data
        """
        # get data to build tree
        tree_data, col_count, existing_assets_in_config_file = self._build_asset_tree_data()

        # if the tree has already been built, clear it and call build method
        if self.asset_tree:
            self.asset_tree.clear_all_items()
            self.asset_tree.build_checkbox_tree(
                tree_data,
                expand=False,
                columns=col_count
            )
        # tree hasn't been built yet
        else:
            self.asset_tree = pyani.core.ui.CheckboxTreeWidget(
                tree_data,
                expand=False,
                columns=col_count
            )
        # check on the assets already listed in the config file
        self.asset_tree.set_checked(existing_assets_in_config_file)

    def get_notes(self, item):
        """
        Gets the notes from CGT for the selected asset - double click calls this
        """
        # only process if asset component supports notes
        if not self.asset_mngr.asset_component_supports_release_notes(self.asset_component):
            self.msg_win.show_info_msg("Notes Support", "{0} does not have notes.".format(self.name))
            pyani.core.ui.center(self.msg_win.msg_box)
            return

        # get the selection from the ui, always send column 0 because want the asset name
        selected_item = self.asset_tree.get_item_at_position(item, 0)
        item_parent = self.asset_tree.get_parent(item)
        selection = [item_parent, selected_item]
        # if an asset type was clicked on ignore
        if selected_item in self.app_vars.asset_types:
            return

        # reset the notes text area
        self.notes_display.clear()

        # get asset as {asset type: [asset names as list], ...} only one asset since we double click to get notes
        converted_asset_selection = self._convert_tree_selection_to_assets_list_by_type(selection)
        # get name out of the asset tuple i.e. ("type", [asset names])
        asset = converted_asset_selection.popitem()
        asset_type = asset[0]
        # the name is always in a list, and since we are only getting one asset, we can grab the first list element
        asset_name = asset[1][0]

        self.msg_win.show_msg("Getting Notes", "Retrieving notes from CGT...")
        pyani.core.ui.center(self.msg_win.msg_box)
        QtWidgets.QApplication.processEvents()

        # get the notes
        notes_text, error = self.asset_mngr.get_release_notes(asset_type, self.asset_component, asset_name)

        self.msg_win.close()

        # error getting notes
        if error:
            self.msg_win.show_error_msg(
                "Notes Error", "Couldn't retrieve notes for: {0}. Error(s) are {1}".format(asset_name, error)
            )
            return
        # no notes for asset
        elif not notes_text:
            self.msg_win.show_info_msg(
                "Notes Warning", "No notes exist for {0}.".format(asset_name)
            )
            return

        # open window with a text scroll area
        self.notes_window.setWindowTitle("{0} Release Notes".format(self.asset_component))

        notes_formatted = ""
        # if there is a note, format as html
        notes_formatted += "<span style='font-size:{0}pt; color: #ffffff;'>{1}</span>".format(
            self.font_size_notes_title,
            asset_name
        )
        notes_formatted += "<p><span style='font-size:{0}pt; color: #ffffff;'>{1}</span></p>".format(
            self.font_size_notes_text,
            notes_text.replace("\n", "<br>")
        )
        # add notes
        self.notes_display.insertHtml(notes_formatted)
        # show window and center where mouse is
        self.notes_window.show()
        pyani.core.ui.center(self.notes_window)

    def _build_asset_tree_data(self):
        """
        Builds data for a pyani.core.ui.CheckboxTreeWidget
        :return: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        """
        # assets in a tree widget
        # get the assets types that have this component
        asset_types = self.asset_mngr.get_asset_type_by_asset_component_name(self.asset_component)
        tree_items = []
        col_count = 1
        # existing assets being updated, stores a list of dicts, where dict is
        # {
        #   "parent": asset type,
        #   "item name": asset name
        #   }
        # This allows the ui to check on and color green the assets already listed in the config file
        existing_assets_updated_list = []

        # shot assets will only ever return shot as the asset type, so first list element always exists
        if asset_types[0] == "shot":
            asset_type = asset_types[0]
            assets_info = self.asset_mngr.get_asset_info_by_asset_component(asset_type, self.asset_component)

            asset_info_modified = dict()
            # loop through all seq/shot assets, asset info is currently a list of "seq###/shot###":asset info
            # but we want a list of seq and their shots that have the specified asset component (excludes shots
            # that don't have the asset component)
            for asset_name, asset_properties in assets_info.items():
                seq, shot = tuple(asset_name.split("/"))
                if seq not in asset_info_modified:
                    asset_info_modified[seq] = list()
                # make a "seq" = ["shot1", "shot2", ..., "shot n"]
                asset_info_modified[seq].append(shot)
            # now build a tree with seq as root and shots as children
            for seq in sorted(asset_info_modified):
                assets_list = list()
                for shot in sorted(asset_info_modified[seq]):
                    # check if this asset is in the asset update config, meaning it gets updated automatically
                    if self.asset_mngr.is_asset_in_asset_update_config(
                            asset_type, self.asset_component, "{0}/{1}".format(seq, shot)
                    ):
                        row_color = [pyani.core.ui.GREEN]
                        existing_assets_updated_list.append(
                            {
                                "parent": seq,
                                "item name": shot
                            }
                        )
                    else:
                        row_color = [pyani.core.ui.WHITE]
                    assets_list.append(pyani.core.ui.CheckboxTreeWidgetItem([shot], colors=row_color))

                item = {
                    'root': pyani.core.ui.CheckboxTreeWidgetItem([seq]),
                    'children': assets_list
                }
                tree_items.append(item)
        # show assets
        else:
            for asset_type in asset_types:
                assets_info = self.asset_mngr.get_asset_info_by_asset_component(asset_type, self.asset_component)
                assets_list = []
                # for all asset names, make a list of tree item objects that have asset name and optionally version
                for asset_name, asset_properties in sorted(assets_info.items()):
                    if self.app_vars.asset_types[asset_type][self.asset_component]['is versioned']:
                        row_text = [asset_name, asset_properties["version"]]
                        col_count = len(row_text)

                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.asset_mngr.is_asset_in_asset_update_config(
                                asset_type, self.asset_component, asset_name
                        ):
                            row_color = [pyani.core.ui.GREEN, pyani.core.ui.WHITE]
                            existing_assets_updated_list.append(
                                {
                                    "parent": asset_type,
                                    "item name": asset_name
                                }
                            )
                        else:
                            row_color = [pyani.core.ui.WHITE, pyani.core.ui.WHITE]

                        # if version si blank put n/a
                        if row_text[1] == "":
                            row_text[1] = "n/a"

                        # check if the version on disk is older than the cloud version
                        json_data = pyani.core.util.load_json(
                            os.path.join(asset_properties["local path"], self.app_vars.cgt_metadata_filename)
                        )
                        if isinstance(json_data, dict):
                            if not json_data["version"] == asset_properties["version"]:
                                row_text[1] = "{0} / ({1})".format(json_data["version"], asset_properties["version"])
                                # keep the first color, but replace white with red for version
                                row_color = [row_color[0], pyani.core.ui.RED.name()]

                    # asset is not versioned
                    else:
                        row_text = [asset_name]
                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.asset_mngr.is_asset_in_asset_update_config(
                                asset_type, self.asset_component, asset_name
                        ):
                            row_color = [pyani.core.ui.GREEN]
                            existing_assets_updated_list.append(
                                {
                                    "parent": asset_type,
                                    "item name": asset_name
                                }
                            )
                        else:
                            row_color = [pyani.core.ui.WHITE]

                    assets_list.append(pyani.core.ui.CheckboxTreeWidgetItem(row_text, colors=row_color))
                item = {
                    'root': pyani.core.ui.CheckboxTreeWidgetItem([asset_type]),
                    'children': assets_list
                }
                tree_items.append(item)

        return tree_items, col_count, existing_assets_updated_list

    def _convert_tree_selection_to_assets_list_by_type(self, selection):
        """
        converts a flat list of asset types and asset names to a dict structure with format:
        {
            asset type: [ asset names as list ],
            ...
        }
        Note the selection is in order [asset type1, asset name1, asset name2, asset type2, asset name1, ..,
        asset name N, ....]
        :param selection: a list of assets and asset types
        :return: a dict in the above format
        """
        assets_by_type = dict()
        current_asset_type = ""

        for selected in selection:
            # check if this is a shot asset - asset type will either be shot or Seq###
            if "seq" in selected.lower():
                seq = selected
                selected = "shot"

            # if this is an asset type and not asset name, create a key
            if selected.lower() in self.app_vars.asset_types:
                # create key if doesn't exist
                if selected.lower() not in assets_by_type:
                    assets_by_type[selected.lower()] = []
                    # save this so we can keep adding to it until we get to another asset type in the list
                    current_asset_type = selected
            # not an asset type so add to the current asset type
            else:
                if current_asset_type:
                    if current_asset_type == "shot":
                        assets_by_type[current_asset_type].append("{0}/{1}".format(seq, selected))
                    else:
                        assets_by_type[current_asset_type].append(selected)

        return assets_by_type

    def _set_asset_tree_display_mode(self):
        """Shows all assets or just assets in the asset update config file
        """
        if self.show_only_auto_update_assets_cbox.checkState():
            # get all checked assets - we want the ones selected in this session as well
            unchecked_assets = self.asset_tree.get_tree_unchecked()
            unchecked_assets_no_asset_types = [
                unchecked_asset for unchecked_asset in unchecked_assets \
                if unchecked_asset not in self.app_vars.asset_types
            ]
            self.asset_tree.hide_items(unchecked_assets_no_asset_types)
            self.asset_tree.expand_all()
        else:
            # show all shots
            self.asset_tree.show_items(None, show_all=True)
            self.asset_tree.collapse_all()


'''

--------------------------------------------------------------------------------------------------

'''




class ToolsTab(QtWidgets.QWidget):
    def __init__(self, name, tools_mngr, tab_desc=None, tool_category=None):
        super(ToolsTab, self).__init__()

        # variables for asset (non-ui)
        self.app_vars = pyani.core.appvars.AppVars()
        self._name = name
        self.tool_category = tool_category
        self.tools_mngr = tools_mngr

        # make a msg window class for communicating with user
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT
        self.font_size_notes_title = 14
        self.font_size_notes_text = 10

        # ui variables
        self.asset_tree = None
        self.tab_description = tab_desc
        self.btn_sync_cgt = pyani.core.ui.ImageButton(
            "images\sync_cache_off.png",
            "images\sync_cache_on.png",
            "images\sync_cache_on.png",
            size=(86, 86)
        )
        self.btn_wiki = pyani.core.ui.ImageButton(
            "images\\wiki_off.png",
            "images\\wiki_on.png",
            "images\\wiki_on.png",
            size=(86, 86)
        )
        self.show_only_auto_update_assets_label, self.show_only_auto_update_assets_cbox = pyani.core.ui.build_checkbox(
            "Show Only Assets that are Auto-Updated.",
            False,
            "Shows assets that are in the auto update config file. These are the green colored assets below."
        )

        # window to display notes
        self.notes_window = QtWidgets.QDialog(parent=self)
        self.notes_window.setMinimumSize(725, 500)
        layout = QtWidgets.QVBoxLayout()
        self.notes_display = QtWidgets.QTextEdit()
        self.notes_display.setReadOnly(True)
        layout.addWidget(self.notes_display)
        self.notes_window.setLayout(layout)

        self.tools_tree = None

        # this widgets layout
        self.layout = QtWidgets.QVBoxLayout()

        self.build_layout()
        self.set_slots()

    @property
    def name(self):
        """
        The tab name
        """
        return self._name

    def get_layout(self):
        """
        The main layout object
        """
        return self.layout

    def build_layout(self):
        header = QtWidgets.QHBoxLayout()

        # optional description
        desc = QtWidgets.QLabel(self.tab_description)
        desc.setWordWrap(True)
        desc.setMinimumWidth(700)
        header.addWidget(desc)
        header.addStretch(1)

        # buttons
        header.addWidget(self.btn_sync_cgt)
        header.addItem(QtWidgets.QSpacerItem(10, 0))
        header.addWidget(self.btn_wiki)

        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addStretch(1)

        self.build_tools_tree()

        self.layout.addLayout(header)
        self.layout.addItem(QtWidgets.QSpacerItem(1, 20))
        self.layout.addLayout(options_layout)
        self.layout.addWidget(self.tools_tree)

    def set_slots(self):
        self.tools_tree.itemDoubleClicked.connect(self.get_notes)
        self.btn_wiki.clicked.connect(self.open_confluence_page)
        self.btn_sync_cgt.clicked.connect(self.sync_tools_with_cgt)
        self.tools_mngr.finished_sync_and_download_signal.connect(self.sync_finished)

    def sync_finished(self, tool_category):
        """
        Runs when the cgt sync finishes. the asset manager class send the signal and name of the asset component that
        was sync'd. It compares the asset component to the name of the tab so other tabs don't get this signal.
        :param tool_category: name of the tool active_type such as Maya, user friendly name
        """
        if str(tool_category) == self.name:
            self.msg_win.show_info_msg(
                "Sync Complete", "The selected tools were updated successfully."
            )
            self.build_tools_tree()

    def sync_tools_with_cgt(self):
        """
        Syncs the selected tools in the ui with CGT. Updates metadata like version and downlaods the latest tools.
        """
        # converts the tree selection to the format {asset type: [list of asset names]}
        tools_by_type = self._convert_tree_selection_to_tools_list_by_type(self.tools_tree.get_tree_checked())

        # paths in the cgt cloud to the files
        tools_info_list = list()

        # get asset info for selected assets, its a list of tuples (asset type, asset component, asset name, info as
        # dict()
        for tool_type in tools_by_type:
            for tool_name in tools_by_type[tool_type]:
                tools_info_list.append(
                    self.tools_mngr.get_tool_info_by_tool_name(self.tool_category, tool_type, tool_name)
                )
        # make a dict of format {tool active_type: {tool type(s): {tool name(s)}}, more tool categories...}
        tools_dict = dict()

        for tool in tools_info_list:
            self.tool_category, tool_type, tool_name, _ = tool
            if self.tool_category not in tools_dict:
                tools_dict[self.tool_category] = dict()
            if tool_type not in tools_dict[self.tool_category]:
                tools_dict[self.tool_category][tool_type] = list()
            tools_dict[self.tool_category][tool_type].append(tool_name)

        self.tools_mngr.sync_local_cache_with_server_and_download(tools_dict)

    def open_confluence_page(self):
        """
        opens an html page in the web browser for help. Can open multiple pages. Displays error if page(s) can't
        be opened
        """

        try:
            selection = str(self.tools_tree.currentItem().text(0))
        except AttributeError:
            # no selection is made
            self.msg_win.show_warning_msg("Selection Error", "No tool selected. Please select a tool to view the"
                                                             " wiki page.")
            return

        # if selection isn't a tool type, then it is a tool name
        if selection not in self.tools_mngr.get_tool_types(self.tool_category):
            url = r"http://172.18.10.11:8090/display/KB/{0}".format(selection)
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
                self.msg_win.show_error_msg(
                    "Confluence Error",
                    "The {0} tool does not have a confluence page".format(selection)
                )

    def get_notes(self, tree_item_clicked):
        """
        Gets the notes from CGT for the selected asset - double click calls this. Note that this shows the notes
        for the latest version on cgt, not the local version
        :param tree_item_clicked: the tree widget text row that was clicked
        """
        tool_type, tool_name = self._get_tree_selection_clicked(tree_item_clicked)
        if not tool_name:
            return

        # only process if notes exist
        notes = self.tools_mngr.get_tool_release_notes(self.tool_category, tool_type, tool_name)
        if not notes:
            self.msg_win.show_info_msg("Notes Support", "{0} does not have release notes.".format(tool_name))
            pyani.core.ui.center(self.msg_win.msg_box)
            return

        # reset the notes text area
        self.notes_display.clear()

        # open window with a text scroll area
        self.notes_window.setWindowTitle("{0} Release Notes".format(tool_name))

        notes_formatted = ""
        # if there is a note, format as html
        notes_formatted += "<span style='font-size:{0}pt; color: #ffffff;'>{1}</span>".format(
            self.font_size_notes_title,
            tool_name
        )
        notes_formatted += "<p><span style='font-size:{0}pt; color: #ffffff;'>{1}</span></p>".format(
            self.font_size_notes_text,
            "<br>".join(notes)
        )
        # add notes
        self.notes_display.insertHtml(notes_formatted)
        # show window and center where mouse is
        self.notes_window.show()
        pyani.core.ui.center(self.notes_window)

    def build_tools_tree(self):
        """
        Calls _build_tools_tree_data to get the tree data (i.e. rows of text). Calling this method with no existing
        tree creates a pyani.core.ui.CheckboxTreeWidget tree object. Calling this method on an existing tree
        rebuilds the tree data
        """
        # get data to build tree
        tree_data, col_count = self._build_tools_tree_data()

        # if the tree has already been built, clear it and call build method
        if self.tools_tree:
            self.tools_tree.clear_all_items()
            self.tools_tree.build_checkbox_tree(
                tree_data,
                expand=True,
                columns=col_count,
                checked=True
            )
        # tree hasn't been built yet
        else:
            self.tools_tree = pyani.core.ui.CheckboxTreeWidget(
                tree_data,
                expand=True,
                columns=col_count,
                checked=True
            )

    def _build_tools_tree_data(self):
        """
        Builds data for a pyani.core.ui.CheckboxTreeWidget
        :return: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        """
        # tools in a tree widget
        tree_items = list()
        col_count = 1

        tool_category = self.tool_category

        for tool_type in sorted(self.tools_mngr.get_tool_types(tool_category)):
            # try to load cgt meta data for tool type which has version info for the local files, this is the
            # version on disk locally, could be different than cloud version
            local_cgt_metadata = pyani.core.util.load_json(
                os.path.join(
                    self.app_vars.tool_types[tool_category][tool_type]['local dir'],
                    self.app_vars.cgt_metadata_filename
                )
            )
            # if can't load set to None
            if not isinstance(local_cgt_metadata, dict):
                local_cgt_metadata = None

            tools_list = list()
            for tool_name in self.tools_mngr.get_tool_names(tool_category, tool_type):
                cgt_version = self.tools_mngr.get_tool_newest_version(tool_category, tool_type, tool_name)
                if cgt_version:
                    row_text = [tool_name, cgt_version]
                else:
                    row_text = [tool_name, "n/a"]
                row_color = [pyani.core.ui.WHITE, pyani.core.ui.WHITE]
                col_count = len(row_text)

                if local_cgt_metadata:
                    if tool_name in local_cgt_metadata:
                        local_version = local_cgt_metadata[tool_name][0]["version"]
                        if not local_version == cgt_version:
                            row_text[1] = "{0} / ({1})".format(local_version, cgt_version)
                            # keep the first color, but replace white with red for version
                            row_color = [row_color[0], pyani.core.ui.RED.name()]
                tools_list.append(pyani.core.ui.CheckboxTreeWidgetItem(row_text, colors=row_color))
            tree_items.append(
                {
                    'root': pyani.core.ui.CheckboxTreeWidgetItem([tool_type]),
                    'children': tools_list
                }
            )

        return tree_items, col_count

    def _get_tree_selection_clicked(self, tree_item_clicked):
        # get the selection from the ui, always send column 0 because want the tool name
        selected_item = self.tools_tree.get_item_at_position(tree_item_clicked, 0)
        # should be the tool type as long as a tool name was clicked
        item_parent = self.tools_tree.get_parent(tree_item_clicked)
        # if a tool type was clicked on ignore
        if selected_item in self.app_vars.tool_types[self.tool_category]:
            return None, None
        else:
            return item_parent, selected_item

    def _convert_tree_selection_to_tools_list_by_type(self, selection):
        """
        converts a flat list of tool types and tool names to a dict structure with format:
        {
            tool type: [ tool names as list ],
            ...
        }
        Note the selection is in order [tool type1, tool name1, tool name2, tool type2, tool name1, ..,
        tool name N, ....]
        :param selection: a list of tool names and tool types
        :return: a dict in the above format
        """
        tools_by_type = dict()
        current_tool_type = ""

        for selected in selection:
            # if this is a tool type and not tool name, create a key
            if selected.lower() in self.tools_mngr.get_tool_types(self.tool_category):
                # create key if doesn't exist
                if selected.lower() not in tools_by_type:
                    tools_by_type[selected.lower()] = []
                    # save this so we can keep adding to it until we get to another tool type in the list
                    current_tool_type = selected
            # not a tool type so add to the current tool type
            else:
                if current_tool_type:
                    tools_by_type[current_tool_type].append(selected)

        return tools_by_type


class AniAppMngrGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for app manager. Shows installed apps, versions, and updates if available.
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """
    def __init__(self, error_logging):
        self.log = []

        # build main window structure
        self.app_name = "PyAppMngr"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniAppMngrGui, self).__init__(
            "Py App Manager",
            "Resources\\pyappmngr_icon.ico",
            self.app_mngr,
            1100,
            900,
            error_logging
        )

        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # save the setup class for error logging to use later
        self.error_logging = error_logging

        # tabs class object
        self.tabs = pyani.core.ui.TabsWidget(tab_name="PyAniTools", tabs_can_close=False)

        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        error = self.asset_mngr.load_server_asset_info_cache()
        if error:
            self.msg_win.show_error_msg(
                "Error",
                "Error loading cgt asset cache. You can continue, however rigs, caches, and audio will not"
                "be available. The error reported is {0}".format(error)
            )
            self.rig_tab = None
            self.audio_tab = None
            self.gpu_cache_tab = None
            self.maya_tools_tab = None
            self.pyanitools_tools_tab = None
        else:
            desc = "<b>Auto Update:</b> Green assets are currently in the asset update configuration file and get " \
                   "updated daily. Select or de-select assets and click the 'save selection for auto-update button' " \
                   "to change what is updated automatically.<br><br><b>Manual Update:</b> Select the assets you want " \
                   "to update and click the 'sync selection with cgt' button." \
                   "<br><br><i>HINT: To update an asset manually without changing your auto-update file, just clear " \
                   "what is selected, select the assets to update, click the 'sync selection...' button, then " \
                   "close this app and don't click the 'save selection...' button."
            self.rig_tab = AssetComponentTab("Rigs", self.asset_mngr, asset_component="rig", tab_desc=desc)
            self.audio_tab = AssetComponentTab("Audio", self.asset_mngr, asset_component="audio")
            self.gpu_cache_tab = AssetComponentTab("GPU Cache", self.asset_mngr, asset_component="model/cache")
            self.maya_tools_tab = ToolsTab("Maya Tools", self.tools_mngr, tool_category="maya")
            self.pyanitools_tools_tab = ToolsTab("PyAni Tools", self.tools_mngr, tool_category="pyanitools")

        self.task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_update",
            os.path.join(self.app_mngr.tools_install_dir, "PyAniToolsUpdate.exe")
        )

        # app vars
        self.app_vars = pyani.core.appvars.AppVars()

        # download monitor - we create here, and set slot to receive signal. When receive signal we process. When
        # a plugin is ready to download pass this object to the maya plugins class object so it can set the cmd to
        # execute and start the process. Then the event loop for QT will run here and call the slot function to process
        # the output.
        self.download_monitor = pyani.core.ui.CGTDownloadMonitor()

        # path to json file containing list of py ani tool apps and maya plugins
        tools_list_json_path = self.app_vars.tools_list

        # INIT FOR PYANITOOLS
        # ---------------------------------------------------------------------
        # list of apps and app mngrs
        self.app_mngrs = self._create_app_mngrs(tools_list_json_path)
        # main ui elements for pyanitools - styling set in the create ui functions
        self.btn_update = QtWidgets.QPushButton("Update App")
        self.btn_install = QtWidgets.QPushButton("Install / Update App(s)")
        self.btn_launch = QtWidgets.QPushButton("Launch App(s)")
        self.btn_manual_update = QtWidgets.QPushButton("Update Core Data Only")
        self.btn_clean_install = QtWidgets.QPushButton("Re-Install Tools To Latest Version")
        self.auto_dl_label = QtWidgets.QLabel("")
        self.menu_toggle_auto_dl = QtWidgets.QComboBox()
        self.menu_toggle_auto_dl.addItem("-------")
        self.menu_toggle_auto_dl.addItem("Enabled")
        self.menu_toggle_auto_dl.addItem("Disabled")
        self.auto_dl_run_time_label = QtWidgets.QLabel("")
        self.auto_dl_hour = QtWidgets.QLineEdit("12")
        self.auto_dl_hour.setMaximumWidth(40)
        self.auto_dl_min = QtWidgets.QLineEdit("00")
        self.auto_dl_min.setMaximumWidth(40)
        self.auto_dl_am_pm = QtWidgets.QComboBox()
        self.auto_dl_am_pm.addItem("AM")
        self.auto_dl_am_pm.addItem("PM")
        self.btn_auto_dl_update_time = QtWidgets.QPushButton("Update Run Time")
        # tree app version information
        self.app_tree = pyani.core.ui.CheckboxTreeWidget(self._format_app_info(), 3)

        # INIT FOR MAYA PLUGINS
        # ---------------------------------------------------------------------
        # list of maya plugins
        self.maya_plugins = pyani.core.mayatoolsmngr_depr.AniMayaTools()
        self.maya_plugins.build_tool_data()
        # store the current plugin that was clicked - gets set in the get plugin from button pressed method
        self.active_plugin = None
        # progress bar widgets
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_label = QtWidgets.QLabel("Checking for downloads...")
        self.progress_bar.hide()
        self.progress_label.hide()

        self.create_layout()
        self.set_slots()

    def create_layout(self):

        self.main_layout.addWidget(self.tabs)

        pyanitools_layout = self.create_layout_pyanitools()
        self.tabs.update_tab(pyanitools_layout)

        maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
        self.tabs.add_tab("Maya Tools", layout=maya_plugins_layout)

        if self.rig_tab:
            self.tabs.add_tab(self.rig_tab.name, layout=self.rig_tab.get_layout())
        if self.audio_tab:
            self.tabs.add_tab(self.audio_tab.name, layout=self.audio_tab.get_layout())
        if self.gpu_cache_tab:
            self.tabs.add_tab(self.gpu_cache_tab.name, layout=self.gpu_cache_tab.get_layout())
        if self.maya_tools_tab:
            self.tabs.add_tab(self.maya_tools_tab.name, layout=self.maya_tools_tab.get_layout())
        if self.pyanitools_tools_tab:
            self.tabs.add_tab(self.pyanitools_tools_tab.name, layout=self.pyanitools_tools_tab.get_layout())

        self.add_layout_to_win()

    def create_layout_and_slots_maya_plugins(self):
        """
        Create the layout for the maya plugins. Lets user know if plugin not found or version not found via ui.
        :return: a pyqt layout object containing the maya plugins app management interface
        """
        maya_plugins_layout = QtWidgets.QVBoxLayout()

        header_layout = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Tools")
        header_label.setFont(self.titles)
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.progress_bar)
        header_layout.addWidget(self.progress_label)
        maya_plugins_layout.addLayout(header_layout)
        maya_plugins_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # make the buttons and labels for each plugin
        for row_index, plugin in enumerate(sorted(self.maya_plugins.maya_tool_data)):
            # common ui elements whether plugin exists locally or not
            #
            plugin_layout = QtWidgets.QGridLayout()
            # add name of plugin - this is the user friendly display name
            name_label = QtWidgets.QLabel(plugin)
            plugin_layout.addWidget(name_label, row_index, 0)
            # space between name and vers or missing plugin label
            plugin_layout.addItem(QtWidgets.QSpacerItem(50, 0), row_index, 1)

            # get version_data
            if self.maya_plugins.maya_tool_data[plugin]["version data"]:
                # first element is the latest version
                version = self.maya_plugins.get_version(plugin, version="latest")
            else:
                version = "N/A"
            vers_label = QtWidgets.QLabel(version)
            plugin_layout.addWidget(vers_label,  row_index, 2)

            # download plugin button
            maya_plugins_dl_btn = pyani.core.ui.ImageButton(
                "images\download_off.png",
                "images\download_on.png",
                "images\download_off.png",
                size=(32, 32)
            )

            # check if tool goes in sub folder, if it does then use that name, otherwis euse the display name
            if self.maya_plugins.maya_tool_data[plugin]["name"]:
                btn_name = self.maya_plugins.maya_tool_data[plugin]["name"]
            else:
                # remove spaces
                btn_name = plugin.replace(" ", "_")

            maya_plugins_dl_btn.setMaximumWidth(32)
            maya_plugins_dl_btn.setObjectName("dl_{0}".format(btn_name))
            maya_plugins_dl_btn.clicked.connect(self.maya_plugins_download)
            maya_plugins_dl_btn.setToolTip("Download the latest version of the plugin.")
            # space between vers and buttons
            plugin_layout.addItem(QtWidgets.QSpacerItem(100, 0), row_index, 3)
            plugin_layout.addWidget(maya_plugins_dl_btn,  row_index, 4)

            # find where its located, local or server
            loc = self.maya_plugins.get_tool_root_directory(plugin)

            # check for existence
            if not os.path.exists(os.path.join(loc, self.maya_plugins.maya_tool_data[plugin]["name"])):
                missing_label = QtWidgets.QLabel(
                    "<font color={0}>( Plugin missing )</font>".format(pyani.core.ui.RED.name())
                )
                plugin_layout.addWidget(missing_label,  row_index, 5)

            else:
                '''
                REMOVED : revert version functionality, uncomment to re-activate

                maya_plugins_vers_btn = pyani.core.ui.ImageButton(
                    "images\change_vers_off.png",
                    "images\change_vers_on.png",
                    "images\change_vers_off.png",
                    size=(24, 24)
                )
                maya_plugins_vers_btn.setObjectName("vers_{0}".format(btn_name)
                maya_plugins_vers_btn.clicked.connect(self.maya_plugins_change_version)
                maya_plugins_vers_btn.setToolTip("Revert to the Previous Version.")
                
                # put this down with the other buttons if re-activate
                plugin_layout.addWidget(maya_plugins_vers_btn)
                '''

                maya_plugins_notes_btn = pyani.core.ui.ImageButton(
                    "images\\release_notes_off.png",
                    "images\\release_notes_on.png",
                    "images\\release_notes_off.png",
                    size=(24, 24)
                )
                maya_plugins_notes_btn.setMaximumWidth(24)
                maya_plugins_notes_btn.setObjectName("notes_{0}".format(btn_name))
                maya_plugins_notes_btn.clicked.connect(self.maya_plugins_view_release_notes)
                maya_plugins_notes_btn.setToolTip("View the release notes for the current plugin version.")

                maya_plugins_confluence_btn = pyani.core.ui.ImageButton(
                    "images\\html_off.png",
                    "images\\html_on.png",
                    "images\\html_off.png",
                    size=(24, 24)
                )
                maya_plugins_confluence_btn.setMaximumWidth(24)
                maya_plugins_confluence_btn.setObjectName("confluence_{0}".format(btn_name))
                maya_plugins_confluence_btn.clicked.connect(self.maya_plugins_open_confluence_page)
                maya_plugins_confluence_btn.setToolTip("Open the plugin's confluence page in a web browser.")

                plugin_layout.addWidget(maya_plugins_notes_btn, row_index, 6)
                plugin_layout.addWidget(maya_plugins_confluence_btn, row_index, 7)
                plugin_layout.addItem(QtWidgets.QSpacerItem(300, 0), row_index, 8)

            maya_plugins_layout.addLayout(plugin_layout)
            # space between rows of plugins
            maya_plugins_layout.addItem(QtWidgets.QSpacerItem(0, 20))

        maya_plugins_layout.addStretch(1)

        return maya_plugins_layout

    def create_layout_pyanitools(self):
        """
        Create the layout for the pyanitools
        :return: a pyqt layout object containing the pyanitools app management interface
        """
        pyanitools_layout = QtWidgets.QVBoxLayout()

        # APP HEADER SETUP -----------------------------------
        # |    label    |   space    |     btn     |      btn       |     space    |
        g_layout_header = QtWidgets.QGridLayout()
        header_label = QtWidgets.QLabel("Applications")
        header_label.setFont(self.titles)
        g_layout_header.addWidget(header_label, 0, 0)
        g_layout_header.addItem(self.empty_space, 0, 1)
        self.btn_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_install.setMinimumSize(175, 30)
        g_layout_header.addWidget(self.btn_install, 0, 2)
        self.btn_launch.setMinimumSize(175, 30)
        self.btn_launch.setStyleSheet("background-color:{0};".format(pyani.core.ui.CYAN))
        g_layout_header.addWidget(self.btn_launch, 0, 3)
        g_layout_header.setColumnStretch(1, 2)
        pyanitools_layout.addLayout(g_layout_header)
        pyanitools_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # APPS TREE  -----------------------------------
        pyanitools_layout.addWidget(self.app_tree)

        pyanitools_layout.addItem(self.v_spacer)

        # MANUAL DOWNLOAD OPTIONS
        g_layout_options = QtWidgets.QGridLayout()
        options_label = QtWidgets.QLabel("Tools Update Options")
        options_label.setFont(self.titles)
        g_layout_options.addWidget(options_label, 0, 0)
        g_layout_options.addItem(self.empty_space, 0, 1)
        g_layout_options.addWidget(self.btn_manual_update, 0, 2)
        self.btn_manual_update.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_manual_update.setMinimumSize(175, 30)
        g_layout_options.addWidget(self.btn_clean_install, 0, 3)
        self.btn_clean_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GOLD))
        self.btn_clean_install.setMinimumSize(175, 30)
        g_layout_options.addItem(self.empty_space, 0, 4)
        g_layout_options.setColumnStretch(1, 2)
        pyanitools_layout.addLayout(g_layout_options)
        pyanitools_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # set initial state of auto download based reset whether
        state = self.task_scheduler.is_task_enabled()
        if not isinstance(state, bool):
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not get state of task {0}. You can continue but you will not be "
                "able to enable or disable the windows task. Error is {1}".format(self.task_scheduler.task_name, state)
            )
        if state:
            state_label = "Enabled"
        else:
            state_label = "Disabled"
        self.auto_dl_label.setText(
            "Auto-download of updates from server <i><font color='#7d8792'>"
            "(Currently: {0})</font></i>".format(state_label)
        )
        h_options_layout = QtWidgets.QHBoxLayout()
        h_options_layout.addWidget(self.auto_dl_label)
        h_options_layout.addWidget(self.menu_toggle_auto_dl)
        h_options_layout.addStretch(1)
        pyanitools_layout.addLayout(h_options_layout)
        h_options_change_time_layout = QtWidgets.QHBoxLayout()

        # get the run time and format as hour:seconds am or pm, ex: 02:00 PM
        run_time = self.task_scheduler.get_task_time()
        if isinstance(run_time, datetime.datetime):
            run_time = run_time.strftime("%I:%M %p")
        else:
            run_time = "N/A"
        self.auto_dl_run_time_label.setText("Change Update Time <i><font color='#7d8792'>"
                                            "(Current Update Time: {0})</font></i>".format(run_time))
        h_options_change_time_layout.addWidget(self.auto_dl_run_time_label)
        h_options_change_time_layout.addWidget(self.auto_dl_hour)
        h_options_change_time_layout.addWidget(self.auto_dl_min)
        h_options_change_time_layout.addWidget(self.auto_dl_am_pm)
        h_options_change_time_layout.addWidget(self.btn_auto_dl_update_time)
        h_options_change_time_layout.addStretch(1)
        pyanitools_layout.addLayout(h_options_change_time_layout)
        pyanitools_layout.addItem(self.v_spacer)

        return pyanitools_layout

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_install.clicked.connect(self.install_apps)
        self.btn_launch.clicked.connect(self.launch)
        self.menu_toggle_auto_dl.currentIndexChanged.connect(self.update_auto_dl_state)
        self.btn_manual_update.clicked.connect(self.update_core_files)
        self.btn_clean_install.clicked.connect(self.reinstall)
        self.btn_auto_dl_update_time.clicked.connect(self.update_auto_dl_time)
        self.download_monitor.data_downloaded.connect(self.progress_received)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tools_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.asset_mngr.error_thread_signal.connect(self.show_multithreaded_error)

    def show_multithreaded_error(self, error):
        self.msg_win.show_error_msg("Error", error)

    def tab_changed(self):
        # get a list of asset components and if tab is an asset component page set the active component in
        # the asset manager
        if self.tabs.currentWidget().name in self.asset_mngr.get_asset_component_names():
            self.asset_mngr.active_asset_component = self.tabs.currentWidget().name
        # get a list of tool categories and if tab is a tool active_type page set the active active_type in
        # the tool manager - note that unlike assets, we don't have a user friendly name, so we use lower
        if self.tabs.currentWidget().name in self.tools_mngr.get_tool_categories(display_name=True):
            self.tools_mngr.active_type = self.tabs.currentWidget().name

    def progress_received(self, data):
        """
        Gets progress from CGTDownloadMonitor class via slot/signals
        :param data: a string or int
        """
        # check for string message or download progress (int)
        if isinstance(data, basestring):
            # get the total number of files being downloaded - only get this data if downloading multiple files
            if "file_total" in data:
                self.progress_label.setText("Downloading {0} files.".format(data.split(":")[1]))
            # get the total file size of the download - only get this data if downloading one file
            elif "file_size" in data:
                self.progress_label.setText("Downloading {0}.".format(data.split(":")[1]))
            # check if we are done downloading and reset/refresh gui
            elif "done" in data or "no_updates" in data:
                self.progress_label.hide()
                self.progress_bar.hide()
                self.progress_bar.setValue(0)
                # a successful download
                if "done" in data:
                    # show where plugin downloaded
                    self.msg_win.show_info_msg(
                        "Download Complete", "Plugin: {0} is up to date. Location is {1}".format(
                            self.active_plugin,
                            self.maya_plugins.get_tool_full_path(self.active_plugin)
                        )
                    )
                    # refresh version info
                    error = self.maya_plugins.build_tool_data()
                    # return error if couldn't refresh data
                    if error:
                        self.msg_win.show_error_msg("Plugin Error", error)

                    # refresh version info in gui, a bit overkill to rebuild ui, but lightweight enough doesn't matter
                    # and don't need to keep track of each plugins ui elements to update
                    maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
                    self.tabs.update_tab(maya_plugins_layout)
                # at the latest
                else:
                    # let user know there aren't any updates
                    self.msg_win.show_info_msg(
                        "Download Complete", "There are no updates for the {0}. You have the latest. ".format(
                            self.active_plugin
                        )
                    )
        else:
            # update progress
            self.progress_bar.setValue(data)

    def maya_plugins_download(self):
        """
        Downloads the plugin based off the button pressed
        """
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)

        if plugin:
            # download from CGT
            self.progress_bar.show()
            self.progress_label.show()
            self.maya_plugins.download_tools(plugin, self.download_monitor)
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to download".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def maya_plugins_change_version(self):
        """
        changes to a previous version. currently just support rolling back to the previous version. if previous version
        not found returns returns without doing any actions. Also returns without action if user declines the change.
        If the files can't be removed, or restored also returns but displays message to user.
        """
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            if not self.maya_plugins.restore_path_exists(plugin):
                self.msg_win.show_error_msg(
                    "Critical Error", "No restore point found for {0}.".format(plugin)
                )
                return
            release_notes = self.maya_plugins.get_release_notes(plugin, version="1")
            version = self.maya_plugins.get_version(plugin, version="1")
            response = self.msg_win.show_question_msg(
                "Version Change", "You are about to change versions to {0}. The release notes are: <br><br>{1}"
                                  "<br>Click yes to continue."
                                  .format(version, release_notes)
            )
            if response:
                error = self.maya_plugins.change_version(plugin)
                if error:
                    self.msg_win.show_error_msg(
                        "Critical Error", "Could not revert plugin to version {0}. Plugin may not function. Please "
                                          "re-download the latest version. Error is: {1}".format(version, error)
                    )
                    return
                # refresh version info in gui, a bit overkill to rebuild ui, but lightweight enough doesn't matter
                # and don't need to keep track of each plugins ui elements to update
                maya_plugins_layout = self.create_layout_and_slots_maya_plugins()
                self.tabs.update_tab(maya_plugins_layout)
            # user canceled version change
            else:
                return
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to change version".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def get_maya_plugin_from_button_press(self, btn_pressed, display_name=True):
        """
        gets the plugin based off the button pressed
        :param btn_pressed: the name of the button set via setObjectName when created
        :param display_name: use the display name (user friendly - no camel case or underscores)of the plugin
        if True, otherwise use the file name (camel case, underscores)
        :return: the name of the plugin for that button, or None if can't be found
        """
        # find which plugin to revert
        for plugin in self.maya_plugins.maya_tool_data:
            # find the plugin clicked
            if self.maya_plugins.maya_tool_data[plugin]["name"] in btn_pressed:
                self.active_plugin = plugin
                if display_name:
                    return plugin
                else:
                    return self.maya_plugins.maya_tool_data[plugin]["name"]
        return None

    def maya_plugins_view_release_notes(self):
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed)
        if plugin:
            release_notes = self.maya_plugins.get_release_notes(plugin)
            # show release notes for prior version
            self.msg_win.show_info_msg(
                "Version Notes", "<b>Release Notes:</b><br><br> {0}".format(release_notes)
            )
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to view release notes".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def maya_plugins_open_confluence_page(self):
        # get the buttons' name
        btn_pressed = self.sender().objectName()
        # find which plugin to revert
        plugin = self.get_maya_plugin_from_button_press(btn_pressed, display_name=False)
        if plugin:
            self.maya_plugins.open_confluence_page(plugin)
        # couldn't find plugin
        else:
            logger.error("Could not find plugin for button {0} to open confluence page".format(btn_pressed))
            self.msg_win.show_error_msg("Critical Error", "Could not find plugin, see log for details")

    def update_auto_dl_state(self):
        """
        Updates a windows task in the windows task scheduler to be enabled or disabled. Informs user if can't
        set the task state
        """
        if not self.menu_toggle_auto_dl.currentIndex() == 0:
            state = self.menu_toggle_auto_dl.currentText()
            if state == "Enabled":
                error = self.task_scheduler.set_task_enabled(True)
            else:
                error = self.task_scheduler.set_task_enabled(False)
            if error:
                self.msg_win.show_warning_msg(
                    "Task Scheduling Error",
                    "Could not set state of task {0}. You can continue but you will not be "
                    "able to enable or disable the windows task. Error is {1}".format(self.task_scheduler.task_name,
                                                                                      state)
                )
                self.auto_dl_label.setText(
                    "Auto-download of updates from server <i>(Currently: Unknown)</i>"
                )
            else:
                self.auto_dl_label.setText(
                    "Auto-download of updates from server <i>(Currently: {0})</i>".format(state)
                )

    def update_auto_dl_time(self):
        """
        Update the run time for the auto updates
        """
        try:
            # get hour an minute from input
            hour = str(self.auto_dl_hour.text())
            min = str(self.auto_dl_min.text())
            time_of_day = str(self.auto_dl_am_pm.currentText())
            run_time = ("{0}:{1}".format(hour, min))
            # validate input - if doesn't work throws ValueError
            datetime.datetime.strptime(run_time, "%H:%M")
            # add am or pm
            run_time += " {0}".format(time_of_day)
            # convert to 24 hours
            military_time = datetime.datetime.strptime(run_time, "%I:%M %p").strftime("%H:%M")
            # set new run time
            error = self.task_scheduler.set_task_time(military_time)
            if error:
                self.msg_win.show_warning_msg(
                    "Task Scheduling Error",
                    "Could not set run time. Error is {0}".format(error)
                )

            # update time in ui
            # get the run time and format as hour:seconds am or pm, ex: 02:00 PM
            run_time = self.task_scheduler.get_task_time()
            if isinstance(run_time, datetime.datetime):
                run_time = run_time.strftime("%I:%M %p")
            else:
                run_time = "N/A"
            self.auto_dl_run_time_label.setText("Change Update Time <i><font color='#7d8792'>"
                                                "(Current Update Time: {0})</font></i>".format(run_time))
        except ValueError:
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not set run time. {0} is not a valid time".format(run_time)
            )

    def reinstall(self):
        """
        Removes the existing PyAniTools installation - shortcuts, nuke modifications, and main tools dir. Then
        downloads the tools from the CG Teamworks, and re-installs. Uses the Install Update Assistant
        (PyAniToolsIUAssist.exe) to launch PyAniToolsSetup.exe and close this app so it can get re=installed.
        See toolsinstallassist_depr.py in pyani package for more details
        """

        # let user know windows will open and to close all existing tools, display process, and ask if they want
        # to continue
        response = self.msg_win.show_question_msg(
            "Continue Re-install Prompt",
            "<i>WARNING: This removes all existing tools and re-installs with the latest version.</i><br><br>"
            "<b>Please close any PyAniTool Apps besides this one and any Windows Explorer "
            "windows that show folders/files from C:\PyAniTools (a windows resource bug)</b><br><br> "
            "The re-installation will error if: <br><br>"
            "(a) any tools are running.<br>"
            "(b) windows explorer is showing files/folders from any folder in C:\PyAniTools. This includes "
            "the shortcuts window.<br><br>"
            "<b>Re-installation Process</b>:<br> "
            "A new window will open, and the app manager will close. The new window stages files for installation and "
            "opens the tool setup app. Once the tool setup finishes, hit close and the app manager will re-open."
        )
        # if the user selected 'yes' (True), proceed
        if response:
            # remove temp dir if exists
            if os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.rm_dir(self.app_vars.download_path_pyanitools)
                if error:
                    self.msg_win.show_error_msg("Install Staging Error", error)
                    return

            # setup directories that need to be removed, exe files to run, stage files in temp dir
            #
            # this is the exe (absolute path) to execute the setup tool in the iu assistant
            app_to_run = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.setup_exe)
            # exe (absolute path) calling assistant
            calling_app = self.app_vars.app_mngr_exe
            # path in temp dir of the assistant
            iu_assistant_app_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.iu_assist_exe)
            # path of the assistant in tools dir
            iu_assistant_app_in_tools = self.app_vars.iu_assist_path
            # what to remove
            files_and_dirs_to_remove = [
                self.app_vars.tools_dir,
                self.app_vars.pyanitools_desktop_shortcut_path,
                self.app_mngr.ani_vars.nuke_user_dir
            ]

            # download latest from cgt - will unzip to temp dir
            #
            self.progress_win.show_msg("Install in Progress", "Downloading Updates from Server. This file is several "
                                       "hundred megabytes (mb), please be patient.")
            QtWidgets.QApplication.processEvents()
            error = self.app_mngr.download_update(skip_update_check=True)
            # done loading hide window
            self.progress_win.hide()
            # not true or false, so an error occurred
            if not isinstance(error, bool):
                QtWidgets.QApplication.processEvents()
                self.msg_win.show_error_msg("Update Failed", "Could not download update. Error is :{0}.".format(error))
                return

            # copy assistant program to temp - can't run it out of C:PyAniTools since that will get removed
            if not os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.make_dir(self.app_vars.download_path_pyanitools)
                if error:
                    msg_append = "Problem staging install file. " + error
                    self.msg_win.show_error_msg("Install Staging Error", msg_append)
                    return
            error = pyani.core.util.copy_file(iu_assistant_app_in_tools, self.app_vars.download_path_pyanitools)
            if error:
                msg_append = "Problem staging install file. " + error
                self.msg_win.show_error_msg("Install Staging Error", msg_append)
                return

            # open assistant passing:
            #       path to assistant in temp dir,
            #       assist type - update core or re-install
            #       the calling app,
            #       app to run,
            #       the directories/files to remove
            #
            # assist type - update or re-install
            args = ["reinstall"]
            # the exe calling this app
            args.append(calling_app)
            # app to run - tools setup
            args.append(app_to_run)
            # files and directories to remove - a list so extend current list
            args.extend(files_and_dirs_to_remove)
            # launch assistant with the parameters
            error = pyani.core.util.launch_app(iu_assistant_app_in_temp, args, open_as_new_process=True)
            if error:
                self.msg_win.show_error_msg("Install Error", error)

    def update_core_files(self):
        """
        Update the existing PyAniTools core app files - the lib files used by nuke and cgt bridge, app packages,
        app data, Install Update assistant (PyAniToolsIUAssist.exe ) and Tools Updater (PyAniToolsUpdate.exe),
        and app manager.

        Uses the Install Update Assistant(PyAniToolsIUAssist.exe) to launch PyAniToolsUpdate.exe, which downloads the
        latest tools from the server, runs the update, then returns here. See toolsinstallassist_depr.py in pyani package
        for more details
        """
        # let user know windows will open and to close all existing tools, display process, and ask if they want
        # to continue
        response = self.msg_win.show_question_msg(
            "Continue Update Prompt",
            "<i>This will not update the apps, only the core tool data. It will get the latest app packages and you"
            "can update using app manager once this completes.</i><br><br>"
            "<b>Please close any PyAniTool Apps besides this one and any Windows Explorer "
            "windows that show folders/files from C:\PyAniTools (a windows resource bug)</b><br><br> "
            "The update will error if: <br><br>"
            "(a) any tools are running.<br>"
            "(b) windows explorer is showing files/folders from any folder in C:\PyAniTools. This includes "
            "the shortcuts window.<br><br>"
            "<b>Update Process</b>:<br> "
            "A new window will open, and the app manager will close. The new window stages files for update and "
            "opens the tool update app. Once the tool update finishes, hit close and the app manager will re-open."
        )
        # if user pressed 'yes' (True) then proceed
        if response:
            # remove temp dir if exists
            if os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.rm_dir(self.app_vars.download_path_pyanitools)
                if error:
                    self.msg_win.show_error_msg("Update Staging Error", error)
                    return

            # setup directories that need to be removed, exe files to run, stage files in temp dir
            #
            # exe (absolute path) calling assistant
            calling_app = self.app_vars.app_mngr_exe

            # copy install / update assist tool
            #
            # copy assistant program to temp - can't run it out of C:PyAniTools since that will get removed
            if not os.path.exists(self.app_vars.download_path_pyanitools):
                error = pyani.core.util.make_dir(self.app_vars.download_path_pyanitools)
                if error:
                    msg_append = "Problem staging update file. " + error
                    self.msg_win.show_error_msg("Update Staging Error", msg_append)
                    return

            # path in temp dir of the assistant
            iu_assistant_app_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.iu_assist_exe)
            # path of the assistant in tools dir
            iu_assistant_app_in_tools = self.app_vars.iu_assist_path
            error = pyani.core.util.move_file(iu_assistant_app_in_tools, self.app_vars.download_path_pyanitools)
            if error:
                msg_append = "Problem staging update file. " + error
                self.msg_win.show_error_msg("Update Staging Error", msg_append)
                return

            # copy update tool
            #
            # path in temp dir of the tool
            update_tool_in_temp = os.path.join(self.app_vars.download_path_pyanitools, self.app_vars.update_exe)
            # path of the tool in tools dir
            update_tool_in_tools = os.path.join(self.app_vars.apps_dir, self.app_vars.update_exe)
            error = pyani.core.util.move_file(update_tool_in_tools, update_tool_in_temp)
            if error:
                msg_append = "Problem staging update file. " + error
                self.msg_win.show_error_msg("Update Staging Error", msg_append)
                return

            app_to_run = update_tool_in_temp

            # open assistant passing:
            #       path to assistant in temp dir,
            #       assist type - update core or re-install
            #       the calling app,
            #       app to run,
            #       the directories/files to remove
            #
            # assist type - update or re-install
            args = ["update"]
            # the exe calling this app
            args.append(calling_app)
            # app to run - tools setup
            args.append(app_to_run)
            # files and directories to remove - a list so extend current list
            args.extend([])
            # launch assistant with the parameters
            error = pyani.core.util.launch_app(iu_assistant_app_in_temp, args, open_as_new_process=True)
            if error:
                self.msg_win.show_error_msg("Update Staging Error", error)

    def install_apps(self):
        """Installs the app(s) and updates ui info. Displays install_apps errors to user.
        """
        apps = self._get_selection()
        error_log = []
        # try to install_apps selected apps, log and display error if can't and skip to next app
        for index, app in enumerate(apps):
            error = app.install()
            if error:
                error_log.append(error)
                continue
            item = [app.app_name, app.user_version, ""]
            item_color = [None, None, None]
            updated_item = pyani.core.ui.CheckboxTreeWidgetItem(item, item_color)
            self.app_tree.update_item(app.app_name, updated_item)

        if error_log:
            self.msg_win.show_error_msg("Install Error", (', '.join(error_log)))

    def launch(self):
        """Launches the app(s). Displays launch error to user
        """
        apps = self._get_selection()
        error_log = []
        for app in apps:
            # set directory, so that app runs from where the exe is, in case it uses relative paths to find resources
            os.chdir(app.app_install_path)
            exe_path = os.path.join(app.app_install_path, app.app_name)
            # pass application path and arguments, in this case none
            error = pyani.core.util.launch_app("{0}.exe".format(exe_path), [])
            if error:
                error_log.append(error)
                continue
        if error_log:
            self.msg_win.show_error_msg("App Launch Error", (', '.join(error_log)))

    def _create_app_mngrs(self, tools_list_json_path):
        """
        Creates the app managers for all py ani tool apps and makes a list of the app names
        :param: the path to the json file that contains the lists of pyanitool apps
        :return: a list of the app names, and a list of the app mngrs
        """
        # list of apps
        app_names = pyani.core.util.load_json(tools_list_json_path)["pyanitools"]
        # list of app managers for each app
        app_mngrs = []
        if not isinstance(app_names, list):
            error = "Critical error loading list of applications from {0}".format(tools_list_json_path)
            logger.error(error)
            self.msg_win.show_error_msg("Critical Error", error)
        else:
            for name in app_names:
                app_mngr = AniAppMngr(name)
                if app_mngr.log:
                    self.msg_win.show_warning_msg(
                        "Warning",
                        "Could not correctly load data for {0}. This application will not be available to update"
                        "until the error is resolved. Error is {1}".format(name, ", ".join(app_mngr.log))
                    )
                else:
                    app_mngrs.append(AniAppMngr(name))
        return app_mngrs

    def _get_selection(self):
        """
        Gets and parses the selected apps in the tree
        :return: a list of the selected tree items as AniMetadataToolMngr objects
        """
        selection = self.app_tree.get_tree_checked()
        apps = []
        # using selection, finds the app in app_mngr and adds to list
        for app_name in selection:
            for app_mngr in self.app_mngrs:
                if app_name == app_mngr.app_name:
                    apps.append(app_mngr)
        return apps

    def _format_app_info(self):
        """
        formats app information for the ui
        :return: a list of the tree information as a list of CheckboxTreeWidgetItems
        """
        tree_info = []

        if self.app_mngrs:
            # display app names, versions, and release notes if a new version is available
            for app in self.app_mngrs:
                # if users version is out of date color orange
                if not app.user_version == app.latest_version:
                    version_text = "{0}     ({1})".format(app.user_version, app.latest_version)
                    text = [app.app_name, version_text, app.features]
                    color = [pyani.core.ui.YELLOW, pyani.core.ui.YELLOW, QtCore.Qt.gray]
                    row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
                    tree_info.append({"root": row})
                # app up to date
                else:
                    text = [app.app_name, app.user_version]
                    color = None
                    row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
                    tree_info.append({"root": row})
        # problems loading app information
        else:
            text = [
                "Could not find application data. Please see log in {0}".format(self.error_logging.log_file_name), ""
            ]
            color = [pyani.core.ui.RED, pyani.core.ui.RED]
            row = pyani.core.ui.CheckboxTreeWidgetItem(text, color)
            tree_info.append({"root": row})

        return tree_info
