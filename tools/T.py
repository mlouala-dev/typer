# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import re
import time

from symspellpy import SymSpell, Verbosity
from string import ascii_letters, digits, whitespace
from html.parser import HTMLParser

from PyQt6.QtCore import QRunnable, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QTextDocument, QFont, QTextOption, QTextBlockFormat, QTextCursor, QFontMetrics
from tools import G, S


class Regex:
    src_audio_path = re.compile(r'^.*?src="audio_record_(.*?)".*?$')
    paragraph_time = re.compile(r'src="paragraph_time_(.*?)"')
    highlight_split = re.compile(r'[ \-\.\,:;!?\"\'\(\)\[\]\n￼«»]')
    ignoretoken = re.compile(r'\d|^[A-Z]|ﷺ|ﷻ|[\u0621-\u064a\ufb50-\ufdff\ufe70-\ufefc]')
    filter_text_style = re.compile(rf' ?font-family:\'{G.__la_font__}\',\'{G.__ar_font__}\';| ?font-family:\'{G.__la_font__}\';| ?font-family:\'{G.__ar_font__}\';| ?font-size:{G.__font_size__}pt;')
    filter_text_margin = re.compile(r' ?margin-\w+:\d+px;| ?line-height:100%;| text-indent:\d+px;')
    filter_ptime_height = re.compile(r'(<img src="paragraph_time_.*?".*?height=)".*?"(.*?>)')
    space_pattern = re.compile(r'\s{2,}')
    arabic_aliflam = re.compile(r"^ال")
    arabic_harakat = re.compile(r"[ًٌٍَُِْ~ّ]")
    arabic_hamzas = re.compile(r'[أإآ]')

    @staticmethod
    def update():
        Regex.filter_text_style = re.compile(rf' ?font-family:\'{G.__la_font__}\',\'{G.__ar_font__}\';| ?font-family:\'{G.__la_font__}\';| ?font-family:\'{G.__ar_font__}\';| ?font-size:{G.__font_size__}pt;')

    @staticmethod
    def complete_page_filter(content: str):
        content = Regex.filter_text_style.sub('', content)
        content = Regex.filter_text_margin.sub('', content)
        content = Regex.filter_ptime_height.sub(rf'\1"{HTML.default_height}"\2', content)
        content = content.replace(" font-family:&quot;'Microsoft Uighur'&quot;; font-size:15pt;", '')
        content = content.replace(' style=""', '')

        return content


def buildCharMap(*characters):
    return {ord(key): key for key in characters}


class Keys:
    phrase_characters = '.!?'
    word_characters = '(),:; "_[]«»' + phrase_characters
    quote_characters = '(\'"'

    NewPhrase = buildCharMap(*phrase_characters)
    NewWord = buildCharMap(*word_characters)
    Quotes = buildCharMap(*quote_characters)

    Exits = {60: "[", 62: "]", **Quotes, **NewWord}

    Latin_Letters = ascii_letters + 'éèêëàâäçîïôöûùü'


class SpellChecker(QObject):
    dictionary: SymSpell
    dictionary_path = G.appdata_path("dict.txt")
    finished = pyqtSignal()

    class Worker(QRunnable):
        name = 'SpellChecker'

        def __init__(self, callback_fn):
            super().__init__()
            self.callback_fn = callback_fn

        def run(self) -> None:
            sympell = SymSpell(max_dictionary_edit_distance=3, prefix_length=5)
            sympell.load_dictionary(SpellChecker.dictionary_path, term_index=0,
                                    count_index=1, encoding="utf8", separator="\t")

            self.callback_fn(sympell)

            self.done(self.name)

    def __init__(self):
        super().__init__()
        self.dictionary = None
        self.loaded = False

    def build(self):
        S.POOL.start(self.Worker(self.load))

    def load(self, dictionary: SymSpell):
        self.dictionary = dictionary
        self.finished.emit()
        self.loaded = True

    def add(self, word):
        """
        add a new word to the dictionary
        :param word: new word
        """

        with open(self.dictionary_path, 'a', encoding='utf-8') as f:
            # adding a new line for the word and a frequency of 1
            f.write(f'\n{word}\t1')

        self.build()

    def lookup(self, *args, **kwargs):
        return self.dictionary.lookup(*args, ignore_token=Regex.ignoretoken, **kwargs)

    def word_check(self, word: str):
        suggestions = self.lookup(word, max_edit_distance=2, verbosity=Verbosity.TOP,
                                  include_unknown=False, transfer_casing=False)

        try:
            return suggestions[0].term == word

        except IndexError:
            pass

    def block_check(self, text: str):
        for word in Regex.highlight_split.split(text):
            if len(word) and not self.word_check(word):
                return False
        else:
            return True


SPELL = SpellChecker()


class HtmlOperator(HTMLParser):
    """
    Core operations over HTML, based on html.parser
    """
    class TAG:
        tag = ''
        tags = {}
        _content = ''

        @property
        def content(self):
            return self._content

        def __repr__(self):
            tags = [self.tag] + [f'{key}="{tag}"' for key, tag in self.tags.items()]
            return f'<{" ".join(tags)}>{self.content}</{self.tag}>'

        def __str__(self):
            return repr(self)

    class P(TAG):
        tag = 'p'

        @property
        def content(self):
            print(len(self._content))
            return '\n'.join(map(str, self._content))

        def raw_content(self):
            return self._content

        def __init__(self, pos=0):
            self.id = pos
            self._content = []
            self.tags = {}

        def addTag(self, key, text):
            text = re.sub(r" +?margin-(top|bottom|left|right):\d+px;", '', text)
            text = re.sub(r" +?text-indent:\d+px;", '', text)
            text = re.sub(r" +?line-height:\d+%;", '', text)
            if len(text.strip()):
                self.tags[key] = text

        def addContent(self, obj: object):
            self._content.append(obj)

        def __iadd__(self, other):
            self.addContent(other)

    class SPAN(TAG):
        tag = 'span'

        def __init__(self):
            self._content = ''
            self.tags = {}

        def addTag(self, key, text):
            text = re.sub(f" +?font-family:\"?'{G.__la_font__}'\"?;", '', text)
            if len(text.strip()):
                self.tags[key] = text

        def __iadd__(self, other):
            self._content += other

    class BR:
        @property
        def content(self):
            return '<br>'

    paragraphs: [P]

    def __init__(self):
        self.paragraphs = []
        self.counter = 0
        self.wip_object = ''
        super().__init__()

    def feed(self, data: str) -> None:
        self.counter = 0

        super().feed(data)

    def handle_starttag(self, tag, attrs):
        print(tag)
        if tag == 'p':
            self.counter += 1
            p = self.P(self.counter)

            for key, tag in attrs:
                p.addTag(key, tag)

            self.wip_object = p

            self.paragraphs.append(p)

        elif tag == 'span':
            if len(self.paragraphs):
                p = self.paragraphs[-1]

            else:
                self.counter += 1
                p = self.P(self.counter)
                self.wip_object = p
                self.paragraphs.append(p)

            span = self.SPAN()
            self.wip_object = span

            p.addContent(span)

            for key, tag in attrs:
                span.addTag(key, tag)

    def handle_endtag(self, tag):
        if len(self.paragraphs):
            p = self.paragraphs[-1]

        if tag == 'span':
            self.wip_object = p

    def handle_data(self, data):
        if self.wip_object:
            self.wip_object += data

    def build(self):
        return self.paragraphs[-4]

    @staticmethod
    def hasParagraphTime(block: str) -> bool:
        return 'src="paragraph_time_' in block

    @staticmethod
    def paragraphTime(block: str) -> int:
        times = Regex.paragraph_time.findall(block)
        try:
            return int(times[0])
        except IndexError:
            return 0

    default_height = 20

    @staticmethod
    def getParagraphTime(t: int = 0) -> str:
        if not t:
            t = int(time.time())

        return f'''<img src="paragraph_time_{t}"
                 width="0" height="{HTML.default_height}" />'''

    def insertParagraphTime(self, cursor: QTextCursor, t: int = 0, metric: QFontMetrics = None):
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)

        if not self.hasParagraphTime(cursor.selection().toHtml()):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.MoveAnchor)
            cursor.insertHtml(self.getParagraphTime(t=t))

    @staticmethod
    def extractTextFragment(t: str, wide=False) -> str:
        """
        This function get a QTextFragment, remove the <html><head> tags and extract only the wanted code
        :param t: the HTML complete Text Fragment code
        :param wide: if we want the complete block (True) or just the selection (False)
        :return: HTML code extracted
        """
        try:
            assert not wide
            # getting what's inside the Start / End tags
            html = t.split('<!--StartFragment-->')[1].split('<!--EndFragment-->')[0]

        # if there is no match, extracting from body to the end and remove - if exists - the Start / End tags
        except (IndexError, AssertionError):
            html = t.split('<body>')[-1].replace('<!--StartFragment-->', '').split('<!--EndFragment-->')[0]

        return html


class TextOperator:
    """
    Core operations over TEXT
    """
    audio_char = 65532
    para_char = 8233
    re_exit_keys = re.compile(f'[{re.escape("".join(Keys.Exits.values()))}]')
    seq_exit_keys = set(Keys.Exits.values()).union(set(digits)).union(set(whitespace))

    @staticmethod
    def is_audio_tag(char):
        return ord(char) == TextOperator.audio_char

    def valid(self, word: str, length: int = 1) -> bool:
        """
        return if a word is valid in app's acception
        """
        elect = len(word) >= length and word[0] in Keys.Latin_Letters and word[-1] in Keys.Latin_Letters
        elect &= not len(set(word).intersection(self.seq_exit_keys))
        return elect

    def split(self, paragraph: str) -> [[str]]:
        """
        split the given paragraph as phrase with words as string inside
        !! this is not for a common use, only for the autosuggestion system
        """
        phrases = [[]]
        for word in self.re_exit_keys.split(paragraph):
            # if the given word in invalid, we break as a new phrase to make sure we'll only keep the
            # coherent suggestion
            if self.valid(word):
                phrases[-1].append(word)
            else:
                phrases.append([])

        # filtering the empty phrases
        return filter(lambda x: len(x), phrases)


class Arabic:
    @staticmethod
    def clean_harakats(text):
        return Regex.arabic_harakat.sub('', text)

    @staticmethod
    def reformat_hamza(text):
        return Regex.arabic_hamzas.sub('ا', text)

    @staticmethod
    def clean_alif_lam(text):
        return Regex.arabic_aliflam.sub('', text)


HTML = HtmlOperator()
TEXT = TextOperator()


class QOperator:
    """
    Operations over Qt objects
    """
    class ApplyDefault:
        @staticmethod
        def BlockFormat(blockformat: QTextBlockFormat):
            blockformat.setAlignment(Qt.AlignmentFlag.AlignJustify)
            blockformat.setTextIndent(10)
            blockformat.setLineHeight(100.0, 1)
            blockformat.setLeftMargin(0)
            blockformat.setRightMargin(0)
            blockformat.setTopMargin(0)
            blockformat.setBottomMargin(0)

        @staticmethod
        def Document(document: QTextDocument, font: QFont = None):
            if not font:
                font = G.get_font()

            document.setDefaultFont(font)
            document.setIndentWidth(10)
            document.setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignLeft))

        @staticmethod
        def Font(font: QFont):
            font.setItalic(False)
            font.setBold(False)
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        @staticmethod
        def DocumentStyleSheet() -> str:
            return f'''p, li, ul, ol {{
                margin-top:0px;
                margin-bottom:0px;
                margin-left:0px;
                margin-right:0px;
                font-family:'{G.__la_font__}','{G.__ar_font__}';
                font-size:{G.__font_size__}pt;
                text-indent: 10px;
            }}'''

    class graphBlockMap(QRunnable):
        name = 'graphBlockMap'

        def __init__(self, document: QTextDocument, callback_fn):
            self.callback_fn = callback_fn
            self.doc = document.clone()

            super().__init__()

        def run(self):
            self.doc.size()
            map = {}

            for block_id in range(self.doc.blockCount()):
                block = self.doc.findBlockByNumber(block_id)
                map[block_id] = (block.layout().position().y() + 1, block.layout().boundingRect().height() - 2)

            self.callback_fn(map)
            self.done(self.name)

    class solveAudioMapping(QRunnable):
        name = 'solveAudioMapping'

        def __init__(self, html: str, callback_fn):
            self.callback_fn = callback_fn
            self.html = re.split('<body.*?>', html)[-1].split('\n')

            super().__init__()

        def run(self):
            blocks = {}

            for i, html_block in enumerate(self.html):
                if HTML.hasParagraphTime(html_block):
                    solve = S.GLOBAL.AUDIOMAP.find(HTML.paragraphTime(html_block))
                    blocks[i - 1] = solve
                else:
                    blocks[i - 1] = -2

            self.callback_fn(blocks)
            self.done(self.name)
