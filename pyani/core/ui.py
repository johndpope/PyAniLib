import os
import sys
import traceback
import shutil
import logging
import pyqtgraph as pg
import numpy as np
from subprocess import Popen, PIPE, STDOUT
import pyani.core.util
import pyani.core.error_logging
import pyani.core.appvars


logger = logging.getLogger()

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore
# qtpy doesn't have fileDialog, so grab from PyQT4
from PyQt4.QtGui import QFileDialog
from PyQt4.QtCore import pyqtSlot, pyqtSignal
from PyQt4.QtCore import QThread


'''
CORE UI ELEMENTS
'''

# COLORS
GOLD = "#be9117"
GREEN = "#397d42"
CYAN = "#429db6"
WHITE = "#ffffff"
YELLOW = QtGui.QColor(234, 192, 25)
RED = QtGui.QColor(216, 81, 81)

# FONTS
FONT_FAMILY = "Century Gothic"
FONT_SIZE_DEFAULT = 10


# try to set to unicode - based reset what QDesigner does
try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


class WorkerSignals(QtCore.QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        `tuple` (exctype, value, traceback.format_exc() )

    result
        `object` data returned from processing, anything

    progress
        `int` indicating % progress

    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class Worker(QtCore.QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param fn: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type fn: function
    :param use_progress_callback: whether to use progress callback
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """
    def __init__(self, fn, use_progress_callback, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        if use_progress_callback:
            self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        """
        Initialize the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exception_type, value = sys.exc_info()[:2]
            self.signals.error.emit((exception_type, value, traceback.format_exc()))
        else:
            # Return the result of the processing
            self.signals.result.emit(result)
        finally:
            # complete
            self.signals.finished.emit()


class CGTDownloadMonitor(QThread):
    """
    Monitors the output from CGT's download process. Looks for lines of output:
    file_total:{number} - gives the total file count before downloading begins
    -->file_size:{number} - gives the number of bytes to download
    -->progress: {number} % - gives the percent of a particular file's download

    Takes a command to execute - should be python interpreter path and then the python file as a list, for example:
    ["C:\cgteamwork\python\python.exe", "C:\PyAniTools\lib\cgt\cgt_download.py"]

    There are two modes

    1. Download a single file - shows progress of the download as percentage of the file size downloaded
    and shows the total file size
    2. Download multiple files - shows progress of the download as a percentage of number of files downloaded and
    shows the total number of files

    Usage:

    create an instance: self.downloader = CGTDownloadMonitor(cmd) or self.downloader = CGTDownloadMonitor()
    if you don't pass a cmd then you need to set self.downloader.download_cmd = cmd.
    run self.downloader.start() to start download via subprocess.
    in the main window make sure you create the slot self.downloader.data_downloaded.connect(slot_function_name)
    in the slot_function, process data as:

        if isinstance(data, basestring):
            if "file_total" in data:
                self.step_label.setText("Downloading {0} files.".format(data.split(":")[1]))
            elif "file_size" in data:
                self.step_label.setText("Downloading {0}.".format(data.split(":")[1]))
            elif "done" in data:
                self.step_label.hide()
                self.progress_bar.hide()
                self.progress_bar.setValue(0)

                # a successful download
                if "done" in data:
                    code here....
                # at the latest - no updates
                else:
                    code here....
        else:
            self.progress_download_bar.setValue(data)

    """
    # signal to fire when have progress to send, can send any python object
    data_downloaded = pyqtSignal(object)

    def __init__(self, cmd=None):
        QThread.__init__(self)
        # cmd to execute
        self.download_cmd = cmd
        # use -u to help with buffer
        self.python_exe = ["C:\Python27\python.exe", "-u"]

    @property
    def download_cmd(self):
        return self.__download_cmd

    @download_cmd.setter
    def download_cmd(self, cmd):
        self.__download_cmd = cmd

    def run(self):
        """
        monitors the subprocess for output from cgt's api callback. Fires a pyqt signal when have data to communicate
        to the main window

        removes old files:
        looks for a string from CGT that has files to remove in the format:
        file_dirs_to_dl#{directory of plugin}@file_names#{list of files separated by comma}
        ex: (note all on one line, put on separate lines below for readability
        file_dirs_to_dl#C:\Users\Patrick\Documents\maya\plug-ins\eyeBallNode\@file_names#C:\Users\Patrick\
        Documents\maya\plug-ins\eyeBallNode\eyeBallNode.py,C:\Users\Patrick\Documents\maya\plug-ins\eyeBallNode\
        plugin_version.json
        """
        process = Popen(self.python_exe + self.download_cmd, shell=True, stdout=PIPE, stderr=STDOUT)
        files_total = 0
        files_downloaded = 0

        # Poll process for new output until finished
        while True:
            next_line = process.stdout.readline()
            if next_line == '' and process.poll() is not None:
                break

            # --------------------------------------------
            # check if any files need to be deleted locally
            # first get the download folders so we can get the local files
            if 'file_dirs_to_dl' in next_line:
                existing_files = []
                file_dirs_next_line = next_line.split("@")[0]
                file_names_next_line = next_line.split("@")[-1]

                # remove 'file_dirs_to_dl'
                temp = file_dirs_next_line.split("#")[-1]
                # the download folders
                dl_dirs = temp.split(",")
                dl_dirs = [dl_dir.replace("\n", "") for dl_dir in dl_dirs]
                dl_dirs = [dl_dir.replace("\r", "") for dl_dir in dl_dirs]
                # list of files locally in download folders
                for dl_dir in dl_dirs:
                    # make sure folder exists
                    if os.path.exists(dl_dir):
                        for root, directories, file_names in os.walk(dl_dir):
                            for directory in directories:
                                existing_files.append(os.path.join(root, directory))
                            for filename in file_names:
                                existing_files.append(os.path.join(root, filename))
                # now check if any local files aren't on CGT
                # remove 'file_list'
                temp = file_names_next_line.split("#")[-1]
                # list of files in CGT
                file_names = temp.split(",")
                # look for any "/" and remove "\r" and "\n"
                file_names = [os.path.normpath(file_name) for file_name in file_names]
                file_names = [file_name.replace("\r", "") for file_name in file_names]
                file_names = [file_name.replace("\n", "") for file_name in file_names]

                for existing_file in existing_files:
                    # look for any files that exist locally but are not in CGT
                    if existing_file not in file_names:
                        if os.path.isfile(existing_file):
                            os.remove(existing_file)
                        else:
                            # only remove directories if empty
                            if not os.listdir(existing_file):
                                shutil.rmtree(existing_file, ignore_errors=True)

            # get the number of files to download
            if 'file_total' in next_line:
                files_total = int(next_line.split(":")[-1])
            # if the file total is greater than 1, then its a file list, and process download completion percentage
            # as files downloaded / file total since cgt can't provide an overall file download progress with multiple
            # files.
            if files_total > 1:
                # fire signal so main window knows number of files
                self.data_downloaded.emit("file_total:{0}".format(files_total))
            # only one file, so we can use cgt's progress
            else:
                if 'file_size' in next_line:
                    # convert bytes to kb, mb, or gb depending on number of digits in bytes
                    bytes_size = float(next_line.split(":")[-1])
                    num_digits = pyani.core.util.number_of_digits(bytes_size)
                    if num_digits < 7:
                        converted_size = "{0} KB".format(bytes_size / 1000.0)
                    elif num_digits < 10:
                        converted_size = "{0} MB".format(bytes_size / 1000000.0)
                    else:
                        converted_size = "{0} GB".format(bytes_size / 1000000000.0)
                    # fire signal so main window knows file size
                    self.data_downloaded.emit("file_size:{0}".format(converted_size))

            # monitor for progress updates
            if 'progress' in next_line:
                percent_done = next_line.split(" ")[1]
                # if there are multiple files, show download progress as files downloaded / files total
                if files_total > 1:
                    if float(percent_done) == 100.0:
                        files_downloaded += 1
                        percent = float(files_downloaded) / float(files_total) * 100.0
                        self.data_downloaded.emit(percent)
                # one file, show actual progress
                else:
                    self.data_downloaded.emit(float(percent_done))

            sys.stdout.write(next_line)
            sys.stdout.flush()

        # finished, check whether anything downloaded or if user has the latest and let main window know
        if files_downloaded == 0:
            # user has latest
            self.data_downloaded.emit("no_updates")
        else:
            # downloaded successfully
            self.data_downloaded.emit("done")

        output = process.communicate()[0]
        exit_code = process.returncode

        if exit_code == 0:
            print output
        else:
            print "error : exit code {0}".format(exit_code)


class BarGraph(pg.GraphicsView):
    """
    Class that provides a single and stacked bar graph implementation based on pyqtgraph's graphics view and
    pyqtgraph's bar graph item (a subclass of graphics item)

    To use, create an instance of the bar graph. If you need to update or change the graph, call update_graph().
    create_graph() is called once to initialize the pyqt graph object - Technical note: pyqtgraph doesn't seem to like
    using a setOpts() if no bars have had values set before greater than 0. That's why we have a create_graph and
    update_graph functions.

    - Allows interaction via mouse clicks. Clicking a bar will emit a single that passes the x value for the bar
    clicked. To use create an instance of this class, and connect your slot / function to its signal.

        Ex:
        bar_graph = BarGraph(options here)
        bar_graph.graph_update_signal.connect(your function)

        The function declaration should be: your_func(x_axis_value) where x_axis_value is the QString passed from
        this class. This class emits the signal in the onClick function.

    - Allows custom labeling for x values. This can be useful for un-even intervals such as 5, 10, 12.5, 15, 19, 20.
    To use just pass a list of strings or numbers where each string or number is the x axis value you want displayed.

    To create a single bar graph, pass a list of numbers in for y_data. To create a stacked bar graph pass a dict
    in the format:
        {
            'total': [list of numbers],
            'components': [ [component #1 list of numbers], ..., [component #n list of numbers] ]
        }

    - Allows custom colors. Colors are specified as:
      For a single bar graph:
            a single pyqt QColor

      For a stacked bar graph:
            {
                'total': pyqt QColor
                'components': [ [component #1 color as a pyqt QColor], [component #n color as a pyqt QColor] ]
            }

    """
    # signal emitted when graph requires an update
    graph_update_signal = pyqtSignal(object)

    def __init__(
            self,
            x_data=None,
            y_data=None,
            x_axis_label="",
            y_axis_label="",
            width=1.0,
            color=QtGui.QColor(150, 150, 150)
    ):
        """
        Creates the initial bar graph
        :param x_data: the x axis data
        :param y_data: the y axis data
        :param x_axis_label: the label for the x axis
        :param y_axis_label: the label for the y axis
        :param width: the width of the bars
        :param color: the color of the bars
        """
        super(BarGraph, self).__init__()

        # --------- options -----------
        # WIDTH OF BARS
        self.bar_width = width
        # COLORS
        self.color = color
        # AXIS LABELS
        self.x_axis_label = x_axis_label
        self.y_axis_label = y_axis_label

        # store options
        # x axis - allows un-even intervals - stores in private variable __x_axis_mapping as a dict
        # maps as {0: 'label1', 2: 'label2', ...}
        if x_data is not None:
            self.x_data = x_data
        else:
            self.x_data = [0.0]
        # y axis - can be a dict for a stacked bar graph or list of numbers for a single bar graph
        if y_data is not None:
            self.y_data = y_data
        else:
            self.y_data = [0.0]

        # the bar graph
        self.__plot_item = pg.PlotItem(labels={'left': self.y_axis_label, 'bottom': self.x_axis_label})
        self.setCentralWidget(self.__plot_item)
        self.bar_graph_item_list = self.create_graph()

        # save the view box
        self.__view_box = self.__plot_item.vb
        self.__view_box.setMouseEnabled(x=True, y=False)
        self.__view_box.enableAutoRange(axis=self.__view_box.XAxis, enable=True)

        self.update_x_axis()

        self.set_slots()

    @property
    def x_axis_label(self):
        """ Get the label for the x axis
        """
        return self.__x_axis_label

    @x_axis_label.setter
    def x_axis_label(self, x_axis_label):
        """ Set the x axis label
        """
        self.__x_axis_label = x_axis_label

    @property
    def y_axis_label(self):
        """ Get the label for the y axis
        """
        return self.__y_axis_label

    @y_axis_label.setter
    def y_axis_label(self, y_axis_label):
        """ Set the y axis label
        """
        self.__y_axis_label = y_axis_label

    @property
    def x_data(self):
        """ Get the mapping of x axis labels to actual values
        """
        return self.__x_data

    @x_data.setter
    def x_data(self, mapping):
        """ Set the x axis labels, can be any string list, maps as {0: 'label1', 2: 'label2', ...}
        """
        if mapping:
            self.__x_data = dict(enumerate(mapping))

    @property
    def y_data(self):
        """ Get the y axis data
        """
        return self.__y_data

    @y_data.setter
    def y_data(self, data):
        """ Set the y data
        """
        self.__y_data = data

    @property
    def bar_width(self):
        """ Get the width of the bars
        """
        return self.__bar_width

    @bar_width.setter
    def bar_width(self, width):
        """ Set the width of the bars, where width is an integer or float
        """
        self.__bar_width = width

    def set_slots(self):
        self.scene().sigMouseClicked.connect(self.onClick)
        self.scene().sigMouseMoved.connect(self.onMove)

    def onClick(self, event):
        """
        process mouse clicks by getting the x axis value and emitting a custom signal called graph_update_signal.
        the class that created this bar graph object can listen for this signal.
        :param event: the mouse event
        """
        pos = QtCore.QPointF(event.scenePos())
        mouse_point = self.__view_box.mapSceneToView(pos)
        key = round(mouse_point.x())
        if key in self.x_data:
            self.graph_update_signal.emit(str(self.x_data[key]))

    def onMove(self, pos):
        # TODO: implement
        pass
        """
        pos = QtCore.QPointF(pos)
        mouse_point = self.__view_box.mapSceneToView(pos)
        key = round(mouse_point.y())
        """

    def create_graph(self):
        """
        Creates the bar graph, whether its single or stacked.
        :return: a list of the bar graph items (BarGraphItem objects from the pyqtgraph lib). These are essentially
        the bar data across the x axis.
        """
        bar_graph_item_list = []

        # stacked bar graph
        if isinstance(self.y_data, dict):
            # the color for the total, put in a list because we will be adding the other bar colors
            colors = [self.color['total']]
            # add the component colors to the list
            colors.extend(self.color['components'])
            # this puts the data into the format pyqtgraph wants
            bar_graph_rows = self._format_stacked_bar_data()
            # now make the actual stacked bars
            for row_index in xrange(0, len(bar_graph_rows)):
                bar_graph_item = pg.BarGraphItem(
                    x=self.x_data.keys(),
                    height=bar_graph_rows[row_index],
                    width=self.bar_width,
                    brush=colors[row_index]
                )
                bar_graph_item_list.append(bar_graph_item)
                self.__plot_item.addItem(bar_graph_item)
        # single bar graph
        else:
            bar_graph_item_list.append(
                pg.BarGraphItem(
                    x=self.x_data.keys(), height=self.y_data, width=self.bar_width, brush=self.color
                )
            )
            self.__plot_item.addItem(bar_graph_item_list[0])

        return bar_graph_item_list

    def update_graph(
            self,
            x_data=None,
            y_data=None,
            x_axis_label=None,
            y_axis_label=None,
            width=None,
            color=None
    ):
        """
        Updates the bar graph with new data. Pyqt graph works best with using the setOpts method to update the bars,
        opposed to deleting or clearing and recreating (doesn't refresh properly). If a value is not passed for a
        parameter, then the current value is used.
        :param x_data: the new x axis data
        :param y_data: the new y axis data
        :param x_axis_label: the new label for the x axis
        :param y_axis_label: the new label for the y axis
        :param width: the width of the bars
        :param color: the color of the bars
        """
        # store options - only ones that user gives, otherwise keep current values
        if width is not None:
            self.bar_width = width
        if color is not None:
            self.color = color
        if x_data is not None:
            self.x_data = x_data
        if y_data is not None:
            self.y_data = y_data
        if x_axis_label is not None:
            self.x_axis_label = x_axis_label
        if y_axis_label is not None:
            self.y_axis_label = y_axis_label

        # number of bars needed is the total (which is 1 bar) + the number of components or sub bars. Note if its not
        # a stacked bar graph component length will be zero
        num_bars_needed = 1 + len(self.y_data['components'][0])

        # check if need to create more bars
        if len(self.bar_graph_item_list) < num_bars_needed:
            bars_to_create = num_bars_needed - len(self.bar_graph_item_list)
            for i in xrange(0, bars_to_create):
                bar_graph_item = pg.BarGraphItem(
                    x=[0.0],
                    height=[0.0],
                    width=1.0,
                )
                self.bar_graph_item_list.append(bar_graph_item)
                self.__plot_item.addItem(bar_graph_item)

        # the color for the total, put in a list because we will be adding the other bar colors
        colors = [self.color['total']]
        # add the component colors to the list
        colors.extend(self.color['components'])

        # reset bars to a height of zero
        for bar in self.bar_graph_item_list:
            bar.setOpts(
                x=[0.0],
                height=[0.0]
            )
        # set data for single and stacked bar graphs
        if isinstance(self.y_data, dict):
            # stacked bar graph data formatted
            bar_graph_rows = self._format_stacked_bar_data()
            # now make the actual stacked bars
            for bar_index in xrange(0, len(bar_graph_rows)):
                self.bar_graph_item_list[bar_index].setOpts(
                    x=self.x_data.keys(),
                    height=bar_graph_rows[bar_index],
                    width=self.bar_width,
                    brush=colors[bar_index]
                )
        # single bar graph
        else:
            self.bar_graph_item_list[0].setOpts(
                x=self.x_data.keys(),
                height=self.y_data,
                width=self.bar_width,
                brush=self.color[0]
            )
        # update the labels
        self.__plot_item.setLabel('left', text=self.y_axis_label)
        self.__plot_item.setLabel('bottom', text=self.x_axis_label)
        # update the x axis mapping
        self.update_x_axis()

    def update_x_axis(self):
        """
        Updates the x axis with the latest x axis mapping
        """
        x_axis = self.__plot_item.getAxis('bottom')
        x_axis.setTicks([self.x_data.items()])

    def _format_stacked_bar_data(self):
        """
        Formats the data for stacked bar graphs
        :return: a 2D list of data that the pyqtgraph bar graph class will accept. Format:
        [ python list that is the size of the number of sequences, shots or frames] each element of
        the list is a bar that is [is the size of the number of stacked bars or total + number of components]
        """
        bar_graph_rows = []
        # stacked bar graph
        if isinstance(self.y_data, dict):
            # total is the overall height of the bar
            total = self.y_data['total']
            # convert the components to a numpy array - easier to add - we switch the axis so that in the 2d array
            # rows become cols, cols become rows. Makes it so that the rows can be fed to the bar graph
            components_rows = np.stack(self.y_data['components'], axis=1)

            # the data to send to the bar graph class, where each index is a row of bar graph data. Start with total,
            # its the largest number. If the components don't add up to the total, the unknown amount will shade the
            # color specified for total, otherwise you won't see the total at all.
            bar_graph_rows = [total]

            # loop through and add up the components so that each component sits on top of the other (no overlap)
            # The idea is to build a list or array of the bars so that bar2 sits on bar1, bar3 sits on bar2 and so on.
            for i in xrange(0, len(components_rows)):
                # this is the size of the x axis
                summed_rows = np.array([0.0] * len(total))
                # we loop through the components, adding up
                for j in xrange(i, len(components_rows)):
                    summed_rows += components_rows[j]
                bar_graph_rows.append(np.ndarray.tolist(summed_rows))
        return bar_graph_rows


class TranslucentWidgetSignals(QtCore.QObject):
    """
    Close signal for pop up window to communicate with main window calling pop-up
    """
    # SIGNALS
    CLOSE = pyqtSignal()


class TranslucentWidget(QtWidgets.QWidget):
    """
    Creates a transparent window with user size and colors. Works like this:
    Given a window A:
    -----------------
    |               |
    |               |
    |       A       |
    |               |
    -----------------
    we draw over all of A, but making B whatever transparency/color we want, and same for C where C is "the pop-up"
    -----------------
    |     -----     |
    |  B  | C |     |
    |     -----     |
    |               |
    -----------------
    """

    def __init__(self, parent=None):
        super(TranslucentWidget, self).__init__(parent)

        # make the window frameless
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # ui elements
        self.close_btn = QtWidgets.QPushButton(self)
        self.close_btn.setText("x")
        font = QtGui.QFont()
        font.setPixelSize(18)
        font.setBold(True)
        self.close_btn.setFont(font)
        self.close_btn.setFixedSize(30, 30)

        # set attributes defaults - colors, window size

        # window bg and border color (outside/behind popup window - the one pop up covers)
        self.__fill_color_outside_popup = QtGui.QColor(0, 0, 0, 0)
        self.__pen_color_outside_popup = QtGui.QColor(0, 0, 0, 0)
        # popup window bg and border color
        self.__fill_color_popup = QtGui.QColor(150, 150, 150, 150)
        self.__pen_color_popup = QtGui.QColor(150, 150, 150, 255)
        # close button color
        self.close_btn.setStyleSheet("background-color: rgb(0, 0, 0, 0); color: rgb(0, 0, 0, 255)")

        # size
        self.__popup_width = 200
        self.__popup_height = 200

        # the text in the window
        self.__text = "<font size='4'>Html formatted text here</font>"

        self.set_slots()
        self.SIGNALS = TranslucentWidgetSignals()

    def set_slots(self):
        self.close_btn.clicked.connect(self._on_close)

    def set_win_size(self, width, height):
        """
        Set pop up size
        :param width: width as an integer
        :param height: height as an integer
        """
        self.__popup_width = width
        self.__popup_height = height

    def set_colors(self, fill, border, btn_color):
        """
        Set the bg and border color of the pop, as well as the btn color
        :param fill: rgba as a tuple i.e (255, 255, 255, 255)
        :param border: rgba as a tuple i.e (255, 255, 255, 255)
        :param btn_color: rgba as a tuple i.e (255, 255, 255, 255)
        """
        self.__fill_color_outside_popup = QtGui.QColor(0, 0, 0, 0)
        self.__pen_color_outside_popup = QtGui.QColor(0, 0, 0, 0)
        # popup window bg and border color
        self.__fill_color_popup = QtGui.QColor(fill[0], fill[1], fill[2], fill[3])
        self.__pen_color_popup = QtGui.QColor(border[0], border[1], border[2], border[3])
        # close button color
        self.close_btn.setStyleSheet(
            "background-color: rgb(0, 0, 0, 0); color: rgb({0}, {1}, {2}, {3})".format(
                btn_color[0],
                btn_color[1],
                btn_color[2],
                btn_color[3]
            )
        )

    def resizeEvent(self, event):
        s = self.size()
        # get right edge of popup
        right_edge = int(s.width() / 2 + self.__popup_width / 2)
        # get top edge of popup
        top_edge = int(s.height() / 2 - self.__popup_height / 2)
        # put close button at top right of window
        self.close_btn.move(right_edge - 35, top_edge)

    def set_text(self, text):
        self.__text = text

    def paintEvent(self, event):
        """Draw the window - note that we are really drawing over any existing window, filling the entire space. We
        just make parts transparent. see class doc string
        """
        # get current window size
        s = self.size()
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing, True)
        # draw bg window, one behind popup
        qp.setPen(self.__pen_color_outside_popup)
        qp.setBrush(self.__fill_color_outside_popup)
        qp.drawRect(0, 0, s.width(), s.height())
        # draw popup
        qp.setPen(self.__pen_color_popup)
        qp.setBrush(self.__fill_color_popup)
        # left edge
        left_edge = int(s.width() / 2 - self.__popup_width / 2)
        # top edge
        top_edge = int(s.height() / 2 - self.__popup_height / 2)
        qp.drawRoundedRect(left_edge, top_edge, self.__popup_width, self.__popup_height, 5, 5)
        # draw text - use html
        td = QtGui.QTextDocument()
        td.setHtml(self.__text)
        qp.translate(left_edge, top_edge)
        td.drawContents(qp, QtCore.QRectF(0, 0, self.__popup_width, self.__popup_height))
        qp.end()

    def _on_close(self):
        self.SIGNALS.CLOSE.emit()


class AniQMainWindow(QtWidgets.QMainWindow):
    """
    Builds a QMain Window with the given title, icon and optional width and height
    Provides the main window widget, called self.main_win
    Provides the main layout for the window - self.main_layout which is a QVBoxlayout
    Adds two ui elements, version as a Qlabel and a help link to documentation as a custom image button class
    at the top of the window.

    Handles version management displaying a message when out of date or no version available

    Drag and drop support - also supports drag and drop into tabs with custom widgets. To use this functionality:
        1. create a method as usual that is given to the drop_event_wrapper in this class
        2. In that wrapper call the tabs class (pyani.core.ui.TabsWidgets) drag_and_drop method
        3. In the tabs class it will pass along the dropped data to the custom widget which needs a drag_and_drop
        method that receives the data
        EX:
        I create a gui subclassing this class:
            class AniTestWindow(pyani.core.ui.AniQMainWindow) and add the methods:
                   def dropEvent(self, e):
                        self.drop_event_wrapper(e, self.tabs_drag_and_drop)
                   def tabs_drag_and_drop(self, file_names):
                        self.tabs.drag_and_drop(file_names, TestWidget)

            - self.tabs is an instance of pyani.core.ui.TabsWidgets
            - TestWidget is the custom widget class name. Not the instance, but the actual type

        I create a custom widget called class TestWidget(QtWidgets.QWidget) and add the method:
        def drag_and_drop(self, data)
            # process the data in some way....


    Creates a msg window class variable which allows apps to display pop up dialog warnings,
    errors, info, etc.. - uses pyani.core.ui.QtMsgWindow class
    Provides some spacing and font widgets:
        self.titles : 14 pt size font bold
        self.bold_font : a bold font - default QT pt size
        self.v_spacer = QSpacerItem 35 px high
        self.empty_space = QSpacerItem with width 1 px and height 1 px
        self.horizontal_spacer = QSpacerItem 50 px width
        self.title_vert_spacer = QSpacerItem 15 px high
    :param win_title : the window's title as a string
    :param win_icon : absolute path to a png or icon (.ico) file
    :param tool_metadata : information for tool
    :param tool_mngr : a pyani.core.mngr.tool object for opening help doc
    :param width : optional width of the window
    :param height: optional height of the window
    :param has_tabs: optional parameter enabling tab support
    :param error_logging : optional error log (pyani.core.error_logging.ErrorLogging object) from trying
           to create logging in main program
    :param show_help: optional boolean whether to show a link to a confluence help page
    :param disable_version: optional boolean if True doesn't show or get version info.
    """
    def __init__(
            self,
            win_title,
            win_icon,
            tool_metadata,
            tool_mngr,
            width=600,
            height=600,
            has_tabs=False,
            error_logging=None,
            show_help=True,
            disable_version=False
    ):
        super(AniQMainWindow, self).__init__()

        # if no error logging object, create a dummy object to grab the root log dir. Don't need a real app name
        # to get this
        if not error_logging:
            error_logging = pyani.core.error_logging.ErrorLogging("Generic App")
            log_name = error_logging.root_log_dir
        else:
            log_name = error_logging.log_file_name

        self.tool_name = tool_metadata['name']
        self.tool_dir = tool_metadata['dir']
        self.tool_type = tool_metadata['type']
        self.tool_category = tool_metadata['category']
        self.tool_mngr = tool_mngr
        self.show_help = show_help
        app_vars = pyani.core.appvars.AppVars()

        # COMMON UI ELEMENTS

        # setup title and icon
        self.win_utils = QtWindowUtil(self)
        self.setWindowTitle(win_title)
        self.win_utils.set_win_icon(win_icon)

        # tab support
        self.has_tabs = has_tabs

        # main widget for window
        self.main_win = QtWidgets.QWidget()

        # pop-up windows
        self.msg_win = QtMsgWindow(self)
        self.progress_win = QtMsgWindow(self)

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT

        # version info
        self.vers_label = QtWidgets.QLabel()

        # main layout
        self.main_layout = QtWidgets.QVBoxLayout()

        # set font size and style for title labels
        self.titles = QtGui.QFont()
        self.titles.setPointSize(14)
        self.titles.setBold(True)
        self.bold_font = QtGui.QFont()
        self.bold_font.setBold(True)
        # spacer to use between sections
        self.v_spacer = QtWidgets.QSpacerItem(0, 35)
        self.empty_space = QtWidgets.QSpacerItem(1, 1)
        self.horizontal_spacer = QtWidgets.QSpacerItem(50, 0)
        self.title_vert_spacer = QtWidgets.QSpacerItem(0, 15)

        # help doc button
        if show_help:
            self.btn_help_doc = pyani.core.ui.ImageButton(
                "{0}\help_off.png".format(app_vars.local_pyanitools_core_dir),
                "{0}\help_on.png".format(app_vars.local_pyanitools_core_dir),
                "{0}\help_on.png".format(app_vars.local_pyanitools_core_dir),
                size=(148, 38)
            )
            self.btn_help_doc.clicked.connect(self._open_help_doc)

        # VERSION MANAGEMENT

        # check if version should be shown
        if not disable_version:
            # try to load cgt meta data for tool type which has version info for the local files, this is the
            # version on disk locally, could be different than cloud version
            try:
                self.local_version = self.tool_mngr.get_tool_local_version(self.tool_dir, self.tool_name)
                self.cgt_version = self.tool_mngr.get_tool_newest_version(
                    self.tool_type,
                    self.tool_category,
                    self.tool_name
                )
                if self.local_version == self.cgt_version:
                    self.vers_label.setText(
                        "<span style='font-size:{0}pt; font-family:{1}; color:#ffffff;'>Version: {2}</span>".format(
                            self.font_size,
                            self.font_family,
                            self.local_version
                        )
                    )
                else:

                    if not self.cgt_version:
                        self.cgt_version = "server version: n/a"

                    self.vers_label.setText(
                        "<span style='font-size:{0}pt; font-family:{1}; color:#ffffff;'>Version (out of date): </span>"
                        "<span style='font-size:{0}pt; font-family:{1}; color:{2};'>local version: {3}</span>"
                        "<span style='font-size:{0}pt; font-family:{1}; color:#ffffff;'> / {4}</span>".format(
                            self.font_size,
                            self.font_family,
                            RED.name(),
                            self.local_version,
                            self.cgt_version
                        )
                    )
                logging.info(
                    "User version: {0}, Latest Version {1}".format(
                        self.local_version,
                        self.cgt_version
                    )
                )
            except (TypeError, KeyError, ValueError) as e:
                logger.exception("Type, Key, or Value error loading version info: {0}".format(e))
                self.vers_label.setText(
                    "<span style='font-size:{0}pt; font-family:{1}; color:{2};'>Version Data Unavailable</span>".format(
                        self.font_size,
                        self.font_family,
                        RED.name()
                    )
                )

                self.msg_win.show_warning_msg(
                    "Version Warning",
                    "There was a problem loading the version information. You can continue, but please "
                    "file a jira and attach the latest log file from here {0}. The error reported is: {1}".format(
                        log_name,
                        e
                    )
                )
        else:
            self.vers_label.setText("")

        # create the layout and add version, plus create signals/slots
        self._build_ui()
        # set default window size
        self.resize(width, height)
        # center the window
        center(self)

    def add_layout_to_win(self):
        """Adds the main layout to the window, called by inheriting classes
        """
        # add the layout to the main app widget
        self.main_win.setLayout(self.main_layout)

    def create_layout(self):
        """Virtual function, require implementation, call add_layout_to_win at end to add main layout
        to the main window
        """
        raise NotImplementedError()

    def set_slots(self):
        """Virtual function, require implementation
        """
        raise NotImplementedError()

    def dragEnterEvent(self, e):
        """
        provides an event which is sent to the target widget as dragging action enters it.
        :param e: mime data of the event
        """
        if e.mimeData().hasUrls:
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        """
        called used when the drag and drop action is in progress.
        :param e: mime data of the event
        """
        if e.mimeData().hasUrls:
            e.accept()
        else:
            e.ignore()

    @staticmethod
    def drop_event_wrapper(e, func):
        """
        wraps functionality of dropEvent(e), generic use lets other windows use drag and drop with
        whatever function they need. passes list of files to the function func
        To use implement dropEvent(self, e) in deriving class, and call this function passing the mime data e and
        function func which takes a list of string filenames. also set call self.setAcceptsDrops(True)
        :param e: mime data of the event
        :param func : function to call to process mime data, should accept a list of strings representing filenames
        """
        if e.mimeData().hasUrls:
            e.setDropAction(QtCore.Qt.CopyAction)
            e.accept()
            # Workaround for OSx dragging and dropping
            file_names = []
            for url in e.mimeData().urls():
                file_names.append(str(url.toLocalFile()))
            func(file_names)
        else:
            e.ignore()

    def _open_help_doc(self):
        """Open help doc
        """
        error = self.tools_mngr.open_help_doc(self.tool_name)
        if error:
            self.msg_win.show_error_msg("Confluence Error", error)

    def _build_ui(self):
        """Builds the UI widgets, slots and layout
        """
        self._create_layout()
        self.setCentralWidget(self.main_win)

    def _create_layout(self):
        """Adds version widget and help doc button to main layout
        """
        # add version to right side of screen
        h_layout_vers = QtWidgets.QHBoxLayout()

        if self.show_help:
            h_layout_vers.addWidget(self.btn_help_doc)

        h_layout_vers.addStretch(1)
        h_layout_vers.addWidget(self.vers_label)
        self.main_layout.addLayout(h_layout_vers)
        self.main_layout.addItem(QtWidgets.QSpacerItem(1, 30))


class FileDialog(QFileDialog):
    '''
    This function allows both files and folders to be selected. QFileDialog doesn't support
    this functionality in pyqt 4.

    Usage:

    dialog = FileDialog.FileDialog()
    dialog.exec_()
    get selection - returns a list
    selection = dialog.get_selection()
    '''
    def __init__(self, *args, **kwargs):
        super(FileDialog, self).__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.selectedFiles = []

        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.ExistingFiles)

        # get all buttons and find one labeled open, connect custom event
        btns = self.findChildren(QtWidgets.QPushButton)
        self.openBtn = [x for x in btns if 'open' in str(x.text()).lower()][0]
        self.openBtn.clicked.disconnect()
        self.openBtn.clicked.connect(self.open_clicked)

        # grab the tree view
        self.tree = self.findChild(QtWidgets.QTreeView)

    def open_clicked(self):
        '''
        Gets the selection in the file dialog window. Stores selection in a class variable.
        :arg: self : Just the class
        '''
        indices = self.tree.selectionModel().selectedIndexes()
        files = []
        for i in indices:
            if i.column() == 0:
                item = i.data()
                # this is needed to handle script conversion to standalone exe. Item executed
                # via python is a string, but is a QVariant in standalone exe. So first check
                # for a QVariant, then convert that to a string which gives a QString. Convert that
                # to python string using str()
                if isinstance(item, QtCore.QVariant):
                    itemName = str(item.toString())
                else:
                    itemName = str(item)
                files.append(os.path.join(str(self.directory().absolutePath()), itemName))
        self.selectedFiles = files
        self.close()
        logger.info("File dialog class un-normalized selection: {0}".format(", ".join(self.selectedFiles)))

    def get_selection(self):
        '''
        Getter function to return the selected files / folders as a list
        :return a list of files and folders selected in the file dialog normalized to os path system convention
        and sorted
        '''
        # make sure paths get normalized so they are correct
        normalized_paths = [os.path.normpath(file_name) for file_name in self.selectedFiles]
        sorted_normalized_paths = sorted(normalized_paths)
        logger.info("File dialog class normalized selection: {0}".format(", ".join(sorted_normalized_paths)))
        # sort the paths
        return sorted_normalized_paths


class QHLine(QtWidgets.QFrame):
    """
    Creates a horizontal line
    :arg: a color in qt css style
    """
    def __init__(self, color):
        super(QHLine, self).__init__()
        # override behavior of style sheet
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setStyleSheet("background-color:{0};".format(color))
        self.setLineWidth(1)


class QVLine(QtWidgets.QFrame):
    """
    Creates a vertical line. Takes a color and optional size, defaults to width 1
    """
    def __init__(self, color, size=None):
        """
        :param color: a color in qt css style
        :param size: optional size
        """
        super(QVLine, self).__init__()
        # override behavior of style sheet
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setStyleSheet("background-color:{0};".format(color))
        self.setLineWidth(1)
        if size:
            self.resize(size[0], size[1])
        else:
            self.setMinimumWidth(1)
            self.setMaximumWidth(1)


class QtMsgWindow(QtWidgets.QMessageBox):
    """
    Class to display QtMessageBox Windows
    Takes the main window upon creation so that pop up appears over it
    """
    def __init__(self, main_win):
        super(QtMsgWindow, self).__init__()
        # create the window and tell it to parent to the main window
        self.msg_box = QtWidgets.QMessageBox(parent=main_win)
        # member variable declaring the type of mesg box, needed because a msg box without buttons must call
        # a different method than close() to close it.
        self.msg_box_type = None

    def hide(self):
        """Hide the msg box
        """
        self.msg_box.hide()

    def show_error_msg(self, title, msg):
        """
        Show a popup window with an error
        :param title: the window title
        :param msg: the message to the user
        """
        self._show_message_box(title, self.Critical, msg)

    def show_warning_msg(self, title, msg):
        """
        Show a popup window with a warning
        :param title: the window title
        :param msg: the message to the user
        """
        self._show_message_box(title, self.Warning, msg)

    def show_question_msg(self, title, msg):
        """
        Opens a qt pop-up window with a yes and no button
        :param title: the window title
        :param msg: the message to the user
        :return: True if user presses Yes, False if user presses No
        """
        response = self.msg_box.question(self, title, msg, self.Yes | self.No)
        center(self.msg_box)
        if response == self.Yes:
            return True
        else:
            return False

    def show_info_msg(self, title, msg):
        """
        Show a popup window with information
        :param title: the window title
        :param msg: the message to the user
        """
        self._show_message_box(title, self.Information, msg)

    def show_msg(self, title, msg):
        self.msg_box.setWindowTitle(title)
        self.msg_box.setIcon(self.NoIcon)
        self.msg_box.setText(msg)
        self.msg_box.setStandardButtons(self.msg_box.NoButton)
        self.msg_box.show()
        self.msg_box_type = "no_btns"

    def close(self):
        """
        Closes the msg box. Calls done(0) for msg boxes with no buttons - found this via a qt message board, not sure
        why but no buttons needs this not close(). If a button is present then close() works
        """
        if self.msg_box_type == "no_btns":
            self.msg_box.done(0)
        else:
            self.msg_box.close()

    def _show_message_box(self, title, icon, msg):
        """
        Show a popup window
        :param title: the window title
        :param icon: icon to show - information, warning, critical, etc...
        :param msg: the message to the user
        """
        self.msg_box_type = "std"
        self.msg_box.setWindowTitle(title)
        self.msg_box.setIcon(icon)
        self.msg_box.setText(msg)
        self.msg_box.setStandardButtons(self.msg_box.Ok)
        self.msg_box.show()
        center(self.msg_box)


class QtInputDialogMenu(QtWidgets.QDialog):
    """
    Class that provides a popup window with a menu of options, optional preference checkbox and an ok and cancel
    button
    :param parent_win: the window calling this popup
    :param title: the window title as a string
    :param option_label: the text label next to the menu as a string
    :param option_list: the menu text options as a list
    :param width: optional - the width of the window
    :param height: optional - the height of the window
    :param modal: optional - whether the window is modal (can't select the main window) or non modal
    :param pref: optional - whether to display the preference checkbox as a boolean
    :param pref_label: optional - required if pref=True, text next to checkbox
    :param pref_state: optional - default state of checkbox, defaults to reset
    :param pref_desc: optional - a text description if the user hovers over the check box
    """
    def __init__(
            self,
            parent_win,
            title,
            option_label,
            option_list,
            width=None,
            height=None,
            modal=True,
            pref=False,
            pref_label=None,
            pref_state=False,
            pref_desc=""
    ):
        super(QtInputDialogMenu, self).__init__(parent=parent_win)
        if width:
            self.setMinimumWidth(width)
        if height:
            self.setMinimumHeight(height)
        # the selection from the menu option
        self.__selection = None
        # menu options
        self.menu_cbox = QtWidgets.QComboBox()
        self.options_label = option_label
        self.options = option_list
        # preference options if provided
        self.has_pref = pref
        if self.has_pref and pref_label is None:
            self.pref_label = "No label provided."
        else:
            self.pref_label = pref_label
        self.pref_default_state = pref_state
        self.pref_desc = pref_desc
        self.pref_cbox = None
        # actions
        self.btn_ok = QtWidgets.QPushButton("Ok")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        # create window
        self.setWindowTitle(title)
        self.setModal(modal)
        self.create_layout()
        self.set_slots()

    @property
    def selection(self):
        """Return the user selection
        """
        return str(self.__selection)

    def pref_checked(self):
        """Return state of the checkbox for preferences, if preferences are used
        """
        if self.has_pref:
            return self.pref_cbox.isChecked()

    def create_layout(self):
        """Creates the window layout
        """
        layout = QtWidgets.QVBoxLayout()
        # menu
        for option in self.options:
            self.menu_cbox.addItem(option)
        menu_label = QtWidgets.QLabel(self.options_label)
        menu_layout = QtWidgets.QHBoxLayout()
        menu_layout.addWidget(menu_label)
        menu_layout.addWidget(self.menu_cbox)
        layout.addLayout(menu_layout)

        # preferences
        if self.has_pref:
            pref_layout = QtWidgets.QHBoxLayout()
            pref_label, self.pref_cbox = pyani.core.ui.build_checkbox(
                self.pref_label,
                self.pref_default_state,
                self.pref_desc
            )
            pref_layout.addWidget(self.pref_cbox)
            pref_layout.addWidget(pref_label)
            layout.addLayout(pref_layout)

        # ok and cancel buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def set_slots(self):
        """Button actions when pressed
        """
        self.btn_ok.clicked.connect(self.ok)
        self.btn_cancel.clicked.connect(self.cancel)

    def ok(self):
        """Saves the current selected text in the menu
        """
        self.__selection = self.menu_cbox.currentText()
        self.close()

    def cancel(self):
        """Closes the window
        """
        self.close()


class QtWindowUtil:
    """
    Class of utility functions common to all qt windows
    Takes the main window
    """

    def __init__(self, main_win):
        self.__win = main_win

    def set_win_icon(self, img):
        """
        Sets the window icon
        :param img: path to an image for the icon
        """
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(_fromUtf8(img)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.__win.setWindowIcon(icon)


class ImageButton(QtWidgets.QAbstractButton):
    """
    Creates a pyqt button that uses images (a png, jpeg, gif or other supported Qt format) and
    has 3 states - reset, hover, pressed
    All images are absolute file paths
    :param image: image when mouse is not over the button
    :param image_hover: image when mouse is over the button
    :param image_pressed: image when button pressed
    :param size: size of the images as a tuple (width, height)
    :param parent: parent widget, defaults to none
    """
    def __init__(self, image, image_hover, image_pressed, size=(32, 32), parent=None):
        super(ImageButton, self).__init__(parent)
        self.pixmap = QtGui.QPixmap(image)
        self.pixmap_hover = QtGui.QPixmap(image_hover)
        self.pixmap_pressed = QtGui.QPixmap(image_pressed)
        self.size = size
        self.set_slots()

    def set_slots(self):
        self.pressed.connect(self.update)
        self.released.connect(self.update)

    def paintEvent(self, event):
        pix = self.pixmap_hover if self.underMouse() else self.pixmap
        if self.isDown():
            pix = self.pixmap_pressed
        painter = QtGui.QPainter(self)
        painter.drawPixmap(event.rect(), pix)

    def set_image(self, state, image):
        """
        set the image for the specified state - off, hover, pressed
        :param state:
        :param image:
        :return:
        """
        if state == "pressed":
            self.pixmap_pressed = QtGui.QPixmap(image)
        elif state == "hover":
            self.pixmap_hover = QtGui.QPixmap(image)
        else:
            self.pixmap = QtGui.QPixmap(image)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def sizeHint(self):
        return QtCore.QSize(self.size[0], self.size[1])


class SliderWidget(QtWidgets.QSlider):
    def mousePressEvent(self, event):
        super(SliderWidget, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.LeftButton:
            val = self.pixel_pos_to_range_value(event.pos())
            self.setValue(val)

    def pixel_pos_to_range_value(self, pos):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderHandle, self)

        if self.orientation() == QtCore.Qt.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == QtCore.Qt.Horizontal else pr.y()
        return QtWidgets.QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin,
                                                        sliderMax - sliderMin, opt.upsideDown)


class CheckboxTreeWidgetItem(object):
    """
    Class of tree items. represents a row of text in a qtreewidget
    Accepts a list of text (the columns) and corresponding text colors. Defaults to white if
    no color given.
    ex: items = ["text1","text2"], colors=None or colors=[None, QtCore.Qt.red]
    """
    def __init__(self, items, colors=None):
        self.__columns = []

        for index in range(0, len(items)):
            # make sure colors given and not None
            if colors:
                # get the color
                color = QtGui.QColor(colors[index])
                # if color is none, set to white
                if not color:
                    color = QtCore.Qt.white
            # no colors given set to white
            else:
                color = QtCore.Qt.white

            item = {"text": items[index], "color": color}
            self.__columns.append(item)

    def col_count(self):
        """Column count - ie length of the list
        """
        return len(self.__columns)

    def text(self, index):
        """
        Text at the specified column index
        :param index: column number
        :return: the text as a string
        """
        return self.__columns[index]["text"]

    def color(self, index):
        """
        Color of the text at the specified column index
        :param index: column number
        :return: a QColor
        """
        return self.__columns[index]["color"]


class CheckboxTreeWidget(QtWidgets.QTreeWidget):
    """
    Qt tree custom class with check boxes. Supports multiple columns. Only supports one level deep, ie parent->child
    not parent->child->child....
    """
    def __init__(self, tree_items=None, columns=None, expand=True, checked=False):
        """
        Builds a self.tree of checkboxes with control over text color. Note allows creation without building tree
        for when tree is built later using user selections.
        :param tree_items: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = [list of CheckboxTreeWidgetItems] }
        :param columns: number of columns in a tree row
        :param expand: show the tree in expanded view
        :param checked: whether the checkboxes should be checked on by default
        """
        super(CheckboxTreeWidget, self).__init__()
        # spacing between columns
        self.__col_space = 50
        self.build_checkbox_tree(tree_items, columns, expand, checked)
        self.itemExpanded.connect(self._resize_on_expand)

    def build_checkbox_tree(self, tree_items, columns, expand=True, checked=False):
        """
        Builds a self.tree of checkboxes with control over text color
        :param tree_items: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = list of CheckboxTreeWidgetItems }
        :param columns: number of columns in a tree row
        :param expand: show the tree in expanded view, default true
        :param checked: whether the checkboxes should be checked on by default
        """
        # root doesn't have any info, hide it
        self.header().hide()

        if tree_items:
            self.setColumnCount(columns)
            # go through tree and build
            for tree_item in tree_items:
                parent = QtWidgets.QTreeWidgetItem(self)
                root_item = tree_item["root"]
                # build main column rows
                for col_index in range(0, root_item.col_count()):
                    parent.setTextColor(col_index, root_item.color(col_index))
                    parent.setText(col_index, root_item.text(col_index))
                parent.setFlags(parent.flags() | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsUserCheckable)
                # build children rows if they exist - keys will be 2 if they exist
                if len(tree_item.keys()) > 1:
                    child_items = tree_item["children"]
                    for child_item in child_items:
                        child = QtWidgets.QTreeWidgetItem(parent)
                        child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
                        for col_index in range(0, child_item.col_count()):
                            child.setTextColor(col_index, child_item.color(col_index))
                            child.setText(col_index, child_item.text(col_index))
                        if checked:
                            child.setCheckState(0, QtCore.Qt.Checked)
                        else:
                            child.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    if checked:
                        parent.setCheckState(0, QtCore.Qt.Checked)
                    else:
                        parent.setCheckState(0, QtCore.Qt.Unchecked)
            if expand:
                self.expandAll()
            # resize columns to fit contents better, but skip last column
            for col in range(0, columns-1):
                self.resizeColumnToContents(col)
                self.setColumnWidth(col, self.columnWidth(col) + self.__col_space)

    def set_checked(self, items_to_check):
        """
        Checks on the specified items. Handles flat trees and trees with parent/child
        :param items_to_check: a list of dict objects in format:
        {
            'parent': None if flat tree, otherwise give parent name
            'item name': text to find
        }
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            for item_to_check in items_to_check:
                # check if there is a parent, ie item to check is a child
                if item_to_check['parent']:
                    # see if the text matches and parent matches for the item
                    if item_to_check['item name'] == str(item.text(0)) and \
                            str(item.parent().text(0)) == item_to_check['parent']:
                        item.setCheckState(0, QtCore.Qt.Checked)
                # no parent
                else:
                    if item_to_check['item name'] == str(item.text(0)):
                        item.setCheckState(0, QtCore.Qt.Checked)
            iterator += 1

    @staticmethod
    def get_item_at_position(item, column):
        """
        Returns the text of the row/column clicked on
        :param item: the row, ie tree item as pyqt4 QTreeWidget item
        :param column: the column as an integer
        :return: the text as a string
        """
        return str(item.text(column))

    @staticmethod
    def get_parent(item):
        """
        Gets the parent of the row/item
        :param item: the row, ie tree item as pyqt4 QTreeWidget item
        :return: the parent name as a string or none if no parent
        """
        try:
            return str(item.parent().text(0))
        except AttributeError:
            return None

    def get_tree_checked(self):
        """
        Finds the selected tree members
        :return: a list of the checked items
        """
        checked = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.Checked)
        while iterator.value():
            item = iterator.value()
            checked.append(str(item.text(0)))
            iterator += 1
        return checked

    def get_tree_unchecked(self):
        """
        Finds the non selected tree members
        :return: a list of the un-checked items
        """
        unchecked = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.NotChecked)
        while iterator.value():
            item = iterator.value()
            unchecked.append(item)
            iterator += 1
        return unchecked

    def expand_all(self):
        """
        Simply expands the tree
        """
        self.expandAll()
        self._resize_on_expand()

    def collapse_all(self):
        """
        Collapse Tree
        """
        self.collapseAll()

    def update_item(self, existing_text, updated_item):
        """
        Updates a tree item
        :param existing_text: the existing item text
        :param updated_item: the updated item as a CheckboxTreeWidgetItem
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.text(0) == existing_text:
                for col_index in range(0, updated_item.col_count()):
                    item.setTextColor(col_index, updated_item.color(col_index))
                    item.setText(col_index, updated_item.text(col_index))
            iterator += 1

    def clear_all_items(self):
        """Clear the tree
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.All)
        while iterator.value():
            iterator.value().takeChildren()
            iterator += 1
        i = self.topLevelItemCount()
        while i > -1:
            self.takeTopLevelItem(i)
            i -= 1

    def hide_items(self, item_list):
        """
        Hides rows based on the list given
        :param item_list: a list of pyqt4 Tree Widget items - more robust, don't have to worry about parents and same
        named children
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            tree_item = iterator.value()
            for item in item_list:
                if tree_item == item:
                    tree_item.setHidden(True)
            iterator += 1

    def show_items(self, item_list, show_all=False):
        """
        Shows rows based on the list given
        :param item_list: a list of pyqt4 Tree Widget items - more robust, don't have to worry about parents and same
        named children
        :param show_all: optional boolean indicating all items should be shown. Ignores item_list when this flag
        is True
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            tree_item = iterator.value()
            if show_all:
                tree_item.setHidden(False)
            else:
                for item in item_list:
                    if tree_item == item:
                        tree_item.setHidden(False)
            iterator += 1

    def _resize_on_expand(self):
        """
        Resize when children shown, otherwise text may be clipped
        """
        # resize columns to fit contents better, but skip last column
        for col in range(0, self.columnCount() - 1):
            self.resizeColumnToContents(col)
            self.setColumnWidth(col, self.columnWidth(col) + self.__col_space)


class TabContentWidget(QtWidgets.QWidget):
    """
    The content that goes in a tab. Used with the TabWidget class.

    Takes the following parameters:
        - name : name of the tab, shows at top of tab
        - layout : the content of the tab, pass the layout containing all the widgets
    """
    def __init__(self, layout=None, name=""):
        super(TabContentWidget, self).__init__()
        # name is shown in the tab, at the top
        self.name = name
        if layout:
            self.setLayout(layout)
        else:
            self.setLayout(QtWidgets.QVBoxLayout())

    @property
    def name(self):
        """Return the name of the tab
        """
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the tab
        """
        self.__name = name

    def update_content(self, new_layout):
        """
        Updates the tab content
        :param new_layout: a pyqt layout object containing the content/widgets
        """
        # to change the layout we need to temporarily assign the current layout or get an error, QT will then delete
        # the widget with our current layout since its scope is this function. Then we assign the new layout.
        current_layout = self.layout()
        QtWidgets.QWidget().setLayout(current_layout)
        self.setLayout(new_layout)


class TabBarWidget(QtWidgets.QTabBar):
    """
    Tab bar that has a plus button floating to the right of the tabs. Subclasses the built in QTabBar and adds
    a plus button so the user can create tabs
    """

    # the user clicked the plus to create a new tab
    plus_clicked_signal = pyqtSignal()

    def __init__(self, parent):
        super(TabBarWidget, self).__init__()
        self.setParent(parent)

        # plus button
        self.plus_button_size = 20
        self.plus_button = QtWidgets.QPushButton("+")
        self.plus_button.setParent(self)
        self.plus_button.setMaximumSize(self.plus_button_size, self.plus_button_size)
        self.plus_button.setMinimumSize(self.plus_button_size, self.plus_button_size)
        # Move to the correct location - the right of the last tab created
        self.move_plus_button()

        self.set_slots()

    def set_slots(self):
        self.plus_button.clicked.connect(self.plus_clicked_signal.emit)

    def sizeHint(self):
        """Return the size of the TabBar with increased width for the plus button.
        """
        size_hint = QtWidgets.QTabBar.sizeHint(self)
        width = size_hint.width()
        height = size_hint.height()
        # add the size of the button plus a small buffer to account for the plus button at the end of the tab bar
        return QtCore.QSize(width + (self.plus_button_size + 5), height)

    def resizeEvent(self, event):
        """Resize the widget and make sure the plus button is in the correct location.
        """
        super(TabBarWidget, self).resizeEvent(event)
        self.move_plus_button()

    def tabLayoutChange(self):
        """This virtual handler is called whenever the tab layout changes.
        If anything changes make sure the plus button is in the correct location.
        """
        super(TabBarWidget, self).tabLayoutChange()
        self.move_plus_button()

    def move_plus_button(self):
        """Move the plus button to the correct location - after the last existing tab
        """
        # Find the width of all of the tabs
        total_width_tabs = 0
        for i in range(self.count()):
            total_width_tabs += self.tabRect(i).width()

        # Set the plus button location in a visible area
        tab_bar_height = self.geometry().top()
        tab_bar_width = self.width()
        # check for scroll buttons when there are more tabs to show than the window size.
        # if there are more tabs than can be displayed, show just to the left of the scroll buttons
        if total_width_tabs > tab_bar_width:
            self.plus_button.move(tab_bar_width - 54, tab_bar_height)
        else:
            self.plus_button.move(total_width_tabs, tab_bar_height)


class TabsWidget(QtWidgets.QTabWidget):
    """
    A tabs widget class that supports multiple tabs, and the ability to create tabs dynamically

    Usage: Create an instance of the TabsWidget class:
    tabs = TabsWidget() or tabs = TabsWidget(dynamic_tab_bar=True)

    Takes:
    :param dynamic_tab_bar: defaults to False, when True displays a plus button to the right of the tab(s) to create
    more tabs
    :param tab_name: name of the first tab, defaults to blank
    :param tabs_can_close: whether tabs can be closed, defaults to True
    """

    tab_created_signal = pyqtSignal(object)

    def __init__(self, dynamic_tab_bar=False, tab_name="", tabs_can_close=True):
        super(TabsWidget, self).__init__()

        self.setMinimumSize(800, 400)

        # set tabs properties
        #
        self.setMovable(True)
        self.tabs_can_close = tabs_can_close

        # Tab Bar - allows you to create tabs by pressing a button. enable by passing dynamic_tab_bar = True.
        # otherwise user can't create tabs
        self.is_dynamic_tab_bar = dynamic_tab_bar
        if self.is_dynamic_tab_bar:
            self.tab = TabBarWidget(self)
            self.setTabBar(self.tab)

        # create the initial tab
        self.add_tab(tab_name)
        self.create_layout()
        self.set_slots()

    def create_layout(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

    def set_slots(self):
        if self.is_dynamic_tab_bar:
            self.tab.plus_clicked_signal.connect(self.add_tab)
            self.tab.tabMoved.connect(self.tab.move_plus_button)
        self.tabCloseRequested.connect(self.removeTab)

    def drag_and_drop(self, dropped_data, custom_widget):
        """
        Adds drag and drop support for tabs containing custom widgets. This just checks the layout for the class type
        of the custom widget, and if found, sends it the data.

        ****** NOTE ******
        The custom widget must implement a method named drag_and_drop that takes a parameter that will be the data that
        was dragged and dropped

        :param dropped_data: the data being dragged and dropped into the window
        :param custom_widget: a class type, for example if I have: class TestWidget(QtWidgets.QWidget), i would pass
        TestWidget. Notice no parenthesis are used, this is not an instance but the type
        :return: True if passed the data, false if not
        """
        current_widget = self._find_widget(custom_widget)
        if current_widget:
            current_widget.drag_and_drop(dropped_data)
            return True
        else:
            return False

    def key_input(self, key, custom_widget):
        """
        Adds key input support for tabs containing custom widgets. This just checks the layout for the class type
        of the custom widget, and if found, sends it the key.

        ****** NOTE ******
        The custom widget must implement a method named key_input that takes a parameter that will be the key that
        the user pressed

        :param key: the key pressed by the user as a Pyqt key binding (ex: QtCore.Qt.Key_I)
        :param custom_widget: a class type, for example if I have: class TestWidget(QtWidgets.QWidget), i would pass
        TestWidget. Notice no parenthesis are used, this is not an instance but the type
        :return: True if passed the key, false if not
        """
        current_widget = self._find_widget(custom_widget)
        if current_widget:
            current_widget.key_input(key)
            return True
        else:
            return False

    def add_tab(self, tab_name="", layout=None):
        """
        Adds a tab page.
        :param tab_name: the name to show at the top of the tab page
        :param layout: the layout for the tab page containing the content
        """
        if self.count() > 0 and self.tabs_can_close:
            self.setTabsClosable(True)
        else:
            self.setTabsClosable(False)

        # this is the tab content page. Holds whatever content/widgets that are part of the layout passed in.
        widget = TabContentWidget(name=tab_name, layout=layout)
        self.addTab(widget, widget.name)
        # lets main window know a tab was created and passes the tab index, always the last one
        self.tab_created_signal.emit(self.count() - 1)

    def removeTab(self, p_int):
        """
        Removes a tab page as long as there are 2 or more tabs. Ensures at least one tab exists
        :param p_int: the tab number (can get with self.currentIndex())
        """
        super(TabsWidget, self).removeTab(p_int)
        if self.count() > 1 and self.tabs_can_close:
            self.setTabsClosable(True)
        else:
            self.setTabsClosable(False)

    def update_tab_name(self, name):
        """
        Updates the active tab's name
        :param name: name as a string
        """
        self.setTabText(self.currentIndex(), name)

    def update_tab(self, layout):
        """
        Updates the tab content for the active tab
        :param layout: the new layout containing the new content/widgets
        """
        self.currentWidget().update_content(layout)

    def _find_widget(self, widget):
        """
        Finds the widget in the layout
        :param widget: a widget class
        :return: the widget if found, otherwise None
        """
        # number of widgets in the layout
        index = self.currentWidget().layout().count()
        while index >= 0:
            # get the current widget, use itemAt, which can then call widget() to get the widget
            current_layout_item = self.currentWidget().layout().itemAt(index)
            if current_layout_item:
                current_widget = current_layout_item.widget()
                if isinstance(current_widget, widget):
                    return current_widget
            index -= 1
        return None


def build_checkbox(label, state, directions):
    """
    Builds a check box with label, state and directions
    :param label: the label to the left of the check box
    :param state: True if checked, False if unchecked
    :param directions: the text when you hover over the check box
    :return: the label, check box
    """
    label = QtWidgets.QLabel(label)
    cbox = QtWidgets.QCheckBox()
    cbox.setChecked(state)
    cbox_directions = directions
    cbox.setToolTip(cbox_directions)
    return label, cbox


def center(win):
    """
    Center the window on screen where the mouse is.
    :param win: the qt window to center
    """
    frame_gm = win.frameGeometry()
    # Use the screenNumber function to determine which screen the mouse is current active on.
    screen = QtWidgets.QApplication.desktop().screenNumber(QtWidgets.QApplication.desktop().cursor().pos())
    # Find the screenGeometry of that monitor and the center point of that screen
    center_point = QtWidgets.QApplication.desktop().screenGeometry(screen).center()
    frame_gm.moveCenter(center_point)
    win.move(frame_gm.topLeft())


def clear_layout(layout):
    """
    clears a layout. we use a while loop because when you are removing children from the layout,
    you are modifying the index # of each child item in the layout. That's why you'll run into problems using a
    for i in range() loop. One option is to reverse loop, but a while is more straightforward
    :param layout: the layout
    """
    if layout:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
