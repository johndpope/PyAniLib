import os
import re
import json
import logging
import pyani.core.util


logger = logging.getLogger()


class AniVars(object):
    '''
    object that holds variables for shot, sequence and scenes. Usage is AniVars(). Then error=load_seq_shot_list(), and
    check for any errors it returns. If it errors then a critical error has occurred and can't return the sequence
    or shot list for the show. If this isn't needed you can still use the object class, just not get_sequence_list()
    or get_shot_list()

    Use update or update_using_shot_path to set sequence and shot vars

    To see a list of Ani Vars:
    print AniVar_instance

    '''

    def __init__(self):
        # not dependent on seq or shot
        self.desktop = os.path.expanduser("~/Desktop")
        self.nuke_user_dir = os.path.join(os.path.expanduser("~"), ".nuke")
        self.shot_master_template = "shot_master.nk"
        self.sequence_shot_list_json = "C:\\PyAniTools\\app_data\\Shared\\sequences.json"
        self.app_data_shared ="C:\\PyAniTools\\app_data\\Shared"
        # os.path.join has issues, maybe due to .nuke? String concat works
        self.nuke_custom_dir = "C:\\PyAniTools\\lib\\"
        # this holds the seq and shot set in PySession app
        self.session_vars_json = os.path.join(self.app_data_shared, "session_env.json")
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
        self.seq_shot_list = None
        self.seq_name = None
        self.shot_name = None
        self.shot_dir = None
        self.shot_light_dir = None
        self.shot_light_work_dir = None
        self.shot_maya_dir = None
        self.shot_comp_dir = None
        self.shot_comp_work_dir = None
        self.shot_comp_file = None
        self.shot_comp_plugin_dir = None
        self.shot_cam_dir = None
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

        self.places = [
            self.movie_dir,
            self.image_dir,
            self.desktop
        ]

    # produce better output
    def __str__(self):
        return json.dumps(vars(self),indent=4 )

    def __repr__(self):
        return '<pyani.core.util.AniVars "Seq{0}, Shot{1}">'.format(self.seq_name, self.shot_name)

    def load_seq_shot_list(self):
        """
        Reads the json dict of sequences, shots, and frame ranges
        :return: None or error as string if encountered
        """
        data = pyani.core.util.load_json(self.sequence_shot_list_json)
        # if couldn't load json, set list to none
        if not isinstance(data, dict):
            error = "Could not set ani vars. Error is {0}".format(data)
            return error

        self.seq_shot_list = data
        return None

    def is_valid_seq(self, seq):
        """
        Checks if a string is in the correct seq format
        :param shot: a string with the word seq followed by a seq number, like seq180
        :return: True if valid, False if not
        """
        if self._get_sequence_name_from_string(seq):
            return True
        else:
            return False

    def is_valid_shot(self, shot):
        """
        Checks if a string is in the correct shot format
        :param shot: a string with the word shot followed by a shot number, like shot190
        :return: True if valid, False if not
        """
        if self._get_shot_name_from_string(shot):
            return True
        else:
            return False

    def get_sequence_list(self):
        """Returns a list of sequence names
        :exception KeyError : if seq_shot_list is not a dict will throw key error, means didn't get set properly
        :return the sequence list or error as string
        """
        try:
            return self.seq_shot_list.keys()
        except KeyError as e:
            error = "Error getting sequence list. Error is {0}".format(e)
            logging.exception(error)
            return error

    def get_shot_list(self):
        """Returns a list of shot names
        :exception KeyError : if seq_shot_list is not a dict will throw key error, means didn't get set properly
        :return the sequence list or error as string
        """
        try:
            shot_list = self.seq_shot_list[self.seq_name]
            return [shot["shot"] for shot in shot_list]
        except KeyError as e:
            error = "Error getting shot list. Error is {0}".format(e)
            logging.exception(error)
            return error

    def update_using_shot_path(self, shot_path):
        """
        Set ani vars based off a shot path that has seq### and shot### in it, like ...sequences/seq180/shot190/...
        :param shot_path: a valid path with the words seq followed by a seq num and shot followed by a shot num
        :return: error if encountered as string, none otherwise
        """

        self.seq_name = self._get_sequence_name_from_string(shot_path)
        self.shot_name = self._get_shot_name_from_string(shot_path)
        if not self.seq_name or not self.shot_name:
            error = "Error setting ani vars from shot path: {0}. Path should have seq#### and shot####" \
                    "in it. Found seq {1} and shot {2}".format(shot_path, self.seq_name, self.shot_name)
            logging.error(error)
            return error
        self._make_seq_vars()
        self._make_shot_vars()

    def update(self, seq_name, shot_name=None):
        """
        sets ani vars based off a seq name and shot name
        :param seq_name: the words seq followed by a number, like seq180
        :param shot_name: the words shot followed by a number, like shot190
        :return: error if encountered as a string, otherwise None
        """
        self.seq_name = seq_name
        if self.is_valid_seq(seq_name):
            self._make_seq_vars()
        else:
            error = "Invalid sequence name: {0}".format(seq_name)
            logging.error(error)
            return error
        # make sure a shot was provided
        if shot_name:
            if self.is_valid_shot(shot_name):
                self.shot_name = shot_name
                self._make_shot_vars()
            else:
                error = "Invalid shot name: {0}".format(shot_name)
                logging.error(error)
                return error

    def _make_seq_vars(self):
        """ Sets the sequence vars based off the sequence name stored - called by update and update_using_shot_path
        """
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
        """ Sets the shot vars based off the shot name stored - called by update and update_using_shot_path
        """
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
        self.shot_comp_file = "{0}_{1}_V001.nk".format(self.seq_name, self.shot_name)
        self.shot_cam_dir = os.path.join(self.shot_dir, "animation/approved/scenes/")

        # directories for shot outside shot directory

        # image directories
        self.shot_image_dir = os.path.normpath("{0}\{1}".format(self.seq_image_dir, self.shot_name))
        self.shot_layer_dir = os.path.normpath("{0}\{1}".format(self.shot_image_dir, "\light\layers"))
        # movie directories
        self.shot_movie_dir = os.path.normpath("{0}\sequences\{1}".format(self.movie_dir, self.seq_name))
        # frames
        for shot in self.seq_shot_list[self.seq_name]:
            if shot["shot"] == self.shot_name:
                self.first_frame = shot["first_frame"]
                self.last_frame = shot["last_frame"]
                self.frame_range = "{0}-{1}".format(str(self.first_frame), str(self.last_frame))
                break

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