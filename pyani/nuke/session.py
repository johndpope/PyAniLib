import os
from functools import partial
import pyani.core.appsession
import tempfile
import logging
import operator
import nuke
import pyani.core.util as utils
import pyani.core.anivars


logger = logging.getLogger()


class AniNukeCmds:
    """
    Class to support plugins and menus in Nuke.
    """

    def __init__(self, movie_tool):
        # don't initialize here, can cause issues with nuke, just declare
        self.ani_vars = pyani.core.anivars.AniVars()
        self.nuke_gui = None
        self.plugins = None
        self.templates = None
        self.session = pyani.core.appsession.AniSession()
        # the move tool to call to create the movie
        self.movie_tool = movie_tool

    def load_nuke_env(self):
        """Loads all sequence and shot plugin paths
        """
        session = self.session.get_session()

        sequence = session['core']['seq']
        shot = session['core']['shot']

        # show based plugins and templates since not in shot envir
        if sequence == "non-prod":
            nuke.pluginAddPath(self.ani_vars.plugin_show)
            nuke.pluginAddPath(self.ani_vars.templates_show)
        # sequence and shot based plugins since in shot envir
        else:
            # do this first, update func needs this set
            self.ani_vars.load_seq_shot_list()
            self.ani_vars.update(sequence, shot)
            nuke.pluginAddPath(self.ani_vars.shot_comp_plugin_dir)
            nuke.pluginAddPath(self.ani_vars.plugin_seq)
            nuke.pluginAddPath(self.ani_vars.templates_seq)

        logging.info("Plugin Paths: {0}".format(nuke.pluginPath()))

    def init_script(self):
        """Runs when a shot nuke script is loaded. Sets the sequence and shot vars, sets nuke project settings
         like frame range, and builds custom menus
        """
        logging.info("Nuke Script Name is {0}".format(nuke.root().name()))
        # project settings
        self.set_project_settings()

    def set_project_settings(self):
        """Set nuke project settings based off sequence and shot
        """
        logging.info(
            "Setting Project Settings: Seq: {0}, Shot: {1}, First frame: {2}, Last frame: {3}".format
                (
                    self.ani_vars.seq_name,
                    self.ani_vars.shot_name,
                    self.ani_vars.first_frame,
                    self.ani_vars.last_frame
                )
        )
        nuke.root()['seq'].setValue(self.ani_vars.seq_name)
        nuke.root()['shot'].setValue(self.ani_vars.shot_name)
        nuke.root()['first_frame'].setValue(int(self.ani_vars.first_frame))
        nuke.root()['last_frame'].setValue(int(self.ani_vars.last_frame))

    @staticmethod
    def create_shot_camera(cam_dir):
        """Creates a camera node that reads the newest (based off modification time) shot camera abc. Ignores
        any file other than alembic (abc). If no cameras found lets user know and does nothing.
        :param cam_dir: the directory to the camera(s)
        """
        logging.info("Creating camera: directory is {0}".format(cam_dir))
        if os.path.exists(cam_dir):
            # get cameras, filtering out other files and files without the word camera
            # make sure cam_dir is in format nuke wants, doesn't like back slashes
            cam_dir = cam_dir.replace("\\", "/")
            cams = [
                os.path.join(cam_dir, cam) for cam in os.listdir(cam_dir) if cam.endswith('.abc') and 'camera' in cam
            ]
            logging.info("Found cameras: {0}".format(', '.join(cams)))
            if not isinstance(cams, list):
                nuke.message("No cameras found in {0}".format(cam_dir))
                return
            # get latest camera in directory
            latest_cam = max(cams, key=os.path.getmtime)
            logging.info("Latest camera is {0}".format(os.path.normpath(latest_cam)))
            # set 'file' and 'read from file' knobs here to avoid pop up asking to destroy cam data,
            #  and avoids needing to show panel for values to get set
            nuke.createNode("Camera2", "file {0} read_from_file True".format(latest_cam))

    @staticmethod
    def load_and_create_plugin(plugin, plugin_path):
        """
        Dynamically in nuke loads a plugin given a path to the plugin and a plugin name. If plugin doesn't exist
        lets user know and does nothing
        :param plugin: name of the plugin without extension. ie: AOV_CC, not AOV_CC.gizmo
        :param plugin_path: absolute path to directory with the plugin
        """
        nuke.pluginAddPath(plugin_path)
        logging.info("Adding plugin path {0} and loading plugin {1}".format(plugin_path, plugin))
        # try to load, since nuke doesn't return an error just throws a runtime exception.
        try:
            nuke.load(plugin)
            nuke.createNode(plugin)
        except RuntimeError as e:
            error = "Could not load the plugin named {0}. Error is {1}".format(plugin, e)
            logging.exception(error)
            nuke.message(error)

    @staticmethod
    def eval_tcl(*args):
        """evaluates a knob's tcl and sets the evaluated value in another knob

        equivalent to the following, except the knobchanged calls "eval_tcl('image_path_eval', 'file')":
        knobChanged "nuke.thisNode()\['image_path_eval'].setValue(nuke.thisNode()\['file'].evaluate())"

        :param args: arbitrary amount of knobs. expects two knobs, the first being the knob to set, the second being
        the knob to evaluate.

        ex:
        knobChanged "cmds.eval_tcl('mov_eval_name','movieName','image_path_eval','file')"
        in the above mov_eval_name is a text knob that gets set to the evaluated movieName file field. same for
        image_path_eval and file
        """
        for index in range(0, len(args), 2):
            nuke.thisNode()[args[index]].setValue(nuke.thisNode()[args[index+1]].evaluate())

    def create_movie(self):
        """
        Create a movie from the scripts composited image sequence
        """
        group = nuke.thisGroup()

        # get options
        image_name = group.knob("file").evaluate()
        movie_name = group.knob("movieName").evaluate()
        create_movie = group.knob("writeMovie").getValue()
        hq_movie = group.knob("hqMovie").getValue()
        view_movie = group.knob("viewMovie").getValue()
        steps = int(group.knob("steps").getValue())
        frame_range = group.knob("frame_range").getValue()

        image_slash_fix = image_name.replace("/", "\\")
        image_parts = image_slash_fix.split("\\")
        image_dir = "\\".join(image_parts[:-1])
        image_dir = os.path.normpath(image_dir)
        image_name = image_parts[-1]
        image_base_name = ".".join(image_name.split(".")[:-2])
        image_ext = image_name.split(".")[-1]

        # build command line arguments
        if create_movie:
            options = [
                "-ng",
                "-i",
                image_dir,
                "-n",
                image_base_name,
                "-e",
                image_ext,
                "-o",
                movie_name,
                "-fs",
                str(steps),
                "--overwrite",
                "--frame_hold",
                "--frame_range",
                frame_range
            ]
            if view_movie:
                options.append("--play")
            if hq_movie:
                options.append("--high_quality")

            print "Movie options are: {0}".format(options)
            logging.info("Movie options are: {0}".format(", ".join(options)))
            # ex using PyShoot: C:\PyAniTools\installed\PyShoot\PyShoot.exe \
            # -ng -i Z:/LongGong/images/Seq180/Shot190/comp/ \
            # -o Z:/LongGong/movies/Seq180/Seq180_Shot190.mp4 -fs 1 --overwrite --frame_hold --frame_range 1001-1041
            utils.launch_app(self.movie_tool, options)

    @staticmethod
    def reload_script():
        """Reloads the current script
        """
        # get the current script
        current_script = nuke.root().knob('name').value()
        # clear the current nuke session
        nuke.scriptClear()
        # reload the script
        nuke.scriptOpen(current_script)

    @staticmethod
    def get_all_nodes_of_type(class_type):
        """
        get all nodes matching the type
        :param class_type: a nuke class
        :return: the list of nodes
        """
        node_list = []
        for n in nuke.allNodes():
            if n.Class() == class_type:
                node_list.append(n)
        return node_list

    @staticmethod
    def set_merge_operation(operation, merge_list):
        """
        sets merges in the merge list to the operation given
        :param operation: the nuke merge operation like add, over, etc...
        :param merge_list: liost of merges
        """
        for n in merge_list:
            n.knob("operation").setValue(operation)

    @staticmethod
    def set_static_text_to_eval_tcl(read, txt):
        """
        set knob callback to evaluate tcl in file read and put in a static text
        Based off:
        cmd = "nuke.thisNode()['image_path_eval'].setValue(nuke.thisNode()['file'].evaluate())"
        n = nuke.selectedNode()
        n['knobChanged'].setValue(cmd)
        :param read: the file knob name of the read node
        :param txt: the static text label
        """
        node = nuke.toNode(read)
        cmd = "nuke.toNode({0})['image_path_eval'].setValue(nuke.toNode({1})['{2}'].evaluate())".format(read, read, txt)
        node['knobChanged'].setValue(cmd)


class AniNukeGui:
    """
    Class to extend Nuke's gui interface
    """

    def __init__(self):
        # get the main nuke menu bar
        self.menu_bar = nuke.menu("Nuke")
        # create a custom menu
        self.custom_menu = self.menu_bar.addMenu("&LongGong")
        self.backdrop_names = {}
        self.asset_replace_keys = {}
        self.template_types_replaceable = []
        # space between existing and newly placed template in x
        self.backdrop_space_between = 10
        self.ani_vars = pyani.core.anivars.AniVars()
        self.ani_vars.load_seq_shot_list()
        # the temporary directory in windows for templates with replaced text
        self.tempDir = os.path.join(tempfile.gettempdir(), "Nuke")
        # commands class - an AniNukeCmds object, pass blank string for movie tool, don't need that part of commands
        self.cmds = AniNukeCmds("")
        self.session = pyani.core.appsession.AniSession()


    @staticmethod
    def show_msg(msg):
        """
        Helper function to display a message to user
        :param msg: the string message
        """
        nuke.message(msg)

    def setup_menu(self):
        """
        Builds the menu for the sequence or if not in a sequence builds menu based off show plugins. For show
        doesn't add templates, those are shot centric. Shot menu contains plugins, templates, and create shot camera.
        If a shot has plugins, shows those as well
        """
        session = self.session.get_session()
        sequence = session['core']['seq']
        shot = session['core']['shot']
        self.ani_vars.load_seq_shot_list()

        # show based plugins and templates since not in shot envir
        if sequence == "non-prod":
            plugins = utils.load_json(os.path.join(self.ani_vars.plugin_show,
                                                   self.ani_vars.plugins_json_name))
            if not isinstance(plugins, list):
                logging.error(plugins)
            templates = utils.load_json(os.path.join(self.ani_vars.templates_show,
                                                     self.ani_vars.templates_json_name))
            if not isinstance(templates, list):
                logging.error(templates)
        # sequence and shot based plugins since in shot envir
        else:
            self.ani_vars.update(sequence, shot)
            plugins = utils.load_json(os.path.join(self.ani_vars.plugin_seq,
                                                   self.ani_vars.plugins_json_name))
            if not isinstance(plugins, list):
                logging.error(plugins)
            templates = utils.load_json(os.path.join(self.ani_vars.templates_seq,
                                                     self.ani_vars.templates_json_name))
            if not isinstance(templates, list):
                logging.error(templates)

        shot_plugins = None
        self.custom_menu.clearMenu()

        # see if we are in a shot env, if so load sequence plugins, otherwise load show plugins
        if self.ani_vars.is_valid_seq(sequence) and self.ani_vars.is_valid_shot(shot):
            self.ani_vars.update(sequence, shot)
            self._build_template_data(templates)

            # display seq_name name as a empty command
            self.custom_menu.addCommand(sequence, "nuke.tprint('')")
            self.custom_menu.addSeparator()

            # check for shot plugins, need to disable sequence plugin, if shot has the same plugin
            if self.ani_vars.shot_name:
                # make sure plugins exist
                if os.path.exists(self.ani_vars.shot_comp_plugin_dir):
                    # check for plugins
                    shot_plugins = [
                        p for p in os.listdir(self.ani_vars.shot_comp_plugin_dir) if not p.endswith('json')
                    ]

        # show the plugins - available for shot and non shot environments
        for plugin in plugins.keys():
            plugin_base_name = plugin.split(".")[0]
            if shot_plugins:
                if plugin in shot_plugins:
                    self.custom_menu.addCommand("Plugins/{0} (not available, shot is overriding)".format(
                        plugin_base_name), "nuke.message('Not Available, Use Shot Copy')")
                # plugin not in shot
                else:
                    self.custom_menu.addCommand("Plugins/{0}".format(plugin_base_name),
                                                "nuke.createNode(\"{0}\")".format(plugin))
            # no shot script loaded
            else:
                self.custom_menu.addCommand("Plugins/{0}".format(plugin_base_name),
                                            "nuke.createNode(\"{0}\")".format(plugin))

        # only show templates and shot options in shot environment
        if self.ani_vars.is_valid_shot(shot):
            for template in templates.keys():
                template_base_name = template.split(".")[0]
                # don't add to menu if it isn't a self contained template, ie skip something like shot_master which
                # is a collection of templates
                if self.backdrop_names[template]:
                    self.custom_menu.addCommand("Templates/{0}".format(template_base_name),
                                                partial(self.create_template, template))

                self.custom_menu.addSeparator()
                self.custom_menu.addCommand(self.ani_vars.shot_name, "nuke.tprint('')")
                self.custom_menu.addSeparator()
                # add shot camera command
                self.custom_menu.addCommand("Get Shot Camera",
                                            lambda: self.cmds.create_shot_camera(self.ani_vars.shot_cam_dir))
                if shot_plugins:
                    # show the plugins available
                    for shot_plugin in shot_plugins:
                        plugin_base_name = shot_plugin.split(".")[0]
                        self.custom_menu.addCommand("Shot Plugins/{0}".format(plugin_base_name),
                                                    "nuke.createNode(\"{0}\")".format(shot_plugin))

    def build_menu2(self, title, plugins, templates):
        """
        Builds the menu for the sequence or if not in a sequence builds menu based off show plugins. For show
        doesn't add templates, those are shot centric. Shot menu contains plugins, templates, and create shot camera.
        If a shot has plugins, shows those as well
        :param title: the menu title
        :param plugins: list of plugins
        :param templates: list of templates
        """
        template_data = None
        # name of script - ie the file path
        current_script = nuke.root().name()
        # see if we are in a shot env, if so load sequence plugins, otherwise load show plugins
        if self.ani_vars.is_valid_seq(current_script) and self.ani_vars.is_valid_shot(current_script):
            self.ani_vars.update_using_shot_path(current_script)
            template_data = utils.load_json(
                os.path.join(self.ani_vars.templates_seq, self.ani_vars.templates_json_name)
            )
            self._build_template_data(template_data)

        self.custom_menu.clearMenu()
        # display title name as a empty command
        self.custom_menu.addCommand(title, "nuke.tprint('')")
        self.custom_menu.addSeparator()

        # if we are in a shot environment, then check for shot plugins, need to disable sequence plugin,
        # if shot has the same plugin
        if self.ani_vars.shot_name:
            # check for plugins
            shot_plugins = [p for p in os.listdir(self.ani_vars.shot_comp_plugin_dir) if not p.endswith('json')]
        else:
            shot_plugins = None

        if plugins:
            # show the plugins and templates available
            for plugin in plugins:
                plugin_base_name = plugin.split(".")[0]
                if shot_plugins:
                    if plugin in shot_plugins:
                        self.custom_menu.addCommand("Plugins/{0} (not available, shot is overriding)".format(
                            plugin_base_name), "nuke.message('Not Available, Use Shot Copy')")
                    # plugin not in shot
                    else:
                        self.custom_menu.addCommand("Plugins/{0}".format(plugin_base_name),
                                                    "nuke.createNode(\"{0}\")".format(plugin))
                # no shot script loaded
                else:
                    self.custom_menu.addCommand("Plugins/{0}".format(plugin_base_name),
                                                "nuke.createNode(\"{0}\")".format(plugin))
        if templates:
            # this will be none if not in sequence/shot environment - ie loaded a non shot based script
            if template_data:
                for template in templates:
                    template_base_name = template.split(".")[0]
                    # don't add to menu if it isn't a self contained template, ie skip something like shot_master which
                    # is a collection of templates
                    if self.backdrop_names[template]:
                        self.custom_menu.addCommand("Templates/{0}".format(template_base_name),
                                                    partial(self.create_template, template))

        # shot dependent, only add if shot has been set
        if self.ani_vars.shot_name:
            self.custom_menu.addSeparator()
            self.custom_menu.addCommand(self.ani_vars.shot_name, "nuke.tprint('')")
            self.custom_menu.addSeparator()
            # add shot camera command
            self.custom_menu.addCommand("Get Shot Camera",
                                        lambda: self.cmds.create_shot_camera(self.ani_vars.shot_cam_dir))
            if shot_plugins:
                # show the plugins available
                for shot_plugin in shot_plugins:
                    plugin_base_name = shot_plugin.split(".")[0]
                    self.custom_menu.addCommand("Shot Plugins/{0}".format(plugin_base_name),
                                                "nuke.createNode(\"{0}\")".format(shot_plugin))

    def _build_template_data(self, template_data):
        """
        A dictionary of data for processing templates, extracts data from sequence template json file
        json format:
        {
          "template_name.nk": {
            "version": "x.x",
            "desc": "..",
            "backdrop_name": "empty or backdrop_name",
            "asset_replace_key": "empty or assetname"
          },...

        :param template_data: the template json file data
        """
        self.backdrop_names = {}
        self.asset_replace_keys = {}
        self.template_types_replaceable = []
        # top level dict, so template_name.nk and its dict
        for t_name, t_data in template_data.items():
            # child dict, ie template_name.nk's dict
            for data_key, data_value in t_data.items():
                # store backdrop name in dict, use template_name.nk as key, may be empty
                if data_key == "backdrop_name":
                    self.backdrop_names[t_name] = data_value
                # store the asset replace key, use template_name.nk as key, may be empty
                if data_key == "asset_replace_key":
                    self.asset_replace_keys[t_name] = data_value
                # make a list of templates that have replaceable text - must have a value for asset_replace_key
                if data_key == "asset_replace_key" and data_value:
                    self.template_types_replaceable.append(t_name)

    def create_template(self, template_type):
        """
        Makes a new template from the available sequence templates
        :param template_type: the nuke script name - selected from the menu
        """
        asset_name = ""
        # template has replaceable text, generally a character or type environment template
        if template_type in self.template_types_replaceable:
            # get replacement text from user
            asset_name = nuke.getInput("Asset Name", "")

        # load the script into nuke
        self.source_script(template_type, asset_name)
        # find the newly created template
        backdrop_name, nodes_in_backdrop = self.get_backdrop_and_nodes_from_selection(template_type, asset_name)
        # move the new template so it doesn't sit on top of an existing one
        self.move_backdrop(backdrop_name, nodes_in_backdrop)

        # cleanup
        self.clear_selection()
        if os.path.exists(self.tempDir):
            utils.rm_dir(self.tempDir)

    def source_script(self, template_type, asset_name):
        """
        Loads a nuke script into nuke, handles both static and dynamic (text replacement) templates
        :param template_type: the nuke script name
        :param asset_name: for templates that have a replaceable text/ dynamic. Its the replacement text
        :return: the replacement text
        """
        # path on disk to template
        template_path = os.path.join(self.ani_vars.templates_seq, template_type)

        # template has replaceable text
        if template_type in self.template_types_replaceable:
            # open the template .nk
            with open(template_path, 'r') as template_file:
                file_data = template_file.read()

            # Replace the target string
            updated_file_data = file_data.replace(self.asset_replace_keys[template_type], asset_name)
            # make a temp dir to write template with replaced text
            if not os.path.exists(self.tempDir):
                utils.make_dir(self.tempDir)
            temp_template_path = os.path.join(self.tempDir, "{0}.nk".format(asset_name))

            # Write the file
            with open(temp_template_path, 'w') as template_file:
                template_file.write(updated_file_data)

            # source the temp file
            nuke.scriptSource(temp_template_path)

            # set the vars on asset delivery
            asset_delivery = nuke.toNode("Asset_Delivery_{0}".format(asset_name))
            asset_delivery.knob("assetName").setValue(asset_name)
            version_list = utils.get_subdirs(self.ani_vars.shot_layer_dir)
            latest_version = utils.natural_sort(version_list)[-1]
            # strip off 'v' from the folder name, the nuke field wants just a number
            asset_delivery.knob("vers").setValue(latest_version.split("v")[1])

        # non replaceable text, just load the original nuke script
        else:
            nuke.scriptSource(template_path)

        return asset_name

    def get_backdrop_and_nodes_from_selection(self, template_type, asset_name):
        """
        Finds the backdrop and nodes for the template
        :param template_type: the nuke script name
        :param asset_name: the replacement text for dynamic templates
        :return: backdrop name and a list of the nodes in the backdrop
        """
        bd_index = None
        backdrop_name_new = ""

        # get nodes and backdrop created, will remove the backdrop below
        nodes_in_backdrop = nuke.selectedNodes()

        # check if this is a backdrop that has replaceable text
        if template_type in self.template_types_replaceable:
            backdrop_name = "backdrop_{0}".format(asset_name)
            # remove the backdrop from the list, only want the backdrop's nodes - do this by finding it and saving
            # it's list index so we can pop it below
            for index in range(0, len(nodes_in_backdrop)):
                if nodes_in_backdrop[index]["name"].value() == backdrop_name:
                    bd_index = index
                    break
        else:
            # remove backdrop from the list of nodes
            backdrop_name = self.backdrop_names[template_type]
            for index in range(0, len(nodes_in_backdrop)):
                if backdrop_name in nodes_in_backdrop[index]["name"].value():
                    bd_index = index
                    backdrop_name_new = nodes_in_backdrop[index]["name"].value()
            backdrop_name = backdrop_name_new

        # remove the backdrop
        nodes_in_backdrop.pop(bd_index)

        return backdrop_name, nodes_in_backdrop

    def move_backdrop(self, backdrop_name, nodes_in_backdrop):
        """
        Move a backdrop over x amount of space. It is the width of the backdrop + an offset amount from the class
        variable backdrop_space_between
        :param backdrop_name: name of the backdrop
        :param nodes_in_backdrop: the nodes in the backdrop
        """
        # Old position of backdrop
        position_x = nuke.toNode(backdrop_name).xpos()
        position_y = nuke.toNode(backdrop_name).ypos()
        width = nuke.toNode(backdrop_name).width()
        position_x_new = position_x + width + self.backdrop_space_between
        position_y_new = position_y

        # Select nodes in Backdrop
        nuke.toNode(backdrop_name).selectNodes(True)

        # Move Backdrop to new position
        nuke.toNode(backdrop_name).setXYpos(position_x_new, position_y_new)

        # Calculate offset between new and old Backdrop position
        offset_x = position_x - (nuke.toNode(backdrop_name).xpos())
        offset_y = position_y - (nuke.toNode(backdrop_name).ypos())

        # Set new position for nodes in Backdrop
        for n in nodes_in_backdrop:
            cur_xpos = n.xpos()
            cur_ypos = n.ypos()
            n.setXYpos(cur_xpos - offset_x, cur_ypos - offset_y)

    @staticmethod
    def clear_selection():
        """Deselects all nuke nodes
        """
        if nuke.selectedNodes():
            for node in nuke.selectedNodes():
                node['selected'].setValue(False)

    def align_nodes(self, direction, node=None):
        """
        If only one node is selected, the node will align to the nearest connected node in the desired direction.
        Multiple nodes will align to the selected node that's the furthest away in the desired direction
        Overlapping nodes will be placed next to the overlapped node instead of overlapping it.
        Takes a node's screensize into account to ensure correct alignment no matter what kind of node it is.
        Ignores Viewers and child nodes with hidden inputs
        :param direction: up, down, left or right to place nodes.
        :param node: optional node to use if not placing based off selection
        :return:
        """

        # USER SETTINGS
        # defines the amount of space that's kept between the nodes. the higher the multiplier, the more space.
        multiplier_x = 1
        multiplier_y = 1
        dont_move = False

        selection = nuke.selectedNodes()

        if selection:
            # set the axis based off direction, and which element of our 2D positions list to use. 0 = x, 1 = y
            if direction in ['left', 'right']:
                axis = 'x'
                index = 0
            else:
                axis = 'y'
                index = 1

            # MULTIPLE NODES
            # if multiple nodes are selected, all the nodes will align to the node that's the
            # furthest away in the specified direction
            if len(selection) > 1:
                all_pos = [[], []]
                for node in selection:
                    all_pos[0].append(node.knob('xpos').value() + (self.get_screen_size(node)[0]))
                    all_pos[1].append(node.knob('ypos').value() + (self.get_screen_size(node)[1]))

                # check whether all selected nodes already share the same position values to prevent overlapping
                # if so, do nothing
                if not all_pos[1 - index].count(all_pos[1 - index][0]) == len(all_pos[1 - index]):
                    if direction in ["left", "up"]:
                        destination = min(all_pos[index])
                    else:
                        destination = max(all_pos[index])
                else:
                    dont_move = True

            # SINGLE NODE
            # if only one node is selected, the selected node will snap to the nearest
            # connected node in the specified direction
            elif len(selection) == 1:
                current_node = selection[0]

                # create a list of all the connected nodes
                input_nodes = current_node.dependencies()
                output_nodes = current_node.dependent()

                # remove nodes with hidden inputs and viewer nodes
                # not every node has a hide input knob (read node for example), so use a "try" in case it doesn't
                for node in output_nodes:
                    try:
                        if node.knob('hide_input').value() or node.Class() == 'Viewer':
                            output_nodes.remove(node)
                    except:
                        pass

                if current_node.knob('hide_input'):
                    if current_node.knob('hide_input').value():
                        input_nodes = []

                connected_nodes = input_nodes + output_nodes

                # create a list for every connected node containing the following
                # [xpos,ypos,relative xpos, relative ypos, node]
                positions = []

                for node in connected_nodes:
                    x_pos = node.xpos() + self.get_screen_size(node)[0]
                    y_pos = node.ypos() + self.get_screen_size(node)[1]
                    current_node_x_pos = current_node.xpos() + self.get_screen_size(current_node)[0]
                    current_node_y_pos = current_node.ypos() + self.get_screen_size(current_node)[1]
                    positions.append(
                        [x_pos, y_pos, x_pos - current_node_x_pos, y_pos - current_node_y_pos, node]
                    )

                # sort the list based on the relative positions
                sorted_nodes_by_pos = sorted(positions, key=operator.itemgetter(index + 2))

                # remove nodes from list to make sure the first item is the node closest to the current_node
                # use the operator module to switch dynamically between ">=" and "<="
                # the positive direction variable is used later to correctly calculate to offset in case
                # nodes are about to overlap
                if direction in ['right', 'down']:
                    equation = operator.le
                    positive_direction = -1
                else:
                    sorted_nodes_by_pos.reverse()
                    equation = operator.ge
                    positive_direction = 1

                try:
                    while equation(sorted_nodes_by_pos[0][index + 2], 0):
                        sorted_nodes_by_pos.pop(0)
                except:
                    pass

                # checking whether there are nodes to align to in the desired direction
                # if there are none, don't move the node
                if len(sorted_nodes_by_pos) != 0:
                    destination = sorted_nodes_by_pos[0][index]

                    current_position = [current_node_x_pos, current_node_y_pos]
                    destination_position = [current_node_x_pos, current_node_y_pos]
                    destination_position[index] = destination

                    # remove the relative positions from the position list
                    for i in range(len(positions)):
                        positions[i] = [positions[i][:2], positions[i][-1]]

                    # Making sure the nodes won't overlap after being aligned.
                    # If they are about to overlap the node will be placed next to the node it tried to snap to.
                    for i in positions:

                        # calculate the difference between the destination and the position of the node it will align to
                        difference = [(abs(i[0][0] - destination_position[0])) * 1.5,
                                      (abs(i[0][1] - destination_position[1])) * 1.5]

                        # define the amount of units a node should offset to not overlap
                        offset_x = 0.75 * (3 * self.get_screen_size(current_node)[0] + self.get_screen_size(i[1])[0])
                        offset_y = 3 * self.get_screen_size(current_node)[1] + self.get_screen_size(i[1])[1]
                        offsets = [int(offset_x), int(offset_y)]

                        # check in both directions whether the node is about to overlap:
                        if difference[0] < offsets[0] and difference[1] < offsets[1]:

                            multiplier = [multiplier_x, multiplier_y][index]
                            offset = positive_direction * multiplier * offsets[index]

                            # find out whether the nodes are already very close to each other
                            # (even closer than they would be after aligning)
                            # don't move the node if that's the case
                            if abs(offset) < abs(destination - current_position[index]):
                                destination = destination + offset
                            else:
                                dont_move = True

                            # stop looping through the list when a suitable node to align to is found
                            break
                else:
                    dont_move = True
            else:
                dont_move = True

            # MOVE THE SELECTED NODES
            nuke.Undo().name('Align Nodes')
            nuke.Undo().begin()

            for node in selection:
                if not dont_move:
                    if axis == 'x':
                        node.setXpos(int(destination - self.get_screen_size(node)[index]))
                    else:
                        node.setYpos(int(destination - self.get_screen_size(node)[index]))
        if node:
            # let nuke place
            node.autoplace()

    @staticmethod
    def get_screen_size(node):
        """
        To get the position of a node in the DAG you can use the xpos/ypos knobs.
        However, that position is influenced by the size of the node.
        When horizontally aligned, a Dot node will have a different ypos than a blur node for example.
        To neutralize a nodes pos you have to add the half the nodes screen dimensions to the position.
        :param node: a nuke node
        :return: the nodes screen position
        """

        return [node.screenWidth() / 2, node.screenHeight() / 2]

