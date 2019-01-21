import ffmpeg
import os
import tempfile
import re
import pyani.core.util
from pyani.media.image.seq import AniImageSeq, AniImageSeqError
from pyani.media.image.core import AniImage, AniFrame, convert_image, AniImageError, AniFrameError
import logging

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtWidgets

logger = logging.getLogger()


class AniShoot:
    """
    Class that creates movies based off user specified frame range and steps.
    """
    def __init__(self, movie_generation, movie_playback, strict_pad):
        self.__seq_list = []

        # path to movie generation app executable
        self.movie_create_app = movie_generation
        # path to playback tool
        self.movie_playback_app = movie_playback
        # strict padding - currently passing to here, but not using, always defaulting to true in AniImageSeq objects
        self.strict_pad = strict_pad
        # default movie quality, ie crf
        self.default_quality = 18

        # indicates if the sequences are combined or not
        self.combine_seq = False
        # whether to frame hold
        self.frame_hold = True

        # temporary image file names when need to rename
        self.temp_image_name = "img_temp"
        # the temporary directory in windows for pyShoot
        self.temp_dir = os.path.join(os.path.normpath(tempfile.gettempdir()), "PyShoot")
        # missing frame image
        self.missing_frame_image = {"exr" : os.path.join(os.getcwd(),"resources\\missing_frame.exr"),
                                    "jpg" : os.path.join(os.getcwd(),"resources\\missing_frame.jpg"),
                                    "jpeg": os.path.join(os.getcwd(),"resources\\missing_frame.jpg"),
                                    "png":  os.path.join(os.getcwd(),"resources\\missing_frame.png")
                                    }

    @property
    def seq_list(self):
        """
        returns the list of sequences. if its a combined sequence get the combined sequence which is the
        last element and return just that sequence. Code calling this api shouldn't need to worry about
        the combined seq implementation (i.e. that we keep the uncombined sequences and just add the
        combine as the last element of the list
        :return: sequence list
        """
        if not self.__seq_list:
            return None

        if self.combine_seq:
            # wrap in list, since accessor wants a list
            return [self.__seq_list[-1]]
        return self.__seq_list

    def seq_parent_directory(self):
        """The top level directory of the image sequences
        :return the parent directory, or error if could not find it
        """
        try:
            parent_dir = os.path.abspath(os.path.join(self.__seq_list[0].directory(), os.pardir))
            return parent_dir
        except (IOError, OSError, WindowsError) as e:
            error_msg = "Could not get parent dir {0} for {1}. Error encountered: {2}".format(
                self.__seq_list[0].directory(),
                os.pardir,
                e
            )
            logger.exception(error_msg)
            return None

    def create_sequences(self, image_path_list):
        """
        Builds a list of sequence(s) based off a list of image paths. Stores in
        member variable seq_list. Clears the member variable if it has sequences in it.
        :param image_path_list: a list of paths to images, ex:
        C:\Images\sq180\s.1001.exr
        :return: Error if encountered, otherwise none
        """
        # reset sequence if exists
        if self.__seq_list:
            self.__seq_list = []

        # process any image paths that are directories and get images
        images_from_directories_list = []
        for image_path in image_path_list:
            if os.path.isdir(image_path):
                images = pyani.core.util.get_images_from_dir(image_path)
                # check if successfully got images, if not return the error
                if not isinstance(images, list):
                    return images
                images_from_directories_list.extend(images)

        # add directory images to main list
        if images_from_directories_list:
            image_path_list = images_from_directories_list

        # remove image paths that are directories from image list
        for index, image_path in enumerate(image_path_list):
            if os.path.isdir(image_path):
                image_path_list.pop(index)
        try:
            for image_path in image_path_list:
                # make an image object
                image = AniImage(image_path)
                # check if any sequences have been created
                if self.__seq_list:
                    for seq in self.__seq_list:
                        # sequence(s) exist, check if this image belongs to one or create a new sequence
                        if seq.includes(image):
                            seq.append(image)
                            break
                    else:
                        # image isn't part of an existing sequence, create a new one
                        self.__seq_list.append(AniImageSeq(image))

                else:
                    # no sequences yet, add image to a new sequence
                    self.__seq_list.append(AniImageSeq(image))
        except (AniImageError, AniImageSeqError, IndexError, ValueError) as e:
            error_msg = "Error creating image sequence from selection. Please see log. Error is: {0}".format(e)
            logger.exception(error_msg)
            return error_msg

        return None

    def combine_sequences(self, progress_update):
        """
        Combines multiple sequences into one, and stores as a new sequence at the end of the sequence list. This
        preserves the original sequences to revert if the user un checks combine sequences. reports progress to ui
        :param progress_update : a pyqt progress dialog object
        :return error msg if can't combine, None if combine successfully
        """
        # make temp directory
        pyani.core.util.make_dir(self.temp_dir)

        flattened_sequences = []
        renamed_image_paths = []

        # check if a sequence exists and the combine flag is true, if not don't combine sequence lists
        if self.combine_seq and self.seq_list:
            # update progress
            progress_update.setLabelText("Flattening {0} Sequences Into One Sequence...".format(len(self.seq_list)))
            progress_update.setValue(25)
            QtWidgets.QApplication.processEvents()

            # build a regular python list of pyani.media.image.core.AniImage objects - must be self.__seq_list,
            # and not self.seq_list, because self.seq_list is an external representation and would
            # return the last sequence which it assume is the combined sequence when combined is checked. combined is
            # checked but we haven't built the combined sequence yet, see doc string. __seq_list will give us the
            # internal representation which is the sequences to combine
            for seq in self.__seq_list:
                for image in seq:
                    flattened_sequences.append(image)

            progress_update.setLabelText("Renaming {0} images...".format(len(flattened_sequences)))
            progress_update.setValue(50)
            QtWidgets.QApplication.processEvents()
            src = []
            # rename the image paths in the image objects and re-index the frames
            for index, image in enumerate(flattened_sequences):
                filename_replaced = image.name.replace(image.base_name, self.temp_image_name)
                new_frame = AniFrame.from_int(index+1, 4, filename_replaced)
                frame_reindexed = filename_replaced.replace(str(image.frame), str(new_frame))
                # fix the prefix so that all prefixes are the same - a dot '.'
                if not image.frame.prefix == ".":
                    last_position = frame_reindexed.rfind(image.frame.prefix)
                    frame_reindexed = frame_reindexed[:last_position] + "." + frame_reindexed[last_position+1:]
                new_image_name = os.path.join(self.temp_dir, frame_reindexed)
                renamed_image_paths.append(new_image_name)
                src.append(image.path)

            thread_count = 120
            progress_update.setLabelText("Copying Images to Temp Dir Using {0} Threads. This could take a while "
                                         "if the images are large in size.".format(str(thread_count)))
            progress_update.setValue(75)
            QtWidgets.QApplication.processEvents()
            try:
                # threaded ok, order of copy doesn't matter
                pyani.core.util.ThreadedCopy(src, renamed_image_paths, threads=thread_count)
            except (IOError, OSError) as e:
                error_msg = "There was an error combining the sequences during copy. Error reported {0}".format(e)
                logger.exception(error_msg)
                return error_msg

            try:
                # build a image sequence of the new named images and add to the end of the existing sequence list
                self.__seq_list.append(AniImageSeq([AniImage(image) for image in renamed_image_paths]))
            except (AniImageSeqError, AniImageError) as e:
                error_msg = "There was an error combining the sequences. Error reported {0}".format(e)
                logger.exception(error_msg)
                return error_msg

            return None

    def separate_sequences(self):
        """Removes the combined sequence at the end of the sequence list"""
        if self.seq_list:
            self.__seq_list.pop(-1)

    def create_movie(self, steps, frame_range, movie_path, movie_quality, progress_update=None):
        """
        Create a movie for each image sequence. Tries to create movie, if can't logs and tries the next movie
        Reports progress back to the ui
        :param steps: frame step size
        :param frame_range: frame range from user
        :param movie_path: the movie name
        :param movie_quality: the quality - regular or uncompressed
        :param progress_update: a pyqt progress dialog object, optional
        :return: a text log, movie_names
        """

        # cleanup temp directory if it exists unless combining movie which already created this
        if not self.combine_seq:
            pyani.core.util.make_dir(self.temp_dir)

        # this will return the sequence list - handles edge cases when dealing with a combined sequence
        # see class doc string for more information
        seq_list = self.seq_list

        log = ""
        movie_list = [movie_path]
        movie_total = len(seq_list)

        # process output path
        if len(seq_list) > 1 and not self.combine_seq:
            if not movie_path.find(".%d.") == -1:
                movie_list = [movie_path.replace("%d", str(index+1)) for index in range(0, len(seq_list))]
            else:
                movie_list = [movie_path.replace("[seq_shot]", seq.name) for seq in seq_list]

        for movie_number, seq in enumerate(seq_list):
            # update progress
            if progress_update:
                progress_update.setLabelText(
                    "Creating Movie {0} of {1}\n\tSetting Up Frame Range".format(movie_number, movie_total)
                )
                progress_update.setValue(10)
                QtWidgets.QApplication.processEvents()

            # figure out if start / end sequence is based off the sequence and/or user input
            user_frame_start, user_frame_end, error = self._setup_frame_range(frame_range, seq)
            if error:
                log += "Movie {0} had the following errors: {1}".format(movie_list[movie_number], error)
                continue

            # update progress
            # get number of missing frames
            missing = len(seq.missing())
            if progress_update:
                progress_update.setLabelText(
                    "Creating Movie {0} of {1}\n\tFilling {2} Frames.".format(movie_number, movie_total, missing)
                )
                progress_update.setValue(30)
                QtWidgets.QApplication.processEvents()

            image_seq_to_write = seq
            # if user frame start is outside image seq start or seq end or missing frames or steps > 1
            # fill in missing frames. this test is an optimization for when all frames exist, user frame range
            # is within sequence frame range and steps are 1. In that case no need to modify sequence and can skip
            # copying sequence images to temp dir
            if user_frame_start < seq.start_frame() or user_frame_end > seq.end_frame() \
               or len(seq.missing()) > 0 or steps > 1:
                # first copy all frames to temp dir and fill missing frames. This handles any missing frames, shooting a
                # separated frame range (i.e. [1-5,10,30-50] and sequential range (1-100)
                image_seq_to_write, error = self._copy_and_fill_seq(seq, user_frame_start, user_frame_end)
                if error:
                    log += "Movie {0} had the following errors: {1}".format(movie_list[movie_number], error)
                    continue

            if progress_update:
                # update progress
                progress_update.setLabelText(
                    "Creating Movie {0} of {1}\n\tChecking Frame Steps".format(movie_number, movie_total)
                )
                progress_update.setValue(50)
                QtWidgets.QApplication.processEvents()

            # next setup steps for ffmpeg
            if steps > 1:
                error = self._setup_steps_for_write(image_seq_to_write, steps)
                if error:
                    log += "Movie {0} had the following errors: {1}".format(movie_list[movie_number], error)
                    continue

            # update progress
            if progress_update:
                progress_update.setLabelText(
                    "Creating Movie {0} of {1}\n\tWriting Movie to Disk".format(movie_number, movie_total)
                )
                progress_update.setValue(75)
                QtWidgets.QApplication.processEvents()

            # write movie
            error = self.write_movie(movie_list[movie_number], user_frame_start, image_seq_to_write, movie_quality)
            if error:
                log += "Movie {0} had the following errors: {1}".format(movie_list[movie_number], error)
        if log:
            logger.warning("Couldn't create the following movies: {0}".format(", ".join(log)))

        return log, movie_list

    def write_movie(self, out_path, user_frame_start, seq, movie_quality):
        """
        Writes a movie to disk using ffmpeg. Uses the python wrapper around ffmpeg called ffmpeg-python. The command
        below is equivalent to calling ffmpeg at the command line (below command assumes ffmpeg is in the system path,
        if not then replace ffmpeg with the full path to ffmpeg exe, ex: c:\ffmpeg\bin\ffmpeg:
        ffmpeg -start_number 1001 -apply_trc iec61966_2_1 -i C:\Users\Patrick\AppData\Local\Temp\PyShoot\s040.%04d.exr
        -c:v libx264 -pix_fmt yuv420p -video_size 1998x1080 out.mp4

        :param out_path: the movie file path
        :param user_frame_start : the frame the user wants to start on
        :param seq: the sequence of images to write as a pyani.image_seq.AniImageSeq object
        :param movie_quality: the quality - regular or uncompressed
        :return: error if encountered, otherwise none
        """

        # format image list for ffmpeg
        width, height = seq[0].size
        formatted_size = "{0}x{1}".format(width, height)
        in_path = "{0}\{1}.{2}.{3}".format(seq.directory(), seq[0].base_name, seq.padding(), seq[0].ext)

        logger.info("FFMPEG path is {0}\nImage sequence is {1}\n Start Frame is {2}\n Movie path is {3}".format(
                self.movie_create_app,
                in_path,
                user_frame_start,
                out_path
            )
        )

        if movie_quality:
            quality = 0
            preset = "ultrafast"
        else:
            quality = self.default_quality
            preset = "slower"

        try:
            (
                ffmpeg
                    .input(in_path, start_number=user_frame_start, apply_trc='iec61966_2_1')
                    .output(out_path, crf=quality, preset=preset, video_size=formatted_size, pix_fmt='yuv420p',
                            tune='animation', format='mp4', acodec='aac')
                    .overwrite_output()
                    .run(cmd=self.movie_create_app)
            )
            return None

        except ffmpeg.Error as e:
            error = "FFMPEG error :{0}".format(e)
            logger.exception(error)
            return error

    def play_movies(self, movie_list):
        """
        Plays the created movie in the playback app
        :param movie_list: a list of movie paths
        :return error if encountered, otherwise none
        """
        error = pyani.core.util.launch_app(self.movie_playback_app, movie_list)
        return error

    def cleanup(self):
        """Remove the temp directory
        """
        pyani.core.util.rm_dir(self.temp_dir)

    def _copy_and_fill_seq(self, seq, user_frame_start, user_frame_end):
        """
        Copies existing frames to temp dir, and fills missing frames based of the frame hold member variable
        If frame hold is checked, holds existing frame until next existing frame. Otherwise fills with an image that
        says 'missing frame'. Uses user's input frame range, so if the sequence should be 1-20, but the first image
        is on frame 5, it will back fill frames 1-4 with 5. Conversely, if the range is 1-20, but the last existing
        frame is frame 15, fills 16-20 with 15.

        LOGIC :

        copy the existing frames to the temp directory. Get the user's frame range input.
        If the user start is before or after seq start (first existing image) then start is the user start. Otherwise
        its the seq start. Same for user frame range end, if its before or after the seq end (last existing image), use
        user inputted end. Then fill in all the missing frames by copying from the temp directory. All work is done
        in the temp directory to avoid changing the original image directory. Note that if the user gives multiple
        sequences frame start and end are set to the sequences frame start/end. Frame range input is ignored.

        :param seq: a pyani.image_seq.AniImageSeq object
        :param user_frame_start: the frame the user wants to start on
        :param user_frame_end: the frame the user wants to end on
        :return: a pyani.image_seq.AniImageSeq object of the copied images and any errors
        """

        # create the correct image version of the missing file image
        try:
            missing_frame_image = self.missing_frame_image[seq[0].ext]
            logger.info("Missing image format is {0}".format(seq[0].ext))
        except KeyError:
            missing_frame_image = convert_image(self.missing_frame_image['png'], seq[0].ext)
            logger.info("Missing image format is png")

        # name of files (up to frame) in temp dir
        image_head_temp = os.path.join(self.temp_dir, seq.name + "_" + seq[0].base_name)

        seq_start = seq.start_frame()
        seq_end = seq.end_frame()

        # Get all missing frames

        # missing frames between user start and end, avoid missing frames outside user frame range
        missing_frames = [frame for frame in seq.missing() if user_frame_start <= frame <= user_frame_end]

        # user start is before sequence start
        if user_frame_start < seq_start:
            # get missing frames based off user inputted start
            missing_temp = range(int(user_frame_start), int(seq_start))
            # make into frames with padding
            pad = user_frame_start.pad
            missing_temp_padded = [str(frame).rjust(pad, '0') for frame in missing_temp]
            # convert to frame objects
            try:
                missing_frames.extend([AniFrame(seq[0].path.replace(str(seq_start), str(f)))
                                       for f in missing_temp_padded])
            except AniFrameError as e:
                error_msg = "Problem creating missing frames. Error is {0}".format(e)
                logger.exception(error_msg)
                return None, error_msg

        # user end is after seq end
        if user_frame_end > seq_end:
            # get missing frames based off user inputted end - a range of ints
            missing_temp = range(int(seq_end) + 1, int(user_frame_end) + 1)
            # make into frames with padding
            pad = user_frame_end.pad
            missing_temp_padded = [str(frame).rjust(pad, '0') for frame in missing_temp]
            # convert to frame objects
            try:
                missing_frames.extend([AniFrame(seq[-1].path.replace(str(seq_end), str(f)))
                                       for f in missing_temp_padded])
            except AniFrameError as e:
                error_msg = "Problem creating missing frames. Error is {0}".format(e)
                logger.exception(error_msg)
                return None, error_msg

        missing_frames = sorted(missing_frames)

        logger.info("Missing Frames are: {0}".format(missing_frames))

        # copy existing frames to missing

        # copy existing frames so that when we fill frames in, can copy from these. Don't want to change anything
        # in the original image directory. Also create an image object for the new copied image. Do after copy since
        # image must exist
        src = []
        dest = []
        thread_count = 90
        for image in seq:
            # make sure images are in the user frame range, if not don't add to list or copy.
            if user_frame_start <= image.frame <= user_frame_end:
                image_renamed = "{0}.{1}.{2}".format(image_head_temp, image.frame, image.ext)
                src.append(image.path)
                dest.append(image_renamed)
        try:
            # threaded ok, order of copy doesn't matter
            pyani.core.util.ThreadedCopy(src, dest, threads=thread_count)
        except (IOError, OSError, WindowsError) as e:
            error_msg = "Problem copying existing images in tmp dir. Error is {0}".format(e)
            logger.exception(error_msg)
            return None, error_msg

        try:
            # the copied images as string paths
            copied_image_list = [AniImage(image) for image in dest]
        except AniImageError as e:
            error_msg = "Problem creating existing images in tmp dir. Error is {0}".format(e)
            logger.exception(error_msg)
            return None, error_msg

        missing_dest = []
        # loop through missing frames, and copy from previous frame, skipping existing frames
        while missing_frames:
            # remove first missing frame from the list
            frame = missing_frames.pop(0)

            # check if missing image is before the seq start, happens when user inputs a start frame before the
            # sequence start - typically when bad frames render, and don't have the starting frame(s)
            if frame < seq_start:
                # as a padded frame
                frame_to_copy = seq_start
            # user start is after seq start
            elif frame > seq_start and frame == user_frame_start:
                # find closest frame - before this one
                for f in range(user_frame_start, seq_start-1, -1):
                    try:
                        first_existing_frame = AniFrame.from_int(f, seq.padding(formatted=False), seq[0].path)
                    except AniFrameError as e:
                        error_msg = "Problem creating AniFrame for first existing frame (unpadded) {0}." \
                                    " Error is {1}".format(str(f), e)
                        logger.exception(error_msg)
                        return None, error_msg
                    if os.path.exists(first_existing_frame.image_parent):
                        frame_to_copy = first_existing_frame
                        break
            # we know the frame before this missing one exists since its not the start
            else:
                try:
                    # the frame number right before the missing frame, converted to a padded frame
                    frame_to_copy = AniFrame.from_int(frame-1, seq.padding(formatted=False), seq[0].path)
                except AniFrameError as e:
                    error_msg = "Problem creating AniFrame for frame (unpadded) {0}. Error is {1}".format(
                        str(frame-1),
                        e
                    )
                    logger.exception(error_msg)
                    return None, error_msg
            # figure out which image we are using for the missing frame
            if self.frame_hold:
                # construct image path to copy - check for special case when user frame start is after seq_start
                # and was missing and have to copy from original directory
                if frame > seq_start and frame == user_frame_start:
                    image_to_copy = "{0}\\{1}.{2}.{3}".format(seq[0].dirname,seq[0].base_name,frame_to_copy,seq[0].ext)
                else:
                    image_to_copy = "{0}.{1}.{2}".format(image_head_temp, frame_to_copy,seq[0].ext)
            else:
                # using the 'missing frame' image
                image_to_copy = missing_frame_image

            # construct image path to copy to
            try:
                frame_padded = AniFrame.from_int(frame, seq.padding(formatted=False), seq[0].path)
            except AniFrameError as e:
                error_msg = "Problem creating AniFrame for frame {0}. Error is {1}".format(frame_padded, e)
                logger.exception(error_msg)
                return None, error_msg

            missing_image = "{0}.{1}.{2}".format(image_head_temp, frame_padded, seq[0].ext)
            missing_dest.append(missing_image)
            # this needs to be sequential, can't use threaded copy
            error_msg = pyani.core.util.copy_file(image_to_copy, missing_image)
            if error_msg:
                logger.exception(error_msg)
                return None, error_msg

        try:
            copied_image_list.extend([AniImage(image) for image in missing_dest])
            filled_sequence = AniImageSeq(sorted(copied_image_list))
        except (AniImageError, AniImageSeqError) as e:
            error_msg = "Problem creating missing images from existing images. Error is {0}".format(e)
            logger.exception(error_msg)
            return None, error_msg

        return filled_sequence, None

    @staticmethod
    def _setup_steps_for_write(image_seq, steps):
        """
        Creates an image sequence on disk that holds frames for the given step size. Does not modify file names.
        Expects a complete sequence, where every frame exists on disk
        For example:
        image.[1-20].exr steps 2 will copy frame 1 to frame 2, frame 3 to frame 4, etc... This gives the appearance
        that every other frame is held. FFMPEG requires an image is provided for every frame, so this provides a format
        that FFMPEG will accept.

        :param image_seq: a pyani.media.image.seq.AniImageSeq object
        :param steps: the frame step size
        :return error if encountered, none otherwise
        """
        src = []
        dest = []

        # loop through frame range, increment by step size - this ends one frame before the last frame
        # don't need to copy the last frame
        for index in range(0, len(image_seq)-1, steps):
            # grab the current frame
            image_to_copy = image_seq[index].path
            src.append(image_to_copy)
            # loop through current frame to current frame + step size
            for sub_index in range(index+1, (index+steps)):
                # copy the current frame to the frame steps
                image_to_overwrite = image_seq[sub_index].path
                dest.append(image_to_overwrite)

        try:
            # threaded ok, order of copy doesn't matter
            pyani.core.util.ThreadedCopy(src, dest, threads=90)
        except (IOError, WindowsError, OSError) as e:
            error_msg = "Problem creating images for steps. Error is {0}".format(e)
            logger.exception(error_msg)
            return error_msg

        return None

    @staticmethod
    def _setup_frame_range(frame_range, seq):
        """
        process frame range input - figure out if start / end sequence is based off the sequence and/or user input
        :param frame_range: a frame range as a string
        :param seq: an image sequence - pyani.media.image.seq.AniImageSeq object
        :returns: the frame range start and frame range end as frame objects - pyani.media.image.core.AniFrame and error
        if encountered
        """
        seq_start = seq.start_frame()
        seq_end = seq.end_frame()
        user_frame_start = seq_start
        user_frame_end = seq_end

        # first see if we have multiple sequences, if not proceed
        if not frame_range == "N/A":
            # get the user's input for frame range
            try:
                temp_start = re.search(r'\d+', frame_range).group()
                temp_end = re.findall(r'\d+', frame_range)[-1]
            except (ValueError, IndexError, AttributeError, TypeError) as e:
                error_msg = "Problem with frame range {0}. Error is {1}".format(frame_range, e)
                logger.exception(error_msg)
                return None, None, error_msg

            # make frame objects
            try:
                temp_path_start = seq[0].path.replace(str(seq_start), temp_start)
                user_frame_start = AniFrame(temp_path_start)
                temp_path_end = seq[-1].path.replace(str(seq_end), temp_end)
                user_frame_end = AniFrame(temp_path_end)
            except (IndexError, ValueError, AniFrameError, TypeError) as e:
                error_msg = "Problem with frame range {0}. Error is {1}".format(frame_range, e)
                logger.exception(error_msg)
                return None, None, error_msg

        logger.info(
            "Should be AniFrame Objects : user frame start {0}, user frame end {1}".format
            (
                user_frame_start,
                user_frame_end
            )
        )
        return user_frame_start, user_frame_end, None


class AniShootUi(object):

    def __init__(self):
        pass

    @staticmethod
    def process_input(user_input, shoot):
        """
        takes user input and makes an image sequence
        :param user_input: a list of image file paths
        :param shoot: the shoot object class
        :return: none or error if encountered
        """
        # only process selection if a selection was made
        if user_input:
            # create pyani.media.image.seq.AniImageSeq objects
            error_msg = shoot.create_sequences(user_input)
            if error_msg:
                return error_msg
            # check if combine sequences is checked, if so combine
            if shoot.combine_seq:
                error_msg = shoot.combine_sequences()
                if error_msg:
                    return error_msg
        return None

    @staticmethod
    def validate_steps(seq, steps):
        """
        Makes sure an image sequence contains valid step size
        :param seq: a pyani.media.image.seq.AniImageSeq class object
        :param steps: integer for frame steps
        :return: msg if fails, none if passes
        """
        msg = None
        # is step size greater than the frame range and its not a single image sequence
        if ((seq.start_frame() + steps) > seq.end_frame()) and (len(seq) > 1):
            msg = "Step Size of {0} is larger than the frame range {1}".format(steps, seq.frame_range())
        return msg

    @ staticmethod
    def validate_image_format(seq):
        """
        Makes sure an image sequence contains supported image formats
        :param seq: a pyani.media.image.seq.AniImageSeq class object
        :return: msg if fails, none if passes
        """
        msg = None
        for image in seq:
            # if selection isn't a supported image and its not a directory warn user
            if not image.ext.endswith(pyani.core.util.SUPPORTED_IMAGE_FORMATS) and not os.path.isdir(image.path):
                msg = (
                    "Your selection contains unsupported images. The following image types are supported: "
                    "{0}".format(' , '.join(pyani.core.util.SUPPORTED_IMAGE_FORMATS))
                )
            break
        return msg

    @staticmethod
    def validate_frame_range(frame_range):
        """Returns true if frame range is in format 1-3 or 1-3,5,... and its not N/A"""
        if not frame_range == "N/A":
            return bool(re.match('^[\d ,-]+$', frame_range))
        return True

    @staticmethod
    def validate_movie_name(seq_list, combined, mov_path):
        """
        check if movie name is valid - not empty, valid extension, correct format for multiple movie
        :param seq_list : list of sequences
        :param combined : boolean indicating if sequence is combined into one
        :param mov_path: movie path
        :return: False if any check fails, True if valid name
        """
        if mov_path == "":
            return False
        if not mov_path.endswith(pyani.core.util.SUPPORTED_MOVIE_FORMATS):
            return False
        # check if multiple sequences
        if len(seq_list) > 1 and not combined:
            # check if using a valid format
            if not re.search(r"[[\]]+", mov_path) and mov_path.find(".%d") == -1:
                return False
        return True

    def validate_selection(self, shoot, steps):
        """
        Validates the selected images
        :return: Error message if encountered, None otherwise
        """
        for seq in shoot.seq_list:
            msg = self.validate_steps(seq, steps)
            if msg:
                return msg
        return None

    def validate_submission(self, seq_list, combined, frame_range, movie_name, frame_steps):
        """
        Validates the submission options frame range and movie name
        :param seq_list: the list of image sequences
        :param combined : flag indicating if the sequence is a combined image sequence
        :param frame_range: the frame range
        :param movie_name: movie output path
        :param frame_steps: frame step size
        :return: Error message if encountered, None otherwise
        """
        # check for letters or symbols in frame range
        if not self.validate_frame_range(frame_range):
            return "Invalid characters in frame range"

        # check step size
        for seq in seq_list:
            error = self.validate_steps(seq, frame_steps)
            if error:
                return error

        # check if name is blank or doesn't have a valid extension
        if not self.validate_movie_name(seq_list, combined, movie_name):
            error_msg = (
                "Please provide a valid movie name (only .mp4 supported). If you are making multiple movies (GUI ONLY),"
                " use either:\n seq/shot format : path_to_movie\[seq_shot].mp4\n"
                " numbered format : path_to_movie\movie_name.%d.mp4"
            )
            return error_msg

        return None
