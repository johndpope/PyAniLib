import os
import OpenEXR
import Imath
import array
import logging
from PIL import Image
import pyani.media.image.core
import pyani.core.appmanager
import multiprocessing
import numpy as np


logger = logging.getLogger()


class AniExr(pyani.media.image.core.AniImage):
    """
    Class to handle an image exr, inherits AniImage
    """

    def __init__(self, file_path):
        super(AniExr, self).__init__(file_path)
        # ignore these channels
        self.__channels_to_ignore = ("crypto")
        # channel names
        self.__channels = []
        # exr header
        self.__header = {}
        # layer names
        self.__layers = {}
        # built during load() func call, creates PIL image objects for layers. Layer name is key, PIL object is value
        self.__layer_images = {}

    @property
    def header(self):
        """The header meta data
        """
        return self.__header

    @property
    def channels(self):
        """All of the channels - ex diffuse.R, diffuse.G, diffuse.B, R, G, B, N.x, N.y, N.z ....
        :return: a sorted list of channels, sorts by layer name then channel name
        """
        return sorted(self.__channels, key=self._channel_sort_key)

    @property
    def layer_images(self):
        """returns a dictionary with layer name as key and PIL image object representing the layer as the value
        """
        return self.__layer_images

    def clear_image_data(self, layer):
        """
        Clears the PIL image object data
        :param layer: layer to clear
        """
        try:
            del self.__layer_images[layer]
        except KeyError as e:
            logger.exception("Error deleting PIL Image object for layer {0}. Error is {1}".format(layer, e))

    def update_layer_images(self, layer, image):
        """
        Updates a layer representation with a new PIL image object
        :param layer: layer name
        :param image: the PIL image object representing the layer
        :exception: key error if layer name doesn't exist
        :return error if layer doesn't exist, otherwise None
        """
        try:
            self.__layer_images[layer] = image
            return None
        except KeyError as e:
            error = "Error updating layer {0}. Error reported is {1}".format(layer, e)
            logger.exception(error)
            return error

    def is_valid_exr(self, exr_handle=None):
        """
        Check if exr is valid and complete (all data present)
        :param exr_handle: optional - an exr InputFile handle. If not provided one is created
        :return: The error if not readable or missing pixels, None otherwise
        """
        # check if a file handle was given
        if not exr_handle:
            # no handle provided so open the exr and get one
            exr_handle = self._open_exr_file_handle(self.path)
            # check for errors
            if not isinstance(exr_handle, OpenEXR.InputFile):
                return exr_handle
        # check of the exr is readable
        if not OpenEXR.isOpenExrFile(self.path):
            error = "The following exr does not exist or is not readable: {0}".format(self.path)
            logging.exception(error)
            exr_handle.close()
            return error
        # check if the exr has complete pixel information
        if not exr_handle.isComplete():
            error = "The following exr has missing pixels: {0}".format(self.path)
            logging.exception(error)
            exr_handle.close()
            return error
        return None

    def open_and_save_header(self):
        """
        Open an exr and save channels, header information. Validates exr as well - checks for exceptions when image
        does not exist, is an invalid exr or other image format
        :return: error if encountered, otherwise None
        """
        # open exr
        exr_handle = self._open_exr_file_handle(self.path)
        # check for errors opening the handle
        if not isinstance(exr_handle, OpenEXR.InputFile):
            return exr_handle

        # validate file is a valid exr and has all pixel data
        error = self.is_valid_exr()
        if error:
            logger.error(error)
            return error

        # try to load the exr data
        try:
            # dict, key is layer name, value is the channel names
            self.__channels = [
                channel for channel in exr_handle.header()['channels'] if self.__channels_to_ignore not in channel
            ]
            # save exr header
            self.__header = exr_handle.header()
            # done with file handle, close
            exr_handle.close()
            # layer names
            self.__layers = self._build_layers_from_channels(self.channels)
        # invalid exr layers (key error or index error)
        except (KeyError, IndexError) as e:
            error = "Could not load exr data: {0}. Error is {1}.".format(self.path, e)
            logging.exception(error)
            return error
        return None

    def layer_names(self):
        """The exr layers as a sorted list, but put RGB first. Displays error if there are no layers.
        :exception KeyError - means no layers present
        :exception IndexError - no RGB layer present
        :return a list of sorted layers with RGB layer first, or an error
        """
        try:
            sorted_layers = sorted(self.__layers.keys())
        except KeyError as e:
            error = "No layers present in the exr. Error is {0}".format(e)
            logging.exception(error)
            return error
        try:
            sorted_layers.insert(0, sorted_layers.pop(sorted_layers.index("RGB")))
        except IndexError as e:
            error = "No RGB layer present in the exr. Error is {0}".format(e)
            logging.exception(error)
            return error
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

    @staticmethod
    def is_single_channel(channel):
        """
        Is the channel just one channel such as depth (Z) or is it multi-channel like rgb or diffuse
        :param channel: the channel data
        :return: True if single channel, False if not
        """
        if len(channel) > 1:
            return False
        else:
            return True

    def layer_channel_names(self, layer_name):
        """
        Return a layer's channel names
        :param layer_name: name of the layer to get channels for, specify RGB for the default r,g,b channels
        :return: channel names as list
        """
        return self.__layers[layer_name]

    def get_layer_image(self, layer_name):
        """
        get the image representation of the layer as a PIL Image object
        :param layer_name: the layer name
        :exception KeyError - occurs if layer name isn't in the dictionary object of PIL Image Objects
        :return: a PIL image object, or error if encountered
        """
        try:
            return self.__layer_images[layer_name]
        except KeyError as e:
            error = "The layer name, {0}, does not exist. Available layers are: {1}. Error is {2}".format(
                layer_name, ', '.join(self.layer_names()), e
            )
            logging.exception(error)
            return error

    def load_layers(self, selected_layer=None):
        """
        loads the exr layers using multiprocessing into PIL Image objects. Handles single layer exrs,
        ,multi-layer exrs and specifying a layer of a multi-layer exr to load
        :param selected_layer: a layer name to load, by default loads all layers and their channels
        :return: error if encountered, otherwise none
        """
        # only used with multilayer exrs
        layer_names = self.layer_names()

        # if a layer name was specified in selected_layer, get just its channels
        if selected_layer:
            channel_names = self.layer_channel_names(selected_layer)
        else:
            channel_names = self.channels

        # get all the channels of the image
        img_file = OpenEXR.InputFile(self.path)
        # read all channel data from exr at once - most efficient way
        all_channel_data = img_file.channels(channel_names, Imath.PixelType(Imath.PixelType.FLOAT))
        img_file.close()

        channel_name_and_data = {}
        # put channel data into a dict with channel name as key
        for i, channel_data in enumerate(all_channel_data):
            channel_name_and_data[channel_names[i]] = channel_data

        # no need to multiprocess when one layer - either image only has one layer or loading a selected layer from
        # a multi layer exr
        if selected_layer or len(self.layer_names()) == 1:
            # get layer name if no layer was provided in selected layer - means exr only has one layer
            if not selected_layer:
                selected_layer = self.layer_names()[0]
            # get channel names for layer
            channel_names = self.layer_channel_names(selected_layer)
            # channel data for this layer
            layer_data = tuple([channel_name_and_data[channel_name] for channel_name in channel_names])
            # add image data
            self.__layer_images.update(convert_channel_data_to_image(selected_layer, layer_data, self.size))
        else:
            # use multiprocessing - do async so processes don't wait on each other
            p = multiprocessing.Pool()
            async_result = []
            # make an image per layer
            for layer_name in layer_names:
                # channel names for this layer
                channel_names = self.layer_channel_names(layer_name)
                # channel data for this layer
                layer_data = tuple([channel_name_and_data[channel_name] for channel_name in channel_names])
                # add async object to list, will use later to get return value
                async_result.append(p.apply_async(convert_channel_data_to_image,
                                                  args=(layer_name, layer_data, self.size)))
            # close pool
            p.close()
            # wait until all processes come back
            p.join()

            # get the return results - more efficient to do this after the join, otherwise if call before join it won't
            # be async anymore, will wait on process for return value
            errors = []
            for async_result in async_result:
                result = async_result.get()
                # check if an error was encountered, will be a string not a dict
                if not isinstance(result, dict):
                    logger.exception(result)
                    errors.append(result)
                else:
                    self.__layer_images.update(result)
            if errors:
                return errors
            return None

    @staticmethod
    def _build_layers_from_channels(channels):
        """
        Build layers from channel names. Combines rgb or rgba into one layer. exr lists r,g,b,a as separate layers
        Skips alpha channel of rgb default layer. Handles single and multi-channel layers, such as Z, raycount which
        are only one channel and then diffuse, RGB, specular, P, N, etc that are multiple channels
        :param channels: list of channels (i.e. diffuse.R, or R)
        :return: the layer names as a dictionary with layers as keys, and channel names as values. format is:
        {
            'multichannel' : [channel1, channel2, channel3]
            'singlechannel' : {channel1}
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

    @staticmethod
    def _sort_dictionary(key):
        """
        Creates a key for sorting by channel
        :param key: a channel, ex R or G, or X...
        :return: returns layer name or if its the channel - R,G,B,A,X,Y,Z returns a numerical mapping
        """
        if key == 'R' or key == 'r':
            return "000010"
        elif key == 'G' or key == 'g':
            return "000020"
        elif key == 'B' or key == 'b':
            return "000030"
        elif key == 'A' or key == 'a':
            return "000040"
        elif key == 'X' or key == 'x':
            return "000110"
        elif key == 'Y' or key == 'y':
            return "000120"
        elif key == 'Z' or key == 'z':
            return "000130"
        else:
            return key

    def _channel_sort_key(self, channel_name):
        """
        creates a key mapping for sorting
        :param channel_name: the full channel name, like diffuse.R
        :return: a list with the layer name and numerical mapping
        """
        return [self._sort_dictionary(x) for x in channel_name.split(".")]

    @staticmethod
    def _open_exr_file_handle(path):
        """
        Open an exr and return a file handle
        :param path: the file path on disk to the exr
        :return: the file handle or error if encountered
        """
        try:
            exr_handle = OpenEXR.InputFile(path)
            return exr_handle
        except IOError as e:
            error = "Error opening {0}. Error is {1}".format(path, e)
            logging.exception(error)
            return error


def get_channel_data(exr_packed_data):
    """
    gets the channel exr_path_and_channels from the exr as string of bytes, outside exr class so can multiprocess
    takes a tuple so can use imap unordered to multiprocess
    :param exr_packed_data: a tuple with the following data:
        [0] path to the exr as a string
        [1] the layer name as a string
        [2] a list of channel names as strings
        [3] size of the exr as a tuple (width, height)
    :return: the channel exr_path_and_channels as a list
    """
    # read all channel exr_path_and_channels from exr at once - most efficient way
    channel_names = exr_packed_data[2]
    file_handle = OpenEXR.InputFile(exr_packed_data[0])
    (all_channel_data) = file_handle.channels(channel_names, Imath.PixelType(Imath.PixelType.FLOAT))
    file_handle.close()
    return convert_channel_data_to_image(exr_packed_data[1], all_channel_data, exr_packed_data[3])


def convert_channel_data_to_image(layer, layer_data, size):
    """
    converts exr channel data to a PIL image object, outside exr class so can multiprocess
    :param layer: name of the layer as a string
    :param layer_data: a tuple of the image data of the exr for the R,G,B or X,Y,Z channels
    :param size: width and height of the image as a tuple
    :return returns an error as a string if encountered, otherwise returns a dict object with
    layername as key, converted channel data to a PIL Image object as value
    """
    try:
        if len(layer_data) == 1:
            layer_data = (layer_data[0], layer_data[0], layer_data[0])

        channels = [array.array('f', c).tolist() for c in (layer_data[0], layer_data[1], layer_data[2])]
        layer_np_array = np.array(channels)
        layer_np_array = layer_np_array.reshape((3, size[1], size[0]))

        # Convert linear -> sRGB
        if not layer == 'Z':
            layer_np_array = np.where(layer_np_array <= 0.0031308, (12.92 * layer_np_array) * 255.0,
                                     (1.055 * (layer_np_array ** (1.0 / 2.4)) - 0.055) * 255.0)
        # clip values above 255
        layer_np_array = np.clip(layer_np_array, 0, 255)
        # convert to 8-bit
        layer_np_array = layer_np_array.astype(np.uint8)
        im = Image.fromarray(layer_np_array.transpose(1, 2, 0), mode='RGB')

        return {layer: im}

    except (IndexError, ValueError) as e:
        error = "Could not convert channel data for layer {0}. Error is {1}".format(layer, e)
        return error

