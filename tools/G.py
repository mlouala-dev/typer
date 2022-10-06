# بسم الله الرحمان الرحيم
"""
the main tool function defining core functions used in the whole script
and reference variables
and the logging system
"""
import time as tm
import os
import logging
import traceback
import pyaudio
from sys import argv
from os import listdir
from os.path import dirname, join, splitext
from pathlib import Path
from functools import wraps

from PyQt6.QtGui import QPixmap, QFont, QIcon, QKeySequence, QAction, QShortcut
from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlDatabase


# The application's core settings
__app__ = 'Typer'   # name
__ver__ = 1.6       # version
__ext__ = '786'     # extension
__debug_level__ = logging.ERROR

# the font(s) used by the app
__la_font__ = 'Arial'
__ar_font__ = 'Arial'
def get_font_size(size: float = 1.2):
    return int(int(size * 12 * 10) / 10.0)
__font_size__ = 12
__additional_fonts__ = ['Microsoft Uighur Bold', 'AGA Arabesque', 'ThanaaWaMadh']
__additional_fonts__.insert(0, __la_font__)

# the file extension of the app


def get_font(size: float = 1.2, *args, **kwargs) -> QFont:
    """
    Will convert the size from "em" format to "point size" then forward
    every additional param

    :param size: size in "em" float format
    :param args: every non-named argument
    :param kwargs: every keyword named argument
    :return: the complete QFont object
    """
    font = QFont(__la_font__, *args, **kwargs)
    font.setPointSizeF(get_font_size(size))

    # we force the antialias
    font.setStyleStrategy(QFont.StyleStrategy.PreferQuality)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)

    return font


# variables data used in the UserDatas
State_Default = 0
State_Correction = 1
State_Audio = 2
State_Reference = 3

InsertRole = 0
QuoteRole = 1


class MAX_SCREEN_SIZE:
    width = 1280
    height = 720


# PATH OPERATORS

# the absolute path of the app
__abs_path__ = dirname(argv[0])


def abs_path(file: str = '') -> str:
    """
    Return absolute path of file
    :param file: file's name
    """
    return join(__abs_path__, file)


def user_path(file: str) -> str:
    """
    Return the absolute path from the User folder
    :param file: le nom du fichier
    """
    return join(Path.home(), file)


def appdata_path(file: str = '') -> str:
    """
    returns absolute path to the %appdata%/Local/Typer
    """
    return join(os.getenv('LOCALAPPDATA'), 'Typer', file)


# we create the appdata folder if doesn't exist
if not os.path.isdir(appdata_path()):
    os.mkdir(appdata_path())

    with open(appdata_path('dict.txt'), mode='a') as f:
        f.write('')

    with open(appdata_path('dict_alif_maqsuur.txt'), mode='a') as f:
        f.write('')


def rsc_path(file: str) -> str:
    """
    Return absolute path to the resource
    :param file: ressource's name
    """
    return abs_path(f'rsc/{file}')


def rsc(file: str):
    """
    Return a ressource object based on file's ext, if the extension is not handled returns abs path
    :param file: file path
    :rtype: QSqlDatabase | QPixmap
    """
    # get absolute path of file
    file_path = rsc_path(file)
    file_ext = splitext(file_path)[1][1:]

    if file_ext == 'db':
        return new_connection(file_path)

    # check if files is an image
    elif file_ext in ('png', 'jpg'):
        return QPixmap(file_path)

    elif file_ext in ('ttf', 'otf'):
        return rsc_path(f'fonts/{file}')

    return file_path


def pixmap(name: str, size: int = 32) -> QPixmap:
    """
    Returns a pixmap of the given name searching in the ressource 'icons' folder
    :param name: file's basename
    :param size: additionnal wanted size of ressource, default is 32px (max)
    """
    # getting the current ressource's path
    res = QPixmap(name)

    # and rescale
    res = res.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation)

    return res


def icon(name: str) -> QIcon:
    """
    Returns an icon of the given name searching in the ressource 'icons' folder
    :param name: icon's basename
    """
    # getting the current ressource's path
    return QIcon(f'icons:{name}.png')


def get_steps(length: int, maximum = 100):
    return max(1, length / maximum)


class SQLConnection(object):
    """
    A simple class to handle the with statement working like :
        with SQLConnection('quran.db') as db:
    or
        with SQLConnection(rsc('quran.db')) as db:
    """
    def __init__(self, c: QSqlDatabase | str):
        # we try to retrieve the db correct path if arg is string
        if isinstance(c, str):
            if os.path.isfile(c):
                path = c
            elif os.path.isfile(rsc_path(c)):
                path = rsc_path(c)
            else:
                path = abs_path(c)
            self.connection = new_connection(path)

        # otherwise we guess its a QSqlDatabse object
        else:
            self.connection = c

        self.database = None

    def __enter__(self):
        self.database = QSqlDatabase.database()
        return self.database

    def __exit__(self, *args, **kwargs):
        self.database.close()
        self.connection.close()


def new_connection(db: str = None) -> QSqlDatabase:
    """
    Create a new QSqlDatabase object with the basic params, if specified open the file
    """

    connection = QSqlDatabase.addDatabase("QSQLITE")
    connection.setConnectOptions('QSQLITE_ENABLE_REGEXP')

    # if specified open the file
    if db is not None:
        connection.setDatabaseName(db)

    return connection


# AUDIO DEVICE DETECTION

def get_audio_inputs():
    pa = pyaudio.PyAudio()
    devices = []

    for a in range(pa.get_device_count()):
        devices.append(pa.get_device_info_by_index(a))

    # getting the bestApi available
    max_api = min([d['hostApi'] for d in devices])

    filtered_devices = filter(lambda x: x['hostApi'] == max_api and x['maxInputChannels'] != 0, devices)

    return {d['name']:{
        'id': d['index'],
        'channels': d['maxInputChannels'],
        'sample': d['defaultSampleRate']
    } for d in filtered_devices}


audio_input_devices = get_audio_inputs()
audio_input_devices_names = list(audio_input_devices.keys())


# SHORTCUTS

class Shortcut(QAction):
    def __init__(self, shortcut, hint='', name='', icon_name='', default_state=True):
        self._shortcut = shortcut

        # if shortcut specified, we assign it and update the hint
        if shortcut != '':
            hint += f' ({shortcut})'

        self.hint = hint
        self.name = name
        self.icon_name = icon_name

        self.default_state = default_state

    def register(self, parent=None, action=None):
        super().__init__(parent)

        shortcut_trigger = QShortcut(QKeySequence(self._shortcut), parent)

        self.setShortcut(self._shortcut)
        self.setShortcutContext(Qt.ShortcutContext.WindowShortcut)

        self.setToolTip(self.hint)
        self.setText(self.hint)
        self.setObjectName(self.name)

        self.setIcon(icon(self.icon_name))

        self.setEnabled(self.default_state)

        if action:
            shortcut_trigger.activated.connect(action)
            self.triggered.connect(action)


class Shortcut_Bank(dict):
    def add(self, *args, **kwargs):
        self[kwargs['name']] = Shortcut(*args, **kwargs)


SHORTCUT = Shortcut_Bank()
SHORTCUT.add(shortcut='Ctrl+N', name='new', hint='New project...', icon_name='Page')
SHORTCUT.add(shortcut='Ctrl+O', name='open', hint='Open project...', icon_name='Open-Folder')
SHORTCUT.add(shortcut='Ctrl+S', name='save', hint='Save project...', icon_name='Page-Save', default_state=False)
SHORTCUT.add(shortcut='Ctrl+Shift+S', name='saveas', hint='Save as project...', icon_name='Save-As', default_state=False)
SHORTCUT.add(shortcut='Ctrl+R', name='ref', hint='Load reference...', icon_name='Book-Link')
SHORTCUT.add(shortcut='Ctrl+Shift+D', name='digest', hint="Learn file's words...", icon_name='Agp')
SHORTCUT.add(shortcut='Ctrl+F', name='find', hint='Search...', icon_name='Search-Plus')
SHORTCUT.add(shortcut='Alt+E', name='navigator', hint='Open Navigator...', icon_name='List')
SHORTCUT.add(shortcut='Alt+A', name='listen', hint='Start Listening...', icon_name='Microphone')
SHORTCUT.add(shortcut='Alt+Z', name='note', hint='Insert Note...', icon_name='Note-Add')
SHORTCUT.add(shortcut='Alt+V', name='pdf', hint="Export to PDF...", icon_name="File-Extension-Pdf")
SHORTCUT.add(shortcut='Alt+V', name='html', hint="Export to HTML...", icon_name="File-Extension-Html")
SHORTCUT.add(shortcut='Alt+R', name='viewer', hint="Display viewer...", icon_name="Book-Picture", default_state=False)
SHORTCUT.add(shortcut='F2', name='bookmark', hint="Summary panel...", icon_name="Application-Side-List")
SHORTCUT.add(shortcut='F3', name='settings', hint="Settings...", icon_name="Setting-Tools")

SHORTCUT.add(shortcut='Ctrl+Alt+C', name='quran_search', hint='Search in Quran...', icon_name='Book')
SHORTCUT.add(shortcut='Alt+C', name='quran_insert', hint='Insert from / Jump to Quran...', icon_name='Book-Go')
SHORTCUT.add(shortcut='Ctrl+Alt+S', name='book_search', hint='Search in Source...', icon_name='Book-Spelling')
SHORTCUT.add(shortcut='Alt+S', name='book_jumper', hint='Insert from / Jump to Source', icon_name='Book-Spelling')
SHORTCUT.add(shortcut='Alt+H', name='hadith_search', hint='Search in hadith database...', icon_name='Book-Keeping')

SHORTCUT.add(shortcut='Ctrl+Shift+B', name='bold', hint='bold', icon_name="Text-Bold")
SHORTCUT.add(shortcut='Ctrl+Shift+I', name='italic', hint='italic', icon_name="Text-Italic")
SHORTCUT.add(shortcut='Ctrl+Shift+U', name='underline', hint='underline', icon_name="Text-Underline")
SHORTCUT.add(shortcut='Ctrl+Shift+1', name='h1', hint='h1', icon_name="Text-Heading-1")
SHORTCUT.add(shortcut='Ctrl+Shift+2', name='h2', hint='h2', icon_name="Text-Heading-2")
SHORTCUT.add(shortcut='Ctrl+Shift+3', name='h3', hint='h3', icon_name="Text-Heading-3")
SHORTCUT.add(shortcut='Ctrl+Shift+4', name='h4', hint='h4', icon_name="Text-Heading-4")
SHORTCUT.add(shortcut='Ctrl+Shift+L', name='aleft', hint='aleft', icon_name="Text-Align-Left")
SHORTCUT.add(shortcut='', name='acenter', hint='acenter', icon_name="Text-Align-Center")
SHORTCUT.add(shortcut='Ctrl+Shift+R', name='aright', hint='aright', icon_name="Text-Align-Right")
SHORTCUT.add(shortcut='Ctrl+Shift+J', name='ajustify', hint='ajustify', icon_name="Text-Align-Justify")


# LOGGING ROUTINES

logger = logging.getLogger(__name__)
logger.setLevel(__debug_level__)

# Create formatters and add it to handlers
log_file = appdata_path('app.log')
with open(log_file, 'wb') as lf:
    lf.flush()

log_handler = logging.FileHandler(log_file)
log_handler.setFormatter(logging.Formatter("%(asctime)s - [%(levelname)s] : %(message)s"))

# Add handlers to the logger
logger.addHandler(log_handler)

def function_info(func, *args, **kwargs):
    """
    Returns a resume of the given function for logs
    :param func: a function
    :return: a resume of the function
    """
    # representing the args
    formatted_args = ", ".join(map(repr, args))

    # and the keyword args
    for key, value in kwargs.items():
        formatted_args += f" [{key}: '{value}']"

    return f'{func.__name__} in [{func.__module__}] :: {formatted_args}'

def log(func):
    """
    a wrapper in log level
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(function_info(func, *args, **kwargs))
        result = func(*args, **kwargs)
        return result

    return wrapper

def debug(func):
    """
    a wrapper in debug level
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(function_info(func, *args, **kwargs))
        result = func(*args, **kwargs)
        return result

    return wrapper

def warning(*msgs):
    logger.warning(" ".join(map(repr, msgs)))

def error(*msgs):
    logger.error(" ".join(map(repr, msgs)))

def exception(e: Exception):
    """
    a function to display an exception in debug level, may be implemented in every try / except
    """
    logger.warning(f'Exception ({e.__class__.__name__}) with context : "{e}"')

def error_exception(e, tb):
    """
    Displays an advanced traceback of the exception
    :param e: exception
    :param tb: traceback for the exception
    """
    logger.error(''.join(traceback.format_tb(tb)) + repr(e))

def time(func):
    """
    a wrapper in log level
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        s = tm.time()
        result = func(*args, **kwargs)
        e = tm.time() - s
        print(f'{e}ms for {function_info(func)}')
        return result

    return wrapper
