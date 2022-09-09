# بسم الله الرحمان الرحيم
"""
The Settings manager
"""
import sqlite3
import html
import tempfile
import os
import re

from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThreadPool, QRunnable

from tools import G, T
from tools.translitteration import translitterate, re_ignore_hamza, clean_harakat


class _Pool(QThreadPool):
    started = pyqtSignal()
    done = pyqtSignal()
    step = pyqtSignal(str)

    def __init__(self):
        super().__init__()


POOL = _Pool()


class _Settings(QObject):
    db: sqlite3.Connection
    cursor: sqlite3.Cursor
    defaults = {}

    def __init__(self):
        super().__init__()

        self.db = None
        self.cursor = None
        self.filename = ''

    def create_db_link(self):
        if self.db:
            self.db.close()

        self.db = sqlite3.connect(self.filename)
        self.cursor = self.db.cursor()

    def buildCoreSettings(self):
        creation_query = '''
        DROP TABLE IF EXISTS "settings";
        CREATE TABLE "settings" (
            "field"	TEXT,
            "value"	BLOB
        );
        '''

        try:
            self.cursor.executescript(creation_query)

        except sqlite3.OperationalError:
            return False

        for field, default_value in self.defaults.items():
            self.cursor.execute('INSERT INTO settings ("field", "value") VALUES (?, ?)', (field, default_value))

        self.db.commit()
        return self.loadCoreSettings()

    def loadCoreSettings(self) -> dict:
        try:
            settings = {key: stg for key, stg in self.cursor.execute('SELECT * FROM settings').fetchall()}

        except sqlite3.OperationalError:
            G.error('Inconsistent config file, rebuild')
            settings = self.buildCoreSettings()

        for key, setting in self.defaults.items():
            if key not in settings:
                G.error(f'Core setting "{key}" not found, updating the file')

                self.cursor.execute('INSERT INTO settings ("field", "value") VALUES (?, ?)', (key, setting))
                self.db.commit()

                settings[key] = setting

        return settings

    def saveSetting(self, setting):
        self.cursor.execute('UPDATE settings SET value=? WHERE field=?', (self.__dict__[setting], setting))
        self.db.commit()


class GlobalSettings(_Settings):
    class Style:
        name = 'Empty'
        palette = QPalette()

        def apply(self):
            QApplication.setStyle(QStyleFactory.create("Fusion"))
            QApplication.setPalette(self.palette)

    class Dark(Style):
        name = 'Dark Theme'
        palette = QPalette()

        darkColor = QColor(45, 45, 45)
        disabledColor = QColor(127, 127, 127)
        whiteText = QColor(169, 183, 198)
        highlight =  QColor(42, 130, 218)
        palette.setColor(QPalette.ColorRole.Window, darkColor)
        palette.setColor(QPalette.ColorRole.WindowText, whiteText)
        palette.setColor(QPalette.ColorRole.Base, QColor(28, 28, 28))

        palette.setColor(QPalette.ColorRole.AlternateBase, darkColor)
        palette.setColor(QPalette.ColorRole.ToolTipBase, whiteText)
        palette.setColor(QPalette.ColorRole.ToolTipText, whiteText)
        palette.setColor(QPalette.ColorRole.Text, whiteText)

        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabledColor)
        palette.setColor(QPalette.ColorRole.Button, darkColor)
        palette.setColor(QPalette.ColorRole.ButtonText, whiteText)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabledColor)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.white)
        palette.setColor(QPalette.ColorRole.Link, highlight)

        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, darkColor)
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabledColor)

    class Light(Style):
        name = 'Light Theme'
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Button, QColor(215, 221, 232))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(42, 130, 218))
        pass

    themes = {
        'dark': Dark(),
        'light': Light()
    }

    defaults = {
        'theme': 'light',
        'toolbar': True,
        'text_toolbar': False,
        'last_file': '',
        'default_path': G.abs_path(),
        'update_default_path': True,
        'auto_load': False,
        'audio_input_device': G.audio_input_devices_names[0],
        'audio_record_path': G.user_path('Music/.typer_records'),
        'audio_sample_rate': 16000,
        'minimum_word_length': 2
    }

    step = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self.filename = G.appdata_path('config.db')
        self.create_db_link()

        self.theme = self.defaults['theme']
        self.toolbar = self.defaults['toolbar']
        self.text_toolbar = self.defaults['text_toolbar']
        self.last_file = self.defaults['last_file']
        self.default_path = self.defaults['default_path']
        self.auto_load = self.defaults['auto_load']
        self.update_default_path = self.defaults['update_default_path']
        self.audio_input_device = self.defaults['audio_input_device']
        self.audio_record_path = self.defaults['audio_record_path']
        self.audio_sample_rate = self.defaults['audio_sample_rate']
        self.audio_record_epoch = 0
        self.minimum_word_length = self.defaults['minimum_word_length']

    def setTheme(self, theme):
        self.theme = theme
        self.themes[self.theme].apply()

        self.step.emit(100, f'Theme "{self.theme}" loaded')

    def setLastFile(self, filename: str):
        self.last_file = filename
        self.saveSetting('last_file')

        self.setDefaultPath(filename)

    def setDefaultPath(self, filename: str):
        if self.update_default_path:
            self.default_path = os.path.dirname(filename)
            self.saveSetting('default_path')

    def setAudioRecordPath(self, path: str):
        self.audio_record_path = path

        if os.path.isdir(self.audio_record_path):
            self.audio_record_epoch = int(os.stat(self.audio_record_path).st_ctime)

    def loadSettings(self):
        settings = self.loadCoreSettings()
        # closing file if other instance needs it
        self.db.close()

        self.setTheme(settings['theme'])

        self.default_path = settings['default_path']

        self.auto_load = bool(settings['auto_load'])
        self.last_file = settings['last_file']
        if self.auto_load and not os.path.isfile(self.last_file):
            self.last_file = ''

        self.update_default_path = bool(settings['update_default_path'])
        self.toolbar = bool(settings['toolbar'])
        self.text_toolbar = bool(settings['text_toolbar'])

        self.setAudioRecordPath(settings['audio_record_path'])
        self.audio_input_device = settings['audio_input_device']
        self.audio_sample_rate = settings['audio_sample_rate']

        self.minimum_word_length = int(settings['minimum_word_length'])

    def saveSetting(self, setting):
        """
        Since the file is opened by multiple instance, we open and close it when needed
        :param setting:
        :return:
        """
        self.create_db_link()

        super().saveSetting(setting)

        self.db.close()


class LocalSettings(_Settings):
    defaults = {
        'pdf_name': '',
        'pdf_data': b'',
        'position': 0,
        'page': 0,
        'geo_x': 50,
        'geo_y': 50,
        'geo_w': 650,
        'geo_h': 350,
        'maximized': False,
        'connected': False,
        'summary_visibility': False,
        'viewer_visibility': False,
        'viewer_external': False,
        'viewer_invert': False,
        'viewer_x': 0,
        'viewer_y': 0,
        'viewer_w': 100,
        'viewer_h': 300,
    }

    step = pyqtSignal(int, str)
    pageChanged = pyqtSignal(int)

    class Book:
        def __init__(self, db: sqlite3.Connection = None, cursor: sqlite3.Cursor = None):
            self._mod = set()
            self._book = {}
            self._db = db
            self._cursor = cursor

            if self._cursor:
                for page, content in self._cursor.execute('SELECT * FROM book').fetchall():
                    self._book[page] = html.unescape(content)

        def getBook(self):
            return self._book

        def savePage(self, page: int):
            try:
                self._cursor.execute('INSERT INTO book ("page", "text") VALUES (?, ?)', (page, html.escape(self[page])))
            except sqlite3.IntegrityError:
                self._cursor.execute(f'UPDATE book SET text=? WHERE page={page}', (html.escape(self[page]),))

            self._db.commit()
            self._mod.remove(page)

        @G.log
        def saveAllPage(self):
            for page in self._mod.intersection(set(self._book.keys())):
                self.savePage(page)

            self._mod.clear()

        def setModified(self, page: int):
            self._mod.add(page)

        def unsetModified(self, page: int):
            try:
                self._mod.remove(page)
            except KeyError:
                pass

        def isModified(self):
            return bool(len(self._mod))

        def modified(self):
            return self._mod

        def update(self, new_book: dict):
            for key, value in new_book.items():
                self[key] = value
                self.setModified(key)

        def __getitem__(self, item):
            return self._book[item]

        def __setitem__(self, key, value):
            try:
                assert self._book[key] != value
            except AssertionError:
                return
            except KeyError:
                pass
            finally:
                self._mod.add(key)
                self._book[key] = value

        def __contains__(self, item):
            return item in self._book

        def __iter__(self):
            for i in self._book:
                yield i

        def __len__(self):
            return len(self._book)

    class BookMap:

        class Kitab:
            def __init__(self, name='', kid=0, page=None):
                """
                :type page: Jumper.Page
                """
                self.id = kid
                self._name = name
                self.page = page
                self.abwab = list()
                self.ahadith = list()

            @property
            def name(self):
                return f'كتاب {self._name}'

            def getBab(self, bid: int):
                """
                :rtype: Jumper.Bab
                """
                for bab in self.abwab:
                    if bab.id == bid:
                        return bab
                else:
                    raise KeyError

            def getHadith(self, hid: int):
                """
                :rtype: Jumper.Hadith
                """
                for hadith in self.ahadith:
                    if hadith.sub_id == hid:
                        return hadith
                else:
                    raise KeyError

        class Bab:
            def __init__(self, name='', bid=0, kid=0, page=None):
                """
                :type page: Jumper.Page
                """
                self.id = bid
                self.kid = kid
                self._name = name
                self.page = page
                self.ahadith = list()

            @property
            def name(self):
                return f'باب {self._name}'

            def getHadith(self, hid: int):
                """
                :rtype: Jumper.Hadith
                """
                for hadith in self.ahadith:
                    if hadith.sub_id == hid:
                        return hadith
                else:
                    raise KeyError

        class Hadith:
            def __init__(self, hid=0, sub_id=0, bid=0, kid=0, content='', grade=''):
                self.id = hid
                self.sub_id = sub_id
                self.bid = bid
                self.kid = kid
                self.content = content
                self.grade = grade

            def toHtml(self):
                h = re.sub(r"« (.*?) »", r'<b>"\1"</b>', self.content)
                h = re.sub(r"\{ (.*) \}", r'''<span style="font-weight:600; color:#169b4c;">﴾ \1 ﴿</span>''', h)
                h = re.sub(r"\{\( (.*) \)\}", r'''<span style="font-weight:600; color:#169b4c;">﴾ \1 ﴿</span>''', h)
                n = f'<span style="font-weight:600; color:#9b6a28;">{self.id}</span>'
                n += f' <span style="font-weight:600; color:#bb9a48;"><i>[{self.sub_id}]</i></span>'
                return f'''{n} {h} <i>({self.grade})</i>'''

        class Page:
            def __init__(self, page=0, kid=0, bid=0, previous_hid=1, hid=1):
                self.page = page
                self.kid = kid
                self.bid = bid
                self.hids = frozenset(range(previous_hid, hid))

            def __int__(self):
                return self.page

            def __contains__(self, item):
                return item in self.hids

            def __repr__(self):
                return str(self.page)

        kutub: {Kitab}
        abwab: [Bab]
        datas: [Hadith]
        pages: [Page]

        def __init__(self):
            self.active = False
            self.kutub = {}
            self.abwab = list()
            self.datas = list()
            self.pages = [LocalSettings.BookMap.Page()]

        def getKitab(self, kid: int) -> Kitab:
            return self.kutub[kid]

        def getBab(self, bid: int, kid: int) -> Bab:
            return self.kutub[kid].getBab(bid)

        def getHadith(self, hid: int) -> Hadith:
            for hadith in self.datas:
                if hadith.id == hid:
                    return hadith
            else:
                raise KeyError

        def getPage(self, page: int) -> Page:
            for p in self.pages:
                if int(p) == page:
                    return p

        def getHadithPage(self, hid: int) -> Page:
            """
            returns the page for the given id
            :param hid: the id of the searched object
            """
            for page in self.pages:
                if hid in page:
                    return page

        def getHadithByPage(self, page: int) -> [Hadith]:
            return [h for h in self.datas if h.id in self.pages[page].hids]

        def findKitab(self, needle: str) -> Kitab:
            for index, kitab in self.kutub.items():
                if needle in re_ignore_hamza.sub('ا', kitab.name):
                    return kitab

        def findBab(self, needle: str, scope: int = None) -> Bab:
            if scope is not None:
                scoped = self.kutub[scope].abwab
            else:
                scoped = self.abwab

            for bab in scoped:
                if needle in re_ignore_hamza.sub('ا', bab.name):
                    return bab

        def findScopedBab(self, needle: int | str, scope: int = None) -> Bab | Hadith:
            try:
                idx = int(needle)
            except ValueError:
                needle = translitterate(needle, True)

                return self.findBab(needle, scope)
            else:

                return self.getBab(idx, scope)

        def _search(self, cmd: str, scope: int = None) -> Kitab | Bab | Hadith:
            try:
                idx = int(cmd)
                assert idx in self.kutub
                return self.kutub[idx]

            # we didn't find this ID in the kutubs' index
            except AssertionError:
                return self.getHadith(idx)

            # this means this is invalid literal for int()
            # so we try to transliterate
            except ValueError:
                needle = translitterate(cmd, True)
                kitab = self.findKitab(needle)
                if kitab:
                    return kitab

                else:
                    bab = self.findScopedBab(needle, scope)
                    if bab:
                        return bab

        def _query(self, cmd=''):
            if not len(cmd):
                raise KeyError

            if cmd.endswith(':'):
                cmd += '1'

            exploded_command = cmd.split(':')

            if len(exploded_command) == 3:
                k, b, h = exploded_command
                kitab = self._search(k)

                if len(b):
                    bab = self.findScopedBab(b, kitab.id)
                    return bab.getHadith(int(h))
                else:
                    return kitab.getHadith(int(h))

            # looking for {kitab}:{bab}
            elif len(exploded_command) == 2:
                k, b = exploded_command
                first = self._search(k)

                if isinstance(first, LocalSettings.BookMap.Kitab):
                    if not len(b):
                        return first
                    else:
                        return self.findScopedBab(b, first.id)
                elif isinstance(first, LocalSettings.BookMap.Bab):
                    return first.getHadith(int(b))

            elif len(exploded_command) == 1:
                return self._search(exploded_command[0])

        def getTextResult(self, cmd=''):
            try:
                result = self._query(cmd)
            except KeyError:
                return ''

            if isinstance(result, LocalSettings.BookMap.Kitab):
                return result.name
            elif isinstance(result, LocalSettings.BookMap.Bab):
                return result.name
            elif isinstance(result, LocalSettings.BookMap.Hadith):
                return result.content

        def getPageResult(self, cmd=''):
            try:
                result = self._query(cmd)
            except KeyError:
                return 1

            if isinstance(result, LocalSettings.BookMap.Kitab):
                return result.page
            elif isinstance(result, LocalSettings.BookMap.Bab):
                return result.page
            elif isinstance(result, LocalSettings.BookMap.Hadith):
                return self.getHadithPage(result.id)

        def getObjectResult(self, cmd=''):
            return self._query(cmd)

    class Dict:
        class Word:
            def __init__(self, word: str, count: int = 1, previous=''):
                self.word = word
                self.root = word[:GLOBAL.minimum_word_length]
                self.count = count
                self.previous = previous

            def __repr__(self):
                return f'[{self.previous}] {self.word}({self.count})'

            def __hash__(self):
                return hash(f'{self.previous}{self.word}')

            def __lt__(self, other):
                return self.count < other.count

            def __gt__(self, other):
                return self.count > other.count

            def disp(self):
                """
                it returns a named dict used by the SQL cursor command
                """
                return {
                    'word': self.word,
                    'count': self.count,
                    'before': self.previous
                }

        class Worker(QRunnable):
            def __init__(self, words, callback_fn):
                super().__init__()

                self.callback_fn = callback_fn
                self.words_to_process = words

                self.words = []
                self.hashes = []
                self.word_roots = {}
                self.word_wide_roots = {}

            def run(self):
                for word in self.words_to_process:
                    try:
                        assert word.previous in self.word_roots[word.root]
                        self.word_roots[word.root][word.previous].append(word)
                        self.word_wide_roots[word.root].append(word)

                    # root not find
                    except KeyError:
                        self.word_roots[word.root] = {}
                        self.word_roots[word.root][word.previous] = [word]
                        self.word_wide_roots[word.root] = [word]

                    # word previous is not an array
                    except AssertionError:
                        self.word_roots[word.root][word.previous] = [word]
                        self.word_wide_roots[word.root].append(word)

                    finally:
                        self.words.append(word)
                        self.hashes.append(hash(word))

                self.callback_fn(
                    self.word_roots,
                    self.word_wide_roots,
                    self.words,
                    self.hashes
                )

        def __init__(self, db: sqlite3.Connection = None, cursor: sqlite3.Cursor = None):
            self._db = db
            self._cursor = cursor

            self.words_to_process = []

            self.words = []
            self.hashes = []
            self.word_roots = {}
            self.word_wide_roots = {}

            self.news = set()
            self.updates = set()

            if self._cursor:
                self.words_to_process = [self.Word(w, c, p) for w, c, p in self._cursor.execute('SELECT * FROM dict').fetchall()]

                worker = self.Worker(self.words_to_process, self.update)
                POOL.start(worker)

        def __getitem__(self, item: Word) -> Word:
            i = self.hashes.index(hash(item))
            return self.words[i]

        def __contains__(self, item: Word):
            return hash(item) in self.hashes

        def __iter__(self) -> [Word]:
            for word in self.words:
                yield word

        def add(self, word: Word):
            try:
                self[word].count += 1
                self.updates.add(self[word])

            # word not find
            except ValueError:
                try:
                    assert word.previous in self.word_roots[word.root]
                    self.word_roots[word.root][word.previous].append(word)
                    self.word_wide_roots[word.root].append(word)

                # root not find
                except KeyError:
                    self.word_roots[word.root] = {}
                    self.word_roots[word.root][word.previous] = [word]
                    self.word_wide_roots[word.root] = [word]

                # word previous is not an array
                except AssertionError:
                    self.word_roots[word.root][word.previous] = [word]
                    self.word_wide_roots[word.root].append(word)

                finally:
                    self.words.append(word)
                    self.news.add(word)
                    self.hashes.append(hash(word))

            finally:
                self.word_roots[word.root][word.previous].sort(reverse=True)
                self.word_wide_roots[word.root].sort(reverse=True)

        def merge(self, ref):
            """
            :type ref: LocalSettings.Dict
            """
            for word in ref:
                if word in self:
                    self[word].count += word.count
                    self.updates.add(self[word])

                else:
                    self.add(word)

        def update(self, word_roots, word_wide_roots, words, hashes):
            self.word_roots.update(word_roots)
            self.word_wide_roots.update(word_wide_roots)
            self.words.extend(words)
            self.hashes.extend(hashes)

        def digest(self, text: str):
            for phrase in T.TEXT.split(text):
                for i, word_text in enumerate(phrase[1:]):
                    # in this configuration, phrase[i] will point the previous word
                    try:
                        assert len(word_text) >= (GLOBAL.minimum_word_length + 1) and len(phrase[i]) >= 2

                    except (AssertionError, IndexError):
                        continue

                    else:
                        word = self.Word(word_text, previous=phrase[i])
                        self.add(word)

        def find(self, word: Word, wide=False):
            """
            Find in current dictionnary's words
            :param word: the Word object we're trying to find candidates for
            :param wide: if specified, will not consider the previous object
            :return: the best candidate
            """
            match = None

            try:
                assert len(word.root) == GLOBAL.minimum_word_length
                bank = self.word_roots[word.root][word.previous] if not wide else self.word_wide_roots[word.root]

                for key in bank:
                    if key.word.startswith(word.word):
                        match = key.word
                        break

            except AssertionError:
                pass
            finally:
                return match

        def save(self):
            if self._cursor:
                self._cursor.executemany('INSERT INTO dict (word, count, before) VALUES (:word, :count, :before)',
                                         [w.disp() for w in self.news])
                self._cursor.executemany('UPDATE dict SET count=:count WHERE word=:word AND before=:before',
                                         [w.disp() for w in self.updates])

                self.news.clear()
                self.updates.clear()

                self._db.commit()

    class Topics:
        class Topic:
            def __init__(self, name: str = '', domain: str = ''):
                self.name = name
                self.domain = domain

            def __lt__(self, other):
                return self.name < other

            def __gt__(self, other):
                return self.name > other

            def __str__(self):
                return self.name

            def __hash__(self):
                return hash(f'{self.domain}@{self.name}')

        def __init__(self):
            self.pages = {}
            self.domains = {
                'prophet': set(),
                'person': set(),
                'place': set(),
                'theme': set(),
                'fiqh': set(),
                'nahw': set(),
                'lugha': set()
            }
            self.topics = {}

        def addTopic(self, name: str = '', domain: str = '', page: int = 0):
            try:
                topic = self.topics[name]
            except KeyError:
                topic = self.Topic(name, domain)

            self.domains[domain].add(topic)

            try:
                self.pages[page].add(topic)
            except KeyError:
                self.pages[page] = {topic}

        def removeTopic(self, name: str = ''):
            for page in self.pages:
                self.removeTopicFromPage(name, page)

            topic = self.getTopic(name)

            for domain in self.domains.values():
                domain.remove(topic)

            self.topics.pop(name)

        def getTopic(self, name: str = ''):
            return self.topics[name]

        def removeTopicFromPage(self, name: str = '', page: int = 0):
            topic = self.topics[name]
            self.pages[page].remove(topic)

    BOOK: Book

    def __init__(self):
        self.BOOK = LocalSettings.Book()
        self.DICT = LocalSettings.Dict()

        self.TOPICS = LocalSettings.Topics()
        self.BOOKMAP = LocalSettings.BookMap()
        self.PDF = None

        self._page = self.defaults['page']
        self.pdf_name = self.defaults['pdf_name']
        self.pdf_data = self.defaults['pdf_data']
        self.position = self.defaults['position']
        self.connected = self.defaults['connected']
        self.geometry = (
            self.defaults['geo_x'],
            self.defaults['geo_y'],
            self.defaults['geo_w'],
            self.defaults['geo_h']
        )
        self.maximized = self.defaults['maximized']

        self.summary = self.defaults['summary_visibility']
        self.viewer = self.defaults['viewer_visibility']
        self.viewer_external = self.defaults['viewer_external']
        self.viewer_invert = self.defaults['viewer_invert']
        self.viewer_geometry = (
            self.defaults['viewer_x'],
            self.defaults['viewer_y'],
            self.defaults['viewer_w'],
            self.defaults['viewer_h']
        )

        super(LocalSettings, self).__init__()

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, value):
        """
        Light function to only update current page in project settings
        :param value: page settings to update
        """
        self._page = value
        self.pageChanged.emit(value)

        if self.cursor:
            self.cursor.execute('UPDATE settings SET value=? WHERE field=?', (value, 'page'))
            self.db.commit()

    # global settings

    def createSettings(self, filename: str = ''):
        self.filename = filename
        self.create_db_link()

        creation_query = '''
        PRAGMA auto_vacuum = '1';
        CREATE TABLE "book" (
            "page"	INTEGER UNIQUE,
            "text"	BLOB,
            PRIMARY KEY("page" AUTOINCREMENT)
        );
        CREATE TABLE "dict" (
            "word"	TEXT,
            "count"	INTEGER,
            "before"	TEXT
        );
        CREATE TABLE "topics" (
            "name"	TEXT,
            "page"	INTEGER,
            "domain"	TEXT    DEFAULT 'theme'
        );
        '''

        try:
            self.cursor.executescript(creation_query)

        except sqlite3.OperationalError:
            return False

        else:
            self.db.commit()

        self.buildCoreSettings()

        self.BOOK = LocalSettings.Book(self.db, self.cursor)

    def loadSettings(self, filename: str = ''):
        self.step.emit(0, f'Loading "{self.filename}"')

        self.filename = filename
        self.create_db_link()

        GLOBAL.setLastFile(filename)

        self.step.emit(10, f'Loading book')
        self.BOOK = LocalSettings.Book(self.db, self.cursor)

        self.step.emit(25, f'Loading words dictionnary')
        self.DICT = LocalSettings.Dict(self.db, self.cursor)

        self.step.emit(50, f'Loading topics')
        for name, page, domain in self.cursor.execute('SELECT * FROM topics').fetchall():
            self.TOPICS.addTopic(name, domain, int(page))

        self.step.emit(65, f'Loading core settings')
        settings = self.loadCoreSettings()

        self.position = settings['position']
        self._page = settings['page']
        self.pdf_name = settings['pdf_name']
        self.connected = bool(settings['connected'])

        if len(settings['pdf_data']):
            self.step.emit(80, f'Unpacking PDF...')
            self.PDF = self.createPDF(settings['pdf_data'])

            try:
                previous_hid = 1

                self.step.emit(90, f'Reading pdf book\'s map')
                # if we have some PDF data we look after a book's map
                for page, kitab, bab, hid, subid in self.cursor.execute('SELECT * FROM bm_pages').fetchall():
                    page = LocalSettings.BookMap.Page(
                        page=page,
                        kid=kitab,
                        bid=bab,
                        previous_hid=previous_hid,
                        hid=hid,
                    )
                    previous_hid = hid
                    self.BOOKMAP.pages.append(page)

                for kid, name, page in self.cursor.execute('SELECT * FROM bm_kutub').fetchall():
                    kitab = self.BOOKMAP.kutub[kid] = LocalSettings.BookMap.Kitab(
                        name=clean_harakat(name),
                        kid=kid,
                        page=self.BOOKMAP.getPage(page)
                    )
                    for bid, bname, bpage in self.cursor.execute(f'SELECT id, name, page FROM bm_abwab WHERE kitab={kid}').fetchall():
                        if bname:
                            bab = LocalSettings.BookMap.Bab(
                                name=clean_harakat(bname),
                                bid=bid,
                                kid=kid,
                                page=self.BOOKMAP.getPage(bpage)
                            )

                            self.BOOKMAP.abwab.append(bab)
                            kitab.abwab.append(bab)

                for hid, subid, kitab, bab, hadith, grade in self.cursor.execute('SELECT * FROM bm_ahadith').fetchall():
                    hadith = LocalSettings.BookMap.Hadith(
                        hid=hid,
                        sub_id=subid,
                        bid=bab,
                        kid=kitab,
                        content=html.unescape(hadith),
                        grade=grade
                    )

                    self.BOOKMAP.kutub[hadith.kid].ahadith.append(hadith)

                    try:
                        self.BOOKMAP.kutub[hadith.kid].getBab(hadith.bid).ahadith.append(hadith)

                    except KeyError:
                        pass

                    self.BOOKMAP.datas.append(hadith)

                # if everything went fine we can set the BOOKMAP as active
                self.BOOKMAP.active = True

            # this means we have no bookmap_datas
            except sqlite3.OperationalError:
                pass

        self.geometry = (
            settings['geo_x'],
            settings['geo_y'],
            settings['geo_w'],
            settings['geo_h']
        )

        self.maximized = settings['maximized']

        self.summary = bool(settings['summary_visibility'])

        self.viewer = bool(settings['viewer_visibility'])
        self.viewer_external = bool(settings['viewer_external'])
        self.viewer_invert = bool(settings['viewer_invert'])
        self.viewer_geometry = (
            settings['viewer_x'],
            settings['viewer_y'],
            settings['viewer_w'],
            settings['viewer_h']
        )

        self.step.emit(100, f'"{self.filename}" loaded')

    @G.log
    def saveAllSettings(self):
        if not self.db:
            return

        self.step.emit(5, f'Saving file')
        self.cursor.executemany('UPDATE settings SET value=? WHERE field=?',
                                [
                                    (self.position, 'position'),
                                    (self.page, 'page'),
                                    (int(self.connected), 'connected')
                                ])

        self.db.commit()

        self.step.emit(30, 'Saving book')
        self.BOOK.saveAllPage()

        self.step.emit(60, 'Saving words dictionnay')
        self.DICT.save()

        self.step.emit(90, 'Saving visual settings')
        self.saveVisualSettings()

        self.step.emit(100, 'Project saved')

    @G.log
    def saveVisualSettings(self):
        if not self.cursor:
            return
        self.cursor.executemany('UPDATE settings SET value=? WHERE field=?',
                                [
                                    (self.position, 'position'),
                                    (int(self.summary), 'summary_visibility'),
                                    (int(self.viewer), 'viewer_visibility'),
                                    (self.geometry[0], 'geo_x'),
                                    (self.geometry[1], 'geo_y'),
                                    (self.geometry[2], 'geo_w'),
                                    (self.geometry[3], 'geo_h'),
                                    (int(self.maximized), 'maximized'),
                                    (int(self.viewer_external), 'viewer_external'),
                                    (self.viewer_geometry[0], 'viewer_x'),
                                    (self.viewer_geometry[1], 'viewer_y'),
                                    (self.viewer_geometry[2], 'viewer_w'),
                                    (self.viewer_geometry[3], 'viewer_h'),
                                ])

        self.db.commit()

    def backup(self):
        """
        make a vacuum of the current file into backup.db, in case of crash of fail at save
        TODO: autosave of the current page ?
        """

        cwd = G.appdata_path('backup.db')
        # we first try to remove the old backup file
        try:
            os.remove(cwd)

        except FileNotFoundError as e:
            G.exception(e)

        # now we vacuum our file in it
        self.cursor.execute(f"VACUUM main INTO ?;", (cwd,))
        self.db.commit()

    def setModifiedFlag(self):
        if len(self.BOOK):
            self.BOOK.setModified(self.page if self.connected else 0)

    def unsetModifiedFlag(self):
        if len(self.BOOK):
            self.BOOK.unsetModified(self.page if self.connected else 0)

    # Topics
    def saveTopics(self, topic_add: list, topic_delete: list):
        """
        Update the topics for the current page
        :param topic_add: list of topics to be added
        :param topic_delete: list of topics to be deleted
        """
        # loop to remove all topics from list
        print(topic_delete)
        self.cursor.executemany(f"DELETE FROM topics WHERE name=? AND page=?",
                                [(topic, self.page) for topic in topic_delete])

        print(topic_add)
        # loop to add all topics from list
        for topic in topic_add:
            self.cursor.execute('''INSERT INTO topics (name, domain, page) VALUES (?, ?, ?)''',
                                (topic.name, topic.domain, self.page))

        self.db.commit()

    # PDF
    @staticmethod
    def createPDF(data: bytes):
        fp = tempfile.mktemp()

        with open(fp, 'wb') as f:
            f.write(data)

        return fp

    def digestPDF(self, pdf_file: str):
        with open(pdf_file, 'rb') as f:
            self.pdf_data = f.read()

        self.pdf_name = os.path.basename(pdf_file)

        self.saveSetting('pdf_name')
        self.saveSetting('pdf_data')

        self.PDF = self.createPDF(self.pdf_data)

    # Responses
    def isModified(self):
        return self.BOOK and self.BOOK.isModified()

    def isSummaryVisible(self):
        return self.summary

    def isViewerVisible(self):
        return self.viewer

    def hasPDF(self):
        return bool(self.PDF)


GLOBAL = GlobalSettings()
LOCAL = LocalSettings()


if __name__ == "__main__":
    d = LOCAL.Dict()
    d.digest('''
    
    ''')
    print(len(d.words), d.words)
