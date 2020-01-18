import logging
import pyani.core.mngr.core
import pyani.core.mngr.assets
import pyani.core.mngr.tools
import pyani.core.mngr.ui.core
import pyani.review.core
import pyani.core.ui

logger = logging.getLogger()


class AniReviewAssetDownloadGui(pyani.core.mngr.ui.core.AniTaskListWindow):
    """
    Downloads assets for review and optional replaces old assets with the downloaded assets
    """

    def __init__(self, error_logging, progress_list):

        self.core_mngr = pyani.core.mngr.core.AniCoreMngr()
        self.review_mngr = pyani.review.core.AniReviewMngr(self.core_mngr)

        description = (
            "<span style='font-size: 9pt; font-family:{0}; color: #ffffff;'>"
            "This tool downloads the latest assets for review from the CGT server. Today's review date is: {1}."
            "</span>".format(
                pyani.core.ui.FONT_FAMILY,
                self.review_mngr.get_display_date()
            )
        )

        if self.review_mngr.review_exists():

            # list of tasks to run, see pyani.core.mngr.ui.core.AniTaskListWindow for format
            self.task_list = [
                # find the latest assets for review
                {
                    'func': self.review_mngr.find_latest_assets_for_review,
                    'params': [],
                    'finish signal': self.core_mngr.finished_signal,
                    'error signal': self.core_mngr.error_thread_signal,
                    'thread task': True,
                    'desc': "Found latest assets for review."
                },
                # download the latest assets for review
                {
                    'func': self.review_mngr.download_latest_assets_for_review,
                    'params': [],
                    'finish signal': self.core_mngr.finished_signal,
                    'error signal': self.core_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Downloaded latest assets for review."
                }
            ]

            pref = self.core_mngr.get_preference("review asset download", "update", "update old assets")
            # if the user preference is to replace old review assets with the latest, run the update
            if isinstance(pref, dict):
                pref_val = pref['update old assets']
                if pref_val:
                    self.task_list.append(
                        {
                            'func': self.review_mngr.update_review_assets_to_latest,
                            'params': [],
                            'finish signal': self.core_mngr.finished_signal,
                            'error signal': self.core_mngr.error_thread_signal,
                            'thread task': False,
                            'desc': "Updated existing review assets."
                        }
                    )
                    progress_list.append("Updating existing review assets with the latest.")

            self.task_list.append(
                {
                    'func': self.review_mngr.generate_download_report_data,
                    'params': [],
                    'finish signal': self.core_mngr.finished_signal,
                    'error signal': self.core_mngr.error_thread_signal,
                    'thread task': False,
                    'desc': "Created table data for report."
                }
            )
            progress_list.append("Creating table data for report.")
        # no review files, let user know
        else:
            description += (
                "<p align='center' style='font-size: 10pt; font-family:{0}; color: {1};'>"
                "No review files exist for today's date."
                "</p>".format(
                    pyani.core.ui.FONT_FAMILY,
                    pyani.core.ui.RED.name()
                )
            )

            self.task_list = None
            progress_list = None

        # information about the app
        app_metadata = {
            "name": "pyReviewDownload",
            "dir": self.review_mngr.app_vars.local_pyanitools_apps_dir,
            "type": "pyanitools",
            "category": "apps"
        }

        # create a ui (non-interactive) to run setup
        super(AniReviewAssetDownloadGui, self).__init__(
            error_logging,
            progress_list,
            "Review Download Tool",
            app_metadata,
            self.task_list,
            app_description=description
        )

        if self.review_mngr.review_exists():
            # NOTE: do this here because the super needs to be called first to create the window
            # used to create an html report to show in a QtDialogWindow
            self.download_report = pyani.core.mngr.ui.core.AniAssetTableReport(self)

            # provide report to review mngr so it can set data
            self.review_mngr.set_report(self.download_report)
            # move update window so it doesn't cover the main update window
            this_win_rect = self.frameGeometry()
            post_tasks = [
                {
                    'func': self.download_report.generate_table_report,
                    'params': []
                },
                {
                    'func': self.download_report.move,
                    'params': [this_win_rect.x() + 150, this_win_rect.y() - 75]
                }
            ]
            self.set_post_tasks(post_tasks)

    def run(self):
        """
        Starts the update process
        """
        self.start_task_list()
