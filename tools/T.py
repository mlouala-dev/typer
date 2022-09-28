# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import copy
import html
import re
import time

from PyQt5.QtWidgets import QWidget, QApplication
from symspellpy import SymSpell, Verbosity
from string import ascii_letters, digits, whitespace
from html.parser import HTMLParser

from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, Qt, QSizeF
from PyQt5.QtGui import QTextDocument, QFont, QTextOption, QTextBlockFormat, QTextCursor, QFontMetrics
from tools import G, S


class Regex:
    src_audio_path = re.compile(r'^.*?src="audio_record_(.*?)".*?$')
    paragraph_time = re.compile(r'src="paragraph_time_(.*?)"')
    highlight_split = re.compile(r'[ \-\.\,:;!?\"\'\(\)\[\]\n]')
    re_ignoretoken = r'\d|^[A-Z]|ﷺ|ﷻ'


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
            sympell = SymSpell(max_dictionary_edit_distance=2, prefix_length=5)
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
        return self.dictionary.lookup(*args, ignore_token=Regex.re_ignoretoken, **kwargs)

    def word_check(self, word: str):
        suggestions = self.lookup(word, max_edit_distance=2, verbosity=Verbosity.TOP,
                                  include_unknown=False, transfer_casing=False)

        # abort if word's already in the dictionary
        return suggestions[0].term == word

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
            text = re.sub(f" +?font-family:\"?'{G.__font__}'\"?;", '', text)
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

    @staticmethod
    def getParagraphTime(metrics: QFontMetrics = None, t: int = 0) -> str:
        if not t:
            t = int(time.time())

        if not metrics:
            metrics = QFontMetrics(G.get_font())

        return f'''<p><img src="paragraph_time_{t}"
                 width="0" height="{int(metrics.height())}" /></p>'''

    def insertParagraphTime(self, cursor: QTextCursor, t: int = 0):
        cursor.select(QTextCursor.BlockUnderCursor)

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
    re_exit_keys = re.compile(f'[{re.escape("".join(Keys.Exits.values()))}]')
    seq_exit_keys = set(Keys.Exits.values()).union(set(digits)).union(set(whitespace))

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


HTML = HtmlOperator()
TEXT = TextOperator()


class QOperator:
    """
    Operations over Qt objects
    """
    class ApplyDefault:
        @staticmethod
        def BlockFormat(blockformat: QTextBlockFormat):
            blockformat.setAlignment(Qt.AlignJustify)
            blockformat.setTextIndent(10)
            blockformat.setLineHeight(100.0, 1)
            blockformat.setLeftMargin(10)
            blockformat.setRightMargin(10)

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

    class graphBlockMap(QRunnable):
        name = 'graphBlockMap'

        def __init__(self, document: QTextDocument, callback_fn):
            self.callback_fn = callback_fn
            self.doc = document.clone()
            self.doc.setHtml(document.toHtml())
            self.doc.size()

            super().__init__()

        def run(self):
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


# t = html.unescape('''&lt;!DOCTYPE HTML PUBLIC &quot;-//W3C//DTD HTML 4.0//EN&quot; &quot;http://www.w3.org/TR/REC-html40/strict.dtd&quot;&gt;
# &lt;html&gt;&lt;head&gt;&lt;meta name=&quot;qrichtext&quot; content=&quot;1&quot; /&gt;&lt;style type=&quot;text/css&quot;&gt;
# p, li { white-space: pre-wrap; }
# &lt;/style&gt;&lt;/head&gt;&lt;body style=&quot; font-family:&#x27;Microsoft Uighur&#x27;,&#x27;Microsoft Uighur&#x27;; font-size:14.4pt; font-weight:400; font-style:normal;&quot;&gt;
# &lt;h3 align=&quot;center&quot; style=&quot; margin-top:14px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;&quot;&gt;&lt;span style=&quot; font-size:large; font-weight:600; color:#9b6a28;&quot;&gt;296&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic; color:#bb9a48;&quot;&gt;[16]&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; وَعَنْ رَجُلٍ مِنْ بَنِي سُلَيْمٍ قَالَ: عَدَّهُنَّ رَسُولِ اللَّهِ ﷺ فِي يَدِي أَوْ فِي يَدِهِ قَالَ: «التَّسْبِيحُ نِصْفُ الْمِيزَانِ وَالْحَمْدُ لِلَّهِ يَمْلَؤُهُ وَالتَّكْبِيرُ يَمْلَأُ مَا بَيْنَ السَّمَاءِ وَالْأَرْضِ وَالصَّوْمُ نِصْفُ الصَّبْرِ وَالطُّهُورُ نِصْفُ الْإِيمَانِ» . رَوَاهُ التِّرْمِذِيُّ وَقَالَ هَذَا حَدِيثٌ حَسَنٌ &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic;&quot;&gt;(ضَعِيف)&lt;/span&gt;&lt;/h3&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662006064&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Le Prophète ﷺ ici a dénombré avec sa main (ou il a pris ma main) et a dit le تَسبِيح est la moitié de la balance et الحَمد remplit la balance, il y a deux manières de comprendre : le حَمد c&#x27;est le تَسبِيح, ou le حَمد remplit la deuxième moitié, ... déjà vu, le jeûne est la moitié du صَبر, pendant le jeûne, l&#x27;homme se préserve de ce qu&#x27;Allah a rendu حَلَال pendant un laps de temps, c&#x27;est un exercice de صَبر , pour qu&#x27;on puisse se préserver de ce qui est حَرَام tout le reste du temps (c&#x27;est la deuxième moitié du صَبر).&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Selon d&#x27;autre la patience a deux aspects ; intérieur (le jeûne) et extérieur.&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;et la pureté est la moitié de la foi.&lt;/span&gt;&lt;/p&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662092607&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/h3&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;span style=&quot; font-size:large; font-weight:600; color:#9b6a28;&quot;&gt;297&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic; color:#bb9a48;&quot;&gt;[17]&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; عَن عبد الله الصنَابحِي قَالَ: قَالَ رَسُولُ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسلم قَالَ: «إِذَا تَوَضَّأَ -[٩٨]- الْعَبْدُ الْمُؤْمِنُ فَمَضْمَضَ خَرَجَتِ الْخَطَايَا مِنْ فِيهِ وَإِذَا اسْتَنْثَرَ خَرَجَتِ الْخَطَايَا مِنْ أَنفه فَإِذَا غَسَلَ وَجْهَهُ خَرَجَتِ الْخَطَايَا مِنْ وَجْهِهِ حَتَّى تَخْرُجَ مِنْ تَحْتِ أَشْفَارِ عَيْنَيْهِ فَإِذَا غسل يَدَيْهِ خرجت الْخَطَايَا مِنْ تَحْتِ أَظْفَارِ يَدَيْهِ فَإِذَا مَسَحَ بِرَأْسِهِ خَرَجَتِ الْخَطَايَا مِنْ رَأْسِهِ حَتَّى تَخْرُجَ مِنْ أُذُنَيْهِ فَإِذَا غَسَلَ رِجْلَيْهِ خَرَجَتِ الْخَطَايَا مِنْ رِجْلَيْهِ حَتَّى تَخْرُجَ مِنْ تَحْتِ أَظْفَارِ رِجْلَيْهِ ثُمَّ كَانَ مَشْيُهُ إِلَى الْمَسْجِدِ وَصَلَاتُهُ نَافِلَةً لَهُ» . رَوَاهُ مَالك وَالنَّسَائِيّ &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic;&quot;&gt;(صَحِيح)&lt;/span&gt;&lt;/h3&gt;
# &lt;p align=&quot;justify&quot; style=&quot;-qt-paragraph-type:empty; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-size:large; font-weight:600; font-style:italic;&quot;&gt;&lt;br /&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662092726&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Lorqsue le serviteur fait ses ablutions, le serviteur ... le nez, les paupières, lorsqu&#x27;il lave sa tête tous les péchés de la tête et des oreilles sont pardonnés.&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Puis les prières qu&#x27;il fera à la mosquée aura des récompenses supplémentaires., selon une autre explication, lorsqu&#x27;on fait les ablutions les péchés commis par les membres lavés sont pardonnés et lorsqu&#x27;on fait la prière ce sont les autres péchés qui sont pardonnés.&lt;/span&gt;&lt;/p&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662092582&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/h3&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-size:large; font-weight:600; color:#9b6a28;&quot;&gt;298&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic; color:#bb9a48;&quot;&gt;[18]&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; وَعَنْ أَبِي هُرَيْرَةَ أَنَّ رَسُولَ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسلم أَتَى الْمَقْبَرَةَ فَقَالَ: «السَّلَامُ عَلَيْكُمْ دَارَ قَوْمٍ مُؤْمِنِينَ وَإِنَّا إِنْ شَاءَ اللَّهُ بِكُمْ لَاحِقُونَ وَدِدْتُ أَنَّا قَدْ رَأَيْنَا إِخْوَانَنَا قَالُوا أَوَلَسْنَا إِخْوَانَكَ يَا رَسُولَ اللَّهِ قَالَ أَنْتُمْ أَصْحَابِي وَإِخْوَانُنَا الَّذِينَ لَمْ يَأْتُوا بَعْدُ فَقَالُوا كَيْفَ تَعْرِفُ مَنْ لَمْ يَأْتِ بَعْدُ مِنْ أُمَّتِكَ يَا رَسُولَ اللَّهِ فَقَالَ أَرَأَيْتَ لَوْ أَنَّ رَجُلًا لَهُ خَيْلٌ غُرٌّ مُحَجَّلَةٌ بَيْنَ ظَهْرَيْ خَيْلٍ دُهْمٍ بُهْمٍ أَلَا يَعْرِفُ خَيْلَهُ قَالُوا بَلَى يَا رَسُولَ اللَّهِ قَالَ فَإِنَّهُمْ يَأْتُونَ غُرًّا مُحَجَّلِينَ مِنَ الْوُضُوءِ وَأَنَا فَرَطُهُمْ عَلَى الْحَوْض» . رَوَاهُ مُسلم &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic;&quot;&gt;(صَحِيح)&lt;/span&gt;&lt;/h3&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662350727&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Le Prophète ﷺ est venu au cimetière de بَقِيرَة il passa la salutation aux défunts. Lorsqu&#x27;on s&#x27;adresse directement aux défunts on les saluts, il y a اتِّفَاق sur le fait que le défunt l&#x27;entend. En dehors du سَلَام, est-ce que le défunt entend ou pas, il y a divergence, d&#x27;un côté عَائِشَة i dit que le mort n&#x27;entend pas alors de ابن عُمَر h dit que le mort n&#x27;entend pas. Le جَمع entre les deux est que le mort n&#x27;entend pas tout mais seulement quelques paroles.&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;La formule de salutation est la même que pour les vivants ; السَّلَام عَلَيكُم.&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Si Dieu le veut nous vous rejoindrons, pourquoi avoir dit ان شَاء الله : &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; بَرُّك بِئِسم الله&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; par habitude, à chaque fois qu&#x27;on parle de quelque chose du futur on rajouter ان شَاء الله&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; il est خَاص pour le lieu : nous vous rejoindrons dans ce cimetière de مَدِينَة&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;J&#x27;aurais aimé que nous puissions voir nos frères, ne sommes-nous pas tes frères O Messager d&#x27;Allah, il leur dit : Vous, vous êtes mes Compagnons [en plus d&#x27;être mes frères], mes frères sont ceux qui ne sont pas encore venu. Les Compagnons demandèrent comment vas-tu les reconnaitre ? &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Le Prophète dit : Si une personne a un cheval, le front avec une tâche blanche et les pieds avec des tâches blanches, s&#x27;il est au milieu d&#x27;un grand nombre de chevaux d&#x27;un noir profond, ne sera-t-il pas capable de reconnaître son cheval ? &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Ils dirent : Si &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Il dit : ... et je les devancerai et les accueillerait au Bassin. Ce اثَر sera réservé à la أُمَّة du Prophète ﷺ,&lt;/span&gt;&lt;/p&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot;-qt-paragraph-type:empty; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-family:&#x27;Microsoft Uighur&#x27;; font-size:large; font-weight:600;&quot;&gt;&lt;br /&gt;&lt;/h3&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-size:large; font-weight:600; color:#9b6a28;&quot;&gt;299&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic; color:#bb9a48;&quot;&gt;[19]&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; عَن أبي الدَّرْدَاء قَالَ: قَالَ رَسُولُ ﷺ: (أَنَا أَوَّلُ مَنْ يُؤْذَنُ لَهُ بِالسُّجُودِ يَوْمَ الْقِيَامَةِ وَأَنَا أَوَّلُ مَنْ يُؤْذَنُ لَهُ أَنْ يرفع رَأسه فَأنْظر إِلَى بَيْنَ يَدِي فَأَعْرِفُ أُمَّتِي مِنْ بَيْنِ الْأُمَمِ وَمِنْ خَلْفِي مِثْلُ ذَلِكَ وَعَنْ يَمِينِي مِثْلُ ذَلِك وَعَن شمَالي مثل ذَلِك &amp;quot;. فَقَالَ لَهُ رَجُلٌ: يَا رَسُولَ اللَّهِ كَيْفَ تَعْرِفُ أُمَّتَكَ مِنْ بَيْنِ الْأُمَمِ -[٩٩]- فِيمَا بَيْنَ نُوحٍ إِلَى أُمَّتِكَ؟ قَالَ: «هُمْ غُرٌّ مُحَجَّلُونَ مِنْ أَثَرِ الْوُضُوءِ لَيْسَ أَحَدٌ كَذَلِكَ غَيْرَهُمْ وَأَعْرِفُهُمْ أَنَّهُمْ يُؤْتونَ كتبهمْ بأيمانهم وأعرفهم يسْعَى بَين أَيْديهم ذُرِّيتهمْ» . رَوَاهُ أَحْمد &lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600; font-style:italic;&quot;&gt;(صَحِيح)&lt;/span&gt;&lt;span style=&quot; font-size:large; font-weight:600;&quot;&gt; &lt;/span&gt;&lt;img src=&quot;paragraph_time_1662351193&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/h3&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;&quot;&gt;&lt;img src=&quot;paragraph_time_1662351210&quot; width=&quot;0&quot; height=&quot;19&quot; /&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Je serai le premier à qui on donnera l&#x27;autorisation de se prosterner au Jour du Jugement, et le premier à qui ont donnera l&#x27;autorisation de relever la tête. Alors je verrai devant moi et je reconnaitrait ma أُمَّة d&#x27;entre les أُمَّة, derrière aussi ainsi qu&#x27;à ma droite et ma gauche, on lui demanda comment feras-tu pour reconnaître depuis نُوح (soit de par la longévité de نُوح ou parce qu&#x27;il était connu) jusqu&#x27;à maintenant ? &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Il dit : les traces des ablutions et par le fait qu&#x27;ils auront leur livre dans la main droite. Mais si on considère que tous les croyants auront leur livre dans la main droite : &lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; Car ils seront les premiers à avoir leur livre, car les autres n&#x27;auront pas encore leur livre&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; il est possible que le livre des membres de la أُمَّة soit quelque peu différent&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&amp;quot;&#x27;Microsoft Uighur&#x27;&amp;quot;; font-size:15pt; font-weight:600; color:#267dff;&quot;&gt;•&lt;/span&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt; a spécificité s&#x27;arrête aux traces des ablutions et le livre est général&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;On leur donnera leur livre de compte dans leur main droite et je reconnaitrait leur postérité (ceux qui sont morts avant la postérité et qui viendront intercéder pour leurs parents musulmans) qui sera devant eux.&lt;/span&gt;&lt;/p&gt;
# &lt;p align=&quot;justify&quot; style=&quot; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; line-height:100%;&quot;&gt;&lt;span style=&quot; font-family:&#x27;Microsoft Uighur&#x27;;&quot;&gt;Le livre des croyants sera remis dans la main droite et celui des non croyants dans la main gauche, il semblerait que pour les hypocrites ils auront leur livre de compte dans la main droite&lt;/span&gt;&lt;/p&gt;
# &lt;h3 align=&quot;justify&quot; style=&quot;-qt-paragraph-type:empty; margin-top:14px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-size:large; font-weight:600;&quot;&gt;&lt;br /&gt;&lt;/h3&gt;&lt;/body&gt;&lt;/html&gt;''')
# HTML.feed(t)
# print(HTML.paragraphs)