"""
script to install the PyAniTools

v 1.0.0

pyinstaller --onefile --name PyAniToolsSetup pyani\\core\\toolsinstall.py
"""

from pyani.core.appmanager import AppManager
import pyani.core.util
import colorama
import os


def main():

    # setup the tools directory
    tools_dir = "C:\\PyAniTools\\"
    if not os.path.exists(tools_dir):
        pyani.core.util.make_dir(tools_dir)

    # init the colored output to terminal
    colorama.init()

    # app properties
    app_update_script = None
    app_name = "PyAniInstall"
    app_dl_path = "Z:\\LongGong\\PyAniTools\\PyAniTools.zip"
    app_install_path = "C:\\PyAniTools\\"
    app_dist_path = "Z:\\LongGong\\PyAniTools\\dist\\"
    app_data_path = "Z:\\LongGong\\PyAniTools\\app_data\\"
    app_manager = AppManager(app_update_script, app_name, app_dl_path, app_install_path, app_dist_path, app_data_path)

    msg = "Starting install {0}.".format(app_manager.app_name)
    print ("{0}{1}".format(colorama.Fore.GREEN, msg))
    print(colorama.Style.RESET_ALL)

    error = app_manager.verify_paths()

    if error:
        print error

    error = app_manager.install()
    if error:
        print ("{0}{1}".format(colorama.Fore.RED, error))
        print(colorama.Style.RESET_ALL)
    else:
        msg = "Successfully installed {0}.".format(app_manager.app_name)
        print ("{0}{1}".format(colorama.Fore.GREEN, msg))
        print(colorama.Style.RESET_ALL)


if __name__ == '__main__':
    main()
