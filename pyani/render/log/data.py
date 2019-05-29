import os
import json
import copy
import ujson
import threading
import Queue
import pyani.core.anivars
import pyani.core.util as util
from PyQt4.Qt import pyqtSignal
from PyQt4.QtCore import QThread


class GetShotStatsThread(threading.Thread):
    """
    Class to get a shot's render stats using multi-threading via a queue
    Takes a queue object in initialization
    """
    # signal to fire when have progress to send, can send any python object
    data_processed = pyqtSignal(bool)

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        '''
        shot's stats in format
        {
                shot: {
                    render layer: {
                            history: {
                                frame: {
                                    stats
                                }
                            }
                    }
              }
        }
        '''
        self.stats = {}
        # store the shot name - set in load_stats() method
        self.shot_name = None

    def load_stats(self, stat_info):
        """
        Gets the stats for every render layer's history within a shot for the entire sequence. Stores result in the
        class variable stats which is a dict
        :param stat_info: a tuple containing the sequence name, shot name and the path to the render data folder
        that holds all the shot's stats
        """
        # unpack from the tuple
        sequence, shot, shot_render_data_path = stat_info
        self.shot_name = shot
        # make the path to the json file, only ever one file in the history directory,
        # so we grab the first element from os.listdir
        json_file_name = "{0}_{1}.json".format(sequence, shot)
        with open(os.path.join(shot_render_data_path, json_file_name), 'r') as json_file:
            stat_data_on_disk = ujson.load(json_file)
        if not isinstance(stat_data_on_disk, dict):
            print stat_data_on_disk
        else:
            self.stats = stat_data_on_disk
            # let another class know this thread is done
            #self.data_processed.emit(True)

    def run(self):
        """
        gets a sequence and path to the render data, passes to the method to get the stats off disk and store in a dict
        """
        while True:
            # get the stat tuple containing sequence name, shot name and path to render data
            stat_info = self.queue.get()
            # load the stats
            self.load_stats(stat_info)
            self.queue.task_done()


class AniRenderData:
    """
        Note a comma after a bracket means there could be more than one entry

        Raw Data - read in from disk, not accessible by viewer, just puts data on disk in memory. Loads all
        sequence data at one time
        ------------------------------------------
        stored as dict in format:
        {
            sequence: {
                shot: {
                    render layer: {
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
            },
        }

        Processed Data - takes raw data and does averaging, this is a deferred loading approach, to speed up processing
        Only process data as requested (when a render layer or stat is changed)

        Averages for stat are a total of all render layers. For example if there are 3 render layers, we sum and
        average the memory for all 3 layers

        Sequence :
            - Store average per stat of all shots, so memory for example is totaling and averaging every shot's memory
            - This is the total of all render layers

        Shot:
            - Store average per stat of all frames, so memory for example is totaling and averaging every frame's memory
            - This is the total of all render layers

        Render Layer:
            - Store average per stat of all frames for this render layer

        --------------------------------------------
        stored as dict in format:
        {
            average: {
                stat: {
                    total: float
                    components: [list of floats]
                },
            }
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
                    render layer: {
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
            },
        }
    """

    def __init__(self, dept="lighting"):
        '''
        :param dept: a department such as lighting or modeling, defaults to lighting
        '''
        self.dept = dept
        # the data on disk read in and stored using format shown in class doc string
        self.raw_stat_data = {}
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
    def raw_stat_data(self):
        """a dict of all stats stored for show in raw format. Every frame stores the same stats.
         See class doc string for format.
        """
        return self.__raw_stat_data

    @raw_stat_data.setter
    def raw_stat_data(self, stats):
        """a dict of all stats stored for show in raw format. Every frame stores the same stats.
         See class doc string for format.
        """
        self.__raw_stat_data = stats


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

    def set_custom_data(self, stat_files, user_seq, user_shot, user_render_layer, stat="frame time"):
        """
        Sets the data to user defined data
        :param stat_files: the user defined data as a list of json files (absolute path) on disk
        :param user_seq: the seq associated with the user data
        :param user_shot: the shot associated with the user data
        :param stat: the stat to show, defaults to frame time
        :return None if successful, otherwise an error string
        """
        # make in format that shots follow - see class docstring for more info under raw format
        combined_stats = {
            user_seq: {
                user_shot: {
                    user_render_layer: {
                        "1": {}
                    }
                }
            }
        }
        # go through each stat file, get the stats and add to the combined file.
        for stat_file in stat_files:
            json_data = pyani.core.util.load_json(stat_file)
            if not json_data:
                return json_data
            # get frame number, should be the second to last element, before .json
            frame_num = stat_file.split(".")[-2]
            # get the data and save under the frame number
            combined_stats[user_seq][user_shot][user_render_layer]['1'][frame_num] = json_data['render 0000']

        self.raw_stat_data = combined_stats
        self.stat_data = {}
        self.process_data(stat)

        return None

    def read_sequence_stats_DEPR(self, sequence):
        """
          Process the data on disk into the format shown in the class doc string under raw data. Stores in a class
          member variable
        """

        # check if sequence already loaded, if so don't load
        if sequence in self.raw_stat_data:
            return

        # thread safe queue for loading json stats off disk
        self.stats_queue = Queue.Queue()

        # spawn threads and keep so we can access contents later
        shots_threads_list = []
        for i in range(0, 50):
            shots_threads_list.append(GetShotStatsThread(self.stats_queue))
            shots_threads_list[i].start()

        self.ani_vars.update(seq_name=sequence)
        # make the paths to the sequence's render data
        for shot in self.ani_vars.get_shot_list():
            shot_stats_path = "Z:\\LongGong\\sequences\\{0}\\lighting\\render_data\\{1}".format(sequence, shot)
            if os.path.exists(shot_stats_path):
                self.stats_queue.put((sequence, shot, shot_stats_path))

        # wait for queue to get empty
        self.stats_queue.join()

        stats_seq = dict()
        # collect stats
        for shot_thread in shots_threads_list:
            stats_seq[shot_thread.shot_name] = shot_thread.stats

        # save the stats
        self.raw_stat_data[sequence] = stats_seq

    def load_shot_stats(self, stat_info):
        """
        Loads a shot's stats from disk and saves in the self.raw_stat_data dict
        :param stat_info - a tuple containing the sequence name, shot name, and path to the stats
        """
        # unpack from the tuple
        sequence, shot, shot_render_data_path = stat_info

        # check if sequence key exists
        if sequence not in self.raw_stat_data:
            self.raw_stat_data[sequence] = {}

        # make the path to the json file, only ever one file in the history directory,
        # so we grab the first element from os.listdir
        json_file_name = "{0}_{1}.json".format(sequence, shot)
        with open(os.path.join(shot_render_data_path, json_file_name), 'r') as json_file:
            stat_data_on_disk = ujson.load(json_file)
            self.raw_stat_data[sequence][shot] = stat_data_on_disk

    def get_stat_type(self, stat):
        """
        returns the format the stat is in, ie seconds, gigabytes, percent
        :param stat: the stat
        :return: the tpe as a string in abbreviated notation s -seconds, gb -gigabytes, % -percentages
        """
        stat_type = self.stats_map[stat]['type']
        if stat_type is 'microseconds':
            return 'min'
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

    def get_stat(self, seq, shot, render_layer, frame, stat, history='1'):
        """
        gets the stat for a specific frame. if the stat is comprised of multiple stats, gets the components values too.
        :param stat:
        :param seq: sequence number as string
        :param shot: shot number as string
        :param render_layer: the render layer as a string
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
            key_path = [seq, shot, render_layer, history, frame] + key_name + [stat_type]
            # figure out data type for conversion
            if stat_type == "bytes":
                stat_total = self._bytes_to_gb(util.find_val_in_nested_dict(self.raw_stat_data, key_path))
            elif stat_type == "percent":
                stat_total = util.find_val_in_nested_dict(self.raw_stat_data, key_path)
            else:
                stat_total = self._microsec_to_min(util.find_val_in_nested_dict(self.raw_stat_data, key_path))

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
                    key_path = [seq, shot, render_layer, history, frame] + key_name + component.split(":")
                    # get time, memory or percent from stats dict
                    if stat_type == "bytes":
                        component_amounts.append(
                            self._bytes_to_gb(util.find_val_in_nested_dict(self.raw_stat_data, key_path))
                        )
                    elif stat_type == "percent":
                        component_amounts.append(util.find_val_in_nested_dict(self.raw_stat_data, key_path))
                    else:
                        component_amounts.append(
                            self._microsec_to_min(util.find_val_in_nested_dict(self.raw_stat_data, key_path))
                        )
            # return the time
            return [stat_total] + component_amounts
        else:
            return [0.0]

    def process_data(self, stat, seq=None, shot=None, render_layer=None, history="1"):
        """
        Takes the raw data and puts in the format listed in the class doc string under Processed Data
        :param stat: the stat name as a string
        :param seq: sequence number as string
        :param shot: shot number as string
        :param render_layer: the render layer as a string
        :param history: the history to get, defaults to the current render data
        """
        # a sequence, shot, and render layer were provided, process frame data
        if seq and shot and render_layer:
            # check if the data has been processed yet
            if not util.find_val_in_nested_dict(self.stat_data, [seq, shot, render_layer, history, 'average', stat]):
                self.process_render_layer_data(stat, seq, shot, render_layer, history=history)
        # a sequence and shot were provided, so process the render layer data
        elif seq and shot:
            # check if the data has been processed yet
            if not util.find_val_in_nested_dict(self.stat_data, [seq, shot, history, 'average', stat]):
                self.process_shot_data(stat, seq, shot, history=history)
        # just a sequence was provided, process all shot data for the sequence
        elif seq:
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

        # get list of all sequences that have stats
        seq_list = self.get_sequences(history=history)

        # no sequences, then don't add anything
        if not seq_list:
            return False

        for seq in seq_list:
            # make the key if its missing
            if seq not in self.stat_data:
                self.stat_data[seq] = {}

            # get the average for the stat for the sequence, skips if there isn't any data for the sequences
            if self.process_sequence_data(stat, seq, history=history):
                # make key if doesn't exist for the average of the stat for all sequences
                if 'average' not in self.stat_data:
                    self.stat_data["average"] = {}

                # check if already summed
                if stat not in self.stat_data["average"]:
                    # get the frame average for the shot and sum
                    main_total_sum += self.stat_data[seq]["average"][stat]["total"]
                    component_totals_sum = [
                        component_totals_sum[index] +
                        self.stat_data[seq]["average"][stat]["components"][index]
                        for index in xrange(len(component_totals_sum))
                    ]
                else:
                    continue

        # average the total sums so that the sequence has an average of all its shots data
        if stat not in self.stat_data["average"]:
            main_total_sum /= len(seq_list)
            component_totals_sum = [component_total / len(seq_list) for component_total in component_totals_sum]
            self.stat_data['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

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

        # process the sequence if it hasn't been processed
        if seq not in self.stat_data:
            self.stat_data[seq] = {}

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
                if 'average' not in self.stat_data[seq]:
                    self.stat_data[seq]["average"] = {}

                # check if already summed
                if stat not in self.stat_data[seq]["average"]:
                    # get the frame average for the shot and sum
                    main_total_sum += self.stat_data[seq][shot]["average"][stat]["total"]
                    component_totals_sum = [
                        component_totals_sum[index] +
                        self.stat_data[seq][shot]["average"][stat]["components"][index]
                        for index in xrange(len(component_totals_sum))
                    ]
                else:
                    continue

        # average the total sums so that the sequence has an average of all its shots data
        if stat not in self.stat_data[seq]["average"]:
            main_total_sum /= len(shot_list)
            component_totals_sum = [component_total / len(shot_list) for component_total in component_totals_sum]
            self.stat_data[seq]['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

    def process_shot_data(self, stat, seq, shot, history="1"):
        """
         Gets the stat and its component values per render layer, and averages those values
         :param stat: the main stat as a string
         :param seq: the seq as a string, format seq###
         :param shot: the shot as a string, format shot###
         :param history: the history as a string, defaults to "1" which is the current render data
         :return: False if no data was added to the processed data dict, True if data added
        """
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # get all of the render layers in the sequence that have data at the given history
        render_layer_list = self.get_render_layers(seq, shot, history=history)
        # no shots, then return False, don't add anything
        if not render_layer_list:
            return False

        for render_layer in render_layer_list:
            # make key if doesn't exist
            if render_layer not in self.stat_data[seq][shot]:
                self.stat_data[seq][shot][render_layer] = {}

            # average the shot's render layer frame data and store, note if process_render_layer_data returns True
            # it means there was render data for the render layer, so we add that data to the average for the shot
            if self.process_render_layer_data(stat, seq, shot, render_layer, history=history):
                # make key if doesn't exist
                if 'average' not in self.stat_data[seq][shot]:
                    self.stat_data[seq][shot]["average"] = {}
                # check if we already summed this stat
                if stat not in self.stat_data[seq][shot]["average"]:
                    # get the render layer average for the shot and sum
                    main_total_sum += self.stat_data[seq][shot][render_layer][history]["average"][stat]["total"]
                    component_totals_sum = [
                        component_totals_sum[index] +
                        self.stat_data[seq][shot][render_layer][history]["average"][stat]["components"][index]
                        for index in xrange(len(component_totals_sum))
                    ]
                else:
                    continue

        # average the total sums so that the shot has an average of all its render layer data - only process
        # if the stat doesn't exist, otherwise we already did this stat
        if stat not in self.stat_data[seq][shot]["average"]:
            main_total_sum /= len(render_layer_list)
            component_totals_sum = [component_total / len(render_layer_list) for component_total in
                                    component_totals_sum]
            self.stat_data[seq][shot]['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

    def process_render_layer_data(self, stat, seq, shot, render_layer, history="1"):
        """
         Gets the stat and its component values per frame, and averages those values
         :param stat: the main stat as a string
         :param seq: the seq as a string, format seq###
         :param shot: the shot as a string, format shot###
         :param render_layer: the render layer as a string
         :param history: the history as a string, defaults to "1" which is the current render data
         :return: False if no data was added to the processed data dict, True if data added
        """
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # get all of the frames in the shot that have data at the given history
        frames = self.get_frames(seq, shot, render_layer, history=history)

        # no frames means no history, so don't add anything to processed data
        if not frames:
            return False

        # make the key if it doesn't exist
        if history not in self.stat_data[seq][shot][render_layer]:
            self.stat_data[seq][shot][render_layer][history] = {}

        for frame in frames:
            # get the stat values for this frame - the main stat total and any sub components
            totals = self.get_stat(seq, shot, render_layer, frame, stat, history)
            # make the key if it doesn't exist
            if frame not in self.stat_data[seq][shot][render_layer][history]:
                self.stat_data[seq][shot][render_layer][history][frame] = {}
            # store frame data
            self.stat_data[seq][shot][render_layer][history][frame][stat] = {
                'total': totals[0],
                'components': totals[1:]
            }

            # sum frame data for averaging
            # first number is the main stat total, remaining numbers are the component totals
            main_total_sum += totals[0]
            component_total = totals[1:]
            component_totals_sum = [component_totals_sum[i] + component_total[i] for i in range(len(component_total))]
        # average the totals now
        main_total = main_total_sum / len(frames)
        component_totals = [component_total / len(frames) for component_total in component_totals_sum]

        # make the key if it doesn't exist
        if 'average' not in self.stat_data[seq][shot][render_layer][history]:
            self.stat_data[seq][shot][render_layer][history]['average'] = {}
        # store the frame average
        self.stat_data[seq][shot][render_layer][history]['average'][stat] = {
            'total': main_total, 'components': component_totals
        }

        return True

    def print_stat_data(self, raw=True, show_stats=False):
        """
        Formatted printout of the stat data dict, useful for debugging
        :param raw: True: show raw data as it exists on disk, False: show processed data
        :param show_stats: show the actual stats in the print (can clutter screen), off by default
        """
        # print entire stat data dict
        if show_stats:
            if raw:
                print json.dumps(self.raw_stat_data, sort_keys=True, indent=4)
            else:
                print json.dumps(self.stat_data, sort_keys=True, indent=4)
        else:
            if raw:
                temp_dict = copy.deepcopy(self.raw_stat_data)
                # only show the seq, shots, history, and frames
                for seq in temp_dict:
                    for shot in temp_dict[seq]:
                        for render_layer in temp_dict[seq][shot]:
                            for history in temp_dict[seq][shot][render_layer]:
                                for frame in temp_dict[seq][shot][render_layer][history]:
                                    temp_dict[seq][shot][render_layer][history][frame] = ""
                print json.dumps(temp_dict, sort_keys=True, indent=4)
            else:
                print json.dumps(self.stat_data, sort_keys=True, indent=4)

    def get_sequences(self, history="1"):
        """
        Get the list of sequences that have render data for a given history
        :param history: the history as a string, example '1'
        :return: the list of sequences in order ascending or an empty list if there are no sequences
        for the given history
        """
        # loop through all sequences, and check if the sequence has data for the given history
        seqs_with_data = []
        if self.raw_stat_data:
            for seq in self.raw_stat_data:
                if self.get_shots(seq, history=history):
                    seqs_with_data.append(seq)
        return sorted(seqs_with_data)

    def get_shots(self, seq, history="1"):
        """
        Get the list of shots that have render data for a given sequence and history
        :param seq: the sequence as a string, format Seq###
        :param history: the history as a string, example '1'
        :return: the list of shots in order ascending or an empty list if there are no shots for the given history
        """
        # loop through all shots in sequence, and check if the shot has data for the given history
        shots_with_data = []
        if seq in self.raw_stat_data:
            for shot in self.raw_stat_data[seq]:
                if self.get_render_layers(seq, shot, history=history):
                    shots_with_data.append(shot)
        return sorted(shots_with_data)

    def get_render_layers(self, seq, shot, history="1"):
        """
        Get the list of render layers that have render data for a given sequence, shot, and history
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param history: the history as a string, example '1'
        :return: the list of render layers in order A-Z, or an empty list if no data
        """
        # loop through all render layers in shot, and check if the render layer has data for the given history
        render_layers_with_data = []
        if seq in self.raw_stat_data:
            if shot in self.raw_stat_data[seq]:
                for render_layer in self.raw_stat_data[seq][shot]:
                    if self.get_frames(seq, shot, render_layer, history):
                        render_layers_with_data.append(render_layer)
        return sorted(render_layers_with_data)

    def get_frames(self, seq, shot, render_layer, history="1"):
        """
        Get the list of frames that have render data for a given sequence, shot, render layer, and history
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param render_layer: the render layer as a string
        :param history: the history as a string, example '1'
        :return: the list of frames (as strings not numbers) in order ascending, or an empty list if no data
        """
        # check for the given history
        if seq in self.raw_stat_data:
            if shot in self.raw_stat_data[seq]:
                if render_layer in self.raw_stat_data[seq][shot]:
                    if str(history) in self.raw_stat_data[seq][shot][render_layer]:
                        return sorted(self.raw_stat_data[seq][shot][render_layer][history].keys())
        return []

    def get_history(self, seq, shot, render_layer):
        """
        Get the list of history for a given shot
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param render_layer: the render layer as a string
        :return: the list of history sorted ascending
        """
        if seq in self.raw_stat_data:
            if shot in self.raw_stat_data[seq]:
                return sorted(self.raw_stat_data[seq][shot][render_layer].keys())
        return []

    @staticmethod
    def _microsec_to_min(microseconds):
        """
        Convert microseconds to minutes
        :param microseconds: the microseconds as a float to convert
        :return: the minutes as a float.
        """
        return float(microseconds) / 60000000.0

    @staticmethod
    def _bytes_to_gb(bytes_num):
        """
        Convert bytes to gigabytes
        :param bytes_num: the bytes as a float to convert
        :return: the gb as a float.
        """
        return float(bytes_num) / 1000000000.0
