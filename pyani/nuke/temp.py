
import pyani.core.util


"""
NukeMngr
____________________


Install first time only, never runs again, new shots added, updates all handled core app

pyani.nuke.mngr

class NukeMngr
class NukeMngrGui

main.py for app contains the gui switching and app updating

is_installed():
    if not (check init.py exists and installed == true (from user pref) and session_mngr.py exists)
         show install gui, click button it does the following:
             copy session_mngr.py from z drive app_data to seq scripts
             create init.py if doesn't exist
             append show init.py to init.py 
             create menu.py if doesn't exist
             append show menu.py to menu.py
    else
        show nuke mngr gui
        
        
Nuke Mngr App

    get a list of all sequences and put in drop down - from app data json
    if change selection rebuild ui
    
    SEQUENCE SETUP
        checkboxes for (on by default):
            copy gizmos - run a copy command on show plugin path to seq plugin path
            copy scripts - run a copy on show scripts to seq scripts
            copy templates run copy show templates to seq templates
            create shot nuke scripts - run a copy on seq template to shots comp.nk
            
            need to overwrite if exists, make sure all folders exist, seq lib and shot composite folders
            
    UPDATE SEQUENCES
        Tree view of checkboxes - plugins, scripts, templates. with version in (ex: version 1.0.0)
        Normal color (off white light grey) for up to date
        Yellow for out of date
        Red for missing         
        
        missing - get list of show gizmos etc... and then check if each exists in seq lib
        yellow - app_data.json has dictionary of versions for all plugins, and each plugin, scripts, templates has a version json, compare
        
        update command >
        get which boxes checked, and copy those items, update version dictionary, change color of item (gui refresh)
        
    SHOT 
        populate a list with all shots from sequence - use app data json
        checkbox to show only localized - have to check all shots to see if plugin folder is empty
        copy from seq to shot based off selected plugins
        remove from shot based off selected plugins

pyani.nuke.session

class menu - any menu gui stuff
class cmds - all the non gui stuff
         
Needed for Inside Nuke - comes from session_mngr.py at sequence level.
    
    On launch check seq shot set - get from file path, if not in the script then set those vars, check frame range correct - use app data
    create movie function that calls py shoot
    menu create and menu items with their commands
        create char asset - makes a char template with the char name given
        create envir asset
        create optical asset
        create mpaint asset
        create fx asset
        plugins> list of gizmos and clicking adds one
"""



######################################################################################

# Z:/LongGong/sequences/Seq180/Shot280/Composite/work/Seq180_Shot280_v003.nk



import nuke
current_script = nuke.root().name()

app_data_path = "Z:\\LongGong\\PyAniTools\\app_data\\NukeMngr\\app_data.json"
nuke_script = "Z:/LongGong/sequences/Seq180/Shot280/Composite/work/Seq180_Shot280_v003.nk"



def is_script_setup():
    """
    Checks if a nuke script has been setup. Checks the user variables under project settings
    :return: True if setup, False if not
    """
    if nuke.root()['seqName'].value() == '' or  nuke.root()['shotName'].value() == '':
        return False
    return True

def get_show_data_from_disk(data_path, nuke_script_path):
    show_data = pyani.core.util.load_json(data_path)
    seq = get_active_sequence_name(nuke_script_path)
    shot = get_active_shot_name(nuke_script_path)
    first_frame = show_data[seq][shot]["first_frame"]
    last_frame = show_data[seq][shot]["last_frame"]
    return seq, shot, first_frame, last_frame

def update_frame_range():
    seq, show, first_frame, last_frame = get_show_data_from_disk()

def init(data_path, nuke_script_path):
    """
    Initialize class variables
    :param data_path: the path to the file containing all the show sequences and shots info
    :param nuke_script_path: the absolute path of the current nuke script
    """
    # if the nuke script has been setup with scene data, skip and read info from nuke
    if is_script_setup():
        seq = nuke.root()['seqName'].value()
        shot = nuke.root()['shotName'].value()
        first_frame = nuke.root()['first_frame'].value()
        last_frame = nuke.root()['last_frame'].value()
    # scene data isn't in nuke, get from disk and save in nuke
    else:
        show_data = pyani.core.util.load_json(data_path)
        seq = get_active_sequence_name(nuke_script_path)
        shot = get_active_shot_name(nuke_script_path)
        first_frame = show_data[seq][shot]["first_frame"]
        last_frame = show_data[seq][shot]["last_frame"]
        nuke.root()['seqName'].setValue(seq)
        nuke.root()['shotName'].setValue(shot)
        nuke.root()['first_frame'].setValue(first_frame)
        nuke.root()['last_frame'].setValue(last_frame)





############################################################################################

# get all nodes matching the type - a nuke class
# returns: the list of nodes
def getAllNodesOfType(type):
    nodeList = []
    for n in nuke.allNodes():
      if n.Class() == type:
        nodeList.append(n)
    return nodeList

# sets merges in the merge list to the operation given
# operation : the nuke
def setMergeOperation(operation, mergeList):
    for n in mergeList:
        n.knob("operation").setValue(operation)

# execute in script editor
nuke.selectedNode().knob('knobChanged').setValue('mergeList = getAllNodesOfType("Merge2") \noperation = nuke.toNode("Merge_main").knob("operation").value() \nsetMergeOperation(operation, mergeList)')



