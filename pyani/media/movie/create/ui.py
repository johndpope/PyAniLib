# Contains both command line and gui interfaces for movie creation

import os
import argparse
import logging
from colorama import Fore, Style
import pyani.media.image.seq
import pyani.media.image.core
import pyani.media.movie.create.core
import pyani.core.util
from pyani.core.ui import QtMsgWindow
from pyani.core.ui import FileDialog
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.mngr.tools

logger = logging.getLogger()

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore


class AniShootGui(pyani.core.ui.AniQMainWindow):
    """
    Gui class for movie shoot creation
    :param movie_generation : the app called to create the actual movie, for example ffmpeg
    :param movie_playback : the app called to play the movie, for example Shotgun RV
    :param strict_pad : enforce the same padding for whole image sequence
    :param error_logging : error log class from trying to create logging in main program
    """
    def __init__(self, movie_generation, movie_playback, strict_pad, error_logging):
        # managers for handling tools
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        app_name = "pyShoot"
        app_vars = pyani.core.appvars.AppVars()
        tool_metadata = {
            "name": app_name,
            "dir": app_vars.local_pyanitools_apps_dir,
            "type": "pyanitools",
            "category": "apps"
        }

        # pass win title, icon path, app manager, width and height
        super(AniShootGui, self).__init__(
            "Py Shoot Movie Creator",
            "Resources\\pyshoot_icon.ico",
            tool_metadata,
            self.tools_mngr,
            1000,
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

        # setup data
        self.ani_vars = pyani.core.anivars.AniVars()
        self.shoot = pyani.media.movie.create.core.AniShoot(movie_generation, movie_playback, strict_pad)
        self.ui = pyani.media.movie.create.core.AniShootUi()

        # progress updating
        self.progress_update = QtWidgets.QProgressDialog("Task in Progress...", "Cancel", 0, 100)

        # ui elements
        self.files_button = QtWidgets.QPushButton("Select Images or Directory")
        self.frame_range_input = QtWidgets.QLineEdit("")
        self.files_display = QtWidgets.QLineEdit("")
        self.steps_sbox = QtWidgets.QSpinBox()
        self.movie_output_button = QtWidgets.QPushButton("Select Movie Directory and Name")
        self.movie_output_name = QtWidgets.QLineEdit("")
        self.create_button = QtWidgets.QPushButton('Create')
        self.close_button = QtWidgets.QPushButton('Close')

        # labels
        self.images_options_img =  pyani.core.ui.Image("images\\image_options.png")
        self.frame_options_img =  pyani.core.ui.Image("images\\frame_options.png")
        self.movie_options_img =  pyani.core.ui.Image("images\\movie_options.png")

        # buttons
        self.btn_select_images = pyani.core.ui.ImageButton(
            "images\\select_images_off.png",
            "images\\select_images_on.png",
            "images\\select_images_on.png",
            size=(62, 84)
        )
        # buttons
        self.btn_save_movie = pyani.core.ui.ImageButton(
            "images\\save_movie_off.png",
            "images\\save_movie_on.png",
            "images\\save_movie_on.png",
            size=(62, 84)
        )
        # buttons
        self.btn_create_movie = pyani.core.ui.ImageButton(
            "images\\create_off.png",
            "images\\create_on.png",
            "images\\create_on.png",
            size=(216, 86)
        )

        # defined later using ui function in create layout()
        self.movie_quality_cbox = None
        self.movie_combine_cbox = None
        self.frame_hold_cbox = None
        self.show_movies_cbox = None
        self.image_file_selection = None

        # set to allow drag and drop
        self.setAcceptDrops(True)

        # layout the ui
        self.create_layout()
        # connect slots
        self.set_slots()

        self.dialog_places = self._build_places()

    def create_layout(self):
        """Build the layout of the UI
        """

        # push buttons to right
        h_layout_actions = QtWidgets.QHBoxLayout()
        h_layout_actions.addStretch(1)
        h_layout_actions.addWidget(self.btn_create_movie)
        h_layout_actions.addItem(QtWidgets.QSpacerItem(40, 0))
        self.main_layout.addLayout(h_layout_actions)
        # add spacer
        self.main_layout.addItem(QtWidgets.QSpacerItem(0, 75))

        # ----------------------
        #  image options
        # ----------------------
        # title
        self.main_layout.addWidget(self.images_options_img)

        # image options spaced horizontally
        h_layout_files = QtWidgets.QHBoxLayout()
        h_layout_files.addWidget(self.files_display)
        h_layout_files.addItem(QtWidgets.QSpacerItem(30, 0))
        h_layout_files.addWidget(self.btn_select_images)
        h_layout_files.addItem(QtWidgets.QSpacerItem(40, 0))
        self.main_layout.addLayout(h_layout_files)

        # ----------------------
        # frame options
        # ----------------------
        # hold frames
        frame_range_label = QtWidgets.QLabel("Frame Range")
        self.frame_range_input.setMinimumWidth(300)
        directions = ("Takes a frame range (denoted with '-' or single frames (separated with commas).\n"
                      "You can combine ranges with single frames.\nUse a comma to separate (i.e. 101-105,108,120-130)"
                      )
        self.frame_range_input.setToolTip(directions)
        # steps - default to 1, every frame
        steps_label = QtWidgets.QLabel("Steps")
        self.steps_sbox.setMinimum(1)

        # add spacer
        self.main_layout.addItem(QtWidgets.QSpacerItem(0, 25))
        # title
        self.main_layout.addWidget(self.frame_options_img)
        # add spacer
        self.main_layout.addItem(QtWidgets.QSpacerItem(0, 25))
        # use a grid for the options so they align correctly
        g_layout_frame_options = QtWidgets.QGridLayout()
        g_layout_frame_options.setHorizontalSpacing(50)
        g_layout_frame_options.setVerticalSpacing(15)
        # frame range
        g_layout_frame_options.addWidget(frame_range_label, 0, 0)
        g_layout_frame_options.addWidget(self.frame_range_input, 0, 1)
        g_layout_frame_options.addItem(self.horizontal_spacer, 0, 2)
        # frame step
        g_layout_frame_options.addWidget(steps_label, 1, 0)
        g_layout_frame_options.addWidget(self.steps_sbox, 1, 1)
        # empty column
        g_layout_frame_options.addItem(self.empty_space, 1, 2)
        g_layout_frame_options.setColumnStretch(2, 1)

        self.main_layout.addLayout(g_layout_frame_options)

        # ----------------------
        # movie options
        # ----------------------
        self.movie_output_button.setMinimumSize(150, 30)
        movie_quality_label, self.movie_quality_cbox = pyani.core.ui.build_checkbox(
            "High Quality",
            False,
            'Creates an uncompressed movie file.'
        )
        movie_combine_label, self.movie_combine_cbox = pyani.core.ui.build_checkbox(
            "Combine Sequences Into One Movie",
            False,
            'Makes one movie out of different image sequences. Default behavior makes a movie per image sequence.'
        )
        frame_hold_label, self.frame_hold_cbox = pyani.core.ui.build_checkbox(
            "Hold Missing Frames",
            True,
            "Holds the previous frame until an existing frame is found. When unchecked, a missing frame image shows."
        )
        show_movies_label, self.show_movies_cbox = pyani.core.ui.build_checkbox(
            "View Movie(s) in RV after creation",
            True,
            "Launches playback application to view movie(s)"
        )

        # add spacer
        self.main_layout.addItem(QtWidgets.QSpacerItem(0, 50))
        # title
        self.main_layout.addWidget(self.movie_options_img)

        h_layout_mov_name = QtWidgets.QHBoxLayout()
        h_layout_mov_name.addWidget(self.movie_output_name)
        h_layout_mov_name.addItem(QtWidgets.QSpacerItem(30, 0))
        h_layout_mov_name.addWidget(self.btn_save_movie)
        h_layout_mov_name.addItem(QtWidgets.QSpacerItem(40, 0))
        self.main_layout.addLayout(h_layout_mov_name)

        # use a grid for the options so they align correctly
        g_layout_movie_options = QtWidgets.QGridLayout()
        g_layout_movie_options.setHorizontalSpacing(20)
        g_layout_movie_options.setVerticalSpacing(5)

        # options
        g_layout_movie_options.addWidget(self.movie_quality_cbox, 0, 0)
        g_layout_movie_options.addWidget(movie_quality_label, 0, 1)
        g_layout_movie_options.addItem(self.horizontal_spacer, 0, 2)
        g_layout_movie_options.addWidget(self.frame_hold_cbox, 1, 0)
        g_layout_movie_options.addWidget(frame_hold_label, 1, 1)
        g_layout_movie_options.addItem(self.horizontal_spacer, 1, 2)
        g_layout_movie_options.addWidget(self.show_movies_cbox, 2, 0)
        g_layout_movie_options.addWidget(show_movies_label, 2, 1)
        g_layout_movie_options.addItem(self.horizontal_spacer, 2, 2)
        g_layout_movie_options.addWidget(self.movie_combine_cbox, 3, 0)
        g_layout_movie_options.addWidget(movie_combine_label, 3, 1)
        g_layout_movie_options.addItem(self.horizontal_spacer, 3, 2)

        # empty column
        g_layout_movie_options.addItem(self.empty_space, 5, 2)
        g_layout_movie_options.setColumnStretch(2, 1)

        self.main_layout.addLayout(g_layout_movie_options)

        # add spacer
        self.main_layout.addItem(self.v_spacer)
        self.add_layout_to_win()

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        # get selection which launches file dialog
        self.btn_select_images.clicked.connect(self.load_file_dialog)
        # open dialog to select output path
        self.btn_save_movie.clicked.connect(self.save_movie)
        # if state changes, update selection
        self.movie_combine_cbox.stateChanged.connect(self.movie_combine_update)
        # if state changes, update selection
        self.frame_hold_cbox.stateChanged.connect(self.update_hold_frame)
        # process options and create movie
        self.btn_create_movie.clicked.connect(self.create_movie)

    def dropEvent(self, e):
        """
        called when the drop is completed when dragging and dropping,
        calls wrapper which gets mime data and calls self.load passing mime data to it
        generic use lets other windows use drag and drop with whatever function they need
        :param e: event mime data
        """
        self.drop_event_wrapper(e, self.load_drag_drop)

    def closeEvent(self, event):
        """
        Custom close window event
        :param event: the window close event
        """
        self.shoot.cleanup()

    def movie_combine_update(self):
        """
        combines or separates sequences based reset user input. Uses the pyani.movie.core.AniShoot class to combine
        if a sequence doesn't exist yet, just saves state and when sequence is created it will see the state and
        combine the sequence
        :return: exits after error if unsuccessful
        """
        if self.movie_combine_cbox.checkState():
            self.progress_update.setLabelText("Combining Sequences...")
            self.progress_update.show()
            QtWidgets.QApplication.processEvents()

            self._unlock_gui_object(self.frame_range_input)
            self.shoot.combine_seq = True
            # try to combine, if can't report to user
            error_msg = self.shoot.combine_sequences(self.progress_update)
            if error_msg:
                self.msg_win.show_error_msg("Invalid Selection", error_msg)
                # reset since couldn't combine
                self._lock_gui_object(self.frame_range_input)
                self.shoot.combine_seq = False
                self.movie_combine_cbox.blockSignals(True)
                self.movie_combine_cbox.setCheckState(False)
                self.movie_combine_cbox.blockSignals(False)
                return
            # update display with combined sequence info
            self.display_gui_info()

            self.progress_update.setLabelText("Finished Combining Sequences")
            self.progress_update.hide()
            QtWidgets.QApplication.processEvents()
        # unchecked, so un-combine sequences
        else:
            self._lock_gui_object(self.frame_range_input)
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

    def load_file_dialog(self):
        dialog = FileDialog()
        dialog.setSidebarUrls(self.dialog_places)
        dialog.exec_()
        self.image_file_selection = dialog.get_selection()
        # only process selection if a selection was made
        if self.image_file_selection:
            self.get_sequence()

    def load_drag_drop(self, file_names):
        self.image_file_selection = sorted([os.path.normpath(file_name) for file_name in file_names])
        if self.image_file_selection:
            self.get_sequence()

    def get_sequence(self):
        """
        Gets the images and builds image sequence(s). Then validates the selection and updates gui
        with the selection information like frame range
        """
        error_msg = self.ui.process_input(self.image_file_selection, self.shoot)
        if error_msg:
            self.msg_win.show_error_msg("Invalid Selection", error_msg)
            return

        # validate sequences
        msg = self.ui.validate_selection(self.shoot, int(self.steps_sbox.value()))
        if msg:
            self.msg_win.show_error_msg("Invalid Selection", msg)
        else:
            self.display_gui_info()

        # check if frame range input should be locked, because there are multiple sequences
        if self.frame_range_input.text() == "N/A":
            # disable so user can't change
            self._lock_gui_object(self.frame_range_input)
        else:
            # enable so user can change
            self._unlock_gui_object(self.frame_range_input)

    def display_gui_info(self):
        """
        displays the frame range and files selected in the qt ui. Handles single sequence selection, multiple
        sequence selection, and combined sequence selection. Displays single sequence as path.[frame range].exr
        multiple sequences displayed as path_to_multiple sequences: sequence_dir\image_name.[frame range].exr , next
        sequence and so on...

        Displays and logs error if cannot parse directory paths
        """
        # only display info if there is a sequence
        if not self.shoot.seq_list:
            return

        # treat combined movie as a single sequence
        seq_list = self.shoot.seq_list

        # one sequence
        if len(seq_list) == 1:
            self.files_display.setText(str(seq_list[0]))
            self.frame_range_input.setText(seq_list[0].frame_range().strip("[]"))
            # special case, want the combined movie to not default to temp, where its images are, but the original
            # directory
            if self.shoot.combine_seq:
                directory = self.shoot.seq_parent_directory()
            else:
                directory = seq_list[0].directory()

            if directory:
                self.movie_output_name.setText("{0}.mp4".format(os.path.join(directory, seq_list[0].name)))
            else:
                self.msg_win.show_error_msg("Gui Display Error", "Could not parse movie name")

        # multiple sequences
        else:
            # multiple sequences share a common parent folder, so get that by going up one level in file system
            try:
                parent_dir = os.path.abspath(os.path.join(os.path.dirname(seq_list[0].directory()), '..'))
            except (IOError, OSError, WindowsError) as e:
                error_msg = "Could not parse parent directory for {0}. Error is {1}".format(seq_list[0].directory(), e)
                self.msg_win.show_error_msg("Gui Display Error", error_msg)
                logger.exception(error_msg)
                return

            try:
                # build file list of sub dirs and their ranges
                seq_names = []
                for seq in seq_list:
                    format_name = "{0}\{1}.{2}.{3} ".format(
                        seq[0].dirname.split("\\")[-1],
                        seq[0].base_name,
                        seq.frame_range(),
                        seq[0].ext
                    )
                    seq_names.append(format_name)
            except (IndexError, ValueError) as e:
                error_msg = "Could not parse parent directory for {0}. Error is {1}".format(seq_list[0].directory(), e)
                self.msg_win.show_error_msg("Gui Display Error", error_msg)
                logger.exception(error_msg)
                return

            self.files_display.setText("{0} : {1}".format(parent_dir, ', '.join(seq_names)))
            self.frame_range_input.setText("N/A")
            self.movie_output_name.setText("{0}\[seq_shot].mp4".format(parent_dir))

    def save_movie(self):
        """Gets the file name selected from the dialog and stores in text edit box in gui"""
        name = FileDialog.getSaveFileName(self, 'Save File', options=FileDialog.DontUseNativeDialog)
        self.movie_output_name.setText(name)

    def create_movie(self):
        """Creates movie for the image sequences
        """
        self.progress_update.setLabelText("Checking Submission...")
        self.progress_update.show()
        QtWidgets.QApplication.processEvents()

        frame_steps = (int(self.steps_sbox.text()))
        frame_range = str(self.frame_range_input.text()).strip()  # remove white space
        movie_name = str(self.movie_output_name.text())
        # validate input
        msg = self.ui.validate_submission(self.shoot.seq_list,
                                          self.shoot.combine_seq,
                                          frame_range,
                                          movie_name,
                                          frame_steps
                                          )
        if msg:
            self.msg_win.show_error_msg("Invalid Option", msg)
            self.progress_update.hide()
            return False

        quality = self.movie_quality_cbox.checkState()

        movie_log, movie_list = self.shoot.create_movie(frame_steps, frame_range, movie_name, quality, self.progress_update)
        self.msg_win.show_info_msg("Movie Report", "Created {0} Movie(s).".format(len(movie_list)))

        # update progress
        self.progress_update.setLabelText("Finished")
        self.progress_update.setValue(100)
        self.progress_update.hide()
        QtWidgets.QApplication.processEvents()

        # open movie playback if option is checked and movie created
        if self.show_movies_cbox.checkState() and movie_list:
            error = self.shoot.play_movies(movie_list)
            if error:
                self.msg_win.show_error_msg("Playback error", "Error opening playback app. Error is {0}".format(error))

        # report movie not created
        if movie_log:
            self.msg_win.show_warning_msg("Movie Report", "Could not create some or all movie. "
                                                          "See Log in C:\PyAniTools\logs\PyShoot\ for more info.")

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
        # setup data
        self.ani_vars = pyani.core.anivars.AniVars()
        self.shoot = pyani.media.movie.create.core.AniShoot(movie_generation, movie_playback, strict_pad)
        self.ui = pyani.media.movie.create.core.AniShootUi()

        # get arguments from command line
        parser = self.build_parser()
        self.args = parser.parse_args()

        # try to format image dir and mov file path, if can't just set to args - means wasn't provided
        self.image_dir = self.args.img
        self.mov_path = self.args.mov
        try:
            self.image_dir = self.image_dir.replace("/", "\\")
            self.image_dir = os.path.normpath(self.image_dir)
            self.mov_path = self.mov_path.replace("/", "\\")
            self.mov_path = os.path.normpath(self.mov_path)
        except:
            pass

    def run(self):
        """
        run the app
        :return log : an errors
        """
        tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        app_vars = pyani.core.appvars.AppVars()

        version = tools_mngr.get_tool_local_version(app_vars.local_pyanitools_apps_dir, "pyShoot")
        self.show_msg("__Version__ : {0}".format(version), Fore.GREEN)

        # process user input and setup the image sequence, if errors exit
        if not self.process_user_input():
            return

        # get the images selected
        self.get_sequence()

        # create the movie
        log = self.create_movie(
            self.args.steps,
            self.args.frame_range,
            self.mov_path,
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
            usage="Given Z:\Images\Seq180\Shot_040\comp.####.exr "
                  "PyShoot.exe -ng -i Z:\Images\Seq180\Shot_040\\ -n test -e exr "
                  "-o Z:\Movies\Seq180\Shot_040\my_movie.mp4"
        )

        # Positional Arguments
        parser.add_argument('-i', '--img', help="Directory of image sequence to create movie")
        parser.add_argument('-o', '--mov', help="Name of the movie.")

        # Keyword / Optional Arguments - action is value when provided, default mis value when not provided
        parser.add_argument('-n', '--name', help="Name of the images", default="")
        parser.add_argument('-e', '--ext', help="image format", default="")
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
        self._add_bool_arg(parser, "frame_hold", "Hold missing frames.", True)
        self._add_bool_arg(parser, "overwrite", "Overwrite movie on disk.", False)
        return parser

    def process_user_input(self):
        """
        process the command line arguments, creating the default values for optional arguments
        :return True if success, False if error
        """
        if not self.args.frame_range:
            self.args.frame_range = "N/A"

        if self.args.frame_hold:
            self.shoot.frame_hold = True
        else:
            self.shoot.frame_hold = False

        # check if image path was given
        if not self.image_dir:
            logging.error("No image directory given.")
            self.show_msg("Please provide an image directory.", Fore.RED)
            return False

        # check if image name was given
        if self.args.name:
            if self.args.ext == "":
                logging.error("When specifying an image name, please also give the format.")
                self.show_msg("When specifying an image name, please also give the format.", Fore.RED)
                return False

        # check if image ext was given
        if self.args.ext:
            if self.args.name == "":
                logging.error("When specifying an image format, please also give the images' name.")
                self.show_msg("When specifying an image format, please also give the images' name.", Fore.RED)
                return False

        # check if image directory exists
        if not os.path.exists(self.image_dir):
            logging.error("Image directory {0} doesn't exist.".format(self.image_dir))
            self.show_msg("Image directory {0} doesn't exist.".format(self.image_dir), Fore.RED)
            return False

        # check if movie name given
        if not self.mov_path:
            logging.error("No movie name given.")
            self.show_msg("Please provide a movie name.", Fore.RED)
            return False

        # check if directory exists, if not make it
        mov_path = self.args.mov.split("\"")[:-1]
        mov_dir = os.path.normpath("\\".join(mov_path))
        if not os.path.exists(mov_dir):
            pyani.core.util.make_all_dir_in_path(mov_dir)
            return False

        return True

    def get_sequence(self):
        """
        Build an image sequence
        """
        image_path = os.path.normpath(self.args.img)
        steps = int(self.args.steps)
        name = self.args.name
        images = []

        # make image list
        if os.path.exists(image_path):
            # check if image name was given
            if self.args.name:
                for image in os.listdir(image_path):
                    if image.endswith(self.args.ext):
                        img = pyani.media.image.core.AniImage(os.path.join(image_path, image))
                        if img.base_name == name:
                            images.append(os.path.join(image_path, image))
            else:
                images = [
                    os.path.join(image_path, image) for image in os.listdir(image_path)
                    if image.endswith(pyani.core.util.SUPPORTED_IMAGE_FORMATS)
                ]

        error_msg = self.ui.process_input(images, self.shoot)
        if error_msg:
            logging.error(error_msg)
            self.show_msg(error_msg, Fore.RED)
            return

        # validate sequence
        msg = self.ui.validate_selection(self.shoot, int(steps))
        if msg:
            logging.error(msg)
            self.show_msg(msg, Fore.RED)
            return

    def create_movie(self, steps, frame_range, movie_name, overwrite, play_movie, quality):
        """
        Creates a movie from an image sequence
        :param steps: frame steps as int
        :param frame_range: frame range as string, accepts ###-### and ###,### or a combination ###,###-###
        :param movie_name: output path for movie
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

        msg = self.ui.validate_submission(self.shoot.seq_list,
                                          self.shoot.combine_seq,
                                          frame_range,
                                          movie_name,
                                          overwrite)
        if msg:
            logging.error(msg)
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
