import os
import logging
import pyani.core.ui
import pyani.core.mngr.tools
import pyani.core.appvars
import collections

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore
from PyQt4.QtCore import pyqtSignal

logger = logging.getLogger()


class AniTaskList:
    """
    The purpose of this class is to provide a list of tasks that can be run in order, sequentially, and let this
    class manage running those. It uses signal/slots of pyqt to do this. A function runs, fires a signal when it
    completes or errors, which causes this class to then respond and either report the error or run the next
    function in the list. Provides a post task list option to run task(s) after the main tasks complete

    Doesn't handle errors directly, connects to methods that get called when error occurs

    Uses a generalized format for task list. See task_list_to_run under init() for format.

    USAGE:

    1. Create an instance, for ex:
        self.task_list = [
            # make tools cache
            {
                'func': self.tools_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.tools_mngr.finished_cache_build_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local tools cache."
            }
        ]

    2. Start the process using start_task_list()
    """

    def __init__(
            self,
            task_list_to_run,
            error_callback=None,
            ui_callback=None,
            post_tasks_to_run=None
        ):
        """
        :param task_list_to_run: a list of dicts that hold task information. The format is:
            {
                'func': this is the function to call - do not put parenthesis, ie do
                _create_asset_list_for_update_report, not _create_asset_list_for_update_report()
                'params': any parameters, pass as a list
                'finish signal': the pyqt signal to connect to for when a method finishes
                'error signal': the pyqt signal to connect to for when a method errors
                'thread task': True means put task in thread, False does not. Only thread non threaded methods. If
                               the method in 'func' creates threads, set this to False otherwise errors will occur.
                'desc': string description describing what this method does. shown in activity log.
            }
        :param post_tasks_to_run: optional task(s) to call when main task(s) finish. a list of dicts in format:
            {
                'func': this is the function(s) to call, pass as a list
                'params': any parameters, pass as a list
            }
        Note optionally you can later call the set_post_tasks method - useful if the post tasks depend on this windows
        creation
        :param error_callback: optional error callback/function for when errors occur
        :param ui_callback: optional ui callback to update a ui
        """
        # setup threading
        self._thread_pool = QtCore.QThreadPool()
        logger.info("Multi-threading with maximum %d threads" % self._thread_pool.maxThreadCount())

        # this tells the next_step_in_task_list() method to not get any more tasks from the task list defined by
        # the class variable task_list
        self._stop_tasks = False
        # function to call if error occurs
        self._error_callback = error_callback
        # function to call to update a ui
        self._ui_callback = ui_callback

        # method vars for setup and updating
        self._task_list = task_list_to_run
        self._method_to_run = None
        self._method_params = None
        self._method_finish_signal = None
        self._method_error_signal = None

        # tasks to run after the main task list runs
        self._post_tasks = post_tasks_to_run

    def set_error_method(self, func):
        """Set the error callback function when errors occur"""
        self._error_callback = func

    def set_post_tasks(self, post_tasks):
        """
        Call this to set task(s) to run after the main task list finishes
        :param post_tasks:  a list of dicts in format:
            {
                'func': this is the function(s) to call, pass as a list
                'params': any parameters, pass as a list
            }
        """
        self._post_tasks = post_tasks

    def add_task(self, task):
        self._task_list.append(task)

    def stop_tasks(self):
        """Stops tasks from running"""
        self._stop_tasks = True

    def start_tasks(self):
        """Starts the task list by getting first task"""
        self._get_next_task_to_run()

    def is_task_remaining(self):
        """Returns true if tasks remain, False if no more tasks"""
        if self._task_list:
            return True
        else:
            return False

    def next_step_in_task_list(self):
        """
        Increments to the next step in the update or setup process task list, provided via the class variable
        task_list. If no more tasks are left, shows the activity report and hides step and progress ui labels
        """
        # check for more steps that need to be run
        if self._task_list and not self._stop_tasks:
            # add to activity log as success
            self._get_next_task_to_run()
        # no more steps
        else:
            # run the post task(s)
            if self._post_tasks:
                for task in self._post_tasks:
                    func = task['func']
                    params = task['params']
                    func(*params)

    def _get_next_task_to_run(self):
        """
        Gets a task from the task list and runs it in a thread
        """
        if self._task_list:
            # update the ui with the first step / task
            if self._ui_callback:
                self._ui_callback()
            task_list_package = self._task_list.pop(0)
            self._method_to_run = task_list_package['func']
            self._method_params = task_list_package['params']
            self._method_finish_signal = task_list_package['finish signal']
            self._method_error_signal = task_list_package['error signal']
            self._task_desc = task_list_package['desc']

            # some tasks are already multi-threaded, so only thread tasks that have the 'thread task' key in task list
            # set to True
            if task_list_package['thread task']:
                # thread task
                worker = pyani.core.ui.Worker(
                    self._method_to_run,
                    False,
                    *self._method_params
                )

                self._thread_pool.start(worker)
                # slot that is called when a thread finishes, passes the active_type so calling classes can
                # know what was updated and the save cache method so that when cache gets updated it can be
                # saved
                worker.signals.finished.connect(self.next_step_in_task_list)
                if self._error_callback:
                    worker.signals.error.connect(self._error_callback)
            # already threaded, don't thread
            else:
                self._method_finish_signal.connect(self.next_step_in_task_list)
                if self._error_callback:
                    self._method_error_signal.connect(self._error_callback)
                self._method_to_run(*self._method_params)


class AniTaskListWindow(pyani.core.ui.AniQMainWindow):
    """
    The purpose of this class is to provide a simple gui interface for running a list of tasks. Displays
    progress, an app description, and the steps being run. Shows an activity log after running. Uses the AniTaskList
    to handle running the tasks

    Inherits from AniQMainWindow

    USAGE:

    1. Create an instance, for ex:
        self.task_list = [
            # make tools cache
            {
                'func': self.tools_mngr.sync_local_cache_with_server,
                'params': [],
                'finish signal': self.tools_mngr.finished_cache_build_signal,
                'error signal': self.tools_mngr.error_thread_signal,
                'thread task': False,
                'desc': "Created local tools cache."
            }
        ]

        # create a ui (non-interactive) to run setup
        AniTaskListWindow(
            error_logging,
            progress_list,
            "Setup",
            "Setup",
            self.task_list
        )
    2. Start the process using start_task_list()
    """

    def __init__(
            self,
            error_logging,
            progress_list,
            win_title,
            metadata,
            task_list_to_run,
            app_description=None,
            post_tasks_to_run=None,
            asset_mngr=None,
            tools_mngr=None):
        """
        :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
        to create logging in main program
        :param progress_list: a list of strings describing the steps being run
        :param win_title: title of the window
        :param metadata: metadata like app name, where it's located. See AniQMainWindow for metadata values
        :param task_list_to_run: a list of dicts that hold task information. The format is:
            {
                'func': this is the function to call - do not put parenthesis, ie do _create_asset_list_for_update_report, not _create_asset_list_for_update_report()
                'params': any parameters, pass as a list
                'finish signal': the pyqt signal to connect to for when a method finishes
                'error signal': the pyqt signal to connect to for when a method errors
                'thread task': True means put task in thread, False does not. Only thread non threaded methods. If
                               the method in 'func' creates threads, set this to False otherwise errors will occur.
                'desc': string description describing what this method does. shown in activity log.
            }
        :param app_description: optional text (can be html formmatted) to display for what this app does
        :param post_tasks_to_run: optional task(s) to call when main task(s) finish. a list of dicts in format:
            {
                'func': this is the function(s) to call, pass as a list
                'params': any parameters, pass as a list
            }
        Note optionally you can later call the set_post_tasks method - useful if the post tasks depend on this windows
        creation
        :param asset_mngr: a pyani.core.mngr.asset object
        :param tool_mngr: a pyani.core.mngr.tool object
        """
        tools_mngr_for_ani_win = pyani.core.mngr.tools.AniToolsMngr()

        # pass win title, icon path, app manager, width and height
        super(AniTaskListWindow, self).__init__(
            win_title,
            "images\\setup.ico",
            metadata,
            tools_mngr_for_ani_win,
            450,
            700,
            error_logging,
            show_help=False,
            disable_version=False
        )

        if tools_mngr:
            self.tools_mngr = tools_mngr
        else:
            self.tools_mngr = None

        if asset_mngr:
            self.asset_mngr = asset_mngr
        else:
            self.asset_mngr = None

        # check if logging was setup correctly in main()
        if error_logging.error_log_list:
            errors = ', '.join(error_logging.error_log_list)
            self.msg_win.show_warning_msg(
                "Error Log Warning",
                "Error logging could not be setup because {0}. You can continue, however "
                "errors will not be logged.".format(errors)
            )

        # save the setup class for error logging to use later
        self.error_logging = error_logging

        # the description if provided to show in the window for what this app does
        self.app_description = app_description

        # the list of steps/tasks descriptions
        self.progress_list = progress_list
        # current step/task
        self.step_num = 0
        # total number of steps / tasks
        if self.progress_list:
            self.step_total = len(self.progress_list)
        else:
            self.step_total = 0
        # logs what runs successfully and errors
        self.activity_log = []
        # shown at end as a description of what ran
        self.task_desc = None

        # indicates an error occurred
        self.error_occurred = False

        self.task_mngr = AniTaskList(
            task_list_to_run,
            error_callback=self.process_error,
            post_tasks_to_run=post_tasks_to_run,
            ui_callback=self.update_ui
        )

        # gui vars
        self.progress_label = QtWidgets.QLabel("")
        self.step_label = QtWidgets.QLabel("")
        self.close_btn = QtWidgets.QPushButton("Close Window", self)
        self.activity_report = QtWidgets.QTextEdit("")
        self.activity_report.setFixedWidth(400)
        self.activity_report.setFixedHeight(350)

        # hide at start, shown when all tasks done
        self.activity_report.hide()

        self.create_layout()
        self.set_slots()

    def create_layout(self):
        h_layout_btn = QtWidgets.QHBoxLayout()
        h_layout_btn.addStretch(1)
        h_layout_btn.addWidget(self.close_btn)
        h_layout_btn.addItem(QtWidgets.QSpacerItem(10, 1))
        self.main_layout.addLayout(h_layout_btn)
        self.main_layout.addItem(QtWidgets.QSpacerItem(1, 25))

        desc_label = QtWidgets.QLabel(self.app_description)
        desc_label.setMaximumWidth(self.frameGeometry().width())
        desc_label.setWordWrap(True)
        self.main_layout.addWidget(desc_label)
        self.main_layout.addItem(QtWidgets.QSpacerItem(1, 30))

        h_layout_progress = QtWidgets.QHBoxLayout()
        h_layout_progress.addStretch(1)
        sub_layout_progress = QtWidgets.QVBoxLayout()
        sub_layout_progress.addWidget(self.step_label)
        sub_layout_progress.addItem(QtWidgets.QSpacerItem(1, 10))
        sub_layout_progress.addWidget(self.progress_label)
        sub_layout_progress.setAlignment(self.step_label, QtCore.Qt.AlignHCenter)
        sub_layout_progress.setAlignment(self.progress_label, QtCore.Qt.AlignHCenter)
        sub_layout_progress.addItem(QtWidgets.QSpacerItem(1, 20))
        h_layout_progress.addLayout(sub_layout_progress)
        h_layout_progress.addStretch(1)
        self.main_layout.addLayout(h_layout_progress)

        self.main_layout.addItem(QtWidgets.QSpacerItem(1, 20))
        h_layout_report = QtWidgets.QHBoxLayout()
        h_layout_report.addStretch(1)
        h_layout_report.addWidget(self.activity_report)
        h_layout_report.addStretch(1)
        self.main_layout.addLayout(h_layout_report)
        self.main_layout.addStretch(1)

        self.add_layout_to_win()

    def set_slots(self):
        self.close_btn.clicked.connect(self.close_window)

    def close_window(self):
        """
        Prevent any more tasks from running and close window. Asks user before closing.
        """
        if self.task_mngr.is_task_remaining():
            if self.error_occurred:
                response = self.msg_win.show_question_msg(
                    "Warning",
                    "Tasks are still running, however it seems a task has errors or stalled. "
                    "Close the window?"
                )
            else:
                response = self.msg_win.show_question_msg(
                    "Warning",
                    "Tasks are still running. Are you sure you want to close the window?"
                )
            if response:
                self.task_mngr.stop_tasks()
                self.close()
        else:
            self.close()

    def set_post_tasks(self, post_tasks):
        """
        Call this to set task(s) to run after the main task list finishes
        :param post_tasks:  a list of dicts in format:
            {
                'func': this is the function(s) to call, pass as a list
                'params': any parameters, pass as a list
            }
        """
        self.task_mngr.set_post_tasks(post_tasks)

    def start_task_list(self):
        """
        Starts running the first task/method in the task list provided via the class variable task_list
        """
        # run the first task
        self.task_mngr.start_tasks()

    def update_ui(self):
        """
        Updates the ui elements
        """
        if self.progress_list:
            self.step_num += 1
            self.step_label.setText(
                "<p align='center'>"
                "<font style='font-size:10pt; font-family:{0}; color: #ffffff;'>S T E P</font><br>"
                "<font style='font-size:20pt; font-family:{0}; color: #ffffff;'>{1} / {2}</font>"
                "</p>".format(
                    self.font_family,
                    self.step_num,
                    self.step_total
                )
            )
            self.progress_label.setText(
                "<span style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>{2}</span>".format(
                    self.font_size,
                    self.font_family,
                    self.progress_list.pop(0)
                )
            )

    def process_error(self, error):
        """
        Collects any errors and adds to activity log
        :param error: the error that occurred
        """
        # add to activity log with red text and formatting
        error_msg = (
            "<span style='font-size:{2}pt; font-family:{0}; color: {1};'><strong>ERROR</strong><br><br></span>"
            "<span style='font-size:{2}pt; font-family:{0}; color: #ffffff;'>The following step errored: {3}.<br><br>"
            " The error is:</br> {4}</span>"
            .format(
                self.font_family,
                pyani.core.ui.RED.name(),
                self.font_size,
                self.progress_label.text(),
                error
            )
        )
        self.task_mngr.stop_tasks()
        self.error_occurred = True
        self.activity_log.append(error_msg)
        logger.error(error_msg)
        self.display_activity_log()

    def add_activity_log_item(self, item):
        """
        Adds a new item to the log
        :param item: a string item, can contain html formatting
        """
        self.activity_log.append(item)

    def display_activity_log(self):
        """
        Show the activity (i.e. install or update steps) that ran or failed
        """
        if not self.error_occurred:
            success_msg = "<span style='font-size:10pt; font-family:{0}; color: {1};'><strong>" \
                          "Setup completed successfully.</strong><br><br></span>".format(
                                self.font_family,
                                pyani.core.ui.GREEN
                          )
        else:
            success_msg = ""

        self.activity_report.setText(
            "<span style='font-size:18pt; font-family:{0}; color: #ffffff;'>ACTIVITY LOG <br><br></span>{1}"
            "<font style='font-size:10pt; font-family:{0}; color: #ffffff;'>"
            "<ul><li>{2}</ul>"
            "</font>".format(
                self.font_family,
                success_msg,
                '<li>'.join(self.activity_log)
            )
        )
        self.activity_report.show()


class AniReportCore(QtWidgets.QDialog):
    """
    Core functionality for all reports, takes the parent window and a title
    """
    # general signal for successful tasks
    finished_signal = pyqtSignal()
    # error message for other classes to receive when doing any local file operations
    error_thread_signal = pyqtSignal(object)

    def __init__(self, parent_win, title, width=800, height=900):
        """
        :param parent_win: window opening this window
        """
        super(AniReportCore, self).__init__(parent=parent_win)

        self.app_vars = pyani.core.appvars.AppVars()

        # font styling
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size_heading_1 = "20"
        self.font_size_heading_2 = "16"
        self.font_size_heading_3 = "11"
        self.font_size_body = "10"

        # image for line
        self.h_line_img = "C:\\PyAniTools\\core\\images\\h_line_cyan.png"

        self.setWindowTitle(title)
        self.win_width = width
        self.setMinimumWidth(self.win_width)
        self.setMinimumHeight(height)
        self.btn_close = QtWidgets.QPushButton("Close")
        self.btn_close.clicked.connect(self.close)

        layout = QtWidgets.QVBoxLayout()

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        self.content = QtWidgets.QTextEdit()
        self.content.setReadOnly(True)
        layout.addWidget(self.content)

        self.setLayout(layout)

    def show_content(self, html_content):
        """
        Sets the content to display in the pyqt Text edit widget and fires a finished signal
        :param html_content: a string of html
        """
        self.content.setHtml(html_content)
        # do show before finished signal, otherwise might move on before executing display of window
        self.show()
        self.finished_signal.emit()


class AniAssetTableReport(AniReportCore):
    """
    A table report that is customizable. Can control headings/number of columns, cellspacing, column width

    headings are a string list and define the number of columns

    column widths are a string list of percents for the size of each column

    row data is a list of tuples, each list item represents a row of data, so the tuple size must match the len of the
    headings list
    """

    def __init__(self, parent_win, cellspacing=5):
        """
        :param parent_win: window opening this window
        :param cellspacing: amount of cellspacing
        """
        super(AniAssetTableReport, self).__init__(parent_win, "Review Assets Download Report", width=1500)
        self.cellspacing = cellspacing
        self.headings = None
        self.col_widths = None
        self.data = None

    def generate_table_report(self):
        """
        Creates an html table for reporting data
        """
        # create header row
        html_content = "<table cellspacing='{0}' border='0'>".format(self.cellspacing)
        html_content += "<tr style='font-size:{0}pt; font-family:{1}; color:{2};'>".format(
                            self.font_size_heading_2,
                            self.font_family,
                            pyani.core.ui.CYAN
                        )

        if not self.headings:
            self.headings = ["Could not build headings"]
            self.col_widths = ["100"]
            self.data = ["Heading build error, could not construct data portion of table."]

        for index, heading in enumerate(self.headings):
            html_content += "<td width='{0}%'>".format(self.col_widths[index])
            html_content += heading
            html_content += "</td>"
        html_content += "</tr>"

        # add spacer row
        html_content += "<tr>"
        for _ in self.headings:
            html_content += "</td>&nbsp;</td>"
        html_content += "</tr>"

        if self.data:
            for data in self.data:
                html_content += "<tr style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>".format(
                    self.font_size_body,
                    self.font_family
                )
                for item in data:
                    html_content += "<td>"
                    html_content += item
                    html_content += "</td>"
                html_content += "</tr>"

        html_content += "</table>"
        self.show_content(html_content)


class AniAssetUpdateReport(AniReportCore):
    """
    Creates a window with a report of assets that have been added, modified or removed. Displays as html. General
    format is:
    Modified Assets
        category (such as rig, audio, etc...)
            asset name : version (if available)

    New Assets
        ....

    Deleted Assets
        ....
    """

    def __init__(self, parent_win):
        """
        :param parent_win: window opening this window
        """
        super(AniAssetUpdateReport, self).__init__(parent_win, "Asset Update Report")

        self.app_vars = pyani.core.appvars.AppVars()

        # dictionary for displaying the assets by category in the following order:
        # rigs, audio, gpu cache, maya tools then pyanitools
        self.assets_grouped_by_cat = collections.OrderedDict()
        self.assets_grouped_by_cat["rig"] = {
                'display name': 'Rigs',
                'assets': []
        }
        self.assets_grouped_by_cat["audio"] = {
                'display name': 'Audio',
                'assets': []
        }
        self.assets_grouped_by_cat["model/cache"] = {
                'display name': 'GPU Cache',
                'assets': []
        }

        self.assets_grouped_by_cat["scripts"] = {
                'display name': 'Maya Scripts',
                'assets': []
        }
        self.assets_grouped_by_cat["plugins"] = {
                'display name': 'Maya Plugins',
                'assets': []
        }
        self.assets_grouped_by_cat["apps"] = {
                'display name': 'PyAniTools Apps',
                'assets': []
        }
        self.assets_grouped_by_cat["core"] = {
                'display name': 'PyAniTools Core Files',
                'assets': []
        }
        self.assets_grouped_by_cat["lib"] = {
                'display name': 'PyAniTools Library Files',
                'assets': []
        }
        self.assets_grouped_by_cat["shortcuts"] = {
                'display name': 'PyAniTools App Shortcuts',
                'assets': []
        }

    def generate_asset_update_report(self, asset_mngr=None, tools_mngr=None):
        """
        Gets the assets that have changed, been added, or removed for all assets (tools, show, shot) and shows the
        report. Sorts the assets by type, putting show and shot assets first, then tool assets
        :param asset_mngr: an asset manager object - pyani.core.mngr.assets
        :param tools_mngr: a tool manager object - pyani.core.mngr.tools
        """
        # see pyani.core.mngr.core.find_new_and_updated_assets() for format of dicts
        if asset_mngr:
            assets_added, assets_modified, assets_deleted = asset_mngr.find_changed_assets()
        else:
            assets_added = dict()
            assets_modified = dict()
            assets_deleted = dict()

        if tools_mngr:
            tools_added, tools_modified, tools_deleted = tools_mngr.find_changed_assets()
        else:
            tools_added = dict()
            tools_modified = dict()
            tools_deleted = dict()

        # combine assets
        assets_added.update(tools_added)
        assets_modified.update(tools_modified)
        assets_deleted.update(tools_deleted)

        self.display_asset_update_report(assets_added, assets_modified, assets_deleted)

    def display_asset_update_report(self, assets_added, assets_modified, assets_deleted):
        """
        Shows a report on screen with assets that were added, removed or modified during an update. emits a signal
        when finished.
        :param assets_added: dictionary of assets added, see see pyani.core.mngr.core.find_new_and_updated_assets()
        for format of dicts
        :param assets_modified: dictionary of assets that have had files updated/modified. in same format as assets
        added.
        :param assets_deleted: dictionary of assets that have been removed. in same format as assets added.
        """
        html_report = "<p><div style='font-size:{0}pt; font-family:{1}; color:{2};'><b>NEW ASSETS</b>" \
                      "<br>" \
                      "<img src='{3}'></img>" \
                      "</div>" \
                      "</p>".format(self.font_size_heading_1, self.font_family, pyani.core.ui.CYAN, self.h_line_img)
        self._reset_assets_list()
        if assets_added:
            self._order_by_asset_category(assets_added)
            html_report += self._create_asset_list_for_update_report()
        else:
            html_report += "<p>" \
                           "<div style='font-size:{0}pt; font-family:{1}; color:#ffffff; margin-left:30px;'>" \
                           "No assets have been updated." \
                           "</div>" \
                           "</p>".format(
                                self.font_size_heading_3,
                                self.font_family
                            )

        html_report += "<p><div style='font-size:{0}pt; font-family:{1}; color:{2};'><b>UPDATED ASSETS</b>" \
                       "<br>" \
                       "<img src='C:\\PyAniTools\\core\\images\\h_line_cyan.png'></img>" \
                       "</div>" \
                       "</p>".format(self.font_size_heading_1, self.font_family, pyani.core.ui.CYAN)
        self._reset_assets_list()
        if assets_modified:
            self._order_by_asset_category(assets_modified)
            html_report += self._create_asset_list_for_update_report()
        else:
            html_report += "<p>" \
                           "<div style='font-size:{0}pt; font-family:{1}; color:#ffffff; margin-left:30px;'>" \
                           "No assets were added." \
                           "</div>" \
                           "</p>".format(
                                self.font_size_heading_3,
                                self.font_family
                            )

        html_report += "<p><div style='font-size:{0}pt; font-family:{1}; color:{2};'><b>REMOVED ASSETS</b>" \
                       "<br>" \
                       "<img src='C:\\PyAniTools\\core\\images\\h_line_cyan.png'></img>" \
                       "</div>" \
                       "</p>".format(self.font_size_heading_1, self.font_family, pyani.core.ui.CYAN)
        self._reset_assets_list()
        if assets_deleted:
            self._order_by_asset_category(assets_deleted)
            html_report += self._create_asset_list_for_update_report()
        else:
            html_report += "<p>" \
                           "<div style='font-size:{0}pt; font-family:{1}; color:#ffffff; margin-left:30px;'>" \
                           "No assets were removed." \
                           "</div>" \
                           "</p>".format(
                                self.font_size_heading_3,
                                self.font_family
                            )

        self.show_content(html_report)

    def _reset_assets_list(self):
        """
        Clears the ordered assets list
        """
        # clear assets
        for asset_category in self.assets_grouped_by_cat:
            if self.assets_grouped_by_cat[asset_category]['assets']:
                self.assets_grouped_by_cat[asset_category]['assets'] = list()

    def _order_by_asset_category(self, assets_list):
        """
        orders the dictionary by category in this format, and then sorts assets by name:
        {
            asset_category: {
                'display name' : name
                'assets': [
                    (
                        asset_name, {asset info such as version, file names, etc}
                    ),
                    (
                        asset_name, {asset info such as version, file names, etc}
                    ),
                    ...
                ]
            },
            ...
        }
        :param assets_list: a dictionary in the format found here: pyani.core.mngr.core.find_new_and_updated_assets()
        """
        # convert unordered to ordered
        for asset_type in assets_list:
            for asset_category in assets_list[asset_type]:
                # convert to an ordered list from an unordered dict. converts the dict to a
                # list of tuples sorted by name
                dict_to_sorted_list_tuples = [
                    (key, assets_list[asset_type][asset_category][key])
                    for key in sorted(assets_list[asset_type][asset_category].keys())
                ]
                self.assets_grouped_by_cat[asset_category]['assets'] = dict_to_sorted_list_tuples

    def _create_asset_list_for_update_report(self):
        """
        Creates the html to display the list of assets by category and then name.
        :return: a string containing the html
        """
        html_report = ""

        for asset_category in self.assets_grouped_by_cat:
            if self.assets_grouped_by_cat[asset_category]['assets']:
                # list the asset category first
                html_report += "<p>" \
                               "<div style='font-size:{0}pt; font-family:{1}; color:{3}; margin-left:30px;'>" \
                               "{2}" \
                               "</div>" \
                               "</p>".format(
                                   self.font_size_heading_2,
                                   self.font_family,
                                   self.assets_grouped_by_cat[asset_category]['display name'],
                                   pyani.core.ui.CYAN
                               )
                html_report += "<div style='font-size:{0}pt; font-family:{1}; color: #ffffff;'>" \
                               "<ul>".format(
                                    self.font_size_body,
                                    self.font_family
                                )

                for asset_name, asset_info in self.assets_grouped_by_cat[asset_category]['assets']:
                    if asset_info['version']:
                        html_report += "<li>{0} : <span style='color:{2};'><i>Version {1}</i></span></li>".format(
                            asset_name, asset_info['version'], pyani.core.ui.CYAN
                        )
                    else:
                        html_report += "<li>{0}</li>".format(asset_name)

                    if asset_info['files added']:
                        html_report += "<ul>" \
                                       "<li><span style='color:{0};'>ADDED:<span></li>".format(pyani.core.ui.GREEN)
                        html_report += "<ul>"
                        # add files that were added, modified or removed
                        for file_name in asset_info['files added']:
                            html_report += "<li>{0}</li>".format(file_name)
                        html_report += "</ul>" \
                                       "</ul>"

                    if asset_info['files modified']:
                        html_report += "<ul>" \
                                    "<li><span style='color:{0};'>UPDATED:<span></li>".format(pyani.core.ui.GOLD)
                        html_report += "<ul>"
                        # add files that were added, modified or removed
                        for file_name in asset_info['files modified']:
                            html_report += "<li>{0}</li>".format(file_name)
                        html_report += "</ul>" \
                                       "</ul>"

                    if asset_info['files removed']:
                        html_report += "<ul>" \
                                       "<li><span style='color:{0};'>REMOVED:<span></li>".format(
                                            pyani.core.ui.RED.name()
                                        )
                        html_report += "<ul>"
                        # add files that were added, modified or removed
                        for file_name in asset_info['files removed']:
                            html_report += "<li>{0}</li>".format(file_name)
                        html_report += "</ul>" \
                                       "</ul>"

                html_report += "</ul>" \
                               "</div>"
        html_report += "<p>&nbsp;</p>"

        return html_report
