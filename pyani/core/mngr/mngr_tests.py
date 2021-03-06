'''
Go to Run > Edit Configurations and remove from tests if pyTest trying to run. PyTest tries to auto-discover
files with 'test' in them
'''

import os
import sys
import json
import qdarkstyle
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core
import pyani.core.util

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets


class TestTaskListWin:
    def __init__(self):
        pass

    def run(self, post_tasks):
        """
        Starts the update process
        """
        # run the post task(s)
        for task in post_tasks:
            func = task['func']
            params = task['params']
            func(*params)


class TestWindow(QtWidgets.QDialog):
    def __init__(self):
        super(TestWindow, self).__init__()

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        self.ui_mngr = pyani.core.mngr.ui.core.AniAssetUpdateReport(self)

        self.setWindowTitle("Unit Tests For Updating Tools and Assets")

        self.btn_test_post_task_unit_test = QtWidgets.QPushButton("start test post task unit test")
        self.btn_test_post_task_unit_test.pressed.connect(self.start_post_task_unit_test)

        '''
        -----------------------------------------------------------------------------------------------------------
        '''

        self.btn_create_setup_dependencies_unit_test = QtWidgets.QPushButton("start create setup dependencies unit test")
        self.btn_create_setup_dependencies_unit_test.pressed.connect(self.start_create_setup_dependencies_unit_test)

        self.btn_create_update_config_unit_test = QtWidgets.QPushButton("start create update config unit test")
        self.btn_create_update_config_unit_test.pressed.connect(self.start_update_config_unit_test)

        self.btn_create_seq_list_unit_test = QtWidgets.QPushButton("start create sequence list unit test")
        self.btn_create_seq_list_unit_test.pressed.connect(self.start_seq_list_unit_test)

        self.btn_create_launcher_unit_test = QtWidgets.QPushButton("start create support launcher unit test")
        self.btn_create_launcher_unit_test.pressed.connect(self.start_launcher_unit_test)

        self.btn_create_desktop_shortcut_unit_test = QtWidgets.QPushButton("start create desktop_shortcut unit test")
        self.btn_create_desktop_shortcut_unit_test.pressed.connect(self.start_desktop_shortcut_unit_test)

        self.btn_create_customize_nuke_unit_test = QtWidgets.QPushButton("start create customize_nuke unit test")
        self.btn_create_customize_nuke_unit_test.pressed.connect(self.start_customize_nuke_unit_test)

        self.btn_create_task_sched_unit_test = QtWidgets.QPushButton("start create windows task sched unit test")
        self.btn_create_task_sched_unit_test.pressed.connect(self.start_create_task_sched_unit_test)

        '''
        -----------------------------------------------------------------------------------------------------------
        '''

        self.btn_build_cache_unit_test = QtWidgets.QPushButton("start asset cache build unit test")
        self.btn_build_cache_unit_test.pressed.connect(self.start_build_cache_unit_test)

        self.btn_update_version_after_dl_unit_test = QtWidgets.QPushButton("start version update after dl unit test")
        self.btn_update_version_after_dl_unit_test.pressed.connect(self.start_update_version_after_dl_unit_test)

        self.btn_audio_changed_unit_test = QtWidgets.QPushButton("start audio changed unit test")
        self.btn_audio_changed_unit_test.pressed.connect(self.start_audio_changed_unit_test)

        self.btn_audio_changed_report_unit_test = QtWidgets.QPushButton("start audio changed report unit test")
        self.btn_audio_changed_report_unit_test.pressed.connect(self.start_audio_changed_report_unit_test)

        # dpwnload assets in update config
        self.btn_assets_download_update_config_unit_test = QtWidgets.QPushButton("start download assets in update config unit test")
        self.btn_assets_download_update_config_unit_test.pressed.connect(self.start_download_assets_in_update_config_test)

        # cleans up update config if any assets non longer exist
        self.btn_sync_update_config_assets = QtWidgets.QPushButton("start sync assets in update config unit test")
        self.btn_sync_update_config_assets.pressed.connect(self.start_sync_update_config_assets)

        '''
        -----------------------------------------------------------------------------------------------------------
        '''

        self.btn_show_tools_cache = QtWidgets.QPushButton("show tools cache unit test")
        self.btn_show_tools_cache.pressed.connect(self.show_tool_data)

        self.btn_save_tools_download_list = QtWidgets.QPushButton("save the list of files to download")
        self.btn_save_tools_download_list.pressed.connect(self.save_tools_to_dl)

        self.btn_build_tools_cache = QtWidgets.QPushButton("start tools cache build (complete rebuild) unit test")
        self.btn_build_tools_cache.pressed.connect(self.start_build_tools_cache_unit_test)

        self.btn_update_tools_cache = QtWidgets.QPushButton("start tools cache update (update existing tools) unit test")
        self.btn_update_tools_cache.pressed.connect(self.start_update_tools_cache_unit_test)

        self.btn_update_config_new_tools = QtWidgets.QPushButton("start tools update config with new tools unit test")
        self.btn_update_config_new_tools.pressed.connect(self.start_update_config_new_tools_unit_test)

        self.btn_download_tools = QtWidgets.QPushButton("start tools download unit test")
        self.btn_download_tools.pressed.connect(self.start_tools_download_unit_test)

        self.btn_tools_cleanup = QtWidgets.QPushButton("start tools cleanup unit test")
        self.btn_tools_cleanup.pressed.connect(self.start_tools_cleanup)

        self.btn_get_tools_version = QtWidgets.QPushButton("get newest version")
        self.btn_get_tools_version.pressed.connect(self.get_tools_version)

        self.btn_get_tools_notes = QtWidgets.QPushButton("get notes")
        self.btn_get_tools_notes.pressed.connect(self.get_tools_notes)

        self.btn_get_new_and_changed_tools = QtWidgets.QPushButton("get new and changed tools")
        self.btn_get_new_and_changed_tools.pressed.connect(self.get_new_and_changed_tools)

        self.btn_get_new_and_changed_assets = QtWidgets.QPushButton("get new and changed assets")
        self.btn_get_new_and_changed_assets.pressed.connect(self.get_new_and_changed_assets)

        self.btn_get_all_new_and_changed_assets = QtWidgets.QPushButton("get all new and changed assets")
        self.btn_get_all_new_and_changed_assets.pressed.connect(self.get_all_new_and_changed_assets)

        self.version_input = QtWidgets.QLineEdit()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("<b>Misc Unit Tests</b>"))
        layout.addWidget(self.btn_test_post_task_unit_test)
        layout.addWidget(QtWidgets.QLabel("<b>Setup/Update Unit Tests</b>"))
        layout.addWidget(self.btn_create_setup_dependencies_unit_test)
        layout.addWidget(self.btn_create_update_config_unit_test)
        layout.addWidget(self.btn_create_seq_list_unit_test)
        layout.addWidget(self.btn_create_launcher_unit_test)
        layout.addWidget(self.btn_create_desktop_shortcut_unit_test)
        layout.addWidget(self.btn_create_customize_nuke_unit_test)
        layout.addWidget(self.btn_create_task_sched_unit_test)

        layout.addWidget(QtWidgets.QLabel("<b>Asset and Tool Unit Tests</b>"))
        layout.addWidget(self.btn_get_all_new_and_changed_assets)

        layout.addWidget(QtWidgets.QLabel("<b>Asset Unit Tests</b>"))
        layout.addWidget(self.btn_build_cache_unit_test)
        layout.addWidget(self.btn_update_version_after_dl_unit_test)
        layout.addWidget(self.btn_audio_changed_unit_test)
        layout.addWidget(self.btn_audio_changed_report_unit_test)
        layout.addWidget(self.btn_assets_download_update_config_unit_test)
        layout.addWidget(self.btn_sync_update_config_assets)
        layout.addWidget(self.btn_get_new_and_changed_assets)

        layout.addWidget(QtWidgets.QLabel("<b>Tools Unit Tests</b>"))
        layout.addWidget(self.btn_show_tools_cache)
        layout.addWidget(self.btn_save_tools_download_list)
        layout.addWidget(self.btn_build_tools_cache)
        layout.addWidget(self.btn_update_tools_cache)
        layout.addWidget(self.btn_update_config_new_tools)
        layout.addWidget(self.btn_download_tools)
        layout.addWidget(self.btn_tools_cleanup)
        layout.addWidget(self.btn_get_tools_version)
        layout.addWidget(self.btn_get_new_and_changed_tools)
        layout.addWidget(QtWidgets.QLabel("version ('latest') or number:"))
        layout.addWidget(self.version_input)
        layout.addWidget(self.btn_get_tools_notes)

        self.setLayout(layout)

        self.core_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.core_mngr.finished_signal.connect(self.finished_job)

        self.asset_mngr.finished_cache_build_signal.connect(self.finished_job)
        self.asset_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.asset_mngr.finished_signal.connect(self.finished_job)
        self.asset_mngr.finished_tracking.connect(self.finished_job)

        self.tools_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.tools_mngr.finished_cache_build_signal.connect(self.finished_job)
        self.tools_mngr.finished_signal.connect(self.finished_job)
        self.tools_mngr.finished_sync_and_download_signal.connect(self.finished_job)

    def show_multithreaded_error(self, error):
        self.tools_mngr.progress_win.close()
        print error

    def finished_job(self, msg):
        print "finito."
        if msg:
            if msg[0] == "audio":
                print self.asset_mngr.shots_with_changed_audio
                print self.asset_mngr.shots_failed_checking_timestamp
                pyani.core.util.open_excel(msg[1])

    def start_post_task_unit_test(self):
        # used to create an html report to show in a QtDialogWindow
        self.asset_report = pyani.core.mngr.ui.core.AniAssetUpdateReport(self)
        # move update window so it doesn't cover the main update window
        this_win_rect = self.frameGeometry()
        post_tasks = [
            {
                'func': self.asset_report.generate_asset_update_report,
                'params': [self.asset_mngr]
            },
            {
                'func': self.asset_report.move,
                'params': [this_win_rect.x() + 150, this_win_rect.y() - 75]
            },
        ]
        test_win = TestTaskListWin()
        test_win.run(post_tasks)

    def start_create_setup_dependencies_unit_test(self):
        self.core_mngr.create_setup_dependencies(setup_dir="C:\\Users\\Patrick\\Downloads\\install\\")

    def start_launcher_unit_test(self):
        self.core_mngr.create_support_launcher()

    def start_create_task_sched_unit_test(self):
        self.core_mngr.create_windows_task_sched()

    def start_desktop_shortcut_unit_test(self):
        self.core_mngr.create_desktop_shortcut()

    def start_customize_nuke_unit_test(self):
        self.core_mngr.customize_nuke()

    def start_seq_list_unit_test(self):
        self.core_mngr.create_sequence_list()

    def start_update_config_unit_test(self):
        self.core_mngr.create_update_config_file()

    def start_build_cache_unit_test(self):
        # look for finished message
        self.asset_mngr.sync_local_cache_with_server()

    def start_download_assets_in_update_config_test(self):
        # for finding assets
        class Found(Exception): pass

        show_and_shot_assets = None

        # load the assets that we want to update - includes tool assets, show assets, and shot assets
        assets_to_update = self.core_mngr.read_update_config()
        if not isinstance(assets_to_update, dict):
            return "Could not load the update configuration file. Error is {0}".format(assets_to_update)

        # all show and shot assets
        potential_assets = {key: value for key, value in assets_to_update.items() if not key == 'tools'}
        # could be empty, make sure there are assets, not just types or components
        try:
            for asset_type in potential_assets:
                for asset_component in potential_assets[asset_type]:
                    if potential_assets[asset_type][asset_component]:
                        # found an asset, so can quit looking, just need one
                        raise Found
        except Found:
            show_and_shot_assets = potential_assets

        if show_and_shot_assets:
            self.asset_mngr.server_download(assets_dict=show_and_shot_assets)

    def start_sync_update_config_assets(self):
        self.asset_mngr.update_config_file_after_sync(debug=True)

    def start_build_tools_cache_unit_test(self):
        self.tools_mngr.sync_local_cache_with_server()

    def start_audio_changed_unit_test(self):
        self.asset_mngr.check_for_new_assets("audio", asset_list="Seq040")

    def start_audio_changed_report_unit_test(self):
        self.asset_mngr.shots_with_changed_audio["Seq050"] = ["Shot010", "Shot030", "Shot160"]
        self.asset_mngr.shots_with_changed_audio["Seq060"] = ["Shot010", "Shot120"]
        self.asset_mngr.shots_failed_checking_timestamp["Seq050"] = {
            "Shot130": "Shot is missing audio. Error is Nonetype doesn't exist"
        }
        print self.asset_mngr._generate_report_for_changed_audio()

    def start_update_tools_cache_unit_test(self):
        """
        Tests updating selected tools. Also ensures sync works when tool no longer is on server
        """
        tools_to_update = {
            'pyanitools': {
                'core': ['help_doc_icons', 'setup', 'update', 'pyAppRoamingLauncher', 'tool_suite_icon']
            }
        }
        # if not visible then no other function called this, so we can show progress window
        if not self.tools_mngr.progress_win.isVisible():
            # reset progress
            self.tools_mngr.init_progress_window("Sync Progress", "Updating tools...")
        # bypass sync_local_cache_with_server because need to give the active type and save method
        self.tools_mngr.server_build_local_cache(
                tools_dict=tools_to_update,
                thread_callback=self.tools_mngr._thread_server_sync_complete,
                thread_callback_args=['Maya Tools', self.tools_mngr.server_save_local_cache]
        )

    def start_update_config_new_tools_unit_test(self):
        """
        Tests update config file syncs properly when new tools added, or removed
        """
        # set up test data:
        # this is the tools cache after sync
        self.tools_mngr.load_server_tool_cache()
        # this is tools cache before sync
        self.tools_mngr._existing_tools_before_sync = \
            pyani.core.util.load_json("C:\\Users\\Patrick\\.PyAniTools\\cgt_tools_cache_orig.json")

        if not isinstance(self.tools_mngr._existing_tools_before_sync, dict):
            print self.tools_mngr._existing_tools_before_sync
            return

        self.tools_mngr.update_config_file_after_sync(debug=True)

    def start_tools_download_unit_test(self):
        self.tools_mngr.server_download()

    def save_tools_to_dl(self):
        error = self.tools_mngr.server_download(debug=True)
        if error:
            print error
        else:
            print "Wrote tool list to desktop."

    def get_all_new_and_changed_assets(self):
        """
        generates the report for tools and assets
        """
        # see C:\Users\Patrick\PycharmProjects\PyAniTools\Test_Files\Mngr_Tests\README.txt for tests
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\tools_timestamps_from_server.json", "r") as read_file:
            self.tools_mngr._tools_timestamp_before_dl = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_tools_cache_after.json", "r") as read_file:
            self.tools_mngr._tools_info = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_tools_cache_before.json", "r") as read_file:
            self.tools_mngr._existing_tools_before_sync = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\assets_timestamps_from_server.json", "r") as read_file:
            self.asset_mngr._assets_timestamp_before_dl = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_asset_info_cache_after.json", "r") as read_file:
            self.asset_mngr._asset_info = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_asset_info_cache_before.json", "r") as read_file:
            self.asset_mngr._existing_assets_before_sync = json.load(read_file)
        self.ui_mngr.generate_asset_update_report(self.asset_mngr, self.tools_mngr)

    def get_new_and_changed_tools(self):
        # see C:\Users\Patrick\PycharmProjects\PyAniTools\Test_Files\Mngr_Tests\README.txt for tests
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\tools_timestamps_from_server.json", "r") as read_file:
            self.tools_mngr._tools_timestamp_before_dl = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_tools_cache_after.json", "r") as read_file:
            self.tools_mngr._tools_info = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_tools_cache_before.json", "r") as read_file:
            self.tools_mngr._existing_tools_before_sync = json.load(read_file)
        self.ui_mngr.generate_asset_update_report(tools_mngr=self.tools_mngr)

    def get_new_and_changed_assets(self):
        # see C:\Users\Patrick\PycharmProjects\PyAniTools\Test_Files\Mngr_Tests\README.txt for tests
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\assets_timestamps_from_server.json", "r") as read_file:
            self.asset_mngr._assets_timestamp_before_dl = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_asset_info_cache_after.json", "r") as read_file:
            self.asset_mngr._asset_info = json.load(read_file)
        with open("C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\Test_Files\\Mngr_Tests\\cgt_asset_info_cache_before.json", "r") as read_file:
            self.asset_mngr._existing_assets_before_sync = json.load(read_file)
        self.ui_mngr.generate_asset_update_report(asset_mngr=self.asset_mngr)

    def start_tools_cleanup(self):
        print self.tools_mngr.remove_files_not_on_server(debug=True)

    def show_tool_data(self):
        self.tools_mngr.load_server_tool_cache()
        print json.dumps(self.tools_mngr._tools_info, indent=4)

    def get_tools_version(self):
        print "VERSION:\n"
        print self.tools_mngr.get_tool_newest_version("maya", "scripts", "rig_picker")

    def get_tools_notes(self):
        version = str(self.version_input.text())
        if version:
            notes = self.tools_mngr.get_tool_release_notes("maya", "scripts", "rig_picker", version=version)
        else:
            notes = self.tools_mngr.get_tool_release_notes("maya", "scripts", "rig_picker")
        print "NOTES:\n"
        print '\n'.join(notes)

    def start_update_version_after_dl_unit_test(self):
        # to verify works look for meta data file on disk in asset folder
        cgt_path = "/LongGong/assets/char/charAnglerFish/rig/approved/charAnglerFish_rig_high.mb"
        local_path  = r"Z:\LongGong\assets\char\charAnglerFish\rig\approved"
        self.asset_mngr.update_local_version(cgt_path, local_path)


def main():

    # create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    window = TestWindow()

    # setup stylesheet - note that in pyani.core.ui has some color overrides used by QFrame, and QButtons
    app.setStyleSheet(qdarkstyle.load_stylesheet_from_environment())

    # run
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()