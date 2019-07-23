import os
import sys
import json
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets


class TestWindow(QtWidgets.QDialog):
    def __init__(self):
        super(TestWindow, self).__init__()
        self.setWindowTitle("Unit Tests For Updating Tools and Assets")

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
        '''
        -----------------------------------------------------------------------------------------------------------
        '''

        self.btn_show_tools_cache = QtWidgets.QPushButton("show tools cache unit test")
        self.btn_show_tools_cache.pressed.connect(self.show_tool_data)

        self.btn_build_tools_cache = QtWidgets.QPushButton("start tools cache build unit test")
        self.btn_build_tools_cache.pressed.connect(self.start_build_tools_cache_unit_test)

        self.btn_download_tools = QtWidgets.QPushButton("start tools download unit test")
        self.btn_download_tools.pressed.connect(self.start_tools_download_unit_test)

        self.btn_tools_cleanup = QtWidgets.QPushButton("start tools cleanup unit test")
        self.btn_tools_cleanup.pressed.connect(self.start_tools_cleanup)

        self.btn_get_tools_version = QtWidgets.QPushButton("get newest version")
        self.btn_get_tools_version.pressed.connect(self.get_tools_version)

        self.btn_get_tools_notes = QtWidgets.QPushButton("get notes")
        self.btn_get_tools_notes.pressed.connect(self.get_tools_notes)

        self.version_input = QtWidgets.QLineEdit()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("<b>Setup/Update Unit Tests</b>"))
        layout.addWidget(self.btn_create_setup_dependencies_unit_test)
        layout.addWidget(self.btn_create_update_config_unit_test)
        layout.addWidget(self.btn_create_seq_list_unit_test)
        layout.addWidget(self.btn_create_launcher_unit_test)
        layout.addWidget(self.btn_create_desktop_shortcut_unit_test)
        layout.addWidget(self.btn_create_customize_nuke_unit_test)
        layout.addWidget(self.btn_create_task_sched_unit_test)

        layout.addWidget(QtWidgets.QLabel("<b>Asset Unit Tests</b>"))
        layout.addWidget(self.btn_build_cache_unit_test)
        layout.addWidget(self.btn_update_version_after_dl_unit_test)

        layout.addWidget(QtWidgets.QLabel("<b>Tools Unit Tests</b>"))
        layout.addWidget(self.btn_show_tools_cache)
        layout.addWidget(self.btn_build_tools_cache)
        layout.addWidget(self.btn_download_tools)
        layout.addWidget(self.btn_tools_cleanup)
        layout.addWidget(self.btn_get_tools_version)
        layout.addWidget(QtWidgets.QLabel("version ('latest') or number:"))
        layout.addWidget(self.version_input)
        layout.addWidget(self.btn_get_tools_notes)

        self.setLayout(layout)

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.core_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.core_mngr.finished_signal.connect(self.finished_building)

        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()
        self.asset_mngr.finished_cache_build_signal.connect(self.finished_building)

        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        self.tools_mngr.error_thread_signal.connect(self.show_multithreaded_error)
        self.tools_mngr.finished_cache_build_signal.connect(self.finished_building)
        self.tools_mngr.finished_signal.connect(self.finished_building)

    def show_multithreaded_error(self, error):
        self.tools_mngr.progress_win.close()
        print error

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

    def start_build_tools_cache_unit_test(self):
        self.tools_mngr.sync_local_cache_with_server()

    def start_tools_download_unit_test(self):
        self.tools_mngr.server_download_no_sync()

    def start_tools_cleanup(self):
        print self.tools_mngr.remove_files_not_on_server(debug=True)

    def show_tool_data(self):
        self.tools_mngr.load_local_tool_cache_data()
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

    def finished_building(self):
        print "finito."


def main():

    # create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    window = TestWindow()

    # run
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()