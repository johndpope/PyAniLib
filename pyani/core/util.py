import re
import shutil
import os
import sys
import time
import inspect
import json
from scandir import scandir
import subprocess
from bisect import bisect_left
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


class WinTaskScheduler:
    """Wrapper around windows task scheduler command line tool named schtasks. Provides functionality to create,
    enable/disable, and query state
    """
    def __init__(self, task_name, command):
        self.__task_name = task_name
        self.__task_command = command

    @property
    def task_name(self):
        """Return the task name
        """
        return self.__task_name

    @property
    def task_command(self):
        """Return the task command
        """
        return self.__task_command

    def setup_task(self,  schedule_type="daily", start_time="12:00"):
        """
        creates a task in windows scheduler using the command line tool schtasks. Uses syntax:
        schtasks /create /sc <ScheduleType> /tn <TaskName> /tr <TaskRun>
        ex:
        schtasks /Create /sc hourly /tn pyanitools_update /tr "C:\\PyAniTools\\installed\\PyAppMngr\\PyAppMngr.exe"

        :param schedule_type: when to run, options are:
            MINUTE, HOURLY, DAILY, WEEKLY, MONTHLY, ONCE, ONSTART, ONLOGON, ONIDLE
        :param start_time: optional start time
        :return: any errors, otherwise None
        """
        is_scheduled, error = self.is_task_scheduled()
        if error:
            return error

        if not is_scheduled:
            p = subprocess.Popen(
                [
                    "schtasks",
                    "/Create",
                    "/sc", schedule_type,
                    "/tn", self.task_name,
                    "/tr", self.task_command,
                    "/st", start_time
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = p.communicate()
            if p.returncode != 0:
                error = "Problem scheduling task {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                    self.task_name,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error
        return None

    def is_task_scheduled(self):
        """
        checks for a task in windows scheduler using the command line tool schtasks. Uses syntax:
        schtasks /query which returns a table format.
        :returns: True if scheduled, False if not. Also returns error if encountered any, otherwise None
        """
        p = subprocess.Popen(["schtasks", "/Query"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
        if p.returncode != 0:
            error = "Problem querying task {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                self.task_name,
                p.returncode,
                output,
                error
            )
            logger.error(error)
            return False, error
        if re.search(r'\b{0}\b'.format(self.task_name), output):
            return True, None
        else:
            return False, None

    def is_task_enabled(self):
        """
        Gets the task state, uses syntax:
        schtasks /query /tn "task name" /v /fo list
        :returns: true if enbaled, false if not, or returns error as string
        """
        is_scheduled, error = self.is_task_scheduled()
        if error:
            return error
        # only attempt to disable or enable if the task exists
        if is_scheduled:
            p = subprocess.Popen(
                ["schtasks", "/Query", "/tn", self.task_name, "/v", "/fo", "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = p.communicate()
            logging.info("task query is: {0}".format(output))
            for line in output.split("\n"):
                if "scheduled task state" in line.lower():
                    if "enabled" in line.lower():
                        return True
                    # don't need to look for 'disabled', if the word enabled isn't present, then we default to
                    # task disabled
                    else:
                        return False
            if p.returncode != 0:
                error = "Problem getting task state for {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                    self.task_name,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error

    def set_task_enabled(self, enabled):
        """
        set the state of a task, either enabled or disabled. calls:
        schtasks.exe /Change /TN "task name" [/Disable or /Enable]
        :param enabled: True or False
        :return: error as string or None
        """
        is_scheduled, error = self.is_task_scheduled()
        if error:
            return error
        # only attempt to disable or enable if the task exists
        if is_scheduled:
            if enabled:
                state = "/Enable"
            else:
                state = "/Disable"
            p = subprocess.Popen(
                ["schtasks", "/Change", "/tn", self.task_name, state],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = p.communicate()
            if p.returncode != 0:
                error = "Problem setting task {0} to {1}. Return Code is {2}. Output is {3}. Error is {4} ".format(
                    self.task_name,
                    state,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error
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


def make_file(file_name):
    """
    makes a file on disk
    :param file_name: name of the file to create, absolute path
    :except IOError, OSError: returns the filename and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        with open(file_name, "w") as init_file:
            init_file.write("# init.py created by PyAniTools\n")
            init_file.close()
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not move {0} to {1}. Received error {2}".format(file_name, e)
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
    except (IOError, OSError, EnvironmentError, ValueError) as e:
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
    except (IOError, OSError, EnvironmentError, ValueError) as e:
        error_msg = "Problem loading {0}. Error reported is {1}".format(json_path, e)
        logger.error(error_msg)
        return error_msg


def launch_app(app, args, open_shell=False, wait_to_complete=False, open_as_new_process=False):
    """
    Launch an external application
    :param app: the path to the program to execute
    :param args: any arguments to pass to the program as a list, if none pass None
    :param open_shell: optional, defaults to false, if true opens command prompt
    :param wait_to_complete: defaults to False, waits for process to finish - this will freeze app launching subprocess
    :param open_as_new_process: opens as a new process not tied to app launching subprocess
    :return: None if no errors, otherwise return error as string
    """

    cmd = [app]
    for arg in args:
        cmd.append(arg)

    try:
        if wait_to_complete and open_as_new_process:
            p = subprocess.Popen(cmd,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            output, error = p.communicate()
            if p.returncode != 0:
                error = "Problem executing command {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                    cmd,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error
            else:
                return None
        elif wait_to_complete and not open_as_new_process:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = p.communicate()
            if p.returncode != 0:
                error = "Problem executing command {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                    cmd,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error
            else:
                return None
        elif open_as_new_process and not wait_to_complete:
            subprocess.Popen(cmd,
                             creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
                             close_fds=True
                             )
        else:
            subprocess.Popen(cmd, shell=open_shell)
    except Exception as e:
        error_msg = "App Open Failed for {0}. Error: {1}".format(cmd, e)
        logger.error(error_msg)
        return error_msg
    return None


def get_script_dir(follow_symlinks=True):
    """
    Find the directory a script is running out of. orks on CPython, Jython, Pypy. It works if the script is executed
    using execfile() (sys.argv[0] and __file__ -based solutions would fail here). It works if the script is inside
    an executable zip file (/an egg). It works if the script is "imported" (PYTHONPATH=/path/to/library.zip python
    -mscript_to_run) from a zip file; it returns the archive path in this case. It works if the script is compiled
    into a standalone executable (sys.frozen). It works for symlinks (realpath eliminates symbolic links). It works
    in an interactive interpreter; it returns the current working directory in this case
    :param follow_symlinks: defaults to True
    :return: the directory of the the path
    """
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)


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


def find_closest_number(list_numbers, number_to_find, use_smallest=False):
    """
    Assumes list_numbers is sorted. Returns the closest number in the list to number_to_find.  If two numbers are
    equally close, return the smaller of the two numbers, unless use_smallest=True. When use_smallest is True, it always
    returns the smaller number, even if it isn't the closest. Useful for finding the closest previous frame in
    image sequences.
    :param list_numbers: a list of numeric values
    :param number_to_find: the number to find
    :param use_smallest: whether to always return the closest smallest number
    :return: the closest number
    """
    # get the position the number_to_find would have in the list of numbers
    pos = bisect_left(list_numbers, number_to_find)
    # at start / first element
    if pos == 0:
        return list_numbers[0]
    # at end / last element
    if pos == len(list_numbers):
        return list_numbers[-1]
    # number before the number provided
    before = list_numbers[pos - 1]
    # number after the number we provided
    after = list_numbers[pos]
    # check if the smaller number should be returned
    if use_smallest:
        return before
    # returns the closer of the two numbers, unless they are equally far away, then returns smaller number
    if after - number_to_find < number_to_find - before:
        return after
    else:
        return before


def convert_to_sRGB(red, green, blue):
    """
    Convert linear to sRGB
    :param red: the red channel data as a list
    :param green: the green channel data as a list
    :param blue: the blue channel data as a list
    :return: the color transformed channel data as a list per r,g,b channel
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
