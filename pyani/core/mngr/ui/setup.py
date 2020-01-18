import os
import logging
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core


logger = logging.getLogger()


class AniSetupGui(pyani.core.mngr.ui.core.AniTaskListWindow):

    def __init__(self, error_logging, progress_list):

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()
        self.asset_mngr = pyani.core.mngr.assets.AniAssetMngr()

        # list of tasks to run, see pyani.core.mngr.ui.core.AniTaskListWindow for format
        # build tool cache first, since tools download will access
        self.task_list = [
            # setup dependencies
            {
                'func': self.core_mngr.create_setup_dependencies,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Installs any dependencies needed for setup"
            },
            # create sequence list
            {
                'func': self.core_mngr.create_sequence_list,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "List of sequences and their shots created."
            },
            # make asset cache
            {
                'func': self.asset_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.asset_mngr.finished_cache_build_signal,
                'error signal': self.asset_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local asset cache."
            },
            # make tools cache
            {
                'func': self.tools_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.tools_mngr.finished_cache_build_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local tools cache."
            },
            # download tools - pyani and maya
            {
                'func': self.tools_mngr.server_download,
                'params': [],
                'finish signal': self.tools_mngr.finished_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Downloaded and installed show tools."
            },
            # create auto-update config
            {
                'func': self.core_mngr.create_update_config_file,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Configuration file for auto-updates is now setup."
            },
            # copy launcher
            {
                'func': self.core_mngr.create_support_launcher,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Created the support launcher for updates."
            },
            # copy desktop shortcut
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
            },
            # create windows task in scheduler
            {
                'func': self.core_mngr.create_windows_task_sched,
                'params': [],
                'finish signal': self.core_mngr.finished_signal,
                'error signal': self.core_mngr.error_thread_signal,
                'thread task': True,
                'desc': "Add daily task to run and update tools and show / shot assets."
            }
        ]

        # information about the app
        app_metadata = {
            "name": "setup",
            "dir": self.core_mngr.app_vars.local_pyanitools_core_dir,
            "type": "pyanitools",
            "category": "core"
        }

        # create a ui (non-interactive) to run setup
        super(AniSetupGui, self).__init__(
            error_logging,
            progress_list,
            "Setup",
            app_metadata,
            self.task_list
        )



    def run(self):
        self.start_task_list()
