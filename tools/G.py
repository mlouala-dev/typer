# بسم الله الرحمان الرحيم
"""
the main tool function defining core functions used in the whole script
and reference variables
and the logging system
"""
import os
import logging
import traceback
from sys import argv
from os import listdir
from os.path import dirname, join, splitext
from pathlib import Path
from functools import wraps

from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase


# The application's core settings
__app__ = 'Typer'   # name
__ver__ = 1.2       # version
__ext__ = '786'     # extension
__debug_level__ = logging.DEBUG

# the font(s) used by the app
__font__ = 'Microsoft Uighur'
__additional_fonts__ = ['Microsoft Uighur Bold', 'AGA Arabesque']
__additional_fonts__.insert(0, __font__)

# the file extension of the app


def get_font(size: float = 1, *args, **kwargs) -> QFont:
    """
    Will convert the size from "em" format to "point size" then forward
    every additional param

    :param size: size in "em" float format
    :param args: every non-named argument
    :param kwargs: every keyword named argument
    :return: the complete QFont object
    """
    font = QFont(__font__, *args, **kwargs)
    font.setPointSizeF(int(size * 12 * 10) / 10.0)

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


# some escape characters
new_phrase_keys = {
    46: '.', 33: '!', 63: '?'
}
new_word_keys = {
    40: '(', 41: ')', 44: ',', 58: ':', 59: ';', 45: '-', 32: ' ', 34: '"'
}
new_word_keys.update(new_phrase_keys)

quotes_keys = {
    40: '(', 39: "'", 34: '"'
}

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
    res = QPixmap(rsc_path(f'icons/{name}.png'))

    # and rescale
    res = res.scaledToHeight(size, Qt.SmoothTransformation)

    return res


def icon(name: str) -> QIcon:
    """
    Returns an icon of the given name searching in the ressource 'icons' folder
    :param name: icon's basename
    """
    # getting the current ressource's path
    return QIcon(rsc_path(f'icons/{name}.png'))


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


logger = logging.getLogger(__name__)
logger.setLevel(__debug_level__)

# Create formatters and add it to handlers
log_file = abs_path('app.log')
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