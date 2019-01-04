import os
import OpenEXR
import Imath
import array
from PIL import Image
import pyani.core.util
import pyani.core.ui
import pyani.media.image.core
import pyani.core.appmanager
from pyani.core.ui import FileDialog
import multiprocessing


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


class AniExr(object):
    """
    Class to handle an image exr
    """

    def __init__(self, file_path):
        self.__image_path = file_path
        self.__image = pyani.media.image.core.AniImage(self.image_path)
        # get the layers in the image
        img_file = OpenEXR.InputFile(self.image_path)
        # dict, key is layer name, value is the channel names
        self.__layers = self._build_layers_from_channels(img_file.header()['channels'].keys())
        img_file.close()
        # set via multiprocessing
        self.__layer_images = None

    @property
    def image(self):
        """The image properties - a pyani.media.image.core.AniImage object
        """
        return self.__image

    @property
    def image_path(self):
        """The image file path on disk
        """
        return self.__image_path

    @property
    def layer_names(self):
        """The exr layers as a sorted list, but put RGB first
        """
        sorted_layers = sorted(self.__layers.keys())
        sorted_layers.insert(0, sorted_layers.pop(sorted_layers.index("RGB")))
        return sorted_layers

    @staticmethod
    def channel_type(channels):
        """
        Return the type of channel data, is it data (P, N, Z, etc) or RGB (diffuse, specular, etc)
        :param channels: the channels
        :return: 'rgb' or 'data'
        """
        channel_type = "rgb"
        channel_split = channels[0].split(".")
        if len(channel_split) > 1:
            if channel_split[1] in ["X", "Y", "Z"]:
                channel_type = "data"
        else:
            if channel_split[0] == "Z":
                channel_type = "data"
        return channel_type

    def layer_channel_names(self, layer_name):
        """
        Return the a layer's channel names
        :param layer_name: name of the layer to get channels for
        :return: channel names as list
        """
        return self.__layers[layer_name]

    def size(self):
        """width, height of the image as a tuple
        """
        width, height = self.image.size
        return width, height

    def get_layer_image(self, layer_name):
        """
        get the image representation of the layer as a PIL Image object
        :param layer_name: the layer name
        :return: a PIL image object
        """
        return self.__layer_images[layer_name]

    def load(self):
        """loads the image layers using multiprocessing
        """
        # mp mannager so that we can get return values
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        jobs = []

        layers = self.layer_names
        # create a process per layer
        for i in range(0, len(layers)):
            channels = self.layer_channel_names(layers[i])
            p = multiprocessing.Process(target=load_exr_layer_mp,
                                        args=(self.image_path, layers[i], channels, self.size(), True, return_dict))
            jobs.append(p)
            p.start()

        # wait for all processes to finish
        for proc in jobs:
            proc.join()

        # dict, key is the layer name, value is a PIL Image object
        self.__layer_images = return_dict

    @staticmethod
    def _build_layers_from_channels(channels):
        """
        Build layers from channel names. Combines rgb or rgba into one layer. exr lists r,g,b,a as separate layers
        Skips alpha channel of rgb default layer
        :param channels: list of channels (i.e. diffuse.R, or R)
        :return: the layer names as a dictionary with layers as keys, and channel names as values
        """
        layers = {}
        for channel in channels:
            # remove the channel, such as R, to get the layer name
            channel_split = channel.split(".")
            channel_base = channel_split[0]
            # handle single channels (ex: depth Z) differently from multi channel (ex : diffuse)
            if len(channel_split) > 1:
                # since this layer appears more than once in the header, i.e. layer.R, layer.G, layer.B, only add once
                if not (channel_base in layers):
                    # its a data pass
                    if channel_split[1] in ["X", "Y", "Z"]:
                        layers[channel_base] = [channel_base + ".X", channel_base + ".Y", channel_base + ".Z"]
                    else:
                        layers[channel_base] = [channel_base + ".R", channel_base + ".G", channel_base + ".B"]
            # single channel layer
            else:
                layers[channel_base] = [channel_base]
        # not concerned with alpha
        if "A" in layers:
            del layers["A"]
        # turn separate R, G, B layers into one "RGB" layer
        try:
            del layers["R"]
            del layers["G"]
            del layers["B"]
            layers["RGB"] = ["R", "G", "B"]
        except KeyError:
            pass
        return layers


def load_exr_layer_mp(image_path, layer_name, channel_names, size, color_transform, return_dict):
    """
    loads a layer from an exr image
    :param image_path: the file path
    :param layer_name: name of the exr layer
    :param channel_names: the channels belonging to the layer
    :param size: the width and height as tuple
    :param color_transform: true to apply color transform
    :param return_dict: used to store the image smade of the exr layers
    """
    img_file = OpenEXR.InputFile(image_path)

    # single channel layer, put same value in red, green, and blue
    if len(channel_names) == 1:
        r_channel = channel_names[0]
        g_channel = channel_names[0]
        b_channel = channel_names[0]
    # multi channel layer
    else:
        r_channel = channel_names[0]
        g_channel = channel_names[1]
        b_channel = channel_names[2]

    (r, g, b) = img_file.channels([r_channel, g_channel, b_channel], Imath.PixelType(Imath.PixelType.FLOAT))

    red = array.array('f', r)
    green = array.array('f', g)
    blue = array.array('f', b)

    # apply color transform (sRGB) if option is True
    if color_transform:
        if not channel_names[0] == 'Z':
            red, green, blue = pyani.core.util.convert_to_sRGB(red, green, blue)

    # convert to rgb 8-bit image
    rgbf = [Image.frombytes("F", size, red.tostring())]
    rgbf.append(Image.frombytes("F", size, green.tostring()))
    rgbf.append(Image.frombytes("F", size, blue.tostring()))
    rgb8 = [im.convert("L") for im in rgbf]

    img_file.close()

    return_dict[layer_name] = Image.merge("RGB", rgb8)


class AniExrViewerGui(pyani.core.ui.AniQMainWindow):
    """
    Class for a gui that displays exrs. Provides: layer/channel viewing, drag and drop for file load.
    """
    def __init__(self):
        self.app_name = "PyExrViewer"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniExrViewerGui, self).__init__("Py Exr Manager", "Resources\\pyexrviewer.png", self.app_mngr, 1920, 1000)

        # class variables
        self.exr_image = None
        self.default_img_width = 1860
        self.default_img_height = 1020

        # main ui elements - styling set in the create ui functions
        self.btn_next = QtWidgets.QPushButton("Next Layer")
        self.btn_prev = QtWidgets.QPushButton("Prev Layer")
        self.layer_list_menu = QtWidgets.QComboBox()
        self.label_image_display = QtWidgets.QLabel()
        self.btn_image_select = QtWidgets.QPushButton("Select Image")
        self.image_file_path = QtWidgets.QLineEdit("")
        self.scroll = QtWidgets.QScrollArea()

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
        # |  channel list  |   space   |   prev      |   next     |   space    |
        g_layout_options = QtWidgets.QGridLayout()
        # image selection
        layer_list_label = QtWidgets.QLabel("Exr Layers:")
        g_layout_options.addWidget(layer_list_label, 0, 0)
        g_layout_options.addWidget(self.layer_list_menu, 0, 1)
        g_layout_header.addItem(self.empty_space, 0, 2)
        self.btn_prev.setMinimumSize(150, 30)
        g_layout_options.addWidget(self.btn_prev, 0, 3)
        self.btn_next.setMinimumSize(150, 30)
        g_layout_options.addWidget(self.btn_next, 0, 4)
        g_layout_header.addItem(self.empty_space, 0, 5)
        g_layout_options.setColumnStretch(1, 2)
        g_layout_options.setColumnStretch(2, 2)
        g_layout_options.setColumnStretch(5, 4)
        self.main_layout.addLayout(g_layout_options)
        self.main_layout.addItem(self.v_spacer)

        # IMAGE
        self.label_image_display.setFixedSize(self.default_img_width, self.default_img_height)
        self.scroll.setWidget(self.label_image_display)
        self.label_image_display.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.scroll)

        # add the layout to the main app widget
        self.add_layout_to_win()

    def set_slots(self):
        """Create the slots/actions that UI buttons / etc... do
        """
        self.layer_list_menu.currentIndexChanged.connect(self.display_layer)
        self.btn_prev.clicked.connect(self.prev_layer_in_menu)
        self.btn_next.clicked.connect(self.next_layer_in_menu)
        self.btn_image_select.clicked.connect(self.open_file_browser)

    def set_keyboard_shortcuts(self):
        """Set keyboard shortcuts for app
        """
        next_img_shortcut = QtWidgets.QShortcut(self)
        next_img_shortcut.setKey(QtCore.Qt.Key_Right)
        self.main_win.connect(next_img_shortcut, QtCore.SIGNAL("activated()"), self.next_layer_in_menu)
        prev_img_shortcut = QtWidgets.QShortcut(self)
        prev_img_shortcut.setKey(QtCore.Qt.Key_Left)
        self.main_win.connect(prev_img_shortcut, QtCore.SIGNAL("activated()"), self.prev_layer_in_menu)

    def dropEvent(self, e):
        """
        called when the drop is completed when dragging and dropping,
        calls wrapper which gets mime data and calls self._load_image passing mime data to it
        generic use lets other windows use drag and drop with whatever function they need
        :param e: event mime data
        """
        self.drop_event_wrapper(e, self._load_image)

    def reset_ui(self):
        """Resets the ui elements when a new image is loaded
        """
        self.layer_list_menu.clear()

    def open_file_browser(self):
        """Gets the file name selected from the dialog and stores in text edit box in gui"""
        name = FileDialog.getOpenFileName(self, "Select Exr Image")
        self.image_file_path.setText(name)
        self._load_image(self.image_file_path.text())

    def display_layer(self):
        """Shows the exr layer in the app
        """
        # skip processing if the menu is empty - avoids problem when we clear the ui on a new
        # image load. Clearing the ui changes the current index and we have a slot / signal that looks
        # for that change and tries to display a new layer. However none exist since its a reset!
        if self.layer_list_menu.currentText():
            layer_image = self.exr_image.get_layer_image(str(self.layer_list_menu.currentText()))
            error = None
            if error is not None:
                self.msg_win.show_error_msg("Error", error)
            else:
                pix = self._pil_to_pixmap(layer_image)
                # resize if needed
                width, height = self.exr_image.size()
                if width > height and width > self.default_img_width:
                    self.label_image_display.setPixmap(pix.scaledToWidth(self.default_img_width))
                elif height > self.default_img_height:
                    self.label_image_display.setPixmap(pix.scaledToHeight(self.default_img_height))
                else:
                    self.label_image_display.setPixmap(pix)

                self.main_app_widget.update()

    def next_layer_in_menu(self):
        """Go to the next layer in the menu
        """
        menu_size = int(self.layer_list_menu.count())
        next_layer_ind = (self.layer_list_menu.currentIndex() + 1) % menu_size
        self.layer_list_menu.setCurrentIndex(next_layer_ind)

    def prev_layer_in_menu(self):
        """Go to the prev layer in the menu
        """
        menu_size = int(self.layer_list_menu.count())
        prev_layer_ind = (self.layer_list_menu.currentIndex() - 1) % menu_size
        self.layer_list_menu.setCurrentIndex(prev_layer_ind)

    def _build_layer_menu(self):
        """Populates the layer menu with the exr layers
        """
        # build the menu of layers
        for layer in self.exr_image.layer_names:
            self.layer_list_menu.addItem(layer)

    def _load_image(self, file_names):
        """
        Load the exr image and its layers
        :param file_names: the exr image path(s)
        """
        exr_img_path = file_names[-1]

        # reset any ui elements
        self.reset_ui()
        # load image
        self.exr_image = AniExr(os.path.normpath(str(exr_img_path)))
        self.image_file_path.setText(exr_img_path)
        # show a progress busy indicator
        self.msg_win.show_msg("Loading", "Loading Exr Layers, Please Wait.")
        QtWidgets.QApplication.processEvents()
        # load the layers as images
        self.exr_image.load()
        self.msg_win.msg_box.hide()

        # build layer menu - clear first in case loading a new image
        self._build_layer_menu()
        # show the rgb of the image
        self.display_layer()
        # set focus to image
        self.main_win.setFocus()

    @staticmethod
    def _pil_to_pixmap(image):
        """
        Converts a PIL image to a QT Image. The PIL.ImageQt class was crashing. This code is from github,
        via stackoveflow https://stackoverflow.com/questions/34697559/pil-image-to-qpixmap-conversion-issue
        Reverse the channels
        :param image: a PIL image object
        :return: converted QT pixmap
        """
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
