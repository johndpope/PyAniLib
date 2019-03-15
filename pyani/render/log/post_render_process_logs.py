"""
    For use in Maya, in render globals Post Render Mel box, add:
    python("import post_render_process_logs\npost_render_process_logs.run()")
"""
import os
import shutil
import re
import logging
import datetime
import tempfile
import json
import maya.cmds as cmds
import maya.mel as mel


logger = logging.getLogger()


def setup_logging():
    """
    Sets up logging, to windows temp dir (C:\Users\{user name here}\AppData\Local\Temp\Maya_Post_Render)
    """
    # setup python logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    temp_path = os.path.join(os.path.normpath(tempfile.gettempdir()), "Maya_Post_Render")
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
    now = datetime.datetime.now()
    time_stamp = now.strftime("%Y-%m-%d_%H-%M")
    log_file_name = "{0}\\post_render_process_{1}.txt".format(temp_path, time_stamp)
    f_handler = logging.FileHandler(log_file_name)
    f_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("(%(levelname)s)  %(lineno)d. %(pathname)s - %(funcName)s: %(message)s")
    f_handler.setFormatter(formatter)
    root_logger.addHandler(f_handler)


class AniLogProcessor:
    """
    Class that processes logs and render stats produced by Arnold. Moves logs to the shot directory and adds some
    custom log data. Also combines the stats json files in a shot into one large json file, stored in the sequence
    directory
    """
    def __init__(self):
        # get maya file name - expects file names in format seq###_shot###_LGT_v###
        self.__maya_file_name = self._get_file_name()

        # get the seq and shot from the file name
        self.__seq_name = self._get_sequence_name_from_string(self.__maya_file_name)
        self.__shot_name = self._get_shot_name_from_string(self.__maya_file_name)

        # only support lighting right now, but can expand, this variable drives the log path for the dept, so
        # code to figure out dept just needs to set this
        self.__dept = "lighting"

        # maya log and stats path - can't set a variable path for render stats, and the MTOA_LOG_PATH isn't set
        # by default. Try to get the MTOA_LOG_PATH, and fall back to the workspace because that's where Maya writes
        # to if MTOA_LOG_PATH isn't set
        try:
            self.__maya_log_dir = os.environ["MTOA_LOG_PATH"]
        except KeyError:
            self.__maya_log_dir = mel.eval("workspace -q -directory")

        # log storage path
        self.__log_dir = r"Z:\LongGong\sequences\{0}\{1}\{2}\render_data".format(
            self.__seq_name,
            self.__shot_name,
            self.__dept
        )
        # stat storage path
        self.__stats_dir = r"Z:\LongGong\sequences\{0}\{1}\render_data".format(
            self.__seq_name,
            self.__dept
        )

        # number of a shot's renders logs to keep
        self.__max_history = 5

        # arnold stats under the render key in jason dict
        self.__arnold_stat_categories = [
            "scene creation time",
            "frame time",
            "peak CPU memory used",
            "ray counts"
        ]

        # store maya log file paths
        self.__logs = [
            os.path.join(self.__maya_log_dir, log) for log in os.listdir(self.__maya_log_dir)
            if log.endswith(".log") and "arnold" in log
        ]
        # store json stats paths
        self.__stats = [
            os.path.join(self.__maya_log_dir, log) for log in os.listdir(self.__maya_log_dir)
            if log.endswith(".json") and "arnold" in log
        ]

    def add_custom_log_info(self):
        """
        Adds custom data to the log file after its generated. Currently adds:
            1. The maya file used to render the scene.
        """
        # add maya file name to log at beginning
        self._add_file_name(self.__maya_file_name)

    def move_logs(self):
        """
        Moves the log files produced by Arnold per frame to the shot directory. stored
        in the render data directory of the shot: Z:\LongGong\sequences\Seq###\Shot###\{dept}\render_data\1\
        Always moves to the first history folder.
        """
        # check for logs, skip if none found
        if not self.__logs:
            logger.warning("No log data found in {0}".format(self.__maya_log_dir))
            return

        # if the render_data folder doesn't exist, make it
        if not os.path.exists(self.__log_dir):
            os.makedirs(self.__log_dir)

        # a list of paths to each history folder
        history_dirs = self._get_history(self.__log_dir)
        logger.info("Found {0} history folders in {1}".format(len(history_dirs), self.__log_dir))
        self._update_history(history_dirs)

        # make first history folder. Shouldn't ever exist at this point, because either there
        # isn't any history or if there is the existing history labeled '1' was moved to '2'. However as a precaution
        # check
        first_history_path = os.path.join(self.__log_dir, "1")
        os.mkdir(first_history_path, 0777)

        # base name of log, should be "arnold" from arnold.frame.log but if it isn't this will still work.
        arnold_log_base_name = self.__logs[0].split("\\")[-1].split(".")[0]
        new_log_base_name = "{0}_{1}".format(self.__seq_name, self.__shot_name)
        # move logs
        for log in self.__logs:
            new_name = log.split("\\")[-1].replace(arnold_log_base_name, new_log_base_name)
            new_log_path = os.path.join(first_history_path, new_name)
            shutil.move(log, new_log_path)

        # display paths in log file
        logger.info("Looking for logs in : {0}".format(self.__maya_log_dir))
        logger.info("Moving logs to : {0}\{1}".format(self.__log_dir, first_history_path))
        logger.info("Renamed logs from {0} to {1}".format(arnold_log_base_name, new_log_base_name))

    def move_stats(self):
        """
        Moves the stat json files produced by Arnold per frame to one json file for the whole shot stored
        in the sequence directory: Z:\LongGong\sequences\Seq###\{dept}\render_data\1\
        Always moves to the first history folder.
        """
        # check for stats, skip if none found
        if not self.__stats:
            logger.warning("No stat data found in {0}".format(self.__maya_log_dir))
            return

        # if the render_data folder doesn't exist, make it
        if not os.path.exists(self.__stats_dir):
            os.makedirs(self.__stats_dir)

        # a list of paths to each history folder
        history_dirs = self._get_history(self.__stats_dir)

        self._update_history(history_dirs)

        # make first history folder. Shouldn't ever exist at this point, because either there
        # isn't any history or if there is the existing history labeled '1' was moved to '2'.
        first_history_path = os.path.join(self.__stats_dir, "1")
        os.mkdir(first_history_path, 0777)

        # combine all frames stats into one json and write to the first history folder
        compiled_stats = self._compile_stats()
        json_path = os.path.join(first_history_path, "stats_{0}_{1}.json".format(self.__seq_name, self.__shot_name))
        with open(json_path, "w") as write_file:
            json.dump(compiled_stats, write_file, indent=4)

        # cleanup the arnold stat json files
        for stat_file in self.__stats:
            os.remove(stat_file)

        # display paths in log file
        logger.info("Looking for stats in : {0}".format(self.__maya_log_dir))
        logger.info("Moving stats to : {0}\{1}".format(self.__stats_dir, first_history_path))


    @staticmethod
    def _get_file_name():
        """
        Uses maya cmds to get the base file name (no path)
        :return: returns the base file name including extension -.ma or .mb
        """
        file_path = cmds.file(q=True, sn=True)
        file_name = os.path.basename(file_path)
        return file_name

    def _compile_stats(self):
        """
        Combines stat data from each frame into one json. Uses member variable __arnold_stat_categories to determine
        what stats to grab
        :return: combined stat data in json format
        """
        compiled_shot_stats = {}
        for stat_file in self.__stats:
            with open(stat_file, "r") as read_file:
                orig_stats = json.load(read_file)
                frame = stat_file.split(".")[-2]
                compiled_shot_stats[frame] = {}
                for cat in self.__arnold_stat_categories:
                    compiled_shot_stats[frame][cat] = orig_stats["render 0000"][cat]
        return compiled_shot_stats

    def _get_history(self, history_path):
        """
        Gets the history folders in the path provided
        :param history_path: a path containing render data history
        :return: a list of absolute paths to the render data history or None
        """
        # list contents of render_data folder - ie the history folders
        history_dirs = sorted(
            [
                os.path.join(history_path, folder) for folder in os.listdir(history_path)
                if os.path.isdir(os.path.join(history_path, folder))
            ]
        )
        logger.info("Found {0} history folders in {1}".format(len(history_dirs), self.__stats_dir))
        return history_dirs

    def _update_history(self, history_dirs):
        """
        Updates the render data history by removing the oldest history folder when the maximum to keep has
        been reached. Then increments/renames each history folder by 1.
        :param history_dirs: a list of absolute paths to the history folders
        :return: None
        """
        # check if any history exists, if it does update
        if history_dirs:
            # check if at max history, use greater than just in case someone added something by hand
            if len(history_dirs) >= self.__max_history:
                # delete the oldest history folder and remove from list
                shutil.rmtree(history_dirs[-1], ignore_errors=True)
                logger.info("At max history of {0}, removed {1}".format(self.__max_history, history_dirs[-1]))
                history_dirs.pop(-1)

            # increment remaining history folders, getting a new file path so can move the old history folder
            # to the new folder, ie Z:\LongGong\sequences\Seq#\Shot#\dept\render_data\1\ becomes
            # Z:\LongGong\sequences\Seq#\Shot#\dept\render_data\2\ and so on
            new_history_dirs = []
            for history_dir in history_dirs:
                history_path_parts = history_dir.split("\\")
                current_history_num = history_path_parts[-1]
                new_history_num = str(int(current_history_num) + 1)
                history_path_parts[-1] = new_history_num
                new_history_dirs.append("\\".join(history_path_parts))

            # starting backwards so don't overwrite the folders, i.e. can't move folder 1 to folder 2 if folder 2
            # isn't yet moved. so start with last and move backwards
            for i in reversed(xrange(len(history_dirs))):
                shutil.move(history_dirs[i], new_history_dirs[i])
                logger.info("Moving history from {0} to {1}".format(history_dirs[i], new_history_dirs[i]))

    def _add_file_name(self, file_name):
        """
        Adds the maya file used to render the scene.
        :param file_name: the maya file name. This is just the file name, not a path
        :return: None
        """
        for log in self.__logs:
            with open(log, "r+") as f:
                contents = f.read()
                f.seek(0, 0)
                new_content = "Maya File Name : {0}.\n\n".format(file_name)
                f.write(new_content + contents)

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


def run():
    setup_logging()
    log_processor = AniLogProcessor()
    log_processor.add_custom_log_info()
    log_processor.move_logs()
    log_processor.move_stats()
