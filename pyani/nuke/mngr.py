import os
import pyani.core.util
import pyani.core.ui
from pyani.core.appmanager import AppManager

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore

# TODO: ready to check for install, and populate with real data, and provide functionality, gui done!
class AniNukeMngr(object):
    def __init__(self):
        self.ani_vars = pyani.core.util.AniVars()
        self.__sequences = self.ani_vars.get_sequence_list()
        self.__plugins = ["pGrad \t\tv1.0", "pAtmos \t\tv3.1", "AOV_CC \t\tv2.2", "Asset_Delivery \t\tv0.5"]
        self.__scripts = ["menu"]
        self.__templates = ["shot", "asset", "mpaint", "fx", "optical", "output"]
        self.__shots = ["shot040", "shot090","shot125","shot280"]

    @property
    def plugins(self):
        return self.__plugins

    @property
    def scripts(self):
        return self.__scripts

    @property
    def templates(self):
        return self.__templates

    @property
    def sequences(self):
        return self.__sequences

    def shots(self, seq):
        return self.ani_vars.get_shot_list(seq)

    def get_all_localized_plugins(self, seq):
        return self._find_shot_plugins("poop")

    def _find_shot_plugins(self, shot):
        return ["pGrad", "pAtmos"]


class AniNukeMngrGui(QtWidgets.QMainWindow):
    def __init__(self, version):
        super(AniNukeMngrGui, self).__init__()

        self.nuke_mngr = AniNukeMngr()

        self.__version = version
        self.win_utils = pyani.core.ui.QtWindowUtil(self)

        self.setWindowTitle('Py Nuke Manager')
        self.win_utils.set_win_icon("Resources\\pynukemngr.png")
        # main widget for window
        self.main_win = QtWidgets.QWidget()
        # main layout
        self.stacked_layout_for_windows = QtWidgets.QStackedLayout()
        # sub layouts
        self.main_app_widget = QtWidgets.QWidget()
        self.install_app_widget = QtWidgets.QWidget()
        # main ui elements - styling set in the create ui functions
        self.btn_install = QtWidgets.QPushButton("Install App")
        self.btn_seq_setup = QtWidgets.QPushButton("Setup Sequence")
        self.btn_seq_update= QtWidgets.QPushButton("Update Sequence")
        self.btn_shot_local = QtWidgets.QPushButton("Localize")
        self.btn_shot_unlocal = QtWidgets.QPushButton("Un-Localize")
        self.seq_update_tree = pyani.core.ui.build_checkbox_tree(
            ["Plugins", "Scripts", "Templates"],
            [self.nuke_mngr.plugins, self.nuke_mngr.scripts, self.nuke_mngr.templates],
            expand=False
        )
        self.shot_update_tree = pyani.core.ui.build_checkbox_tree(
            # todo - initially show nothing, then once select seq populate - self.nuke_mngr.shots(seq)
            ["s05", "s40"],
            self.nuke_mngr.get_all_localized_plugins("Seq180")
        )

        self.msg_win = pyani.core.ui.QtMsgWindow(self)

        self.build_ui()
        # set default window size
        self.resize(600, 400)

        # version management
        app_manager = AppManager.version_manager(
            "PyNukeMngr",
            "C:\\PyAniTools\\PyNukeMngr\\",
            "Z:\\LongGong\\PyAniTools\\app_data\\"
        )
        msg = app_manager.version_check()
        if msg:
            self.msg_win.show_info_msg("Version Update", msg)

    @property
    def version(self):
        """Return the app version
        """
        return self.__version

    def build_ui(self):
        """Builds the UI widgets, slots and layout
        """

        # TODO: skip if already installed

        self.create_ui_install()

        self.create_ui_main()

        self.set_slots()

        # add sub windows / layouts to stack layout
        self.stacked_layout_for_windows.addWidget(self.install_app_widget)
        self.stacked_layout_for_windows.addWidget(self.main_app_widget)
        # set main windows layout as the stacked layout
        self.main_win.setLayout(self.stacked_layout_for_windows)
        # set main window
        self.setCentralWidget(self.main_win)

    def create_ui_install(self):
        """Creates all the widgets used by the UI and build layout
        """
        # install button
        self.btn_install.setFixedSize(150, 40)
        self.btn_install.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))

        instructions = QtWidgets.QLabel("Welcome to Nuke Manager. Please install the app to \n"
                                        "continue. Installation is quick and only runs once. \n"
                                        "After installation the main app will launch.\n")

        # Grid layout for install screen
        g_layout_ins = QtWidgets.QGridLayout()
        g_layout_ins.setColumnStretch(0, 1)
        g_layout_ins.setColumnStretch(2, 1)
        g_layout_ins.setRowStretch(0, 1)
        g_layout_ins.setRowStretch(3, 1)
        g_layout_ins.addWidget(instructions, 1, 1)
        g_layout_ins.addWidget(self.btn_install, 2, 1, QtCore.Qt.AlignCenter)
        self.install_app_widget.setLayout(g_layout_ins)

    def create_ui_main(self):
        # set font size and style for title labels
        titles = QtGui.QFont()
        titles.setPointSize(14)
        titles.setBold(True)

        # spacer to use between sections
        v_spacer = QtWidgets.QSpacerItem(0, 35)
        # use this to space grid elements vertically
        g_layout_vert_item_spacing = 5

        # begin layout
        main_layout = QtWidgets.QVBoxLayout()

        # add version to right side of screen
        vers_label = QtWidgets.QLabel("Version {0}".format(self.version))
        h_layout_vers = QtWidgets.QHBoxLayout()
        h_layout_vers.addStretch(1)
        h_layout_vers.addWidget(vers_label)
        main_layout.addLayout(h_layout_vers)
        main_layout.addItem(v_spacer)

        # SEQUENCE SETUP -----------------------------------
        # title
        g_layout_seq_setup = QtWidgets.QGridLayout()
        seq_setup_title = QtWidgets.QLabel("Sequence Setup")
        seq_setup_title.setFont(titles)
        self.btn_seq_setup.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_seq_setup.setMinimumSize(150, 30)
        g_layout_seq_setup.addWidget(seq_setup_title, 0, 0)
        g_layout_seq_setup.setColumnStretch(0, 1)
        g_layout_seq_setup.addWidget(self.btn_seq_setup, 0, 2)
        main_layout.addLayout(g_layout_seq_setup)
        main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # layout for options
        g_layout_seq_setup_opt = QtWidgets.QGridLayout()
        g_layout_seq_setup_opt.setHorizontalSpacing(20)
        g_layout_seq_setup_opt.setVerticalSpacing(g_layout_vert_item_spacing)
        # options
        seq_select_label = QtWidgets.QLabel("Select Sequence")
        seq_select_menu = QtWidgets.QComboBox()
        seq_select_menu.addItem("------")
        for seq in self.nuke_mngr.sequences:
            seq_select_menu.addItem(seq)

        copy_gizmos_cbox_label, copy_gizmos_cbox = pyani.core.ui.build_checkbox(
            "Copy Gizmos",
            True,
            "Copy Gizmos from the show to the sequence library"
        )
        copy_scripts_cbox_label, copy_scripts_cbox = pyani.core.ui.build_checkbox(
            "Copy Scripts",
            True,
            "Copy Scripts from the show to the sequence library"
        )
        copy_template_cbox_label, copy_template_cbox = pyani.core.ui.build_checkbox(
            "Create Shot Nuke Comps",
            True,
            "Copy the show's nuke comp template to all shots in the sequence"
        )

        # use a list with a for loop to layout, don't have to keep changing rows and column numbers
        # when want to re-order, just change in list below
        # list of the widgets, put in order that they should be added
        widget_list = [(seq_select_label, seq_select_menu),
                       (copy_gizmos_cbox_label, copy_gizmos_cbox),
                       (copy_scripts_cbox_label, copy_scripts_cbox),
                       (copy_template_cbox_label, copy_template_cbox)]
        # layout the widgets
        row = col = 0
        for widget in widget_list:
            label, widget = widget
            g_layout_seq_setup_opt.addWidget(label, row, col)
            g_layout_seq_setup_opt.addWidget(widget, row, col+1)
            row += 1
        main_layout.addLayout(g_layout_seq_setup_opt)
        main_layout.addItem(v_spacer)

        # UPDATE SEQUENCE -----------------------------------
        g_layout_seq_update = QtWidgets.QGridLayout()
        seq_update_title = QtWidgets.QLabel("Sequence Update")
        seq_update_title.setFont(titles)
        self.btn_seq_update.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_seq_update.setMinimumSize(150, 30)
        g_layout_seq_update.addWidget(seq_update_title, 0, 0)
        g_layout_seq_update.setColumnStretch(0, 1)
        g_layout_seq_update.addWidget(self.btn_seq_update, 0, 2)
        main_layout.addLayout(g_layout_seq_update)
        main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        main_layout.addWidget(self.seq_update_tree)
        main_layout.addItem(v_spacer)

        # UPDATE SHOT -----------------------------------
        # title
        g_layout_shot_update = QtWidgets.QGridLayout()
        shot_update_title = QtWidgets.QLabel("Shot Update")
        shot_update_title.setFont(titles)
        self.btn_shot_local.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_shot_local.setMinimumSize(150, 30)
        self.btn_shot_unlocal.setStyleSheet("background-color:{0};".format(pyani.core.ui.GOLD))
        self.btn_shot_unlocal.setMinimumSize(150, 30)
        g_layout_shot_update.addWidget(shot_update_title, 0, 0)
        g_layout_shot_update.setColumnStretch(0, 1)
        g_layout_shot_update.addWidget(self.btn_shot_local, 0, 2)
        g_layout_shot_update.addWidget(self.btn_shot_unlocal, 0, 3)
        main_layout.addLayout(g_layout_shot_update)
        main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # layout for options
        g_layout_shot_update_opt = QtWidgets.QGridLayout()
        g_layout_shot_update_opt.setHorizontalSpacing(20)
        g_layout_shot_update_opt.setVerticalSpacing(g_layout_vert_item_spacing)
        # options
        shot_select_label = QtWidgets.QLabel("Select Shot")
        shot_select_menu = QtWidgets.QComboBox()
        shot_select_menu.addItem("-------")
        shot_select_menu.addItem("Shot040")
        shot_select_menu.addItem("Shot090")
        show_local_cbox_label, show_local_cbox = pyani.core.ui.build_checkbox(
            "Show Only Localized Plugins",
            True,
            "Show only shots that have copies of the sequence Gizmos and Plugins"
        )
        widget_list = [(shot_select_label, shot_select_menu),
                       (show_local_cbox_label, show_local_cbox)]
        # layout the widgets
        row = col = 0
        for widget in widget_list:
            label, widget = widget
            g_layout_shot_update_opt.addWidget(label, row, col)
            g_layout_shot_update_opt.addWidget(widget, row, col + 1)
            row += 1
        main_layout.addLayout(g_layout_shot_update_opt)
        main_layout.addWidget(self.shot_update_tree)
        # add the layout to the main app widget
        self.main_app_widget.setLayout(main_layout)

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_install.clicked.connect(self.install)
        self.btn_seq_update.clicked.connect(self.seq_update)

    def install(self):
        # finished install show main app screen
        self.stacked_layout_for_windows.setCurrentIndex(1)
        self.resize(1000, 1000)

    def seq_update(self):
        checked_items = pyani.core.ui.get_tree_checked(self.seq_update_tree)
        print checked_items
