import logging
import os
import pyani.core.util
import pyani.core.appmanager
import pyani.core.ui
import pyani.render.log.data


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore


logger = logging.getLogger()


class AniRenderDataViewer(pyani.core.ui.AniQMainWindow):
    def __init__(self, error_logging):
        self.app_name = "PyRenderDataViewer"
        self.app_mngr = pyani.core.appmanager.AniAppMngr(self.app_name)
        # pass win title, icon path, app manager, width and height
        super(AniRenderDataViewer, self).__init__(
            "Py Render Data Viewer",
            "images\pyrenderdataviewer.png",
            self.app_mngr,
            1200,
            1000,
            error_logging
        )
        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        self.render_data = pyani.render.log.data.AniRenderData(dept="lighting")

        error = self.render_data.ani_vars.load_seq_shot_list()
        if error:
            self.msg_win.show_error_msg("Critical Error", "A critical error occurred: {0}".format(error))
        else:
            # setup color sets for the graph. Use cool colors for time stats, warm colors for memory stats, and yellow
            # for single bar stats.
            self.color_set_cool = [
                QtGui.QColor(44, 187, 162),
                QtGui.QColor(0, 160, 187),
                QtGui.QColor(51, 102, 204),
                QtGui.QColor(102, 102, 204),
                QtGui.QColor(127, 76, 159)
            ]
            self.color_set_warm = [
                QtGui.QColor(227, 192, 0),
                QtGui.QColor(227, 155, 0),
                QtGui.QColor(227, 134, 0),
                QtGui.QColor(204, 102, 0),
                QtGui.QColor(204, 51, 0),
                QtGui.QColor(204, 0, 0)
            ]

            # text font to use for ui
            self.font_family = "Century Gothic"
            self.font_size_menus = 10
            self.font_size_nav_crumbs = 11

            # tracks the where we are at - show (displays sequences), sequence (display shots) or shot
            # (displays frames)
            # current level is 0-show, 1-sequence, 2-shot, corresponds as an index into self.levels list
            self.current_level = 0
            self.levels = ["Sequence", "Shot", "Frame"]

            self.seq = None
            self.shot = None

            # stats menu
            self.stats_menu = QtWidgets.QComboBox()
            for stat in self.render_data.stat_names:
                self.stats_menu.addItem(stat)
            self.selected_stat = str(self.stats_menu.currentText())

            # set up the data
            self.render_data.read_stats()
            self.render_data.process_data(self.selected_stat)

            # history widgets - show level and sequence level only allow history="1", because you would have
            # to check all sequences for show level for the most history and use the one with the most
            # history for the combo box. same for sequence level. so for now make it easy and do just shot level
            # run this after render data has been populated
            self.history_menu = QtWidgets.QComboBox()
            self._build_history_menu()
            self.history = "1"

            self.nav_crumbs = QtWidgets.QLabel()
            self.set_nav_link()

            # averages side bar widgets created dynamically, just store layout
            self.averages_layout = QtWidgets.QVBoxLayout()

            x_axis_labels, graph_data, colors = self.build_graph_data()

            self.bar_graph = pyani.core.ui.BarGraph(
                x_axis_labels, graph_data, self.levels[self.current_level], self.selected_stat, width=.95, color=colors
            )
            # override any custom qt style, which breaks the text spacing for the bar graph on axis labels
            self.bar_graph.setStyle(QtWidgets.QCommonStyle())

            self.create_layout()
            self.set_slots()

    def create_layout(self):
        main_layout = QtWidgets.QHBoxLayout()

        graph_layout = QtWidgets.QVBoxLayout()

        graph_header_layout = QtWidgets.QHBoxLayout()
        graph_header_layout.addWidget(self.nav_crumbs)
        graph_header_layout.addStretch(1)

        history_label = QtWidgets.QLabel(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>History</span>".format(
                self.font_size_menus, self.font_family
            )
        )
        graph_header_layout.addWidget(history_label)
        graph_header_layout.addWidget(self.history_menu)
        stats_label = QtWidgets.QLabel(
            "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>Render Stats</span>".format(
                self.font_size_menus, self.font_family
            )
        )
        graph_header_layout.addWidget(stats_label)
        graph_header_layout.addWidget(self.stats_menu)

        graph_layout.addLayout(graph_header_layout)
        graph_layout.addWidget(self.bar_graph)
        main_layout.addLayout(graph_layout)
        # space between graph and sidebar
        main_layout.addItem(QtWidgets.QSpacerItem(20, 0))

        # side bar gui
        self.build_averages_sidebar()
        main_layout.addLayout(self.averages_layout)
        # space between side bar and edge window
        main_layout.addItem(QtWidgets.QSpacerItem(20, 0))

        self.main_layout.addLayout(main_layout)
        self.add_layout_to_win()

    def set_slots(self):
        self.nav_crumbs.linkActivated.connect(self.update_from_nav_link)
        self.history_menu.currentIndexChanged.connect(self.update_displayed_history)
        self.stats_menu.currentIndexChanged.connect(self.update_displayed_stat)
        self.bar_graph.graph_update_signal.connect(self.update_from_graph)

    def set_nav_link(self):
        """
        Sets the navigation link text and http link that appears above the graph. This is used to navigate up through
        the data. ie. from shot level to sequence level to show level
        """
        if 0 <= self.current_level < len(self.levels):
            if self.current_level is 0:
                nav_str = "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>" \
                          "<b>Show</b></span></font>".format(self.font_size_nav_crumbs, self.font_family)
            elif self.current_level is 1:
                nav_str = "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>" \
                          "<a href='#Show'><span style='text-decoration: none; color: #ffffff'>Show</span></a> > " \
                          "<b>{2}</b>" \
                          "</span>".format(self.font_size_nav_crumbs, self.font_family, self.seq)
            else:
                nav_str = "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>" \
                          "<a href='#Show'><span style='text-decoration: none; color: #ffffff'>Show</span></a> > " \
                          "<a href='#Seq'><span style='text-decoration: none; color: #ffffff'>{2}</span></a> > " \
                          "<b>{3}</b>" \
                          "</span>".format(self.font_size_nav_crumbs, self.font_family, self.seq, self.shot)

            self.nav_crumbs.setText(nav_str)

    def update_displayed_history(self):
        """
        Updates the graph and sidebar averages with the history selected
        """
        # only allow history when viewing a shot's data
        self.history = str(self.history_menu.currentText())
        self.update_ui()

    def update_displayed_stat(self):
        """
        Updates the graph and sidebar averages with the render stat selected
        """
        self.selected_stat = str(self.stats_menu.currentText())
        self.update_ui()

    def update_from_graph(self, x_axis_value):
        """
        Takes a x axis value clicked on and updates the ui and graph. Clicking the graph allows you to dive further into
        the data, ie go from show view to sequence view to shot view
        :param x_axis_value: the x axis value clicked on from the graph = gets via signal slot,
        see pyani.core.ui.BarGraph class
        """
        # set the level based off x axis value clicked on
        if pyani.core.util.is_valid_seq_name(str(x_axis_value)):
            self.seq = str(x_axis_value)
            self.current_level = 1
        elif pyani.core.util.is_valid_shot_name(str(x_axis_value)):
            self.shot = str(x_axis_value)
            self.current_level = 2
            self._build_history_menu()
        elif pyani.core.util.is_valid_frame(str(x_axis_value)):
            # no more levels, don't do anything except show log
            pass
        else:
            # don't know what it is, display warning and don't change level
            self.msg_win.show_warning_msg(
                "Warning", "Could not update graph. {0} is not a valid x axis value".format(str(x_axis_value))
            )

        self.set_nav_link()
        self.update_ui()

    def update_from_nav_link(self, link):
        """
        Updates the graph and sidebar averages based off the navigation text that was clicked
        :param link: passed from the signal connected to the text
        """
        if link == "#Show":
            self.current_level = 0
        elif link == "#Seq":
            self.current_level = 1
        self.set_nav_link()
        self.update_ui()

    def update_ui(self):
        """
        Updates the data based off the ui selections, and passes to graph. Also updates sidebar averages
        :return:
        """
        # process the render data based off level
        if self.current_level is 2:
            self.render_data.process_data(self.selected_stat, self.seq, self.shot, history=self.history)
        elif self.current_level is 1:
            self.render_data.process_data(self.selected_stat, self.seq)
        else:
            self.render_data.process_data(self.selected_stat)

        # rebuild data
        x_axis_labels, graph_data, colors = self.build_graph_data()

        self.bar_graph.update_graph(
            x_axis_label=self.levels[self.current_level],
            y_axis_label=self.selected_stat,
            x_data=x_axis_labels,
            y_data=graph_data,
            width=0.95,
            color=colors
        )

        # rebuild sidebar averages ui
        self.build_averages_sidebar()

    def build_graph_data(self):
        """
        Makes the data dict and color dict needed by the bar graph
        :return: The data dict of float data and the color dict of pyqt colors corresponding to the data
        """
        # colors for the main stat number i.e. the total
        colors = {
            'total': QtGui.QColor(100, 100, 100),
            'components': []
        }

        # the data we pass to the bar graph, expects the format:
        # { 'total': [;list of floats], 'components':[nested list of floats, where each element is a frame, shot, or
        # sequence of data] }
        graph_data = {}
        graph_data['total'] = []
        graph_data['components'] = []

        # build data for show
        if self.current_level is 0:
            x_axis_labels = self.render_data.get_sequences()
            for seq in x_axis_labels:
                graph_data['total'].append(self.render_data.stat_data[seq]['average'][self.selected_stat]['total'])
                graph_data['components'].append(
                    self.render_data.stat_data[seq]['average'][self.selected_stat]['components'])
        # build data for sequence
        elif self.current_level is 1:
            x_axis_labels = self.render_data.get_shots(self.seq)
            for shot in x_axis_labels:
                graph_data['total'].append(
                    self.render_data.stat_data[self.seq][shot]['average'][self.selected_stat]['total'])
                graph_data['components'].append(
                    self.render_data.stat_data[self.seq][shot]['average'][self.selected_stat]['components'])
        # build data for shot
        else:
            x_axis_labels = self.render_data.get_frames(self.seq, self.shot)

            for frame in x_axis_labels:
                graph_data['total'].append(
                    self.render_data.stat_data[self.seq][self.shot][self.history][frame][self.selected_stat]['total'])
                graph_data['components'].append(
                    self.render_data.stat_data[self.seq][self.shot][self.history][frame][self.selected_stat]['components'])

        if self.render_data.get_stat_type(self.selected_stat) == "sec":
            colors_to_use = self.color_set_cool
        elif self.render_data.get_stat_type(self.selected_stat) == 'gb':
            colors_to_use = self.color_set_warm
        else:
            colors_to_use = None
            colors['total'] = pyani.core.ui.YELLOW
        # set colors for the components
        for index in xrange(0, len(graph_data['components'][0])):
            colors['components'].append(colors_to_use[index])

        return x_axis_labels, graph_data, colors

    def build_averages_sidebar(self):
        """
        Makes the side bar that displays averages for the stats. The sidebar lists the main stat first, then
        any sub-component averages
        """
        # clear side bar layout
        pyani.core.ui.clear_layout(self.averages_layout)

        # push sidebar down
        self.averages_layout.addItem(QtWidgets.QSpacerItem(0, 75))

        # figure out if its measured in time, size, or percent
        stat_type = self.render_data.get_stat_type(self.selected_stat)

        # set the color set based off stat type
        if stat_type is 'gb':
            color_set = self.color_set_warm
        else:
            color_set = self.color_set_cool

        # average based off level - ie sequence, shot, or frame
        if self.levels[self.current_level] == "Frame":
            # average stat for all the frames for this shot
            main_total = self.render_data.stat_data[self.seq][self.shot][self.history]['average'][self.selected_stat]["total"]
            component_totals = self.render_data.stat_data[self.seq][self.shot][self.history]['average'][self.selected_stat]["components"]
        elif self.levels[self.current_level] == "Shot":
            # average stat across all shots in sequence
            main_total = self.render_data.stat_data[self.seq]['average'][self.selected_stat]["total"]
            component_totals = self.render_data.stat_data[self.seq]['average'][self.selected_stat]["components"]
        else:
            # average stat across all sequences in show
            main_total = self.render_data.stat_data['average'][self.selected_stat]["total"]
            component_totals = self.render_data.stat_data['average'][self.selected_stat]["components"]

        # format the total - the average followed by the type such as seconds. Then add a '/' followed by level
        # examples: 25.5s / frame or 30gb / shot
        average_total = QtWidgets.QLabel()
        average_total.setText(
            "<span style='font-size:30pt; font-family:{3};'><b>{0:.2f}</span></b>"
            "<span style='font-size:12pt; font-family:{3};'> {1} / {2}</span>"
                .format(main_total, stat_type, self.levels[self.current_level], self.font_family)
        )
        # add subtitle displaying stat name
        average_total_subtitle = QtWidgets.QLabel()
        average_total_subtitle.setText(
            "<span style='font-size:12pt; font-family:{1};'><b>{0}</b></span>".format(
                self.selected_stat, self.font_family
            )
        )
        average_total_subtitle.setAlignment(QtCore.Qt.AlignCenter)
        self.averages_layout.addWidget(average_total)
        self.averages_layout.addWidget(average_total_subtitle)
        self.averages_layout.addItem(QtWidgets.QSpacerItem(0, 50))

        # now add any components, and format the same as the main total
        for index, component_name in enumerate(self.render_data.get_stat_components(self.selected_stat)):
            label = QtWidgets.QLabel()
            label.setText(
                "<span style='font-size:25pt; font-family:{3};'><b>{0:.2f}</span></b>"
                "<span style='font-size:12pt; font-family:{3};'> {1} / {2}</span>"
                .format(component_totals[index], stat_type, self.levels[self.current_level], self.font_family)
            )
            label_subtitle = QtWidgets.QLabel()
            label_subtitle.setText(
                "<span style='font-size:12pt; color:{0}; font-family:{2};'><b>{1}</b></span>"
                .format(color_set[index].name(), component_name, self.font_family)
            )
            label_subtitle.setAlignment(QtCore.Qt.AlignCenter)
            self.averages_layout.addWidget(label)
            self.averages_layout.addWidget(label_subtitle)
            self.averages_layout.addItem(QtWidgets.QSpacerItem(0, 15))
        self.averages_layout.addStretch(1)

    def _build_history_menu(self):
        """Makes the history menu based off the current seq and shot. If no seq or shot is set, defaults to
        "1"
        """
        self.history_menu.blockSignals(True)
        self.history_menu.clear()

        if self.seq and self.shot:
            for history in self.render_data.get_history(self.seq, self.shot):
                self.history_menu.addItem(history)
        else:
            self.history_menu.addItem("1")
        self.history_menu.blockSignals(False)

