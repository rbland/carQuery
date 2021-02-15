#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import os
import re
import sys
import json
import errno
import shutil
import hashlib
import urllib2
import tempfile

# ---------------------------------------------------------------------------- #
# -- GLOBALS ----------------------------------------------------------------- #

# The Kelly Blue Book public site.
DOMAIN = 'https://www.kbb.com'
CAR_FOR_SALE = 'cars-for-sale'

IS_LINUX = IS_MAC = IS_WINDOWS = False
if 'darwin' in sys.platform:
    IS_MAC = True
elif 'win' in sys.platform:
    IS_WINDOWS = True
else:
    IS_LINUX = True

DIRECTORY = os.path.dirname(os.path.dirname(__file__))
RESOURCES = os.path.join(DIRECTORY, 'resources')
ICON_DIR = os.path.join(RESOURCES, 'icons')
NO_THUMB = os.path.join(RESOURCES, 'nothumb.jpeg')
WINDOW_ICON = os.path.join(ICON_DIR, '{size}x{size}.png')
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'carquery')

# ---------------------------------------------------------------------------- #
# -- FUNCTIONS --------------------------------------------------------------- #

def get_window_icon():
    """
    Gets the icon used to represent the application. 
    """
    from qtpy import QtGui, QtCore
    icon = QtGui.QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        path = WINDOW_ICON.format(size=size)
        icon.addFile(path, QtCore.QSize(size, size))
    return icon


def print_line(text, color=None, error=False, bold=False):
    """
    Prints a single line of output to the console.
    """
    stream = sys.stderr if error else sys.stdout
    if error and color is None:
        color = TermColors.RED
    if color is not None:
        text = color.colorize(text)
    if bold:
        text = TermColors.BOLD.colorize(text)
    stream.write(text + '\n')


def get_url(args=None, params=None):
    """
    Generates a URL from python arguments. 
    """
    args_str = ''
    if args:
        args_str = '/' + '/'.join(str(a).strip('/') for a in args)
    url = DOMAIN + args_str
    if params:
        url += '?' + params_to_url(params)
    return url


def params_to_url(params):
    """
    Converts GET parameters to a URL query string.
    """
    if isinstance(params, dict):
        params = params.items()
    return '&'.join('{0}={1}'.format(k, v) for k, v in params)


def parse_number(value, default=0):
    """
    Parses an integer number from a string.
    """
    if isinstance(value, basestring):
        value = re.sub('[^0-9]+', '', value)
        if value:
            return int(value)
    return default


def safe_makedirs(directory):
    """
    Creates the specified directory if it is missing.
    """
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def to_price(value):
    """
    Retrieves a string representation of a dollar amount.
    """
    # cast to integer, no need for cents; it doesn't make sense.
    return '${0:d}'.format(int(value))


def to_decimal(value):
    """
    Casts a number to a string with a single decimal place of accuracy.
    """
    return '{0:.1f}'.format(float(value))


def flatten(in_list):
    """
    Flattens two-deep nested iterables.
    """
    return [item for sublist in in_list for item in sublist]


def write_file(path, data, binary=True):
    """
    Writes the specified data to disk.
    """
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, 'wb' if binary else 'w') as out_fd:
        out_fd.write(data)


# ---------------------------------------------------------------------------- #
# -- ENUMERATORS ------------------------------------------------------------- #

class TermColor(object):
    """
    A special enum class that provides a convenience method
    printing a terminal color escape character.
    """
    DEFAULT = '\033[m'
    
    def __init__(self, number, name):
        """
        Initialization.
        """
        self.number = number
        self.code = '\033[' + str(number) + 'm'
        self.name = name

    def colorize(self, text):
        """
        Wraps the input string in the colorized and default escape codes.
        """
        if IS_WINDOWS:
            return str(text)
        kwargs = dict(color=self.code, text=text, escape=self.DEFAULT)
        return '{color}{text}{escape}'.format(**kwargs)


class TermColors(object):
    """
    Enumeration class to define terminal foreground color escape strings
    """
    DEFAULT = TermColor(0, 'default')
    # not actually a color but handled the same
    BOLD = TermColor(1, 'bold')
    BLACK = TermColor(30, 'black')
    RED = TermColor(31, 'red')
    GREEN = TermColor(32, 'green')
    YELLOW = TermColor(33, 'yellow')
    BLUE = TermColor(34, 'blue')
    MAGENTA = TermColor(35, 'magenta')
    CYAN = TermColor(36, 'cyan')
    WHITE = TermColor(37, 'white')


# ---------------------------------------------------------------------------- #
# -- CLASSES ----------------------------------------------------------------- #

class File(object):
    """
    A context manager for interacting with files on disk.
    """
    MODE = 'r'
    
    def __init__(self, path, binary=False):
        """
        Initialization.
        """
        self.path = path
        self.binary = binary
        self.locked = False
        self.descriptor = None
        
    def makedirs(self):
        """
        Creates the parent directory if missing.
        """
        safe_makedirs(os.path.dirname(self.path))
        
    def get_mode(self):
        """
        Gets the file mode used to open the file.
        """
        return self.MODE + 'b' if self.binary else self.MODE
        
    def validate_locked(self, locked=True):
        """
        """
        if self.locked != locked:
            label = 'locked' if self.locked else 'unlocked'
            raise RuntimeError('File "{0}" {1}.'.format(self.path, label))
        
    def __enter__(self):
        """
        Callback when we enter a with block.
        """
        self.validate_locked(False)
        self.locked = True
        self.makedirs()
        self.descriptor = open(self.path, self.get_mode())
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Callback when we leaves a with block.
        """
        self.locked = False
        if self.descriptor is not None:
            self.descriptor.close()
            self.descriptor = None


class InputFile(File):
    """
    A context manager for reading data from disk
    """
    MODE = 'r'

    def read_json(self):
        """
        Reads and returns JSON data from disk.
        """
        data = self.read()
        return json.JSONDecoder().decode(data)
        
    def read(self):
        """
        Reads all data from the file on disk.
        """
        self.validate_locked()
        return self.descriptor.read()


class OutputFile(File):
    """
    A context manager for writing data to disk
    """
    MODE = 'w'

    def write_json(self, serialized):
        """
        Writes the specified data to a JSON representation on disk.
        """
        self.write(json.JSONEncoder().encode(serialized))
        
    def write(self, data):
        """
        Writes raw data to disk.
        """
        self.validate_locked()
        self.descriptor.write(data)


class WebImage(object):
    """
    An image loaded from a web URL.
    """
    BY_URL = dict()

    @classmethod
    def instance(cls, local_dir, url):
        if url not in cls.BY_URL:
            cls.BY_URL[url] = cls(local_dir, url)
        return cls.BY_URL[url]

    def __init__(self, local_dir, url):
        """
        Initialization.
        """
        self.url = url
        self.ext = 'jpg'
        md5 = hashlib.md5()
        md5.update(self.url)
        self.checksum = md5.hexdigest()
        ext = self.url.rpartition('.')[2].lower()
        if re.match('^[a-z0-9]{1,4}$', ext):
            self.ext = ext
        name = self.checksum + '.' + self.ext
        self.path = os.path.join(local_dir, 'images', name)
        self.pixmap = None
        self.load_image()

    def load_image(self):
        """
        Loads the image data for this QPixmap.
        """
        from qtpy import QtGui
        if not os.path.isfile(self.path):
            try:
                data = urllib2.urlopen(self.url).read()
            except urllib2.HTTPError:
                shutil.copy(NO_THUMB, self.path)
            else:
                write_file(self.path, data, binary=True)
        self.pixmap = QtGui.QPixmap(self.path)
