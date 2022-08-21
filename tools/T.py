# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import re
from html.parser import HTMLParser
from PyQt5.QtGui import QTextCursor


class HTML(HTMLParser):
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
            p = HTML.P(self.counter)

            for key, tag in attrs:
                p.tags[key] = tag

            self.wip_object = p

            self.paragraphs.append(p)

        elif tag == 'span':
            p = self.paragraphs[-1]

            span = HTML.SPAN()
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
            html = t.split('<body>')[1].replace('<!--StartFragment-->', '').split('<!--EndFragment-->')[0]

        return html


class Keys:
    NewPhrase = {
        46: '.', 33: '!', 63: '?'
    }
    NewWord = {
        40: '(', 41: ')', 44: ',', 58: ':', 59: ';', 45: '-', 32: ' ', 34: '"', **NewPhrase
    }

    Quotes = {
        40: '(', 39: "'", 34: '"'
    }

    Exits = {60: "[", 62: "]", **NewWord, **Quotes}


class TEXT:
    """
    Core operations over TEXT
    """
    re_exit_keys = re.compile(r'[' + ''.join(Keys.Exits.values()) + r']')

    def word_split(self, text):
        words = self.re_exit_keys.split(text)
        return words


if __name__ == "__main__":
    parser = HTML()
    parser.feed('''<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p align="center" dir='rtl' style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; line-height:87%;"><img src="./rsc/ayat_separator_LD.png" /></p>
<p align="center" dir='rtl' style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; -qt-user-state:99; line-height:87%;"><span style=" font-family:'Microsoft Uighur'; font-size:17pt; font-weight:600; color:#267dff;">﴿ وَمِنْهُم مَّن يَقُولُ ائْذَن لِّي وَلَا تَفْتِنِّي ۚ أَلَا فِي الْفِتْنَةِ سَقَطُوا ۗ وَإِنَّ جَهَنَّمَ لَمُحِيطَةٌ بِالْكَافِرِينَ </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt;">﴾</span></p>
<p align="center" dir='rtl' style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; -qt-user-state:99; line-height:87%;"><span style=" font-family:'Microsoft Uighur'; font-size:17pt;">(التوبة ٩‎:٤٩)</span></p>
<p align="center" dir='rtl' style="-qt-paragraph-type:empty; margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; line-height:87%; font-family:'Microsoft Uighur'; font-size:17pt;"><br /></p>
<p style=" margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;"><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; color:#267dff;">Parmi eux il y a qui disaient : </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; font-style:italic; color:#267dff;">&quot;Autorise moi </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt;">[à ne pas participer aux expéditions]</span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; font-style:italic; color:#267dff;"> et ne me jette pas dans la tentation&quot;</span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; color:#267dff;">.</span></p>
<p align="justify" style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-family:'Microsoft Uighur'; font-size:17pt; font-weight:600;"><br /></p>
<p align="justify" style=" margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;"><span style=" font-family:'Microsoft Uighur'; font-size:17pt; font-weight:600;">Cause de révélation : </span></p>
<p align="justify" style=" margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:1; text-indent:10px; -qt-user-state:0; line-height:100%;"><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt;">الجَدّ بن قَيس a dit : </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-style:italic;">&quot;Autorise moi </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt;">[à ne pas participer] </span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-style:italic;">et ne me jette pas dans la tentation&quot;</span><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt;">. L'objet de sa tentation selon certains serait les بَنَات des بَنُو اصفَر ; les filles des byzantins, il a invoqué comme excuse d'être trop attaché aux femmes.</span></p>
<p align="justify" style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-family:'Microsoft Uighur'; font-size:14.4pt;"><br /></p>
<p align="justify" style=" margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%;"><span style=" font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; color:#267dff;">En faisant cela, il est déjà tombé dans la tentation, et l'enfer cernera les infidèles.</span></p>
<p align="justify" style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:10px; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; line-height:100%; font-family:'Microsoft Uighur'; font-size:14.4pt; font-weight:600; color:#267dff;"><br /><!--EndFragment--></p></body></html>''')
    print(parser.build())
