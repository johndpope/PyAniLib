import logging
import os
import multiprocessing
from PIL import Image
import pyani.core.appmanager
import pyani.media.image.core
import pyani.media.image.seq
import pyani.core.ui
from pyani.core.ui import FileDialog
from pyani.media.image.exr import AniExr

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore
from PyQt4.QtCore import pyqtSignal, pyqtSlot

logger = logging.getLogger()


class AniImageViewer(QtWidgets.QGraphicsView):
    """
    Provides a image viewer class that provides:
        - zoom in and out with fit to window using mouse wheel
        - pan using right mouse button
        - reset to zoom level 0 with keyboard 'R' key
    """
    def __init__(self, parent):
        super(AniImageViewer, self).__init__(parent)
        # zoom level
        self._zoom = 0
        # how much to scale up when zooming in
        self._zoom_inc_factor = 1.25
        # how much to scale down when zooming out
        self._zoom_dec_factor = 0.8
        self._empty = True
        # setup QGraphicsView (its the widget that holds the QGraphicsScene (the class managing the 2d graphics)
        self._scene = QtWidgets.QGraphicsScene(self)
        self._image = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._image)
        self.setScene(self._scene)

        # put zooming and panning under mouse location
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        # turn reset scroll bars, set bg color, and turn reset frame around scene
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        # setup keyboard shortcuts
        self.set_keyboard_shortcuts()

    def has_image(self):
        """
        Checks if a photo has been loaded
        :return: True if loaded, False if not
        """
        return not self._empty

    def set_keyboard_shortcuts(self):
        """Set keyboard shortcuts for app
        """
        reset_shortcut = QtWidgets.QShortcut(self)
        reset_shortcut.setKey(QtCore.Qt.Key_R)
        self.connect(reset_shortcut, QtCore.SIGNAL("activated()"), self.fitInView)

    def fitInView(self):
        """
        Re-implemented from QGraphicsView because the built in version adds a weird fixed margin that can't
        be removed. Fits the scene bbobx inside viewport
        """
        # image bbox - never changes
        rect = QtCore.QRectF(self._image.pixmap().rect())
        # make sure there is an image
        if not rect.isNull():
            # set scene bbox to dimensions of image
            self.setSceneRect(rect)
            # map image dimensions to 0 to 1, at start always 0 to 1, but if resize window will change (since
            # size of pixmap never really changes, we are scaling it, but we always have its original size)
            unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
            # set scale factor - how much smaller or larger is image compared to window/scene object
            self.scale(1 / unity.width(), 1 / unity.height())
            # get the viewport bbox - based reset window size
            view_rect = self.viewport().rect()
            # map to actual image dimensions
            scene_rect = self.transform().mapRect(rect)
            # figure out which is smaller, width or height, used to scale to fit window
            factor = min(view_rect.width() / scene_rect.width(),
                         view_rect.height() / scene_rect.height())
            # fit to window
            self.scale(factor, factor)
            # reset zoom
            self._zoom = 0

    @pyqtSlot(QtGui.QPixmap)
    def set_image(self, pix, image_path=None, reset=True):
        """
        Set an image in the QGraphicsView. Takes an image path or a pixmap object, option to not reset zoom, so you can
        switch between images without losing zoom level

        NOTE: the main gui communicates with this class via signal/slots when images are loaded, so that this can
        update, uses imageLoaded custom signal - see AniExrViewerGui class for signal

        :param pix: a pixmap object
        :param image_path: optional, a path to an image to load, just pass None for pix parameter
        :param reset: True means reset zoom, otherwise leave as is
        """
        if image_path:
            pixmap = QtGui.QPixmap(image_path)
        else:
            pixmap = pix

        if pixmap and not pixmap.isNull():
            self._empty = False
            # turn on dragging
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self._image.setPixmap(pixmap)
            logger.info("Loaded image into QGraphicsView in Viewer class. Drag on. Image is: {0}".format(image_path))
        # invalid image, skip
        else:
            self._empty = True
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self._image.setPixmap(QtGui.QPixmap())
        if reset:
            self._zoom = 0
            self.fitInView()

    def wheelEvent(self, event):
        """
        Handles the zoom in and out based reset mouse wheel
        :param event: the qt event, in this case mouse scrolling ie QEvent.Wheel
        """
        if self.has_image():
            # the delat is the number if notches scrolled
            # pyqt 5 is event.angleDelta().y()
            if event.delta() > 0:
                factor = self.zoom_in()
            else:
                factor = self.zoom_out()
            self.scale_image(factor)

    def zoom_in(self):
        """
        Increases zoom level and returns the factor to scale up by
        :return: the amount to scale the image up, as a float
        """
        self._zoom += 1
        return self._zoom_inc_factor

    def zoom_out(self):
        """
        Decreases zoom level and returns the factor to scale down by
        :return: the amount to scale the image down, as a float
        """
        self._zoom -= 1
        return self._zoom_dec_factor

    def scale_image(self, factor):
        """
        Scales the image up or down, amd handles stopping zoom when user is back to original size (all the way zoomed
        out).
        :param factor: a float, that specifies the amount to scale up (1 <= x )or down (0 < x < 1)
        """
        # check if mouse wheel moved forward or back, if so 'zoom' in on image by setting scale - property of
        # QGraphicsView
        if self._zoom > 0:
            self.scale(factor, factor)
        # back to no zoom, so fit in window
        elif self._zoom == 0:
            self.fitInView()
        # don't allow zooming out beyond original fit
        else:
            self._zoom = 0


class AniImageSeqPlaybackController(QtWidgets.QWidget):
    """
    Provides a timeline and functionality to control playing of an image sequence. Requires a viewer class object.
    Can be any class, as long as it has a set_image function that takes a pixmap
    :param viewer: a class object that can display a pixmap image
    :param fps: optional frames per second, defaults to 30 frames per second
    :param loop: optional loop_playback play of image sequence, defaults to True
    :param reset_zoom : optional, whether to maintain zoom or to reset when ever hit playback buttons
    """
    def __init__(self, viewer, fps=30.0, loop=True, reset_zoom=False):
        super(AniImageSeqPlaybackController, self).__init__()
        # the __timer for how long to hold a frame (give it a parent, self, so that it can make use of Qt's
        # shared memory system)
        self.__timer = QtCore.QTimer(self)
        # the image sequence (set via set_image_sequence() - list of pixmaps
        self.__image_sequence = None
        # the current frame number (just a index to the image_sequence list, does not correspond to the
        # image frame numbers)
        self.__current_frame = 0
        # number of frames to display in a second
        self.__fps = fps
        # a flag whether to loop playback
        self.__loop_playback = loop
        # the image viewer class object
        self.__viewer = viewer
        # whether to allow zoom or to reset when ever hit playback buttons
        self.__reset_zoom = reset_zoom
        # the frame timeline/slider
        self.__timeline_controller = pyani.core.ui.SliderWidget(QtCore.Qt.Horizontal)
        # frame numbers - pyani.media.image.core.AniFrame objects
        self.__start_frame = None
        self.__end_frame = None
        # ui labels to display frame start/end and current frame
        self.curr_frame_label = QtWidgets.QLabel("")
        self.start_frame_label = QtWidgets.QLabel("")
        self.end_frame_label = QtWidgets.QLabel("")

        # buttons
        self.btn_play = pyani.core.ui.ImageButton(
            "images\play_off.png",
            "images\play_on.png",
            "images\play_on.png"
        )
        self.btn_stop = pyani.core.ui.ImageButton(
            "images\stop_off.png",
            "images\stop_on.png",
            "images\stop_on.png"
        )
        self.btn_pause = pyani.core.ui.ImageButton(
            "images\pause_off.png",
            "images\pause_on.png",
            "images\pause_on.png"
        )
        self.btn_step_fwd = pyani.core.ui.ImageButton(
            "images\step_fwd_off.png",
            "images\step_fwd_on.png",
            "images\step_fwd_on.png"
        )
        self.btn_step_back = pyani.core.ui.ImageButton(
            "images\step_back_off.png",
            "images\step_back_on.png",
            "images\step_back_on.png"
        )
        self.btn_loop = pyani.core.ui.ImageButton(
            "images\loop_off.png",
            "images\loop_on.png",
            "images\loop_on.png"
        )
        self.loop_disabled_img = \
            "images\loop_disabled.png"
        self.loop_enabled_img = \
            "images\loop_off.png"

        self.build_widget()
        # set signal/slots
        self.set_slots()

    @property
    def keep_zoom(self):
        return self.__reset_zoom

    @keep_zoom.setter
    def keep_zoom(self, value):
        self.__reset_zoom = value

    @property
    def loop_playback(self):
        return self.__loop_playback

    @loop_playback.setter
    def loop_playback(self, value):
        self.__loop_playback = value

    @property
    def fps(self):
        return self.__fps

    @fps.setter
    def fps(self, value):
        self.__fps = value

    def build_widget(self):
        """
        Makes the slider widget with frame labels and playback buttons
        """
        main_layout = QtWidgets.QVBoxLayout()
        timeline_layout = QtWidgets.QHBoxLayout()
        timeline_layout.addWidget(self.start_frame_label)
        timeline_layout.addWidget(self.__timeline_controller)
        timeline_layout.addWidget(self.end_frame_label)
        main_layout.addLayout(timeline_layout)
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addItem(QtWidgets.QSpacerItem(0, 10))
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addItem(QtWidgets.QSpacerItem(10, 0))
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addItem(QtWidgets.QSpacerItem(10, 0))
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addItem(QtWidgets.QSpacerItem(20, 0))
        controls_layout.addWidget(self.curr_frame_label)
        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(14)
        font.setBold(True)
        self.curr_frame_label.setFont(font)
        controls_layout.addItem(QtWidgets.QSpacerItem(20, 0))
        controls_layout.addWidget(self.btn_step_back)
        controls_layout.addItem(QtWidgets.QSpacerItem(10, 0))
        controls_layout.addWidget(self.btn_step_fwd)
        controls_layout.addItem(QtWidgets.QSpacerItem(10, 0))
        controls_layout.addWidget(self.btn_loop)
        controls_layout.addStretch(1)
        controls_layout.addItem(QtWidgets.QSpacerItem(0, 20))
        main_layout.addLayout(controls_layout)
        self.setLayout(main_layout)

    def set_slots(self):
        """Set pyqt signals
        """
        self.__timer.timeout.connect(self._play)
        self.__timeline_controller.valueChanged.connect(self.update_playback_position)
        # notice calling public play() which starts __timer because __timer calls _play()
        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self.pause)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_loop.clicked.connect(self.toggle_loop)
        self.btn_step_fwd.clicked.connect(self.step_forward)
        self.btn_step_back.clicked.connect(self.step_back)

    def set_image_sequence(self, pixmap_seq):
        """
        Stores a list of pixmaps representing the image sequence.
        :param pixmap_seq: a list of pixmaps
        """
        self.__image_sequence = pixmap_seq
        # make sure the viewer is run once with fit to view to fit the image in the viewer space
        self.__viewer.set_image(self.__image_sequence[0], reset=True)

    def set_timeline(self, frame_range):
        """
        Set the slider range and text labels for first and last frame
        :param frame_range: a tuple of pyani.media.image.core.AniFrame objects representing start, end frame
        (AniFrame for start, AniFrame for end)
        :return:
        """
        # store AniFrame objects and set labels
        self.__start_frame = frame_range[0]
        self.start_frame_label.setText(self.__start_frame.frame)
        self.__end_frame = frame_range[1]
        self.end_frame_label.setText(self.__end_frame.frame)
        self.__timeline_controller.setRange(int(self.__start_frame.frame), int(self.__end_frame.frame))

    def update_timeline(self, frame):
        """
        Set slider position and current frame text label
        :param frame: the frame as an integer
        """
        self.__timeline_controller.setSliderPosition(frame)
        self.curr_frame_label.setText(str(frame))

    def update_playback_position(self):
        """
        called when the slider position is changed - gets the current slider position, and converts to
        an index to get the corresponding image. If the the timer is not active, ie playing,
        then it also updates the timeline slider and sets the image for the corresponding frame
        This is for when the user clicks arbitrarily on the timeline
        """
        if self.__image_sequence:
            # get slider position
            timeline_pos = self.__timeline_controller.value()
            # convert to an index for getting the corresponding image.
            self.__current_frame = timeline_pos - int(self.__start_frame)
            # if not playing, paused or stopped, update image and frame text.
            if not self.__timer.isActive():
                self.update_timeline(timeline_pos)
                # update image
                self.__viewer.set_image(self.__image_sequence[self.__current_frame], reset=self.__reset_zoom)

    def play(self):
        """
        Play an image sequence (list of pixmaps) using a QTimer object.
        Need to call set_image_sequence(pixmap_seq) first to give it the pixmaps to use.
        """
        if self.__image_sequence:
            # check if at the end of the slider/timeline, ie last frame, if so reset to start
            if self.__timeline_controller.value() == int(self.__end_frame.frame):
                self.__current_frame = 0
            # start playback - calls the signal which will call _play()
            self.__timer.start(self.__fps)

    def pause(self):
        """
        Stop at the current slider position if playing, otherwise resume playing
        """
        if self.__image_sequence:
            if not self.__timer.isActive():
                self.__timer.start(self.__fps)
            else:
                self.__timer.stop()

    def stop(self):
        """
        Stop playback and reset to start
        """
        if self.__image_sequence:
            self.__timer.stop()
            # reset current frame to start
            self.__current_frame = 0
            self.__viewer.set_image(self.__image_sequence[self.__current_frame], reset=self.__reset_zoom)
            self.update_timeline(self.__start_frame + self.__current_frame)

    def toggle_loop(self):
        """
        if playback looping is reset, turns on and if on turns reset
        """
        if self.__loop_playback:
            self.__loop_playback = False
            self.btn_loop.set_image("off", self.loop_disabled_img)
        else:
            self.__loop_playback = True
            self.btn_loop.set_image("off", self.loop_enabled_img)

    def step_forward(self):
        """
        Go one frame forward on the timeline
        """
        if self.__image_sequence:
            if self.__timer.isActive():
                self.pause()
            self.__current_frame = (self.__current_frame + 1) % len(self.__image_sequence)
            self.__viewer.set_image(self.__image_sequence[self.__current_frame], reset=self.__reset_zoom)
            self.update_timeline(self.__start_frame + self.__current_frame)

    def step_back(self):
        """
        Go one frame backwards on the timeline
        """
        if self.__image_sequence:
            if self.__timer.isActive():
                self.pause()
            self.__current_frame = (self.__current_frame - 1) % len(self.__image_sequence)
            self.__viewer.set_image(self.__image_sequence[self.__current_frame], reset=self.__reset_zoom)
            self.update_timeline(self.__start_frame + self.__current_frame)

    def reset(self):
        """
        Resets the player controller to default startup state. Clears the timeline/slider and frame info,
        deletes the pixmap sequence, sets current frame index to 0.
        """
        if self.__image_sequence:
            self.stop()
            self.__image_sequence = []
            self.__start_frame = None
            self.__end_frame = None
            self.start_frame_label.setText("")
            self.end_frame_label.setText("")
            self.__current_frame = 0
            self.__timeline_controller.setRange(0, 0)
            self.__timeline_controller.setSliderPosition(0)
            self.curr_frame_label.setText("")

    def _play(self):
        """
        Private function called by play() that changes the image sequence index to get the next image, and updates
        the image viewer class object
        """
        # check if we have reached the end of playback
        if self.__current_frame < len(self.__image_sequence):
            self.__viewer.set_image(self.__image_sequence[self.__current_frame], reset=self.__reset_zoom)
            self.update_timeline(self.__start_frame + self.__current_frame)
            self.__current_frame += 1
        # reached end of playback
        else:
            # check if looping, if so reset current frame
            if self.__loop_playback:
                self.__current_frame = 0
            else:
                self.__timer.stop()


class AniExrViewerGui(pyani.core.ui.AniQMainWindow):
    """
    Class for a gui that displays exrs. Provides:
        - layer/channel viewing
        - drag and drop for file load
        - zoom in and out - preserves zoom level when switching exr layers, resets when load new image
        - exr header meta data display in custom pop up
        - keyboard shortcuts:
            - left and right arrow keys navigate exr layers
            - 'r' resets zoom level
            - 'i' toggles exr metadata window open and close
    :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """

    # the pyqt signal used to communicate with the viewer class object AniImageViewer when its in a thread
    imageChanged = pyqtSignal(QtGui.QPixmap)

    def __init__(self, error_logging):
        self.app_name = "PyExrViewer"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniExrViewerGui, self).__init__(
            "Py Exr Viewer",
            "images\pyexrviewer.ico",
            self.app_mngr,
            1920,
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

        # exr object for single image
        self.exr_image = None
        # list of exr objects for image sequences
        self.exr_image_list = None
        # dict of pixmap objects created for the exr image list - cache so don't re-create
        # key is layer name, value is a list of pixmaps
        self.pixmap_layer_cache = {}
        # the header info from an exr to get for display
        self.header_metadata_categories = [
            "displayWindow", "dataWindow", "pixelAspectRatio", "compression", "type", "sample", "arnold/version",
            "depth", "arnold/stats/rays", "arnold/stats/time", "arnold/stats/memory"
        ]
        # the viewer object that holds the image - provides viewing functionality like zoom
        self.viewer = AniImageViewer(self)
        # the playback controller, takes the function
        self.playback_controller = AniImageSeqPlaybackController(self.viewer)

        # main ui elements - styling set in the create ui functions
        self.layer_list_menu = QtWidgets.QComboBox()
        self.btn_image_select = QtWidgets.QPushButton("Select Image")
        self.image_file_path = QtWidgets.QLineEdit("")
        self.btn_next = pyani.core.ui.ImageButton(
            "images\layer_next_off.png",
            "images\layer_next_on.png",
            "images\layer_next_off.png",
            size=(45, 32)
        )
        self.btn_prev = pyani.core.ui.ImageButton(
            "images\layer_prev_off.png",
            "images\layer_prev_on.png",
            "images\layer_prev_off.png",
            size=(45, 32)
        )
        self.btn_info = pyani.core.ui.ImageButton(
            "images\info_off.png",
            "images\info_on.png",
            "images\info_on.png"
        )
        self.btn_zoom_in = pyani.core.ui.ImageButton(
            "images\zoom_plus_off.png",
            "images\zoom_plus_on.png",
            "images\zoom_plus_on.png"
        )
        self.btn_zoom_out = pyani.core.ui.ImageButton(
            "images\zoom_minus_off.png",
            "images\zoom_minus_on.png",
            "images\zoom_minus_on.png"
        )
        # for popup window displaying exr metadata
        self.metadata_popup_win = None
        self.metadata_popup_open = False
        # exr layer selection window when loading an image sequence
        self.layer_selection_win = QtWidgets.QWidget()
        # progress window for loading image sequence
        self.progress_bar = QtWidgets.QProgressDialog()
        self.progress_bar.setCancelButton(None)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)

        # set to allow drag and drop
        self.setAcceptDrops(True)

        # keyboard shortcuts
        self.set_keyboard_shortcuts()

        self.create_layout()
        self.set_slots()

    def create_layout(self):
        """Creates all the widgets used by the UI and build layout
        """

        # HEADER
        # |    label    | file path --|-->       |     btn     |      space       |
        g_layout_header = QtWidgets.QGridLayout()
        # image selection
        image_label = QtWidgets.QLabel("Image:")
        g_layout_header.addWidget(image_label, 0, 0)
        g_layout_header.addWidget(self.image_file_path, 0, 1)
        self.btn_image_select.setStyleSheet("background-color:{0};".format(pyani.core.ui.GREEN))
        self.btn_image_select.setMinimumSize(150, 30)
        g_layout_header.addWidget(self.btn_image_select, 0, 2)
        g_layout_header.addItem(self.empty_space, 0, 3)
        g_layout_header.setColumnStretch(1, 2)
        g_layout_header.setColumnStretch(3, 2)
        self.main_layout.addLayout(g_layout_header)
        self.main_layout.addItem(self.v_spacer)
        # OPTIONS
        # |  channel list  |   space   |   prev    |   next   |   space  |  exr info  |  space  | zoom | space  |
        g_layout_options = QtWidgets.QGridLayout()
        # layer list
        layer_list_label = QtWidgets.QLabel("Exr Layers:")
        g_layout_options.addWidget(layer_list_label, 0, 0)
        g_layout_options.addWidget(self.layer_list_menu, 0, 1)
        g_layout_options.addItem(QtWidgets.QSpacerItem(15, 0), 0, 2)
        # prev button
        prev_label = QtWidgets.QLabel("Prev Layer")
        g_layout_options.addWidget(prev_label, 0, 3)
        g_layout_options.addWidget(self.btn_prev, 0, 4)
        g_layout_options.addItem(QtWidgets.QSpacerItem(25, 0), 0, 5)
        # next button
        next_label = QtWidgets.QLabel("Next Layer")
        g_layout_options.addWidget(self.btn_next, 0, 6)
        g_layout_options.addWidget(next_label, 0, 7)
        # space
        g_layout_options.addItem(self.empty_space, 0, 8)
        # exr info
        exr_header_info_title = QtWidgets.QLabel("Exr Header Information:")
        g_layout_options.addWidget(exr_header_info_title, 0, 9)
        g_layout_options.addWidget(self.btn_info, 0, 10)
        # space
        g_layout_options.addItem(self.empty_space, 0, 11)
        # zoom
        zoom_title = QtWidgets.QLabel("Zoom:")
        g_layout_options.addWidget(zoom_title, 0, 12)
        g_layout_options.addWidget(self.btn_zoom_in, 0, 13)
        g_layout_options.addItem(QtWidgets.QSpacerItem(25, 0), 0, 14)
        g_layout_options.addWidget(self.btn_zoom_out, 0, 15)
        # space
        g_layout_options.addItem(self.empty_space, 0, 16)

        g_layout_options.setColumnStretch(1, 2)
        g_layout_options.setColumnStretch(8, 2)
        g_layout_options.setColumnStretch(11, 2)
        g_layout_options.setColumnStretch(16, 4)
        self.main_layout.addLayout(g_layout_options)
        self.main_layout.addItem(self.v_spacer)

        # IMAGE
        self.viewer.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.viewer)
        self.main_layout.addWidget(self.playback_controller)
        # add the layout to the main app widget
        self.add_layout_to_win()

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.layer_list_menu.currentIndexChanged.connect(self.layer_menu_changed)
        self.btn_prev.clicked.connect(self.prev_layer_in_menu)
        self.btn_next.clicked.connect(self.next_layer_in_menu)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_info.clicked.connect(self.display_header_info)
        self.btn_image_select.clicked.connect(self.open_file_browser)
        self.imageChanged.connect(self.viewer.set_image)

    def set_keyboard_shortcuts(self):
        """Set keyboard shortcuts for app
        """
        next_img_shortcut = QtWidgets.QShortcut(self)
        next_img_shortcut.setKey(QtCore.Qt.Key_Right)
        self.main_win.connect(next_img_shortcut, QtCore.SIGNAL("activated()"), self.next_layer_in_menu)
        prev_img_shortcut = QtWidgets.QShortcut(self)
        prev_img_shortcut.setKey(QtCore.Qt.Key_Left)
        self.main_win.connect(prev_img_shortcut, QtCore.SIGNAL("activated()"), self.prev_layer_in_menu)
        metadata_shortcut = QtWidgets.QShortcut(self)
        metadata_shortcut.setKey(QtCore.Qt.Key_I)
        self.main_win.connect(metadata_shortcut, QtCore.SIGNAL("activated()"), self.display_header_info)

    def dropEvent(self, e):
        """
        called when the drop is completed when dragging and dropping,
        calls wrapper which gets mime data and calls self.load passing mime data to it
        generic use lets other windows use drag and drop with whatever function they need
        :param e: event mime data
        """
        self.drop_event_wrapper(e, self.load)

    def reset(self):
        """Resets these ui elements when a new image is loaded:
                - the layer menu
           Also resets the following data:
                - pixmap_layer_cache - cache for exr sequences
                - exr_image_list - list of exr objects for exr sequence
                - exr_image - exr image object if single exr loaded
        """
        self.layer_list_menu.clear()
        self.pixmap_layer_cache.clear()
        self.exr_image_list = None
        self.exr_image = None
        self.playback_controller.reset()

    def open_file_browser(self):
        """Gets the file(s) selected from the dialog and loads them"""
        selection = FileDialog.getOpenFileNames(self, "Select Exr Image")
        if selection:
            self.load(selection)

    def zoom_in(self):
        """Zooms in on the image, calls viewer class to handle
        """
        if self.viewer.has_image():
            factor = self.viewer.zoom_in()
            self.viewer.scale_image(factor)

    def zoom_out(self):
        """Zooms out on the image, calls viewer class to handle
        """
        if self.viewer.has_image():
            factor = self.viewer.zoom_out()
            self.viewer.scale_image(factor)

    def display_header_info(self):
        """
        Displays the exr header data in a pop up window using html for text formatting
        :return: error if encountered otherwise none
        """
        if not self.metadata_popup_open:
            font_size = 3
            cell_spacing = 8
            fill_color = (0, 0, 0, 225)
            border_color = (100, 100, 100, 255)
            button_color = (175, 175, 175, 255)
            font_color = "#ffffff"
            formatted_metadata = """
            <head>
                <title>Metadata</title>
                <style>
                </style>
            </head>
            <body>
                <table width="100%" cellspacing="{0}" >
                    <tr>
                        <td><font size="5" color="#ffffff"><b>Exr Metadata:</b></font></td>
                    </tr>
            """.format(cell_spacing)

            # get header metatdata and format it as html
            try:
                if self.viewer.has_image():
                    # get the metadata we want
                    matching_metadata = {
                        key: value for (key, value) in self.exr_image.header.items()
                        if any(cat in key for cat in self.header_metadata_categories)
                    }
                    # separate arnold metadata and sort - returns sorted key value as a list of tuples
                    arnold_metadata = {key: value for (key, value) in matching_metadata.items() if "arnold" in key}
                    arnold_metadata = sorted(arnold_metadata.iteritems())
                    # extract non arnold metadata and sort - returns sorted key value as a list of tuples
                    gen_exr_metadata = {key: value for (key, value) in matching_metadata.items() if "arnold" not in key}
                    gen_exr_metadata = sorted(gen_exr_metadata.iteritems())
                    # combine the lists
                    final_metadata = gen_exr_metadata
                    final_metadata.extend(arnold_metadata)
                    for metadata in final_metadata:
                        formatted_metadata += """
                                    <tr>
                                        <td><font size={0} color="{3}">{1}</font></td>
                                        <td><font size={0} color={3}>{2}</font></td>
                                    </tr>
                                    """.format(font_size, metadata[0], metadata[1], font_color)
                    formatted_metadata += "</table></body>"
                    self.metadata_popup_win = pyani.core.ui.TranslucentWidget(self.main_win)
                    self.metadata_popup_win.set_win_size(800, 600)
                    self.metadata_popup_win.set_colors(fill_color, border_color, button_color)
                    self.metadata_popup_win.move(0, 0)
                    self.metadata_popup_win.resize(self.width(), self.height())
                    self.metadata_popup_win.SIGNALS.CLOSE.connect(self.close_popup)
                    self.metadata_popup_open = True
                    self.metadata_popup_win.set_text(formatted_metadata)
                    self.metadata_popup_win.show()
                    return None
                else:
                    self.msg_win.show_error_msg("Error", "Please load an image to view exr metadata.")
                    return

            except (KeyError, ValueError, TypeError) as e:
                error = "Could not get meta data from {0}. Error is {1}".format(self.exr_image_list.path, e)
                logger.exception(error)
                self.msg_win.show_error_msg("Exr Error", error)
        else:
            self.metadata_popup_open = False
            self.metadata_popup_win.close()

    def resizeEvent(self, event):
        """
        Sets the size for the popup window containing exr metadata
        :param event: a qt event
        """
        if self.metadata_popup_open:
            self.metadata_popup_win.move(0, 0)
            self.metadata_popup_win.resize(self.main_win.width(), self.main_win.height())

    def close_popup(self):
        """Close the popup containing the exr metadata
        """
        self.metadata_popup_win.close()
        self.metadata_popup_open = False

    def layer_menu_changed(self):
        """
        Called when the layer menu changes, means a new exr layer has been selected. Displays the layer if a single
        exr is loaded, or loads the layer for each exr if its an exr sequence.
        """
        # skip processing if the menu is empty - avoids problem when we clear the ui on a new
        # image load. Clearing the ui changes the current index and we have a slot / signal that looks
        # for that change and tries to display a new layer. However none exist since its a reset!
        if self.layer_list_menu.currentText():
            # check if a sequence is loaded or a single image
            if self.exr_image_list:
                layer = str(self.layer_list_menu.currentText())
                # load the images, and starts playback
                self.play_exr_sequence(layer)
            # single image exr
            else:
                self.display_layer(False)

    def display_layer(self, reset):
        """
        Shows the exr layer in the app. Displays error if layer or pixmap isn't valid
        :param reset: flag whether to reset zoom level
        """
        layer_image = self.exr_image.get_layer_image(str(self.layer_list_menu.currentText()))
        # if the layer isn't a PIL Image object, its an error, so display
        if not isinstance(layer_image, Image.Image):
            self.msg_win.show_error_msg("Exr Layer Error", layer_image)
        else:
            pix = self._pil_to_pixmap(layer_image)
            if not isinstance(pix, QtGui.QPixmap):
                self.msg_win.show_error_msg("Exr Layer Error", pix)
            self.viewer.set_image(pix, reset=reset)

    def next_layer_in_menu(self):
        """Go to the next layer in the menu
        """
        menu_size = int(self.layer_list_menu.count())
        if menu_size > 0:
            next_layer_ind = (self.layer_list_menu.currentIndex() + 1) % menu_size
            self.layer_list_menu.setCurrentIndex(next_layer_ind)

    def prev_layer_in_menu(self):
        """Go to the prev layer in the menu
        """
        menu_size = int(self.layer_list_menu.count())
        if menu_size > 0:
            prev_layer_ind = (self.layer_list_menu.currentIndex() - 1) % menu_size
            self.layer_list_menu.setCurrentIndex(prev_layer_ind)

    def load(self, file_names):
        """
        Load the exr image or images
        :param file_names: an exr image path or a list of the exr image path(s)
        """
        if file_names:
            # reset any ui elements and data pertaining to a prev loaded exr or exr sequence
            self.reset()

            # doesn't matter if you load one or more exrs, always need the first exr header data because when loading
            # multiple exrs we ask what layer they want to see. Need header to do that.

            file_names = sorted(file_names)
            # create an exr class object - will error if file isn't on disk
            exr_img_path = file_names[0]
            try:
                self.exr_image = AniExr(os.path.normpath(str(exr_img_path)))
            except pyani.media.image.core.AniImageError as e:
                error = "Could not load image: {0}. Error is {1}.".format(exr_img_path, e)
                logging.exception(error)
                self.msg_win.show_error_msg("Image Load Error", error)
                return
            # load the exr data
            error = self.exr_image.open_and_save_header()
            if error:
                self.msg_win.show_error_msg("Exr Error", error)
                return

            # check if this multiple exrs
            if len(file_names) > 1:
                # get the exr layer to view by calling a pop up dialog that gets user selection
                menu_win = pyani.core.ui.QtInputDialogMenu(
                    self,
                    "Select the exr layer to load",
                    "Select Layer to View:",
                    self.exr_image.layer_names()
                )
                menu_win.exec_()
                # get the layer selected
                layer = str(menu_win.selection)
                # make exrs for all images on disk
                try:
                    # make a list of AniExr objects, then pass to a AniImageSeq object which handles image sequences.
                    # We can use this since AniExr inherits from AniImage, and AniImageSeq takes AniImage objects
                    exrs = [AniExr(os.path.normpath(str(file_name))) for file_name in file_names]
                    self.exr_image_list = pyani.media.image.seq.AniImageSeq(exrs)
                    for exr in self.exr_image_list:
                        exr.open_and_save_header()
                except (pyani.media.image.core.AniImageError, pyani.media.image.seq.AniImageSeqError) as e:
                    error = "Could not load image: {0}. Error is {1}.".format(file_name, e)
                    logging.exception(error)
                    self.msg_win.show_error_msg("Image Load Error", error)
                    return
                self.play_exr_sequence(layer)
                # set the image path on disk in ui file path widget
                file_name = "{0}/{1}.[{2}-{3}].exr".format(
                    self.exr_image_list[0].dirname,
                    self.exr_image_list[0].base_name,
                    self.exr_image_list[0].frame.frame,
                    self.exr_image_list[-1].frame.frame
                )
                self.image_file_path.setText(file_name)
            # single exr
            else:
                # set the image path on disk in ui file path widget
                self.image_file_path.setText(exr_img_path)
                # load the actual pixel data
                self._load_exr_layers()
        else:
            error = "Could not load files, drag and drop or file dialog error."
            logger.error(error)
            logger.error(file_names)
            self.msg_win.show_error_msg("File Error", error)
            return

    def play_exr_sequence(self, layer):
        """
        plays an exr sequence given a layer of the exr. can play multi-layer and single layer exrs. Loads the exr
        layers first using multiprocessing pool, then plays it using a AniImageSeqPlaybackController object. Caches
        multi-layer exr layers as they are loaded so don't have to reload if you switch to a prev loaded layer

        checks for missing frames, and holds the previous existing frame until the next existing frame is encountered.
        algorithm is below in comment block.

        :param layer: layer name in the exr
        """
        # save one frame of the sequence so app can build the layer menu
        self.exr_image = self.exr_image_list[0]
        # build layer menu - note that we block signals because we don't want the index changed signal to get
        # called. Why? Because it puts the RGB layer on top and it could try to access that and it may not be loaded
        self.layer_list_menu.blockSignals(True)
        self._build_layer_menu()
        self.layer_list_menu.setCurrentIndex(self.layer_list_menu.findText(layer))
        self.layer_list_menu.blockSignals(False)

        # check if the layer is already loaded
        if layer not in self.pixmap_layer_cache:
            # get channel name
            channel_names = self.exr_image_list[0].layer_channel_names(layer)
            # subtract one since starting at 0
            num_jobs = len(self.exr_image_list)-1

            p = multiprocessing.Pool()
            errors = []
            pixmaps = []
            self.progress_bar.setLabelText("Starting Multiprocess Loading, This May Take A Few Seconds...")
            self.progress_bar.show()
            QtWidgets.QApplication.processEvents()
            # package frame start and end
            frame_range = (self.exr_image_list[0].frame, self.exr_image_list[-1].frame)
            # update timeline in the controller
            self.playback_controller.set_timeline(frame_range)

            '''
            The way we hold  missing frames is described via an example:
            
            EX:
            we have a frame range 1-5, with frames 1,3, 5 given. 2 and 4 are missing.
            Our list variable, frame_exists, is [True, False, True, False, True]. 
            
            When multi-proc runs, it returns 3 PIL objects for frames 1, 3, 5. These are converted to pixmaps 
            for QT, so lets refer to these as pixmaps. We get these back in order. We start with frame 2 
            (since frame 1 always exists). That's why current_index starts at 1. current_index is our list index and 
            corresponds to the current frame. So we check frame_exists[current_index] to see if frame 2 exists. 
            If it exists don't do anything, just increment our index counter, current_index. However since its 
            missing, we store frame 1's pixmap and then increment the index counter by 1 placing us on frame 3. We 
            keep checking if a frame is missing, adding the pixmap, and incrementing the counter until an existing 
            frame is found. In our example frame 3 or current_index = 2 exists. Skip and increment the current_index
            to 3. Frame 4 doesn't exist, so store 3's pixmap for frame 4 and then increment the current_index to 4. 
            We can stop since on the last frame.
            '''
            # list of missing and existing frames
            all_frames = range(frame_range[0], frame_range[1] + 1)
            frame_exists = []
            # populate the frame exists list with True if frame exists, False if not.
            for frame_index, frame in enumerate(all_frames):
                if frame in self.exr_image_list.missing():
                    frame_exists.append(False)
                else:
                    frame_exists.append(True)
            # used to track what frame we are on when converting the exrs' layer to pixmaps. It is the only way we
            # can know what frame/list element we are on
            current_index = 1
            # total number of frames
            end_index = len(all_frames)

            # multi-proc loading
            for i, result in enumerate(
                    p.imap(
                        pyani.media.image.exr.get_channel_data,
                        [(exr.path, layer, channel_names, exr.size) for exr in self.exr_image_list],
                        chunksize=1
                    )
            ):
                # convert image object to a pixmap
                pix = self._pil_to_pixmap(result[layer])
                # append to list
                pixmaps.append(pix)

                # check and fill missing frames - using the current index to track what list element (i.e. frame)
                # we are on. each list element tells us if that frame exists or is missing
                #
                # only check for missing frames if not on last frame
                if current_index < end_index:
                    # loop until an existing frame is found - current index will be set to that existing frame at
                    # that point
                    while not frame_exists[current_index]:
                            pixmaps.append(pix)
                            current_index += 1

                progress = float(i)/float(num_jobs)*100.0
                self.progress_bar.setLabelText("Loading Image Sequence")
                self.progress_bar.setValue(int(progress))

                # while loading, update the viewer - note we subtract one because current index is ahead of
                # what is stored by 1, its on the next existing frame, while we are on the last missing frame
                self.imageChanged.emit(pixmaps[current_index-1])

                # advance index to the next frame. We are on the next existing frame - see while loop above.
                # The next for loop iteration will load the existing frame and add it. We want our index to be 1 past
                # that.
                current_index += 1
                QtWidgets.QApplication.processEvents()

            # close pool
            p.close()

            # check if any errors - count occurrences of None compared to length of list
            if not errors.count(None) == len(errors):
                num_errors = errors.count(None)
                total_frames = len(errors)
                self.msg_win.show_warning_msg(
                    "Load Error", "{0} out of {1} frames could not be loaded".format(num_errors, total_frames)
                )

            # set regular fps
            self.playback_controller.fps = 33.0
            # save pixmaps for later
            self.pixmap_layer_cache[layer] = pixmaps
        else:
            # already loaded, get from the cache
            pixmaps = self.pixmap_layer_cache[layer]

        self.playback_controller.set_image_sequence(pixmaps)
        self.playback_controller.play()

        # set focus to image
        self.main_win.setFocus()

    def _load_exr_layers(self):
        """
        Load the exr image and its layers. Displays and logs error if problem loading exr.
        :param exr_img_path: an image path on disk of an exr
        """
        # show a progress busy indicator
        self.msg_win.show_msg("Loading",
                              "Loading {0} Exr Layers, Please Wait.".format(len(self.exr_image.layer_names())))
        QtWidgets.QApplication.processEvents()

        # load the layers as images
        errors = self.exr_image.load_layers()
        # done loading hide window
        self.msg_win.msg_box.hide()
        # display any errors
        if errors:
            self.msg_win.show_error_msg("Exr Channel Error", ', '.join(errors))
            return

        # build layer menu - clear first in case loading a new image
        self._build_layer_menu()
        # show the rgb of the image, pass True to tell it to reset view to fit image
        self.display_layer(True)
        # set focus to image
        self.main_win.setFocus()

    def _build_layer_menu(self):
        """Populates the layer menu with the exr layers
        """
        # build the menu of layers
        for layer in self.exr_image.layer_names():
            self.layer_list_menu.addItem(layer)

    @staticmethod
    def _pil_to_pixmap(image):
        """
        Converts a PIL image to a QT Image. The PIL.ImageQt class was crashing. This code is from github,
        via stackoveflow https://stackoverflow.com/questions/34697559/pil-image-to-qpixmap-conversion-issue
        Reverse the channels
        :param image: a PIL image object
        :exception ValueError - if the data isn't valid in the PIL Image object
        :return: converted QT pixmap or error
        """
        try:
            if image.mode == "RGB":
                r, g, b = image.split()
                image = Image.merge("RGB", (b, g, r))
            elif image.mode == "RGBA":
                r, g, b, a = image.split()
                image = Image.merge("RGBA", (b, g, r, a))
            elif image.mode == "L":
                image = image.convert("RGBA")
            image2 = image.convert("RGBA")
            data = image2.tobytes("raw", "RGBA")
            qt_image = QtGui.QImage(data, image.size[0], image.size[1], QtGui.QImage.Format_ARGB32)
            return QtGui.QPixmap.fromImage(qt_image)
        except ValueError as e:
            error = "Problem converting PIL Image object to a pixmap. Error is {0}".format(e)
            logging.exception(error)
            return error
