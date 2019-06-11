"""
This script generates test data. Just set the variables under configuration variables

This will generate data for the specified settings below and also create a sequence / shot list in
C:pyanitools\app_data\shared\sequences.json with the fake sequences and shots
"""

import os
import pyani.core.anivars
import pyani.core.util
import tempfile
import shutil


"""
CONFIGURATION VARIABLES
"""
# should be a sequence number that doesn't exist, will increment by one and remove these after testing
seq_start = 5002
# this will get padded with two zeroes
shot_start = 1
# this will get padded with 2 zeroes
render_lyr_start = 1
# number of sequences to generate data for
num_sequences = 1
# number of shots to generate data for
num_shots = 50
# number of frames to generate data for
num_frames = 150
# number of render layers to generate data for
num_render_layers = 5
# number of history to generate data for
num_history = 1
"""
END CONFIG
"""

# do not change these variables unless core code locations changed
anivars = pyani.core.anivars.AniVars()
# the file from maya with a frame of data
stat_source = "C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\PyRenderDataViewer\\venv\\data_generation_to_test\\stat_data.json"
seq_root = "Z:\\LongGong\\sequences"
temp_output_path = os.path.join(tempfile.gettempdir(), "PyRenderDataViewer")
shot_template_stats_file = os.path.join(temp_output_path, "shot_template_stats.json")
sequence_list_json = os.path.join(temp_output_path, "sequences.json")
# build fake history
history_list = [str(count) for count in range(1, num_history+1)]
# build fake sequences
seq_names_list = ["Seq{0}".format(str(count)) for count in range(seq_start, seq_start+num_sequences)]
# build fake shots
shot_names_list = ["Shot{0}".format(str(count).zfill(3)) for count in range(shot_start, shot_start+num_shots)]
# build fake render layers
render_lyrs_list = [
    "Render_Lyr{0}".format(str(count).zfill(3)) for count in range(render_lyr_start, render_lyr_start+num_render_layers)
]


def make_sequence_list():
    """
    Creates a json file with the testing sequence directories in format
    "Seq230": [
          {
             "last_frame": "",
             "first_frame": "",
             "shot": "Shot040"
          },...
      ],...
    }
    :return:
    """
    sequences = {}
    for seq_name in seq_names_list:
        if seq_name not in sequences:
            sequences[seq_name] = []
        for shot in shot_names_list:
            shot_dict = {}
            shot_dict["shot"] = shot
            shot_dict["first frame"] ="1001"
            shot_dict["last frame"] ="1150"
            sequences[seq_name].append(shot_dict)
    error = pyani.core.util.write_json(sequence_list_json, sequences, indent=4)
    if error:
        print error

    shutil.move(anivars.sequence_shot_list_json, os.path.join(anivars.app_data_shared, "sequences_bk.json"))
    shutil.copy2(sequence_list_json, anivars.app_data_shared)


def setup_directories():
    """
    Make the render data directories, ie Z:\LongGong\sequences\Seq###\lighting\render_data\Shot###\history\Seq###_Shot###.json
    """
    for seq_name in seq_names_list:
        print "Creating {0}".format(seq_name)
        for shot in shot_names_list:
            print "\tCreating {0}".format(shot)
            for history in history_list:
                print "\t\tCreating history: {0}".format(history)
                path = os.path.join(seq_root, seq_name, "lighting\\render_data", shot, history)
                os.makedirs(path)
                stats_file_name = os.path.join(path, "{0}_{1}.json".format(seq_name, shot))
                shutil.copy2(shot_template_stats_file, stats_file_name)


def cleanup():
    """
    Remove render data directories made for testing
    Z:\LongGong\sequences\Seq###
    :return:
    """
    for seq_name in seq_names_list:
        shutil.rmtree(os.path.join(seq_root, seq_name), ignore_errors=True)

    os.remove(anivars.sequence_shot_list_json)
    shutil.move(os.path.join(anivars.app_data_shared, "sequences_bk.json"),
                os.path.join(anivars.app_data_shared, "sequences.json"))


def make_stat_file(input_data_file, output_data_file, num_frames):
    """
    Takes a stat file with one frame of data and makes a new one with num_frames worth of data in the temp dir
    :param input_data_file: the file with a frame of data
    :param output_data_file: new file with num_frames worth of data
    :param num_frames: number of frames
    """
    json_data = pyani.core.util.load_json(input_data_file)
    if not json_data:
        print json_data
    # get the data from the file
    frame_data = json_data['1001']
    # a dict of all the frame sof data
    frames_data = {}
    shot_data = {}
    # create data for every frame - start at frame 1001, go to 1001 + the number of desired frames worth of data
    for frame in xrange(1001, 1001+num_frames):
        frames_data[frame] = frame_data

    ''' now build dict in format
    {
        <render lyr> : {
                <frame> : {
                    stats
                },...
        },...
    '''
    for render_lyr in render_lyrs_list:
        if render_lyr not in shot_data:
            shot_data[render_lyr] = {}
        shot_data[render_lyr] = frames_data
    # write data to disk
    error = pyani.core.util.write_json(output_data_file, shot_data, indent=4)
    if error:
        print error


if __name__ == '__main__':
    # setup the temp file to write to, this will be used to copy to all sequences, its a shots worth of data
    if os.path.exists(temp_output_path):
        error = pyani.core.util.rm_dir(temp_output_path)
        if error:
            print error
    error = pyani.core.util.make_dir(temp_output_path)
    if error:
        print error
    # make a file that represents a shot's worth of data - 200 frames
    make_stat_file(stat_source, shot_template_stats_file, num_frames)

    # copy the above file to the sequences for every shot
    setup_directories()

    # make the sequence list
    make_sequence_list()


