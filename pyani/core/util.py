import re
import shutil
import os
import time
import json
from scandir import scandir
from subprocess import Popen, PIPE
import logging
import Queue
import threading


logger = logging.getLogger()


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

    List of Ani Vars:

    print AniVar_instance

    '''

    def __init__(self, shot_path=None):
        # not dependent on seq or shot
        self.desktop = os.path.expanduser("~/Desktop")
        self.seq_shot_list = self._get_sequences_and_shots("C:\\PyAniTools\\app_data\\Shared\\sequences.json")
        self.nuke_user_dir = os.path.join(os.path.expanduser("~"), ".nuke")
        self.shot_master_template = "shot_master.nk"
        # os.path.join has issues, maybe due to .nuke? String concat works
        self.nuke_custom_dir = self.nuke_user_dir + "\\pyanitools"
        self.plugins_json_name = "plugins.json"
        self.templates_json_name = "templates.json"
        # movie directories
        self.movie_dir = os.path.normpath("Z:\LongGong\movie")
        self.seq_movie_dir = os.path.normpath("{0}\sequences".format(self.movie_dir))
        # comp plugin, script, template lib directories
        self.plugin_show = os.path.normpath("Z:\LongGong\lib\comp\plugins")
        self.templates_show = os.path.normpath("Z:\LongGong\lib\comp\\templates")
        # image directories
        self.image_dir = os.path.normpath("Z:\LongGong\images")
        # begin vars dependent on seq and shot
        self.seq_name = None
        self.shot_name = None
        self.shot_dir = None
        self.shot_light_dir = None
        self.shot_light_work_dir = None
        self.shot_maya_dir = None
        self.shot_comp_dir = None
        self.shot_comp_work_dir = None
        self.shot_comp_plugin_dir = None
        self.shot_movie_dir = None
        self.seq_lib = None
        self.seq_comp_lib = None
        self.plugin_seq = None
        self.script_seq = None
        self.templates_seq = None
        self.seq_image_dir = None
        self.shot_image_dir = None
        self.shot_layer_dir = None
        self.first_frame = None
        self.last_frame = None
        self.frame_range = None

        if shot_path:
            self.seq_name = self._get_sequence_name_from_string(shot_path)
            self.shot_name = self._get_shot_name_from_string(shot_path)
            self._make_seq_vars()
            self._make_shot_vars()

        self.places = [
            self.movie_dir,
            self.seq_movie_dir,
            self.image_dir,
            self.desktop
        ]

    # produce better output
    def __str__(self):
        return json.dumps(vars(self),indent=4 )

    def __repr__(self):
        return '<pyani.core.util.AniVars "Seq{0}, Shot{1}">'.format(self.seq_name, self.shot_name)

    def is_valid_seq(self, seq):
        if self._get_sequence_name_from_string(seq):
            return True
        else:
            return False

    def is_valid_shot(self, shot):
        if self._get_shot_name_from_string(shot):
            return True
        else:
            return False

    def get_sequence_list(self):
        return self.seq_shot_list.keys()

    def get_shot_list(self):
        shot_list = self.seq_shot_list[self.seq_name]
        return [shot["Shot"] for shot in shot_list]

    def update_using_shot_path(self, shot_path):
        self.seq_name = self._get_sequence_name_from_string(shot_path)
        self.shot_name = self._get_shot_name_from_string(shot_path)
        self._make_seq_vars()
        self._make_shot_vars()

    def update(self, seq_name, shot_name=None):
        self.seq_name = seq_name
        self._make_seq_vars()
        if shot_name:
            self.shot_name = shot_name
            self._make_shot_vars()

    def _make_seq_vars(self):
        self.seq_lib = os.path.normpath("Z:\LongGong\lib\sequences\{0}".format(self.seq_name))
        # movie directories
        self.seq_movie_dir = os.path.normpath("{0}\sequences".format(self.movie_dir))
        # image directories
        self.seq_image_dir = os.path.normpath("{0}\{1}".format(self.image_dir, self.seq_name))
        # comp directories
        self.seq_comp_lib = os.path.normpath("{0}\comp".format(self.seq_lib))
        self.plugin_seq = os.path.normpath("{0}\plugins".format(self.seq_comp_lib))
        self.templates_seq = os.path.normpath("{0}\\templates".format(self.seq_comp_lib))

    def _make_shot_vars(self):
        # shot directories in shot
        self.shot_dir = os.path.normpath("Z:\LongGong\sequences\{0}\{1}".format(self.seq_name, self.shot_name))
        self.shot_light_dir = os.path.normpath("{0}\lighting".format(self.shot_dir))
        self.shot_light_work_dir = os.path.normpath("{0}\work".format(self.shot_light_dir))
        self.shot_maya_dir = os.path.normpath("{0}\scenes".format(self.shot_light_work_dir))
        self.shot_comp_dir = os.path.normpath("{0}\composite".format(self.shot_dir))
        self.shot_comp_work_dir = os.path.normpath("{0}\work".format(self.shot_comp_dir))
        self.shot_comp_plugin_dir = os.path.normpath("Z:\LongGong\sequences\{0}\{1}\Composite\plugins".format(
            self.seq_name, self.shot_name)
        )
        # directories for shot outside shot directory

        # image directories
        self.shot_image_dir = os.path.normpath("{0}\{1}".format(self.seq_image_dir, self.shot_name))
        self.shot_layer_dir = os.path.normpath("{0}\{1}".format(self.shot_image_dir, "\light\layers"))
        # movie directories
        self.shot_movie_dir = os.path.normpath("{0}\sequences\{1}".format(self.movie_dir, self.seq_name))
        # frames
        for shot in self.seq_shot_list[self.seq_name]:
            if shot["Shot"] == self.shot_name:
                self.first_frame = shot["first_frame"]
                self.last_frame = shot["last_frame"]
                self.frame_range = "{0}-{1}".format(str(self.first_frame), str(self.last_frame))
                break

    @staticmethod
    def _get_sequences_and_shots(file_path):
        """
        Reads the json dict of sequences, shots, and frame ranges
        :param file_path: path to json file
        :return: a python dict as with Seq### as key, then a list of dicts with keys "Shot", "first_frame", "last_frame"
        """
        return load_json(file_path)

    @staticmethod
    def _get_sequence_name_from_string(string_containing_sequence):
        """
        Finds the sequence name from a file path. Looks for Seq### or seq###. Sequence number is 2 or more digits
        :param string_containing_sequence: the absolute file path
        :return: the seq name as Seq### or seq### or None if no seq found
        """
        pattern = "[a-zA-Z]{3}\d{2,}"
        # make sure the string is valid
        if string_containing_sequence:
            # check if we get a result, if so return it
            if re.search(pattern, string_containing_sequence):
                return re.search(pattern, string_containing_sequence).group()
            else:
                return None
        else:
            return None

    @staticmethod
    def _get_shot_name_from_string(string_containing_shot):
        """
        Finds the shot name from a file path. Looks for Shot### or seq###. Shot number is 2 or more digits
        :param string_containing_shot: the absolute file path
        :return: the shot name as Shot### or shot### or None if no shot found
        """
        pattern = "[a-zA-Z]{4}\d{2,}"
        # make sure the string is valid
        if string_containing_shot:
            # check if we get a result, if so return it
            if re.search(pattern, string_containing_shot):
                return re.search(pattern, string_containing_shot).group()
            else:
                return None
        else:
            return None

"""
Threaded copy - faster than multi proc copy, and 2-3x speed up over sequential copy
"""
fileQueue = Queue.Queue()


class ThreadedCopy:
    """
    Copies files using threads
    :param src a list of the files to copy
    :param dest: a list of the file names to copy to
    :param threads: number of threads to use, defaults to 16
    :except IOError, OSError: returns the file src and dest and error
    :return: None if no errors, otherwise return error as string
    """
    def __init__(self, src, dest, threads=16):
        self.thread_worker_copy(src, dest, threads)

    def copy_worker(self):
        while True:
            src, dest = fileQueue.get()
            try:
                shutil.copy(src, dest)
            except (IOError, OSError) as e:
                error_msg = "Could not copy {0} to {1}. Received error {2}".format(src, dest, e)
                logger.error(error_msg)
            fileQueue.task_done()

    def thread_worker_copy(self, src, dest, threads):
        for i in range(threads):
            t = threading.Thread(target=self.copy_worker)
            t.daemon = True
            t.start()
        for i in range(0, len(src)):
            fileQueue.put((src[i], dest[i]))
        fileQueue.join()


def copy_file(src, dest):
    """
    Copies file from src to dest.
    :param src: source file
    :param dest: destination directory or file - overwrites if exists
    :except IOError, OSError: returns the file src and dest and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        shutil.copy(src, dest)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not copy {0} to {1}. Received error {2}".format(src, dest, e)
        logger.error(error_msg)
        return error_msg


def copy_files(src, dest, ext=None):
    """
    Copies all files from src to dest. Optional extension can be provided to filter
    what files are copied
    :param src: source directory
    :param dest: destination directory
    :param ext: extension to filter for
    :except IOError, OSError: returns the file src and dest and error
    :return: None if no errors, otherwise return error as string
    """
    s = None
    d = None
    try:
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            # filter out files when extension provided
            if ext is not None and s.endswith(ext):
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            else:
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not copy {0} to {1}. Received error {2}".format(s, d, e)
        logger.error(error_msg)
        return error_msg


def move_file(src, dest):
    """
    moves file from src to dest (ie copies to new path and deletes from old path).
    :param src: source file
    :param dest: destination directory or file
    :except IOError, OSError: returns the file src and dest and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        shutil.move(src, dest)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not move {0} to {1}. Received error {2}".format(src, dest, e)
        logger.error(error_msg)
        return error_msg


def delete_file(file_path):
    """
    Deletes file
    :param file_path: the file to delete - absolute path. if the file doesn't exist does nothing
    :except IOError, OSError: returns the file  and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not delete {0}. Received error {1}".format(file_path, e)
        logger.error(error_msg)
        return error_msg


def delete_by_day(num_days, file_path):
    """
    Delete file older than a certain date
    :param num_days: any files older than this are deleted
    :param file_path: the full path to the file
    :return: none if no error, or the error if encountered - will be a IOError or OSError
    """
    # get the time in seconds, note a day is 24 hours * 60 min * 60 sec
    time_in_secs = time.time() - (num_days * 24 * 60 * 60)
    # check that the path exists before trying to get creation time
    if os.path.exists(file_path):
        stat = os.stat(file_path)
        # check if creation time is older than
        if stat.st_ctime <= time_in_secs:
            error = delete_file(file_path)
            logger.info("Deleted the following log: {0}")
            return error


def delete_all(dir_path):
    """
    Deletes files and directories
    :param dir_path: the path to the directory of files - absolute path, can contain subdirs
    :except IOError, OSError: returns the file  and error
     :return: None if no errors, otherwise return error as string
    """
    try:
        full_paths = [os.path.join(dir_path, file_name) for file_name in os.listdir(dir_path)]
        # note that if there aren't any files in directory this loop won't run
        for file_name in full_paths:
            if os.path.isdir(file_name):
                rm_dir(file_name)
            else:
                delete_file(file_name)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not delete {0}. Received error {1}".format(file_name, e)
        logger.error(error_msg)
        return error_msg


def make_dir(dir_path):
    '''
    Build the directory
    :except IOError, OSError: returns the directory and error
    :return: None if no errors, otherwise return error as string
    '''
    try:
        if os.path.exists(dir_path):
            # this will remove regardless of whether its empty or read only
            shutil.rmtree(dir_path, ignore_errors=True)
        os.mkdir(dir_path, 0777)
    except (IOError, OSError) as e:
        error_msg = "Could not make directory {0}. Received error {1}".format(dir_path, e)
        logger.error(error_msg)
        return error_msg
    return None


def make_all_dir_in_path(dir_path):
    """
    makes all the directories in the path if they don't exist
    :param dir_path: a file path
    :return: None if no errors, otherwise return error as string
    """
    # make directory if doesn't exist
    try:
        os.makedirs(dir_path)
    except (IOError, OSError) as e:
        if not os.path.isdir(dir_path):
            error_msg = "Could not make directory {0}. Received error {1}".format(dir_path, e)
            logger.error(error_msg)
            return error_msg
    return None


def rm_dir(dir_path):
    """
    removes a directory if it exists
    :param dir_path: a path to a directory
    :except IOError, OSError: returns the directory and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        if os.path.exists(dir_path):
            # this will remove regardless of whether its empty or read only
            shutil.rmtree(dir_path, ignore_errors=True)
    except (IOError, OSError) as e:
        error_msg = "Could not remove directory {0}. Received error {1}".format(dir_path, e)
        logger.error(error_msg)
        return error_msg
    return None


def get_subdirs(path):
    """
    return a list of directory names not starting with '.' under given path.
    :param path: the directory path
    :return: a list of subdirectories, none if no subdirectories
    """
    dir_list = []
    for entry in scandir(path):
        if not entry.name.startswith('.') and entry.is_dir():
            dir_list.append(entry.name)
    return dir_list


def natural_sort(iterable):
    """
    Sorts a iterable using natural sort
    :param iterable: The python iterable to be sorted. - ie a list / etc...
    :return: the sorted list
    """
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(iterable, key=alphanum_key)


def load_json(json_path):
    """
    Loads a json file
    :param json_path: the path to the json data
    :return: the json data, or error if couldn't load
    """
    try:
        with open(json_path, "r") as read_file:
            return json.load(read_file)
    except (IOError, OSError, EnvironmentError) as e:
        error_msg = "Problem loading {0}. Error reported is {1}".format(json_path, e)
        logger.error(error_msg)
        return error_msg


def write_json(json_path, user_data, indent=0):
    """
    Write to a json file
    :param json_path: the path to the file
    :param user_data: the data to write
    :param indent: optional indent
    :return: None if wrote to disk, error if couldn't write
    """
    try:
        with open(json_path, "w") as write_file:
            json.dump(user_data, write_file, indent=indent)
            return None
    except (IOError, OSError, EnvironmentError) as e:
        error_msg = "Problem loading {0}. Error reported is {1}".format(json_path, e)
        logger.error(error_msg)
        return error_msg


def launch_app(app, args):
    """
    Launch an external application
    :param app: the path to the program to execute
    :param args: any arguments to pass to the program as a list
    :return: None if no errors, otherwise return error as string
    """
    cmd = [app]
    for arg in args:
        cmd.append(arg)
    try:
        Popen(cmd, shell=False)
    except Exception as e:
        error_msg = "App Open Failed for {0}. Error: {1}".format(cmd, e)
        logger.error(error_msg)
        return error_msg
    return None


def get_images_from_dir(dir_path):
    """
    get list of images in the directory, takes any image of supported types, so if directory has a mix, for
    # example jpeg and exr, it will grab both.
    :param dir_path: path to a directory
    :return: a list of the images in the directory, or error if encountered
    """
    try:
        images = [f.path for f in scandir(dir_path) if f.path.endswith(SUPPORTED_IMAGE_FORMATS)]
    except (IOError, OSError) as e:
        error_msg = "Error getting a list of images with ext {0} from {1}. Reported error {2}".format(
            SUPPORTED_IMAGE_FORMATS,
            dir_path,
            e
        )
        logger.exception(error_msg)
        return error_msg
    return images


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
