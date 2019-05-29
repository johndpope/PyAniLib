"""
    For use in Maya, in render globals:

    Pre Render Mel box, add:
    python("import post_render_process_logs\npost_render_process_logs.setup()")

    Post Render Mel box, add:
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
import maya.app.renderSetup.model.renderSetup as renderSetup


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
    custom log data. Also combines the stats json files in a shot into one large json file for the shot to reduce load
    times for the viewer. Stored in:
    Z:\LongGong\sequences\{sequence}\{dept}\render_data\{shot}\
    ex: Z:\LongGong\sequences\Seq040\lighting\render_data\Shot260\

    Maya / Arnold writes logs and stats to :
    Z:\LongGong\sequences\{sequence}\{shot}\{dept}\render_data\
    ex: Z:\LongGong\sequences\Seq040\Shot260\lighting\render_data\

    Show logs are stored in:
    Z:\LongGong\sequences\{sequence}\{shot}\{dept}\render_data\{render layer}\history
    ex: Z:\LongGong\sequences\Seq040\Shot260\lighting\render_data\env\1

    Stat files are stored in one json file per render layer for each shot in a sequence (Note the difference from logs
    is we store all frames in one file, instead of a file per frame):
    Z:\LongGong\sequences\{sequence}\{dept}\render_data\{shot}\{render layer}\history
    ex: Z:\LongGong\sequences\Seq040\lighting\render_data\Shot260\env\1

    Format of stat file is:
    {
        render layer:
        {
            frame:
            {
                arnold stat name (from self.__arnold_stat_categories):
                {
                    stats
                },
                ...
            },
            ...
        },
        ...
    }



    """
    def __init__(self, seq, shot, dept, maya_file_name):
        self.maya_file_name = maya_file_name
        self.seq_name = seq
        self.shot_name = shot
        self.dept = dept

        # number of a shot's renders logs to keep
        self.__max_history = 5

        # holds all the log and stats paths on disk, set by store_log_and_stat_paths
        self.logs = {}
        self.stats = {}

        # arnold stats under the render key in jason dict
        self.__arnold_stat_categories = [
            "scene creation time",
            "frame time",
            "peak CPU memory used"
        ]

        # store each render layers log and stats paths
        self.log_stat_loc_info = {}

        # these are the same for all render layers
        # maya log and stats path - where arnold is writing the logs
        self.log_stat_loc_info['arnold log dir'] = \
            r"Z:\LongGong\sequences\{0}\{1}\{2}\render_data".format(
                self.seq_name,
                self.shot_name,
                self.dept
            )
        self.log_stat_loc_info['arnold stat dir'] = \
            r"Z:\LongGong\sequences\{0}\{1}\{2}\render_data".format(
                self.seq_name,
                self.shot_name,
                self.dept
            )

        self.render_layers = []
        # get the render layers in the scene - ignore the default render layer and only want renderable layers
        render_setup = renderSetup.instance()
        render_layers = render_setup.getRenderLayers()
        for render_layer in render_layers:
            # Without "rs_" prefix
            render_layer_name = render_layer.name()
            if render_layer.isRenderable() and 'defaultRenderLayer' not in render_layer_name:
                    # remove any 'rs_' or 'rl_'
                    formatted_render_layer = render_layer_name.replace("rs_", "")
                    formatted_render_layer = formatted_render_layer.replace("rl_", "")
                    self.render_layers.append(formatted_render_layer)

        for layer in self.render_layers:
            self.log_stat_loc_info[layer] = {}
            # name of the log and stat files
            self.log_stat_loc_info[layer]['log name'] = "{0}_{1}_{2}".format(
                self.seq_name, self.shot_name, layer
            )
            self.log_stat_loc_info[layer]['stat name'] = "{0}_{1}_{2}".format(
                self.seq_name, self.shot_name, layer
            )
            # show log and stats path - where show logs and stats are kept
            self.log_stat_loc_info[layer]['show log dir'] = \
                r"Z:\LongGong\sequences\{0}\{1}\{2}\render_data\{3}".format(
                    self.seq_name,
                    self.shot_name,
                    self.dept,
                    layer
                )
            self.log_stat_loc_info[layer]['show stat dir'] = \
                r"Z:\LongGong\sequences\{0}\{1}\render_data\{2}\{3}".format(
                self.seq_name,
                self.dept,
                self.shot_name,
                layer
            )

        logger.info(
            "seq:{0}\nshot:{1}\ndept:{2}\nrender layers:{3}".format
            (
                self.seq_name,
                self.shot_name,
                self.dept,
                ', '.join(self.render_layers)
            )
        )

    @property
    def seq_name(self):
        """Returns the name of the sequence as Seq###"""
        return self.__seq_name

    @seq_name.setter
    def seq_name(self, seq_name):
        """Sets the name of the sequence as Seq###"""
        self.__seq_name = seq_name

    @property
    def shot_name(self):
        """Returns the name of the shot as Shot###"""
        return self.__shot_name

    @shot_name.setter
    def shot_name(self, shot_name):
        """Sets the name of the shot as Shot###"""
        self.__shot_name = shot_name

    @property
    def dept(self):
        """Returns the name of the department or pipeline step. ex: lighting"""
        return self.__dept

    @dept.setter
    def dept(self, dept):
        """Sets the name of the department or pipeline step"""
        self.__dept = dept

    @property
    def maya_file_name(self):
        """Returns the name of the maya file that is calling this class object"""
        return self.__maya_file_name

    @maya_file_name.setter
    def maya_file_name(self, maya_file_name):
        """Sets the name of the maya file that is calling this class object"""
        self.__maya_file_name = maya_file_name

    @property
    def render_layers(self):
        """Returns the render layers that are being rendered"""
        return self.__render_layers

    @render_layers.setter
    def render_layers(self, render_layers):
        """Sets the render layers being rendered"""
        self.__render_layers = render_layers

    @property
    def log_stat_loc_info(self):
        """Returns a dict that contains path and file names for the logs and stats. Available info:
                log name, the base log file name
                stat name, the base stat file name
                arnold log dir, the directory where arnold writes the log files
                arnold stat dir, the directory where arnold writes the stat files
                show log dir, the directory where the logs are kept for the show
                show stat dir, the directory where the stat files are kept for the show
        """
        return self.__log_stat_loc_info

    @log_stat_loc_info.setter
    def log_stat_loc_info(self, log_stat_loc_info):
        """Sets the log/stat file names and storage locations"""
        self.__log_stat_loc_info = log_stat_loc_info

    def create_file_paths(self):
        """
        Creates any file paths that don't exist, Arnold won't create folders and will error if they don't exist. Run
        this in Pre-Render mel in render globals
        """
        # move logs for each render layer to the show location for logs
        for layer in self.render_layers:

            # if the render_data folder doesn't exist for a render layer, make it
            if not os.path.exists(self.log_stat_loc_info[layer]['show log dir']):
                try:
                    os.makedirs(self.log_stat_loc_info[layer]['show log dir'])
                except (OSError, WindowsError) as e:
                    msg = "Error creating {0}. Error is {1}".format(self.log_stat_loc_info[layer]['show log dir'], e)
                    logging.exception(msg)

                try:
                    os.makedirs(self.log_stat_loc_info[layer]['show stat dir'])
                except (OSError, WindowsError) as e:
                    msg = "Error creating {0}. Error is {1}".format(self.log_stat_loc_info[layer]['show stat dir'], e)
                    logging.exception(msg)

    def add_custom_log_info(self):
        """
        Adds custom data to the log file after its generated. Currently adds:
            1. The maya file used to render the scene.
        """
        for layer in self.render_layers:
            # add maya file name to log at beginning
            self._add_file_name(self.maya_file_name, layer)

    def store_log_and_stat_paths(self):
        """
        Stores all the paths on disk to the logs and stats arnold wrote. Stores as absolute paths
        :return:
        """
        # store all the paths to the logs and stats that arnold wrote - this contains all the render layer
        # logs and stats file paths. These are absolute paths, ie
        # Z:\LongGong\sequences\Seq040\Shot260\lighting\render_data\Seq040_Shot260_env.log
        for layer in self.render_layers:
            logs = [
                os.path.join(self.log_stat_loc_info['arnold log dir'], log)
                for log in os.listdir(self.log_stat_loc_info['arnold log dir'])
                if log.endswith(".log") and layer in log
            ]
            # if there are logs for the render layer, add, otherwise don't add, makes it easy to know if there are
            # any logs to process
            if logs:
                self.logs[layer] = logs
            stats = [
                os.path.join(self.log_stat_loc_info['arnold stat dir'], log)
                for log in os.listdir(self.log_stat_loc_info['arnold stat dir'])
                if log.endswith(".json") and layer in log
            ]
            # if there are stats for the render layer, add, otherwise don't add, makes it easy to know if there are
            # any stats to process
            if stats:
                self.stats[layer] = stats

    def move_logs(self):
        """
        Moves the log files produced by Arnold per frame to the show log path. See class doc string for the actual
        location. Always moves to the first history folder.
        """
        # check for logs, skip if none found
        if not self.logs:
            logger.warning("No log data found in {0}".format(self.log_stat_loc_info['arnold log dir']))
            return

        # move logs for each render layer to the show location for logs
        for layer in self.render_layers:

            # if the render_data folder doesn't exist for a render layer, make it
            if not os.path.exists(self.log_stat_loc_info[layer]['show log dir']):
                os.makedirs(self.log_stat_loc_info[layer]['show log dir'])

            # a list of paths to each history folder
            history_dirs = self._get_history(self.log_stat_loc_info[layer]['show log dir'])
            logger.info("Found {0} history folders in {1}".format(
                    len(history_dirs),
                    self.log_stat_loc_info[layer]['show log dir']
                )
            )
            self._update_history(history_dirs)

            # make first history folder. Shouldn't ever exist at this point, because either there
            # isn't any history or if there is the existing history labeled '1' was moved to '2'.
            # However as a precaution check
            first_history_path = os.path.join(self.log_stat_loc_info[layer]['show log dir'], "1")
            os.mkdir(first_history_path, 0777)

            # move logs
            for log in self.logs[layer]:
                # get frame
                frame = log.split(".")[-2]
                full_log_name = "{0}.{1}.log".format(self.log_stat_loc_info[layer]['log name'], frame)
                new_log_path = os.path.join(first_history_path, full_log_name)
                try:
                    shutil.move(log, new_log_path)
                except (IOError, WindowsError, OSError) as e:
                    logger.error("encountered error moving {0} to {1}. Error is {2}".format(log, new_log_path, e))

            # display paths in log file
            logger.info("Looking for logs in : {0}".format(self.log_stat_loc_info['arnold log dir']))
            logger.info("Looking for logs named : {0}".format(self.log_stat_loc_info[layer]['log name']))
            logger.info("Moving logs to : {0}".format(first_history_path))

    def move_stats(self):
        """
        Moves the stat json files produced by Arnold per frame to one json file for the whole shot stored
        in the sequence directory. See class doc string for the actual location. Always moves to the first
        history folder.
        """
        # check for stats, skip if none found
        if not self.stats:
            logger.warning("No stat data found in {0}".format(self.log_stat_loc_info['arnold stat dir']))
            return

        # move stats for each render layer to the show location for stats
        for layer in self.render_layers:

            # if the render_layer folder doesn't exist for a shot, make it, ie
            # does Z:\LongGong\sequences\Seq040\lighting\render_data\Shot260\Char_Hei exist
            if not os.path.exists(self.log_stat_loc_info[layer]['show stat dir']):
                os.makedirs(self.log_stat_loc_info[layer]['show stat dir'])

            # a list of paths to each history folder
            history_dirs = self._get_history(self.log_stat_loc_info[layer]['show stat dir'])
            logger.info("Found {0} history folders in {1}".format(
                len(history_dirs),
                self.log_stat_loc_info[layer]['show stat dir']
                )
            )

            self._update_history(history_dirs)

            # make first history folder. Shouldn't ever exist at this point, because either there
            # isn't any history or if there is the existing history labeled '1' was moved to '2'.
            first_history_path = os.path.join(self.log_stat_loc_info[layer]['show stat dir'], "1")
            os.mkdir(first_history_path, 0777)

            # combine all frames stats into one json and write to the first history folder
            compiled_stats = self._compile_stats(layer)
            json_path = os.path.join(first_history_path, self.log_stat_loc_info[layer]['stat name'] + ".json")
            logging.info("writing shot stats json file to {0}".format(json_path))
            try:
                with open(json_path, "w") as write_file:
                    json.dump(compiled_stats, write_file, indent=4)
            except (IOError, WindowsError, OSError) as e:
                logger.error("encountered error writing json file {0}. Error is {1}".format(write_file, e))

            # cleanup the arnold stat json files
            for stat_file in self.stats[layer]:
                try:
                    os.remove(stat_file)
                except (IOError, WindowsError, OSError) as e:
                    logger.error("encountered error removing {0}. Error is {1}".format(stat_file, e))

            # display paths in log (not the arnold log, but tool log file)
            logger.info("Looking for stats in : {0}".format(self.log_stat_loc_info['arnold stat dir']))
            logger.info("Looking for stats named : {0}".format(self.log_stat_loc_info[layer]['stat name']))
            logger.info("Moving stats to : {0}".format(first_history_path))

    def cache_stats_for_shot(self):
        """
        Takes the shot's stat data that is broken down by render layer and history and combines into one json to
        reduce the number of files to load by render data viewer
        """
        cached_data = {}
        # go through every render layer on disk
        for layer in self.render_layers:
            # add key id doesn't exist
            if layer not in cached_data:
                cached_data[layer] = {}
            # get a list of the history
            history_dirs = os.listdir(self.log_stat_loc_info[layer]['show stat dir'])
            # go through all history folders to get stats
            for history in history_dirs:
                # add key if doesn't exist
                if history not in cached_data[layer]:
                    cached_data[layer][history] = {}
                # the file path to the json stat data on disk
                path_to_data = os.path.join(
                    self.log_stat_loc_info[layer]['show stat dir'],
                    history,
                    (self.log_stat_loc_info[layer]['stat name'] + ".json")
                )
                # open the stats file
                try:
                    with open(path_to_data, "r") as json_data:
                        stat_frame_data = json.load(json_data)
                        cached_data[layer][history] = stat_frame_data
                except (IOError, WindowsError, OSError) as e:
                    logger.error("encountered error reading json file {0}. Error is {1}".format(path_to_data, e))
        # path to write the cached stats to, contains all the shots render layer's stat data for all history anf frame.
        # its a cache of all the render data for the shot in one file
        shot_stats_path = "Z:\\LongGong\\sequences\\{0}\\lighting\\render_data\\{1}\\{2}_{3}.json".format(
            self.seq_name, self.shot_name, self.seq_name, self.shot_name
        )
        # write the file to disk
        try:
            with open(shot_stats_path, "w") as write_file:
                json.dump(cached_data, write_file, indent=4)
        except (IOError, WindowsError, OSError) as e:
            logger.error("encountered error writing json file {0}. Error is {1}".format(write_file, e))

    def _compile_stats(self, layer):
        """
        Combines stat data from each frame of a render layer into one json.
        Uses member variable __arnold_stat_categories to determine what stats to grab
        :param layer: a render layer name in maya as a string
        :return: combined stat data in json format for a single render layer
        """
        compiled_shot_stats = {}
        for stat_file in self.stats[layer]:
            with open(stat_file, "r") as read_file:
                orig_stats = json.load(read_file)
                frame = stat_file.split(".")[-2]
                compiled_shot_stats[frame] = {}
                for cat in self.__arnold_stat_categories:
                    compiled_shot_stats[frame][cat] = orig_stats["render 0000"][cat]
        return compiled_shot_stats

    @staticmethod
    def _get_history(history_path):
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
        logger.info("Found {0} history folders in {1}".format(len(history_dirs), history_path))
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
            # to the new folder, ie Z:\LongGong\sequences\Seq#\Shot#\dept\render_data\render_layer\1\ becomes
            # Z:\LongGong\sequences\Seq#\Shot#\dept\render_data\render_layer\2\ and so on
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

    def _add_file_name(self, file_name, render_layer):
        """
        Adds the maya file used to render the scene.
        :param file_name: the maya file name. This is just the file name, not a path
        :param render_layer: the render layer name in maya as a string
        :return: None
        """
        # for every render layer, add the maya file name to the logs of that render layer
        for log in self.logs[render_layer]:
            with open(log, "r+") as f:
                contents = f.read()
                f.seek(0, 0)
                new_content = "Maya File Name : {0}.\n\n".format(file_name)
                f.write(new_content + contents)


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


def get_shot_name_from_string(string_containing_shot):
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


def get_file_name():
    """
    Uses maya cmds to get the base file name (no path)
    :return: returns the base file name including extension -.ma or .mb
    """
    file_path = cmds.file(q=True, sn=True)
    file_name = os.path.basename(file_path)
    return file_name


def setup(dept="lighting"):
    """
    Pre render mel calls this
    :param dept: the department or pipeline step as a string
    """
    setup_logging()
    # get maya file name - expects file names in format seq###_shot###_LGT_v###
    maya_file_name = get_file_name()
    shot = get_shot_name_from_string(maya_file_name)
    seq = get_sequence_name_from_string(maya_file_name)
    log_processor = AniLogProcessor(seq, shot, dept, maya_file_name)
    log_processor.create_file_paths()


def run(dept="lighting"):
    """
    Post render mel calls this
    :param dept: the department or pipeline step as a string
    """
    setup_logging()
    # get maya file name - expects file names in format seq###_shot###_LGT_v###
    maya_file_name = get_file_name()
    shot = get_shot_name_from_string(maya_file_name)
    seq = get_sequence_name_from_string(maya_file_name)
    log_processor = AniLogProcessor(seq, shot, dept, maya_file_name)
    log_processor.store_log_and_stat_paths()
    log_processor.add_custom_log_info()
    log_processor.move_logs()
    log_processor.move_stats()
    log_processor.cache_stats_for_shot()
