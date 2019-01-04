import ffmpeg
import os
import sys
import tempfile
import re
import pyani.core
import traceback
from subprocess import Popen
from pyani.media.image.seq import AniImageSeq
from pyani.media.image.core import AniImage, AniFrame, convert_image


class AniShoot:
    """
    TODO: add explaination of how class works, especially combiend sequences and being last element
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
        self.tempDir = os.path.join(tempfile.gettempdir(), "PyShoot")
        # missing frame image
        self.missing_frame_image = {"exr" : os.path.join(os.getcwd(),"resources\\missing_frame.exr"),
                                    "jpg" : os.path.join(os.getcwd(),"resources\\missing_frame.jpg"),
                                    "jpeg": os.path.join(os.getcwd(),"resources\\missing_frame.jpg"),
                                    "png":  os.path.join(os.getcwd(),"resources\\missing_frame.png")
                                    }

        # cleanup temp directory if it exists from app not closing properly previous launch
        pyani.core.util.make_dir(self.tempDir)

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
        """
        return os.path.abspath(os.path.join(self.__seq_list[0].directory(), os.pardir))

    def create_sequences(self, image_path_list):
        """
        Builds a list of sequence(s) based off a list of image paths. Stores in
        member variable seq_list. Clears the member variable if it has sequences in it.
        :param image_path_list: a list of paths to images, ex:
        C:\Images\sq180\s.1001.exr
        :return: None
        """
        # reset sequence if exists
        if self.__seq_list:
            self.__seq_list = []

        # process any image paths that are directories and get images
        images_from_directories_list = []
        for image_path in image_path_list:
            if os.path.isdir(image_path):
                images_from_directories_list.extend(pyani.core.util.get_images_from_dir(image_path))

        # add directory images to main list
        if images_from_directories_list:
            image_path_list = images_from_directories_list

        # remove image paths that are directories from image list
        for index, image_path in enumerate(image_path_list):
            if os.path.isdir(image_path):
                image_path_list.pop(index)

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

        pyani.core.util.LOG.debug("Create Sequence: {0}".format(self.__seq_list))

    def combine_sequences(self):
        """
        Combines multiple sequences into one, and stores as a new sequence at the end of the sequence list. This
        preserves the original sequences to revert if the user un checks combine sequences.
        :return error msg if can't combine, None if combine successfully
        """
        # check if a sequence exists and the combine flag is true, if not don't combine sequence lists
        if self.combine_seq and self.seq_list:
            flattened_sequences = []
            renamed_image_paths = []
            # build a regular python list of pyani.media.image.core.AniImage objects
            for seq in self.__seq_list:
                for image in seq:
                    flattened_sequences.append(image)

            # rename the image paths in the image objects and re-index the frames
            for index, image in enumerate(flattened_sequences):
                filename_replaced = image.name.replace(image.base_name, self.temp_image_name)
                new_frame = AniFrame.from_int(index+1, 4, filename_replaced)
                frame_reindexed = filename_replaced.replace(str(image.frame), str(new_frame))
                # fix the prefix so that all prefixes are the same - a dot '.'
                if not image.frame.prefix == ".":
                    last_position = frame_reindexed.rfind(image.frame.prefix)
                    frame_reindexed = frame_reindexed[:last_position] + "." + frame_reindexed[last_position+1:]
                new_image_name = os.path.join(self.tempDir, frame_reindexed)
                renamed_image_paths.append(new_image_name)
                # copy original image to temp dir so it exists
                pyani.core.util.copy_image(image.path, new_image_name)

            try:
                # build a image sequence of the new named images and add to the end of the existing sequence list
                self.__seq_list.append(AniImageSeq([AniImage(image) for image in renamed_image_paths]))
            except pyani.media.image.seq.AniImageSeqError:
                # for debugging so don't lose the actual error
                traceback.print_exc(file=sys.stdout)
                return "Could not combine sequences. See console for errors."
            return None

    def separate_sequences(self):
        """Removes the combined sequence at the end of the sequence list"""
        if self.seq_list:
            self.__seq_list.pop(-1)

    def create_movie(self, steps, frame_range, movie_path, movie_quality):
        """
        Create a movie for each image sequence. Tries to create movie, if can't logs and tries the next movie
        :param steps: frame step size
        :param frame_range: frame range from user
        :param movie_path: the movie name
        :param movie_quality: the quality - regular or uncompressed
        :return: a text log, movie_names
        """
        # this will return the sequence list - handles edge cases when dealing with a combined sequence
        # see class doc string for more information
        seq_list = self.seq_list

        movie_log = ""
        movie_list = [movie_path]

        # process output path
        if len(seq_list) > 1 and not self.combine_seq:
            if not movie_path.find(".%d.") == -1:
                movie_list = [movie_path.replace("%d", str(index+1)) for index in range(0, len(seq_list))]
            else:
                movie_list = [movie_path.replace("[seq_shot]", seq.name) for seq in seq_list]

        for movie_number, seq in enumerate(seq_list):
            # figure out if start / end sequence is based off the sequence and/or user input
            user_frame_start, user_frame_end = self._setup_frame_range(frame_range, seq)
            image_seq_to_write = seq
            # if user frame start is outside image seq start or seq end or missing frames or steps > 1
            # fill in missing frames. this test is an optimization for when all frames exist, user frame range
            # is within sequence frame range and steps are 1. In that case no need to modify sequence and can skip
            # copying sequence images to temp dir
            if user_frame_start < seq.start_frame() or user_frame_end > seq.end_frame() \
               or len(seq.missing()) > 0 or steps > 1:
                # first copy all frames to temp dir and fill missing frames. This handles any missing frames, shooting a
                # separated frame range (i.e. [1-5,10,30-50] and sequential range (1-100)
                image_seq_to_write = self._copy_and_fill_seq2(seq, user_frame_start, user_frame_end)
            # next setup steps for ffmpeg
            if steps > 1:
                self._setup_steps_for_write(image_seq_to_write, steps)
            # write movie
            if not self.write_movie(movie_list[movie_number], user_frame_start, image_seq_to_write, movie_quality):
                movie_log += "\t{0}\n".format(movie_list[movie_number])
            pyani.core.util.LOG.debug("Problem creating these movie:\n{0}".format(movie_log))
        return movie_log, movie_list

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
        :return: True if successful, False if fails
        """

        # format image list for ffmpeg
        width, height = seq[0].size
        formatted_size = "{0}x{1}".format(width, height)
        in_path = "{0}\{1}.{2}.{3}".format(seq.directory(), seq[0].base_name, seq.padding(), seq[0].ext)
        pyani.core.util.LOG.debug("FFMPEG ({0}):".format(self.movie_create_app))
        pyani.core.util.LOG.debug("\tin_path, start frame: {0} , {1}".format(in_path, user_frame_start))
        pyani.core.util.LOG.debug("\tout_path: {0}".format(out_path))

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
            pyani.core.util.rm_dir(self.tempDir)
            return True

        except ffmpeg.Error as e:
            pyani.core.util.LOG.debug("\t{0}".format(e.stderr))
            pyani.core.util.rm_dir(self.tempDir)
            return False

    def play_movies(self, movie_list):
        """
        Plays the created movie in the playback app
        :param movie_list: a list of movie paths
        """
        pyani.core.util.launch_app(self.movie_playback_app, movie_list)

    def _copy_and_fill_seq2(self, seq, user_frame_start, user_frame_end):
        # TODO : check where need to convert to AniFrames
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
        :return: a pyani.image_seq.AniImageSeq object of the copied images
        """

        pyani.core.util.LOG.debug("Copy and Fill Sequence {0} - {1}:".format(user_frame_start, user_frame_end))

        # create the correct image version of the missing file image
        try:
            missing_frame_image = self.missing_frame_image[seq[0].ext]
        except KeyError:
            missing_frame_image = convert_image(self.missing_frame_image['png'], seq[0].ext)

        # name of files (up to frame) in temp dir
        image_head_temp = os.path.join(self.tempDir, seq.name + "_" + seq[0].base_name)

        seq_start = seq.start_frame()
        seq_end = seq.end_frame()

        """
        Get all missing frames
        """

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
            missing_frames.extend([AniFrame(seq[0].path.replace(str(seq_start), str(f)))
                                   for f in missing_temp_padded])
        # user end is after seq end
        if user_frame_end > seq_end:
            # get missing frames based off user inputted end - a range of ints
            missing_temp = range(int(seq_end) + 1, int(user_frame_end) + 1)
            # make into frames with padding
            pad = user_frame_end.pad
            missing_temp_padded = [str(frame).rjust(pad, '0') for frame in missing_temp]
            # convert to frame objects
            missing_frames.extend([AniFrame(seq[-1].path.replace(str(seq_end), str(f)))
                                   for f in missing_temp_padded])
        missing_frames = sorted(missing_frames)

        """
        copy existing frames to missing
        """
        # the copied images as string paths
        copied_image_list = []
        # copy existing frames so that when we fill frames in, can copy from these. Don't want to change anything
        # in the original image directory. Also create an image object for the new copied image. Do after copy since
        # image must exist
        for image in seq:
            # make sure images are in the user frame range, if not don't add to list or copy.
            if user_frame_start <= image.frame <= user_frame_end:
                image_renamed = "{0}.{1}.{2}".format(image_head_temp, image.frame, image.ext)
                pyani.core.util.copy_image(image.path, image_renamed)
                copied_image_list.append(AniImage(image_renamed))

        pyani.core.util.LOG.debug("\tExisting Frames: {0}".format(copied_image_list))
        pyani.core.util.LOG.debug("\tMissing Frames: {0}".format(missing_frames))

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
                    first_existing_frame = AniFrame.from_int(f, seq.padding(formatted=False), seq[0].path)
                    if os.path.exists(first_existing_frame.image_parent):
                        frame_to_copy = first_existing_frame
                        break
            # we know the frame before this missing one exists since its not the start
            else:
                # the frame number right before the missing frame, converted to a padded frame
                frame_to_copy = AniFrame.from_int(frame-1, seq.padding(formatted=False), seq[0].path)

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
            frame_padded = AniFrame.from_int(frame, seq.padding(formatted=False), seq[0].path)
            missing_image = "{0}.{1}.{2}".format(image_head_temp, frame_padded, seq[0].ext)
            pyani.core.util.copy_image(image_to_copy, missing_image)
            pyani.core.util.LOG.debug("\t\tCopy {0} to {1}".format(image_to_copy, missing_image))
            copied_image_list.append(AniImage(missing_image))

        filled_sequence = AniImageSeq(sorted(copied_image_list))
        pyani.core.util.LOG.debug("\tFilled Sequence: {0}".format(filled_sequence))
        return filled_sequence

    def _copy_and_fill_seq(self, seq, user_frame_start, user_frame_end):
        # TODO : check where need to convert to AniFrames
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
        :return: a pyani.image_seq.AniImageSeq object of the copied images
        """

        pyani.core.util.LOG.debug("Copy and Fill Sequence {0} - {1}:".format(user_frame_start, user_frame_end))

        # create the correct image version of the missing file image
        try:
            missing_frame_image = self.missing_frame_image[seq[0].ext]
        except KeyError:
            missing_frame_image = convert_image(self.missing_frame_image['png'], seq[0].ext)

        # if multiple sequence have images with the same name
        image_head_temp = os.path.join(self.tempDir, seq.name + "_" + seq[0].base_name)
        # the copied images as string paths
        copied_image_list = []

        seq_start = seq.start_frame()
        seq_end = seq.end_frame()

        # missing frames between seq start and end
        missing_frames = seq.missing()
        frames_to_keep = []
        # remove frames the user doesn't want
        for frame in missing_frames:
            if user_frame_start <= frame <= user_frame_end:
                frames_to_keep.append(frame)
        missing_frames = frames_to_keep

        # if the user's frame start and end are not the same as sequence, do some processing, otherwise skip
        if not (user_frame_start == seq_start and user_frame_end == seq_end):
            # is the user frame start before the actual start, if so back fill - we know these images don't
            # exist since the sequence start is the first existing image
            if user_frame_start < seq_start:

                # get missing frames based off user inputted start
                missing_temp = range(int(user_frame_start), int(seq_start))
                # make into frames with padding
                pad = user_frame_start.pad
                missing_temp_padded = [str(frame).rjust(pad, '0') for frame in missing_temp]

                # convert to frame objects
                missing_frames.extend([AniFrame(seq[0].path.replace(str(seq_end),str(f)))
                                       for f in missing_temp_padded])

            # if user frame is after the seq end, copy seq end until reach user end. Know these don't exist because
            # seq end is the last existing image
            if user_frame_end > seq_end:
                # get missing frames based off user inputted end - a range of ints
                missing_temp = range(int(seq_end)+1, int(user_frame_end)+1)
                # make into frames with padding
                pad = user_frame_end.pad
                missing_temp_padded = [str(frame).rjust(pad, '0') for frame in missing_temp]
                # convert to frame objects
                missing_frames.extend([AniFrame(seq[-1].path.replace(str(seq_end),str(f)))
                                       for f in missing_temp_padded])

        # copy existing frames so that when we fill frames in, can copy from these. Don't want to change anything
        # in the original image directory. Also create an image object for the new copied image. Do after copy since
        # image must exist
        for image in seq:
            image_renamed = "{0}.{1}.{2}".format(image_head_temp, image.frame, image.ext)
            pyani.core.util.copy_image(image.path, image_renamed)
            # make sure images are in the user frame range, if not don't add to list. note need to copy, that's
            # why the above is always run. we will use the existing start to copy sometimes. But the list below
            # is our copied frame range we are using, so existing images may not be apart of it.
            if user_frame_start <= image.frame <= user_frame_end:
                copied_image_list.append(AniImage(image_renamed))

        pyani.core.util.LOG.debug("\tExisting Frames: {0}".format(copied_image_list))
        pyani.core.util.LOG.debug("\tMissing Frames: {0}".format(missing_frames))

        # loop through missing frames, and copy from previous frame, skipping existing frames
        while missing_frames:
            # remove first missing frame from the list
            frame = missing_frames.pop(0)

            # check if missing image is before the seq start, happens when user inputs a start frame before the
            # sequence start - typically when bad frames render, and don't have the starting frame(s)
            if frame < seq_start:
                # as a padded frame
                frame_to_copy = seq_start
            else:
                # the frame number right before the missing frame, converted to a padded frame
                # TODO : make AniFrame
                frame_to_copy = pyani.core.util.convert_frame_to_padded_frame(frame - 1, seq.padding(formatted=False))

            # after sequence start, so copy seq start, if doesn't exist
            if frame == user_frame_start and user_frame_start > seq_start:
                frame_to_copy = seq_start

            # figure out which image we are using for the missing frame
            if self.frame_hold:
                # construct image path to copy
                image_to_copy = "{0}.{1}.{2}".format(image_head_temp, frame_to_copy, seq[0].ext)
            else:
                # using the 'missing frame' image
                image_to_copy = missing_frame_image

            # construct image path to copy to
            # TODO : make AniFrame
            frame_padded = pyani.core.util.convert_frame_to_padded_frame(frame, seq.padding(formatted=False))
            missing_image = "{0}.{1}.{2}".format(image_head_temp, frame_padded, seq[0].ext)
            pyani.core.util.copy_image(image_to_copy, missing_image)
            pyani.core.util.LOG.debug("\t\tCopy {0} to {1}".format(image_to_copy, missing_image))
            copied_image_list.append(AniImage(missing_image))

        filled_sequence = AniImageSeq(sorted(copied_image_list))

        pyani.core.util.LOG.debug("\tFilled Sequence: {0}".format(filled_sequence))

        return filled_sequence

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
        """
        pyani.core.util.LOG.debug("Steps {0}:".format(steps))

        # loop through frame range, increment by step size - this ends one frame before the last frame
        # don't need to copy the last frame
        for index in range(0, len(image_seq)-1, steps):
            # grab the current frame
            image_to_copy = image_seq[index].path
            # loop through current frame to current frame + step size
            for sub_index in range(index+1, (index+steps)):
                # copy the current frame to the frame steps
                image_to_overwrite = image_seq[sub_index].path
                pyani.core.util.copy_image(image_to_copy, image_to_overwrite)

    @staticmethod
    def _setup_frame_range(frame_range, seq):
        """
        process frame range input - figure out if start / end sequence is based off the sequence and/or user input
        :param frame_range: a frame range as a string
        :param seq: an image sequence - pyani.media.image.seq.AniImageSeq object
        :returns: the frame range start and frame range end as frame objects - pyani.media.image.core.AniFrame
        """
        seq_start = seq.start_frame()
        seq_end = seq.end_frame()
        user_frame_start = seq_start
        user_frame_end = seq_end

        # first see if we have multiple sequences, if not proceed
        if not frame_range == "N/A":
            # get the user's input for frame range
            temp_start = re.search(r'\d+', frame_range).group()
            temp_end = re.findall(r'\d+', frame_range)[-1]

            # make frame objects
            temp_path_start = seq[0].path.replace(str(seq_start), temp_start)
            user_frame_start = AniFrame(temp_path_start)
            temp_path_end = seq[-1].path.replace(str(seq_end), temp_end)
            user_frame_end = AniFrame(temp_path_end)

        return user_frame_start, user_frame_end


class AniShootUi(object):

    def __init__(self):
        pass

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

    def validate_shot_info(self):
        # TODO: check frame range inputted against actual shot frame range - need cg teamworks
        pass

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

    @staticmethod
    def process_input(user_input, shoot):
        error_msg = None
        # only process selection if a selection was made
        if user_input:
            # create pyani.media.image.seq.AniImageSeq objects
            shoot.create_sequences(user_input)
            # check if combine sequences is checked, if so combine
            if shoot.combine_seq:
                error_msg = shoot.combine_sequences()
        return error_msg, shoot

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

    def validate_submission(self, seq_list, combined, frame_range, movie_name, overwrite):
        """
        Validates the submission options frame range and movie name
        :param seq_list: the list of image sequences
        :param combined : flag indicating if the sequence is a combined image sequence
        :param frame_range: the frame range
        :param movie_name: movie output path
        :param overwrite: whether to overwrite if movie exists
        :return: Error message if encountered, None otherwise
        """
        # check for letters or symbols in frame range
        if not self.validate_frame_range(frame_range):
            return "Invalid characters in frame range"
        # check if name is blank or doesn't have a valid extension
        if not self.validate_movie_name(seq_list, combined, movie_name):
            error_msg = (
                "Please provide a valid movie name (only .mp4 supported). If you are making multiple movies (GUI ONLY),"
                " use either:\n seq/shot format : path_to_movie\[seq_shot].mp4\n"
                " numbered format : path_to_movie\movie_name.%d.mp4"
            )
            return error_msg

        # check if movie exists and user doesn't have the overwrite checkbox checked
        if os.path.exists(str(movie_name)) and not overwrite:
            msg = "Movie exists. Please toggle on the 'overwrite if exists' option."
            return msg
        return None
