import datetime
import os
import logging
import pyani.core.appvars
import pyani.core.mngr.core
import pyani.core.ui
import pyani.core.util


logger = logging.getLogger()


class AniReviewMngr:
    """
    A class object to handle reviews. Currently supports downloading daily review assets - sequence or shot level and
    updating assets on disk. Uses this folder structure:

    Sequence/
        nCloth/
            only nCloth shot movies
        BG/
            only BG shot movies
        list of shot movies. Only keeps one of animation, layout, previs, nHair and Shot Finaling, whichever movie
        for that shot is the latest version. If a review has multiple movies, uses this order of precedence:
        'animation' > 'shotFinaling' > 'nCloth' > 'layout' > 'previs']
    """
    def __init__(self, mngr):
        self.app_vars = pyani.core.appvars.AppVars()
        self.mngr = mngr

        self.review_assets = dict()
        # get todays date formatted to yyyymmdd from yyyy-mm-dd
        self.review_date = str(datetime.datetime.date(datetime.datetime.now())).replace("-", "")
        self.review_path = "{0}/{1}".format(self.app_vars.review_movie_server_directory, self.review_date)
        self.review_exists_on_server = self.mngr.server_file_exists(self.review_path)
        # get the local download location - use the saved preference if exists, otherwise use the default show location
        pref = self.mngr.get_preference("review asset download", "download", "location")
        if not isinstance(pref, dict):
            self.local_download_dir = self.app_vars.review_movie_local_directory
        else:
            self.local_download_dir = pref['location']

        # report object
        self.report = None
        # report headings, used when making report
        self.report_headings = ["Seq", "Shot", "Dept", "File Name", "Download Location", "Replaced File"]
        # width in percent
        self.report_col_widths = ["5", "5", "7", "18", "25", "40"]
        # report data
        self.report_data = list()

    @staticmethod
    def get_display_date():
        """gets the date as mm/dd/yyyy
        """
        return datetime.datetime.now().strftime('%m/%d/%Y')

    def set_report(self, report):
        """
        Stores a report object used to display a download report to user
        :param report: a pyani.core.mngr.ui.core AniAssetTableReport table report object
        """
        self.report = report

    def review_exists(self):
        """
        Checks if a review exists for today
        return: True if exists, False if not
        """
        if self.review_exists_on_server:
            return True
        else:
            return False

    def find_latest_assets_for_review(self):
        """
        Finds the review files for today's date and builds a dictionary in format:
        {
            sequence name:
                department name: [ list of dicts* representing review assets for the sequence in format:
                        {
                            'server path': absolute path on the server,
                            'file name': just the file name, no folders,
                            'local download path': absolute path on the local machine
                        }
                shot name:
                    department name: [  list of dicts* representing review assets for a shot in format:
                        {
                            'server path': absolute path on the server,
                            'file name': just the file name, no folders,
                            'local download path': absolute path on the local machine
                        }
                        ... more review assets
                    ]
                    ... more departments
                 ...more shots
            ... more sequences
        }
        * we do a list so that in future could expand review assets beyond just movies, could also have other files
        for a shot/department in the same review
        """
        # get files in folder
        logging.info("Searching for review assets in: {0}".format(self.review_path))

        files = self.mngr.server_get_dir_list(self.review_path, files_only=True, walk_dirs=True, absolute_paths=True)

        for file_path in files:
            # split file into parts to get department name and file name
            file_name_no_review_path = file_path.replace(self.review_path + "/", "")
            file_name_split = file_name_no_review_path.split("/")
            dept = file_name_split[0]
            file_name = file_name_split[1]

            seq = pyani.core.util.get_sequence_name_from_string(file_name)
            shot = pyani.core.util.get_shot_name_from_string(file_name)

            # sometimes sq or Sq used so check "[a-zA-Z]{3}\d{2,}"
            if not seq:
                seq = pyani.core.util.get_sequence_name_from_string(file_name, pattern="[a-zA-Z]{2}\d{2,}")
                # check if found a sequence, if not put not available
                if not seq:
                    seq = "N/A"

            if seq not in self.review_assets:
                self.review_assets[seq] = dict()

            # sequence asset, like editorial movie
            if not shot:
                if dept not in self.review_assets[seq]:
                    self.review_assets[seq][dept] = list()
                self.review_assets[seq][dept].append(
                    {
                        'server path': file_path,
                        'file name': file_name,
                        'local download path': os.path.normpath(
                            os.path.join(self.local_download_dir, self.review_date, dept)
                        )
                    }
                )
                # done processing this file, go to next one
                continue

            if shot not in self.review_assets[seq]:
                self.review_assets[seq][shot] = dict()

            # check for special case background ('BG'). Can be a subfolder, a main folder, or in the file name
            if 'bg' in dept.lower() or '_bg_' in file_name.lower() or 'bg/' in file_name.lower():
                # check if 'bg' key exists in dict, if not add
                if 'BG' not in self.review_assets[seq][shot]:
                    self.review_assets[seq][shot]['BG'] = list()

                local_download_path = os.path.normpath(
                    os.path.join(self.local_download_dir, self.review_date, 'BG')
                )
                self.review_assets[seq][shot]['BG'].append(
                    {
                        'server path': file_path,
                        'file name': file_name,
                        'local download path': local_download_path
                    }
                )
                # done processing, go to next file, don't want to make a duplicate entry
                continue

            # check for special case camera polishing which is other department files
            if 'camera polishing' in dept.lower():
                # make a lower case version of file name parts
                file_name_split = [part.lower() for part in file_name.split("_")]
                # find which department this file belongs to
                for dept_longhand, dept_shorthand in self.app_vars.review_depts.items():
                    if dept_shorthand.lower() in file_name_split:
                        # check if department key exists in dict, if not add
                        if dept_longhand not in self.review_assets[seq][shot]:
                            self.review_assets[seq][shot][dept_longhand] = list()

                        local_download_path = os.path.normpath(
                            os.path.join(self.local_download_dir, self.review_date, dept_longhand)
                        )
                        # add file to the dept list of review assets
                        self.review_assets[seq][shot][dept_longhand].append(
                            {
                                'server path': file_path,
                                'file name': file_name,
                                'local download path': local_download_path
                            }
                        )
                # done processing, go to next file, don't want to make a camera polishing entry below
                continue

            # check if department key exists in dict, if not add - do this here so we don't make departments for
            # special cases - some like camera polishing aren't a dept
            if dept not in self.review_assets[seq][shot]:
                self.review_assets[seq][shot][dept] = list()

            local_download_path = os.path.normpath(
                os.path.join(self.local_download_dir, self.review_date, dept)
            )

            # add file to the dept list of review assets
            self.review_assets[seq][shot][dept].append(
                {
                    'server path': file_path,
                    'file name': file_name,
                    'local download path': local_download_path
                }
            )

        # done, let any listeners know if running in a multi-threaded environment
        self.mngr.finished_signal.emit(None)

    def download_latest_assets_for_review(self):
        """
        Downloads the review assets
        """
        # make a list of the files to download from the server and where to download to
        file_list = list()
        for seq in self.review_assets:
            for asset in self.review_assets[seq]:
                # check if this is a sequence or a shot asset, will be a sequence asset if the value for the asset key
                # is a list, see above format for the review asset dict. if this is a sequence asset then key, aka
                # asset is a department name
                if isinstance(self.review_assets[seq][asset], list):
                    for review_asset in self.review_assets[seq][asset]:
                        file_list.append(
                            (review_asset['server path'], review_asset['local download path'])
                        )
                # shot asset so this key is a shot name
                else:
                    for dept in self.review_assets[seq][asset]:
                        for review_asset in self.review_assets[seq][asset][dept]:
                            file_list.append(
                                (review_asset['server path'], review_asset['local download path'])
                            )
        self.mngr.server_file_download_mt(file_list, thread_count=3)

    def update_review_assets_to_latest(self, debug=False):
        """
        Updates review assets on disk with the downloaded review assets according to rules in class doc
        :param debug: If true doesn't perform disk operations, just prints the actions performed
        """
        if debug:
            self.review_assets = pyani.core.util.load_json('C:\\Users\\Patrick\\Downloads\\20200114\\test_review_data.json')

        for seq in self.review_assets:
            # couldn't find a sequence so skip
            if seq == "N/A":
                continue

            # path to sequence folder
            seq_folder = os.path.normpath(
                os.path.join(self.local_download_dir, seq)
            )
            # check if sequence is in local review asset location and if not make it
            if not os.path.exists(seq_folder):
                if debug:
                    print "Making Folder: {0}".format(seq_folder)
                else:
                    error = pyani.core.util.make_dir(seq_folder)
                    if error:
                        self.mngr.send_thread_error(error)
                        return error

            # now process sequence and shot assets
            for asset in self.review_assets[seq]:
                # check if this is a sequence asset, if so skip, we don't update these right now
                if not pyani.core.util.is_valid_shot_name(asset):
                    if debug:
                        print "Skipping {0}, {1}".format(seq, asset)
                        print "---------------"
                    continue

                # make a copy, so that we can remove nCloth and BG - need review assets to remain unchanged
                department_list_for_shot = self.review_assets[seq][asset].keys()

                # check if shot has nCloth and/or BG, if so move those, then handle the rest of the departments
                if "nCloth" in department_list_for_shot:
                    # get a list of all files in the seq directory.
                    sub_folder = os.path.join(seq_folder, "nCloth")
                    existing_files_in_dir = [
                        os.path.join(sub_folder, file_name) for file_name in pyani.core.util.get_all_files(sub_folder)
                    ]
                    dest_path = os.path.join(seq_folder, "nCloth")
                    # check if the folder exists
                    if not os.path.exists(dest_path):
                        if debug:
                            print "Making Sub-Folder: {0}".format(dest_path)
                        else:
                            error = pyani.core.util.make_dir(dest_path)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error

                    self._replace_file(seq, asset, "nCloth", existing_files_in_dir, dest_path, debug=debug)

                    # done with this so can remove
                    department_list_for_shot.remove("nCloth")

                if "BG" in department_list_for_shot:
                    # get a list of all files in the seq directory.
                    sub_folder = os.path.join(seq_folder, "BG")
                    existing_files_in_dir = [
                        os.path.join(sub_folder, file_name) for file_name in
                        pyani.core.util.get_all_files(sub_folder)
                    ]
                    dest_path = os.path.join(seq_folder, "BG")
                    # check if the folder exists
                    if not os.path.exists(dest_path):
                        if debug:
                            print "Making Sub-Folder: {0}".format(dest_path)
                        else:
                            error = pyani.core.util.make_dir(dest_path)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error
                    self._replace_file(seq, asset, "BG", existing_files_in_dir, dest_path, debug=debug)

                    # done with this so can remove
                    department_list_for_shot.remove("BG")

                # check if any remaining depts, can skip if we already processed everything
                if not department_list_for_shot:
                    continue

                # check if multiple movies for this shot, if so get the dept that will update any existing asset
                if len(department_list_for_shot) > 1:

                    # multiple movies, move in order of precedence
                    new_order = [
                        dept for dept in self.app_vars.review_dept_precedence if dept in department_list_for_shot
                    ]
                    dept = new_order[0]
                    if debug:
                        print "Precedence - Found depts {0}, using dept: {1}".format(','.join(department_list_for_shot), dept)
                # only one movie for this shot, so only one dept as well
                else:
                    dept = department_list_for_shot[0]

                # see if shot has a file already in the seq folder, if so delete it
                existing_files_in_dir = [
                    os.path.join(seq_folder, file_name) for file_name in
                    pyani.core.util.get_all_files(seq_folder, walk=False)
                ]

                self._replace_file(seq, asset, dept, existing_files_in_dir, seq_folder, debug=debug)

        # done, let any listeners know if running in a multi-threaded environment
        self.mngr.finished_signal.emit(None)

    def generate_download_report_data(self):
        """
        Creates the data for the report and sends the data to the report
        """
        # set the headings and column widths
        self.report.headings = self.report_headings
        self.report.col_widths = self.report_col_widths

        # create the row data
        for seq in sorted(self.review_assets):
            for asset in sorted(self.review_assets[seq]):
                # check if this is a sequence asset
                if not pyani.core.util.is_valid_shot_name(asset):
                    # process the review assets
                    for review_asset in self.review_assets[seq][asset]:
                        replaced_file = ""
                        if 'replaced file' in review_asset:
                            replaced_file = review_asset['replaced file']
                        self.report_data.append(
                            (
                                seq,
                                "",
                                asset,
                                review_asset['file name'],
                                review_asset['local download path'],
                                replaced_file
                            )
                        )
                else:
                    for dept in sorted(self.review_assets[seq][asset]):
                        # process the review assets
                        for review_asset in self.review_assets[seq][asset][dept]:
                            replaced_file = ""
                            if 'replaced file' in review_asset:
                                replaced_file = review_asset['replaced file']
                            self.report_data.append(
                                (
                                    seq,
                                    asset,
                                    dept,
                                    review_asset['file name'],
                                    review_asset['local download path'],
                                    replaced_file
                                )
                            )
            # add empty row of data to create a separator between sequences
            self.report_data.append(
                (
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                )
            )
        # send the row data to report
        self.report.data = self.report_data
        # done, let any listeners know if running in a multi-threaded environment
        self.mngr.finished_signal.emit(None)

    def _replace_file(self, seq, asset, dept, existing_files_in_dir, dest_path, debug=False):
        """
        Helper function to find existing files, remove them, store files replaced and move new files to the right
        location
        :param seq: the seq
        :param asset: typically the shot, but can be a department if we handle sequence assets
        :param dept: a pipeline department
        :param existing_files_in_dir: a list of existing files as absolute paths
        :param dest_path: the folder to copy to
        :param debug: if True prints actions, but doesn't perform any actual disk operations
        """

        # see if shot has a file already in the folder, if so delete it
        existing_asset = ""
        if existing_files_in_dir:
            for file_name in existing_files_in_dir:
                # here asset is shot, so check if shot in filename.
                if asset in file_name:
                    existing_asset = file_name
                    if debug:
                        print "Deleting File: {0}".format(file_name)
                    else:
                        error = pyani.core.util.delete_file(file_name)
                        if error:
                            self.mngr.send_thread_error(error)
                            return error
                        break

        # right now only one review asset per dept
        review_asset = self.review_assets[seq][asset][dept][0]

        # record what file was replaced
        self.review_assets[seq][asset][dept][0]['replaced file'] = existing_asset
        if debug:
            print "Replaced File : {0}".format(existing_asset)

        src_path = os.path.join(review_asset['local download path'], review_asset['file name'])
        if debug:
            print "Moving File From: {0} to {1}".format(src_path, dest_path)
            print "---------------"
        else:
            error = pyani.core.util.move_file(src_path, dest_path)
            if error:
                self.mngr.send_thread_error(error)
                return error
            # update the download location to reflect where the movie now resides
            self.review_assets[seq][asset][dept][0]['local download path'] = dest_path
