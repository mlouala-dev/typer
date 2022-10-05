# بسم الله الرحمان الرحيم
"""
The styles applied in the app
"""
from PyQt6.QtGui import QTextBlockFormat, QTextCharFormat, QFont, QTextCursor, QTextBlock, QBrush, QColor
from PyQt6.QtCore import Qt

from tools import G, T


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

        T.QOperator.ApplyDefault.BlockFormat(block)

        f = textchar.font()
        f.setPointSizeF(G.get_font().pointSizeF())
        f.setItalic(False)
        f.setBold(False)
        # f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        textchar.setFont(f)
        textchar.setFontPointSize(f.pointSize())
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


class Header(TyperStyle):
    """
    The Alt+1 style
    """
    id = 1
    children = ['Title', 'SubTitle']

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setFontPointSize(21.0)


class Title(TyperStyle):
    """
    The Alt+2 style
    """
    id = 2
    children = ['Subtitle']

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignLeft)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(True)
        f.setUnderline(False)

        textchar.setFont(f)
        textchar.setFontPointSize(19.0)


class Subtitle(TyperStyle):
    """
    The Alt+3 style
    """
    id = 3

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignLeft)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setFontPointSize(17.0)


class SuratAR(TyperStyle):
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


class KitabAR(SuratAR):
    id = 981
    children = ['BabAR', 'HadithAR']
    pass


class BabAR(SuratAR):
    id = 982
    children = ['HadithAR']

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        super(BabAR, self).apply(block, textchar)
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        block.setLineHeight(90.0, 1)

        f = textchar.font()
        f.setBold(True)
        f.setItalic(False)
        f.setUnderline(False)
        textchar.setFont(f)
        textchar.setForeground(QBrush(QColor(115, 195, 255)))
        textchar.setFontPointSize(30.0)


class HadithAR(TyperStyle):
    id = 983

    def apply(self, block: QTextBlockFormat, textchar: QTextCharFormat):
        block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        f = textchar.font()
        f.setBold(False)
        f.setItalic(False)
        f.setUnderline(False)
        default = QTextCharFormat()
        textchar.setFont(f)
        textchar.setForeground(default.foreground())
        textchar.setFontPointSize(21.0)


class SuratFR(TyperStyle):
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


class SuratOrnament(TyperStyle):
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


class Ayat(TyperStyle):
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


class Styles:
    Default = TyperStyle()
    Header = Header()
    Title = Title()
    Subtitle = Subtitle()
    SuratAR = SuratAR()
    SuratFR = SuratFR()
    SuratOrnament = SuratOrnament()
    Ayat = Ayat()
    Kitab = KitabAR()
    Bab = BabAR()
    Hadith = HadithAR()


# the keyboard's shortcut connections
Styles_Shortcut = {
    Qt.Key.Key_twosuperior: Styles.Default,
    Qt.Key.Key_Ampersand: Styles.Header,
    Qt.Key.Key_Eacute: Styles.Title,
    Qt.Key.Key_QuoteDbl: Styles.Subtitle,
    39: Styles.Ayat
}
