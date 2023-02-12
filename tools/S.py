# بسم الله الرحمان الرحيم
"""
The Settings manager
"""
import importlib
import sqlite3
import html
import tempfile
import os
import re
from functools import partial
from html.parser import HTMLParser

from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThreadPool, QRunnable, QDir, QThread

from tools import G, T, Audio
from tools.translitteration import translitterate

QDir.addSearchPath('icons', G.rsc_path('images/icons'))
QDir.addSearchPath('typer', G.rsc_path('images/typer'))


class LIB:
    db = sqlite3.connect(G.rsc_path('ressources.db'))
    cursor = db.cursor()

    files = {}
    for name, data, local in cursor.execute('SELECT name,data,local FROM files').fetchall():
        if local:
            files[name] = G.abs_path(name)
        else:
            files[name] = tempfile.mktemp()

        with open(files[name], 'wb') as f:
            f.write(data)


class _Pool(QThreadPool):
    state = pyqtSignal(int)

    def __init__(self):
        self._count = 0
        self.jobs = []
        self.uniqids = []
        super().__init__()
        self.setThreadPriority(QThread.Priority.HighestPriority)

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, val):
        self._count = val
        self.state.emit(self._count)

    def start(self, job, uniq=None, priority=0, weight=1):
        if uniq and uniq in self.uniqids:
            return
        elif uniq:
            self.uniqids.append(uniq)
            job.done = partial(self.uniqJobDone, uniq)
        else:
            job.done = self.jobDone

        self.count += weight
        self.jobs.append(job.name)

        super().start(job, priority=priority)

    def jobDone(self, name: str):
        self.jobs.remove(name)
        self.count -= 1

    def uniqJobDone(self, uniqid, name):
        self.jobs.remove(name)
        self.uniqids.remove(uniqid)
        self.count -= 1


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
    class Quran:
        class Page:
            def __init__(self, page: int):
                self.num = page
                self.ayats = []

            def __repr__(self):
                return f'[PAGE:{self.num} == {",".join(map(repr, self.ayats))}'

        class Ayat:
            def __init__(self, num: int, text: str):
                self.num = num
                self.text = text
                self.surat = None
                self.page = 0

            def __repr__(self):
                return f'[{self.num}:{self.surat.num}@{self.page.num}]'

        class Surat:
            def __init__(self, num: int, name: str, name_ar: str, rev: int, place: int):
                self.num = num
                self.name = name
                self.arabic = name_ar
                self.rev = rev
                self.place = place

                self.ayats = []
                self.pages = []

            def __repr__(self):
                return f'[SURAT:{self.num} == {",".join(map(repr, self.ayats))}'

        def __init__(self):
            self.db = sqlite3.connect(G.rsc_path('quran.db'))
            self.cursor = self.db.cursor()

            self.ayats = []
            self.surats = {}
            self.pages = {}

            i = 1
            for name, arabic, revelation, place in self.cursor.execute(
                    'SELECT Name, Arabic, Revelation, Place FROM surats').fetchall():
                self.surats[i] = self.Surat(i, name, arabic, revelation, place)
                i += 1

            for surat, ayat, txt in self.cursor.execute('SELECT * FROM quran').fetchall():
                ayat = self.Ayat(ayat, txt)
                ayat.surat = self.surats[surat]
                self.surats[surat].ayats.append(ayat)
                self.ayats.append(ayat)

            prev_verse, prev_surat = 1, 1
            for num, surat, verse in self.cursor.execute('SELECT * FROM pages ORDER BY page ASC, surat ASC').fetchall():
                if surat != prev_surat:
                    prev_verse = 0

                if num in self.pages:
                    page = self.pages[num]
                else:
                    page = self.Page(num)
                    self.pages[num] = page

                for ayat in self.surats[surat].ayats[prev_verse:verse]:
                    page.ayats.append(ayat)
                    ayat.page = page

                self.surats[surat].pages.append(page)

                prev_verse = verse
                prev_surat = surat

        def getPageContent(self, num: int):
            page_content = [[]]
            page = self.pages[num].ayats
            previous_surat = page[0].surat.num

            for ayat in page:
                if ayat.surat.num != previous_surat:
                    page_content.append([])
                    previous_surat = ayat.surat.num

                page_content[-1].append(ayat)

            return page_content

        def getSuratContent(self, num: int):
            return [x.text for x in self.surats[num].ayats]

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
        highlight = QColor(42, 130, 218)
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
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
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

    class Lexicon:
        match_parenthesis = re.compile('(\(.*?\))')
        match_square_brackets = re.compile(r'(\[.*?])')

        class EntryContent:
            indent = {
                '': 0,
                'a': 1,
                'b': 2
            }

            def __init__(self, type: str = '', num: str = '', content: str = ''):
                self.type = type.lower()
                self.num = num
                self._content = content

            def post_treatment(self):
                content = ''
                splitted_content = GlobalSettings.Lexicon.match_square_brackets.split(self._content)
                for part in splitted_content:
                    if part.startswith('['):
                        part = f'<i>{part}</i>'
                        part = part.replace('<em>', '<em class="sub">')
                    content += part
                return content.strip()

            @property
            def content(self):
                return f'''<p align="justify" dir="ltr" style="margin-left:{pow(self.indent[self.type], 2) * 7}px;margin-right:10px;">
                {self.post_treatment()}
                </p>'''

            @content.setter
            def content(self, value: str):
                self._content = value

            def add_content(self, value: str):
                self._content += value

        class Entry(HTMLParser):
            needle = -1
            ignore = None

            def __init__(self, nid: str, root: str, word: str, bword: str):
                super().__init__()

                self.nodeid = nid
                self.root = root
                self.word = word
                self.bareword = bword

                self.contents = [
                    GlobalSettings.Lexicon.EntryContent()
                ]

            def add_content(self, value):
                nice_value = value.replace('\n', '')
                nice_value = T.Regex.space_pattern.sub(' ', nice_value)
                self.contents[-1].add_content(nice_value)

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if self.ignore:
                    return

                attrs = {a: b for a, b in attrs}
                if tag == 'sense':
                    self.contents.append(GlobalSettings.Lexicon.EntryContent(attrs['type'], attrs['n']))
                elif tag == 'hi' and attrs['rend'] == 'ital':
                    self.add_content('<em>')
                elif tag == 'ref':
                    self.add_content(f'<a href="{attrs["cref"]}">{attrs["target"]}</a> ')
                elif tag == 'foreign' and attrs['lang'] == 'ar':
                    self.add_content(f'<dfn>')
                elif tag == 'itype':
                    self.add_content('<code>')
                elif tag == 'orth' and not 'orig' in attrs:
                    self.ignore = tag
                elif tag == 'orth':
                    self.add_content('<cite>')
                elif tag == 'assumedtropical':
                    self.add_content('<samp>')
                elif tag == 'tropical':
                    self.add_content('<samp>')
                # else:
                #     print(tag, attrs)

            def handle_endtag(self, tag: str) -> None:
                if self.ignore and self.ignore == tag:
                    self.ignore = None
                    return

                if tag == 'hi':
                    self.add_content('</em>')
                elif tag == 'foreign':
                    self.add_content('</dfn>')
                elif tag == 'itype':
                    self.add_content('</code>')
                elif tag == 'orth':
                    self.add_content('</cite>')
                elif tag == 'assumedtropical':
                    self.add_content('</samp>')
                elif tag == 'tropical':
                    self.add_content('</samp>')

            def handle_data(self, data: str) -> None:
                if not self.ignore:
                    self.add_content(GlobalSettings.Lexicon.match_parenthesis.sub(r'<tt>\1</tt>', data))

            def __str__(self):
                res = ''
                for r in [T.Regex.space_pattern.sub(" ", c.content) for c in self.contents]:
                    res += f'<p align="justify" dir="ltr">{r}</p>'
                return res

        def __init__(self):
            self.db = sqlite3.connect(G.rsc_path(f'lexicon_{GLOBAL.lang}.db'))
            self.cursor = self.db.cursor()

            self.barewords = self.fetchall_results('SELECT bareword FROM entry')
            self.roots = self.fetchall_results('SELECT DISTINCT root FROM entry')

        def fetchall_results(self, *args):
            res = []
            for p in self.cursor.execute(*args).fetchall():
                res.extend(p)
            return res

        def bare_search(self, needle):
            return self.fetchall_results('SELECT nodeid FROM entry WHERE bareword=?', (needle,))

        def search(self, needle):
            return self.fetchall_results('SELECT nodeid FROM entry WHERE word=?', (needle,))

        def wide_search(self, needle):
            return self.fetchall_results(f'SELECT nodeid FROM entry WHERE word LIKE "%{needle}%"')

        def wide_bare_search(self, needle):
            return self.fetchall_results(f'SELECT nodeid FROM entry WHERE bareword LIKE "%{needle}%"')

        def get_results(self, result_id: list):
            if len(result_id):
                res = []
                for node_id in result_id:
                    nid, root, word, bword, xml = \
                    self.cursor.execute('SELECT nodeid, root, word, bareword, xml FROM entry WHERE nodeid=?',
                                        (node_id,)).fetchall()[0]
                    bword = T.Arabic.reformat_hamza(bword)
                    new_entry = GlobalSettings.Lexicon.Entry(nid, root, word, bword)
                    new_entry.feed(xml)
                    res.append(str(new_entry))
                return '\n<hr/>\n'.join(res), root
            else:
                return None, None

        def find(self, needle):
            if T.Regex.arabic_harakat.findall(needle):
                res = self.search(needle)
            else:
                res = None
            if not res:
                res = self.bare_search(needle)

            no_harakat = T.Arabic.clean_harakats(needle)
            if not res and len(no_harakat) > 4:
                sub_needle = T.Arabic.clean_alif_lam(no_harakat)
                sub_needle = T.Arabic.reformat_hamza(sub_needle)
                res = self.bare_search(sub_needle)

            if not res:
                res = self.wide_search(needle)

            if not len(res):
                res = self.wide_bare_search(needle)
            return self.get_results(res)

        def find_by_root(self, needle):
            needle = T.Arabic.clean_harakats(needle)

            if needle in self.roots:
                return self.get_results(self.fetchall_results('SELECT nodeid FROM entry WHERE root=?', (needle,)))
            return None, None

        def find_deep(self, needle):
            needle = T.Arabic.reformat_hamza(needle)
            pat = re.compile(T.Arabic.wide_arabic_pattern(needle))

            def matched(value):
                return pat.search(T.Arabic.reformat_hamza(value)) is not None

            self.db.create_function('REGEXP', 1, matched)

            res = self.fetchall_results('SELECT nodeid FROM entry WHERE REGEXP(xml)')
            return self.get_results(res)

    class Predikt(QRunnable):
        name = 'Predikt'
        db_path = G.appdata_path('predikt_data.db')
        loaded = False
        chunk_size = 500000

        class Word:
            def __init__(self, word, ancestors=('', ''), tag='', tense=0, _weight=1, _vector=None):
                self.word = str(word)
                self.tag = tag
                self._ancestors = []
                self.tail = ''
                self.tense = tense

                self.weight = _weight

                self.first_ancestor = ''
                self.last_ancestor = ''

                self.ancestors = list(ancestors)

            @property
            def ancestors(self):
                return self._ancestors

            @ancestors.setter
            def ancestors(self, value: [str]):
                self._ancestors = value
                if len(value):
                    if value[-1].startswith('-'):
                        self.tail = ''.join(value)
                    else:
                        self.tail = ' '.join(value)

                    self.first_ancestor, self.last_ancestor = value

            def set_tense(self, tense=0):
                self.tense = tense

            def __repr__(self):
                res = f'"{self.word}" ({self.weight}) [{", ".join(map(str, self.ancestors))}]'

                if self.tense != "000":
                    res += f' = {self.tense}'

                res += f' #{hash(self)}'

                return res

            def __hash__(self):
                return hash(' '.join(self.ancestors) + self.word)

            def __eq__(self, other):
                if isinstance(other, GlobalSettings.Predikt.Word):
                    return (' '.join(self.ancestors) + self.word) == (' '.join(other.ancestors) + other.word)

                return False

        class Loader(QRunnable):
            name = 'PrediktLoader'

            def __init__(self, cb):
                self.callback = cb
                super().__init__()

            def run(self):
                db = sqlite3.connect(GlobalSettings.Predikt.db_path)
                cursor = db.cursor()
                cursor.execute(f'SELECT * FROM tokens ORDER BY weight DESC')

                words = cursor.fetchmany(GlobalSettings.Predikt.chunk_size)
                database = []

                while words:
                    database.extend([GlobalSettings.Predikt.Word(word, ancestors=[t1, t2], _weight=weight) for
                                    word, weight, t1, t2 in words])
                    words = cursor.fetchmany(GlobalSettings.Predikt.chunk_size)

                db.close()
                self.callback(database)
                self.done(self.name)

        class Temporal(QObject):
            masks = {
                'tense': {
                    'Pres': 1,
                    'Imp': 2,
                    'Past': 3,
                    'Fut': 4
                },
                'voice': {
                    'Pass': 1
                },
                'form': {
                    'Fin': 1,
                    'Part': 2,
                    'Inf': 3
                }
            }
            tenseAnalysed = pyqtSignal(int)

            class Analysis(QRunnable):
                name = 'PrediktAnalysis'

                def __init__(self, sample, nlp, callback):
                    self.cb = callback
                    self.nlp = nlp
                    self.sample = sample
                    super().__init__()

                def run(self):
                    doc = self.nlp(self.sample)

                    for token in reversed(doc):
                        if token.pos_ == "VERB":
                            t, v, f = token.morph.get("Tense"), token.morph.get("Voice"), token.morph.get("VerbForm")
                            verb_data = ''
                            verb_data += str(GLOBAL.PREDIKT.Temporal.masks['tense'][t[0]]) if len(t) else '0'
                            verb_data += str(GLOBAL.PREDIKT.Temporal.masks['voice'][v[0]]) if len(v) else '0'
                            verb_data += str(GLOBAL.PREDIKT.Temporal.masks['form'][f[0]]) if len(f) else '0'

                            self.cb(int(verb_data))
                            break

                    self.done(self.name)

            class Loader(QRunnable):
                name = 'PrediktAnalysisLoader'

                def __init__(self, callback):
                    self.cb = callback
                    super().__init__()

                def run(self):
                    # nlp = importlib.import_module('fr_core_news_lg')
                    nlp = None
                    self.cb(nlp)
                    self.done(self.name)

        class Digester(QRunnable):
            name = 'PrediktDigester'
            lower_exceptions = ('Prophète', 'Muhammad', 'Abû', 'Allah', 'Dieu', 'Coran')

            cleanups = [
                ('[\n\r]', ' '),
                ('“', '"'),
                ('[ḤḢḦ]', 'H'),
                ('[ḥḣḧ]', 'h'),
                ('[ḊḌḎḐḒ]', 'D'),
                ('[ḋḍḏḑḓ]', 'd'),
                ('[ṠṢṨ]', 'S'),
                ('[ṡṣṩ]', 's'),
                ('[ṪṬṮṰ]', 'T'),
                ('[ṫṭṯṱ]', 't'),
                (fr'''([{T.Regex.extra_characters}]){{2,}}''', r'\1'),
                ('œ', 'oe'),
                ("'’ʽ`", "'"),
                ('–', '-')
            ]

            R_cleanups = [re.compile(a) for a, b in cleanups]

            def cleanup(self, text=''):
                for seq, eqs in zip(self.R_cleanups, self.cleanups):
                    text = seq.sub(eqs[1], text)

                return text

            def __init__(self, sample, cb):
                self.sample = sample
                self.callback = cb
                super().__init__()

            def run(self):
                # print(f'reading book ... {len(self.sample)}')
                cleanup = self.cleanup(self.sample)

                elements = set()

                for text_block in T.Regex.Predikt_full_match.findall(cleanup):
                    sentences = []

                    for sentence in T.Regex.Predikt_hard_split.split(text_block):
                        sentence = sentence.strip(' -')

                        if len(sentence) <= 3:
                            continue

                        for exception in self.lower_exceptions:
                            if sentence.startswith(exception):
                                break
                        else:
                            sentences.append(sentence[0].lower() + sentence[1:])

                    for sentence in sentences:
                        # print(f'== {sentence}')

                        words = list(filter(lambda x: len(x), T.Regex.Predikt_soft_split.split(sentence)))

                        for i, word in enumerate(words):
                            if (T.Regex.proper_nouns.match(word)
                                or not T.Regex.Predikt_ignore_for_dictionnary.match(word)) \
                                    and word not in T.SPELL.flat_dictionary\
                                    or T.Regex.bad_uppercase.match(word):

                                replace = ' '.join(words[i + 1:])

                                sentences.append(replace)

                                break

                            ancestor_1, ancestor_2 = (('', '',) + tuple(words[max(0, i - 2):i]))[-2:]
                            # print(ancestor_1, ancestor_2, word)

                            obj = GlobalSettings.Predikt.Word(word, (ancestor_1, ancestor_2))

                            if obj in elements:
                                for e in elements:
                                    if hash(obj) == hash(e):
                                        e.weight += 1
                                        break
                            else:
                                elements.add(obj)

                self.callback(elements)
                self.done(self.name)

        def __init__(self):
            self.TEMPORAL = self.Temporal()

            self.nlp = None

            self.database = []
            self.wanted = 0

            self.raw = []
            self.words_tail_last_letter = {}
            self.words_tail = {}
            self.words_tail_last_word = {}

            self.wide_range = {}
            self.words = set()

            super().__init__()

            self.setAutoDelete(False)
            self.preload()

        def preload(self):
            POOL.start(self.Loader(self.core_loaded))
            POOL.start(self.Temporal.Loader(self.nlp_loaded))

        def core_loaded(self, database):
            self.database.extend(database)
            POOL.start(self)

        def analyze(self, sample=''):
            if not self.nlp or not self.loaded:
                return

            POOL.start(self.Temporal.Analysis(sample, self.nlp, self.analysis_done), uniq=192)

        def analysis_done(self, tense=0):
            self.TEMPORAL.tenseAnalysed.emit(tense)

        def nlp_loaded(self, nlp):
            self.nlp = nlp

        def run(self):
            word: GlobalSettings.Predikt.Word

            self.raw.extend(self.database)

            for word in self.database:
                try:
                    if word.tail[-1] in self.words_tail_last_letter:
                        self.words_tail_last_letter[word.tail[-1]].append(word)
                    else:
                        self.words_tail_last_letter[word.tail[-1]] = [word]

                    if word.last_ancestor in self.words_tail_last_word:
                        self.words_tail_last_word[word.last_ancestor].append(word)
                    else:
                        self.words_tail_last_word[word.last_ancestor] = [word]

                except IndexError:
                    # no ancestor
                    pass

                try:
                    if len(word.word) <= 2:
                        raise IndexError

                    for chr in range(1, len(word.word)):
                        if word.word[:chr] in self.wide_range:
                            self.wide_range[word.word[:chr]].append(word)
                        else:
                            self.wide_range[word.word[:chr]] = [word]

                except IndexError:
                    pass

                if word.tail in self.words_tail:
                    self.words_tail[word.tail].append(word)
                else:
                    self.words_tail[word.tail] = [word]

            self.database.clear()

            self.loaded = True
            self.done(self.name)

        def predict(self, ancestor_1, ancestor_2, word, tense=None):
            if not self.loaded:
                return ''

            def sort_by_tense(elements):
                if tense:
                    elements.sort(key=lambda x: x.tense != tense)

            tail = ' '.join((ancestor_1, ancestor_2,))

            def filter_by_tail(elements):
                for element in elements:
                    if element.tail.endswith(tail):
                        return [element]
                else:
                    return []

            def filter_by_head(elements):
                for element in elements:
                    if element.word.startswith(word):
                        return [element]
                else:
                    return []

            # print(f'trying to predict... "{tail}"..."{word}"', f' (preferring {tense} tense)' if tense else '')

            results = []
            target = self.Word(word, (ancestor_1, ancestor_2))

            go_tail = False

            try:
                candidates = self.wide_range[word]
                sort_by_tense(candidates)
                results = filter_by_tail(candidates)

                if not len(results):
                    results = [candidates[0]]

            except KeyError:
                # print("= CANT FIND WORD AND TAIL")
                # both word first letter and tail can't be found

                try:
                    candidates = self.words_tail_last_word[target.last_ancestor]
                    sort_by_tense(candidates)
                    results = filter_by_head(candidates)

                except (IndexError, KeyError):
                    go_tail = True
                    # print('CANT FIND LAST ANCESTOR ONLY')
                    pass

            if go_tail:
                try:
                    results = self.words_tail[tail]

                except KeyError:
                    # print("=== CANT FIND WORD TAIL")
                    try:
                        candidates = self.words_tail_last_letter[tail[-1]]
                        results = filter_by_tail(candidates)
                        sort_by_tense(results)

                    except IndexError:
                        # print('==== NO TAIL LENGTH')
                        pass

                    except KeyError:
                        # print("==== CANT FIND WORD LAST LETTER")
                        pass

            if len(results):
                # print(results)
                return results[0].word
            else:
                return ''

        def digest(self, text=''):
            POOL.start(self.Digester(text, self.apply_to_db))

        def apply_to_db(self, elements):
            db = sqlite3.connect(self.db_path)
            cursor = db.cursor()

            news, updates = 0, 0

            for element in elements:
                try:
                    cursor.execute('INSERT INTO tokens (word, weight, ancestor_1, ancestor_2) VALUES (?, ?, ?, ?)',
                                   (element.word, element.weight, element.first_ancestor, element.last_ancestor))
                    news += 1

                except sqlite3.IntegrityError:
                    res = cursor.execute('SELECT weight FROM tokens WHERE word=? AND ancestor_1=? AND ancestor_2=?',
                                         (element.word, element.first_ancestor, element.last_ancestor))
                    element.weight += res.fetchone()[0]
                    cursor.execute('UPDATE tokens SET weight=? WHERE word=? AND ancestor_1=? AND ancestor_2=?',
                                   (element.weight, element.word, element.first_ancestor, element.last_ancestor))
                    updates += 1

                except sqlite3.OperationalError:
                    return self.apply_to_db(elements)

            db.commit()
            db.close()

            self.core_loaded(elements)

    themes = {
        'dark': Dark(),
        'light': Light()
    }

    defaults = {
        'lang': 'en',
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
        'minimum_word_length': 2,
        'arabic_font_family': 'Arial',
        'latin_font_family': 'Arial',
        'font_size': 14
    }

    step = pyqtSignal(int, str)
    loaded = pyqtSignal()

    def __init__(self):
        self.QURAN = GlobalSettings.Quran()
        self.LEXICON = None
        self.PREDIKT = GlobalSettings.Predikt()

        super().__init__()
        self.filename = G.appdata_path('config.db')
        self.create_db_link()

        self.lang = self.defaults['lang']
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

        self.arabic_font_family = self.defaults['arabic_font_family']
        self.latin_font_family = self.defaults['latin_font_family']
        self.font_size = self.defaults['font_size']

        self.AUDIOMAP = Audio.AudioMap

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
            self.AUDIOMAP = Audio.AudioMap(self.audio_record_path)

    def loadSettings(self):
        settings = self.loadCoreSettings()
        # closing file if other instance needs it
        self.db.close()

        self.setTheme(settings['theme'])

        self.lang = settings['lang']
        self.LEXICON = GlobalSettings.Lexicon()

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

        self.arabic_font_family = settings['arabic_font_family']
        self.latin_font_family = settings['latin_font_family']
        G.__ar_font__ = self.arabic_font_family
        G.__la_font__ = self.latin_font_family

        self.font_size = int(settings['font_size'])
        G.__font_size__ = self.font_size

        self.loaded.emit()

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
        'audio_map': False
    }

    step = pyqtSignal(int, str)
    pageChanged = pyqtSignal(int)

    class Book:
        class Page:
            def __init__(self, content: str, cursor: int = -1):
                self._content = content
                self.cursor = cursor if cursor is not None else 0

            @property
            def content(self):
                return self._content

            @content.setter
            def content(self, new_content):
                self._content = T.Regex.complete_page_filter(new_content)

            @property
            def head(self):
                return self.content.split('<hr />')[0]

            @property
            def body(self):
                return self.content.split('<hr />')[-1]

            def __repr__(self):
                return self.content

            def __str__(self):
                return self.content

        def __init__(self, db: sqlite3.Connection = None, cursor: sqlite3.Cursor = None):
            self._mod = set()
            self._book = {}
            self._db = db
            self._cursor = cursor

            if self._cursor:
                try:
                    self._cursor.execute('SELECT cursor FROM book').fetchone()
                except sqlite3.OperationalError:
                    G.error('Inconsistent database (missing cursor column), updating')
                    self._cursor.execute('ALTER TABLE book ADD cursor INTEGER')
                    self._db.commit()
                finally:
                    for p, text, cur in self._cursor.execute('SELECT page, text, cursor FROM book').fetchall():
                        self._book[p] = self.Page(html.unescape(text), cur)

        def getBook(self) -> dict:
            return {a: b.content for a, b in self._book.items()}

        def savePage(self, page: int):
            clean_page = html.escape(self[page].content)

            try:
                self._cursor.execute('INSERT INTO book ("page", "text", "cursor") VALUES (?, ?, ?)',
                                     (page, clean_page, self[page].cursor))

            except sqlite3.IntegrityError:
                self._cursor.execute(f'UPDATE book SET text=?, cursor=? WHERE page={page}',
                                     (clean_page, self[page].cursor))

            self._db.commit()
            self._mod.remove(page)

        def removePage(self, page: int):
            self._book.pop(page)
            self.unsetModified(page)
            self._cursor.execute('DELETE FROM book WHERE page=?', (page,))
            self._db.commit()

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
                self[key].content = value
                self.setModified(key)

        def minPageNumber(self) -> int:
            return int(min(self._book.keys()))

        def maxPageNumber(self) -> int:
            return int(max(self._book.keys()))

        def pages(self) -> list:
            return list(self._book.keys())

        def __getitem__(self, item):
            return self._book[item]

        def __setitem__(self, key, value):
            if isinstance(value, self.Page):
                self._book[key] = value

            else:
                try:
                    assert self._book[key].content != value

                except AssertionError:
                    return

                except KeyError:
                    pass

                finally:
                    self._mod.add(key)
                    self._book[key].content = value

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

            def __contains__(self, item):
                return T.Arabic.clean_harakats(item) in T.Arabic.clean_harakats(self.content)

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
                if needle in T.Arabic.reformat_hamza(kitab.name):
                    return kitab

        def findBab(self, needle: str, scope: int = None) -> Bab:
            if scope is not None:
                scoped = self.kutub[scope].abwab
            else:
                scoped = self.abwab

            for bab in scoped:
                if needle in T.Arabic.reformat_hamza(bab.name):
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

    class Topics:
        Domains = {
            'prophet': 'Prophètes',
            'person': 'Personnalités',
            'place': 'Lieux',
            'theme': 'Thèmes',
            'fiqh': 'Questions jurisprudencielles',
            'nahw': 'Grammaire',
            'lugha': 'Linguistique'
        }

        class Topic:
            def __init__(self, name: str = '', domain: str = ''):
                self.name = name
                self.domain = domain

            def __lt__(self, other):
                return self.name < other

            def __gt__(self, other):
                return self.name > other

            def __eq__(self, other):
                return self.name == other.name and self.domain == other.domain

            def __str__(self):
                return self.name

            def __repr__(self):
                return self.name

            def __hash__(self):
                return hash(repr(self))

        def __init__(self):
            self.pages = {}
            self.domains = {dom: set() for dom in self.Domains}
            self.topics = {}

        def addTopic(self, name: str = '', domain: str = '', page: int = 0):
            try:
                topic = self.topics[name]
            except KeyError:
                self.topics[name] = topic = self.Topic(name, domain)

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
                if topic in domain:
                    domain.remove(topic)

            self.topics.pop(name)

        def updateTopicDomain(self, name: str = '', domain_name: str = ''):
            topic = self.getTopic(name)

            for domain in self.domains.values():
                if topic in domain:
                    domain.remove(topic)

            self.domains[domain_name].add(topic)
            topic.domain = domain_name

        def getTopic(self, name: str = ''):
            return self.topics[name]

        def removeTopicFromPage(self, name: str = '', page: int = 0):
            for item in reversed(list(self.pages[page])):
                if item.name == name:
                    self.pages[page].remove(item)

    BOOK: Book

    def __init__(self):
        self.BOOK = LocalSettings.Book()

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
        self.audio_map = self.defaults['audio_map']
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
            CONSTRAINT "uniq" UNIQUE("word","before")
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
                        name=T.Arabic.clean_harakats(name),
                        kid=kid,
                        page=self.BOOKMAP.getPage(page)
                    )
                    for bid, bname, bpage in self.cursor.execute(
                            f'SELECT id, name, page FROM bm_abwab WHERE kitab={kid}').fetchall():
                        if bname:
                            bab = LocalSettings.BookMap.Bab(
                                name=T.Arabic.clean_harakats(bname),
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
        self.audio_map = bool(settings['audio_map'])
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
                                    (int(self.audio_map), 'audio_map')
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
        self.cursor.executemany(f"DELETE FROM topics WHERE name=? AND page=?",
                                [(topic.name, self.page) for topic in topic_delete])

        # loop to add all topics from list
        for topic in topic_add:
            self.cursor.execute('''INSERT INTO topics (name, domain, page) VALUES (?, ?, ?)''',
                                (topic.name, topic.domain, self.page))

        self.db.commit()

    def changeTopicDomain(self, topic: str = '', domain: str = ''):
        self.TOPICS.updateTopicDomain(topic, domain)
        self.cursor.execute('''UPDATE topics SET domain=? WHERE name=?''', (domain, topic))

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
