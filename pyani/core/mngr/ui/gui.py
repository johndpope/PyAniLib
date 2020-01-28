import os
import sys
import datetime
import pyani.core.util
import logging
import functools
import pyani.core.ui
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core
import pyani.review.core

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore


logger = logging.getLogger()


class CoreTab(QtWidgets.QWidget):
    """
    A class that provides core functionality for tab pages for assets and tools.

    the general format / display is:

    ---------------------------------------------------------
    tab description (if provided)      |     buttons
                                       |
    ---------------------------------------------------------
    main_options_widgets (if provided) - can be horizontal or vertical in layout

    ---------------------------------------------------------
    additional options widgets if provided

    ----------------------------------------------------------
    tree list - can be disabled with the show_tree option when creating an instance of this class

    """

    def __init__(
            self,
            name,
            mngr,
            tab_desc=None,
            items_to_collapse=None,
            show_tree=True,
            options_layout_orientation="Horizontal"
    ):
        """
        :param name: name of the tab, displayed on tab
        :param mngr: a manager object, see available mngrs in pyani.core.mngr
        :param tab_desc: an optional description
        :param items_to_collapse: optional list of tree items to collapse by default (only supports collapsing parent
        items, not specific children of a parent
        :param show_tree: whether to show the tree area, default is true
        :param options_layout_orientation: whether to put the main_options_widgets horizontally or vertically. Defaults to Horizontal
        Values are 'Horizontal' or 'Vertical'
        """
        super(CoreTab, self).__init__()

        # core variables
        self.app_vars = pyani.core.appvars.AppVars()
        self._name = name
        self.asset_report = pyani.core.mngr.ui.core.AniAssetUpdateReport(self)
        self.mngr = mngr

        # make a msg window class for communicating with user
        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT
        self.font_size_notes_title = 14
        self.font_size_notes_text = 10

        # ui variables
        self.tab_description = tab_desc
        self.tab_description_label = QtWidgets.QLabel(tab_desc)
        self.tab_description_label.setWordWrap(True)
        self.tab_description_label.setMinimumWidth(700)

        self.show_tree = show_tree
        self.options_orientation = options_layout_orientation

        self.show_only_auto_update_assets_label, self.show_only_auto_update_assets_cbox = pyani.core.ui.build_checkbox(
            "Show Only Assets that are Auto-Updated.",
            False,
            "Shows assets that are in the auto update config file. These are the green colored assets below."
        )
        # buttons are a list of pyani.core.ui.ImageButton objects
        self.buttons = list()

        # options widgets are a list of dicts, where each dict is
        '''
            "widget": pyqt widget
            "label": pyqt qlabel widget
        '''
        # the main main_options_widgets
        self.main_options_widgets = list()
        # additional specific main_options_widgets
        self.additional_options = list()
        self.additional_options_title = "Asset Specific Options"
        self.additional_options_widgets = list()
        self.additional_options_menu = QtWidgets.QComboBox()

        self.tree = None

        self.parent_categories_to_collapse = items_to_collapse

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

    def add_button(self, image_button):
        """
        adds a button to the tab
        :param image_button: a pyani.core.ui.ImageButton object
        """
        self.buttons.append(image_button)

    def add_general_option(self, option_widget, option_label):
        """
        adds an option to the tab. This option goes in the general main_options_widgets area, see class doc
        :param option_widget: a pyqt widget or a list of widgets
        :param option_label: a pyqt QLabel
        """
        self.main_options_widgets.append(
            {
                "widget": option_widget,
                "label": option_label
            }
        )

    def add_additional_option(self, option_label, option_widget=None, option_layout=None):
        """
        adds an option or layout to the additional options section of the tab. Provide one or the other, but not both.
        If both are provided the layout will be ignored
        :param option_widget: a pyqt widget or a list of widgets
        :param option_label: a pyqt QLabel
        :param option_layout: optional pyqt layout, if this is provided any widgets provided will be ignored
        """
        # both widget and layout provided, ignore layout
        if option_layout and option_widget:
            option_layout = None

        self.additional_options_widgets.append(
            {
                "widget": option_widget,
                "label": option_label,
                "layout": option_layout
            }
        )

    def set_additional_options_title(self, title):
        """Sets the title for the additional options"""
        self.additional_options_title = title

    def add_additional_option_to_menu(self, option_name):
        """
        The additional option name, added to a menu so user can switch between additional options - see class docstring
        :param option_name: the name as a string
        """
        self.additional_options.append(option_name)

    def build_layout(self, tree_data=None, col_count=None, existing_items_in_config_file=None):
        """
        builds the tab layout, can pass tree data if ready to build tree, or it will be blank
        :param tree_data: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        :param col_count: the max number of columns
        :param existing_items_in_config_file: items in the config file
        """

        header = QtWidgets.QHBoxLayout()

        # optional description
        header.addWidget(self.tab_description_label)
        header.addStretch(1)

        # buttons
        for button in self.buttons:
            header.addWidget(button)
            header.addItem(QtWidgets.QSpacerItem(10, 0))

        self.layout.addLayout(header)
        self.layout.addItem(QtWidgets.QSpacerItem(1, 20))

        # main options widgets section
        if self.options_orientation == "Horizontal":
            options_layout = QtWidgets.QHBoxLayout()
            for option in self.main_options_widgets:
                # get the widget, and check if its a list. If it's a list, we need to build a horizontal layout to
                # contain all the widgets, otherwise we can just add single widgets straight to the layout
                option_widget = option['widget']
                if isinstance(option_widget, tuple):
                    widget_layout = QtWidgets.QHBoxLayout()
                    for widget in option_widget:
                        widget_layout.addWidget(widget)
                    options_layout.addLayout(widget_layout)
                else:
                    options_layout.addWidget(option['widget'])
                if option['label']:
                    options_layout.addWidget(option['label'])
                options_layout.addItem(QtWidgets.QSpacerItem(40, 0))
            options_layout.addStretch(1)
        else:
            options_layout = QtWidgets.QVBoxLayout()
            for option in self.main_options_widgets:
                option_sub_layout = QtWidgets.QHBoxLayout()
                if option['label']:
                    option_sub_layout.addWidget(option['label'])
                # get the widget, and check if its a list. If it's a list, we need to build a horizontal layout to
                # contain all the widgets, otherwise we can just add single widgets straight to the layout
                option_widget = option['widget']
                if isinstance(option_widget, tuple):
                    widget_layout = QtWidgets.QHBoxLayout()
                    for widget in option_widget:
                        widget_layout.addWidget(widget)
                        widget_layout.addItem(QtWidgets.QSpacerItem(10, 0))
                    option_sub_layout.addLayout(widget_layout)
                else:
                    option_sub_layout.addWidget(option['widget'])
                option_sub_layout.addStretch(1)
                options_layout.addLayout(option_sub_layout)

        self.layout.addLayout(options_layout)

        # additional options section
        if self.additional_options:
            self.layout.addItem(QtWidgets.QSpacerItem(0, 75))
            additional_options_layout = QtWidgets.QVBoxLayout()
            # create the title and the menu, default to generic title if not provided
            header_layout = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel(
                "<span style = 'font-size:12pt; font-family:{0}; color:{2};'><b>{1}</b></span>".format(
                    self.font_family, self.additional_options_title, pyani.core.ui.CYAN
                )
            )
            header_layout.addWidget(title)
            for option in self.additional_options:
                self.additional_options_menu.addItem(option)
            header_layout.addWidget(self.additional_options_menu)
            header_layout.addStretch(1)
            additional_options_layout.addLayout(header_layout)

            additional_options_layout.addItem(QtWidgets.QSpacerItem(0, 30))
            # create the actual options layout
            for option in self.additional_options_widgets:
                additional_option_layout = QtWidgets.QHBoxLayout()
                if option['label']:
                    additional_option_layout.addWidget(option['label'])
                    additional_option_layout.addItem(QtWidgets.QSpacerItem(10, 0))
                # unpack the option, may be several widgets or a layout, and add to additional options layout
                if option['widget']:
                    for widget in option['widget']:
                        additional_option_layout.addWidget(widget)
                else:
                    additional_option_layout.addLayout(option['layout'])
                # now add option to layout
                additional_options_layout.addLayout(additional_option_layout)
            self.layout.addLayout(additional_options_layout)

        if self.show_tree:
            self.build_tree(
                tree_data=tree_data, col_count=col_count, existing_items_in_config_file=existing_items_in_config_file
            )
            self.layout.addWidget(self.tree)
        else:
            self.layout.addStretch(1)

    def build_tree(self, tree_data=None, col_count=None, existing_items_in_config_file=None):
        """
        Calling this method with no existing tree creates a pyani.core.ui.CheckboxTreeWidget tree object.
        Calling this method on an existing tree rebuilds the tree data
        :param tree_data: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        :param col_count: the max number of columns
        :param existing_items_in_config_file: items in the config file
        """

        # if the tree has already been built, clear it and call build method
        if self.tree:
            self.tree.clear_all_items()
            self.tree.build_checkbox_tree(
                tree_data,
                expand=True,
                columns=col_count
            )
        # tree hasn't been built yet
        else:
            self.tree = pyani.core.ui.CheckboxTreeWidget(
                tree_data,
                expand=True,
                columns=col_count
            )

        # collapse certain tool categories
        if self.parent_categories_to_collapse:
            for item_to_collapse in self.parent_categories_to_collapse:
                self.tree.collapse_item(item_to_collapse)

        # check on the assets already listed in the config file
        self.tree.set_checked(existing_items_in_config_file)


class ReviewTab(CoreTab):
    """
    A class that provides a tab page for reviewing asset tools
    """
    def __init__(self, name, core_mngr, tab_desc=None):
        """
        :param name: name of the tab, displayed on tab
        :param core_mngr: a core manager object pyani.core.mngr.core
        :param tab_desc: an optional description
        """
        super(ReviewTab, self).__init__(
            name, core_mngr, tab_desc=tab_desc, items_to_collapse=None, show_tree=False, options_layout_orientation='Vertical'
        )

        # create a task scheduler object
        self.task_scheduler = pyani.core.util.WinTaskScheduler(
            "pyanitools_review_download", r"'{0}'".format(
                self.app_vars.review_download_tool_path
            )
        )

        # review manager object for downloading review assets
        self.download_report = pyani.core.mngr.ui.core.AniAssetTableReport(self)
        self.review_mngr = pyani.review.core.AniReviewMngr(core_mngr)
        # provide report to review mngr so it can set data
        self.review_mngr.set_report(self.download_report)

        # setup tasks for downloading reviews

        # create a task list manager placeholder, create instance in download function
        self.task_mngr = None
        self.progress_list = list()

        # UI VARIABLES

        # buttons
        self.btn_download = pyani.core.ui.ImageButton(
            "images\\download_off.png",
            "images\\download_on.png",
            "images\\download_on.png",
            size=(86, 86)
        )
        self.add_button(self.btn_download)

        # general main_options_widgets
        self.enable_auto_download_label = QtWidgets.QLabel("Turn on Automatic Downloads for Review Assets")
        self.enable_auto_download_menu = QtWidgets.QComboBox()
        self.enable_auto_download_menu.addItem("-------")
        self.enable_auto_download_menu.addItem("Enabled")
        self.enable_auto_download_menu.addItem("Disabled")

        self.auto_dl_label = QtWidgets.QLabel("Change Download Time")
        self.auto_dl_am_pm = QtWidgets.QComboBox()
        self.auto_dl_am_pm.addItem("AM")
        self.auto_dl_am_pm.addItem("PM")
        self.auto_dl_hour = QtWidgets.QLineEdit("")
        self.auto_dl_hour.setMaximumWidth(40)
        self.auto_dl_min = QtWidgets.QLineEdit("")
        self.auto_dl_min.setMaximumWidth(40)
        self.save_auto_dl_time_button = pyani.core.ui.ImageButton(
            "images\\save_pref_off.png",
            "images\\save_pref_on.png",
            "images\\save_pref_on.png",
            size=(34, 30)
        )

        self.set_download_location_label = QtWidgets.QLabel(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Set Download Location for Review "
            "Assets</span>".format(
                self.font_size,
                self.font_family
            )
        )
        self.set_download_location_input = QtWidgets.QLineEdit("")
        self.set_download_location_input.setMinimumWidth(400)
        self.set_download_location_button = pyani.core.ui.ImageButton(
            "images\\file_open_off.png",
            "images\\file_open_on.png",
            "images\\file_open_on.png",
            size=(37, 30)
        )
        self.save_download_location_button = pyani.core.ui.ImageButton(
            "images\\save_pref_off.png",
            "images\\save_pref_on.png",
            "images\\save_pref_on.png",
            size=(34, 30)
        )

        self.replace_old_assets_label, self.replace_old_assets_cbox = pyani.core.ui.build_checkbox(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Replace Existing Review Assets With "
            "Latest</span>".format(
                self.font_size,
                self.font_family
            ),
            False,
            "Replaces assets on the local drive with today's review assets on the server."
        )

        self.add_general_option(self.enable_auto_download_menu, self.enable_auto_download_label)
        self.add_general_option(
            (self.auto_dl_hour, self.auto_dl_min, self.auto_dl_am_pm,  self.save_auto_dl_time_button),
            self.auto_dl_label
        )
        self.add_general_option(
            (self.set_download_location_input, self.set_download_location_button, self.save_download_location_button),
            self.set_download_location_label
        )
        self.add_general_option(self.replace_old_assets_cbox, self.replace_old_assets_label)

        # loads and sets the general preferences that apply to all assets
        self.load_and_set_general_preferences()

        # add additional main_options_widgets
        self.set_additional_options_title("Review Specific Options")
        self.add_additional_option_to_menu("Movies")
        # list of widgets we need to be able to reference, store in a dict with key the department name and value
        # another dict where the ket is the widget name, and value is the widget
        self.additional_options_widgets_list = dict()

        # these options allow a user to assign multiple departments to one folder, but only keep one dept based off
        # a precedence list and have the rest go into the general download location when multiple movies are present
        # in a review. example, anim, layout and previs go into one folder. anim and layout are in a review. the order
        # of precedence is anim, layout, previs. Then anim is kept in the folder and layout moved to general folder.
        pref = self.mngr.get_preference("review asset download", "movie", "use precedence")
        if isinstance(pref, dict):
            pref_value = pref["use precedence"]
        else:
            pref_value = False
        self.use_dept_precedence_label, self.use_dept_precedence_cbox = pyani.core.ui.build_checkbox(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Keep only one dept in folder "
            "based off precedence list</span>".format(
                self.font_size,
                self.font_family
            ),
            pref_value,
            "Allows multiple departments to be assigned to a folder, but only one is ever kept and rest are put" \
            " into the general download location based off the precedence list."
        )

        self.dept_movie_precedence_list_widget = QtWidgets.QListWidget()
        pref = self.mngr.get_preference("review asset download", "movie", "precedence order")
        if isinstance(pref, dict):
            dept_order = pref["precedence order"]
        else:
            dept_order = sorted(self.app_vars.review_depts)
        for dept in dept_order:
            self.dept_movie_precedence_list_widget.addItem(dept)
        self.dept_movie_precedence_list_widget.setMinimumHeight(150)
        self.dept_movie_precedence_list_widget.setMaximumHeight(155)
        self.dept_movie_precedence_list_widget.setMaximumWidth(600)
        # Enable drag & drop ordering of items.
        self.dept_movie_precedence_list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        # button to save the list to the preference file
        self.btn_save_dept_precedence = pyani.core.ui.ImageButton(
            "images\\save_pref_off.png",
            "images\\save_pref_on.png",
            "images\\save_pref_on.png",
            size=(34, 30)
        )

        self.create_movie_options()

        self.build_layout()
        self.set_slots()

    def set_slots(self):
        self.replace_old_assets_cbox.clicked.connect(self.set_general_pref_replace_assets)
        self.set_download_location_button.clicked.connect(self.get_general_pref_download_location_from_filedialog)
        self.save_download_location_button.clicked.connect(self.set_general_pref_download_location)
        self.save_auto_dl_time_button.clicked.connect(self.set_download_time)
        self.enable_auto_download_menu.currentIndexChanged.connect(self.set_auto_download_state)
        self.btn_download.clicked.connect(self.download_review_assets)
        self.btn_save_dept_precedence.clicked.connect(self.set_movie_pref_dept_precedence)
        self.use_dept_precedence_cbox.clicked.connect(self.set_movie_pref_use_precedence)

    def create_movie_options(self):
        """
        Creates options for review movies
        """

        '''
        list_label = QtWidgets.QLabel(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Drag and Drop the departments to create "
            "your precedence order (<i>highest to lowest</i>)</span>".format(
                self.font_size,
                self.font_family
            )
        )
        list_label.setWordWrap(True)
        list_label.setMaximumWidth(800)
        precedence_desc = QtWidgets.QLabel(
            "<span style='font-size:9pt; font-family:{0}; color: {2};'>"
            "Use the options below to put multiple departments in a folder, but only keep the department with the "
            "most recent movie in the folder. The precedence list defines what happens if a review has multiple "
            "departments in the review. The department with highest precedence gets put in the folder, while the "
            "other departments get put in the general download location: {1}"
            "</span>".format(
                self.font_family,
                str(self.set_download_location_input.text()),
                pyani.core.ui.GRAY_MED
            )
        )
        precedence_desc.setMaximumWidth(800)
        precedence_desc.setWordWrap(True)

        precedence_layout = QtWidgets.QVBoxLayout()

        precedence_layout.addWidget(precedence_desc)
        precedence_layout.addItem(QtWidgets.QSpacerItem(0, 20))

        precedence_sub_layout = QtWidgets.QHBoxLayout()
        precedence_sub_layout.addWidget(self.use_dept_precedence_cbox)
        precedence_sub_layout.addWidget(self.use_dept_precedence_label)
        precedence_sub_layout.addItem(QtWidgets.QSpacerItem(75, 0))

        precedence_list_layout = QtWidgets.QVBoxLayout()
        precedence_list_layout.addWidget(list_label)

        precedence_list_sub_layout = QtWidgets.QHBoxLayout()
        precedence_list_sub_layout.addWidget(self.dept_movie_precedence_list_widget)
        precedence_list_sub_layout.addItem(QtWidgets.QSpacerItem(15, 0))
        precedence_list_sub_layout.addWidget(self.btn_save_dept_precedence)
        precedence_list_sub_layout.addStretch(1)

        precedence_list_layout.addLayout(precedence_list_sub_layout)

        precedence_sub_layout.addLayout(precedence_list_layout)
        precedence_sub_layout.addStretch(1)

        precedence_layout.addLayout(precedence_sub_layout)
        precedence_layout.addItem(QtWidgets.QSpacerItem(0, 25))

        precedence_sub_layout.setAlignment(self.use_dept_precedence_cbox, QtCore.Qt.AlignTop)
        precedence_sub_layout.setAlignment(self.use_dept_precedence_label, QtCore.Qt.AlignTop)
        precedence_list_sub_layout.setAlignment(self.btn_save_dept_precedence, QtCore.Qt.AlignTop)

        self.add_additional_option("", option_layout=precedence_layout)
        '''
        movie_dl_layout = QtWidgets.QVBoxLayout()
        movie_dl_desc = QtWidgets.QLabel(
            "<span style='font-size:9pt; font-family:{0}; color: {1};'>"
            "Use the options below to choose which department movies are downloaded and where they download to. "
            "You can also choose per department whether movies on disk get replaced."
            "</span>".format(
                self.font_family,
                pyani.core.ui.GRAY_MED
            )
        )

        movie_dl_desc.setMaximumWidth(800)
        movie_dl_desc.setWordWrap(True)

        movie_dl_layout.addWidget(movie_dl_desc)
        movie_dl_layout.addItem(QtWidgets.QSpacerItem(0, 20))

        grid_layout = QtWidgets.QGridLayout()

        # loop through departments and create widget main_options_widgets
        for index, dept in enumerate(sorted(self.app_vars.review_depts)):
            # dept label and checkbox for choosing to download the department's movies, checked by default
            pref = self.mngr.get_preference("review asset download", dept, "download movies")
            pref_val = True
            if isinstance(pref, dict):
                pref_val = pref["download movies"]
            dept_label, dept_cbox = pyani.core.ui.build_checkbox(
                "<span style='font-size:{0}pt; font-family:{2}; color: #ffffff;'>{1}</span>".format(
                    self.font_size, dept, self.font_family
                ),
                pref_val,
                "Whether to download this department's movies"
            )

            # whether to replace local movies - first get the general preference, so that we can use that if there
            # isn't a preference saved for the dept
            pref_general = self.review_mngr.mngr.get_preference("review asset download", "update", "update old assets")
            pref = self.review_mngr.mngr.get_preference("review asset download", dept, "replace existing movies")
            pref_val = pref_general['update old assets']
            if isinstance(pref, dict):
                pref_val = pref["replace existing movies"]
            replace_label, replace_cbox = pyani.core.ui.build_checkbox(
                "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Replace existing movies</span>".format(
                    self.font_size,
                    self.font_family
                ),
                pref_val,
                "Replaces movies on the local drive with today's review movies on the server."
            )

            # download location for this department's movies, uses main download location by default
            pref = self.review_mngr.mngr.get_preference("review asset download", dept, "download movie location")
            pref_val = str(self.set_download_location_input.text())
            if isinstance(pref, dict):
                pref_val = pref["download movie location"]
            download_location_input = QtWidgets.QLineEdit(pref_val)
            download_location_input.setMinimumWidth(400)
            set_download_location_button = pyani.core.ui.ImageButton(
                "images\\file_open_off.png",
                "images\\file_open_on.png",
                "images\\file_open_on.png",
                size=(37, 30)
            )
            save_download_location_button = pyani.core.ui.ImageButton(
                "images\\save_pref_off.png",
                "images\\save_pref_on.png",
                "images\\save_pref_on.png",
                size=(34, 30)
            )

            grid_layout.addWidget(dept_cbox, index, 0)
            grid_layout.addWidget(dept_label, index, 1)
            grid_layout.addItem(QtWidgets.QSpacerItem(40, 0), index, 2)
            grid_layout.addWidget(replace_cbox, index, 3)
            grid_layout.addWidget(replace_label, index, 4)
            grid_layout.addItem(QtWidgets.QSpacerItem(40, 0), index, 5)
            grid_layout.addWidget(download_location_input, index, 6)
            grid_layout.addItem(QtWidgets.QSpacerItem(10, 0), index, 7)
            grid_layout.addWidget(set_download_location_button, index, 8)
            grid_layout.addItem(QtWidgets.QSpacerItem(10, 0), index, 9)
            grid_layout.addWidget(save_download_location_button, index, 10)
            grid_layout.setColumnStretch(11, 1)

            # connect slots/signals
            dept_cbox.stateChanged.connect(
                functools.partial(self.set_movie_pref_download, dept_cbox, dept)
            )
            replace_cbox.stateChanged.connect(
                functools.partial(self.set_movie_pref_replace_existing, replace_cbox, dept)
            )
            save_download_location_button.clicked.connect(
                functools.partial(
                    self.set_movie_pref_download_location,
                    download_location_input,
                    dept
                )
            )

            # save widgets for later reference
            self.additional_options_widgets_list[dept] = {
                "replace cbox": replace_cbox,
                "download location": download_location_input
            }

        movie_dl_layout.addLayout(grid_layout)
        # add layout with all options
        self.add_additional_option("", option_layout=movie_dl_layout)

    def update_ui(self):
        """Updates the ui"""
        self._update_movie_ui()

    def update_progress(self):
        """
        Updates progress when downloading review assets
        """
        # report progress to user so they know what's going on, do in tab description area
        progress_step = self.progress_list.pop(0)
        if self.progress_list:
            progress_desc = (
                "<p align ='right'><font style='font-size: 11pt; font-family:{0}; color: {1};'><b>Progress Update:</b>"
                "</font><font style='font-size: 11pt; font-family:{0}; color: #ffffff;'> {2}</font></p>".format(
                    self.font_family,
                    pyani.core.ui.GREEN,
                    progress_step
                )
            )
            tab_desc = self.tab_description + progress_desc
        # done, restore tab description
        else:
            tab_desc = self.tab_description

        self.tab_description_label.setText(tab_desc)

    def download_review_assets(self):
        """
        Downloads review assets
        """
        if self.review_mngr.review_exists():
            self.progress_list = [
                "Finding latest assets for review..This may take a few seconds...",
                "Downloading assets for review..."
            ]

            # list of tasks to run, see pyani.core.mngr.ui.core.AniTaskListWindow for format
            task_list = [
                # find the latest assets for review
                {
                    'func': self.review_mngr.find_latest_assets_for_review,
                    'params': [],
                    'finish signal': self.review_mngr.mngr.finished_signal,
                    'error signal': self.review_mngr.mngr.error_thread_signal,
                    'thread task': True,
                    'desc': "Found latest assets for review."
                },
                # download the latest assets for review
                {
                    'func': self.review_mngr.download_latest_assets_for_review,
                    'params': [],
                    'finish signal': self.review_mngr.mngr.finished_signal,
                    'error signal': self.review_mngr.mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Downloaded latest assets for review."
                }
            ]

            pref = self.review_mngr.mngr.get_preference("review asset download", "update", "update old assets")
            # if the user preference is to replace old review assets with the latest, run the update
            if isinstance(pref, dict):
                pref_val = pref['update old assets']
                if pref_val:
                    task_list.append(
                        {
                            'func': self.review_mngr.update_review_assets_to_latest,
                            'params': [],
                            'finish signal': self.review_mngr.mngr.finished_signal,
                            'error signal': self.review_mngr.mngr.error_thread_signal,
                            'thread task': True,
                            'desc': "Updated existing review assets."
                        }
                    )
                self.progress_list.append("Updating existing review assets with the latest...")

            task_list.append(
                {
                    'func': self.review_mngr.generate_download_report_data,
                    'params': [],
                    'finish signal': self.review_mngr.mngr.finished_signal,
                    'error signal': self.review_mngr.mngr.error_thread_signal,
                    'thread task': True,
                    'desc': "Created table data for report."
                }
            )
            self.progress_list.append("Creating table data for report...")

            self.task_mngr = pyani.core.mngr.ui.core.AniTaskList(task_list, ui_callback=self.update_progress)

            # NOTE: do this here because the super needs to be called first to create the window
            # used to create an html report to show in a QtDialogWindow
            self.download_report = pyani.core.mngr.ui.core.AniAssetTableReport(self)

            # provide report to review mngr so it can set data
            self.review_mngr.set_report(self.download_report)
            # move update window so it doesn't cover the main update window
            this_win_rect = self.frameGeometry()
            post_tasks = [
                {
                    'func': self.download_report.generate_table_report,
                    'params': []
                },
                {
                    'func': self.download_report.move,
                    'params': [this_win_rect.x() + 10, this_win_rect.y() - 10]
                }
            ]
            self.task_mngr.set_post_tasks(post_tasks)

            self.task_mngr.start_tasks()
        # no review files, let user know
        else:
            msg = (
                "<p align='center' style='font-size: 9pt; font-family:{0}; color: {1};'>"
                "No review files exist for today's date."
                "</p>".format(
                    pyani.core.ui.FONT_FAMILY,
                    pyani.core.ui.RED.name()
                )
            )
            msg_win = pyani.core.ui.QtMsgWindow(self)
            msg_win.show_error_msg("No Review Assets", msg)

    def load_and_set_general_preferences(self):
        # load the preferences and set value
        pref = self.mngr.get_preference("review asset download", "update", "update old assets")
        if isinstance(pref, dict):
            self.replace_old_assets_cbox.setChecked(pref.get("update old assets"))

        pref = self.mngr.get_preference("review asset download", "download", "location")
        if isinstance(pref, dict):
            self.set_download_location_input.setText(pref.get("location"))
        else:
            self.set_download_location_input.setText(self.app_vars.review_movie_local_directory)

        exists = self.task_scheduler.is_task_scheduled()
        # check if we got an error getting task existence
        if isinstance(exists, bool):
            # check if it exists
            if exists:
                # set initial state of auto download
                state = self.task_scheduler.is_task_enabled()
                # check if error getting task state
                if isinstance(state, bool):
                    if state:
                        state_label = "Enabled"
                    else:
                        state_label = "Disabled"
                else:
                    state_label = "Could not get task state."
            else:
                state_label = "Task doesn't exist. You must first enable the task."
        else:
            state_label = "Could not query task."

        if state_label == "Enabled":
            self.enable_auto_download_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Turn on Automatic Downloads for Review Assets "
                "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GREEN, state_label
                )
            )
        else:
            self.enable_auto_download_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Turn on Automatic Downloads for Review Assets "
                "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED, state_label
                )
            )

        # get the run time and format as hour:seconds am or pm, ex: 02:00 PM
        run_time = self.task_scheduler.get_task_time()

        if isinstance(run_time, datetime.datetime):
            run_time = run_time.strftime("%I:%M %p")
            # set task time in ui fields
            pyani.core.ui.set_ui_time(
                self.task_scheduler, self.auto_dl_hour, self.auto_dl_min, self.auto_dl_am_pm
            )
        else:
            run_time = "N/A"
            # time doesn't exist, set to default
            time_split = self.app_vars.review_download_time.split(":")
            hour = time_split[0]
            min = time_split[1].split(" ")[0]
            time_of_day = time_split[1].split(" ")[1]
            self.auto_dl_hour.setText(hour)
            self.auto_dl_min.setText(min)
            self.auto_dl_am_pm.setCurrentIndex(self.auto_dl_am_pm.findText(time_of_day))

        self.auto_dl_label.setText(
            "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
            "Change Download Time  "
            "<font color='{2}'><i>(Current Download Time: {3})</font></i></span>".format(
                self.font_size, self.font_family, pyani.core.ui.GRAY_MED, run_time
            )
        )

    def set_auto_download_state(self):
        """
        Creates task if doesn't exist. If it exists, sets to enabled or disabled based off user selection
        """
        # check if the task exists
        is_scheduled = self.task_scheduler.is_task_scheduled()
        if not isinstance(is_scheduled, bool):
            error_fmt = "Can't get Windows Task state. Error is: {0}".format(is_scheduled)
            logging.error(error_fmt)
            self.msg_win.show_error_msg("Task Error", error_fmt)
            return None
        # task doesn't exist, schedule
        if not is_scheduled:
            # schedule tools update to run, if it is already scheduled skips. If scheduling errors then informs user
            # but try to install apps
            run_time = self.app_vars.review_download_time
            military_time = datetime.datetime.strptime(run_time, "%I:%M %p").strftime("%H:%M")
            error = self.task_scheduler.setup_task(schedule_type="daily", start_time=military_time)
            if error:
                error_fmt = "Can't Setup Windows Task Scheduler. Error is: {0}".format(error)
                logging.error(error_fmt)
                self.msg_win.show_error_msg("Task Error", error_fmt)
                return None

        # set the task state
        if not self.enable_auto_download_menu.currentIndex() == 0:
            state = self.enable_auto_download_menu.currentText()
            if state == "Enabled":
                error = self.task_scheduler.set_task_enabled(True)
            else:
                error = self.task_scheduler.set_task_enabled(False)
            if error:
                self.msg_win.show_warning_msg(
                    "Task Scheduling Error",
                    "Could not set state of task {0}. Error is {1}".format(
                        self.task_scheduler.task_name,
                        state
                    )
                )
                return None

            if state == "Enabled":
                self.enable_auto_download_label.setText(
                    "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                    "Turn on Automatic Downloads for Review Assets "
                    "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                        self.font_size, self.font_family, pyani.core.ui.GREEN, state
                    )
                )
            else:
                self.enable_auto_download_label.setText(
                    "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                    "Turn on Automatic Downloads for Review Assets "
                    "<font color='{2}'><i>(Currently: {3})</font></i></span>".format(
                        self.font_size, self.font_family, pyani.core.ui.GRAY_MED, state
                    )
                )

            # get the run time and format as hour:seconds am or pm, ex: 02:00 PM
            run_time = self.task_scheduler.get_task_time()
            if isinstance(run_time, datetime.datetime):
                run_time = run_time.strftime("%I:%M %p")
            else:
                run_time = "N/A"

            self.auto_dl_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Change Download Time  "
                "<font color='{2}'><i>(Current Download Time: {3})</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED, run_time
                )
            )

    def set_download_time(self):
        """
        Update the run time for the auto download
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
            self.auto_dl_label.setText(
                "<span style = 'font-size:{0}pt; font-family:{1}; color:'#ffffff';' > "
                "Change Download Time  "
                "<font color='{2}'><i>(Current Download Time: {3})</font></i></span>".format(
                    self.font_size, self.font_family, pyani.core.ui.GRAY_MED, run_time
                )
            )
        except ValueError:
            self.msg_win.show_warning_msg(
                "Task Scheduling Error",
                "Could not set run time. {0} is not a valid time".format(run_time)
            )

    def get_general_pref_download_location_from_filedialog(self):
        """Gets the file name selected from the dialog and stores in text edit box in gui"""
        name = pyani.core.ui.FileDialog.getExistingDirectory(
            self,
            'Select Location'
        )
        self.set_download_location_input.setText(name)

    def set_general_pref_download_location(self):
        """Saves the location in the edit box to preference file"""
        pref_value = str(self.set_download_location_input.text())

        error = self.mngr.save_preference("review asset download", "download", "location", pref_value)
        if error:
            error_msg = "Could not set the download location preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)
        self.update_ui()

    def set_general_pref_replace_assets(self):
        """saves preference for replacing assets on disk with the latest downloaded"""
        pref_value = bool(self.replace_old_assets_cbox.isChecked())

        error = self.mngr.save_preference("review asset download", "update", "update old assets", pref_value)
        if error:
            error_msg = "Could not save the replace assets preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)

        self.update_ui()

    def set_movie_pref_download(self, dept_cbox, dept_name):
        """
        Saves the preference for whether to download a department's movies
        :param dept_cbox: the pyqt checkbox
        :param dept_name: the name of the department as a string - same as the checkbox label,
        taken from pyani.core.app_vars.review_depts
        """
        error = self.mngr.save_preference(
            "review asset download", dept_name, "download movies", bool(dept_cbox.isChecked())
        )
        if error:
            error_msg = "Could not set the download dept movie preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)

    def set_movie_pref_download_location(self, download_location_input, dept_name):
        """
        Saves the preference for where to download a department's movies
        :param download_location_input: a pyqt line edit widget containing the download path
        :param dept_name: the name of the department as a string - same as the checkbox label,
        taken from pyani.core.app_vars.review_depts
        """
        # make sure a path is entered
        if not download_location_input:
            self.msg_win.show_error_msg("Save Preference Error", "Please enter a valid path.")
        error = self.mngr.save_preference(
            "review asset download", dept_name, "download movie location", str(download_location_input.text())
        )
        if error:
            error_msg = "Could not set the movie download location preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)

    def set_movie_pref_replace_existing(self, cbox, dept_name):
        """
        Saves the preference for whether to replace existing movies with the movies from today's review
        :param cbox: the pyqt checkbox
        :param dept_name: the name of the department as a string - same as the checkbox label,
        taken from pyani.core.app_vars.review_depts
        """
        error = self.mngr.save_preference(
            "review asset download", dept_name, "replace existing movies", bool(cbox.isChecked())
        )
        if error:
            error_msg = "Could not set the replace existing movies preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)

    def set_movie_pref_dept_precedence(self):
        """saves the dept order precedence list"""
        dept_order = [
            str(self.dept_movie_precedence_list_widget.item(i).text())
            for i in range(self.dept_movie_precedence_list_widget.count())
        ]
        error = self.mngr.save_preference("review asset download", "movie", "precedence order", dept_order)
        if error:
            error_msg = "Could not save the precedence order preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)

    def set_movie_pref_use_precedence(self):
        """Saves the preference to use precedence"""
        pref_value = bool(self.use_dept_precedence_cbox.isChecked())
        error = self.mngr.save_preference("review asset download", "movie", "use precedence", pref_value)
        if error:
            error_msg = "Could not save the use precedence preference. Error is {0}".format(error)
            self.msg_win.show_error_msg("Save Preference Error", error_msg)
        # turn on replace since using precedence
        self.replace_old_assets_cbox.setChecked(True)
        for dept in sorted(self.app_vars.review_depts):
            self.additional_options_widgets_list[dept]["replace cbox"].blockSignals(True)
            self.additional_options_widgets_list[dept]["replace cbox"].setChecked(True)
            self.additional_options_widgets_list[dept]["replace cbox"].blockSignals(False)

    def _update_movie_ui(self):
        """Updates the movie specific options widgets"""
        # loop through and update dept widgets
        for dept in sorted(self.app_vars.review_depts):
            # whether to replace local movies - first get the general preference, so that we can use that if there
            # isn't a preference saved for the dept
            pref_general = self.review_mngr.mngr.get_preference("review asset download", "update", "update old assets")
            pref = self.review_mngr.mngr.get_preference("review asset download", dept, "replace existing movies")
            pref_val = pref_general['update old assets']
            if isinstance(pref, dict):
                pref_val = pref["replace existing movies"]
            # disable slots/signals don't want it to save the value which will happen because stateChanged will get
            # fired
            self.additional_options_widgets_list[dept]["replace cbox"].blockSignals(True)
            self.additional_options_widgets_list[dept]["replace cbox"].setChecked(pref_val)
            self.additional_options_widgets_list[dept]["replace cbox"].blockSignals(False)

            # download location for this department's movies, uses main download location by default
            pref = self.review_mngr.mngr.get_preference("review asset download", dept, "download movie location")
            pref_val = str(self.set_download_location_input.text())
            if isinstance(pref, dict):
                pref_val = pref["download movie location"]
            self.additional_options_widgets_list[dept]["download location"].setText(pref_val)


class AssetComponentTab(CoreTab):
    """
    A class that provides a tab page for show and shot assets.
    """
    def __init__(self, name, mngr, tab_desc=None, asset_component=None):
        """
        :param name: name of the tab, displayed on tab
        :param mngr: an asset manager object pyani.core.mngr.assets
        :param tab_desc: an optional description
        :param asset_component: the asset's category or component such as rig, audio, or gpu cache
        """
        super(AssetComponentTab, self).__init__(name, mngr, tab_desc=tab_desc, items_to_collapse=None)

        # variables for asset (non-ui)
        self.assets_with_versions = ["rig"]
        self.assets_supporting_update_tracking = ["audio"]
        # if asset component specified set it, otherwise use the name
        if asset_component:
            self.asset_component = asset_component
        else:
            self.asset_component = self.name

        # ui variables
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
        self.add_button(self.btn_sync_cgt)
        self.add_button(self.btn_save_config)

        self.show_only_auto_update_assets_label, self.show_only_auto_update_assets_cbox = pyani.core.ui.build_checkbox(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Show Only Assets that are Auto-Updated."
            "</span>".format(
                self.font_size,
                self.font_family
            ),
            False,
            "Shows assets that are in the auto update config file. These are the green colored assets below."
        )
        self.track_asset_changes_label, self.track_asset_changes_cbox = pyani.core.ui.build_checkbox(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Generate daily report for asset "
            "updates.</span>".format(
                self.font_size,
                self.font_family
            ),
            False,
            "Tracks updates to assets. Generates an excel report of any changed assets for the show."
        )

        self.add_general_option(self.show_only_auto_update_assets_cbox, self.show_only_auto_update_assets_label)
        # add asset changes tracking option if this component supports it
        if self.name.lower() in self.assets_supporting_update_tracking:
            self.add_button(self.btn_tracking)
            self.add_general_option(self.track_asset_changes_cbox, self.track_asset_changes_label)
            pref = self.mngr.get_preference("asset mngr", "audio", "track updates")
            if isinstance(pref, dict):
                self.track_asset_changes_cbox.setChecked(pref.get("track updates"))

        tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
        self.build_layout(tree_data, col_count, existing_assets_in_config_file)
        self.set_slots()

    def set_slots(self):
        self.tree.itemDoubleClicked.connect(self.get_notes)
        self.btn_save_config.clicked.connect(self.save_asset_update_config)
        self.btn_sync_cgt.clicked.connect(self.sync_assets_with_cgt)
        self.btn_tracking.clicked.connect(self.generate_tracking_report)
        self.show_only_auto_update_assets_cbox.clicked.connect(self._set_tree_display_mode)
        self.mngr.finished_sync_and_download_signal.connect(self.sync_finished)
        self.mngr.finished_tracking.connect(self.tracking_finished)
        self.track_asset_changes_cbox.clicked.connect(self.update_tracking_preferences)

    def sync_finished(self, asset_component):
        """
        Runs when the cgt sync finishes. the asset manager class send the signal and name of the asset component that
        was sync'd. It compares the asset component to the name of the tab so other tabs don't get this signal.
        :param asset_component: user friendly name of the asset component
        """
        if str(asset_component).lower() == self.name.lower():
            self.asset_report.generate_asset_update_report(asset_mngr=self.mngr)
            tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
            self.build_tree(tree_data, col_count, existing_assets_in_config_file)

    def tracking_finished(self, tracking_info):
        """
        Opens the excel report for the asset tracking information
        :param tracking_info: a tuple containing the asset component/category and filename of the excel report
        """
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
        """
        Creates the excel report for assets being tracked
        """
        self.mngr.check_for_new_assets(self.name.lower())

    def update_tracking_preferences(self):
        """
        Updates tracking asset preference for this asset component. Displays error if can't update, or success msg
        if successfully updated.
        """
        # get the preference name and value as a dict
        pref = self.mngr.get_preference("asset mngr", self.name.lower(), "track updates")
        # check if we have a valid preference
        if not isinstance(pref, dict):
            self.msg_win.show_error_msg("Preferences Error", "Could not get preference, error is: {0}".format(pref))
            return

        pref_name = pref.keys()[0]

        if self.track_asset_changes_cbox.isChecked():
            pref_value = True
        else:
            pref_value = False
        error = self.mngr.save_preference("asset mngr", self.name.lower(), pref_name, pref_value)
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
        assets_by_type = self._convert_tree_selection_to_assets_list_by_type(self.tree.get_tree_checked())

        # paths in the cgt cloud to the files
        asset_info_list = list()

        # get asset info for selected assets, its a list of tuples (asset type, asset component, asset name, info as
        # dict()
        for asset_type in assets_by_type:
            for asset_name in assets_by_type[asset_type]:
                asset_info_list.append(
                    self.mngr.get_asset_info_by_asset_name(asset_type, self.asset_component, asset_name)
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

        self.mngr.sync_local_cache_with_server_and_download_gui(update_data_dict=assets_dict)

    def save_asset_update_config(self):
        """
        Saves the selection to the asset update config file
        """
        updated_config_data = dict()
        # converts the tree selection to the format {asset type: [list of asset names]}
        assets_by_type = self._convert_tree_selection_to_assets_list_by_type(self.tree.get_tree_checked())

        for asset_type in assets_by_type:
            if asset_type not in updated_config_data:
                updated_config_data[asset_type] = dict()

            if self.asset_component not in updated_config_data[asset_type]:
                updated_config_data[asset_type][self.asset_component] = list()

            for asset_name in assets_by_type[asset_type]:
                updated_config_data[asset_type][self.asset_component].append(asset_name)

        error = self.mngr.update_config_file_by_component_name(self.asset_component, updated_config_data)
        if error:
            self.msg_win.show_error_msg(
                "Save Error",
                "Could not save asset update config file. Error is: {0}".format(error)
            )
        else:
            self.msg_win.show_info_msg("Saved", "The asset update config file was saved.")
        # finished saving, refresh ui
        tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
        self.build_tree(tree_data, col_count, existing_assets_in_config_file)

    def get_notes(self, item):
        """
        Gets the notes from CGT for the selected asset - double click calls this
        """
        # only process if asset component supports notes
        if not self.mngr.asset_component_supports_release_notes(self.asset_component):
            self.msg_win.show_info_msg("Notes Support", "{0} does not have notes.".format(self.name))
            pyani.core.ui.center(self.msg_win.msg_box)
            return

        # get the selection from the ui, always send column 0 because want the asset name
        selected_item = self.tree.get_item_at_position(item, 0)
        item_parent = self.tree.get_parent(item)
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
        notes_text, error = self.mngr.get_release_notes(self.asset_component, asset_name)

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

    def build_tree_data(self):
        """
        Builds data for a pyani.core.ui.CheckboxTreeWidget
        :return: a tuple where the tuple is:
        (
            a list of dicts, where dict is:
            { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] },
            the max number of columns,
            the existing assets in the config file
        )
        """
        # assets in a tree widget
        # get the assets types that have this component
        asset_types = self.mngr.get_asset_type_by_asset_component_name(self.asset_component)
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
            asset_names = self.mngr.get_assets_by_asset_component(asset_type, self.asset_component)

            asset_info_modified = dict()
            # loop through all seq/shot assets, asset info is currently a list of "seq###/shot###":asset info
            # but we want a list of seq and their shots that have the specified asset component (excludes shots
            # that don't have the asset component)
            for asset_name in asset_names:
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
                    if self.mngr.is_asset_in_update_config(
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
                asset_names = self.mngr.get_assets_by_asset_component(asset_type, self.asset_component)
                assets_list = []
                # for all asset names, make a list of tree item objects that have asset name and optionally version
                for asset_name in sorted(asset_names):
                    if self.mngr.is_asset_versioned(asset_type, self.asset_component):
                        asset_version = self.mngr.get_asset_version_from_cache(
                            asset_type,
                            self.asset_component,
                            asset_name
                        )
                        row_text = [asset_name, asset_version]
                        # will be 3 since version assets have approved and work folders and we have a column for that
                        # after version
                        col_count = 3

                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.mngr.is_asset_in_update_config(
                                asset_type, self.asset_component, asset_name
                        ):
                            # check if file doesn't exist on server - this let's user know so they don't wonder why
                            # update isn't getting any files
                            if not self.mngr.get_asset_files(asset_type, self.asset_component, asset_name):
                                # found missing file on server, set to strikeout - see pyani.core.ui.CheckboxTreeWidget
                                # for available formatting main_options_widgets
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
                            if not self.mngr.get_asset_files(asset_type, self.asset_component, asset_name):
                                # found missing file on server, set to strikeout - see pyani.core.ui.CheckboxTreeWidget
                                # for available formatting main_options_widgets
                                row_text[0] = "strikethrough:{0}".format(row_text[0])
                                row_color[0] = pyani.core.ui.GRAY_MED

                        # if version is blank put n/a
                        if row_text[1] == "":
                            row_text[1] = "n/a"

                        # check if the version on disk is older than the cloud version
                        json_data = pyani.core.util.load_json(
                            os.path.join(
                                self.mngr.get_asset_local_dir_from_cache(asset_type, self.asset_component,
                                                                         asset_name),
                                self.app_vars.cgt_metadata_filename
                            )
                        )

                        if isinstance(json_data, dict):
                            if not json_data["version"] == asset_version:
                                row_text[1] = "{0} / ({1})".format(json_data["version"], asset_version)
                                # keep the first color, but replace white with red for version
                                row_color = [row_color[0], pyani.core.ui.RED.name()]

                        # check if asset is publishable
                        if not self.mngr.is_asset_approved(asset_type, self.asset_component, asset_name):
                            row_text.append("images\\not_approved.png")
                            row_color.append("")

                    # asset is not versioned
                    else:
                        row_text = [asset_name]
                        # check if this asset is in the asset update config, meaning it gets updated automatically
                        if self.mngr.is_asset_in_update_config(
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
            unchecked_assets = self.tree.get_tree_unchecked()
            self.tree.hide_items(unchecked_assets)
            self.tree.expand_all()
        else:
            # show all items
            self.tree.show_items(None, show_all=True)
            self.tree.collapse_all()


class ToolsTab(CoreTab):
    """
    A class that provides a tab page for tools.
    """
    def __init__(self, name, mngr, tab_desc=None, tool_type=None):
        """
        :param name: the tab name, displayed on tab
        :param mngr: a tools manager object - pyani.core.mngr.tools
        :param tab_desc: a description displayed on the tab page to the left of the buttons
        :param tool_type: the tool type is the asset type, such as maya or pyanitools
        """
        super(ToolsTab, self).__init__(
            name,
            mngr,
            tab_desc=tab_desc,
            items_to_collapse=['lib', 'shortcuts', 'core']
        )

        # variables for asset (non-ui)
        self.app_vars = pyani.core.appvars.AppVars()
        self._name = name
        self.tool_type = tool_type

        # ui variables
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
        self.add_button(self.btn_sync_cgt)
        self.add_button(self.btn_wiki)
        self.add_button(self.btn_save_config)
        self.show_only_auto_update_assets_label, self.show_only_auto_update_assets_cbox = pyani.core.ui.build_checkbox(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Show Only Assets that are Auto-Updated."
            "</span>".format(
                self.font_size,
                self.font_family
            ),
            False,
            "Shows assets that are in the auto update config file. These are the green colored assets below."
        )

        self.add_general_option(self.show_only_auto_update_assets_cbox, self.show_only_auto_update_assets_label)
        tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
        self.build_layout(tree_data, col_count, existing_assets_in_config_file)
        self.set_slots()

    def set_slots(self):
        self.tree.itemDoubleClicked.connect(self.get_notes)
        self.btn_wiki.clicked.connect(self.open_confluence_page)
        self.btn_sync_cgt.clicked.connect(self.sync_tools_with_cgt)
        self.mngr.finished_sync_and_download_signal.connect(self.sync_finished)
        self.btn_save_config.clicked.connect(self.save_update_config)
        self.show_only_auto_update_assets_cbox.clicked.connect(self._set_tree_display_mode)

    def sync_finished(self, tool_category):
        """
        Runs when the cgt sync finishes. the asset manager class send the signal and name of the asset component that
        was sync'd. It compares the asset component to the name of the tab so other tabs don't get this signal.
        :param tool_category: name of the tool active_type such as Maya, user friendly name
        """
        if str(tool_category) == self.name:
            error = self.mngr.remove_files_not_on_server()
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
            error = self.mngr.update_config_file_after_sync()
            if error:
                error_msg = "Could not sync update configuration file. Error is: {0}".format(error)
                self.msg_win.show_error_msg("File Sync Warning", error_msg)

            self.asset_report.generate_asset_update_report(tools_mngr=self.mngr)
            tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
            self.build_tree(tree_data, col_count, existing_assets_in_config_file)

    def sync_tools_with_cgt(self):
        """
        Syncs the selected tools in the ui with CGT. Updates metadata like version and downloads the latest tools.
        """
        # converts the tree selection to the format {tool type: [list of tool names]}
        tools_by_cat = self._convert_tree_selection_to_tools_list_by_category(self.tree.get_tree_checked())

        # paths in the cgt cloud to the files
        tools_info_list = list()

        # get tool info for selected tools, its a list of tuples (tool type, tool component, tool name, info as
        # dict()
        for tool_type in tools_by_cat:
            for tool_name in tools_by_cat[tool_type]:
                tools_info_list.append(
                    self.mngr.get_tool_info_by_tool_name(self.tool_type, tool_type, tool_name)
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

        self.mngr.sync_local_cache_with_server_and_download_gui(tools_dict)

    def open_confluence_page(self):
        """
        opens an html page in the web browser for help.  Displays error if page(s) can't
        be opened
        """

        try:
            selection = str(self.tree.currentItem().text(0))
        except AttributeError:
            # no selection is made
            self.msg_win.show_warning_msg("Selection Error", "No tool selected. Please select a tool to view the"
                                                             " wiki page.")
            return

        # if selection isn't a tool type, then it is a tool name
        if selection not in self.mngr.get_tool_types(self.tool_type):
            error = self.mngr.open_help_doc(selection)
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
        notes = self.mngr.get_tool_release_notes(self.tool_type, tool_cat, tool_name)
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
        if self.tree.get_tree_unchecked():
            response = self.msg_win.show_question_msg(
                "Caution!",
                "Some tools are de-selected and will not auto update. Disabling a tool from auto updating is not "
                "recommended. Are you sure you want to continue?"
            )
        else:
            response = True

        if response:
            # converts the tree selection to the format {tool sub category: [list of tool names]}
            tools_by_cat = self._convert_tree_selection_to_tools_list_by_category(self.tree.get_tree_checked())

            updated_config_data = {self.tool_type: dict()}

            # builds config data to save
            for tool_cat in tools_by_cat:
                if tool_cat not in updated_config_data[self.tool_type]:
                    updated_config_data[self.tool_type][tool_cat] = list()

                for tool_name in tools_by_cat[tool_cat]:
                    updated_config_data[self.tool_type][tool_cat].append(tool_name)

            error = self.mngr.update_config_file_by_tool_type(updated_config_data)
            if error:
                self.msg_win.show_error_msg(
                    "Save Error",
                    "Could not save update config file. Error is: {0}".format(error)
                )
            else:
                self.msg_win.show_info_msg("Saved", "The update config file was saved.")
            # finished saving, refresh ui
            tree_data, col_count, existing_assets_in_config_file = self.build_tree_data()
            self.build_tree(tree_data, col_count, existing_assets_in_config_file)

    def build_tree_data(self):
        """
        Builds data for a pyani.core.ui.CheckboxTreeWidget
        :return: a tuple where the tuple is:
        (
            a list of dicts, where dict is:
            { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] },
            the max number of columns,
            the existing assets in the config file
        )
        """
        # tools in a tree widget
        tree_items = list()
        col_count = 1

        existing_tools_in_config_file = []

        for tool_category in sorted(self.mngr.get_tool_types(self.tool_type)):
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
            for tool_name in self.mngr.get_tool_names(self.tool_type, tool_category):
                row_text = [tool_name]
                cgt_version = self.mngr.get_tool_newest_version(self.tool_type, tool_category, tool_name)
                desc = self.mngr.get_tool_description(self.tool_type, tool_category, tool_name)
                if cgt_version:
                    row_text.append(cgt_version)
                else:
                    row_text.append("n/a")
                if desc:
                    row_text.append(desc)
                else:
                    row_text.append("")

                # check if this asset is in the asset update config, meaning it gets updated automatically
                if self.mngr.is_asset_in_update_config(
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
        selected_item = self.tree.get_item_at_position(tree_item_clicked, 0)
        # should be the tool type as long as a tool name was clicked
        item_parent = self.tree.get_parent(tree_item_clicked)
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
            if selected.lower() in self.mngr.get_tool_types(self.tool_type):
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
            unchecked_assets = self.tree.get_tree_unchecked()
            self.tree.hide_items(unchecked_assets)
            self.tree.expand_all()
        else:
            # show all items
            self.tree.show_items(None, show_all=True)
            self.tree.collapse_all()


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
        self.core_mngr_for_reviews = pyani.core.mngr.assets.AniCoreMngr()

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
            1000,
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
            self.review_tab = None
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
            review_desc = (
                "<p><span style='font-size:9pt; font-family:{0}; color: #ffffff;'>"
                "Options for downloading review assets from CGT. Currently only movies for animation, layout, previz "
                "nHair, nCloth, and Shot Finaling are supported.".format(self.font_family)
            )
            self.rig_tab = AssetComponentTab("Rigs", self.asset_mngr, asset_component="rig", tab_desc=asset_desc)
            self.audio_tab = AssetComponentTab("Audio", self.asset_mngr, asset_component="audio", tab_desc=asset_desc)
            self.gpu_cache_tab = AssetComponentTab("GPU Cache", self.asset_mngr, asset_component="model/cache", tab_desc=asset_desc)
            self.maya_tools_tab = ToolsTab("Maya Tools", self.tools_mngr, tool_type="maya", tab_desc=tool_desc)
            self.pyanitools_tools_tab = ToolsTab("PyAni Tools", self.tools_mngr, tool_type="pyanitools", tab_desc=tool_desc)
            self.review_tab = ReviewTab("Reviews", self.core_mngr_for_reviews, tab_desc=review_desc)

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
        self.auto_dl_hour = QtWidgets.QLineEdit("")
        self.auto_dl_hour.setMaximumWidth(40)
        self.auto_dl_min = QtWidgets.QLineEdit("")
        self.auto_dl_min.setMaximumWidth(40)
        self.btn_auto_dl_update_time = pyani.core.ui.ImageButton(
            "images\\save_pref_off.png",
            "images\\save_pref_on.png",
            "images\\save_pref_on.png",
            size=(34, 30)
        )
        # get the current time and set it
        pyani.core.ui.set_ui_time(
            self.task_scheduler, self.auto_dl_hour, self.auto_dl_min, self.auto_dl_am_pm
        )

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
        if self.review_tab:
            self.tabs.add_tab(self.review_tab.name, layout=self.review_tab.get_layout(), use_scroll_bars=True)

        self.add_layout_to_win()

    def create_layout_maint_and_options(self):
        """
        Create the layout for the hub which has the update, install, and main_options_widgets
        :return: a pyqt layout object
        """
        maint_and_options_main_layout = QtWidgets.QVBoxLayout()

        maint_and_options_main_layout.addItem(QtWidgets.QSpacerItem(1, 100))

        # this section creates the update and re-install main_options_widgets with descriptions beneath
        # and a vertical line separating the two actions
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
        options_change_time_layout.addItem(QtWidgets.QSpacerItem(10, 0))
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
        if self.tabs.get_current_tab_name() in self.asset_mngr.get_asset_component_names():
            self.asset_mngr.active_asset_component = self.tabs.get_current_tab_name()
        # get a list of tool categories and if tab is a tool active_type page set the active active_type in
        # the tool manager - note that unlike assets, we don't have a user friendly name, so we use lower
        if self.tabs.get_current_tab_name() in self.tools_mngr.get_tool_categories(display_name=True):
            self.tools_mngr.active_type = self.tabs.get_current_tab_name()

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
                # now that the task is re-enabled, get its time (note that task time is only available from windows
                # when its enabled, otherwise it returns n/a even though it saves the time.
                pyani.core.ui.set_ui_time(
                    self.task_scheduler, self.auto_dl_hour, self.auto_dl_min, self.auto_dl_am_pm
                )
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
