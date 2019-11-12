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
import operator
import datetime
from functools import reduce # python 3 compatibility


logger = logging.getLogger()


# regex for matching numerical characters
DIGITS_RE = re.compile(r'\d+')
# regex for matching format directives
FORMAT_RE = re.compile(r'%(?P<pad>\d+)?(?P<var>\w+)')
# supported image types
SUPPORTED_IMAGE_FORMATS = ("exr", "jpg", "jpeg", "tif", "png")  # tuple to work with endswith of scandir
# supported movie containers
SUPPORTED_MOVIE_FORMATS = ("mp4")  # tuple to work with endswith of scandir


class CGTError(Exception):
    """
    Custom exception for CGT download errors
    """
    pass


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
        is_scheduled = self.is_task_scheduled()
        # check for errors getting state
        if not isinstance(is_scheduled, bool):
            return is_scheduled

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
        :returns: True if scheduled, False if not, or error as string
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
            return error
        if re.search(r'\b{0}\b'.format(self.task_name), output):
            return True
        else:
            return False

    def is_task_enabled(self):
        """
        Gets the task state, uses syntax:
        schtasks /query /tn "task name" /v /fo list
        :returns: true if enabled, false if not, or returns error as string
        """
        is_scheduled = self.is_task_scheduled()
        # check for errors getting state
        if not isinstance(is_scheduled, bool):
            return is_scheduled

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
        is_scheduled = self.is_task_scheduled()
        # check for errors getting state
        if not isinstance(is_scheduled, bool):
            return is_scheduled

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

    def get_task_time(self):
        """
        Returns the time a task runs
        :return: the time as a datetime object. Returns the error if an error occurs, or None if
        no errors but can't get time
        """
        p = subprocess.Popen(
            ["schtasks", "/Query", "/tn", self.task_name, "/fo", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, error = p.communicate()
        logging.info("task query is: {0}".format(output))
        for line in output.split("\n"):
            if "Next Run Time:" in line:
                split_line = line.split(" ")[-2:]
                run_time = " ".join(split_line)
                run_time = run_time.replace("\r", "")

                # check for case when disabled, prints Time: N/A
                if "N/A" in run_time:
                    return None

                try:
                    # windows 10 does a hour:minute:second pm/am format
                    time_object = datetime.datetime.strptime(run_time, "%I:%M:%S %p")
                except ValueError:
                    # windows 7 provides a date and time, so convert run time to a time object as just time
                    # windows 7 does day/month/year hours:minutes:seconds
                    time_object = datetime.datetime.strptime(run_time, "%d/%m/%Y %H:%M:%S")

                logging.info("Run time for task {0} is {1}".format(self.task_name, time_object.strftime("%I:%M %p")))
                return time_object

        if p.returncode != 0:
            error = "Problem getting task state for {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                self.task_name,
                p.returncode,
                output,
                error
            )
            logger.error(error)
            return error
        return None

    def set_task_time(self, run_time):
        """
        Sets the time a task runs - deletes existing task then creates a new task. Trying to update an existing task
        causes problems because you need a password, or have to input password when prompted after run schtasks command
        :param run_time: the time as hours:minutes to run as military time
        :return error if encountered as a string, otherwise None
        """
        error = self.delete_task()
        if error:
            return error
        error = self.setup_task(start_time=run_time)
        if error:
            return error
        return None

    def delete_task(self):
        """
        Deletes a task, checks that it exists before deleting
        :return: error if encountered as a string, otherwise None
        """
        is_scheduled = self.is_task_scheduled()
        # check for errors getting state
        if isinstance(is_scheduled, bool) and is_scheduled:
            p = subprocess.Popen(
                ["schtasks", "/Delete", "/tn", self.task_name, "/f"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = p.communicate()
            logging.info("task query is: {0}".format(output))
            if p.returncode != 0:
                error = "Problem deleting task {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
                    self.task_name,
                    p.returncode,
                    output,
                    error
                )
                logger.error(error)
                return error
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
            #print src[i], dest[i]
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


def move_files(src, dest):
    """
    moves files from src to dest (ie copies to new path and deletes from old path).
    :param src: source dir or list of files
    :param dest: destination directory
    :except IOError, OSError: returns the file src and dest and error
    :return: None if no errors, otherwise return error as string
    """
    try:
        for file_path in src:
            shutil.move(file_path, dest)
        return None
    except (IOError, OSError) as e:
        error_msg = "Could not move {0} to {1}. Received error {2}".format(file_path, dest, e)
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
    makes all the directories in the path if they don't exist, handles if some folders already exist
    :param dir_path: a file path
    :return: None if no errors, otherwise return error as string
    """
    # make directory if doesn't exist
    try:
        if not os.path.exists(dir_path):
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


def read_file(file_path):
    """
    Loads a file off disk
    :param file_path: the path to the file data
    :return: a tuple (data, error) where the data is a string and error if occurred is a string, otherwise is None
    """
    try:
        with open(file_path, "r") as file_data:
            return file_data.read(), None
    except (IOError, OSError, EnvironmentError, ValueError) as e:
        error_msg = "Problem loading {0}. Error reported is {1}".format(file_path, e)
        logger.error(error_msg)
        return None, error_msg


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


def write_json(json_path, user_data, indent=4):
    """
    Write to a json file
    :param json_path: the path to the file
    :param user_data: the data to write
    :param indent: optional indent, defaults to 4 spaces for each line
    :return: None if wrote to disk, error if couldn't write
    """
    try:
        with open(json_path, "w") as write_file:
            json.dump(user_data, write_file, indent=indent)
            return None
    except (IOError, OSError, EnvironmentError, ValueError) as e:
        error_msg = "Problem writing {0}. Error reported is {1}".format(json_path, e)
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
            print output, error
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


def open_excel(file_path):
    """
    Open an excel file in excel
    :param file_path: the file path of the excel file, newest excel does not accept forward slash in path
    """
    try:
        from win32com.client import Dispatch
        xl = Dispatch("Excel.Application")
        # otherwise excel is hidden
        xl.Visible = True
        xl.Workbooks.Open(file_path)
    except ImportError:
        print("Cannot run win32com.clinet dispatch. Ignore this error if running Nuke.")


def call_ext_py_api(command, interpreter=None):
    """
    Run a python script
    :param command: External python file to run with any arguments, leave off python interpreter,
    ie just script.py arguments, not python.exe script.py arguments. Must be a list:
    ["script.py", "arg1", ...., "arg n"]

    HINT: To pass python lists as arguments in the command, do a join ",".join(list), then the python
    script being called can parse that as sys.argv[n].split(",") to convert back to a list. Note the ",".join has no
    spaces between comma

    :param interpreter: the python interpreter, i.e. the full path to pyhton.exe.
    if none defaults to cg teamworks python exe
    :return: the output from the script and any errors (from subprocess, not CGT) encountered.
    If no output returns None and if no errors (from subprocess not CGT) returns None
    :raises: CGTError: means an error occurred connecting or accessing CGT, contains the error
    """
    if not interpreter:
        interpreter = os.path.normpath("C:\cgteamwork\python\python.exe")

    if not isinstance(command, list):
        # no output, but an error
        return None, "Invalid command format. Should be a list."
    # use -u to help with buffer
    py_command = [interpreter, "-u"]
    py_command.extend(command)
    logger.info("Command is: {0}".format(' '.join(py_command)))

    p = subprocess.Popen(py_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = p.communicate()

    if p.returncode != 0:
        error = "Problem executing command {0}. Return Code is {1}. Output is {2}. Error is {3} ".format(
            command,
            p.returncode,
            output,
            error
        )
        logger.error(error)
        # no output, but an error
        return None, error

    # check for output
    if output:
        if not "".join(output.split()) == "":
            # check for the word error in output
            for line in output.split("\n"):
                # check for both error and cgt in same line to ensure don't grab a file with the word error in path or
                # file name
                if ("Error" in line or "error" in line) and ("cgt" in line or "CGT" in line):
                    raise CGTError(line)
            return output, None
    # no output and no errors
    return None, None


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


def find_val_in_nested_dict(dictionary, key_path, keys=True):
    """
    Finds a value in a nested dictionary provided a list of keys. To get root level keys, pass [] or None. Returns
    only the keys at that value, unless keys=False is provided. For example:
    { 'key1':
        { 'key2a':
            { key3a':
                ...
            }
        },
        { 'key2b':
            { key3b':
                ...
            }
        }
    }
    if we ask for 'key1' and  keys=True, we will get just ['key2a', 'key2b'] back. If keys=False, we get back:
        { 'key2a':
            { key3a':
                ...
            }
        },
        { 'key2b':
            { key3b':
                ...
            }
        }
    :param dictionary: the dictionary to look through
    :param key_path: a list of the keys. To get root level keys, pass [] or None
    :param keys: boolean indicating whether to return the keys or the keys and any values they have. Note this could
    return a large nested dict.
    :return: the value or None if not found
    """
    try:
        if not key_path:
            return dictionary.keys()
        result = reduce(operator.getitem, key_path, dictionary)
        if keys:
            # handle case when at end of nested dict, and get a value back, won't have keys
            try:
                return result.keys()
            except AttributeError:
                return result
        else:
            return result
    except (TypeError, KeyError):
        return None


def get_shot_name_from_string(string_containing_shot):
    """
    Finds the shot name from a file path. Looks for Shot### or shot###. Shot number is 2 or more digits
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


def get_sequence_name_from_string(string_containing_sequence):
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


def is_valid_shot_name(shot_name):
    """
    Checks if the string is a valid shot. Looks for Shot### or shot###. Shot number is 2 or more digits
    :param shot_name: the shot name as a string
    :return: True if it is a valid shot name, False if not
    """
    shot_name_no_case = shot_name.lower()
    pattern = "shot\d{2,}"
    # make sure the string is valid
    if shot_name_no_case:
        # check if we get a result, if so return it
        if re.search(pattern, shot_name_no_case):
            return True
        else:
            return False
    else:
        return False


def is_valid_seq_name(seq_name):
    """
    Checks if the string is a valid sequence. Looks for Seq### or seq###. Sequence number is 2 or more digits
    :param seq_name: the sequence name as a string
    :return: True if it is a valid shot name, False if not
    """
    seq_name_no_case = seq_name.lower()
    pattern = "seq\d{2,}"
    # make sure the string is valid
    if seq_name_no_case:
        # check if we get a result, if so return it
        if re.search(pattern, seq_name_no_case):
            return True
        else:
            return False
    else:
        return False


def is_valid_frame(string_containing_frame):
    """
    Checks if the string is a valid frame, i.e. '1001'
    :param string_containing_frame: a string with a frame number
    :return: true if a frame, false if not
    """
    pattern = "^\d{4}$"
    # make sure the string is valid
    if string_containing_frame:
        # check if we get a result, if so return it
        if re.search(pattern, string_containing_frame):
            return True
        else:
            return False
    else:
        return False


def is_number(string_var):
    """
    checks if the string is a number
    :param string_var: the string to check
    :return: returns True if it is a number, otherwise False
    """
    try:
        float(string_var)
    except ValueError:
        return False
    else:
        return True


def number_of_digits(num):
    """
    Count the number of digits in a number using log, since len(str(num)) is much slower
    :param num: a number
    :return: the number of digits
    """
    # Uses string modulo instead of str(i)
    return len("%i" % num)
