import logging
import os
import datetime
import pyani.core.util


def setup_error_logging(app_name, error_level):
    """
    Sets up the python logging class for an app. Creates the root config logger, and log directory if it doesn't exist
    Cleans up logs older than a week
    :param app_name: name of app
    :param error_level: level of errors to log
    :return: error as string if encountered, otherwise none.
    """

    # how long to keep logs
    days_to_keep_log = 7

    # setup log file name
    now = datetime.datetime.now()
    time_stamp = now.strftime("%Y-%m-%d_%H-%M")
    log_dir = os.path.normpath("C:\PyAniTools\logs")
    log_file_name = "{0}\\{1}\\{2}_{3}.txt".format(log_dir, app_name, app_name, time_stamp)

    # make sure log folders exist - both "C:\PyAniTools\logs" and "C:\PyAniTools\logs\{app_name}"
    if not os.path.exists(log_dir):
        error = pyani.core.util.make_dir(log_dir)
        if error:
            return error
    app_log_dir = os.path.join(log_dir, app_name)
    if not os.path.exists(app_log_dir):
        error = pyani.core.util.make_dir(app_log_dir)
        if error:
            return error

    # remove old logs
    for log_name in os.listdir(app_log_dir):
        pyani.core.util.delete_by_day(days_to_keep_log, os.path.join(app_log_dir, log_name))

    # setup python logging
    root_logger = logging.getLogger()
    root_logger.setLevel(error_level)
    f_handler = logging.FileHandler(log_file_name)
    f_handler.setLevel(error_level)
    formatter = logging.Formatter("(%(levelname)s)  %(lineno)d. %(pathname)s - %(funcName)s: %(message)s")
    f_handler.setFormatter(formatter)
    root_logger.addHandler(f_handler)

    return None
