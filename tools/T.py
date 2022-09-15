# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import re
from symspellpy import SymSpell, Verbosity
from string import ascii_letters, digits, whitespace
from html.parser import HTMLParser

from PyQt5.QtCore import QRunnable, pyqtSignal, QObject
from tools import G, S


class Regex:
    src_audio_path = re.compile(r'^.*?src="audio_record_(.*?)".*?$')
    paragraph_time = re.compile(r'src="paragraph_time_(.*?)"')
    highlight_split = re.compile(r'[ \-\.\,:;!?\"\'\(\)\[\]]')
    re_ignoretoken = r'\d|^[A-Z]|ﷺ|ﷻ'


def buildCharMap(*characters):
    return {ord(key): key for key in characters}


class Keys:
    phrase_characters = '.!?'
    word_characters = '(),:; "_[]' + phrase_characters
    quote_characters = '(\'"'

    NewPhrase = buildCharMap(*phrase_characters)
    NewWord = buildCharMap(*word_characters)
    Quotes = buildCharMap(*quote_characters)

    Exits = {60: "[", 62: "]", **Quotes, **NewWord}

    Latin_Letters = ascii_letters + 'éèêëàâäçîïôöûùü'


class SpellChecker(QObject):
    dictionnary: SymSpell
    finished = pyqtSignal()

    class Worker(QRunnable):
        def __init__(self, callback_fn):
            super().__init__()
            self.callback_fn = callback_fn

        def run(self) -> None:
            dict_path = G.appdata_path("dict.txt")
            sympell = SymSpell(max_dictionary_edit_distance=2, prefix_length=5)
            sympell.load_dictionary(dict_path, term_index=0, count_index=1, encoding="utf8", separator="\t")

            self.callback_fn(sympell)

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

    def lookup(self, *args, **kwargs):
        kwargs.update({'ignore_token': Regex.re_ignoretoken})
        return self.dictionary.lookup(*args, **kwargs)

    def word_check(self, word: str):
        suggestions = self.lookup(word, max_edit_distance=2, verbosity=Verbosity.TOP,
                                  include_unknown=False, transfer_casing=False)

        # abort if word's already in the dictionary
        return suggestions[0].term != word

    def block_check(self, text: str):
        for word in Regex.highlight_split.split(text):
            if not self.word_check(word):
                return False


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

        def __init__(self, pos=0):
            self.id = pos
            self._content = []
            self.tags = {}

        def addContent(self, obj: object):
            self._content.append(obj)

        def __iadd__(self, other):
            self.addContent(other)

    class SPAN(TAG):
        tag = 'span'

        def __init__(self):
            self._content = ''
            self.tags = {}

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
        if tag == 'p':
            self.counter += 1
            p = self.P(self.counter)

            for key, tag in attrs:
                p.tags[key] = tag

            self.wip_object = p

            self.paragraphs.append(p)

        elif tag == 'span':
            p = self.paragraphs[-1]

            span = self.SPAN()
            self.wip_object = span

            p.addContent(span)

            for key, tag in attrs:
                span.tags[key] = tag

    def handle_endtag(self, tag):
        p = self.paragraphs[-1]
        if tag == 'span':
            self.wip_object = p

    def handle_data(self, data):
        self.wip_object += data

    def build(self):
        return self.paragraphs[-4]

    def hasParagraphTime(self, block: str) -> bool:
        return 'src="paragraph_time_' in block

    def paragraphTime(self, block: str) -> int:
        times = Regex.paragraph_time.findall(block)
        return int(times[0])

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


if __name__ == "__main__":
    text = '''Ce Coran est une révélation (ou Il l'a fait descendre) du Seigneur des Mondes, est descendu avec l'Esprit Fidèle (Jibril ￼) Il l'a fait descendre sur ton coeur afin que tu sois du nombre des avertisseurs [auprès de ta communauté] en une langue arabe claire. Le Coran (ou la mention du Prophète ﷺ  ou la mention de la religion de l'islam) figure dans les livres (زُبُر) des premiers anciens (la Torah, le انجِيل et les autres livres célestes) N'est pas un signe pour les détracteurs que le fait que les érudits des بَنُ اسرَائِيل le (il y a différents avis sur ce ضَمِير : les propos du Coran, le Prophète) connaissent et si nous l'avions fait descendre sur quelques non arabe et qu'il leur aurait récité il n'y croiraient pas car ça a été révélé en notre langue. Et iil n'y croiront pas aoir d'avoir le châtiment douloureux.

Ainsi nous l'avons fait entrer dans les coeurs des criminels

19/05
20/05
une fourmi avait avert lorsque Soulayman ￼ avait voulu traverser : elle aussi a un soucis pour ses semblables. 
Soulayman a entendu une fourmi 
C'est une sourate مَكِّيَّة
Voici les versets d'un Livre explicite (le Coran) un guide [vers le paradis] et une bonne annonce [de récompense] pour les croyants, ceux ...
Ceux qui ne croient pas en l'au-delà, nous embellissons à leurs yeux leurs actions, ils pensent être dans le bien, la condition qui valide les actes de biens c'est la foi, certains font de mauvaises actions et se croient être dans le bien. Et ils se montreront hésitants [dans ce monde], Allah nous montre que sans la foi, même si certaines sont reconnues comme étant de bonnes actions'''
    print(TEXT.split(text))
