# Contains both command line and gui interfaces for movie creation

import os
import argparse
from colorama import Fore, Style
import pyani.media.image.seq
import pyani.media.movie.create.core
import pyani.core.util
from pyani.core.ui import QtMsgWindow
from pyani.core.ui import FileDialog
from pyani.core.appmanager import AniAppMngr

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


class AniShootGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for movie shoot creation
    :param movie_generation : the app called to create the actual movie, for example ffmpeg
    :param movie_playback : the app called to play the movie, for example Shotgun RV
    :param strict_pad : enforce the same padding for whole image sequence
    """
    def __init__(self, movie_generation, movie_playback, strict_pad):
        # build main window structure
        self.app_name = "PyShoot"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniShootGui, self).__init__("Py Shoot Movie Creator", "Resources\\pyshoot.png", self.app_mngr, 1000, 400)

        # setup data
        self.ani_vars = pyani.core.util.AniVars()
        self.shoot = pyani.media.movie.create.core.AniShoot(movie_generation, movie_playback, strict_pad)

        # disable logging by default
        pyani.core.util.logging_disabled(True)

        # setup UI widgets and layout
        # create widgets - buttons, checkboxes, etc...
        self.create_widgets()
        # connect slots
        self.set_slots()
        # layout the ui
        self.create_layout()

        self.dialog_places = self._build_places()

    def create_widgets(self):
        """Creates all the widgets used by the UI
        """
        # ----------------------
        # general options widgets
        # ----------------------
        self.generalOptionsLabel = QtWidgets.QLabel("General Options")
        self.generalOptionsLabel.setFont(self.titles)
        self.log_label = QtWidgets.QLabel("Show Log")
        self.log_cbox = QtWidgets.QCheckBox()
        self.log_cbox.setChecked(False)
        directions = 'Prints a log of the movie creation to the terminal.'
        self.log_cbox.setToolTip(directions)

        self.validate_input_label = QtWidgets.QLabel("Validate Submission. <i>(Recommended)</i>")
        self.validate_input_cbox = QtWidgets.QCheckBox()
        self.validate_input_cbox.setChecked(True)
        directions = 'Turns off validation checks. Not recommended, however for performance you can toggle off.'
        self.validate_input_cbox.setToolTip(directions)

        # ----------------------
        # image options widgets
        # ----------------------
        # open file dialog to select images
        self.imageOptionsLabel = QtWidgets.QLabel("Image Options")
        self.imageOptionsLabel.setFont(self.titles)
        self.filesBtn = QtWidgets.QPushButton("Select Images or Directory")
        self.filesBtn.setMinimumSize(150,30)
        self.filesDisplay = QtWidgets.QLineEdit("")

        # ----------------------
        # frame options widgets
        # ----------------------
        # hold frames
        self.frameOptionsLabel = QtWidgets.QLabel("Frame Options")
        self.frameOptionsLabel.setFont(self.titles)
        self.frameRangeLabel = QtWidgets.QLabel("Frame Range")
        self.frameRangeInput = QtWidgets.QLineEdit("")
        self.frameRangeInput.setMinimumWidth(300)
        directions = ("Takes a frame range (denoted with '-' or single frames (separated with commas).\n"
                      "You can combine ranges with single frames.\nUse a comma to separate (i.e. 101-105,108,120-130)"
                      )
        self.frameRangeInput.setToolTip(directions)
        # steps - default to 1, every frame
        self.stepsLabel = QtWidgets.QLabel("Steps")
        self.stepsSbox = QtWidgets.QSpinBox()
        self.stepsSbox.setMinimum(1)

        # ----------------------
        # movie options widgets
        # ----------------------
        self.movieOptionsLabel = QtWidgets.QLabel("Movie Options")
        self.movieOptionsLabel.setFont(self.titles)

        # write to path
        self.movieOutputBtn = QtWidgets.QPushButton("Select Movie Directory")
        self.movieOutputBtn.setMinimumSize(150,30)
        self.movie_output_name = QtWidgets.QLineEdit("")

        self.movie_quality_label = QtWidgets.QLabel("High Quality")
        self.movie_quality_cbox = QtWidgets.QCheckBox()
        self.movie_quality_cbox.setChecked(False)
        directions = 'Creates an uncompressed movie file.'
        self.movie_quality_cbox.setToolTip(directions)

        self.movie_overwrite_label = QtWidgets.QLabel("Overwrite if Exists")
        self.movie_overwrite_cbox = QtWidgets.QCheckBox()
        self.movie_overwrite_cbox.setChecked(True)
        directions = 'If the movie exists, overwrites the existing movie.'
        self.movie_overwrite_cbox.setToolTip(directions)

        self.movie_combine_label = QtWidgets.QLabel("Combine Sequences Into One Movie")
        self.movie_combine_cbox = QtWidgets.QCheckBox()
        self.movie_combine_cbox.setChecked(False)
        directions = ('Makes one movie out of different image sequences. Default behavior makes a movie per image'
                      ' sequence.'
                      )
        self.movie_combine_cbox.setToolTip(directions)

        self.frame_hold_label = QtWidgets.QLabel("Hold Missing Frames")
        self.frame_hold_cbox = QtWidgets.QCheckBox()
        self.frame_hold_cbox.setChecked(True)
        directions = ('Holds the previous frame until an existing frame is found. When unchecked, a missing frame'
                      'image shows. '
                      )

        self.frame_hold_cbox.setToolTip(directions)

        self.show_movies_label = QtWidgets.QLabel("View Movie(s) in RV after creation")
        self.show_movies_cbox = QtWidgets.QCheckBox()
        self.show_movies_cbox.setChecked(True)
        directions = 'Launches playback application to view movie(s)'
        self.show_movies_cbox.setToolTip(directions)

        # ----------------------
        # action button widgets
        # ----------------------
        # create the movie
        self.createBtn = QtWidgets.QPushButton('Create')
        self.createBtn.setMinimumSize(150,40)
        self.createBtn.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        # close application
        self.closeBtn = QtWidgets.QPushButton('Close')
        self.closeBtn.setMinimumSize(150,40)
        self.closeBtn.setStyleSheet("background-color:{0};".format(pyani.core.ui.GOLD))

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        # get selection which launches file dialog
        self.filesBtn.clicked.connect(self.get_sequence)
        # open dialog to select output path
        self.movieOutputBtn.clicked.connect(self.save_movie)
        # if state changes, update selection
        self.movie_combine_cbox.stateChanged.connect(self.movie_combine_update)
        # if state changes, update selection
        self.frame_hold_cbox.stateChanged.connect(self.update_hold_frame)
        # if state changes update
        self.log_cbox.stateChanged.connect(self.update_logging)
        # process options and create movie
        self.createBtn.clicked.connect(self.create_movie)
        # call close built-in function
        self.closeBtn.clicked.connect(self.close)

    def create_layout(self):
        """Build the layout of the UI
        """

        # ----------------------
        # general options
        # ----------------------
        # title
        self.main_layout.addWidget(self.generalOptionsLabel)
        self.main_layout.addItem(self.title_vert_spacer)

        # use a grid for the options so they align correctly
        gLayoutGeneralOptions = QtWidgets.QGridLayout()
        gLayoutGeneralOptions.setHorizontalSpacing(20)
        gLayoutGeneralOptions.setVerticalSpacing(15)

        # options
        gLayoutGeneralOptions.addWidget(self.log_cbox, 0, 0)
        gLayoutGeneralOptions.addWidget(self.log_label, 0, 1)
        gLayoutGeneralOptions.addWidget(self.validate_input_cbox, 1, 0)
        gLayoutGeneralOptions.addWidget(self.validate_input_label, 1, 1)

        # empty column and stretch to window
        gLayoutGeneralOptions.addItem(self.empty_space, 0, 2)
        gLayoutGeneralOptions.setColumnStretch(2, 1)
        self.main_layout.addLayout(gLayoutGeneralOptions)

        # ----------------------
        #  image options
        # ----------------------
        # add spacer
        self.main_layout.addItem(self.v_spacer)
        self.main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # title
        self.main_layout.addWidget(self.imageOptionsLabel)
        self.main_layout.addItem(self.title_vert_spacer)

        # image options spaced horizontally
        hLayoutFiles = QtWidgets.QHBoxLayout()
        hLayoutFiles.addWidget(self.filesDisplay)
        hLayoutFiles.addWidget(self.filesBtn)
        self.main_layout.addLayout(hLayoutFiles)

        # use a grid for the options so they align correctly
        gLayoutImageOptions = QtWidgets.QGridLayout()
        gLayoutImageOptions.setHorizontalSpacing(20)
        gLayoutImageOptions.setVerticalSpacing(15)

        # empty column
        gLayoutImageOptions.addItem(self.empty_space, 1, 2)
        gLayoutImageOptions.setColumnStretch(2, 1)

        self.main_layout.addLayout(gLayoutImageOptions)

        # ----------------------
        # frame options
        # ----------------------
        # add spacer
        self.main_layout.addItem(self.v_spacer)
        self.main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))

        # title
        self.main_layout.addWidget(self.frameOptionsLabel)
        self.main_layout.addItem(self.title_vert_spacer)

        # use a grid for the options so they align correctly
        gLayoutFrameOptions = QtWidgets.QGridLayout()
        gLayoutFrameOptions.setHorizontalSpacing(50)
        gLayoutFrameOptions.setVerticalSpacing(15)

        # frame range
        gLayoutFrameOptions.addWidget(self.frameRangeLabel, 0, 0)
        gLayoutFrameOptions.addWidget(self.frameRangeInput, 0, 1)
        gLayoutFrameOptions.addItem(self.horizontal_spacer, 0, 2)
        # frame step
        gLayoutFrameOptions.addWidget(self.stepsLabel, 1, 0)
        gLayoutFrameOptions.addWidget(self.stepsSbox, 1, 1)

        # empty column
        gLayoutFrameOptions.addItem(self.empty_space, 1, 2)
        gLayoutFrameOptions.setColumnStretch(2, 1)

        self.main_layout.addLayout(gLayoutFrameOptions)

        # ----------------------
        # movie options
        # ----------------------
        # add spacer
        self.main_layout.addItem(self.v_spacer)
        self.main_layout.addWidget(pyani.core.ui.QHLine(pyani.core.ui.CYAN))
        # title
        self.main_layout.addWidget(self.movieOptionsLabel)
        self.main_layout.addItem(self.title_vert_spacer)

        hLayoutMovName = QtWidgets.QHBoxLayout()
        hLayoutMovName.addWidget(self.movie_output_name)
        hLayoutMovName.addWidget(self.movieOutputBtn)
        self.main_layout.addLayout(hLayoutMovName)

        # use a grid for the options so they align correctly
        gLayoutMovieOptions = QtWidgets.QGridLayout()
        gLayoutMovieOptions.setHorizontalSpacing(20)
        gLayoutMovieOptions.setVerticalSpacing(5)

        # options
        gLayoutMovieOptions.addWidget(self.movie_quality_cbox, 0, 0)
        gLayoutMovieOptions.addWidget(self.movie_quality_label, 0, 1)
        gLayoutMovieOptions.addItem(self.horizontal_spacer, 0, 2)
        gLayoutMovieOptions.addWidget(self.movie_overwrite_cbox, 1, 0)
        gLayoutMovieOptions.addWidget(self.movie_overwrite_label, 1, 1)
        gLayoutMovieOptions.addItem(self.horizontal_spacer, 1, 2)
        gLayoutMovieOptions.addWidget(self.frame_hold_cbox, 2, 0)
        gLayoutMovieOptions.addWidget(self.frame_hold_label, 2, 1)
        gLayoutMovieOptions.addItem(self.horizontal_spacer, 2, 2)
        gLayoutMovieOptions.addWidget(self.show_movies_cbox, 3, 0)
        gLayoutMovieOptions.addWidget(self.show_movies_label, 3, 1)
        gLayoutMovieOptions.addItem(self.horizontal_spacer, 3, 2)
        gLayoutMovieOptions.addWidget(self.movie_combine_cbox, 4, 0)
        gLayoutMovieOptions.addWidget(self.movie_combine_label, 4, 1)
        gLayoutMovieOptions.addItem(self.horizontal_spacer, 4, 2)

        # empty column
        gLayoutMovieOptions.addItem(self.empty_space, 5, 2)
        gLayoutMovieOptions.setColumnStretch(2, 1)

        self.main_layout.addLayout(gLayoutMovieOptions)

        # ----------------------
        # actions
        # ----------------------
        # add spacer
        self.main_layout.addItem(self.v_spacer)
        # push buttons to bottom
        self.main_layout.addStretch(1)
        # push buttons to right
        hLayoutActions = QtWidgets.QHBoxLayout()
        hLayoutActions.addStretch(1)
        hLayoutActions.addWidget(self.createBtn)
        hLayoutActions.addWidget(self.closeBtn)
        self.main_layout.addLayout(hLayoutActions)

        self.add_layout_to_win()

    def movie_combine_update(self):
        """
        combines or separates sequences based off user input. Uses the pyani.movie.core.AniShoot class to combine
        if a sequence doesn't exist yet, just saves state and when sequence is created it will see the state and
        combine the sequence
        :return: exits after error if unsuccessful
        """
        if self.movie_combine_cbox.checkState():
            self._unlock_gui_object(self.frameRangeInput)
            self.shoot.combine_seq = True
            # try to combine, if can't report to user
            error_msg = self.shoot.combine_sequences()
            if error_msg:
                self.msg_win.show_error_msg("Invalid Selection", error_msg)
                # reset since couldn't combine
                self._lock_gui_object(self.frameRangeInput)
                self.shoot.combine_seq = False
                self.movie_combine_cbox.blockSignals(True)
                self.movie_combine_cbox.setCheckState(False)
                self.movie_combine_cbox.blockSignals(False)
                return
            # update display with combined sequence info
            self.display_gui_info()
        # unchecked, so un-combine sequences
        else:
            self._lock_gui_object(self.frameRangeInput)
            self.shoot.combine_seq = False
            self.shoot.separate_sequences()
            # update display
            self.display_gui_info()

    def update_hold_frame(self):
        """
        Sets the state of frame hold in the pyani.movie.core.AniShoot class object. Not done as a lambda
        in the slot, because then qt won't garbage collect since you reference self (i.ee the checkbox)
        """
        self.shoot.frame_hold = self.frame_hold_cbox.checkState()

    def update_logging(self):
        """Sets logging to be on or off
        """
        if self.log_cbox.checkState():
            pyani.core.util.logging_disabled(False)
        else:
            pyani.core.util.logging_disabled(True)

    def get_sequence(self):
        """
        Gets the images and builds image sequence(s). Then validates the selection and updates gui
        with the selection information like frame range
        """
        dialog = FileDialog()
        dialog.setSidebarUrls(self.dialog_places)
        dialog.exec_()
        self.file_dialog_selection = dialog.get_selection()

        # only process selection if a selection was made
        if self.file_dialog_selection:
            error_msg, self.shoot = self.ui.process_input(self.file_dialog_selection, self.shoot)
            if error_msg:
                self.msg_win.show_error_msg("Invalid Selection", error_msg)
                return

            # validate sequences
            if self.validate_input_cbox.checkState():
                msg = self.ui.validate_selection(self.shoot, int(self.stepsSbox.value()))
                if msg:
                    self.msg_win.show_error_msg("Invalid Selection", msg)
                else:
                    self.display_gui_info()
            else:
                self.display_gui_info()

            # check if frame range input should be locked, because there are multiple sequences
            if self.frameRangeInput.text() == "N/A":
                # disable so user can't change
                self._lock_gui_object(self.frameRangeInput)
            else:
                # enable so user can change
                self._unlock_gui_object(self.frameRangeInput)

    def display_gui_info(self):
        """
        displays the frame range and files selected in the qt ui. Handles single sequence selection, multiple
        sequence selection, and combined sequence selection. Displays single sequence as path.[frame range].exr
        multiple sequences displayed as path_to_multiple sequences: sequence_dir\image_name.[frame range].exr , next
        sequence and so on...
        """
        # only display info if there is a sequence
        if not self.shoot.seq_list:
            return

        # treat combined movie as a single sequence
        seq_list = self.shoot.seq_list

        # one sequence
        if len(seq_list) == 1:
            self.filesDisplay.setText(str(seq_list[0]))
            self.frameRangeInput.setText(seq_list[0].frame_range().strip("[]"))
            # special case, want the combined movie to not default to temp, where its images are, but the original
            # directory
            if self.shoot.combine_seq:
                directory = self.shoot.seq_parent_directory()
            else:
                directory = seq_list[0].directory()
            self.movie_output_name.setText("{0}.mp4".format(os.path.join(directory, seq_list[0].name)))
        # multiple sequences
        else:
            # multiple sequences share a common parent folder, so get that by going up one level in file system
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(seq_list[0].directory()), '..'))
            # build file list of sub dirs and their ranges
            seq_names = []
            for seq in seq_list:
                format_name = "{0}\{1}.{2}.{3} ".format(seq[0].dirname.split("\\")[-1], seq[0].base_name,
                                                        seq.frame_range(), seq[0].ext)
                seq_names.append(format_name)

            self.filesDisplay.setText("{0} : {1}".format(parent_dir, ', '.join(seq_names)))
            self.frameRangeInput.setText("N/A")
            self.movie_output_name.setText("{0}\[seq_shot].mp4".format(parent_dir))

    def save_movie(self):
        """Gets the file name selected from the dialog and stores in text edit box in gui"""
        name = FileDialog.getSaveFileName(self, 'Save File', options=FileDialog.DontUseNativeDialog)
        self.movie_output_name.setText(name)

    def create_movie(self):
        """Creates movie for the image sequences
        """
        frame_steps = (int(self.stepsSbox.text()))
        frame_range = str(self.frameRangeInput.text()).strip()  # remove white space
        movie_name = str(self.movie_output_name.text())
        if self.validate_input_cbox.checkState():
            msg = self.ui.validate_submission(self.shoot.seq_list,
                                              self.shoot.combine_seq,
                                              frame_range,
                                              movie_name,
                                              self.movie_overwrite_cbox.checkState())
            if msg:
                self.msg_win.show_error_msg("Invalid Option", msg)
                return False

        quality = self.movie_quality_cbox.checkState()

        movie_log, movie_list = self.shoot.create_movie(frame_steps, frame_range, movie_name, quality)
        self.msg_win.show_info_msg("Movie Report", "Created {0} Movie(s).".format(len(movie_list)))

        # open movie playback if option is checked and movie created
        if self.show_movies_cbox.checkState() and movie_list:
            self.shoot.play_movies(movie_list)

        # report movie not created
        if movie_log:
            self.msg_win.show_warning_msg("Movie Report", "Could not create some or all movie. "
                                                          "See Log for More Information.")

    @staticmethod
    def _lock_gui_object(pyqt_object):
        """
        Disable a pyqt gui object
        :param pyqt_object: The pyqt object
        """
        pyqt_object.setDisabled(True)

    @staticmethod
    def _unlock_gui_object(pyqt_object):
        """
        Disable a pyqt gui object
        :param pyqt_object: The pyqt object
        """
        pyqt_object.setDisabled(False)

    def _build_places(self):
        """returns a list of qt urls to directories in the os"""
        return [QtCore.QUrl.fromLocalFile(place) for place in self.ani_vars.places]


class AniShootCLI:
    """
    Command line version of the shoot movie creation app. Does not support multiple movie creation like
    GUI app. All other features supported.
    :param movie_generation : the app called to create the actual movie, for example ffmpeg
    :param movie_playback : the app called to play the movie, for example Shotgun RV
    :param strict_pad : enforce the same padding for whole image sequence
    """

    def __init__(self,  movie_generation, movie_playback, strict_pad):
        app_manager = AniAppMngr("PyShoot")
        self.version = app_manager.user_version

        # setup data
        self.ani_vars = pyani.core.util.AniVars()
        self.shoot = pyani.media.movie.create.core.AniShoot(movie_generation, movie_playback, strict_pad)
        self.ui = pyani.media.movie.create.core.AniShootUi()
        # disable logging by default
        pyani.core.util.logging_disabled(True)

        # get arguments from command line
        parser = self.build_parser()
        self.args = parser.parse_args()

    def run(self):
        """
        run the app
        :return log : an errors
        """
        self.show_msg("__Version__ : {0}".format(self.version), Fore.GREEN)

        # process user input and setup the image sequence
        self.process_user_input()

        image_path = os.path.normpath(self.args.img)
        # get the images selected
        self.get_sequence(image_path, self.args.steps, self.args.validate_submission)

        # create the movie
        log = self.create_movie(
            self.args.steps,
            self.args.frame_range,
            self.args.mov,
            self.args.validate_submission,
            self.args.overwrite,
            self.args.play,
            self.args.high_quality
        )

        return log

    def build_parser(self):
        """
        Create the parser with positional and keyword arguments. Also create help.
        :return: the parser
        """
        # First lets create a new parser to parse the command line arguments
        # The arguments are  displayed when a user incorrectly uses your tool or if they ask for help
        parser = argparse.ArgumentParser(
            description="Shoots movie from an image sequence",
            usage="PyShoot.exe -ng -i 'Z:\Images\Seq180\Shot_040\\' -o 'Z:\Movies\Seq180\Shot_040\my_movie.mp4'"
        )

        # Positional Arguments
        parser.add_argument('-i', '--img', help="Directory of image sequence to create movie")
        parser.add_argument('-o', '--mov', help="Name of the movie.")

        # Keyword / Optional Arguments - action is value when provided, default mis value when not provided
        parser.add_argument('-ng', '--nogui', help="Run in command line mode. By default it is gui.",
                            action="store_true", default=False)
        parser.add_argument('-fs', '--steps', help="Frame step size. Default is 1", default=1)
        parser.add_argument('-fr', '--frame_range', help="Default is frame range of image sequence.")
        parser.add_argument('-hq', '--high_quality', help="Create an uncompressed movie. Default is False.",
                            action="store_true", default=False)
        parser.add_argument('-p', '--play', help="Play the movie in the movie after creation. Uses the show "
                                                 "default movie playback tool: {0}. "
                                                 "Default is False.".format(self.shoot.movie_playback_app),
                            action="store_true", default=False)
        self._add_bool_arg(parser, "log", "Output a log to terminal.", False)
        self._add_bool_arg(parser, "validate_submission", "Check submission for errors.", True)
        self._add_bool_arg(parser, "frame_hold", "Hold missing frames.", True)
        self._add_bool_arg(parser, "overwrite", "Overwrite movie on disk.", False)
        return parser

    def process_user_input(self):
        """process the command line arguments, creating the default values for optional arguments
        """
        # check if logging should be enabled or disabled
        if self.args.log:
            pyani.core.util.logging_disabled(False)
        else:
            pyani.core.util.logging_disabled(True)

        pyani.core.util.LOG.debug("command line args {0}:".format(self.args))

        if not self.args.frame_range:
            self.args.frame_range = "N/A"

        if self.args.frame_hold:
            self.shoot.frame_hold = True
        else:
            self.shoot.frame_hold = False

        # check if images were given
        if not self.args.img:
            self.show_msg("Please provide an image sequence.", Fore.RED)

        # check if movie name given
        if not self.args.mov:
            self.show_msg("Please provide a movie name.", Fore.RED)

    def get_sequence(self, images, steps, validate):
        """
        Build an image sequence
        :param images: a set of images
        :param steps: the frame step size
        :param validate: check image selection as boolean
        """
        # build the sequence
        if not isinstance(images, list):
            images = [images]
        error_msg, self.shoot = self.ui.process_input(images, self.shoot)
        if error_msg:
            self.show_msg(error_msg, Fore.RED)
            return

        # validate sequence
        if validate:
            msg = self.ui.validate_selection(self.shoot, int(steps))
            if msg:
                self.show_msg(msg, Fore.RED)
                return

    def create_movie(self, steps, frame_range, movie_name, validate, overwrite, play_movie, quality):
        """
        Creates a movie from an image sequence
        :param steps: frame steps as int
        :param frame_range: frame range as string, accepts ###-### and ###,### or a combination ###,###-###
        :param movie_name: output path for movie
        :param validate: check submission before creating as boolean
        :param overwrite: overwrite movie if exists
        :param play_movie: play the movie after creation as boolean
        :param quality: compressed or uncompressed movie as a boolean
        :return movie_log : a log of any errors
        """
        frame_steps = int(steps)
        frame_range = frame_range.strip()  # remove white space

        movie_name = os.path.normpath(movie_name)
        movie_path = os.path.dirname(movie_name)

        # make directory if doesn't exist - makes all directories in path if missing
        pyani.core.util.make_all_dir_in_path(movie_path)

        if validate:
            msg = self.ui.validate_submission(self.shoot.seq_list,
                                              self.shoot.combine_seq,
                                              frame_range,
                                              movie_name,
                                              overwrite)
            if msg:
                self.show_msg(msg, Fore.RED)
                return False

        movie_log, movie_list = self.shoot.create_movie(frame_steps, frame_range, movie_name, quality)
        # report movie creation, since no multi-movie support in command line, always just one movie created
        if movie_log:
            self.show_msg("Could not create movie: {0}.".format(movie_log), Fore.RED)
        else:
            self.show_msg("Created movie: {0}.".format(movie_list[0]), Fore.GREEN)

        # open movie playback if option is checked and movie created
        if play_movie and movie_list:
            self.shoot.play_movies(movie_list)

        return movie_log

    @staticmethod
    def show_msg(msg, color=Fore.WHITE):
        """
        Shows message in the console
        :param msg: the message to display
        :param color: text color, default is white
        """
        print ("{0}{1}".format(color, msg))
        print(Style.RESET_ALL)

    @staticmethod
    def _add_bool_arg(parser, name, help, default=False):
        """
        Helper function to create a mutually exclusive group argument. For example:
        create --feature, and --no-feature, one is True, other is False.
        :param parser: the argparser instance
        :param name: argument name
        :param help: the help message
        :param default: default value if not supplied
        """
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument('--' + name, dest=name, help=help, action='store_true')
        group.add_argument('--no-' + name, dest=name, help=help, action='store_false')
        parser.set_defaults(**{name: default})