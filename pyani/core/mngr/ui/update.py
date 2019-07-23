import os
import logging
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core


logger = logging.getLogger()


class AniUpdateGui(pyani.core.mngr.ui.core.AniTaskListWindow):

    def __init__(self, error_logging, progress_list):

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()

        self.tool_assets = None
        self.show_and_shot_assets = None

        error = self.load_tracked_assets()

        # list of tasks to run, see pyani.core.mngr.ui.core.AniTaskListWindow for format
        # build tool cache first, since tools download will access
        self.task_list = [
            # rebuild tools cache
            {
                'func': self.tools_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.tools_mngr.finished_cache_build_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local tools cache."
            },
            # rebuild asset cache
            {
                'func': self.asset_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.asset_mngr.finished_cache_build_signal,
                'error signal': self.asset_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local asset cache."
            },
            # update sequence list
            {
                'func': self.core_mngr.create_sequence_list,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "List of sequences and their shots created."
            },
            # update desktop shortcut
            {
                'func': self.core_mngr.create_desktop_shortcut,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Created desktop shortcut for pyAniTool applications."
            },
            # create nuke custom plugin path
            {
                'func': self.core_mngr.customize_nuke,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Added custom menu and plugins to Nuke."
            }
        ]

        # if tools present in update config file, download tool assets
        if self.tool_assets:
            self.task_list.append(
                {
                    'func': self.tools_mngr.server_download_no_sync,
                    'params': [self.tool_assets],
                    'finish signal': self.tools_mngr.finished_signal,
                    'error signal': self.tools_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Updated show tools."
                }
            )
            progress_list.append("Checking for tool updates")

        # if show or shot assets present in update config file, download
        if self.show_and_shot_assets:
            self.task_list.append(
                {
                    'func': self.asset_mngr.server_download_no_sync,
                    'params': [self.show_and_shot_assets],
                    'finish signal': self.asset_mngr.finished_signal,
                    'error signal': self.asset_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Updated show and shot assets tracked in the update config file."
                }
            )
            progress_list.append("Checking for asset updates")

        # create a ui (non-interactive) to run setup
        super(AniUpdateGui, self).__init__(
            error_logging,
            progress_list,
            "Update",
            "Update",
            self.task_list
        )

        if self.tool_assets is None:
            self.msg_win.show_warning_msg("Update Warning",
                                          "Warning: No tools will be updated. All tools are missing from the update "
                                          "configuration file.")
        if error:
            self.msg_win.show_warning_msg("Update Warning",
                                          "Could not load update configuration file. Error is {0}".format(error))

    def run(self):
        self.start_task_list()

    def load_tracked_assets(self):
        # load the assets that we want to update - includes tool assets, show assets, and shot assets
        assets_to_update = self.core_mngr.read_update_config()
        if not isinstance(assets_to_update, dict):
            return "Could not load the update configuration file. Error is {0}".format(assets_to_update)

        # get tools to update
        if 'tools' in assets_to_update:
            self.tool_assets = assets_to_update['tools']

        # all show and shot assets
        self.show_and_shot_assets = {key: value for key, value in assets_to_update.items() if not key == 'tools'}

        return None

