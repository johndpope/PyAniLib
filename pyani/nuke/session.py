"""
Gets copied to c:\users\{user_name}\.nuke\pyanitools\ by install script
"""

import nuke


def my_function():
    read = nuke.createNode("Read")
    read["name"].setValue("Hello")
    write = nuke.createNode("Write")
    write["name"].setValue("World")