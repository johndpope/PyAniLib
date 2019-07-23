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
        # notes formats supported
        self.notes_format_supported = ["txt", "json"]
        # the directory where the unzipped files are for installation
        self.tools_package = "PyAniToolsPackage.zip"
        # to debug, unzip to downloads folder and set this to "C:\\Users\\Patrick\\Downloads\\PyAniToolsPackage"
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
        self.tools_list = self.app_data_dir + "\\Shared\\app_list.json"
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
        # users path i.e. C:\Users\{username}\
        homepath = os.path.join("C:", os.environ["HOMEPATH"])
        # user desktop
        self.user_desktop = os.path.join(homepath, "Desktop")
        # the code to add to init.py
        self.custom_plugin_path = "nuke.pluginAddPath(\"C:\\PyAniTools\\lib\")"
        # path to .nuke/init.py
        self.nuke_init_file_path = os.path.join(self.ani_vars.nuke_user_dir, "init.py")
        # permanent directory path
        self.persistent_data_path = "{0}\\.PyAniTools".format(homepath)
        # base temp dir
        self.local_temp_dir = os.path.normpath(tempfile.gettempdir())

        # this holds the seq and shot set in PySession app
        self.session_file = os.path.join(self.persistent_data_path, "session_env.json")

        # confluence / wiki page
        self.wiki_user = "Patrick"
        self.wiki_pass = "evan0510"

        # tools general
        self.cgt_tools_cache_path = "{0}\\cgt_tools_cache.json".format(self.persistent_data_path)
        self.tool_ignore_list = ["json", "txt"]
        self.tools_temp_dir = os.path.join(self.local_temp_dir, "pyanitools")

        # cgt cloud
        self.cgt_metadata_filename = "cgt_metadata.json"
        self.cgt_tools_online_path = "/LongGong/tools/"
        self.cgt_pyanitools_app_dir = "/LongGong/tools/pyanitools/apps"
        self.cgt_pyanitools_lib_dir = "/LongGong/tools/pyanitools/lib"
        self.cgt_pyanitools_core_dir = "/LongGong/tools/pyanitools/core"
        self.cgt_pyanitools_shortcuts_dir = "/LongGong/tools/pyanitools/shortcuts"
        self.cgt_maya_script_dir = "/LongGong/tools/maya/scripts"
        self.cgt_maya_plugins_dir = "/LongGong/tools/maya/plugins"

        self.cgt_download_path = os.path.join(self.local_temp_dir, "CGT")
        self.cgt_path_pyanitools = os.path.join(self.cgt_tools_online_path, self.tools_package)
        # TODO: os.path.normpath("C:\PyAniTools\lib\app_bridge")
        self.cgt_bridge_api_path = os.path.normpath(
            "C:\\Users\\Patrick\\PycharmProjects\\PyAniTools\\PyAniToolsAppBridge\\venv")
        self.cgt_user = "Patrick"
        self.cgt_pass = "longgong19"
        self.cgt_ip = "172.18.100.246"

        # pyanitools
        self.local_pyanitools_apps_dir = self.tools_dir + "\\apps"
        self.local_pyanitools_lib_dir = self.tools_dir + "\\lib"
        self.local_pyanitools_core_dir = self.tools_dir + "\\core"
        self.local_pyanitools_shortcuts_dir = self.tools_dir + "\\shortcuts"
        self.pyanitools_support_launcher_name = "pyAppRoamingLauncher.exe"
        self.pyanitools_support_launcher_path = os.path.join(
            self.persistent_data_path, self.pyanitools_support_launcher_name
        )
        self.pyanitools_update_app_name = "update.exe"
        self.pyanitools_setup_app_name = "setup.exe"
        self.pyanitools_desktop_shortcut_name = "PyAniTools.lnk"
        self.pyanitools_desktop_shortcut_path = os.path.join(self.user_desktop, self.pyanitools_desktop_shortcut_name)

        # maya tools
        # json file name to find the plugin version, this file will be in the plugins directory
        self.maya_tools_vers_json_name = "plugin_version.json"  # todo remove
        self.maya_tools_restore_dir = "restore"  # todo remove

        self.maya_scripts_local_dir = "Z:\\LongGong\\tools\\maya\\scripts"
        self.maya_plugins_local_dir = "Z:\\LongGong\\tools\\maya\\plugins"

        # tool types, add additional types and tools mngr will find
        self.tool_types = {
            "maya": {
                "scripts": {
                    "cgt cloud dir": self.cgt_maya_script_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_maya_script_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "maya_scripts"),
                    "local dir": self.maya_scripts_local_dir
                },
                "plugins": {
                    "cgt cloud dir": self.cgt_maya_plugins_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_maya_plugins_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "maya_plugins"),
                    "local dir": self.maya_plugins_local_dir
                }
            },
            "pyanitools": {
                "apps": {
                    "cgt cloud dir": self.cgt_pyanitools_app_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_pyanitools_app_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "pyanitools_apps"),
                    "local dir": self.local_pyanitools_apps_dir
                },
                "lib": {
                    "cgt cloud dir": self.cgt_pyanitools_lib_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_pyanitools_lib_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "pyanitools_lib"),
                    "local dir": self.local_pyanitools_lib_dir
                },
                "core": {
                    "cgt cloud dir": self.cgt_pyanitools_core_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_pyanitools_core_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "pyanitools_core"),
                    "local dir": self.local_pyanitools_core_dir
                },
                "shortcuts": {
                    "cgt cloud dir": self.cgt_pyanitools_shortcuts_dir,
                    "cgt cloud metadata path": "{0}/{1}".format(
                        self.cgt_pyanitools_shortcuts_dir, self.cgt_metadata_filename
                    ),
                    "local temp path": os.path.join(self.tools_temp_dir, "pyanitools_shortcuts"),
                    "local dir": self.local_pyanitools_shortcuts_dir
                }
            }
        }
        # these are user friendly names for tools, since constructed differently and requires refactor to add
        # names to tool_types above
        self.tool_types_display_names = {
            "maya": "Maya Tools",
            "pyanitools": "PyAniTools"
        }

        # download vars
        self.client_install_data_json = os.path.join(self.app_data_dir, "Shared\\install_data.json")
        self.sequence_list_json = os.path.join(self.persistent_data_path, "sequences.json")
        self.server_update_json_name = "last_update.json"
        self.server_update_json_path = os.path.join(self.cgt_tools_online_path, self.server_update_json_name)
        self.server_update_json_download_path = os.path.join(self.cgt_download_path, self.server_update_json_name)
        self.download_path_pyanitools = os.path.join(os.path.normpath(tempfile.gettempdir()), "PyAniTools")

        # asset management vars -
        # asset types are the supported show and shot assets. The first key is the asset type, which is unique, and then
        # the component, which is not unique and may belong to multiple asset types.
        # the remaining info is meta data to help manage asset updating. name is the user friendly name of the
        # asset component. root path is the path up to the assets
        self.asset_types = {
            "char": {
                "rig": {
                    "name": "Rigs",
                    "root path": "/LongGong/assets/char",
                    "is publishable": True,
                    "is versioned": True,
                    "supports notes": True
                }
            },
            "prop": {
                "rig": {
                    "name": "Rigs",
                    "root path": "/LongGong/assets/prop",
                    "is publishable": True,
                    "is versioned": True,
                    "supports notes": True
                }
            },
            "set": {
                "rig": {
                    "name": "Rigs",
                    "root path": "/LongGong/assets/set",
                    "is publishable": True,
                    "is versioned": True,
                    "supports notes": True
                },
                "model/cache": {
                    "name": "GPU Cache",
                    "root path": "/LongGong/assets/set",
                    "is publishable": False,
                    "is versioned": False,
                    "supports notes": False
                }
            },
            "shot": {
                "audio": {
                    "name": "Audio",
                    "root path": "/LongGong/sequences",
                    "is publishable": True,
                    "is versioned": False,
                    "supports notes": False
                }
            }
        }
        # cgt asset info cache
        self.cgt_asset_info_cache_path = "{0}\\cgt_asset_info_cache.json".format(self.persistent_data_path)
        # update config file used during updating to determine assets to update
        self.update_config_file = "{0}\\update_config.json".format(self.persistent_data_path)

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