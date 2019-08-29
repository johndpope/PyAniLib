"""
This script generates test data. Just set the variables under configuration variables

This will generate data for the specified settings below and also create a sequence / shot list in
C:pyanitools\app_data\shared\sequences.json with the fake sequences and shots
"""

import os
import sys
import pyani.core.anivars
import pyani.core.appvars
import pyani.core.util
import tempfile
import shutil

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets


class RenderDataCreateWin(QtWidgets.QDialog):
    def __init__(
            self,
            seq_start,
            shot_start,
            render_lyr_start,
            num_sequences,
            num_shots,
            num_frames,
            num_render_layers,
            num_history
    ):
        super(RenderDataCreateWin, self).__init__()
        self.setWindowTitle("Render Data Generator")
        self.setFixedWidth(400)
        self.setFixedHeight(200)


        """
        CONFIGURATION VARIABLES
        """
        # should be a sequence number that doesn't exist, will increment by one and remove these after testing
        self.seq_start = seq_start
        # this will get padded with two zeroes
        self.shot_start = shot_start
        # this will get padded with 2 zeroes
        self.render_lyr_start = render_lyr_start
        # number of sequences to generate data for
        self.num_sequences = num_sequences
        # number of shots to generate data for
        self.num_shots = num_shots
        # number of frames to generate data for
        self.num_frames = num_frames
        # number of render layers to generate data for
        self.num_render_layers = num_render_layers
        # number of history to generate data for
        self.num_history = num_history
        """
        END CONFIG
        """

        # do not change these variables unless core code locations changed
        self.anivars = pyani.core.anivars.AniVars()
        self.appvars = pyani.core.appvars.AppVars()
        # the file from maya with a frame of data
        self.stat_source = "C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\PyRenderDataViewer\\venv\\" \
                           "data_generation_to_test\\stat_data.json"
        self.seq_root = "Z:\\LongGong\\sequences"
        self.temp_output_path = os.path.join(tempfile.gettempdir(), "PyRenderDataViewer")
        self.shot_template_stats_file = os.path.join(self.temp_output_path, "shot_template_stats.json")
        self.sequence_list_json = os.path.join(self.temp_output_path, "sequences.json")
        # build fake history
        self.history_list = [str(count) for count in range(1, self.num_history + 1)]
        # build fake sequences
        self.seq_names_list = ["Seq{0}".format(str(count)) for count in range(
            self.seq_start, self.seq_start + self.num_sequences)]
        # build fake shots
        self.shot_names_list = ["Shot{0}".format(str(count).zfill(3)) for count in range(
            self.shot_start, self.shot_start + self.num_shots)]
        # build fake render layers
        self.render_lyrs_list = [
            "Render_Lyr{0}".format(str(count).zfill(3)) for count in
            range(self.render_lyr_start, self.render_lyr_start + self.num_render_layers)
        ]

        # UI vars
        self.btn_make_data_and_sequence_list = QtWidgets.QPushButton("generate all test data + sequence list")
        self.btn_make_data_and_sequence_list.pressed.connect(self.generate_data_and_sequence_list)

        self.btn_make_sequence_list = QtWidgets.QPushButton("generate test sequence list only")
        self.btn_make_sequence_list.pressed.connect(self.generate_sequence_list)

        self.btn_make_data = QtWidgets.QPushButton("generate test data only")
        self.btn_make_data.pressed.connect(self.generate_data)

        self.btn_cleanup = QtWidgets.QPushButton("remove test data")
        self.btn_cleanup.pressed.connect(self.cleanup)

        self.btn_revert_sequence_list = QtWidgets.QPushButton("revert sequence list")
        self.btn_revert_sequence_list.pressed.connect(self.revert_sequence_list)

        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.btn_make_data_and_sequence_list)
        layout.addWidget(self.btn_make_sequence_list)
        layout.addWidget(self.btn_make_data)
        layout.addWidget(QtWidgets.QLabel("Cleanup Operations:"))
        layout.addWidget(self.btn_cleanup)
        layout.addWidget(self.btn_revert_sequence_list)

        self.setLayout(layout)

    def setup(self):
        """
        Makes the temp dir for creating data file
        :return: True if created, False if not
        """
        # setup the temp file to write to, this will be used to copy to all sequences, its a shots worth of data
        if os.path.exists(self.temp_output_path):
            error = pyani.core.util.rm_dir(self.temp_output_path)
            if error:
                print error
                return False
        error = pyani.core.util.make_dir(self.temp_output_path)
        if error:
            print error
            return False
        return True

    def generate_data_and_sequence_list(self):
        if not self.generate_sequence_list():
            print "Can't continue, sequence list can't be generated, see above error."
            return

        if not self.generate_data():
            print "Data not generated, see above error."
            return

    def generate_data(self):
        """
        Makes the data for sequence(s)
        :return: True if data made, False if Not
        """
        # make a file that represents a shot's worth of data - 200 frames
        if not self.make_stat_file(self.stat_source, self.shot_template_stats_file, self.num_frames):
            print "Stat file template couldn't be made, see above error."
            return False

        print "Stat file template generated."

        # copy the above file to the sequences for every shot
        if not self.copy_data():
            print "Could not copy the data file to all shot(s) in the sequence(s). See above error"
            return False

        print "Data for sequences generated."

    def generate_sequence_list(self):
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
        :return: True if created, False if not
        """
        sequences = {}
        for seq_name in self.seq_names_list:
            if seq_name not in sequences:
                sequences[seq_name] = []
            for shot in self.shot_names_list:
                shot_dict = dict()
                shot_dict["shot"] = shot
                shot_dict["first frame"] = "1001"
                shot_dict["last frame"] = "1150"
                sequences[seq_name].append(shot_dict)
        error = pyani.core.util.write_json(self.sequence_list_json, sequences, indent=4)
        if error:
            print error
            return False

        try:
            shutil.move(self.anivars.sequence_shot_list_json,
                        os.path.join(self.appvars.persistent_data_path, "sequences_bk.json"))
            shutil.copy2(self.sequence_list_json, self.appvars.persistent_data_path)
        except (WindowsError, EnvironmentError, IOError, AttributeError) as error:
            print error
            return False

        print "Sequence list created."

        return True

    def copy_data(self):
        """
        Make the render data directories, ie
        Z:\LongGong\sequences\Seq###\lighting\render_data\Shot###\history\Seq###_Shot###.json
        return: True if created, False if not
        """
        for seq_name in self.seq_names_list:
            print "Creating {0}".format(seq_name)
            for shot in self.shot_names_list:
                print "\tCreating {0}".format(shot)
                for history in self.history_list:
                    print "\t\tCreating history: {0}".format(history)
                    try:
                        path = os.path.join(self.seq_root, seq_name, "lighting\\render_data", shot, history)
                        os.makedirs(path)
                        stats_file_name = os.path.join(path, "{0}_{1}.json".format(seq_name, shot))
                        shutil.copy2(self.shot_template_stats_file, stats_file_name)
                    except (WindowsError, IOError, AttributeError, ValueError, EnvironmentError, IndexError) as error:
                        print error
                        return False

        return True

    def make_stat_file(self, input_data_file, output_data_file, num_frames):
        """
        Takes a stat file with one frame of data and makes a new one with num_frames worth of data in the temp dir
        :param input_data_file: the file with a frame of data
        :param output_data_file: new file with num_frames worth of data
        :param num_frames: number of frames
        :return: True if file made, False if Not
        """
        json_data = pyani.core.util.load_json(input_data_file)
        if not json_data:
            print json_data
            return False

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
        for render_lyr in self.render_lyrs_list:
            if render_lyr not in shot_data:
                shot_data[render_lyr] = {}
            shot_data[render_lyr] = frames_data
        # write data to disk
        error = pyani.core.util.write_json(output_data_file, shot_data, indent=4)
        if error:
            print error
            return False

        return True

    def cleanup(self):
        """
        Remove render data directories made for testing
        Z:\LongGong\sequences\Seq###
        :return: True if removed, False if not
        """
        for seq_name in self.seq_names_list:
            try:
                shutil.rmtree(os.path.join(self.seq_root, seq_name), ignore_errors=True)
            except (WindowsError, IOError, EnvironmentError) as error:
                print error
                return False

        print "Test data removed."

    def revert_sequence_list(self):
        """
        restore the original sequence list
        :return: True if restored, False if not
        """
        try:
            os.remove(self.anivars.sequence_shot_list_json)
            shutil.move(os.path.join(self.appvars.persistent_data_path, "sequences_bk.json"),
                        os.path.join(self.appvars.persistent_data_path, "sequences.json"))
        except (WindowsError, IOError, EnvironmentError) as error:
            print error
            return False

        print "Reverted."

def main():
    """
    entry function
    """

    """
    ========================================================================================================
    CONFIGURATION VARIABLES
    """

    # should be a sequence number that doesn't exist, will increment by one and remove these after testing
    seq_start = 5001
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
    ========================================================================================================
    """

    # create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    render_data_gen_win = RenderDataCreateWin(
        seq_start,
        shot_start,
        render_lyr_start,
        num_sequences,
        num_shots,
        num_frames,
        num_render_layers,
        num_history
    )
    if not render_data_gen_win.setup():
        print "Could not create temp directory to make data file template. See above error"
        return

    # run
    render_data_gen_win.show()
    app.exec_()


if __name__ == '__main__':
    main()
