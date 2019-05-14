import os
import pyani.core.anivars
import pyani.core.util
import tempfile
import shutil

anivars = pyani.core.anivars.AniVars()
# the file from maya with a frame of data
stat_source = "C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\PyRenderDataViewer\\venv\\render_data\\stat_data.json"
seq_root = "Z:\\LongGong\\sequences"
temp_output_path = os.path.join(tempfile.gettempdir(), "PyRenderDataViewer")
shot_template_stats_file = os.path.join(temp_output_path, "shot_template_stats.json")
sequence_list_json = os.path.join(temp_output_path, "sequences.json")
# should be a sequence number that doesn't exist, will increment by one and remove these after testing
seq_start = 5001
shot_start = 1
render_lyr_start = 1
num_sequences = 50
num_shots = 50
num_frames = 150
num_render_layers = 4
history_list = [str(count) for count in range(1,6)]
seq_names_list = ["Seq{0}".format(str(count)) for count in range(seq_start, seq_start+num_sequences)]
shot_names_list = ["Shot{0}".format(str(count).zfill(3)) for count in range(shot_start, shot_start+num_shots)]
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
    Make the render data directories, ie Z:\LongGong\sequences\Seq###\lighting\render_data\Shot###\render_layer\history
    """
    for seq_name in seq_names_list:
        for shot in shot_names_list:
            for render_lyr in render_lyrs_list:
                for history in history_list:
                    path = os.path.join(seq_root, seq_name, "lighting\\render_data", shot, render_lyr, history)
                    os.makedirs(path)
                    shutil.copy2(shot_template_stats_file, path)


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
    shot_data = {}
    # create data for every frame - start at frame 1001, go to 1001 + the number of desired frames worth of data
    for frame in xrange(1001, 1001+num_frames):
        shot_data[frame] = frame_data
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


