import os
import logging
import pyani.core.ui


# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets, QtCore


logger = logging.getLogger()


class AniTaskListWindow(pyani.core.ui.AniQMainWindow):
    """
    The purpose of this class is to allow any setup or update process to provide a list of tasks, and let this
    class manage running those. It uses signal/slots of pyqt to do this. A function runs, fires a signal when it
    completes or errors, which causes this class to then respond and either report the error or run the next
    function in the list.

    Inherits from AniQMainWindow, and doesn't shown version information. This information isn't always available
    when setup runs, so we just don't show it

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

    def __init__(self, error_logging, progress_list, win_title, app_name, task_list_to_run):
        """
        :param error_logging : error log (pyani.core.error_logging.ErrorLogging object) from trying
        to create logging in main program
        :param progress_list: a list of strings describing the steps being run
        :param win_title: title of the window
        :param app_name: name of the application
        :param task_list_to_run: a list of dicts that hold task information. The format is:
            {
                'func': this is the function to call - do not put parenthesis, ie do method_name, not method_name()
                'params': any parameters, pass as a list
                'finish signal': the pyqt signal to connect to for when a method finishes
                'error signal': the pyqt signal to connect to for when a method errors
                'thread task': True means put task in thread, False does not. Only thread non threaded methods. If
                               the method in 'func' creates threads, set this to False otherwise errors will occur.
                'desc': string description describing what this method does. shown in activity log.
            }
        """
        self.tools_mngr = pyani.core.mngr.tools.AniToolsMngr()

        app_vars = pyani.core.appvars.AppVars()
        tool_metadata = {
            "name": app_name,
            "dir": app_vars.local_pyanitools_core_dir,
            "type": "pyanitools",
            "category": "apps"
        }

        # pass win title, icon path, app manager, width and height
        super(AniTaskListWindow, self).__init__(
            win_title,
            "images\\setup.ico",
            tool_metadata,
            self.tools_mngr,
            450,
            700,
            error_logging,
            show_help=False,
            disable_version=True
        )

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

        # setup threading
        self.thread_pool = QtCore.QThreadPool()
        logger.info("Multi-threading with maximum %d threads" % self.thread_pool.maxThreadCount())

        # text font to use for ui
        self.font_family = pyani.core.ui.FONT_FAMILY
        self.font_size = pyani.core.ui.FONT_SIZE_DEFAULT

        # the list of steps/tasks descriptions
        self.progress_list = progress_list
        # current step/task
        self.step_num = 0
        # total number of steps / tasks
        self.step_total = len(self.progress_list)
        # logs what runs successfully and errors
        self.activity_log = []
        # this tells the next_step_in_task_list() method to not get any more tasks from the task list defined by
        # the class variable task_list
        self.stop_tasks = False
        # indicates an error occurred
        self.error_occurred = False
        # method vars for setup and updating
        self.task_list = task_list_to_run
        self.method_to_run = None
        self.method_params = None
        self.method_finish_signal = None
        self.method_error_signal = None
        # shown at end as a description of what ran
        self.task_desc = None

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

        desc_label = QtWidgets.QLabel(
            "<span style='font-size: 9pt; font-family:{0}; color: #ffffff;'>"
            "About the pyAniTools asset management system: Setup creates configuration files, builds caches that help "
            "speed up CGT connectivity, downloads tools, and sets up a user's system to work with the pyAniTools "
            "update system. The update system allows assets such as tools, rigs, and more to be auto updated daily. "
            "A gui interface, called Asset Manager, provides a user interface to the asset management system."
            "</span>".format(
                self.font_family
            )
        )
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
        Prevent any more tasks from running and close window. Warns user that installation will be incomplete if close
        before setup finishes.
        """
        if self.task_list:
            response = self.msg_win.show_question_msg(
                "Setup Warning",
                "Closing the setup window while setup is running may result in an incomplete "
                "installation of the tools. Are you sure you want to close the window?"
            )
            if response:
                self.stop_tasks = True
                self.close()
        else:
            self.close()

    def start_task_list(self):
        """
        Starts running the first task/method in the task list provided via the class variable task_list
        """
        # update the ui with the first step / task
        self.update_ui()
        # run the first task
        self._get_next_task_to_run()

    def next_step_in_task_list(self):
        """
        Increments to the next step in the update or setup process task list, provided via the class variable
        task_list. If no more tasks are left, shows the activity report and hides step and progress ui labels
        """
        # check for more steps that need to be run
        if self.task_list and not self.stop_tasks:
            self.update_ui()
            # add to activity log as success
            self._get_next_task_to_run()
        # no more steps, display activity log
        else:
            # hide steps / task info since done
            self.step_label.hide()
            self.progress_label.hide()
            # show the log of activity
            self.display_activity_log()

    def update_ui(self):
        """
        Updates the ui elements
        """
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
            "<span style='font-size:{2}pt; font-family:{0}; color: {1};'><strong>SETUP ERROR</strong><br><br></span>"
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
        self.stop_tasks = True
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

    def _get_next_task_to_run(self):
        """
        Gets a task from the task list and runs it in a thread
        """
        task_list_package = self.task_list.pop(0)
        self.method_to_run = task_list_package['func']
        self.method_params = task_list_package['params']
        self.method_finish_signal = task_list_package['finish signal']
        self.method_error_signal = task_list_package['error signal']
        self.task_desc = task_list_package['desc']
        self.activity_log.append(self.task_desc)

        # some tasks are already multi-threaded, so only thread tasks that have the 'thread task' key in task list
        # set to True
        if task_list_package['thread task']:
            # server_download expects a list of files, so pass list even though just one file
            worker = pyani.core.ui.Worker(
                self.method_to_run,
                False,
                *self.method_params
            )

            self.thread_pool.start(worker)
            # slot that is called when a thread finishes, passes the active_type so calling classes can
            # know what was updated and the save cache method so that when cache gets updated it can be
            # saved
            worker.signals.finished.connect(self.next_step_in_task_list)
            worker.signals.error.connect(self.process_error)
        # already threaded, don't thread
        else:
            self.method_finish_signal.connect(self.next_step_in_task_list)
            self.method_error_signal.connect(self.process_error)
            self.method_to_run(*self.method_params)
