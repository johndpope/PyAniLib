import os
import json
import pyani.core.anivars
import pyani.core.util as util


class AniRenderData:
    """
        Note a comma after a bracket means there could be more than one entry

        Raw Data stored as
        {
            sequence: {
                shot: {
                    history: {
                        frame: {
                            stat: {
                                item(s)
                            },
                            more stats...
                        },
                    },
                },
            },
        }
        Processed Data stored as
        {
            sequence#: {
                average: {
                    stat: {
                        total: float
                        components: [list of floats]
                    },
                }
                shot#: {
                    average: {
                        stat: {
                            total: float
                            components: [list of floats]
                        },
                    }
                    history: {
                        average: {
                            stat: {
                                total: float
                                components: [list of floats]
                            },
                        }
                        frame: {
                            stat: {
                                total: float
                                components: [list of floats]
                            },
                        },
                    },
                },
            },
        }
    """

    def __init__(self, dept="lighting"):
        '''
        :param dept: a department such as lighting or modeling, defaults to lighting
        '''
        self.ani_vars = pyani.core.anivars.AniVars()
        self.dept = dept
        # the data on disk read in and stored using format shown in class doc string
        self.__raw_stat_data = {}
        # the data averaged and processed
        self.stat_data = {}
        # the stats as a dict, keys are the labels, values are the labels/keys in the json file
        # render time is a subset of frame time in json file. if a jason key is not under the label name in
        # the mapping, then the key is provided. Ex: render time is not a json key, its
        # frame time:rendering:microseconds in the json file.
        self.stats_map = {
            'frame time': {
                "key name": "frame time",
                "type": "microseconds",
                "components": [
                    'node init:microseconds',
                    'driver init/close:microseconds',
                    'rendering:microseconds'
                ]
            },
            'render time': {
                "key name": "frame time:rendering",
                "type": "microseconds",
                "components": [
                    'subdivision:microseconds',
                    'mesh processing:microseconds',
                    'displacement:microseconds',
                    'pixel rendering:microseconds',
                    'accel. building:microseconds',
                ]
            },
            'memory': {
                "key name": "peak CPU memory used",
                "type": "bytes",
                "components": [
                    'at startup:bytes',
                    'texture cache:bytes',
                    'accel. structs:bytes',
                    'geometry:bytes',
                    'plugins:bytes',
                    'output buffers:bytes'
                ]
            },
            'cpu utilization': {
                "key name": "frame time:machine utilization",
                "type": "percent"
            },
            'scene creation time': {
                "key name": "scene creation time",
                "type": "microseconds",
                "components": [
                    'plugin loading:microseconds'
                ]
            }
        }
        self.stat_names = self.stats_map.keys()

    @property
    def dept(self):
        """the pipeline stage or department, such as lighting or modeling.
        """
        return self.__dept

    @dept.setter
    def dept(self, dept):
        """the pipeline stage or department, such as lighting or modeling.
        """
        self.__dept = dept

    @property
    def stat_data(self):
        """a dict of all stats stored for show. Every frame stores the same stats. See class doc string for format.
        """
        return self.__stat_data

    @stat_data.setter
    def stat_data(self, stats):
        """a dict of all stats stored for show. Every frame stores the same stats. See class doc string for format.
        """
        self.__stat_data = stats

    @property
    def stat_names(self):
        """Return list of available stats
        """
        return sorted(self.__stat_names)

    @stat_names.setter
    def stat_names(self, names):
        """Set the list of available stats
        """
        self.__stat_names = names

    @property
    def stats_map(self):
        """Return nested dict that maps labels to the key/value pair in stats data. Allows labels to be anything
        you want. Mapping tells where that label's data is in the stats data dict. Uses semicolons to indicate a nested
        path. for example: rendering is 'frame time:rendering:microseconds'
        """
        return self.__stats_map

    @stats_map.setter
    def stats_map(self, mapping):
        """Set the nested dict that maps labels to the key/value pair in stats data. Allows labels to be anything
        you want. Mapping tells where that label's data is in the stats data dict. Uses semicolons to indicate a nested
        path. for example: rendering is 'frame time:rendering:microseconds'
        """
        self.__stats_map = mapping

    def get_stat_type(self, stat):
        """
        returns the format the stat is in, ie seconds, gigabytes, percent
        :param stat: the stat
        :return: the tpe as a string in abbreviated notation s -seconds, gb -gigabytes, % -percentages
        """
        stat_type = self.stats_map[stat]['type']
        if stat_type is 'microseconds':
            return 'sec'
        elif stat_type is 'bytes':
            return 'gb'
        else:
            return '%'

    def get_stat_components(self, stat):
        """
        Get the component names for the stat if it has any
        :param stat: name of the stat
        :return: a list of components or empty list if there are no components for the stat
        """
        components = []
        # skip if no components
        try:
            if 'components' in self.stats_map[stat]:
                # components are stored as paths, get just component name
                for component in self.stats_map[stat]['components']:
                    component_path_split = component.split(":")
                    # components are always path:type, for example plugin loading:microseconds or memory:bytes.
                    # We want the plugin loading or memory only, no :microseconds or :bytes
                    components.append(component_path_split[-2])
        except KeyError:
            print "There is no stat named: {0}. Available stats are: {1}".format(stat, ", ".join(self.stat_names))
        return components

    def get_stat(self, seq, shot, frame, stat, history='1'):
        """
        gets the stat for a specific frame. if the stat is comprised of multiple stats, gets the components values too.
        :param stat:
        :param seq: sequence number as string
        :param shot: shot number as string
        :param frame: frame number as a string
        :param stat: the stat to get
        :param history: the history number as string - defaults to 1
        :return: a list of the total (time, memory, or percent) for the stat, and if it has components returns their
        values too. Returns a a list with one element set to 0.0 if stat can't be found
        """
        if stat in self.stat_names:
            # get mapping dict
            mapping_dict = self.stats_map[stat]
            # get the key name, may contain a path like frame time:rendering
            key_name = mapping_dict['key name'].split(":")
            # get the type - seconds or bytes
            stat_type = mapping_dict['type']
            # get the total time for stat
            key_path = [seq, shot, history, frame] + key_name + [stat_type]
            # figure out data type for conversion
            if stat_type == "bytes":
                stat_total = self._bytes_to_gb(util.find_val_in_nested_dict(self.__raw_stat_data, key_path))
            elif stat_type == "percent":
                stat_total = util.find_val_in_nested_dict(self.__raw_stat_data, key_path)
            else:
                stat_total = self._microsec_to_sec(util.find_val_in_nested_dict(self.__raw_stat_data, key_path))

            # if no total, return 0.0. Note return a list for compatibility with return value of actual data which
            # is a list
            if not stat_total:
                return [0.0]

            # seconds or amount of memory from stat components
            component_amounts = []
            # get the components (ie the actual stats) that make up the stat, these will be a path like
            # subdivision:microseconds. Some stats may not have components
            if "components" in mapping_dict:
                component_keys = mapping_dict['components']
                # loop through stat data dict and get microseconds for every component
                for component in component_keys:
                    # build key path to access value in stat data
                    key_path = [seq, shot, history, frame] + key_name + component.split(":")
                    # get time, memory or percent from stats dict
                    if stat_type == "bytes":
                        component_amounts.append(
                            self._bytes_to_gb(util.find_val_in_nested_dict(self.__raw_stat_data, key_path))
                        )
                    elif stat_type == "percent":
                        component_amounts.append(util.find_val_in_nested_dict(self.__raw_stat_data, key_path))
                    else:
                        component_amounts.append(
                            self._microsec_to_sec(util.find_val_in_nested_dict(self.__raw_stat_data, key_path))
                        )
            # return the time
            return [stat_total] + component_amounts
        else:
            return [0.0]

    def process_data(self, stat, seq=None, shot=None, history="1"):
        """
        Takes the raw data and puts in the format listed in the class doc string under Processed Data
        :param stat: the stat name as a string
        :param seq: sequence number as string
        :param shot: shot number as string
        :param history: the history to get, defaults to the current render data
        """
        # a sequence and shot were provided, so process the frame data
        if seq and shot:
            # check if the data has been processed yet
            if not util.find_val_in_nested_dict(self.stat_data, [seq, shot, history, 'average', stat]):
                self.process_shot_data(stat, seq, shot, history=history)
        # just a sequence was provided, process all shot data for the sequence
        elif seq and not shot:
            # check if the data has been processed already
            if not util.find_val_in_nested_dict(self.stat_data, [seq, 'average', stat]):
                self.process_sequence_data(stat, seq)
        # show level - no sequence or shot provided
        else:
            # check if the data has been processed already
            if not util.find_val_in_nested_dict(self.stat_data, ['average', stat]):
                self.process_show_data(stat)

    def process_show_data(self, stat, history="1"):
        """
        Gets the stat and its component values for the show. values are the average of all sequence data
        :param stat: the main stat as a string
        :param history: the history as a string, defaults to "1" which is the current render data
        :returns: False if no data was added to the processed data dict, True if data added
        """
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # average stat across all sequences
        seq_list = self.get_sequences(history=history)

        # no sequences, then don't add anything
        if not seq_list:
            return False

        for seq in seq_list:
            # make the key if its missing
            if seq not in self.stat_data:
                self.stat_data[seq] = {}

            # get the average for the stat for the sequence
            self.process_sequence_data(stat, seq, history=history)
            # sum the average
            main_total_sum += self.stat_data[seq]["average"][stat]["total"]
            component_totals_sum = [
                component_totals_sum[index] +
                self.stat_data[seq]["average"][stat]["components"][index]
                for index in xrange(len(component_totals_sum))
            ]

        # average the sequence data
        main_total_sum /= len(seq_list)
        component_totals_sum = [component_total / len(seq_list) for component_total in component_totals_sum]
        if 'average' not in self.stat_data:
            self.stat_data['average'] = {}
        self.stat_data['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

    def process_sequence_data(self, stat, seq, history="1"):
        """
        Gets the stat and its component values per shot. Values are the average of the frame data
        :param stat: the main stat as a string
        :param seq: the sequence as a string, format seq###
        :param history: the history as a string, defaults to "1" which is the current render data
        :return: False if no data was added to the processed data dict, True if data added
        """
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # get all of the shots in the sequence that have data at the given history
        shot_list = self.get_shots(seq, history=history)
        # no shots, then return False, don't add anything
        if not shot_list:
            return False

        for shot in shot_list:
            # make key if doesn't exist
            if shot not in self.stat_data[seq]:
                self.stat_data[seq][shot] = {}

            # average the shot's frame data and store
            if self.process_shot_data(stat, seq, shot, history=history):
                # make key if doesn't exist
                if 'average' not in self.stat_data[seq][shot]:
                    self.stat_data[seq][shot]["average"] = {}
                # set the shot total
                self.stat_data[seq][shot]["average"][stat] = {
                    'total': self.stat_data[seq][shot][history]["average"][stat]["total"],
                    'components': self.stat_data[seq][shot][history]["average"][stat]["components"]
                }
                # get the frame average for the shot and sum
                main_total_sum += self.stat_data[seq][shot][history]["average"][stat]["total"]
                component_totals_sum = [
                    component_totals_sum[index] +
                    self.stat_data[seq][shot][history]["average"][stat]["components"][index]
                    for index in xrange(len(component_totals_sum))
                ]

        # average the total sums so that the sequence has an average of all its shots data
        main_total_sum /= len(shot_list)
        component_totals_sum = [component_total / len(shot_list) for component_total in component_totals_sum]
        if 'average' not in self.stat_data[seq]:
            self.stat_data[seq]['average'] = {}
        self.stat_data[seq]['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

    def process_shot_data(self, stat, seq, shot, history="1"):
        """
         Gets the stat and its component values per frame, and averages those values
         :param stat: the main stat as a string
         :param seq: the seq as a string, format seq###
         :param shot: the shot as a string, format shot###
         :param history: the history as a string, defaults to "1" which is the current render data
         :return: False if no data was added to the processed data dict, True if data added
        """
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # get all of the frames in the shot that have data at the given history
        frames = self.get_frames(seq, shot, history=history)

        # no frames means no history, so don't add anything to processed data
        if not frames:
            return False

        # make the key if it doesn't exist
        if history not in self.stat_data[seq][shot]:
            self.stat_data[seq][shot][history] = {}

        for frame in frames:
            # get the stat values for this frame - the main stat total and any sub components
            totals = self.get_stat(seq, shot, frame, stat, history)
            # make the key if it doesn't exist
            if frame not in self.stat_data[seq][shot][history]:
                self.stat_data[seq][shot][history][frame] = {}
            # store frame data
            self.stat_data[seq][shot][history][frame][stat] = {'total': totals[0], 'components': totals[1:]}

            # sum frame data for averaging
            # first number is the main stat total, remaining numbers are the component totals
            main_total_sum += totals[0]
            component_total = totals[1:]
            component_totals_sum = [component_totals_sum[i] + component_total[i] for i in range(len(component_total))]
        # average the totals now
        main_total = main_total_sum / len(frames)
        component_totals = [component_total / len(frames) for component_total in component_totals_sum]

        # make the key if it doesn't exist
        if 'average' not in self.stat_data[seq][shot][history]:
            self.stat_data[seq][shot][history]['average'] = {}
        # store the frame average
        self.stat_data[seq][shot][history]['average'][stat] = {
            'total': main_total, 'components': component_totals
        }

        return True

    def read_stats(self):
        """
        Process the data on disk into the format shown in the class doc string under raw data. Stores in a class
        member variable
        """
        stats = {}
        stats_processed = {}
        # for every seq, go through shots and get the frame data
        for sequence in self.ani_vars.get_sequence_list():
            # path to the stats for this sequence
            sequence_stats_path = os.path.normpath(
                "Z:\\LongGong\\sequences\\{0}\\lighting\\render_data\\".format(sequence)
            )
            # sequence may not have render stat data, don't process if the path doesn't exist
            if os.path.exists(sequence_stats_path):
                '''
                adds the sequence to the dict, so we have 
                {
                    sequence: {
                    }
                }
                '''
                stats[sequence] = {}
                stats_processed[sequence] = {'average': {}}
                # update ani vars to this sequence
                self.ani_vars.update(sequence)
                # get a list of the history for this sequence
                history_numbers = [history for history in os.listdir(sequence_stats_path) if util.is_number(history)]
                # make sure there is history, if not skip
                if history_numbers:
                    # get a list of the paths to the history
                    history_stats_paths = [os.path.join(sequence_stats_path, history) for history in history_numbers]
                    # loop through history folders to get stats
                    for history_index in range(0, len(history_numbers)):
                        # a list of all the shots stat files in the history folder, skips files
                        if os.path.isdir(history_stats_paths[history_index]):
                            shot_stats_files = [
                                os.path.join(history_stats_paths[history_index], shot_stats_file)
                                for shot_stats_file in os.listdir(history_stats_paths[history_index])
                            ]
                        # no directory, its a file, so don't process
                        else:
                            shot_stats_files = []

                        if shot_stats_files:
                            # for every shot stat file, add to our stat data dict
                            for shot_stat_file in shot_stats_files:
                                shot_name = pyani.core.util.get_shot_name_from_string(shot_stat_file)
                                # check if shot added yet, if not add as a key with a dict as value
                                if shot_name not in stats[sequence]:
                                    '''
                                      add shot to get:
                                      {
                                          sequence: {
                                                shot: {
                                    '''
                                    stats[sequence][shot_name] = {}
                                    stats_processed[sequence][shot_name] = {'average': {}}

                                stat_data_on_disk = util.load_json(shot_stat_file)

                                # now set history to the loaded stat data - a nested dict of frames and their
                                # associated stat data
                                '''
                                  add history, frames, and stats, so we have now:
                                  {
                                      sequence: {
                                            shot: {
                                                  history: {
                                                      frame: {
                                                          stats
                                                      }
                                                  }
                                            }
                                      }
                                  }   
                                '''
                                stats[sequence][shot_name][history_numbers[history_index]] = stat_data_on_disk
                else:
                    # no history so remove the sequence key
                    stats.pop(sequence)
        # save the stats
        self.__raw_stat_data = stats

    def print_stat_data(self, raw=True, show_stats=False):
        """
        Formatted printout of the stat data dict, useful for debugging
        :param raw: True: show raw data as it exists on disk, False: show processed data
        :param show_stats: show the actual stats in the print (can clutter screen), off by default
        """
        # print entire stat data dict
        if show_stats:
            if raw:
                print json.dumps(self.__raw_stat_data, sort_keys=True, indent=5)
            else:
                print json.dumps(self.stat_data, sort_keys=True, indent=5)
        else:
            if raw:
                # only show the seq, shots, history, and frames
                for seq in self.__raw_stat_data:
                    for shot in self.__raw_stat_data[seq]:
                        for history in self.__raw_stat_data[seq][shot]:
                            for frame in self.__raw_stat_data[seq][shot][history]:
                                self.__raw_stat_data[seq][shot][history][frame] = ""
            else:
                json.dumps(self.stat_data, sort_keys=True, indent=5)

    def get_sequences(self, history="1"):
        """
        Get the list of sequences that have render data for a given history
        :param history: the history as a string, example '1'
        :return: the list of sequences in order ascending or an empty list if there are no sequences
        for the given history
        """
        # loop through all sequences, and check if the sequence has data for the given history
        seqs_with_data = []
        if self.__raw_stat_data:
            for seq in self.__raw_stat_data:
                if self.get_shots(seq, history=history):
                    seqs_with_data.append(seq)
        return sorted(seqs_with_data)

    def get_shots(self, seq, history="1"):
        """
        Get the list of shots that have render data for a given shot and history
        :param seq: the sequence as a string, format Seq###
        :param history: the history as a string, example '1'
        :return: the list of shots in order ascending or an empty list if there are no shots for the given history
        """
        # loop through all shots in sequence, and check if the shot has data for the given history
        shots_with_data = []
        if seq in self.__raw_stat_data:
            for shot in self.__raw_stat_data[seq]:
                if self.get_frames(seq, shot, history=history):
                    shots_with_data.append(shot)
        return sorted(shots_with_data)

    def get_frames(self, seq, shot, history="1"):
        """
        Get the list of frames that have render data for a given shot and history
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param history: the history as a string, example '1'
        :return: the list of frames in order ascending, or an empty list if no data
        """
        # check for the given history
        if seq in self.__raw_stat_data:
            if shot in self.__raw_stat_data[seq]:
                if history in self.__raw_stat_data[seq][shot]:
                    return sorted(self.__raw_stat_data[seq][shot][history].keys())
        return []

    def get_history(self, seq, shot):
        """
        Get the list of history for a given shot
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :return: the list of history sorted ascending
        """
        if seq in self.__raw_stat_data:
            if shot in self.__raw_stat_data[seq]:
                return sorted(self.__raw_stat_data[seq][shot].keys())
        return []

    @staticmethod
    def _microsec_to_sec(microseconds):
        """
        Convert microseconds to seconds
        :param microseconds: the microseconds as a float to convert
        :return: the seconds as a float. If the microseconds is not a float returns None
        """
        if not isinstance(microseconds, (float, int)):
            return None
        return float(microseconds) / 1000000.0

    @staticmethod
    def _bytes_to_gb(bytes_num):
        """
        Convert bytes to gigabytes
        :param bytes_num: the bytes as a float to convert
        :return: the gb as a float. If the bytes is not a float returns None
        """
        if not isinstance(bytes_num, (float, int)):
            return None
        return float(bytes_num) / 1000000000.0