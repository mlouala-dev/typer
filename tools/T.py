# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import re
import sys
import time

from symspellpy import SymSpell, Verbosity
from string import ascii_letters, digits, whitespace
from html.parser import HTMLParser

from PyQt6.QtCore import QRunnable, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QTextDocument, QFont, QTextOption, QTextBlockFormat, QTextCursor, QFontMetrics
from tools import G


class Regex:
    src_audio_path = re.compile(r'^.*?src="audio_record_(.*?)".*?$')
    paragraph_time = re.compile(r'src="paragraph_time_(.*?)"')
    highlight_split = re.compile(r'[ \-\.\,:;!?\"\(\)\[\]\n￼«»]')
    ignoretoken = re.compile(r'\d|^[A-Z]|ﷺ|ﷻ|[\u0621-\u064a\ufb50-\ufdff\ufe70-\ufefc]')
    filter_text_style = re.compile(rf' ?font-family:\'{G.__la_font__}\',\'{G.__ar_font__}\';| ?font-family:\'{G.__la_font__}\';| ?font-family:\'{G.__ar_font__}\';| ?font-size:{G.__font_size__}pt;')
    filter_text_margin = re.compile(r' ?margin-\w+:\d+px;| ?line-height:100%;| text-indent:\d+px;')
    filter_ptime_height = re.compile(r'(<img src="paragraph_time_.*?".*?height=)".*?"(.*?>)')
    space_pattern = re.compile(r'\s{2,}')
    arabic_aliflam = re.compile(r"^ال")
    arabic_harakat = re.compile(r"[ًٌٍَُِْ~ّ]")
    arabic_hamzas = re.compile(r'[أإآ]')
    simple_quotes = re.compile(r"[’ʽ]")
    double_quotes = re.compile(r"[«»]")
    match_SAWS = re.compile(r"\s?-?صلى الله عليه وسلم-?\s?")

    uppercases = "".join([chr(i) for i in range(sys.maxunicode) if chr(i).isupper()])
    proper_nouns = re.compile('^[{}]'.format(uppercases))
    bad_uppercase = re.compile('^.+[{}]'.format(uppercases))

    soft_break_characters = r''',;[\]*/+@<=>^_{|}°~'''
    hard_break_characters = r'''￼().!?"«»:…۞'''

    extra_characters = r'''\-–'’`ʽ''' + soft_break_characters + hard_break_characters
    alpha_characters = r'''A-Za-zÀ-ÿ'''
    full_match_characters = alpha_characters + extra_characters + whitespace

    tokenizer = re.compile(r"""([A-Za-zÀ-ÿ]+'|-|[A-Za-zÀ-ÿ]+)|([().!?\"«»:…۞,;[\]*\/+@<=>^_{|}°~￼]+)|([\d\u0621-\u064a\ufe70-\ufefc]+.*?\s)""")
    is_title = re.compile(r"^[A-ZÔÎÛÂÊ]").match
    is_digit = re.compile(r'.*?\d+').match

    Predikt_hard_split = re.compile(f'''[{hard_break_characters}]''')
    Predikt_hard_soft_split = re.compile(f'''[{hard_break_characters}{soft_break_characters}]''')
    Predikt_hard_soft_w_split = re.compile(f'''[{hard_break_characters}{soft_break_characters}{whitespace}]|(?<=')''')
    Predikt_soft_split = re.compile(f'''[{soft_break_characters}{whitespace}]|(?<=')''')
    Predikt_full_match = re.compile(f'''([{full_match_characters}]{{3,}})''')

    Predikt_ignore_token = re.compile(r'.*?[\d\u0621-\u064a\ufe70-\ufefc]')
    Predikt_ignore_for_dictionnary = re.compile(r'''^[A-ZÔÎÛÂÊ]|^.*[\-']''')

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

    @staticmethod
    def Predikt_cleanup(content: str):
        cleanup = Regex.Predikt_cleanup_whitespace.sub(' ', content)
        cleanup = cleanup.replace('œ', 'oe')
        cleanup = cleanup.strip()
        cleanup = cleanup.strip('-')

        return cleanup

    @staticmethod
    def tokenize(body_text: str):
        """
        this tokenizes the text with a rule
        :param body_text: the whole text we want to tokenize
        :return: yield the index of the word and the word itself
        """
        # TODO: this split regex should be an re.unescape(''.join(G.escape...) ???
        iterator = Regex.tokenizer.finditer(body_text)

        x = None
        try:
            y = next(iterator)
        except StopIteration:
            y = 0

        for z in iterator:
            y1, yd, ya = y.groups()
            z1, zd, za = z.groups()
            if yd or ya:
                x = None
                y = z
                continue
            index = y.span(0)[0] + 1
            yield index, x, y1, z1
            # increments the current text's index

            x = y1
            y = z


def buildCharMap(*characters):
    return {ord(key): key for key in characters}


class Keys:
    phrase_characters = '.!?'
    word_characters = '(),:; "_[]«»' + phrase_characters
    quote_characters = '(\'"'
    whitespace = ' \t\n\r\v\f'

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

            flat_dictionary = set()

            with open(SpellChecker.dictionary_path, mode='r+', encoding='utf-8') as f:
                for line in f.readlines():
                    flat_dictionary.add(line.split('\t')[0])

            self.callback_fn(sympell, flat_dictionary)

            self.done(self.name)

    def __init__(self):
        super().__init__()
        self.dictionary = None
        self.flat_dictionary = set()
        self.loaded = False

    def build(self):
        from tools.S import POOL
        POOL.start(self.Worker(self.load))

    def load(self, dictionary: SymSpell, flat_dictionary: set):
        self.dictionary = dictionary
        self.flat_dictionary.update(flat_dictionary)

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


class ArabicOperator:
    hurufs = frozenset('ذضصثقفغعهخحجدشسيبلاتنمكطئءؤرىةوزظإأـ')
    digits = list("٠١٢٣٤٥٦٧٨٩")

    @staticmethod
    def clean_harakats(text):
        return Regex.arabic_harakat.sub('', text)

    @staticmethod
    def reformat_hamza(text):
        return Regex.arabic_hamzas.sub('ا', text).replace('ٓ', '')

    @staticmethod
    def clean(text):
        return ArabicOperator.clean_harakats(ArabicOperator.reformat_hamza(text))

    @staticmethod
    def clean_alif_lam(text):
        return Regex.arabic_aliflam.sub('', text)

    def wide_arabic_pattern(self, needle):
        if Regex.arabic_harakat.fullmatch(needle):
            needle = self.clean_harakats(needle)

        return re.sub(f'([{"".join(self.hurufs)}])', r'\1[ًٌٍَُِّْ]{0,2}', needle)

    def is_arabic(self, text):
        text = self.reformat_hamza(self.clean_harakats(text))
        return len(re.findall(f'[{self.hurufs}]', text)) == len(text)


HTML = HtmlOperator()
TEXT = TextOperator()
Arabic = ArabicOperator()


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
