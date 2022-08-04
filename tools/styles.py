# بسم الله الرحمان الرحيم
"""
The styles applied in the app
"""
from PyQt5.QtGui import QTextBlockFormat, QTextCharFormat, QFont, QTextCursor, QTextBlock, QBrush, QColor
from PyQt5.QtCore import Qt

from tools import G


class TyperStyle:
    """
    The source style
    """
    # uniqid
    id = 0
    children = []

    def applyStyle(self, *args):
        """
        Will be called from the app itself and QLineEdit to apply styles no matters how we call it
        :param args: can be : (blockFormat, charFormat) or (textCursor) or (textBlock)
        """
        # we'll forward to the subclass "apply" function
        if len(args) == 1:
            tc = args[0]
            if isinstance(tc, QTextCursor):
                self.apply(tc.blockFormat(), tc.blockCharFormat())

            elif isinstance(tc, QTextBlock):
                self.apply(tc.blockFormat(), tc.charFormat())

        # if there is two args, we guess the user provided (QBlockFormat, QCharFormat)
        elif len(args) == 2:
            self.apply(*args)

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        """
        Subclassed to apply a custom style to the selection, cursor etc...
        :param block: the text block format
        :param textchar: the text character format
        """
        block: QTextBlockFormat
        textchar: QTextCharFormat

        block.setAlignment(Qt.AlignJustify)
        block.setTextIndent(10)
        block.setLineHeight(100.0, 1)
        block.setBottomMargin(10)
        block.setLeftMargin(10)
        block.setRightMargin(10)

        f = textchar.font()
        f.setPointSizeF(G.get_font(1.2).pointSizeF())
        f.setItalic(False)
        f.setBold(False)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        textchar.setFont(f)

    def matching_props(self, block: QTextBlock) -> bool:
        """
        Checks if the block's match the current one
        :param block: a QTextBlock to compare
        :return:
        """
        return self.id == block.userState()

    def __eq__(self, other):
        """
        the (==) implementation
        """
        return self.matching_props(other)


class HeaderStyle(TyperStyle):
    """
    The Alt+1 style
    """
    id = 1
    children = ['TitleStyle', 'SubTitleStyle']

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignCenter)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setFontPointSize(21.0)


class TitleStyle(TyperStyle):
    """
    The Alt+2 style
    """
    id = 2
    children = ['SubTitleStyle']

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignLeft)
        block.setLineHeight(100.0, 1)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(True)
        f.setUnderline(False)

        textchar.setFont(f)
        textchar.setFontPointSize(19.0)


class SubTitleStyle(TyperStyle):
    """
    The Alt+3 style
    """
    id = 3

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignLeft)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setFontPointSize(17.0)


class SuratStyleAR(TyperStyle):
    """
    The Surat paragraph
    """
    id = 98

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        block.setLeftMargin(30)
        block.setRightMargin(30)
        block.setIndent(0)
        block.setTextIndent(0)

        block.setLineHeight(80.0, 1)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setForeground(QBrush(QColor(38, 125, 255)))
        textchar.setFontPointSize(40.0)


class SuratStyleFR(TyperStyle):
    """
    The Surat FR paragraph
    """
    id = 97

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        block.setLeftMargin(30)
        block.setRightMargin(30)

        block.setLineHeight(0.0, 1)
        block.setIndent(0)
        block.setTextIndent(0)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setForeground(QBrush(QColor(38, 125, 255)))
        textchar.setFontPointSize(30.0)


class SuratStyleOrnament(TyperStyle):
    """
    The Surat decoration paragraph
    """
    id = 96

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        block.setLeftMargin(30)
        block.setRightMargin(30)

        block.setLineHeight(60.0, 1)
        block.setIndent(0)
        block.setTextIndent(0)


class AyatStyle(TyperStyle):
    """
    The Ayat paragraph
    """
    id = 99

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        block.setLineHeight(87.0, 1)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setForeground(QBrush(QColor(38, 125, 255)))
        textchar.setFontPointSize(17.0)


Styles = {
    "default": TyperStyle(),
    "header": HeaderStyle(),
    "title": TitleStyle(),
    "subtitle": SubTitleStyle(),
    "surat_ar": SuratStyleAR(),
    "surat_fr": SuratStyleFR(),
    "surat_ornament": SuratStyleOrnament(),
    "ayat": AyatStyle()
}

# the keyboard's shortcut connections
Styles_Shortcut = {
    Qt.Key_twosuperior: Styles['default'],
    Qt.Key_Ampersand: Styles['header'],
    Qt.Key_Eacute: Styles['title'],
    Qt.Key_QuoteDbl: Styles['subtitle'],
    39: Styles['ayat']
}
