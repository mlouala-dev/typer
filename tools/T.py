# بسم الله الرحمان الرحيم
"""
Some handful text operations especially on HTML code
"""
import re
from PyQt5.QtGui import QTextCursor


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


def cleanCssStyle(text: str):
    text = clean_font_family.sub(r'\1\3', text)
    text = clean_font_size.sub(r'\1\3', text)
    text = clean_b.sub(r'<b>\1</b>', text)
    text = clean_i.sub(r'<i>\1</i>', text)
    text = clean_empty_span.sub(r'\1', text)

    return text


def applyBlockTag(textCursor: QTextCursor, tag: str):
    textCursor.beginEditBlock()
    block = cleanCssStyle(getHtmlBlock(textCursor))

    apply = True
    for block_tag in block_checker:
        if len(block_checker[tag]['check'].findall(block)):
            block = block_checker[tag]['clean'].sub('', block)
            block = clean_empty_span.sub(r'\1', block)
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


def getHtmlBlock(textCursor: QTextCursor):
    textCursor.select(QTextCursor.SelectionType.BlockUnderCursor)
    block = textCursor.selection().toHtml()

    block = clean_empty_line.sub('', block)

    # remove the triming <p> tag
    block = clean_p.sub(r'\1', block)

    # avoiding a bug in Qt Html selection for Block under cursor, it returns this block and an empty one
    return extractTextFragment(block)


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
