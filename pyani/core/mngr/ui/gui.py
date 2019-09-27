import os
import sys
import datetime
import pyani.core.util
import logging
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.mngr.assets
import pyani.core.mngr.tools


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets

logger = logging.getLogger()


class AssetComponentTab(QtWidgets.QWidget):
    def __init__(self, name, asset_mngr, tab_desc=None, asset_component=None):
        super(AssetComponentTab, self).__init__()

        # variables for asset (non-ui)
        self.app_vars = pyani.core.appvars.AppVars()
        self.asset_mngr = asset_mngr
        self._name = name
        self.assets_with_versions = ["rig"]
        self.assets_supporting_update_tracking = ["audio"]
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
        self.btn_tracking = pyani.core.ui.ImageButton(
            "images\\tracking_off.png",
            "images\\tracking_on.png",
            "images\\tracking_on.png",
            size=(86, 86)
        )
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
        self.track_asset_changes_label, self.track_asset_changes_cbox = pyani.core.ui.build_checkbox(
            "Generate daily report for asset updates.",
            False,
            "Tracks updates to assets. Generates an excel report of any changed assets for the show."
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
        # add asset changes tracking button if this component supports it
        if self.name.lower() in self.assets_supporting_update_tracking:
            header.addItem(QtWidgets.QSpacerItem(10, 0))
            header.addWidget(self.btn_tracking)

        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(self.show_only_auto_update_assets_cbox)
        options_layout.addWidget(self.show_only_auto_update_assets_label)
        # add asset changes tracking option if this component supports it
        if self.name.lower() in self.assets_supporting_update_tracking:
            options_layout.addItem(QtWidgets.QSpacerItem(40, 0))
            options_layout.addWidget(self.track_asset_changes_cbox)
            options_layout.addWidget(self.track_asset_changes_label)
            pref = self.asset_mngr.get_preference("asset mngr", "audio", "track updates")
            if isinstance(pref, dict):
                self.track_asset_changes_cbox.setChecked(pref.get("track updates"))

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
        self.btn_tracking.clicked.connect(self.generate_tracking_report)
        self.show_only_auto_update_assets_cbox.clicked.connect(self._set_tree_display_mode)
        self.asset_mngr.finished_sync_and_download_signal.connect(self.sync_finished)
        self.asset_mngr.finished_tracking.connect(self.tracking_finished)
        self.track_asset_changes_cbox.clicked.connect(self.update_tracking_preferences)

    def sync_finished(self, asset_component):
        """
        Runs when the cgt sync finishes. the asset manager class send the signal and name of the asset component that
        was sync'd. It compares the asset component to the name of the tab so other tabs don't get this signal.
        :param asset_component: user friendly name of the asset component
        """
        if str(asset_component).lower() == self.name.lower():
            self.msg_win.show_info_msg(
                "Sync Complete", "The selected assets were updated."
            )
            self.build_asset_tree()

    def tracking_finished(self, tracking_info):
        asset_component = str(tracking_info[0])
        filename = str(tracking_info[1])
        if asset_component.lower() == self.name.lower():
            pyani.core.util.open_excel(filename)
            self.msg_win.show_info_msg(
                "Tracking Complete", "Report saved to {0} and should open automatically.".format(
                    self.app_vars.persistent_data_path
                )
            )

    def generate_tracking_report(self):
        self.asset_mngr.check_for_new_assets(self.name.lower())

    def update_tracking_preferences(self):
        """
        Updates tracking asset preference for this asset component. Displays error if can't update, or success msg
        if successfully updated.
        """
        # get the preference name and value as a dict
        pref = self.asset_mngr.get_preference("asset mngr", self.name.lower(), "track updates")
        # check if we have a valid preference
        if not isinstance(pref, dict):
            self.msg_win.show_error_msg("Preferences Error", "Could not get preference, error is: {0}".format(pref))
            return

        pref_name = pref.keys()[0]

        if self.track_asset_changes_cbox.isChecked():
            pref_value = True
        else:
            pref_value = False
        error = self.asset_mngr.save_preference("asset mngr", self.name.lower(), pref_name, pref_value)
        if error:
            self.msg_win.show_error_msg(
                "Preferences Error", "Could not save preference, error is: {0}".format(error)
            )
            return
        else:
            self.msg_win.show_info_msg(
                "Preferences Saved", "The preference, {0}, was successfully update to {1}".format(
                    pref_name,
                    pref_value
                )
            )

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

        self.asset_mngr.sync_local_cache_with_server_and_download_gui(update_data_dict=assets_dict)

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

        error = self.asset_mngr.update_config_file_by_component_name(self.asset_component, updated_config_data)
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
        # the name is always in a list, and since we are only getting one asset, we can grab the first list element
        asset_name = asset[1][0]

        self.msg_win.show_msg("Getting Notes", "Retrieving notes from CGT...")
        pyani.core.ui.center(self.msg_win.msg_box)
        QtWidgets.QApplication.processEvents()

        # get the notes
        notes_text, error = self.asset_mngr.get_release_notes(self.asset_component, asset_name)

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
        # if there is a note, format
        notes_formatted += "<span style='font-size:{0}pt; color: #ffffff;'>{1}</span>".format(
            self.font_size_notes_title,
            asset_name
        )
        notes_formatted += "<p><span style='font-size:{0}pt; color: #ffffff;'>{1}</span></p>".format(
            self.font_size_notes_text,
            notes_text
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
                    if self.asset_mngr.is_asset_in_update_config(
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
                        # will be 3 since version assets have approved and work folders and we have a column for that
                        # after version
                        col_count = 3

                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.asset_mngr.is_asset_in_update_config(
                                asset_type, self.asset_component, asset_name
                        ):
                            # check if file doesn't exist on server - this let's user know so they don't wonder why
                            # update isn't getting any files
                            if not asset_properties['file name']:
                                # found missing file on server, set to strikeout - see pyani.core.ui.CheckboxTreeWidget
                                # for available formatting options
                                row_text[0] = "strikethrough:{0}".format(row_text[0])
                                row_color = [pyani.core.ui.DARK_GREEN, pyani.core.ui.WHITE]
                            else:
                                row_color = [pyani.core.ui.GREEN, pyani.core.ui.WHITE]

                            existing_assets_updated_list.append(
                                {
                                    "parent": asset_type,
                                    "item name": asset_name
                                }
                            )
                        else:
                            row_color = [pyani.core.ui.WHITE, pyani.core.ui.WHITE]
                            # check if file doesn't exist on server - this let's user know so they don't wonder why
                            # update isn't getting any files
                            if not asset_properties['file name']:
                                # found missing file on server, set to strikeout - see pyani.core.ui.CheckboxTreeWidget
                                # for available formatting options
                                row_text[0] = "strikethrough:{0}".format(row_text[0])
                                row_color[0] = pyani.core.ui.GRAY_MED

                        # if version is blank put n/a
                        if row_text[1] == "":
                            row_text[1] = "n/a"

                        # check if the version on disk is older than the cloud version - will only exist and be
                        # accurate if asset is in update config file. If file was added then removed, can't guarantee
                        # version information, may have updated the asset via cgt interface.
                        if self.asset_mngr.is_asset_in_update_config(
                                asset_type, self.asset_component, asset_name
                        ):
                            json_data = pyani.core.util.load_json(
                                os.path.join(asset_properties["local path"], self.app_vars.cgt_metadata_filename)
                            )
                        else:
                            json_data = None

                        if isinstance(json_data, dict):
                            if not json_data["version"] == asset_properties["version"]:
                                row_text[1] = "{0} / ({1})".format(json_data["version"], asset_properties["version"])
                                # keep the first color, but replace white with red for version
                                row_color = [row_color[0], pyani.core.ui.RED.name()]

                        # check if asset is publishable
                        if not self.asset_mngr.is_asset_approved(asset_type, self.asset_component, asset_name):
                            row_text.append("images\\not_approved.png")
                            row_color.append("")

                    # asset is not versioned
                    else:
                        row_text = [asset_name]
                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.asset_mngr.is_asset_in_update_config(
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

    def _set_tree_display_mode(self):
        """Shows all assets or just assets in the update config file
        """
        if self.show_only_auto_update_assets_cbox.checkState():
            # get all checked assets - we want the ones selected in this session as well
            unchecked_assets = self.asset_tree.get_tree_unchecked()

            '''
            seems to do nothing:
            unchecked_assets_no_asset_types = [
                unchecked_asset for unchecked_asset in unchecked_assets \
                if unchecked_asset not in self.app_vars.asset_types
            ]
            '''

            self.asset_tree.hide_items(unchecked_assets)
            self.asset_tree.expand_all()
        else:
            # show all items
            self.asset_tree.show_items(None, show_all=True)
            self.asset_tree.collapse_all()


class ToolsTab(QtWidgets.QWidget):
    def __init__(self, name, tools_mngr, tab_desc=None, tool_type=None):
        super(ToolsTab, self).__init__()

        # variables for asset (non-ui)
        self.app_vars = pyani.core.appvars.AppVars()
        self._name = name
        self.tool_type = tool_type
        self.tools_mngr = tools_mngr

        # make a msg window class for communicating with user
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT
        self.font_size_notes_title = 14
        self.font_size_notes_text = 10

        # ui variables
        self._tool_categories_to_collapse = ['lib', 'shortcuts', 'core']
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
        header.addItem(QtWidgets.QSpacerItem(10, 0))
        header.addWidget(self.btn_save_config)

        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(self.show_only_auto_update_assets_cbox)
        options_layout.addWidget(self.show_only_auto_update_assets_label)
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
        self.btn_save_config.clicked.connect(self.save_update_config)
        self.show_only_auto_update_assets_cbox.clicked.connect(self._set_tree_display_mode)

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

            error = self.tools_mngr.remove_files_not_on_server()
            if error:
                # if error list is very long cap errors
                num_errors = len(error)
                if num_errors > self.app_vars.max_errors_to_display:
                    error = error[:self.app_vars.max_errors_to_display]
                    error.append("+ {0} more files... See log for full list.".format(num_errors))
                error_msg = "The following files are not on the server and attempts to remove failed. " \
                            "The files are \n\n {0}".format(', '.join(error))

                self.msg_win.show_warning_msg("File Sync Warning", error_msg)

            # update config file
            error = self.tools_mngr.update_config_file_after_sync()
            if error:
                error_msg = "Could not sync update configuration file. Error is: {0}".format(error)
                self.msg_win.show_error_msg("File Sync Warning", error_msg)

            self.build_tools_tree()

    def sync_tools_with_cgt(self):
        """
        Syncs the selected tools in the ui with CGT. Updates metadata like version and downloads the latest tools.
        """
        # converts the tree selection to the format {tool type: [list of tool names]}
        tools_by_cat = self._convert_tree_selection_to_tools_list_by_category(self.tools_tree.get_tree_checked())

        # paths in the cgt cloud to the files
        tools_info_list = list()

        # get tool info for selected tools, its a list of tuples (tool type, tool component, tool name, info as
        # dict()
        for tool_type in tools_by_cat:
            for tool_name in tools_by_cat[tool_type]:
                tools_info_list.append(
                    self.tools_mngr.get_tool_info_by_tool_name(self.tool_type, tool_type, tool_name)
                )
        # make a dict of format {tool active_type: {tool type(s): {tool name(s)}}, more tool categories...}
        tools_dict = dict()

        for tool in tools_info_list:
            self.tool_type, tool_cat, tool_name, _ = tool
            if self.tool_type not in tools_dict:
                tools_dict[self.tool_type] = dict()
            if tool_cat not in tools_dict[self.tool_type]:
                tools_dict[self.tool_type][tool_cat] = list()
            tools_dict[self.tool_type][tool_cat].append(tool_name)

        self.tools_mngr.sync_local_cache_with_server_and_download_gui(tools_dict)

    def open_confluence_page(self):
        """
        opens an html page in the web browser for help.  Displays error if page(s) can't
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
        if selection not in self.tools_mngr.get_tool_types(self.tool_type):
            error = self.tools_mngr.open_help_doc(selection)
            if error:
                self.msg_win.show_error_msg("Confluence Error", error)

    def get_notes(self, tree_item_clicked):
        """
        Gets the notes from CGT for the selected asset - double click calls this. Note that this shows the notes
        for the latest version on cgt, not the local version
        :param tree_item_clicked: the tree widget text row that was clicked
        """
        tool_cat, tool_name = self._get_tree_selection_clicked(tree_item_clicked)
        if not tool_name:
            return

        # only process if notes exist
        notes = self.tools_mngr.get_tool_release_notes(self.tool_type, tool_cat, tool_name)
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

    def save_update_config(self):
        """
        Saves the selection to the update config file, asks user before committing changes
        :return:
        """
        # only show warning if deselected something
        if self.tools_tree.get_tree_unchecked():
            response = self.msg_win.show_question_msg(
                "Caution!",
                "Some tools are de-selected and will not auto update. Disabling a tool from auto updating is not "
                "recommended. Are you sure you want to continue?"
            )
        else:
            response = True

        if response:
            # converts the tree selection to the format {tool sub category: [list of tool names]}
            tools_by_cat = self._convert_tree_selection_to_tools_list_by_category(self.tools_tree.get_tree_checked())

            updated_config_data = {self.tool_type: dict()}

            # builds config data to save
            for tool_cat in tools_by_cat:
                if tool_cat not in updated_config_data[self.tool_type]:
                    updated_config_data[self.tool_type][tool_cat] = list()

                for tool_name in tools_by_cat[tool_cat]:
                    updated_config_data[self.tool_type][tool_cat].append(tool_name)

            error = self.tools_mngr.update_config_file_by_tool_type(updated_config_data)
            if error:
                self.msg_win.show_error_msg(
                    "Save Error",
                    "Could not save update config file. Error is: {0}".format(error)
                )
            else:
                self.msg_win.show_info_msg("Saved", "The update config file was saved.")
            # finished saving, refresh ui
            self.build_tools_tree()

    def build_tools_tree(self):
        """
        Calls _build_tools_tree_data to get the tree data (i.e. rows of text). Calling this method with no existing
        tree creates a pyani.core.ui.CheckboxTreeWidget tree object. Calling this method on an existing tree
        rebuilds the tree data
        """
        # get data to build tree
        tree_data, col_count, existing_tools_in_config_file = self._build_tools_tree_data()

        # if the tree has already been built, clear it and call build method
        if self.tools_tree:
            self.tools_tree.clear_all_items()
            self.tools_tree.build_checkbox_tree(
                tree_data,
                expand=True,
                columns=col_count
            )
        # tree hasn't been built yet
        else:
            self.tools_tree = pyani.core.ui.CheckboxTreeWidget(
                tree_data,
                expand=True,
                columns=col_count
            )

        # collapse certain tool categories
        for tool_cat_to_collapse in self._tool_categories_to_collapse:
            self.tools_tree.collapse_item(tool_cat_to_collapse)

        # check on the assets already listed in the config file
        self.tools_tree.set_checked(existing_tools_in_config_file)

    def _build_tools_tree_data(self):
        """
        Builds data for a pyani.core.ui.CheckboxTreeWidget
        :return: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        """
        # tools in a tree widget
        tree_items = list()
        col_count = 1

        existing_tools_in_config_file = []

        for tool_category in sorted(self.tools_mngr.get_tool_types(self.tool_type)):
            # try to load cgt meta data for tool type which has version info for the local files, this is the
            # version on disk locally, could be different than cloud version
            local_cgt_metadata = pyani.core.util.load_json(
                os.path.join(
                    self.app_vars.tool_types[self.tool_type][tool_category]['local dir'],
                    self.app_vars.cgt_metadata_filename
                )
            )
            # if can't load set to None
            if not isinstance(local_cgt_metadata, dict):
                local_cgt_metadata = None

            tools_list = list()
            for tool_name in self.tools_mngr.get_tool_names(self.tool_type, tool_category):
                row_text = [tool_name]
                cgt_version = self.tools_mngr.get_tool_newest_version(self.tool_type, tool_category, tool_name)
                desc = self.tools_mngr.get_tool_description(self.tool_type, tool_category, tool_name)
                if cgt_version:
                    row_text.append(cgt_version)
                else:
                    row_text.append("n/a")
                if desc:
                    row_text.append(desc)
                else:
                    row_text.append("")

                # check if this asset is in the asset update config, meaning it gets updated automatically
                if self.tools_mngr.is_asset_in_update_config(
                        "tools", self.tool_type, tool_name, tool_category
                ):
                    row_color = [pyani.core.ui.GREEN, pyani.core.ui.WHITE, pyani.core.ui.GRAY_MED]
                    existing_tools_in_config_file.append(
                        {
                            "parent": tool_category,
                            "item name": tool_name
                        }
                    )
                else:
                    row_color = [pyani.core.ui.WHITE, pyani.core.ui.WHITE, pyani.core.ui.GRAY_MED]
                col_count = len(row_text)

                if local_cgt_metadata:
                    if tool_name in local_cgt_metadata:
                        local_version = local_cgt_metadata[tool_name][0]["version"]
                        if not local_version == cgt_version:
                            row_text[1] = "{0} / ({1})".format(local_version, cgt_version)
                            # keep the first color, but replace white with red for version
                            row_color = [row_color[0], pyani.core.ui.RED.name(), pyani.core.ui.GRAY_MED]
                tools_list.append(pyani.core.ui.CheckboxTreeWidgetItem(row_text, colors=row_color))
            tree_items.append(
                {
                    'root': pyani.core.ui.CheckboxTreeWidgetItem([tool_category]),
                    'children': tools_list
                }
            )

        return tree_items, col_count, existing_tools_in_config_file

    def _get_tree_selection_clicked(self, tree_item_clicked):
        # get the selection from the ui, always send column 0 because want the tool name
        selected_item = self.tools_tree.get_item_at_position(tree_item_clicked, 0)
        # should be the tool type as long as a tool name was clicked
        item_parent = self.tools_tree.get_parent(tree_item_clicked)
        # if a tool type was clicked on ignore
        if selected_item in self.app_vars.tool_types[self.tool_type]:
            return None, None
        else:
            return item_parent, selected_item

    def _convert_tree_selection_to_tools_list_by_category(self, selection):
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
            if selected.lower() in self.tools_mngr.get_tool_types(self.tool_type):
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

    def _set_tree_display_mode(self):
        """Shows all assets or just assets in the asset update config file
        """
        if self.show_only_auto_update_assets_cbox.checkState():
            # get all checked assets - we want the ones selected in this session as well
            unchecked_assets = self.tools_tree.get_tree_unchecked()
            self.tools_tree.hide_items(unchecked_assets)
            self.tools_tree.expand_all()
        else:
            # show all items
            self.tools_tree.show_items(None, show_all=True)
            self.tools_tree.collapse_all()


class AniAssetMngrGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for app manager. Shows installed apps, versions, and updates if available.
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """

    def __init__(self, error_logging):

        # managers for handling assets and tools
        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()

        app_name = "pyAssetMngr"
        app_vars = pyani.core.appvars.AppVars()
        tool_metadata = {
            "name": app_name,
            "dir": app_vars.local_pyanitools_apps_dir,
            "type": "pyanitools",
            "category": "apps"
        }

        # pass win title, icon path, app manager, width and height
        super(AniAssetMngrGui, self).__init__(
            "Py Asset Manager",
            "Resources\\pyassetmngr_icon.ico",
            tool_metadata,
            self.tools_mngr,
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

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT

        # tabs class object with the tools hub
        self.tabs = pyani.core.ui.TabsWidget(tab_name="Maintenance and Options", tabs_can_close=False)

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
            asset_desc = (
                "<p><span style='font-size:9pt; font-family:{0}; color: #ffffff;'>"
                "<font style='color: {1};'><b>Auto Update:</b></font> "
                "Green assets are currently in the update configuration file and get " 
                "updated daily. Select or de-select assets and click the 'save selection for auto-update button' " 
                "to change what is updated automatically.<br><br><b>Manual Update:</b> Select the assets you want " 
                "to update and click the 'sync selection with cgt' button." 
                "<br><br><i>HINT: To update an asset manually without changing your auto-update file, just clear " 
                "what is selected, select the assets to update, click the 'sync selection...' button, then " 
                "close this app and don't click the 'save selection...' button."
                "</span></p>".format(self.font_family, pyani.core.ui.GREEN)
            )

            tool_desc = (
                "<p><span style='font-size:9pt; font-family:{0}; color: #ffffff;'>"
                "<font style='color: {1};'><b>Auto Update:</b></font> "
                "Green tools are currently in the update configuration file and get "
                "updated daily. Select or de-select tools and click the 'save selection for auto-update button' "
                "to change what is updated automatically. "
                "<font style='color: {2};'><b>WARNING:</b> Removing a tool from the update config file is not "
                "recommended.</font>"
                "<br><br><b>Manual Update:</b> Select the assets you want "
                "to update and click the 'sync selection with cgt' button."
                "<br><br><i>HINT: To update an asset manually without changing your auto-update file, just clear "
                "what is selected, select the assets to update, click the 'sync selection...' button, then "
                "close this app and don't click the 'save selection...' button."
                "</span></p>".format(self.font_family, pyani.core.ui.GREEN, pyani.core.ui.YELLOW.name())
            )
            self.rig_tab = AssetComponentTab("Rigs", self.asset_mngr, asset_component="rig", tab_desc=asset_desc)
            self.audio_tab = AssetComponentTab("Audio", self.asset_mngr, asset_component="audio", tab_desc=asset_desc)
            self.gpu_cache_tab = AssetComponentTab("GPU Cache", self.asset_mngr, asset_component="model/cache", tab_desc=asset_desc)
            self.maya_tools_tab = ToolsTab("Maya Tools", self.tools_mngr, tool_type="maya", tab_desc=tool_desc)
            self.pyanitools_tools_tab = ToolsTab("PyAni Tools", self.tools_mngr, tool_type="pyanitools", tab_desc=tool_desc)

        # INIT FOR MAINTENANCE AND OPTIONS
        # ---------------------------------------------------------------------
        self.btn_update = pyani.core.ui.ImageButton(
            "images\\update_core_off.png",
            "images\\update_core_on.png",
            "images\\update_core_on.png",
            size=(256, 256)
        )
        self.btn_install = pyani.core.ui.ImageButton(
            "images\\re_install_off.png",
            "images\\re_install_on.png",
            "images\\re_install_on.png",
            size=(256, 256)
        )

        self.task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_update", r"'{0}' {1} {2}".format(
                app_vars.pyanitools_support_launcher_path,
                app_vars.local_pyanitools_core_dir,
                app_vars.pyanitools_update_app_name
            )
        )

        # main ui elements for pyanitools - styling set in the create ui functions
        self.auto_dl_label = QtWidgets.QLabel("")
        self.menu_toggle_auto_dl = QtWidgets.QComboBox()
        self.menu_toggle_auto_dl.addItem("-------")
        self.menu_toggle_auto_dl.addItem("Enabled")
        self.menu_toggle_auto_dl.addItem("Disabled")
        self.auto_dl_run_time_label = QtWidgets.QLabel("")
        self.auto_dl_am_pm = QtWidgets.QComboBox()
        self.auto_dl_am_pm.addItem("AM")
        self.auto_dl_am_pm.addItem("PM")

        # get the current time and set it
        current_update_time = self.task_scheduler.get_task_time()
        hour, min, time_of_day = self._get_update_time_components(current_update_time)

        self.auto_dl_am_pm.setCurrentIndex(self.auto_dl_am_pm.findText(time_of_day))
        self.auto_dl_hour = QtWidgets.QLineEdit(hour)
        self.auto_dl_hour.setMaximumWidth(40)
        self.auto_dl_min = QtWidgets.QLineEdit(min)
        self.auto_dl_min.setMaximumWidth(40)
        self.btn_auto_dl_update_time = QtWidgets.QPushButton("Update Run Time")

        # if task is missing, this button shows
        self.btn_create_task = QtWidgets.QPushButton("Create Daily Update Task")
        self.btn_create_task.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))

        self.create_layout()
        self.set_slots()

    def create_layout(self):

        self.main_layout.addWidget(self.tabs)

        maint_and_options_layout = self.create_layout_maint_and_options()
        self.tabs.update_tab(maint_and_options_layout)

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

    def create_layout_maint_and_options(self):
        """
        Create the layout for the hub which has the update, install, and options
        :return: a pyqt layout object
        """
        maint_and_options_main_layout = QtWidgets.QVBoxLayout()

        maint_and_options_main_layout.addItem(QtWidgets.QSpacerItem(1, 100))

        # this section creates the update and re-install options with descriptions beneath and a vertical line
        # separating the two actions
        maint_main_layout = QtWidgets.QHBoxLayout()
        maint_update_layout = QtWidgets.QVBoxLayout()
        maint_install_layout = QtWidgets.QVBoxLayout()

        maint_update_layout.addWidget(self.btn_update)
        maint_update_desc = QtWidgets.QLabel(
                "<p><span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>"
                "Update will sync local caches with the server, update out of date tool, show and shot assets. Update "
                "does not replace any configuration files or preferences."
                "</span></p>".format(self.font_size, self.font_family)
        )
        maint_update_desc.setWordWrap(True)
        maint_update_layout.addWidget(maint_update_desc)

        maint_install_layout.addWidget(self.btn_install)
        main_install_desc = QtWidgets.QLabel(
                "<p><span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>"
                "Install will re-install all tools and sync local caches with the server. A re-install will "
                "<u>replace</u> configuration files and preferences."
                "</span></p>".format(self.font_size, self.font_family)
        )
        main_install_desc.setWordWrap(True)
        maint_install_layout.addWidget(main_install_desc)

        maint_main_layout.addStretch(1)
        maint_main_layout.addLayout(maint_update_layout)
        maint_main_layout.addItem(QtWidgets.QSpacerItem(100, 1))
        maint_main_layout.addWidget(pyani.core.ui.QVLine("#ffffff"))
        maint_main_layout.addItem(QtWidgets.QSpacerItem(100, 1))
        maint_main_layout.addLayout(maint_install_layout)
        maint_main_layout.addStretch(1)
        maint_and_options_main_layout.addLayout(maint_main_layout)

        maint_and_options_main_layout.addItem(QtWidgets.QSpacerItem(1, 100))

        # OPTIONS
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.addWidget(
            QtWidgets.QLabel(
                "<span style='font-size:18pt; font-family:{0}; color: #ffffff;'><b>Options</b></span>".format(
                    self.font_family
                )
            )
        )

        # set initial state of auto download
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
            "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
            "Auto-download of updates from server "
            "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                self.font_size, self.font_family, pyani.core.ui.GRAY_MED, state_label
            )
        )

        # check if task exists, if not show create task button
        is_scheduled = self.task_scheduler.is_task_scheduled()

        if not is_scheduled:
            options_create_task_layout = QtWidgets.QHBoxLayout()
            options_create_task_layout.addWidget(self.btn_create_task)
            options_create_task_layout.addStretch(1)
            options_layout.addLayout(options_create_task_layout)
            options_layout.addItem(QtWidgets.QSpacerItem(1, 30))

        options_auto_update_enabled_layout = QtWidgets.QHBoxLayout()
        options_auto_update_enabled_layout.addWidget(self.auto_dl_label)
        options_auto_update_enabled_layout.addWidget(self.menu_toggle_auto_dl)
        options_auto_update_enabled_layout.addStretch(1)
        options_layout.addLayout(options_auto_update_enabled_layout)

        options_change_time_layout = QtWidgets.QHBoxLayout()

        # get the run time and format as hour:seconds am or pm, ex: 02:00 PM
        run_time = self.task_scheduler.get_task_time()
        if isinstance(run_time, datetime.datetime):
            run_time = run_time.strftime("%I:%M %p")
        else:
            run_time = "N/A"
        self.auto_dl_run_time_label.setText(
            "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
            "Change Update Time  "
            "<font color='{2}'><i>(Current Update Time: {3})</font></i></span>".format(
                self.font_size, self.font_family, pyani.core.ui.GRAY_MED, run_time
            )
        )
        options_change_time_layout.addWidget(self.auto_dl_run_time_label)
        options_change_time_layout.addWidget(self.auto_dl_hour)
        options_change_time_layout.addWidget(self.auto_dl_min)
        options_change_time_layout.addWidget(self.auto_dl_am_pm)
        options_change_time_layout.addWidget(self.btn_auto_dl_update_time)
        options_change_time_layout.addStretch(1)
        options_layout.addLayout(options_change_time_layout)
        options_layout.addStretch(1)
        maint_and_options_main_layout.addLayout(options_layout)
        maint_and_options_main_layout.addItem(QtWidgets.QSpacerItem(1, 50))

        return maint_and_options_main_layout

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.menu_toggle_auto_dl.currentIndexChanged.connect(self.update_auto_dl_state)
        self.btn_update.clicked.connect(self.update)
        self.btn_install.clicked.connect(self.reinstall)
        self.btn_auto_dl_update_time.clicked.connect(self.update_auto_dl_time)
        self.btn_create_task.clicked.connect(self.create_missing_task)
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

    def create_missing_task(self):
        """
        Adds the daily update task with run time 12:00 pm
        """
        error = self.task_scheduler.setup_task(schedule_type="daily", start_time="12:00")
        if error:
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not create task {0}. Error is {1}".format(
                    self.task_scheduler.task_name,
                    error
                )
            )
        else:
            self.msg_win.show_info_msg(
                "Task Success",
                "The daily update task was created."
            )
            self.auto_dl_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Auto-download of updates from server "
                "<font color='{2}'><i>(Currently: Enabled)</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED
                )
            )
            self.auto_dl_run_time_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Change Update Time  "
                "<font color='{2}'><i>(Current Update Time: 12:00 PM)</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED
                )
            )
            self.btn_create_task.hide()

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
                    "able to enable or disable the windows task. Error is {1}".format(
                        self.task_scheduler.task_name,
                        state
                    )
                )
                self.auto_dl_label.setText(
                    "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                    "Auto-download of updates from server "
                    "<font color='{2}'><i>(Currently: Unknown)</font></i></span>".format(
                        self.font_size, self.font_family, pyani.core.ui.GRAY_MED
                    )
                )
            else:
                self.auto_dl_label.setText(
                    "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                    "Auto-download of updates from server "
                    "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                        self.font_size, self.font_family, pyani.core.ui.GRAY_MED, state
                    )
                )

    def update_auto_dl_time(self):
        """
        Update the run time for the auto updates
        """
        run_time = "n/a"
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
            self.auto_dl_run_time_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Change Update Time  "
                "<font color='{2}'><i>(Current Update Time: {3})</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED, run_time
                )
            )
        except ValueError:
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not set run time. {0} is not a valid time".format(run_time)
            )

    def reinstall(self):
        """
        Re=installs tools by calling app roaming launcher which copies setup.exe to temp dir and re-installs
        :return:
        """
        app_vars = pyani.core.appvars.AppVars()
        app_path = app_vars.local_pyanitools_core_dir
        app_name = app_vars.pyanitools_setup_app_name

        response = self.msg_win.show_question_msg("Auto Close Warning",
                                                  "This application will close now so the install can run. "
                                                  "Press Yes to continue or No to cancel. Ok to continue?"
                                                  )
        if response:
            # launch app
            error = pyani.core.util.launch_app(
                app_vars.pyanitools_support_launcher_path,
                [app_path, app_name],
                open_as_new_process=True
            )
            if error:
                self.msg_win.show_error_msg(
                    "Setup Error",
                    "Could not copy setup application for re-installation. Error is {0}".format(error)
                )
                logger.error(error)
                return
            sys.exit()

    def update(self):
        """
        Updates assets and caches by calling app roaming launcher which copies update.exe to temp dir and updates
        """
        app_vars = pyani.core.appvars.AppVars()
        app_path = app_vars.local_pyanitools_core_dir
        app_name = app_vars.pyanitools_update_app_name

        response = self.msg_win.show_question_msg("Auto Close Warning",
                                                  "This application will close now so the asset manager can "
                                                  "update. Press Yes to continue or No to cancel. Ok to continue?"
                                                  )
        if response:
            # launch app
            error = pyani.core.util.launch_app(
                app_vars.pyanitools_support_launcher_path,
                [app_path, app_name],
                open_as_new_process=True
            )
            if error:
                self.msg_win.show_error_msg(
                    "Setup Error",
                    "Could not copy update application to update files. Error is {0}".format(error)
                )
                logger.error(error)
                return
            sys.exit()

    @staticmethod
    def _get_update_time_components(update_time):
        """
        Gets the hour, min ,a dn time of day (AM/PM) from a date time object
        :param update_time: the date time object
        :return: hour, min, and time of day (AM/PM)
        """
        if isinstance(update_time, datetime.datetime):
            hour = "{:d}".format(update_time.hour)
            min = "{:02d}".format(update_time.minute)
            time_of_day = update_time.strftime('%p')
        else:
            hour = ""
            min = ""
            time_of_day = "AM"

        return hour, min, time_of_day



