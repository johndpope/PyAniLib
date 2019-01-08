import nuke
import os
import pyani.core.util as utils
from functools import partial
import tempfile


class AniNukeCmds:
    """
    Class to support plugins and menus in Nuke.
    """

    def __init__(self, movie_tool):
        # don't initialize here, can cause issues with nuke, just declare
        self.ani_vars = utils.AniVars()
        self.nuke_gui = None
        self.plugins = None
        self.templates = None
        # the move tool to call to create the movie
        self.movie_tool = movie_tool

    def load_plugin_paths(self):
        """Loads show and all sequences' plugins, menus, and scripts folders
        """
        # load show
        nuke.pluginAddPath(self.ani_vars.plugin_show)
        nuke.pluginAddPath(self.ani_vars.templates_show)
        # get list of all sequences
        sequences = self.ani_vars.get_sequence_list()
        for sequence in sequences:
            self.ani_vars.update(sequence)
            nuke.pluginAddPath(self.ani_vars.plugin_seq)
            nuke.pluginAddPath(self.ani_vars.templates_seq)

    def init_script(self):
        """Runs when a shot nuke script is loaded. Sets the sequence and shot vars, sets nuke project settings
         like frame range, and builds custom menus
        """
        current_script = nuke.root().name()
        self.nuke_gui = AniNukeGui()
        self.ani_vars.update_using_shot_path(current_script)
        # project settings
        self.set_project_settings()
        # menus
        self.setup_seq_menu()

    def set_project_settings(self):
        """Set nuke project settings based off sequence and shot
        """
        nuke.root()['seq'].setValue(self.ani_vars.seq_name)
        nuke.root()['shot'].setValue(self.ani_vars.shot_name)
        nuke.root()['first_frame'].setValue(self.ani_vars.first_frame)
        nuke.root()['last_frame'].setValue(self.ani_vars.last_frame)

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

    def setup_seq_menu(self):
        """Make the custom show menu
        """
        self.plugins = utils.load_json(os.path.join(self.ani_vars.plugin_seq,
                                                    self.ani_vars.plugins_json_name)).keys()
        self.templates = utils.load_json(os.path.join(self.ani_vars.templates_seq,
                                                      self.ani_vars.templates_json_name)).keys()
        self.nuke_gui.build_menu(self.ani_vars.seq_name, self.plugins, self.templates)

    def create_movie(self, output_plugin_name):
        """
        Create a movie from the scripts composited image sequence
        :param output_plugin_name: name of the OUTPUT gizmo.
        """
        group = nuke.toNode(output_plugin_name)
        # get options
        movie_name = group.knob("mov_eval_name").value()
        image_name = group.knob("image_path_eval").value()
        create_movie = group.knob("writeMovie").getValue()
        hq_movie = group.knob("hqMovie").getValue()
        view_movie = group.knob("viewMovie").getValue()
        steps = int(group.knob("steps").getValue())
        frame_range = group.knob("frame_range").getValue()

        # build command line arguments
        if create_movie:
            options = [
                "-ng",
                "-i",
                image_name,
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

            # ex using PyShoot: C:\PyAniTools\installed\PyShoot\PyShoot.exe \
            # -ng -i Z:/LongGong/images/Seq180/Shot190/comp/Seq180_Shot190.1001.exr \
            # -o Z:/LongGong/movies/Seq180/Seq180_Shot190.mp4 -fs 1 --overwrite --frame_hold --frame_range 1001-1041
            utils.launch_app(self.movie_tool, options)

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
        self.ani_vars = utils.AniVars()
        # the temporary directory in windows for templates with replaced text
        self.tempDir = os.path.join(tempfile.gettempdir(), "Nuke")

    @staticmethod
    def show_msg(msg):
        """
        Helper function to display a message to user
        :param msg: the string message
        """
        nuke.message(msg)

    def default_menu(self):
        """Builds the menu when not in a shot environment
        """
        # Make the custom show menu
        plugins = utils.load_json(os.path.join(self.ani_vars.plugin_show,
                                               self.ani_vars.plugins_json_name)).keys()
        self.build_menu("Show Plugins", plugins, None)

    def build_menu(self, title, plugins, templates):
        """
        Builds the menu for the sequence or if not in a sequence builds menu based off show plugins. For show
        doesn't add templates, those are shot centric
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
        # show the plugins and templates available
        for plugin in plugins:
            plugin_base_name = plugin.split(".")[0]
            self.custom_menu.addCommand("Plugins/{0}".format(plugin_base_name),
                                        "nuke.createNode(\"{0}\")".format(plugin))
        # this will be none if not in sequence/shot environment - ie loaded a non shot based script
        if template_data:
            for template in templates:
                template_base_name = template.split(".")[0]
                # don't add to menu if it isn't a self contained template, ie skip something like shot_master which
                # is a collection of templates
                if self.backdrop_names[template]:
                    self.custom_menu.addCommand("Templates/{0}".format(template_base_name),
                                                partial(self.create_template, template))

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
