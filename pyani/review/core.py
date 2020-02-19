import datetime
import os
import re
import logging
from collections import OrderedDict
import copy
import pyani.core.appvars
import pyani.core.mngr.core
import pyani.core.ui
import pyani.core.util


logger = logging.getLogger()


class AniReviewMngr:
    """
    A class object to handle reviews. Currently supports downloading daily review assets - sequence or shot level and
    updating assets on disk.

    Seq assets are replaced by dept name and seq name, so a movie for seq120 of all animation, gets updated if a new
    movie is in the review for animation and the sequence

    Shot assets are updated by seq, shot, dept, so a layout movie for seq110 shot020, gets updated when a new one is
    in the review for seq110, shot020 and layout.
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
        # a list of downloaded files
        self.download_list = list()

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

    def reset_review(self):
        """Reset all member variables for review in case its been run already, such as via asset manager"""
        self.review_assets = dict()
        self.report_data = list()
        self.download_list = list()

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
        # clear existing review, in case it has been run alread
        self.reset_review()

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
                    seq = "non_seq_asset"

            if seq not in self.review_assets:
                self.review_assets[seq] = dict()

            # sequence asset, like editorial movie
            if not shot:
                if dept not in self.review_assets[seq]:
                    self.review_assets[seq][dept] = list()

                # check if this dept has a specific download directory for the asset
                pref = self.mngr.get_preference("review asset download", dept, "download movie location")
                if isinstance(pref, dict):
                    local_download_path = pref["download movie location"]
                    # check if using custom general path, if so set download path to it
                elif not self.local_download_dir == self.app_vars.review_movie_local_directory:
                    local_download_path = self.local_download_dir
                    # using default path, so add review date and dept
                else:
                    local_download_path = os.path.normpath(
                        os.path.join(self.local_download_dir, self.review_date, dept)
                    )

                # replace placeholders for seq, review date and/or dept
                local_download_path = self._replace_placeholders(local_download_path, seq, dept)

                self.review_assets[seq][dept].append(
                    {
                        'server path': file_path,
                        'file name': file_name,
                        'local download path': local_download_path
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

                # check if this dept has a specific download directory for the asset
                pref = self.mngr.get_preference("review asset download", "BG", "download movie location")
                if isinstance(pref, dict):
                    local_download_path = pref["download movie location"]
                    # check if using custom general path, if so set download path to it
                elif not self.local_download_dir == self.app_vars.review_movie_local_directory:
                    local_download_path = self.local_download_dir
                    # using default path, so add review date and dept
                else:
                    local_download_path = os.path.normpath(
                        os.path.join(self.local_download_dir, self.review_date, "BG")
                    )

                # replace placeholders for seq, review date and/or dept
                local_download_path = self._replace_placeholders(local_download_path, seq, "BG")

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

                        # check if this dept has a specific download directory for the asset
                        pref = self.mngr.get_preference("review asset download", dept_longhand, "download movie location")
                        if isinstance(pref, dict):
                            local_download_path = pref["download movie location"]
                        # check if using custom general path, if so set download path to it
                        elif not self.local_download_dir == self.app_vars.review_movie_local_directory:
                            local_download_path = self.local_download_dir
                        # using default path, so add review date and dept
                        else:
                            local_download_path = os.path.normpath(
                                os.path.join(self.local_download_dir, self.review_date, dept_longhand)
                            )

                        # replace placeholders for seq, review date and/or dept
                        local_download_path = self._replace_placeholders(local_download_path, seq, dept_longhand)

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

            # check if this dept has a specific download directory for the asset
            pref = self.mngr.get_preference("review asset download", dept, "download movie location")
            if isinstance(pref, dict):
                local_download_path = pref["download movie location"]
            # check if using custom general path, if so set download path to it
            elif not self.local_download_dir == self.app_vars.review_movie_local_directory:
                local_download_path = self.local_download_dir
            # using default path, so add review date and dept
            else:
                local_download_path = os.path.normpath(
                        os.path.join(self.local_download_dir, self.review_date, dept)
                )

            # replace placeholders for seq, review date and/or dept
            local_download_path = self._replace_placeholders(local_download_path, seq, dept)

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
                        pref = self.mngr.get_preference("review asset download", asset, "download movies")
                        if isinstance(pref, dict):
                            # check if the preference is False, don't download, if so continue to next review asset
                            if not pref["download movies"]:
                                continue
                        file_list.append(
                            (review_asset['server path'], review_asset['local download path'])
                        )
                # shot asset so this key is a shot name
                else:
                    for dept in self.review_assets[seq][asset]:
                        for review_asset in self.review_assets[seq][asset][dept]:
                            pref = self.mngr.get_preference("review asset download", dept, "download movies")
                            if isinstance(pref, dict):
                                # check if the preference is False, don't download, if so continue to next review asset
                                if not pref["download movies"]:
                                    continue
                            file_list.append(
                                (review_asset['server path'], review_asset['local download path'])
                            )
        # use this when replacing files in update_review_assets_to_latest() to know what was downloaded since
        # these file sgo in with the existing review assets on disk
        for server_path, local_path in file_list:
            file_name = server_path.split("/")[-1]
            file_path = os.path.join(local_path, file_name)
            self.download_list.append(file_path)
        self.mngr.server_file_download_mt(file_list, thread_count=3)

    def update_review_assets_to_latest(self):
        """
        Updates review assets on disk with the downloaded review assets according to rules in class doc
        """
        # get general preference to see if assets should be replaced locally
        pref = self.mngr.get_preference("review asset download", "update", "update old assets")
        if isinstance(pref, dict):
            gen_replace_pref = pref["update old assets"]
        else:
            gen_replace_pref = False

        # get preference for one shot per movie, ie use precedence
        pref = self.mngr.get_preference("review asset download", "movie", "use precedence")
        precedence_order = list()
        if isinstance(pref, dict):
            precedence_pref = pref["use precedence"]
            # now get order
            pref = self.mngr.get_preference("review asset download", "movie", "precedence order")
            precedence_order = pref["precedence order"]
        else:
            precedence_pref = False

        # find the general local download path
        pref = self.mngr.get_preference("review asset download", "download", "location")
        if isinstance(pref, dict):
            gen_dl_loc = pref["location"]
        else:
            gen_dl_loc = self._replace_placeholders(self.app_vars.review_movie_local_directory)

        # tracks which files were moved to the general download location if precedence is on and there are multiple
        # movies for a dept
        moved_files = dict()

        # loop through sequence and shot assets
        for sequence in self.review_assets:
            '''
            Pre-process a seq into seq assets (no shot name) and shot assets (have shot name) 
            '''
            seq_dept_assets = dict()
            shot_assets = dict()
            # seq_asset is either a dept if its a sequence asset, or shot name if its a shot asset
            # separate seq assets into dept or shot
            for seq_asset in self.review_assets[sequence]:
                # do deep copy because these are modified and don't want to alter review assets
                # check if dept, ie not a shot
                if not pyani.core.util.is_valid_shot_name(seq_asset):
                    seq_dept_assets[seq_asset] = copy.deepcopy(self.review_assets[sequence][seq_asset])
                # its a shot
                else:
                    shot_assets[seq_asset] = copy.deepcopy(self.review_assets[sequence][seq_asset])

            '''

            SEQUENCE ASSETS

            '''

            '''
            Precedence Section for sequence assets.
            Handles when a sequence has multiple assets in a review - ie Seq310 having
            Editorial and Animation which download to the same location and both are sequence assets
            '''
            # find the dept to keep, move any other depts to general dl location, set the sequence assets to just
            # the dept being kept, and then change the download location for moved assets
            # NOTE: if precedence is on, only need to process this if more than one dept, otherwise its just one dept
            # so don't need to do anything special
            if precedence_pref and len(seq_dept_assets) > 1:
                # re-order the assets by order of precedence to find which seq asset to keep
                seq_dept_assets_re_ordered = OrderedDict()
                for dept in precedence_order:
                    if dept in seq_dept_assets:
                        seq_dept_assets_re_ordered[dept] = seq_dept_assets[dept]

                # now move the assets except for the one being kept
                seq_dept_kept, seq_asset_kept = seq_dept_assets_re_ordered.popitem(last=False)
                for dept in seq_dept_assets_re_ordered:
                    if dept not in self.app_vars.review_assets_no_precedence:
                        for review_asset in seq_dept_assets_re_ordered[dept]:
                            # move assets to general download location
                            src = os.path.join(review_asset['local download path'], review_asset['file name'])
                            dest = os.path.join(gen_dl_loc, review_asset['file name'])
                            # make sure folder exists
                            error = pyani.core.util.make_all_dir_in_path(gen_dl_loc)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error
                            error = pyani.core.util.move_file(src, dest)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error
                            if sequence not in moved_files:
                                moved_files[sequence] = list()
                            moved_files[sequence].append(review_asset['file name'])

                # get any assets in sequence assets not part of precedence
                no_precedence_assets  = dict()
                for dept in self.app_vars.review_assets_no_precedence:
                    if dept in seq_dept_assets:
                        no_precedence_assets[dept] = copy.deepcopy(seq_dept_assets[dept])

                # finally set seq asset list to the asset kept as well as assets ignoring precedence
                seq_dept_assets.clear()
                seq_dept_assets[seq_dept_kept] = seq_asset_kept
                for key, value in no_precedence_assets.items():
                    seq_dept_assets[key] = value

            '''
            Replace section for sequence assets
            '''
            # process sequence department assets
            for seq_dept_asset in seq_dept_assets:
                # get asset specific preference - not use precedence requires replace, so we ignore this preference
                # when use preference is enabled.
                pref = self.mngr.get_preference("review asset download", seq_dept_asset, "replace existing movies")
                # if it exists use that, otherwise use the general preference for replacing assets
                if isinstance(pref, dict):
                    replace_pref = pref["replace existing movies"]
                else:
                    replace_pref = gen_replace_pref

                # now check if this seq_asset should get replaced
                if replace_pref:
                    # all dept assets in same location
                    dept_dl_location = seq_dept_assets[seq_dept_asset][0]["local download path"]

                    # check if folder exists, if not make it
                    if not os.path.exists(dept_dl_location):
                        error = pyani.core.util.make_all_dir_in_path(dept_dl_location)
                        if error:
                            self.mngr.send_thread_error(error)
                            return error

                    # see if dept has a file(s) already in the download folder - probably is dept name, but maybe
                    # not, depends how user configures, could put all sequence depts in one folder
                    # also ignore any of the downloaded files, since we don't want to count those
                    existing_files_in_dir = [
                        os.path.join(dept_dl_location, file_name) for file_name in
                        pyani.core.util.get_all_files(dept_dl_location, walk=False)
                        if os.path.join(dept_dl_location, file_name) not in self.download_list
                    ]
                    # check for existing asset and remove - remove if dept and seq match
                    for existing_file in existing_files_in_dir:
                        # compare existing file against files in review - have to do because of part names
                        for review_asset in seq_dept_assets[seq_dept_asset]:
                            print seq_dept_asset
                            # if using precedence don't check dept name, since we want to replace depts with other depts
                            # otherwise check if the dept matches.
                            if precedence_pref and seq_dept_asset not in self.app_vars.review_assets_no_precedence:
                                error = self._replace_seq_asset(review_asset, existing_file, sequence, seq_dept_asset)
                                if error:
                                    self.mngr.send_thread_error(error)
                                    return error
                            # check for dept name in file name
                            elif self.app_vars.review_depts[seq_dept_asset].lower() in existing_file.lower():
                                error = self._replace_seq_asset(review_asset, existing_file, sequence, seq_dept_asset)
                                if error:
                                    self.mngr.send_thread_error(error)
                                    return error
                            # no dept name in file name, so check if sequence matches - editorial for instance is in
                            # format seq###_movie_v###.mov
                            elif sequence.lower() in existing_file.lower() and \
                                    seq_dept_asset in self.app_vars.review_assets_no_dept_in_name:
                                error = self._replace_seq_asset(review_asset, existing_file, sequence, seq_dept_asset)
                                if error:
                                    self.mngr.send_thread_error(error)
                                    return error

            '''
            
            SHOT ASSETS
            
            '''
            for shot_name in shot_assets.keys():
                '''
                Precedence Section for shot assets.
                Handles when a shot has multiple dept assets in a review - ie Seq310 Shot010 having
                Editorial and Animation which download to the same location
                '''
                # find the dept to keep, move any other depts to general dl location, set the shot assets to just
                # the dept being kept, and then change the download location for moved assets
                # NOTE: if precedence is on, only need to process this if more than one dept, otherwise its just
                # one dept so don't need to do anything special
                if precedence_pref and len(shot_assets[shot_name]) > 1:
                    # re-order the assets by order of precedence to find which asset to keep
                    shot_dept_assets_re_ordered = OrderedDict()
                    for dept in precedence_order:
                        if dept in shot_assets[shot_name]:
                            shot_dept_assets_re_ordered[dept] = shot_assets[shot_name][dept]
                    # now move the assets except for the one being kept
                    shot_dept_kept, shot_asset_kept = shot_dept_assets_re_ordered.popitem(last=False)
                    for dept in shot_dept_assets_re_ordered:
                        for review_asset in shot_dept_assets_re_ordered[dept]:
                            # move assets to general download location
                            src = os.path.join(review_asset['local download path'], review_asset['file name'])
                            dest = os.path.join(gen_dl_loc, review_asset['file name'])
                            # make sure folder exists
                            error = pyani.core.util.make_all_dir_in_path(gen_dl_loc)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error
                            error = pyani.core.util.move_file(src, dest)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error
                            if sequence not in moved_files:
                                moved_files[sequence] = dict()
                            if shot_name not in moved_files[sequence]:
                                moved_files[sequence][shot_name] = dict()
                            if dept not in moved_files[sequence][shot_name]:
                                moved_files[sequence][shot_name][dept] = list()
                            moved_files[sequence][shot_name][dept].append(review_asset['file name'])

                    # finally set shot asset list to the asset kept
                    shot_assets[shot_name].clear()
                    shot_assets[shot_name][shot_dept_kept] = shot_asset_kept

                for dept in shot_assets[shot_name]:
                    # get asset specific preference
                    pref = self.mngr.get_preference("review asset download", dept, "replace existing movies")
                    # if it exists use that, otherwise use the general preference for replacing assets
                    if isinstance(pref, dict):
                        replace_pref = pref["replace existing movies"]
                    else:
                        replace_pref = gen_replace_pref

                    if replace_pref:
                        # all dept assets in same location
                        dept_dl_location = shot_assets[shot_name][dept][0]["local download path"]

                        # check if folder exists, if not make it
                        if not os.path.exists(dept_dl_location):
                            error = pyani.core.util.make_all_dir_in_path(dept_dl_location)
                            if error:
                                self.mngr.send_thread_error(error)
                                return error

                        # see if dept has a file(s) already in the download folder, ignore downloaded files
                        existing_files_in_dir = [
                            os.path.join(dept_dl_location, file_name) for file_name in
                            pyani.core.util.get_all_files(dept_dl_location, walk=False)
                            if os.path.join(dept_dl_location, file_name) not in self.download_list
                        ]

                        for existing_file in existing_files_in_dir:
                            # if using precedence, just check if seq and shot match,, otherwise check if the
                            # seq, shot and dept match
                            if sequence.lower() in existing_file.lower() and shot_name.lower() in existing_file.lower():
                                if precedence_pref:
                                    error = self._replace_shot_asset(existing_file, sequence, shot_name, dept)
                                    if error:
                                        self.mngr.send_thread_error(error)
                                        return error
                                elif self.app_vars.review_depts[dept].lower() in existing_file.lower():
                                    error = self._replace_shot_asset(existing_file, sequence, shot_name, dept)
                                    if error:
                                        self.mngr.send_thread_error(error)
                                        return error

        '''
        Updating download location for any moved seq and/or shot assets
        '''
        # check for moved files due to precedence
        if precedence_pref:
            for seq in self.review_assets:
                for asset in self.review_assets[seq]:
                    if not pyani.core.util.is_valid_shot_name(asset):
                        for index, _ in enumerate(self.review_assets[seq][asset]):
                            if seq in moved_files:
                                orig_file_path = os.path.join(
                                    self.review_assets[seq][asset][index]['local download path'],
                                    self.review_assets[seq][asset][index]['file name']
                                )
                                new_file_path = os.path.join(
                                    gen_dl_loc,
                                    self.review_assets[seq][asset][index]['file name']
                                )
                                if self.review_assets[seq][asset][index]['file name'] in moved_files[seq]:
                                    # change path in review assets
                                    self.review_assets[seq][asset][index]['local download path'] = gen_dl_loc
                                    # also need to update downloaded files
                                    self.download_list.remove(orig_file_path)
                                    self.download_list.append(new_file_path)
                    else:
                        for dept in self.review_assets[seq][asset]:
                            for index, _ in enumerate(self.review_assets[seq][asset][dept]):
                                if seq in moved_files and asset in moved_files[seq] and dept in moved_files[seq][asset]:
                                    orig_file_path = os.path.join(
                                        self.review_assets[seq][asset][dept][index]['local download path'],
                                        self.review_assets[seq][asset][dept][index]['file name']
                                    )
                                    new_file_path = os.path.join(
                                        gen_dl_loc,
                                        self.review_assets[seq][asset][dept][index]['file name']
                                    )
                                    if self.review_assets[seq][asset][dept][index]['file name'] in moved_files[seq][asset][dept]:
                                        # change path in review assets
                                        self.review_assets[seq][asset][dept][index]['local download path'] = gen_dl_loc
                                        # also need to update downloaded files
                                        self.download_list.remove(orig_file_path)
                                        self.download_list.append(new_file_path)

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
                        file_path = os.path.join(
                            review_asset['local download path'],
                            review_asset['file name']
                        )
                        if file_path in self.download_list:
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
                            file_path = os.path.join(
                                review_asset['local download path'],
                                review_asset['file name']
                            )
                            if file_path in self.download_list:
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

    def _replace_placeholders(self, local_download_path, seq=None, dept=None):
        """
        Replaces dynamic placeholders for things like seq name, dept name and review date
        :param local_download_path: the absolute path on disk where the movies are to be stored - doesn't include
        movie file name, just up to the parent directory
        :param seq: optional, the seq name as Seq### where ### is the sequence number
        :param dept: optional, the name of the department - see pyani.core.appvars.review_depts
        :return: the download path with placeholders replaced by actual values
        """

        # check if sequence is to be included in path
        if "seq" in local_download_path.lower() and "###" in local_download_path and seq:
            # remove the placeholder seq### (we convert to lower case so case doesn't matter) and add the
            # actual sequence
            start = local_download_path.lower().find("seq###")
            local_download_path = local_download_path[:start] + seq
            local_download_path = os.path.normpath(local_download_path)

        # check if review date should be used in path
        if "yyyymmdd" in local_download_path:
            # remove the placeholder and add the actual review date
            local_download_path = local_download_path.replace("yyyymmdd", self.review_date)

        # check if dept name should be used
        if 'dept' in local_download_path and dept:
            # remove the placeholder and add the actual dept
            local_download_path = local_download_path.replace("dept", dept)

        return local_download_path

    def _replace_seq_asset(self, review_asset, existing_file, seq, dept):
        """
        Replaces a seq asset deleting it from disk. If no error deleting records in the review asset member dictionary
        the name of the removed file
        :param review_asset: a dictionary containing the file name of the downloaded asset
        :param existing_file: the path of the existing file on disk for the asset
        :param seq: the seq number as a string Seq###
        :param dept: the department name, see pyani.core.appvars.review_depts
        :return: error if occurs otherwise none
        """
        new_asset_file_name = review_asset["file name"]
        # check if has part# in file name
        pattern = "part\d{1,}"

        # check for part name in both
        if re.search(pattern, existing_file) and re.search(pattern, new_asset_file_name):
            part_name_existing_file = re.search(pattern, existing_file).group()
            part_name_new_file = re.search(pattern, new_asset_file_name).group()
            # check if part names match, if so delete
            if part_name_existing_file == part_name_new_file:
                error = pyani.core.util.delete_file(existing_file)
                if error:
                    return error
                # record what file was replaced
                self.review_assets[seq][dept][0]['replaced file'] = existing_file
        # no part name - have to check no part name in both, because otherwise could get a part name in one but not
        # a part name in the other
        elif not re.search(pattern, existing_file) and not re.search(pattern, new_asset_file_name):
            error = pyani.core.util.delete_file(existing_file)
            if error:
                return error
            # record what file was replaced
            self.review_assets[seq][dept][0]['replaced file'] = existing_file

        return None

    def _replace_shot_asset(self, existing_file, seq, shot, dept):
        """
        Replace a shot asset on disk. If successfully replaces, then record the name of the asset replaced
        :param existing_file: the path on disk of the asset to replace
        :param seq: the seq number as a string in format Seq###
        :param shot: the shot number as a string in format Shot###
        :param dept: the department name as a string, see pyani.core.appvars.review_depts
        :return: error if occurs deleting asset on disk, otherwise none
        """
        error = pyani.core.util.delete_file(existing_file)
        if error:
            return error
        self.review_assets[seq][shot][dept][0]['replaced file'] = existing_file
        return None
