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

def main():

    tools_dir = "C:\\PyAniTools"
    app_data_dir = tools_dir + "\\app_data"
    packages_dir = tools_dir + "\\packages"
    apps_dir = tools_dir + "\\installed"
    install_scripts_dir = tools_dir + "\\install_scripts"
    ani_vars = pyani.core.util.AniVars()

    # init the colored output to terminal
    colorama.init()

    msg = "Starting install"
    print ("{0}{1}".format(colorama.Fore.GREEN, msg))
    print(colorama.Style.RESET_ALL)

    # set color to red, only errors printed below
    print ("{0}".format(colorama.Fore.RED))

    # setup the tools directory - run first install only
    if not os.path.exists(tools_dir):
        error = pyani.core.util.make_dir(tools_dir)
        if error:
            print error

    # setup app_data - always update this
    if os.path.exists(app_data_dir):
        error = pyani.core.util.rm_dir(app_data_dir)
        if error:
            print error

    # update app data
    error = pyani.core.util.move_file("PyAniTools\\app_data", app_data_dir)
    if error:
        print error

    # setup packages dir - always update this
    if os.path.exists(packages_dir):
        error = pyani.core.util.rm_dir(packages_dir)
        if error:
            print error

    # update packages
    error = pyani.core.util.move_file("PyAniTools\\packages", packages_dir)
    if error:
        print error

    # setup apps directory
    if not os.path.exists(apps_dir):
        error = pyani.core.util.move_file("PyAniTools\\installed", apps_dir)
        if error:
            print error
        # copy folder shortcut
        user_desktop = os.path.join(os.environ["HOMEPATH"], "Desktop")
        if not os.path.exists(os.path.join(user_desktop, "PyAniTools.lnk")):
            error = pyani.core.util.move_file(apps_dir + "\\PyAniTools.lnk", user_desktop)
            if error:
                print error
    else:
        # just update app mngr
        error = pyani.core.util.delete_file(os.path.join(apps_dir, "PyAppMngr.exe"))
        if error:
            print error
        error = pyani.core.util.move_file("PyAniTools\\installed\\PyAppMngr.exe", apps_dir)
        if error:
            print error

    # setup nuke copying init.py, menu.py, and session.py to c:\users\{user_name}\.nuke\pyanitools\ (create
    # directory if doesn't exist). checks if nuke is installed by looking for .nuke in the user dir, since all
    # nuke installs create this.
    if os.path.exists(ani_vars.nuke_user_dir):
        # if the custom dir doesn't exist, add it and append init.py with the custom nuke path
        if not os.path.exists(ani_vars.nuke_custom_dir):
            error = pyani.core.util.make_dir(ani_vars.nuke_custom_dir)
            if error:
                print error
            # update the init.py - only append, don't want to lose existing code added by user
            try:
                file_path = os.path.join(ani_vars.nuke_user_dir, "init.py")
                with open(file_path, "a+") as init_file:
                    init_file.write("nuke.pluginAddPath(\"./pyanitools\")")
                    init_file.close()
            except (IOError, OSError) as e:
                print "Could not open {0}. Received error {1}".format(file_path, e)

        # copy custom init.py, menu.py, and session.py (script with python code to support menu and gizmos)
        error = pyani.core.util.copy_files(install_scripts_dir, ani_vars.nuke_custom_dir)
        if error:
            print error
        # remove install scripts
        error = pyani.core.util.rm_dir(install_scripts_dir)
        if error:
            print error

    # reset color, done with printing errors
    print(colorama.Style.RESET_ALL)

    print ("{0}{1}".format(colorama.Fore.GREEN, "Successfully installed"))
    print(colorama.Style.RESET_ALL)


if __name__ == '__main__':
    main()
    raw_input("Install complete, Press enter to exit)")
