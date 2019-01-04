import os
import OpenEXR, Imath     # Imath needed when build standalone executables
from PIL import Image
from pyani.core import util


def convert_image(image_path, convert_format):
    """
    change to a different image format - all supported except exrs
    :param image_path: the image to convert
    :param convert_format: the format to convert to
    :return: the converted image
    """
    im = Image.open(image_path)
    image_ext_removed = image_path.split(".")[:-1]
    new_image = '{0}.{1}'.format(image_ext_removed, convert_format)
    im.save(new_image)
    return new_image


class AniImageError(Exception):
    """Special exception for Image errors
    """
    pass


class AniFrameError(Exception):
    """Special exception for Image errors
    """
    pass


class AniFrame(object):

    def __init__(self, img_path):

        self.frame_object = img_path
        # allow user to pass an AniFrame object, or a string path
        self.__image_parent = getattr(self.frame_object, 'image_parent', None)
        if self.__image_parent is None:
            self.__image_parent = os.path.abspath(str(img_path))

        # get the filename
        dir_name, filename = os.path.split(self.__image_parent)
        # gets the frame and where it starts and ends in the filename string
        self.__frame, self.__start, self.__end = self._get_frame_from_name(filename)
        # get the prefix, ie. dot (.), underscore (_) etc... that separates frame from filename
        # assumes only one character long
        self.__prefix = filename[self.start-1]
        # how many places in frame, ie is it 003, 0003, 03, 3, etc...
        self.__pad = len(self.__frame)

    @classmethod
    def from_int(cls, frame, pad, image_path):
        # make padded frame
        frame_padded = str(frame).rjust(pad, '0')
        # make image path
        frame_to_replace, start, end = cls._get_frame_from_name(image_path)
        image_path = image_path.replace(frame_to_replace, frame_padded)
        return cls(image_path)

    # compare strings for equal, since 0003 != 003, if do ints 0003 == 003 since strips 0
    def __eq__(self, other):
        if isinstance(other, int):
            return int(self.frame) == other
        return self.frame == other.frame

    def __ne__(self, other):
        if isinstance(other, int):
            return int(self.frame) != other
        return self.frame != other.frame

    def __lt__(self, other):
        if isinstance(other, int):
            return int(self.frame) < other
        return int(self.frame) < int(other.frame)

    def __gt__(self, other):
        if isinstance(other, int):
            return int(self.frame) > other
        return int(self.frame) > int(other.frame)

    def __ge__(self, other):
        if isinstance(other, int):
            return int(self.frame) >= other
        return int(self.frame) >= int(other.frame)

    def __le__(self, other):
        if isinstance(other, int):
            return int(self.frame) <= other
        return int(self.frame) <= int(other.frame)

    def __str__(self):
        return self.frame

    def __int__(self):
        return int(self.frame)

    def __repr__(self):
        return '<pyani.media.image.core.AniFrame "{0}">'.format(self.frame)

    def __getattr__(self, key):
        return getattr(self.frame_object, key)

    def __add__(self, other):
        if isinstance(other, int):
            return int(self.frame) + other
        return int(self.frame) + int(other.frame)

    def __sub__(self, other):
        if isinstance(other, int):
            return int(self.frame) - other
        return int(self.frame) - int(other.frame)

    @property
    def frame(self):
        return self.__frame

    @property
    def pad(self):
        return self.__pad

    @property
    def prefix(self):
        return self.__prefix

    @property
    def image_parent(self):
        return self.__image_parent

    @property
    def start(self):
        return self.__start

    @property
    def end(self):
        return self.__end

    @staticmethod
    def _get_frame_from_name(filename):
        """
        Get the frame from an image name, handles image names with digits in the image name
        For example ::
            'file01_0040.exr' -> 0040
        :return: frame number as string with it's start and end position in the string name
        """
        digits_matches = [digits for digits in util.DIGITS_RE.finditer(filename)]
        return digits_matches[-1].group(), digits_matches[-1].start(), digits_matches[-1].end()


class AniImage(str):
    """
        A class that describes an image. This class is a core part of the pyani package.
        Inherits the str class. Constructor takes either a string representing an image
        path on disk or an AnImage object. Image must exist or an AniImageError will be raised
        and program execution will stop.
    """

    def __init__(self, image):
        super(AniImage, self).__init__()
        self.image = image
        # allow user to pass a AnImage object, or a string path
        self.__path = getattr(image, 'path', None)
        if self.__path is None:
            self.__path = str(image)

        # image parts
        self.__dirname, self.__filename = os.path.split(self.__path)
        # all numeric parts image name
        self.__digits = util.DIGITS_RE.findall(self.name)
        # get all non numeric parts of image name
        self.__parts = util.DIGITS_RE.split(self.name)
        self.__size = (0, 0)

        # get image size using OpenExr for exrs and PIL for other image formats. Lighter weight than using cv2 which
        # causes standalone executable to be 30 megs bigger
        if OpenEXR.isOpenExrFile(self.path):
            try:
                exr_image = OpenEXR.InputFile(self.path)
                dw = exr_image.header()['dataWindow']
                self.__size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)
                exr_image.close()
            except (IOError, OSError, ValueError) as e:
                raise AniImageError('Image: {0} is not a valid exr.'.format(self.path))
        else:
            try:
                with Image.open(self.path) as img:
                    self.__size = img.size
            except (IOError, OSError, ValueError) as e:
                raise AniImageError('Image: {0} does not exist on disk or is invalid.'.format(self.path))

        try:
            # get the frame as a pyani.core. AniFrame object
            self.__frame = AniFrame(self.path)
        except IndexError:
            # image must not have a frame
            self.__frame = None

        # the start and end are at the . in file name, or whatever separates frame number from extension and image name
        # subtract one from start to get image name no '.' and add one to get extension no '.'
        if self.frame:
            self.__base_name = self.name[:self.frame.start-1]
            self.__ext = self.name[self.frame.end+1:]
        else:
            # no frame in image name, split at extension
            split_name = self.name.split(".")
            self.__base_name = ".".join(split_name[:-1])
            self.__ext = split_name[-1]

    def __eq__(self, other):
        return self.path == other.path

    def __ne__(self, other):
        return self.path != other.path

    def __lt__(self, other):
        return self.frame < other.frame

    def __gt__(self, other):
        return self.frame > other.frame

    def __ge__(self, other):
        return self.frame >= other.frame

    def __le__(self, other):
        return self.frame <= other.frame

    # produce better output
    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return '<pyani.media.image.core.AniImage "{0}">'.format(self.name)

    def __getattr__(self, key):
        return getattr(self.image, key)

    @property
    def path(self):
        """Image absolute path
        """
        return self.__path

    @property
    def name(self):
        """Image full name with ext and frame
        """
        return self.__filename

    @property
    def base_name(self):
        """Image name no frame or ext
        """
        return self.__base_name

    @property
    def dirname(self):
        """"Image directory name
        """
        return self.__dirname

    @property
    def digits(self):
        """Numerical components of image name.
        """
        return self.__digits

    @property
    def parts(self):
        """Non-numerical components of image name
        """
        return self.__parts

    @property
    def exists(self):
        """Returns True if this item exists on disk
        """
        return os.path.isfile(self.__path)

    @property
    def size(self):
        """Returns the width and height as a tuple
        """
        return self.__size

    @property
    def ext(self):
        """Returns the image format
        """
        return self.__ext

    @property
    def frame(self):
        """Returns the image frame object pyani.media.image.core.AniFrame
        """
        return self.__frame
