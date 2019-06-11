import json
import copy
import ujson
import pyani.core.anivars
import pyani.core.util as util


class AniRenderData:
    """
        Note a comma after a bracket means there could be more than one entry

        LOGIC:

        read in shot's data from disk as:
                render layer: {
                    history: {
                        frame: {
                            stat: {
                                item(s)
                            },
                            more stats...
                        },
                    },
                },...

        and process the shot into:
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
                        render_layer: {
                            stat: {
                                total: float
                                components: [list of floats]
                            },
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

        Sequence :
            - Has an average of the stat and it's components for all shots, access with [seq]['average'][stat]:
                    This is all render layers combined
            - Also stores the above average but per render layer. So you can see for example how long a character
              on average takes to render for the sequence. access as [seq]['average'][render layer][stat]

        Shot:
            - Has a sum of the stat and it's components for all render layers,
              access with [seq][shot]['average'][stat]:

                we don't average because that would be the minutes on average a render layer takes in a shot. However
                environments will almost always be much longer than a character, so the average isn't very helpful. Ex:
                a shot has an environment that takes 2 hours, while a character is 30 minutes. Knowing that on average
                render layers take 75 minutes in the shot is not useful. The environment distorts the data in this case.
                more helpful is the average total time all the layers take. So we get 150 minutes.

        Render Layer:
            - Store average per stat and it's components of all frames for each history, access with
              [seq][shot][render layer][history]['average'][stat]:

        Frame:
            - has the total of the stat and it's components, acess with
              [seq][shot][render layer][history][frame]['average'][stat]:


        --------------------------------------------
        stored as dict in format:

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

    def set_custom_data(self, stat_files, user_seq, user_shot, user_render_layer):
        """
        Sets the data to user defined data
        :param stat_files: the user defined data as a list of json files (absolute path) on disk
        :param user_seq: the seq associated with the user data
        :param user_shot: the shot associated with the user data
        :param user_render_layer: the render_layer associated with render data
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

        self.stat_data[user_seq] = {}
        self.stat_data[user_seq][user_shot] = {}
#

        # go through each stat file, get the stats and add to the combined file.
        for stat_file in stat_files:
            json_data = pyani.core.util.load_json(stat_file)
            if not json_data:
                return json_data
            # get frame number, should be the second to last element, before .json
            frame_num = stat_file.split(".")[-2]
            # get the data and save under the frame number
            combined_stats[user_seq][user_shot][user_render_layer]['1'][frame_num] = json_data['render 0000']
        self.process_data(combined_stats, user_seq, user_shot)

        return None

    def is_loaded(self, seq):
        """
        Find if a sequence has been processed
        :param seq: a sequence name as a string in format Seq###
        :return True if sequence has been processed, False if not
        """
        if seq in self.stat_data:
            return True
        else:
            return False

    def load_shot_stats(self, stat_info):
        """
        Loads a shot's stats from disk and saves in the self.raw_stat_data dict. Process all render layers unless
        a render layer is given in the stat_info
        :param stat_info - a tuple containing the sequence name, shot name, history number and path to the stats
                           optionally provide a render layer. Format of tuple is:
                           (sequence, shot, history, render layer (optional), file path)
                           ex: no render layer ('Seq040', 'Shot150', '2', 'Z:/.....')
                           w/ render layer ('Seq040', 'Shot150', '2', 'layer001', 'Z:/.....')
        """
        # unpack from the tuple, check if a render layer was provided
        if len(stat_info) > 4:
            sequence, shot, history, render_layer, shot_render_data_path = stat_info
        else:
            sequence, shot, history, shot_render_data_path = stat_info
            render_layer = None

        stat_data = dict()
        stat_data[sequence] = {}
        stat_data[sequence][shot] = {}

        if sequence not in self.stat_data:
            self.stat_data[sequence] = {}
        if shot not in self.stat_data[sequence]:
            self.stat_data[sequence][shot] = {}

        with open(shot_render_data_path, 'r') as json_file:
            stat_data_on_disk = ujson.load(json_file)
            render_layers = stat_data_on_disk.keys()
            for render_lyr in render_layers:
                stat_data[sequence][shot][render_lyr] = {}
                stat_data[sequence][shot][render_lyr][history] = stat_data_on_disk[render_lyr]
            # if a render layer was provided, process only that render layer for shot
            if render_layer:
                self.process_data(stat_data, sequence, shot, render_layer=render_layer, history=history)
            else:
                self.process_data(stat_data, sequence, shot, history=history)

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

    def get_totals(self, stat, seq, shot, render_layer, frame, history="1"):
        if not stat:
            return 0.0, [0.0]
        if seq and shot and render_layer and history and frame:
            return (
                self.stat_data[seq][shot][render_layer][history][frame][stat]['total'],
                self.stat_data[seq][shot][render_layer][history][frame][stat]['components']
            )

    def get_average(self, stat, seq=None, shot=None, render_layer=None, history="1"):
        if not stat:
            return 0.0, [0.0]
        # sequence stat average (all render layers)
        if seq and not shot and not render_layer:
            return (
                self.stat_data[seq]['average'][stat]["total"],
                self.stat_data[seq]['average'][stat]["components"]
            )
        # shot stat average (all render layers)
        if seq and shot and not render_layer:
            return (
                self.stat_data[seq][shot]['average'][stat]['total'],
                self.stat_data[seq][shot]['average'][stat]['components']
            )
        # render layer stat average
        if seq and shot and render_layer:
            return (
                self.stat_data[seq][shot][render_layer][history]['average'][stat]['total'],
                self.stat_data[seq][shot][render_layer][history]['average'][stat]['components']
            )
        # seq stat average for a specific render layer
        if seq and not shot and render_layer:
            return (
                self.stat_data[seq]['average'][render_layer][stat]["total"],
                self.stat_data[seq]['average'][render_layer][stat]["components"]
            )

    def get_stat(self, stat_data, stat, seq, shot, render_layer, frame, history='1'):
        """
        gets the stat for a specific frame. if the stat is comprised of multiple stats, gets the components values too.
        :param stat_data: the stat data to process as a nested dict, see doc string for format
        :param stat: the stat to get
        :param seq: sequence number as string
        :param shot: shot number as string
        :param render_layer: the render layer as a string
        :param frame: frame number as a string
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
                stat_total = self._bytes_to_gb(util.find_val_in_nested_dict(stat_data, key_path))
            elif stat_type == "percent":
                stat_total = util.find_val_in_nested_dict(stat_data, key_path)
            else:
                stat_total = self._microsec_to_min(util.find_val_in_nested_dict(stat_data, key_path))

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
                            self._bytes_to_gb(util.find_val_in_nested_dict(stat_data, key_path))
                        )
                    elif stat_type == "percent":
                        component_amounts.append(util.find_val_in_nested_dict(stat_data, key_path))
                    else:
                        component_amounts.append(
                            self._microsec_to_min(util.find_val_in_nested_dict(stat_data, key_path))
                        )
            # return the stats
            return [stat_total] + component_amounts
        else:
            return [0.0]

    def process_data(self, stat_data, seq=None, shot=None, render_layer=None, history="1"):
        """
        Takes the raw data and puts in the format listed in the class doc string under Processed Data
        :param stat_data: the stat data to process as a nested dict, see doc string for format
        :param seq: sequence number as string
        :param shot: shot number as string
        :param render_layer: the render layer as a string
        :param history: the history to get, defaults to the current render data
        """
        # a sequence, shot, and render layer were provided, process frame data
        if seq and shot and render_layer:
            for stat in self.stat_names:
                # check if the data has been processed yet
                if not util.find_val_in_nested_dict(
                        self.stat_data, [seq, shot, render_layer, history, 'average', stat]
                ):
                    self.process_render_layer_data(stat_data, stat, seq, shot, render_layer, history=history)
        # a sequence and shot were provided, so process the render layer data
        elif seq and shot:
            for stat in self.stat_names:
                # check if the data has been processed yet
                if not util.find_val_in_nested_dict(self.stat_data, [seq, shot, 'average', stat]):
                    self.process_shot_data(stat_data, stat, seq, shot, history=history)
        # just a sequence was provided, process all shot data for the sequence
        elif seq:
            for stat in self.stat_names:
                # check if the data has been processed already
                if not util.find_val_in_nested_dict(self.stat_data, [seq, 'average', stat]):
                    self.process_sequence_data(stat_data, stat, seq)
        # show level - no sequence or shot provided
        else:
            for stat in self.stat_names:
                # check if the data has been processed already
                if not util.find_val_in_nested_dict(self.stat_data, ['average', stat]):
                    self.process_show_data(stat_data, stat, history=history)

    def process_show_data(self, stat_data, stat, history="1"):
        """
        Gets the stat and its component values for the show. values are the average of all sequence data. If all
        sequences have already been processed, then skips processing sequences and just averages the sequences
        :param stat_data: the stat data to process as a nested dict, see doc string for format
        :param stat: the main stat as a string
        :param history: the history as a string, defaults to "1" which is the current render data
        :returns: False if no data was added to the processed data dict, True if data added
        """
        # get list of all sequences that have stats
        sequences = self.get_sequences(history=history, stat_data=stat_data)
        # no sequences, then don't add anything
        if not sequences:
            return False

        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        for seq in sequences:
            # make the key if its missing
            if seq not in self.stat_data:
                self.stat_data[seq] = {}

            # get the average for the stat for the sequence, skips if there isn't any data for the sequence or sequence
            # has already been processed
            if self.process_sequence_data(stat_data, stat, seq, history=history):
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

        # average the total sums so that the show has an average of all its seq data
        if stat not in self.stat_data["average"]:
            main_total_sum /= len(sequences)
            component_totals_sum = [component_total / len(sequences) for component_total in component_totals_sum]
            self.stat_data['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

    def process_sequence_data(self, stat_data, stat, seq, history="1"):
        """
        Gets the stat and its component values per shot. Values are the average of the frame data. If all
        shots have already been processed, then skips processing shots and just averages the shots
        :param stat_data: the stat data to process as a nested dict, see doc string for format
        :param stat: the main stat as a string
        :param seq: the sequence as a string, format seq###
        :param history: the history as a string, defaults to "1" which is the current render data
        :return: False if no data was added to the processed data dict, True if data added
        """
        # get all of the shots in the sequence
        shots = self.get_shots(seq, history=history, stat_data=stat_data)
        # no shots, then return False, don't add anything
        if not shots:
            return False

        # totals for all render layers
        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        render_layers_sums = {}

        for shot in shots:
            # make key if doesn't exist
            if shot not in self.stat_data[seq]:
                self.stat_data[seq][shot] = {}

            # average the shot's frame data and store
            if self.process_shot_data(stat_data, stat, seq, shot, history=history):
                # make key if doesn't exist
                if 'average' not in self.stat_data[seq]:
                    self.stat_data[seq]["average"] = {}

                # check if already summed
                if stat not in self.stat_data[seq]["average"]:
                    # get the frame average for all render layers in shot and sum
                    main_total_sum += self.stat_data[seq][shot]["average"][stat]["total"]
                    component_totals_sum = [
                        component_totals_sum[index] +
                        self.stat_data[seq][shot]["average"][stat]["components"][index]
                        for index in xrange(len(component_totals_sum))
                    ]

                    # get average for each render layer in shot and sum - note some shots may not have every
                    # render layer
                    for render_layer in self.get_render_layers(seq, shot, history=history):
                        # check if render layer in the dict, if not make it and initialize
                        if render_layer not in render_layers_sums:
                            render_layers_sums[render_layer] = {}
                            # how many shots this render layer is in
                            render_layers_sums[render_layer]['shot count'] = 0.0
                            render_layers_sums[render_layer]['main total sum'] = 0.0
                            render_layers_sums[render_layer]['component totals sum'] = [0.0] * len(self.get_stat_components(stat))
                        # sum each render layer for this shot
                        render_layers_sums[render_layer]['shot count'] += 1.0
                        render_layers_sums[render_layer]['main total sum'] += self.stat_data[seq][shot][render_layer][history]["average"][stat]["total"]
                        render_layers_sums[render_layer]['component totals sum'] = [
                            render_layers_sums[render_layer]['component totals sum'][index] +
                            self.stat_data[seq][shot][render_layer][history]["average"][stat]["components"][index]
                            for index in xrange(len(render_layers_sums[render_layer]['component totals sum']))
                        ]
                else:
                    continue

        # average the total sums so that the sequence has an average of all its shots data
        if stat not in self.stat_data[seq]["average"]:
            main_total_sum /= len(shots)
            component_totals_sum = [component_total / len(shots) for component_total in component_totals_sum]
            self.stat_data[seq]['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

            for render_layer in render_layers_sums:
                shot_count = render_layers_sums[render_layer]['shot count']
                render_layers_sums[render_layer]['main total sum'] /= shot_count
                render_layers_sums[render_layer]['component totals sum'] = [component_total / shot_count for component_total in render_layers_sums[render_layer]['component totals sum']]
                if render_layer not in self.stat_data[seq]['average']:
                    self.stat_data[seq]['average'][render_layer] = {}
                self.stat_data[seq]['average'][render_layer][stat] = {'total': render_layers_sums[render_layer]['main total sum'], 'components': render_layers_sums[render_layer]['component totals sum']}

        return True

    def process_shot_data(self, stat_data, stat, seq, shot, history="1"):
        """
         Gets the stat and its component values per render layer, and averages those values. If all
         render layers have already been processed, then skips processing render layers and just averages the
         render layers
         :param stat_data: the stat data to process as a nested dict, see doc string for format
         :param stat: the render stat name as a string
         :param seq: the seq as a string, format seq###
         :param shot: the shot as a string, format shot###
         :param history: the history as a string, defaults to "1" which is the current render data
         :return: False if no data was added to the processed data dict, True if data added
        """
        render_layers = self.get_render_layers(seq, shot, history=history, stat_data=stat_data)
        # no render layers, then return False, don't add anything
        if not render_layers:
            return False

        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        for render_layer in render_layers:
            # make key if doesn't exist
            if render_layer not in self.stat_data[seq][shot]:
                self.stat_data[seq][shot][render_layer] = {}

            # average the shot's render layer frame data and store, note if process_render_layer_data returns True
            # it means there was render data for the render layer, so we add that data to the average for the shot
            if self.process_render_layer_data(stat_data, stat, seq, shot, render_layer, history=history):
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

        # only process if the stat doesn't exist, otherwise we already did this stat
        if stat not in self.stat_data[seq][shot]["average"]:
            """
            we don't average becuase that would be the minutes on average a render layer takes in a shot. However
            environments will almost always be much longer than a character, so the average isn't very helpful. Ex:
            a shot has an environment that takes 2 hours, while a character is 30 minutes. Knowing that on average
            render layers take 75 minutes in the shot is not useful. The environment distorts the data in this case.
            more helpful is the average total time all the layers take. So we get 150 minutes.
            to average the total minutes per render layer for a shot, uncomment below.
            
            main_total_sum /= len(render_layers)
            component_totals_sum = [component_total / len(render_layers) for component_total in
                                    component_totals_sum]
            """
            self.stat_data[seq][shot]['average'][stat] = {'total': main_total_sum, 'components': component_totals_sum}

        return True

    def process_render_layer_data(self, stat_data, stat, seq, shot, render_layer, history="1"):
        """
         Gets the stat and its component values per frame, and averages those values. If all
         frames have already been processed, then skips processing frames and just averages the frames
         :param stat_data: the stat data to process as a nested dict, see doc string for format
         :param stat: the main stat as a string
         :param seq: the seq as a string, format seq###
         :param shot: the shot as a string, format shot###
         :param render_layer: the render layer as a string
         :param history: the history as a string, defaults to "1" which is the current render data
         :return: False if no data was added to the processed data dict, True if data added
        """
        # check if the data has already been processed - an average should exist if it has been processed
        if self.is_render_layer_stat_processed(seq, shot, render_layer, history, stat):
            return True

        frames = self.get_frames(seq, shot, render_layer, history=history, stat_data=stat_data)
        if not frames:
            return False

        main_total_sum = 0.0
        component_totals_sum = [0.0] * len(self.get_stat_components(stat))

        # make the key if it doesn't exist
        if history not in self.stat_data[seq][shot][render_layer]:
            self.stat_data[seq][shot][render_layer][history] = {}

        for frame in frames:
            # get the stat values for this frame - the main stat total and any sub components
            totals = self.get_stat(stat_data, stat, seq, shot, render_layer, frame, history)
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

    def print_stat_data(self, show_stats=False):
        """
        Formatted printout of the stat data dict, useful for debugging
        :param show_stats: show the actual stats in the print (can clutter screen), off by default
        """
        # print entire stat data dict
        if show_stats:
            print json.dumps(self.stat_data, sort_keys=True, indent=4)
        else:
            temp_dict = copy.deepcopy(self.stat_data)
            # only show the seq, shots, history, and frames
            for seq in temp_dict:
                if 'average' in seq:
                    temp_dict['average'] = {key: "" for key in temp_dict['average'].keys()}
                for shot in temp_dict[seq]:
                    if 'average' in shot:
                        average_list = {}
                        for key in temp_dict[seq]['average'].keys():
                            if key in self.stat_names:
                                average_list[key] = ""
                            else:
                                render_layer_stats = temp_dict[seq]['average'][key].keys()
                                average_list[key] = render_layer_stats
                        temp_dict[seq]['average'] = average_list
                    else:
                        for render_layer in temp_dict[seq][shot]:
                            if 'average' in render_layer:
                                temp_dict[seq][shot]['average'] = {
                                    key: "" for key in temp_dict[seq][shot]['average'].keys()
                                }
                            else:
                                for history in temp_dict[seq][shot][render_layer]:
                                    if 'average' in history:
                                        temp_dict[seq][shot][render_layer]['average'] = {
                                            key: "" for key in temp_dict[seq][shot][render_layer]['average'].keys()
                                        }

                                    else:
                                        for frame in temp_dict[seq][shot][render_layer][history]:
                                            if 'average' in frame:
                                                temp_dict[seq][shot][render_layer][history]['average'] = {
                                                    key: "" for key in temp_dict[seq][shot][render_layer][history]['average'].keys()
                                                }
                                            else:
                                                temp_dict[seq][shot][render_layer][history][frame] = ""
            print json.dumps(temp_dict, sort_keys=True, indent=4)

    def get_sequences(self, history="1", stat_data=None):
        """
        Get the list of sequences that have render data for a given history
        :param history: the history as a string, example '1'
        :param stat_data: a nested dict of stats in format described in doc string, defaults to the class
                          member variable self.stat_data
        :return: the list of sequences in order ascending or an empty list if there are no sequences
        for the given history
        """
        if not stat_data:
            stat_data = self.stat_data
        # loop through all sequences, and check if the sequence has data for the given history
        seqs_with_data = []
        if stat_data:
            for seq in stat_data:
                # make sure the sequence has data and is a valid sequence name
                if self.get_shots(seq, history=history, stat_data=stat_data) and util.is_valid_seq_name(seq):
                    seqs_with_data.append(seq)
        return sorted(seqs_with_data)

    def get_shots(self, seq, history="1", stat_data=None, render_layer=None):
        """
        Get the list of shots that have render data for a given sequence and history or get a list of shots in
        a sequence that have render data for a given render layer at the specified history
        :param seq: the sequence as a string, format Seq###
        :param history: the history as a string, example '1'
        :param stat_data: a nested dict of stats in format described in doc string, defaults to the class
                          member variable self.stat_data
        :return: the list of shots in order ascending or an empty list if there are no shots for the given history
        """
        if not stat_data:
            stat_data = self.stat_data

        shots_with_data = []
        # get any shots in the sequence that have data for the render layer provided - uses recursion
        if render_layer:
            for shot in self.get_shots(seq, history=history):
                if render_layer in self.get_render_layers(seq, shot, history=history, stat_data=stat_data) \
                            and util.is_valid_shot_name(shot):
                    shots_with_data.append(shot)
        # get shots based off sequence using all render layers
        else:
            # loop through all shots in sequence, and check if the shot has data for the given history
            if seq in stat_data:
                for shot in stat_data[seq]:
                    if self.get_render_layers(seq, shot, history=history, stat_data=stat_data) \
                            and util.is_valid_shot_name(shot):
                        shots_with_data.append(shot)
        return sorted(shots_with_data)

    def get_render_layers(self, seq, shot=None, history="1", stat_data=None):
        """
        Get the list of render layers that have render data for a given sequence or shot at the provided history.
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###.
        :param history: the history as a string, example '1'
        :param stat_data: a nested dict of stats in format described in doc string, defaults to the class
                  member variable self.stat_data
        :return: the list of render layers in order A-Z, or an empty list if no data
        """
        if not stat_data:
            stat_data = self.stat_data

        # sequence level
        if seq and not shot:
            render_layers_with_data = []
            for shot in self.get_shots(seq, history=history, stat_data=stat_data):
                # for every render layer check if in list, if not add - note uses recursion
                for render_layer in self.get_render_layers(seq, shot, history=history, stat_data=stat_data):
                    if render_layer not in render_layers_with_data:
                        render_layers_with_data.append(render_layer)
        # shot level
        else:
            # loop through all render layers in shot, and check if the render layer has data for the given history
            render_layers_with_data = []
            if seq in stat_data:
                if shot in stat_data[seq]:
                    for render_layer in stat_data[seq][shot]:
                        if self.get_frames(seq, shot, render_layer, history, stat_data=stat_data) \
                                and 'average' not in render_layer:
                            render_layers_with_data.append(render_layer)
        return sorted(render_layers_with_data)

    def get_frames(self, seq, shot, render_layer, history="1", stat_data=None):
        """
        Get the list of frames that have render data for a given sequence, shot, render layer, and history
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param render_layer: the render layer as a string
        :param history: the history as a string, example '1'
        :param stat_data: a nested dict of stats in format described in doc string, defaults to the class
                  member variable self.stat_data
        :return: the list of frames (as strings not numbers) in order ascending, or an empty list if no data
        """
        if not stat_data:
            stat_data = self.stat_data
        # check for the given history
        if seq in stat_data:
            if shot in stat_data[seq]:
                if render_layer in stat_data[seq][shot]:
                    if str(history) in stat_data[seq][shot][render_layer]:
                        valid_frames = [
                            frame for frame in stat_data[seq][shot][render_layer][history]
                            if util.is_valid_frame(frame)
                        ]
                        return sorted(valid_frames)
        return []

    def get_history(self, seq, shot, render_layer, stat_data=None):
        """
        Get the list of history for a given shot
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param render_layer: the render layer as a string
        :param stat_data: a nested dict of stats in format described in doc string, defaults to the class
                          member variable self.stat_data
        :return: the list of history sorted ascending
        """
        if not stat_data:
            stat_data = self.stat_data
        if seq in stat_data:
            if shot in stat_data[seq]:
                valid_history = [
                    history for history in stat_data[seq][shot][render_layer]
                    if util.is_number(history)
                ]
                return sorted(valid_history)
        return []

    def is_render_layer_stat_processed(self, seq, shot, render_layer, history, stat):
        """
        Checks if a render stat in a render layer has been averaged
        :param seq: the sequence as a string, format Seq###
        :param shot: the shot as a string, format Shot###
        :param render_layer: the render layer as a string
        :param history: the history as a string, example '1'
        :param stat: the name of the stat as a string
        :return: True if processed, False if not
        """
        # check if the data has already been processed - an average should exist if it has been processed
        if util.find_val_in_nested_dict(self.stat_data, [seq, shot, render_layer, history, 'average', stat]):
            return True
        else:
            return False

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
