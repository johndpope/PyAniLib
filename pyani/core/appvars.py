import os
import json
import tempfile
import pyani.core.anivars


class AppVars:
    """
    Variables used by app management - updating and installation

    To see a list of App Vars:
    print AppVars_instance
    """
    def __init__(self):
        self.ani_vars = pyani.core.anivars.AniVars()
        # the directory where the unzipped files are for installation
        self.tools_package = "PyAniToolsPackage.zip"
        # to debug, unzip to downloads folder and set this to "C:\\Users\\Patrick\\Downloads\\PyANiToolsPackage"
        self.setup_dir = ""
        self.setup_app_data_path = os.path.join(self.setup_dir, "PyAniTools\\app_data")
        self.setup_packages_path = os.path.join(self.setup_dir, "PyAniTools\\packages")
        self.setup_installed_path = os.path.join(self.setup_dir, "PyAniTools\\installed")
        self.setup_apps_shortcut_dir = os.path.join(self.setup_dir, "PyAniTools\\installed\\shortcuts")
        self.setup_nuke_scripts_path = os.path.join(self.setup_dir, "PyAniTools\\install_scripts\\")
        # directory where installed files go
        self.tools_dir = "C:\\PyAniTools"
        self.app_data_dir = self.tools_dir + "\\app_data"
        self.packages_dir = self.tools_dir + "\\packages"
        self.apps_dir = self.tools_dir + "\\installed"
        self.setup_exe = "PyAniToolsSetup.exe"
        self.update_exe = "PyAniToolsUpdate.exe"
        self.update_path = os.path.join(self.apps_dir, self.update_exe)
        self.iu_assist_exe = "PyAniToolsIUAssist.exe"
        self.iu_assist_path = os.path.join(self.apps_dir, self.iu_assist_exe)
        self.apps_shortcut_dir = self.apps_dir + "\\shortcuts"
        self.install_scripts_dir = self.tools_dir + "\\install_scripts"
        self.app_mngr_path = os.path.join(self.apps_dir, "PyAppMngr")
        self.app_mngr_exe = os.path.join(self.app_mngr_path, "PyAppMngr.exe")
        self.app_mngr_shortcut = os.path.normpath("C:\PyAniTools\installed\shortcuts\PyAppMngr.lnk")
        # shortcut link on desktop
        homepath = os.path.join("C:", os.environ["HOMEPATH"])
        self.user_desktop = os.path.join(homepath, "Desktop")
        self.tools_shortcuts = os.path.join(self.user_desktop, "PyAniTools.lnk")
        # the code to add to init.py
        self.custom_plugin_path = "nuke.pluginAddPath(\"C:\\PyAniTools\\lib\")"
        # path to .nuke/init.py
        self.nuke_init_file_path = os.path.join(self.ani_vars.nuke_user_dir, "init.py")

        # cgt paths
        # TODO : remove ->
        self._cgt_download_path = "Z:\\LongGong\\common\\tools"

        self.cgt_tools_online_path = "/LongGong/tools/"
        self.download_path_cgt = os.path.join(os.path.normpath(tempfile.gettempdir()), "CGT")
        self.cgt_path_pyanitools = os.path.join(self.cgt_tools_online_path, self.tools_package)

        # download vars
        self.client_install_data_json = os.path.join(self.app_data_dir, "Shared\\install_data.json")
        self.sequence_list_json = os.path.join(self.app_data_dir, "Shared\\sequences.json")
        self.server_update_json_name = "last_update.json"
        self.server_update_json_path = os.path.join(self.cgt_tools_online_path, self.server_update_json_name)
        self.server_update_json_download_path = os.path.join(self.download_path_cgt, self.server_update_json_name)
        self.download_path_pyanitools = os.path.join(os.path.normpath(tempfile.gettempdir()), "PyAniTools")

    # produce better output
    def __str__(self):
        return json.dumps(vars(self), indent=4)

    def __repr__(self):
        return '<pyani.core.appvars.AppVars>'

    def update_setup_dir(self, new_setup_dir):
        """
        Updates member variables to point to a ne setup directory than the one set during init
        :param new_setup_dir: file path to location of unzipped tool files
        """
        self.setup_dir = new_setup_dir
        self.setup_app_data_path = os.path.join(self.setup_dir, "PyAniTools\\app_data")
        self.setup_packages_path = os.path.join(self.setup_dir, "PyAniTools\\packages")
        self.setup_installed_path = os.path.join(self.setup_dir, "PyAniTools\\installed")
        self.setup_apps_shortcut_dir = os.path.join(self.setup_dir, "PyAniTools\\installed\\shortcuts")
        self.setup_nuke_scripts_path = os.path.join(self.setup_dir, "PyAniTools\\install_scripts\\")