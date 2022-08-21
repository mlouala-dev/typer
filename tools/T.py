# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
NOT IMPLEMENTED YET
"""
import re
from PyQt5.QtGui import QTextCursor


class HTML:
    css = r"[\w\d;: \-_'#.]"
    clean_font_family = re.compile(f"(<span style=\"{css}*?)( ?font-family:'.*?';)({css}*\">)")
    clean_font_size = re.compile(f"(<span style=\"{css}*?)( ?font-size:[\d.\w]+;)({css}*\">)")
    clean_b = re.compile(r"<span style=\" ?font-weight:600;\">(.*?)</span>")
    clean_i = re.compile(r"<span style=\" ?font-style:italic;\">(.*?)</span>")
    clean_empty_span = re.compile(r"<span style=\" *?\">(.*?)</span>")

    clean_empty_line = re.compile(r"^<p style=\".*?><br /></p>$", re.MULTILINE)

    clean_p = re.compile(r"^<p.*?>(.*?)(</p>)?$", re.MULTILINE)

    block_checker = {
        'h1': {'needle': 'xx-large'},
        'h2': {'needle': 'x-large'},
        'h3': {'needle': 'large'},
    }

    for tag in block_checker:
        block_checker[tag]['check'] = re.compile(f"^<span style=\"{css}*?font-size:" + block_checker[tag]['needle'] + f";{css}*?font-weight:600;{css}*?\">")
        block_checker[tag]['clean'] = re.compile(f" font-size:" + block_checker[tag]['needle'] + f"; font-weight:600;")

    def cleanCssStyle(self, text: str):
        text = self.clean_font_family.sub(r'\1\3', text)
        text = self.clean_font_size.sub(r'\1\3', text)
        text = self.clean_b.sub(r'<b>\1</b>', text)
        text = self.clean_i.sub(r'<i>\1</i>', text)
        text = self.clean_empty_span.sub(r'\1', text)

        return text

    def applyBlockTag(self, textCursor: QTextCursor, tag: str):
        textCursor.beginEditBlock()
        block = self.cleanCssStyle(self.getHtmlBlock(textCursor))

        apply = True
        for block_tag in self.block_checker:
            if len(self.block_checker[tag]['check'].findall(block)):
                block = self.block_checker[tag]['clean'].sub('', block)
                block = self.clean_empty_span.sub(r'\1', block)
                if block_tag == tag:
                    apply = False

        if apply:
            block = f'<{tag}>{block}</{tag}>'

        num = textCursor.blockNumber()
        textCursor.removeSelectedText()

        if num != 0:
            textCursor.insertBlock()

        textCursor.insertHtml(block)
        textCursor.endEditBlock()

    def getHtmlBlock(self, textCursor: QTextCursor):
        textCursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        block = textCursor.selection().toHtml()

        block = self.clean_empty_line.sub('', block)

        # remove the triming <p> tag
        block = self.clean_p.sub(r'\1', block)

        # avoiding a bug in Qt Html selection for Block under cursor, it returns this block and an empty one
        return self.extractTextFragment(block)

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
    re_exit_keys = re.compile(r'[' + ''.join(Keys.Exits.values()) + r']')

    def word_split(self, text):
        words = self.re_exit_keys.split(text)
        return words
