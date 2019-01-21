import os
import logging
import pyani.core.util
import pyani.core.ui
import pyani.core.appmanager
from pyani.core.appsession import AniSession
import pyani.core.anivars

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets


logger = logging.getLogger()


class AniSessionGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for launching nuke in a shot environment
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """
    def __init__(self, error_logging):
        self.log = []

        # build main window structure
        self.app_name = "PySession"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniSessionGui, self).__init__(
            "Py Session",
            "Resources\pysession.png",
            self.app_mngr,
            600,
            400,
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

        self.ani_vars = pyani.core.anivars.AniVars()

        # this holds the session variables - other apps may access
        self.session = AniSession()

        error = self.session.create_session()
        # if can't create session, exit, can't continue
        if error:
            self.msg_win.show_error_msg("Critical Error", "Could not create session, Error is: {0}".format(error))
            return

        error = self.ani_vars.load_seq_shot_list()
        # if can't load sequence shot list exit, critical, needed to launch nuke
        if error:
            self.msg_win.show_error_msg("Critical Error", "A critical error occurred: {0}".format(error))
        else:
            # main ui elements - styling set in the create ui functions
            self.btn_set_session = QtWidgets.QPushButton("Activate Session")

            self.seq_select_menu = QtWidgets.QComboBox()
            self.seq_select_menu.addItem("------")
            for seq in sorted(self.ani_vars.get_sequence_list()):
                self.seq_select_menu.addItem(seq)
            self.shot_select_menu = QtWidgets.QComboBox()

            self.create_layout()
            self.set_slots()

    def create_layout(self):

        # APP HEADER SETUP -----------------------------------
        # |    label    |   space    |      btn       |
        h_layout_header = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Application Session")
        header_label.setFont(self.titles)
        h_layout_header.addWidget(header_label)
        h_layout_header.addStretch(1)
        self.btn_set_session.setMinimumSize(150, 30)
        self.btn_set_session.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        h_layout_header.addWidget(self.btn_set_session)
        self.main_layout.addLayout(h_layout_header)
        self.main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        self.main_layout.addItem(self.v_spacer)

        #  OPTIONS
        options_menu_label = QtWidgets.QLabel("Select a sequence and shot using the menu boxes. This will allow apps "
                                              "to take advantage of a sequence and shot number.")
        self.main_layout.addWidget(options_menu_label)
        h_layout_menus_seq = QtWidgets.QHBoxLayout()
        seq_label = QtWidgets.QLabel("Sequence")
        h_layout_menus_seq.addWidget(seq_label)
        h_layout_menus_seq.addWidget(self.seq_select_menu)
        self.main_layout.addLayout(h_layout_menus_seq)

        h_layout_menus_shot = QtWidgets.QHBoxLayout()
        shot_label = QtWidgets.QLabel("Shot")
        h_layout_menus_shot.addWidget(shot_label)
        h_layout_menus_shot.addWidget(self.shot_select_menu)
        self.main_layout.addLayout(h_layout_menus_shot)

        self.main_layout.addItem(self.v_spacer)

        # set main windows layout as the stacked layout
        self.add_layout_to_win()

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.btn_set_session.clicked.connect(self.set_environment_vars)
        self.seq_select_menu.currentIndexChanged.connect(self.update_shot_list)

    def update_shot_list(self):
        """
        Build the shot menu
        """
        self.ani_vars.update(str(self.seq_select_menu.currentText()))
        self.shot_select_menu.clear()
        self.shot_select_menu.addItem("------")
        for shot in sorted(self.ani_vars.get_shot_list()):
            self.shot_select_menu.addItem(shot)

    def set_environment_vars(self):
        """sets the session object. Displays warnign if invalid selection or if session could not be created
        """
        # make sure both launch methods aren't selected
        seq_index = self.seq_select_menu.currentIndex()
        shot_index = self.shot_select_menu.currentIndex()
        if (seq_index == 0 or seq_index == -1) or (shot_index == 0 or shot_index == -1) :
            self.msg_win.show_error_msg("Error", "Please select a sequence and a shot")
            return

        error = self.session.set_session(
            str(self.seq_select_menu.currentText()),
            str(self.shot_select_menu.currentText())
        )
        if error:
            self.msg_win.show_error_msg("Error", "Could not set session up. Error is {0}".format(error))
            return

        self.msg_win.show_info_msg("Session Created","The session was successfully created.")