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
            self.current_session_label = QtWidgets.QLabel()
            self._update_session_label()
            self.seq_select_menu = QtWidgets.QComboBox()
            self.seq_select_menu.addItem("------")
            self.seq_select_menu.addItem("non-prod")
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
        self.main_layout.addWidget(self.current_session_label)

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
        seq = str(self.seq_select_menu.currentText())
        if not seq == "non-prod" and not self.seq_select_menu.currentIndex() == 0:
            self.ani_vars.update(seq)
            self.shot_select_menu.clear()
            self.shot_select_menu.addItem("------")
            for shot in sorted(self.ani_vars.get_shot_list()):
                self.shot_select_menu.addItem(shot)
        else:
            self.shot_select_menu.clear()

    def set_environment_vars(self):
        """sets the session object. Displays warnign if invalid selection or if session could not be created
        """
        # make sure both launch methods aren't selected
        seq_index = self.seq_select_menu.currentIndex()
        shot_index = self.shot_select_menu.currentIndex()
        if str(self.seq_select_menu.currentText()) == "non-prod":
            seq = "non-prod"
            shot = "non-prod"
        else:
            if (seq_index == 0 or seq_index == -1) or (shot_index == 0 or shot_index == -1):
                self.msg_win.show_error_msg("Error", "Please select a sequence and a shot")
                return
            seq = str(self.seq_select_menu.currentText())
            shot = str(self.shot_select_menu.currentText())
        error = self.session.set_session(seq, shot)
        if error:
            self.msg_win.show_error_msg("Error", "Could not set session up. Error is {0}".format(error))
            return
        self._update_session_label()
        self.msg_win.show_info_msg("Session Created", "The session was successfully created.")

    def _update_session_label(self):
        """
        Gets the session and stores in the label so user knows what the current session is
        """
        # get session
        current_session = self.session.get_session()
        if not isinstance(current_session, dict):
            error = "Could not get session. Error is {0}".format(current_session)
            logger.error(error)
            self.current_session_label.setText("<b>Current Session:</b> Could not get active session data.")
        else:
            sequence = current_session['core']['seq']
            shot = current_session['core']['shot']
            if sequence == "non-prod":
                self.current_session_label.setText("<b>Current Session:</b> Not in a shot environment. Will use show "
                                                   "level data for session.")
            else:
                self.current_session_label.setText("<b>Current Session:</b> {0}, {1}".format(sequence, shot))
