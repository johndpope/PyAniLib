from pyani.media.image.core import AniImage, AniFrame
import pyani.core.util
import os


class AniImageSeqError(Exception):
    """Special exception for Sequence errors
    """
    pass


class AniImageSeq(list):
    """
    Class that represents an image sequence. Contains pyani.core.image objects. An image is part
    of a sequence if the file name and ext match.
    """

    def __init__(self, images, strict_pad=True):
        """
        Constructor
        :param images: one or more pyani.image.AniImage objects
        :param strict_pad: option strict pad flag (True means padding must match)
        """

        # if pass a single image in, turn into a one element list
        if not isinstance(images, list):
            images = [images]

        super(AniImageSeq, self).__init__([AniImage(images.pop(0))])

        self.__strict_pad = strict_pad
        self.__missing = []     # list of integers representing missing frames
        self.__frames = None    # list of integers representing the frames in the sequence
        self.__name = None      # name of the sequence TODO: eventually this can be seq_shot when we get info

        while images:
            self.append(images.pop(0))

    def __str__(self):
        return self.format()

    def __repr__(self):
        return '<pyani.media.image.seq.AniImageSeq "%s">' % str(self)

    def __getattr__(self, key):
        return getattr(self[0], key)

    def __contains__(self, image):
        super(AniImageSeq, self).__contains__(AniImage(image))

    def __setitem__(self, index, image):
        """ Used to set a particular element in the sequence
        """
        # convert to an animage if its a string path
        if type(image) is not AniImage:
            image = AniImage(image)

        # check if image exists in sequence
        if self.includes(image):
            super(AniImageSeq, self).__setitem__(index, image)
            self.__frames = None
            self.__missing = None
        else:
            raise AniImageSeqError("Image is not a member of the image sequence.")

    @property
    def strict_pad(self):
        """:return: whether strict padding is enabled"""
        return self.__strict_pad

    @property
    def name(self):
        """ :return: the directory holding the images"""
        return self[0].dirname.split("\\")[-1]

    def format(self):
        """ :return: the formatted sequence as path_to_images\image[range].ext"""
        return "{0}\{1}{2}{3}.{4}".format(self[0].dirname,
                                          self[0].base_name,
                                          self[0].frame.prefix,
                                          self.frame_range(),
                                          self[0].ext)

    def directory(self):
        """ :return: the directory containing the images"""
        return self[0].dirname + os.sep

    def frames(self):
        """:return: List of frames sequence as pyani.core.image.AniFrames sorted"""
        self.__frames = self._get_frames()
        self.__frames.sort()
        return self.__frames

    def frame_range(self):
        """:return: frame range string, e.g. [1-500]"""
        return self._get_frame_range(self.frames())

    def start_frame(self):
        """:return: First frame in sequence as pyani.core.image.AniFrame"""
        return self.frames()[0]

    def end_frame(self):
        """:return: Last frame in sequence as pyani.core.image.AniFrame"""
        return self.frames()[-1]

    def padding(self, formatted=True):
        """ TODO
        Sequence frame padding, formatted as %0d, unless format is false then return padding as int: %ie 001 = 3
        :param formatted: whether to format as %0d or just return the padding length
        :return: formatted padding or integer representing number of padding
        """
        if not formatted:
            return self[0].frame.pad
        return self._get_padding()

    def missing(self):
        """:return: List of missing frames as pyani.core.image.AniFrame objects."""
        # check if missing has been set, if not set, otherwise return missing image list
        if not hasattr(self, '__missing') or not self.__missing:
            self.__missing = self._get_missing()
        return self.__missing

    def path(self):
        """:return: Absolute path to sequence including all images => C:\path_to_images\images_name[framerange].ext"""
        dir_name = str(os.path.dirname(os.path.abspath(self[0].path)))
        return os.path.join(dir_name, str(self))

    def includes(self, image):
        """Checks if the item can be included in this sequence. i.e. does it share the same file name
        For example:
            s = Sequence(['fileA.0001.jpg', 'fileA.0002.jpg'])
            s.includes('fileA.0003.jpg')
            True
            s.includes('fileB.0003.jpg')
            False
        """

        # check if the seq exists
        if len(self) > 0:
            if not isinstance(image, AniImage):
                image = AniImage(image)
            # check if the image is the same as the last image, if not see if it can be a member
            if self[-1] != image:
                return self._is_member(self[-1], image)
            # check if the image is the same as the first image, if not see if it can be a member
            elif self[0] != image:
                return self._is_member(self[0], image)
            else:
                #  only image int he sequence
                if self[0] == image:
                    return True

        return True

    def contains(self, image):
        """Checks for sequence membership.
        For example:
            s = Sequence(['fileA.0001.jpg', 'fileA.0002.jpg'])
            s.contains('fileA.0003.jpg')
            False
            s.contains('fileB.0003.jpg')
            False
        :param image: pyani.media.image.core.AniImage class object.
        :return: True if image is a sequence member.
        """
        if len(self) > 0:
            if not isinstance(image, AniImage):
                image = AniImage(image)
            return self.includes(image) and self.end_frame() >= image.frame >= self.start_frame()

        return False

    def append(self, image):
        """
        Adds another image to the sequence.
        :param image:  pyani.media.image.core.AniImage class object.
        :raises: an exception if image is not a sequence member.
        """
        if type(image) is not AniImage:
            image = AniImage(image)

        if self.includes(image):
            super(AniImageSeq, self).append(image)
            self.__frames = None
            self.__missing = None
        else:
            raise AniImageSeqError('Image {0} is not in this image sequence {1}'.format(image.path, self.path))

    def insert(self, index, image):
        """ Add another image to the sequence at the given index.
            :param image: a pyani.core.AnImage class object.
            :exc: `AniImageSeqError` raised if image is not a sequence member.
        """
        if type(image) is not AniImage:
            image = AniImage(image)

        if self.includes(image):
            super(AniImageSeq, self).insert(index, image)
            self.__frames = None
            self.__missing = None
        else:
            raise AniImageSeqError('Image {0} is not in this image sequence {1}'.format(image.path, self.path))

    def extend(self, images):
        """ Add images to the sequence.
            :param images: list of pyani.image.AniImage objects.
            :exc: `AniImageSeqError` raised if any images are not a sequence member.
        """
        for image in images:
            if type(image) is not AniImage:
                image = AniImage(image)

            if self.includes(image):
                super(AniImageSeq, self).append(image)
                self.__frames = None
                self.__missing = None
            else:
                raise AniImageSeqError('Image {0} is not in this image sequence {1}'.format(image.path, self.path))

    def _format_frames(self, frames):
        """
        converts frames as ints to padded frames as strings
        :param frames: a list of frames as ints
        :return: converted integer frames with padding as a string list
        """
        return [self._format_frame(frame) for frame in frames]

    def _format_frame(self, frame):
        """
        converts frame as int to padded frame as string
        :param frame: frame as an integer
        :return: converted integer frame with padding as a string
        """
        return str(frame).rjust(self[0].frame.pad, '0')

    def _get_padding(self):
        """:return: padding string format, e.g. %07d"""
        pad = self[0].frame.pad
        if pad is None:
            return ""
        if pad < 2:
            return '%d'
        return '%{0:02d}d'.format(pad)

    def _get_frame_range(self, frames, missing=True):
        """
        converts frame range string, e.g. [1-500].
        :param frames: list of ints like [1,4,8,12,15].
        :param missing: Expand sequence to exclude missing sequence indices.
        :return: formatted frame range string.
        """
        frange = []
        start = ''
        end = ''

        # if we don't need to check for missing frames
        if not missing:
            if frames:
                return '{0}-{1}'.format(self.start_frame(), self.end_frame())
            else:
                return ''

        # if no frames then return nothing
        if not frames:
            return ''

        # loop through frame range and build a list of the frames, will account for missing frames
        # and format as an example [1-3,5,10-12,15,20-24]
        for i in range(0, len(frames)):
            frame = frames[i]
            # if not at the start and frames aren't equal - happens when have missing frames
            if i != 0 and frame != frames[i - 1] + 1:
                # check if start and end are different, if so have a range so record
                if start != end:
                    frange.append('{0}-{1}'.format(str(start), str(end)))
                # the same start and end, so we have a single frame
                elif start == end:
                    frange.append(str(start))
                # start a new range by setting start and end to the current frame
                start = end = frame
                continue
            # if start empty or past the current frame - set back to prev frame
            if start is '' or start > frame:
                start = frame
            # if end is blank or before the current frame - update end to the current frame
            if end is '' or end < frame:
                end = frame

        # closes out frame range
        if start == end:
            frange.append(str(start))
        else:
            frange.append('{0}-{1}'.format(str(start), str(end)))

        return "[{0}]".format(", ".join(frange))

    def _get_frames(self):
        """returns the frames as pyani.core.image.AniFrame objects for all images in sequence
        """
        return [img.frame for img in self if img.frame is not None]

    def _get_missing(self):
        """
        Looks for missing frames in image sequence and returns the missing frames sorted. If there are
        no frames, returns an empty list
        :return: empty list if no frames, a list of pyani.core.image.AniFrame objects for missing frames
        """
        frames = [int(frame) for frame in self.frames()]
        if len(frames) == 0:
            return []

        # full frame range
        full_frame_range = range(int(frames[0]), int(frames[-1]) + 1)
        # find all missing frames, sorted. uses set's symmetric_difference method to find missing frames
        # symmetric_difference compares two sets to find the elements in one of the sets but not both
        # so compare the frames we have (frames) and the frames we should have (full_frame_range)
        missing = sorted(list(set(frames).symmetric_difference(full_frame_range)))

        missing_frames = []
        # convert frames back into frame objects
        for missing_frame in missing:
            missing_frames.append(AniFrame("{0}\{1}{2}{3}.{4}".format(self.directory(),
                                                                      self[0].base_name,
                                                                      self[0].frame.prefix,
                                                                      self._format_frame(missing_frame),
                                                                      self[0].ext)))
        return missing_frames

    def _is_member(self, image1, image2):
        """
        Determines if the images are part of the same sequence. Checks if file path
        and file name match
        :param image1: a pyani.media.core.image.AniImage
        :param image2: a pyani.media.core.image.AniImage
        :return: True if this and the other image are part of the same sequence.
        """
        # check for differences in name
        count = self._diff_name(image1, image2)
        return (count == 1) and (image1.parts == image2.parts) and (image1.dirname == image2.dirname)

    def _diff_name(self, image1, image2):
        """
        Examines differences in image name between image1 and image2 and make sure the same and frame
        padding the same.
        :param image1: pyani.media.core.image.AniImage object
        :param image2: pyani.media.core.image.AniImage object
        :return: count, count = 1 means same image
        """

        # grab digits in image name, gets a list of iterators
        l1 = [m for m in pyani.core.util.DIGITS_RE.finditer(image1.name)]
        l2 = [m for m in pyani.core.util.DIGITS_RE.finditer(image2.name)]

        count = 0
        # if not the same not the same image name
        if len(l1) == len(l2):
            # go through iterators to find frame
            for i in range(0, len(l1)):
                m1 = l1.pop(0)
                m2 = l2.pop(0)
                # check if its the same file name, if it is the same file, start() should match.
                # Also check if the digits match, if they do its part of the file name or the same frame
                # (i.e tex_v012_09.1001.exr, want to ignore the v012 and 09 part - group != group does that
                if (m1.start() == m2.start()) and (m1.group() != m2.group()):
                    # enforces padding - checks if padding must match and then checks padding length matches
                    if self.__strict_pad and (len(m1.group()) != len(m2.group())):
                        continue
                    # a dict of the frame, and the points in the image name it starts and finishes.
                    # useful for grabbing the image name without frame or extension or getting extension.
                    count += 1

        return count
