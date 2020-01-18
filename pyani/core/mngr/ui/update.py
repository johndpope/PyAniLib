import os
import logging
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core
import pyani.core.ui

logger = logging.getLogger()


class AniUpdateGui(pyani.core.mngr.ui.core.AniTaskListWindow):
    """
    Updates cgt cache, tools and assets
    """

    def __init__(self, error_logging, progress_list):

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()

        self.tool_assets = None
        self.show_and_shot_assets = None

        error = self.load_tracked_assets()

        description = (
            "<span style='font-size: 9pt; font-family:{0}; color: #ffffff;'>"
            "About the pyAniTools asset management system: Setup creates configuration files, builds caches that help "
            "speed up CGT connectivity, downloads tools, and sets up a user's system to work with the pyAniTools "
            "update system. The update system allows assets such as tools, rigs, and more to be auto updated daily. "
            "A gui interface, called Asset Manager, provides a user interface to the asset management system."
            "</span>".format(
                pyani.core.ui.FONT_FAMILY
            )
        )

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
                'desc': "Updated local tools cache."
            },
            # rebuild asset cache
            {
                'func': self.asset_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.asset_mngr.finished_cache_build_signal,
                'error signal': self.asset_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Updated local asset cache."
            },
            # update sequence list
            {
                'func': self.core_mngr.create_sequence_list,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "List of sequences and their shots updated."
            },
            # update desktop shortcut
            {
                'func': self.core_mngr.create_desktop_shortcut,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Updated desktop shortcut for pyAniTool applications."
            },
            # create nuke custom plugin path
            {
                'func': self.core_mngr.customize_nuke,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Updated custom menu and plugins to Nuke."
            }
        ]

        # if tools present in update config file, download tool assets
        if self.tool_assets:
            self.task_list.append(
                {
                    'func': self.tools_mngr.server_download,
                    'params': [self.tool_assets],
                    'finish signal': self.tools_mngr.finished_signal,
                    'error signal': self.tools_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Updated show tools."
                }
            )
            progress_list.append("Checking for tool updates")

            # copy launcher
            self.task_list.append(
                {
                    'func': self.core_mngr.create_support_launcher,
                    'params': [],
                    'finish signal': self.core_mngr.finished_signal,
                    'error signal': self.core_mngr.error_thread_signal,
                    'thread task': True,
                    'desc': "Updated the support launcher."
                }
            )
            progress_list.append("Checking for support launcher updates.")

        # if show or shot assets present in update config file, download
        if self.show_and_shot_assets:
            self.task_list.append(
                {
                    'func': self.asset_mngr.server_download,
                    'params': [self.show_and_shot_assets],
                    'finish signal': self.asset_mngr.finished_signal,
                    'error signal': self.asset_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Updated show and shot assets tracked in the update config file."
                }
            )
            progress_list.append("Checking for asset updates")

        # add update config sync step for assets
        self.task_list.append(
            {
                'func': self.asset_mngr.update_config_file_after_sync,
                'params': [],
                'finish signal': self.asset_mngr.finished_signal,
                'error signal': self.asset_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Checking update config file for old assets."
            }
        )
        progress_list.append("Syncing update config file with assets on server.")

        # add update config sync for tools
        self.task_list.append(
            {
                'func': self.tools_mngr.update_config_file_after_sync,
                'params': [],
                'finish signal': self.tools_mngr.finished_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Checking update config file for old tools or missing new tools."
            }
        )
        progress_list.append("Syncing update config file with tools on server.")

        # add asset tracking step for audio
        if self.asset_mngr.get_preference("asset mngr", "audio", "track updates")['track updates']:
            self.task_list.append(
                {
                    'func': self.asset_mngr.check_for_new_assets,
                    'params': ["audio"],
                    'finish signal': self.asset_mngr.finished_tracking,
                    'error signal': self.asset_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Checked for any new audio and saved report in {0}.".format(
                        self.asset_mngr.app_vars.audio_excel_report_dir
                    )
                }
            )
            progress_list.append("Checking all show audio for changes.")

        # add cleanup step
        self.task_list.append(
            {
                'func': self.tools_mngr.remove_files_not_on_server,
                'params': [],
                'finish signal': self.tools_mngr.finished_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Removed out-dated tools."
            }
        )
        progress_list.append("Removing any out-of-date tools.")

        # information about the app
        app_metadata = {
            "name": "update",
            "dir": self.core_mngr.app_vars.local_pyanitools_core_dir,
            "type": "pyanitools",
            "category": "core"
        }

        # create a ui (non-interactive) to run setup
        super(AniUpdateGui, self).__init__(
            error_logging,
            progress_list,
            "Update",
            app_metadata,
            self.task_list,
            app_description=description,
            asset_mngr=self.asset_mngr,
            tools_mngr=self.tools_mngr
        )

        # NOTE: do this here because the super needs to be called first to create the window
        # used to create an html report to show in a QtDialogWindow
        self.asset_report = pyani.core.mngr.ui.core.AniAssetUpdateReport(self)
        # move update window so it doesn't cover the main update window
        this_win_rect = self.frameGeometry()
        post_tasks = [
            {
                'func': self.asset_report.generate_asset_update_report,
                'params': [self.asset_mngr, self.tools_mngr]
            },
            {
                'func': self.asset_report.move,
                'params': [this_win_rect.x() + 150, this_win_rect.y() - 75]
            },
        ]
        self.set_post_tasks(post_tasks)

        if self.tool_assets is None:
            self.msg_win.show_warning_msg("Update Warning",
                                          "Warning: No tools will be updated. All tools are missing from the update "
                                          "configuration file.")
        if error:
            self.msg_win.show_warning_msg("Update Warning",
                                          "Could not load update configuration file. Error is {0}".format(error))

    def run(self):
        """
        Starts the update process
        """
        self.start_task_list()

    def load_tracked_assets(self):
        """
        Loads assets in the update config, checks for empty asset lists
        :return:
        """
        # for finding assets
        class Found(Exception): pass

        # load the assets that we want to update - includes tool assets, show assets, and shot assets
        assets_to_update = self.core_mngr.read_update_config()
        if not isinstance(assets_to_update, dict):
            return "Could not load the update configuration file. Error is {0}".format(assets_to_update)

        # get tools to update
        if 'tools' in assets_to_update:
            potential_assets = assets_to_update['tools']
            # could be empty, make sure there are assets, not just types or categories
            try:
                for asset_type in potential_assets:
                    for asset_component in potential_assets[asset_type]:
                        if potential_assets[asset_type][asset_component]:
                            # found an asset, so can quit looking, just need one
                            raise Found
            except Found:
                self.tool_assets = potential_assets
            # in case no assets, these would be thrown
            except (KeyError, TypeError):
                pass

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
            self.show_and_shot_assets = potential_assets
        # in case no assets, these would be thrown
        except (KeyError, TypeError):
            pass

        return None

