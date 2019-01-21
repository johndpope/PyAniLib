import logging
import os
import datetime
import pyani.core.util


class ErrorLogging:
    def __init__(self, app_name, error_level=logging.DEBUG):
        """
        Sets up the python logging class for an app. Creates the root config logger, and log directory if it doesn't exist
        Cleans up logs older than a week
        :param app_name: name of app
        :param error_level: level of errors to log, default to DEBUG
        """

        self.__error_log_list = []

        # how long to keep logs
        self.__days_to_keep_log = 7

        # setup log file name
        now = datetime.datetime.now()
        time_stamp = now.strftime("%Y-%m-%d_%H-%M")
        self.__tools_dir = os.path.normpath("C:\PyAniTools")
        self.__root_log_dir = os.path.join(self.__tools_dir, "logs")
        self.__app_log_dir = os.path.join(self.__root_log_dir, app_name)
        self.__log_file_name = "{0}\\{1}_{2}.txt".format(self.__app_log_dir, app_name, time_stamp)
        self.__app_name = app_name

        self.__error_level = error_level

    @property
    def app_name(self):
        """Name of the app this log is for
        """
        return self.__app_name

    @property
    def app_log_dir(self):
        """path to this apps logs
        """
        return self.__app_log_dir

    @property
    def error_level(self):
        """The error level of the python logging class
        """
        return self.__error_level

    @property
    def days_to_keep_log(self):
        """Number of days log is kept
        """
        return self.__days_to_keep_log

    @property
    def root_log_dir(self):
        """The main directory holding app logs
        """
        return self.__root_log_dir

    @property
    def log_file_name(self):
        """the absolute path to the log file
        """
        return self.__log_file_name

    @property
    def error_log_list(self):
        return self.__error_log_list

    def setup_logging(self):
        """
        Sets up the python logging class for an app. Creates the root config logger, and log directory if it doesn't
        exist. Cleans up logs older than a week. Logs errors in error log list member variable
        """

        # make sure log folders exist - "C:\PyAniTools\", "C:\PyAniTools\logs" & "C:\PyAniTools\logs\{app_name}"
        if not os.path.exists(self.__tools_dir):
            error = pyani.core.util.make_dir(self.__tools_dir)
            if error:
                self.__error_log_list.append(error)
        if not os.path.exists(self.root_log_dir):
            error = pyani.core.util.make_dir(self.root_log_dir)
            if error:
                self.__error_log_list.append(error)
        if not os.path.exists(self.app_log_dir):
            error = pyani.core.util.make_dir(self.app_log_dir)
            if error:
                self.__error_log_list.append(error)

        # make sure log path exists since we don't exit on error - apps warn log not created, but allow usage
        if os.path.exists(self.app_log_dir):
            # remove old logs
            for log_name in os.listdir(self.app_log_dir):
                error = pyani.core.util.delete_by_day(self.days_to_keep_log, os.path.join(self.app_log_dir, log_name))
                if error:
                    self.__error_log_list.append(error)

            try:
                # setup python logging
                root_logger = logging.getLogger()
                root_logger.setLevel(self.error_level)
                f_handler = logging.FileHandler(self.log_file_name)
                f_handler.setLevel(self.error_level)
                formatter = logging.Formatter("(%(levelname)s)  %(lineno)d. %(pathname)s - %(funcName)s: %(message)s")
                f_handler.setFormatter(formatter)
                root_logger.addHandler(f_handler)
            except (IOError, OSError, WindowsError, EnvironmentError) as e:
                self.__error_log_list.append(
                    "Could not create root logger in ErrorLogging class for {0}".format(self.app_name)
                )

