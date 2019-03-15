import logging
import os
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
from PyQt4.QtCore import pyqtSignal, pyqtSlot

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
            1000,
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

        self.render_data = pyani.render.log.data.AniRenderData()
        self.seq = None
        self.shot = None
        self.current_level = 0
        self.levels = ["Sequence", "Shot", "Frame"]

        self.nav_crumbs_font_size = 4
        self.nav_crumbs = QtWidgets.QLabel("<b><font size={0}>Show</font></b>".format(self.nav_crumbs_font_size))
        self.stats_menu = QtWidgets.QComboBox()
        for stat in self.render_data.stats:
            self.stats_menu.addItem(stat)
        self.averages_list = None
        self.average_title = QtWidgets.QLabel()
        self.btn_test = QtWidgets.QPushButton("Dive")

        self.create_layout()
        self.set_slots()

    def create_layout(self):
        main_layout = QtWidgets.QHBoxLayout()

        graph_layout = QtWidgets.QVBoxLayout()

        graph_header_layout = QtWidgets.QHBoxLayout()
        graph_header_layout.addWidget(self.nav_crumbs)
        graph_header_layout.addStretch(1)
        graph_header_layout.addWidget(self.btn_test)
        stats_label = QtWidgets.QLabel("Render Stat")
        graph_header_layout.addWidget(stats_label)
        graph_header_layout.addWidget(self.stats_menu)

        graph_layout.addLayout(graph_header_layout)

        averages_layout = QtWidgets.QVBoxLayout()
        self.average_title.setText("Average Per {0}".format(self.levels[self.current_level]))
        averages_layout.addWidget(self.average_title)

        main_layout.addLayout(graph_layout)
        main_layout.addLayout(averages_layout)
        self.main_layout.addLayout(main_layout)
        self.add_layout_to_win()

    def set_slots(self):
        self.btn_test.clicked.connect(self.nav_forwards)
        self.nav_crumbs.linkActivated.connect(self.nav_backwards)

    def nav_backwards(self, link):
        if self.current_level > 0:
            self.current_level = 0
            if link == "#Show":
                nav_str = "<font size={0}><b>Show</b></font>".format(self.nav_crumbs_font_size)
            else:
                self.current_level = 1
                nav_str = "<font size={0}>" \
                          "<a href='#Show'><span style='text-decoration: none; color: #ffffff'>Show</span></a> > " \
                          "<a href='#Seq'><span style='text-decoration: none; color: #ffffff'><b>Seq ###</b></span></a>" \
                          "</font>".format(self.nav_crumbs_font_size)

            self.nav_crumbs.setText(nav_str)

    def nav_forwards(self):
        if self.current_level < len(self.levels):
            self.current_level += 1
            if self.levels[self.current_level] == "Shot":
                nav_str = "<font size={0}>" \
                          "<a href='#Show'><span style='text-decoration: none; color: #ffffff'>Show</span></a> > " \
                          "<b>Seq ###</b>" \
                          "</font>".format(self.nav_crumbs_font_size)
            else:
                nav_str = "<font size={0}>" \
                          "<a href='#Show'><span style='text-decoration: none; color: #ffffff'>Show</span></a> > " \
                          "<a href='#Seq'><span style='text-decoration: none; color: #ffffff'>Seq ###</span></a> > " \
                          "<b>Shot ###</b>" \
                          "</font>".format(self.nav_crumbs_font_size)
            self.nav_crumbs.setText(nav_str)
