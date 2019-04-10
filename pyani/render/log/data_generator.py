import os
import pyani.core.anivars
import pyani.core.util
import tempfile

# the file from maya with a frame of data
stat_source = "C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\PyRenderDataViewer\\venv\\render_data\\stat_data.json"
seq_root = "Z:\\LongGong\\sequences"
anivars = pyani.core.anivars.AniVars()


def make_stat_file(input_data_file, output_data_file, num_frames):
    json_data = pyani.core.util.load_json(input_data_file)
    if not json_data:
        print json_data
    # get the data from the file
    frame_data = json_data['render 0000']
    shot_data = {}
    # create data for every frame - start at frame 1001, go to 1001 + the number of desired frames worth of data
    for frame in xrange(1001, 1001+num_frames):
        shot_data[frame] = frame_data
    # write data to disk
    error = pyani.core.util.write_json(output_data_file, shot_data, indent=4)
    if error:
        print error


def make_sequences_render_data_structure(stats_file):
    for sequence in anivars.get_sequence_list():
        # make all sequence folder if doesn't exist
        sequence_path = os.path.join(seq_root, sequence)
        if not os.path.exists(sequence_path):
            error = pyani.core.util.make_dir(sequence_path)
            if error:
                    print error
        # make lighting render data folders if don't exist
        sequence_render_data_path = os.path.join(sequence_path, "lighting\\render_data\\1")
        if not os.path.exists(sequence_render_data_path):
            error = pyani.core.util.make_all_dir_in_path(sequence_render_data_path)
            if error:
                    print error
        # get a list of shots
        anivars.update(sequence)
        shots = anivars.get_shot_list()
        for shot in shots:
            dest_file_name = "{0}\\stats_{1}_{2}.json".format(sequence_render_data_path, sequence, shot)
            pyani.core.util.copy_file(stats_file, dest_file_name)


if __name__ == '__main__':
    # setup the temp file to write to, this will be used to copy to all sequences, its a shots worth of data
    temp_output_path = os.path.join(tempfile.gettempdir(), "PyRenderDataViewer")
    shot_template_stats_file = os.path.join(temp_output_path, "shot_template_stats.json")
    if os.path.exists(temp_output_path):
        error = pyani.core.util.rm_dir(temp_output_path)
        if error:
            print error
    error = pyani.core.util.make_dir(temp_output_path)
    if error:
            print error
    # make a file that represents a shot's worth of data - 200 frames
    make_stat_file(stat_source, shot_template_stats_file, 200)
    # copy the above file to the sequences for every shot
    # make_sequences_render_data_structure(temp_output_path)
