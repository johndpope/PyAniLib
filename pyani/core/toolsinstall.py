"""
script to install the PyAniTools - copies from Z drive (downloaded via cg teamworks) to c: drive

Dependencies

    Python packages
    ----------
        pyanilib - custom library

Making Executable - Pyinstaller

    pyinstaller --onefile "C:\Users\Patrick\PycharmProjects\PyAniLib\pyani\core\toolsinstall.py" --icon "C:\Users\Patrick\PycharmProjects\PyAniTools\Resources\setup.ico" --name "C:\Users\Patrick\PycharmProjects\PyAniTools\Dist\PyAniToolsSetup"
"""

import pyani.core.util
import colorama
import os
import shutil


def main():

    tools_dir = "C:\\PyAniTools"
    app_data_dir = tools_dir + "\\app_data"
    packages_dir = tools_dir + "\\packages"
    apps_dir = tools_dir + "\\installed"

    # init the colored output to terminal
    colorama.init()

    msg = "Starting install"
    print ("{0}{1}".format(colorama.Fore.GREEN, msg))
    print(colorama.Style.RESET_ALL)

    # setup the tools directory - run first install only
    if not os.path.exists(tools_dir):
        pyani.core.util.make_dir(tools_dir)

    # setup app_data - always update this
    if os.path.exists(app_data_dir):
        shutil.rmtree(app_data_dir)
    # update app data
    shutil.move("PyAniTools\\app_data", app_data_dir)

    # setup packages dir - always update this
    if os.path.exists(packages_dir):
        shutil.rmtree(packages_dir)
    # update packages
    shutil.move("PyAniTools\\packages", packages_dir)

    # setup apps directory
    if not os.path.exists(apps_dir):
        shutil.move("PyAniTools\\installed", apps_dir)
        # copy folder shortcut
        user_desktop = os.path.join(os.environ["HOMEPATH"], "Desktop")
        if not os.path.exists(os.path.join(user_desktop, "PyAniTools.lnk")):
            shutil.move(apps_dir + "\\PyAniTools.lnk", user_desktop)
    else:
        # just update app mngr
        os.remove(os.path.join(apps_dir, "PyAppMngr.exe"))
        shutil.move("PyAniTools\\installed\\PyAppMngr.exe", apps_dir)

    print ("{0}{1}".format(colorama.Fore.GREEN, "Successfully installed"))
    print(colorama.Style.RESET_ALL)


if __name__ == '__main__':
    main()
