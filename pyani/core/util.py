import re
import shutil
import os
import logging
import OpenEXR
# include Imath (which OpenEXR uses) and ffmpeg so that standalone exe works.
import Imath
import json
from scandir import scandir
from subprocess import Popen, call
from PIL import Image

# regex for matching numerical characters
DIGITS_RE = re.compile(r'\d+')
# regex for matching format directives
FORMAT_RE = re.compile(r'%(?P<pad>\d+)?(?P<var>\w+)')
# supported image types
SUPPORTED_IMAGE_FORMATS = ("exr", "jpg", "jpeg", "tif", "png")  # tuple to work with endswith of scandir
# supported movie containers
SUPPORTED_MOVIE_FORMATS = ("mp4")  # tuple to work with endswith of scandir


class AniVars(object):
    '''
    object that holds variables for shot, sequence and scenes. Parses based off a shot path since there is no access
    to a show environment vars. Option to not provide a shot path, in which case a dummy path is created
    '''

    def __init__(self, shot_path=None):
        self.desktop = os.path.expanduser("~/Desktop")
        self.seq_shot_list = self._get_sequences_and_shots("Z:\\LongGong\\PyANiTools\\app_data\\Shared\\sequences.json")

        if not shot_path:
            shot_path = os.path.normpath("Z:\LongGong\sequences\Seq180\Shot280")
        self.seq_name = self._get_active_sequence_name(shot_path)
        self.shot_name = self._get_active_shot_name(shot_path)

        # shot directories
        self.shot_dir = os.path.normpath("Z:\LongGong\sequences\{0}\{1}".format(self.seq_name, self.shot_name))
        self.shot_light_dir = os.path.normpath("{0}\lighting".format(self.shot_dir))
        self.shot_light_work_dir = os.path.normpath("{0}\work".format(self.shot_light_dir))
        self.shot_maya_dir = os.path.normpath("{0}\scenes".format(self.shot_light_work_dir))
        self.shot_comp_dir = os.path.normpath("{0}\composite".format(self.shot_dir))
        self.shot_comp_work_dir = os.path.normpath("{0}\work".format(self.shot_comp_dir))
        self.shot_comp_plugin_dir = os.path.normpath("Z:\LongGong\sequences\{0}\{1}\Composite\plugins".format(
            self.seq_name, self.shot_name))

        # movie directories
        self.movie_dir = os.path.normpath("Z:\LongGong\movie")
        self.seq_movie_dir = os.path.normpath("{0}\sequences".format(self.movie_dir))
        self.shot_movie_dir = os.path.normpath("{0}\sequences\{1}".format(self.movie_dir, self.seq_name))

        # comp plugin, script, template lib directories
        self.plugin_show = os.path.normpath("Z:\LongGong\lib\comp\plugins")
        self.plugin_seq = os.path.normpath("Z:\LongGong\lib\sequences\{0}\comp\plugins".format(self.seq_name))
        self.script_show = os.path.normpath("Z:\LongGong\lib\comp\scripts")
        self.script_seq = os.path.normpath("Z:\LongGong\lib\sequences\{0}\comp\scripts".format(self.seq_name))
        self.templates_show = os.path.normpath("Z:\LongGong\lib\comp\\templates")
        self.templates_seq = os.path.normpath("Z:\LongGong\lib\sequences\{0}\comp\\templates".format(self.seq_name))

        # image directories
        self.image_dir = os.path.normpath("Z:\LongGong\images")
        self.seq_image_dir = os.path.normpath("{0}\{1}".format(self.image_dir, self.seq_name))
        self.shot_image_dir = os.path.normpath("{0}\{1}".format(self.seq_image_dir, self.shot_name))

        # shot data
        if shot_path:
            seq = self.seq_shot_list[self.seq_name]
            for shot in seq:
                if shot == self.shot_name:
                    self.first_frame = self.seq_shot_list[self.seq_name]["first_frame"]
                    self.last_frame = self.seq_shot_list[self.seq_name]["last_frame"]
                    self.frame_range = "{0}-{1}".format(str(self.first_frame), str(self.last_frame))
                    break
        else:
            self.first_frame = None
            self.last_frame = None
            self.frame_range = None

        self.places = [
            self.movie_dir,
            self.seq_movie_dir,
            self.shot_movie_dir,
            self.image_dir,
            self.seq_image_dir,
            self.shot_image_dir,
            self.desktop
        ]

    def get_sequence_list(self):
        return self.seq_shot_list.keys()

    def get_shot_list(self, seq_name):
        shot_list = self.seq_shot_list[self.seq_name]
        return [shot["Shot"] for shot in shot_list]

    @staticmethod
    def _get_sequences_and_shots(file_path):
        """
        Reads the json dict of sequences, shots, and frame ranges
        :param file_path: path to json file
        :return: a python dict as with Seq### as key, then a list of dicts with keys "Shot", "first_frame", "last_frame"
        """
        return load_json(file_path)

    @staticmethod
    def _get_active_sequence_name(file_path):
        """
        Finds the sequence name from a file path. Looks for Seq### or seq###. Sequence number is 2 or more digits
        :param file_path: the absolute file path
        :return: the seq name as Seq### or seq###
        """
        pattern = "[a-zA-Z]{3}\d{2,}"
        return re.search(pattern, file_path).group()

    @staticmethod
    def _get_active_shot_name(file_path):
        """
        Finds the shot name from a file path. Looks for Shot### or seq###. Shot number is 2 or more digits
        :param file_path: the absolute file path
        :return: the shot name as Shot### or shot###
        """
        pattern = "[a-zA-Z]{4}\d{2,}"
        return re.search(pattern, file_path).group()


# logging
"""
Level	Numeric value
CRITICAL	50
ERROR	    40
WARNING	    30
INFO	    20
DEBUG	    10
NOTSET	    0
"""


def logging_disabled(state):
    LOG.disabled = state


LOG = logging.getLogger('pyani')
LOG.addHandler(logging.StreamHandler())
LOG.setLevel(10)


def load_json(json_path):
    """
    Loads a json file
    :param json_path: the path to the json data
    :return: the json data, or None if couldn't load
    """
    try:
        with open(json_path, "r") as read_file:
            return json.load(read_file)
    except EnvironmentError:
        return None


def write_json(json_path, user_data):
    """
    Write to a json file
    :param json_path: the path to the file
    :param user_data: the data to write
    :return: Success message as string if wrote to file, None if didn't
    """
    try:
        with open(json_path, "w") as write_file:
            json.dump(user_data, write_file)
            return "Successfully wrote data to: {0}".format(write_file)
    except EnvironmentError:
        return None


def launch_app(app, *args):
    """
    Launch an external application
    :param app: the path to the program to execute
    :param args: any arguments to pass to the program
    """
    cmd = [app]
    for arg in args:
        cmd.append(arg)

    p = Popen([cmd], shell=True)

    if p.returncode is not None:
        LOG.debug("App Open Failed for {0}. Error: {1}".format(cmd, p.returncode))


def copy_image(source, dest):
    '''
    Copies a frame from the source file to the destination file or folder. If the file exists will
    overwrite
    :param source: the path to the source file
    :param dest: the path to the destination
    :raises: IOError if problem copying

    '''
    # asterisk on destination name required to suppress input on whether its a file or directory
    # /Y overwrites without asking
    cmd = ['xcopy', source, (dest+"*"), '/Y']
    p = Popen(cmd, stdin= PIPE, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()
    if p.returncode != 0:
        LOG.debug("Copy Failed {0} {1} {2}".format(p.returncode, output, error))


def make_dir(dir_path):
    '''
    Build the directory
    :return: True if successful and False if unsuccessful
    '''
    try:
        if os.path.exists(dir_path):
            # this will remove regardless of whether its empty or read only
            shutil.rmtree(dir_path, ignore_errors=True)
        os.mkdir(dir_path, 0777)
    except IOError:
        return False
    return True


def rm_dir(dir_path):
    """
    removes a directory if it exists
    :param dir_path: a path to a directory
    :return: True if successful and False if unsuccessful
    """
    try:
        if os.path.exists(dir_path):
            # this will remove regardless of whether its empty or read only
            shutil.rmtree(dir_path, ignore_errors=True)
    except IOError:
        return False
    return True


def get_images_from_dir(dir_path):
    """
    get list of images in the directory, takes any image of supported types, so if directory has a mix, for
    # example jpeg and exr, it will grab both.
    :param dir_path: path to a directory
    :return: a list of the images in the directory
    """
    return [f.path for f in scandir(dir_path) if f.path.endswith(SUPPORTED_IMAGE_FORMATS)]


def convert_image(image_path, convert_format):
    """
    change to a different image format - all supported except exrs
    :param image_path: the image to convert
    :param convert_format: the format to convert to
    :return: the converted image
    """
    im = Image.open(image_path)
    image_ext_removed = image_path.split(".")[:-1]
    new_image = '{0}.{1}'.format(image_ext_removed, convert_format)
    im.save(new_image)
    return new_image


def get_exr_size(exr):
    """
    gets the exr image size which is the display and data windows
    :param exr: a valid exr image
    :return: the display and data windows in a dict, None if it isn't an exr file
    """
    if OpenEXR.isOpenExrFile(exr):
        infile = OpenEXR.InputFile(exr)
        h = infile.header()
        h['displayWindow'] = Imath.Box2i(Imath.point(-1, -1), Imath.point(1998, 1080))
        h['dataWindow'] = Imath.Box2i(Imath.point(-1, -1), Imath.point(1998, 1080))
        return {"display": h['displayWindow'], "data": h['dataWindow']}
    return None


def convert_to_sRGB(red, green, blue):
    """
    Convert linear to sRGB
    :param red: the red channel data
    :param green: the green channel data
    :param blue: the blue channel data
    :return: the color transformed channel data as a red, green blue tuple
    """

    def encode_to_sRGB(v):
        """
        Convenience function, does the math to convert linear to sRGB
        :param v: the pixel value as linear
        :return: the pixel value as sRGB
        """
        if v <= 0.0031308:
            return (v * 12.92) * 255.0
        else:
            return (1.055 * (v ** (1.0 / 2.2)) - 0.055) * 255.0
    rgb_size = range(len(red))
    for i in rgb_size:
        red[i] = encode_to_sRGB(red[i])
        green[i] = encode_to_sRGB(green[i])
        blue[i] = encode_to_sRGB(blue[i])
    return red, green, blue
