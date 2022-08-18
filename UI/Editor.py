# بسم الله الرحمان الرحيم
import re
import string
import os
import sqlite3
from time import time
from functools import partial
from symspellpy import SymSpell, Verbosity

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from UI import QuranWorker
from UI.Modules import Conjugate, Jumper
from tools.styles import Styles, Styles_Shortcut, TyperStyle
from tools import G, translitteration, S


class Typer(QTextEdit):
    """
    The main widget after the window, this is the one which display what used is typing, providing some
    interfacing with the other tools like right click menus & shortcuts
    """
    symspell: SymSpell
    _win: QMainWindow

    symspell = None
    auto_complete = False
    auto_complete_available = True
    default_font = G.get_font(1.2)

    # used to automatically superscript some patterns
    re_numbering = re.compile(r'((1)(ers?|ères?))|((\d+)([èe]mes?))')
    re_textblock = re.compile(r'(.*?>)( +)?[-\u2022]?(<span.*?>\d\)</span>)?( +)?([\w\d]+)(.*?)<', flags=re.IGNORECASE)
    re_ignoretoken = r'\d|^[A-Z]|ﷺ|ﷻ'

    contentChanged = pyqtSignal()
    contentEdited = pyqtSignal()

    def __init__(self, parent=None):
        super(Typer, self).__init__(parent)
        self._win = parent

        # preparing the Conjugate dialog
        self.dictionary = sqlite3.connect(G.rsc_path("lang.db"))
        self.cursor = self.dictionary.cursor()
        self.conjugateDialog = Conjugate(self._win, self.dictionary)

        # will expand since the others have fixed widths
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # autocomplete label
        self.auto_complete_label = QLabel(self)
        self.auto_complete_label.hide()
        self.auto_complete_label.setFont(G.get_font(1.2))
        self.auto_complete_label.setStyleSheet("""
        QLabel {
            color: #2a82da;
            background-color: rgba(65, 59, 69, 230);
            padding-left:0;
            padding-right:3px;
            padding-top:1px;
            padding-bottom:1px;
            border-left:0;
            border-right:1px solid #333;
            border-top:1px solid #333;
            border-bottom:1px solid #333;
            border-top-left-radius:0;
            border-top-right-radius:3px;
            border-bottom-left-radius:0;
            border-bottom-right-radius:3px;
        }
        """)
        graph = QGraphicsOpacityEffect(self)
        graph.setOpacity(0.9)
        self.auto_complete_label.setGraphicsEffect(graph)

        # we should never need a horizontal scrollbar since the text is wrapped
        self.horizontalScrollBar().setDisabled(True)
        self.horizontalScrollBar().hide()

        # this is the current word
        self._word = ''
        # we measure time spent to type a word
        self.word_time = time()

        self.new_word = True

        self.translitteration_bound = None
        self.translitterate_mode = False

        self.default_blockFormat = QTextBlockFormat()
        self.default_blockFormat.setAlignment(Qt.AlignJustify)
        self.default_blockFormat.setTextIndent(10)
        self.default_blockFormat.setLineHeight(100.0, 1)
        self.default_blockFormat.setBottomMargin(10)
        self.default_blockFormat.setLeftMargin(10)
        self.default_blockFormat.setRightMargin(10)

        self.default_textFormat = QTextCharFormat()
        self.default_font.setPointSizeF(self.default_font.pointSizeF())
        self.default_font.setItalic(False)
        self.default_font.setBold(False)
        self.default_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.default_textFormat.setFont(self.default_font)
        self.default_textFormat.setProperty(8167, [G.__font__])

        self.setCurrentCharFormat(self.default_textFormat)
        self.setFont(self.default_font)
        self.setCurrentFont(self.default_font)
        self.document().setDefaultFont(self.default_font)
        self.document().setIndentWidth(25)
        self.toggleFormat()
        self.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignLeft))
        self.document().blockCountChanged.connect(self.contentChanged.emit)

        # applying a simple syntax highlighter
        self.syntaxhighlighter = TyperHighlighter(self, self.document())

    @property
    def word(self):
        return self._word

    @word.setter
    def word(self, value):
        """
        when word attr is set
        """
        # if this is a new word we update the time
        if not len(value):
            self.word_time = time()
            self.new_word = False

        self._word = value

    def mousePressEvent(self, e: QMouseEvent) -> None:
        """
        When mouse is pressed we check what word we have and what we can do
        """

        modifiers = QApplication.keyboardModifiers()

        # if alt modifier is on we directly display the word corrections
        if modifiers == Qt.KeyboardModifier.AltModifier:
            c = self.cursorForPosition(e.pos())
            c.select(QTextCursor.WordUnderCursor)
            text = c.selectedText()

            solution_menu = QMenu(f'Suggestions for {text}', self)

            # appending all the suggestions for the given word
            self.buildSpellMenu(text, c, solution_menu)

            solution_menu.exec_(self.mapToGlobal(e.pos()))

        # otherwise we pop the classic popupmenu
        else:
            super(Typer, self).mousePressEvent(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """
        The main function, handle every thing when a letter is typed
        """
        tc: QTextCursor

        # getting the next character
        tc = self.textCursor()
        tc.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        # we check if next character exists to prevent useless autocompletion display
        next_character = tc.selectedText()

        # getting the current word
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        self.word = tc.selectedText()

        # ARABIC GLYPHS #
        # TODO: update with the ThanaaWaMadh font
        lowered_text = tc.selectedText().lower()
        if lowered_text in ("sws", "saws", "jj", "aas", "ra", 'raha', 'rahuma', 'rahum'):
            # a glyph for Salla Allahu 'alayhi wa sallam
            if lowered_text in ("sws", "saws"):
                tc.insertText("ﷺ")

            # a glyph for Jalla Jalaaluhu
            elif lowered_text == "jj":
                tc.insertText("ﷻ")

            # for the other case we need images... until we implement the ThanaaWaMadh font
            elif lowered_text in ("aas", "ra", 'raha', 'rahuma', 'rahum') and e.key() in G.new_word_keys:
                # getting the image ressource path
                path = G.rsc_path(f'{lowered_text}_LD.png')

                # adding it as a HTML image
                tc.insertHtml(f"<img src='{path}'>")

            # setting word to null
            self.word = ""

        # if it matches our regex for 1st 1er 2nd 34eme etc
        is_number = self.re_numbering.match(self.word)

        # if the user corrected the ى manually, we update the text database
        if e.text() == "ى" and (next_character in G.new_word_keys.values() or len(next_character) == 0):
            translitteration.append_to_dict(self.word + "ى")

        # it make the 'st' 'er' to superscript
        elif is_number and e.key() in G.new_word_keys:
            # getting the groups from the regex match
            num = int(is_number.groups()[1] or is_number.groups()[4])
            sup = is_number.groups()[2] or is_number.groups()[5]

            # and insert the next char to force the <sup> tag to be closed
            tc.insertHtml(f"{num}<sup>{sup}</sup><span>{e.text()}</span>")

            # since we added the current char, no need to continue
            return

        # Quote text
        elif e.key() in G.quotes_keys and len(self.textCursor().selectedText()):
            self.quoteText(e.text())
            return

        # brackets override, this mean that < and > will become [ and ] useful when typing a translation
        # and need to insert a translation note
        elif e.key() in [60, 62]:   # 60 is < and 62 >

            # the replacement pattern
            eq = {60: "[", 62: "]"}
            # if there is a selection, we apply quote to it
            if len(self.textCursor().selectedText()):
                self.quoteText("[")

            # otherwise we just override the < and >
            else:
                self.textCursor().insertText(eq[e.key()])

            # since we added what we want from this event, abort
            return

        # if we're not typing translitteration and we are at the end of the document
        elif not self.translitterate_mode and (len(next_character) == 0 or next_character == '\u2029'):
            if len(self.word):

                # if we start a new word
                if e.key() in G.new_word_keys:
                    # we measure the time it took to type the previous word and applies an automatic
                    # correction if ratio is under a given value
                    ratio = (time() - self.word_time) / len(self.word)

                    # needs to be implemented in settings and should be customizable by user
                    if ratio <= 0.15 and not self.word[0].isupper():
                        # applies an automatic spell correction, the ignore token to be sure we don't try
                        # to correct the digits, proper names or glyphs
                        suggestions = self.symspell.lookup(self.word, ignore_token=self.re_ignoretoken,
                                                           max_edit_distance=1, verbosity=Verbosity.TOP,
                                                           include_unknown=True, transfer_casing=True)

                        # this is the first and closest correction
                        correction = suggestions[0].term

                        # automatically replace it if correction is different
                        if tc.selectedText() != correction:
                            tc.insertText(correction)

                    # replacing the cursor
                    tc_prev = self.textCursor()
                    tc_prev.movePosition(QTextCursor.MoveOperation.PreviousWord, QTextCursor.MoveMode.KeepAnchor, 2)
                    tc_prev.select(tc.SelectionType.WordUnderCursor)

                    self.new_word = True

        modifiers = QApplication.keyboardModifiers()

        # resetting timing if backspace pressed for more accurate ratio
        if e.key() == Qt.Key.Key_Backspace:
            self.word_time = time()

        # this means we enter the translitterate mode, this is equivalent to type on Alt+Gr
        # TODO: find another less annoying shortcut, should be customizable by the user
        if e.key() == Qt.Key.Key_Alt and modifiers == Qt.KeyboardModifier.ControlModifier:
            tc = self.textCursor()

            # selection has length
            if tc.position() != tc.anchor():
                txt = tc.selectedText()
                tc.removeSelectedText()

                # then we directly translitterate it
                tc.insertText(translitteration.translitterate(txt))

            # if there is no selection
            else:
                # revert state
                self.translitterate_mode = not self.translitterate_mode

                if self.translitterate_mode:
                    # recording the current position for upcoming translitteration
                    self.translitteration_bound = tc.position()

                    # adding a special character to indicate we're in translitteration mode
                    # TODO: we could indicate differently, maybe with a border, or a text color ?
                    self.insertHtml(u"<span style='font-weight:bold;'>\u262a</span>")

                # otherwise we just add a character to force the style to return to format
                else:
                    self.insertHtml("<span style='font-weight:normal;'>'</span>")

                    # selecting all the text, from the first special character to the end
                    tc.setPosition(tc.position(), tc.MoveMode.MoveAnchor)
                    tc.movePosition(tc.MoveOperation.Left, tc.MoveMode.KeepAnchor,
                                    tc.position() - self.translitteration_bound)
                    txt = tc.selectedText()[1:-1]

                    tc.removeSelectedText()

                    # translitterate what's between the head and tail characters
                    tc.insertText(translitteration.translitterate(txt))

        # can't remember the purpose of this statement
        if modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            self.insertPlainText(e.text().lower())
            return

        # handling some special shortcuts
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):

            # to copy the HTML code of the selection
            if e.key() == Qt.Key.Key_C:
                tc = self.textCursor()
                QApplication.clipboard().setText(tc.selection().toHtml())

            # to paste the clipboard as HTML
            elif e.key() == Qt.Key.Key_V:
                self.insertHtml(QApplication.clipboard().text())
                self.contentChanged.emit()

            # to cut HTML code
            elif e.key() == Qt.Key.Key_X:
                tc = self.textCursor()
                QApplication.clipboard().setText(tc.selection().toHtml())
                tc.removeSelectedText()
                self.contentChanged.emit()

            # insert a force RTL character
            elif e.key() == Qt.Key.Key_E:
                self.insertHtml('&#x200e;')

            # otherwise we just consider it a normal command
            else:
                super(Typer, self).keyPressEvent(e)

        # the alt modifier is used to apply some fast styles
        elif modifiers == Qt.KeyboardModifier.AltModifier:

            # the main title shortcut
            if e.key() in Styles_Shortcut:  # Alt+1

                # apply the style to the whold text block
                self.applyOverallBlock(partial(self.toggleFormat, Styles_Shortcut[e.key()]))

                # and update parent's widget(s)
                self.contentChanged.emit()

            # unindent the text block
            elif e.key() == Qt.Key.Key_Left:
                self.applyOverallBlock(partial(self.offsetIndent, -1))

            # indent the text block
            elif e.key() == Qt.Key.Key_Right:
                self.applyOverallBlock(partial(self.offsetIndent, 1))

            # moving cursor to the previous text block
            elif e.key() == Qt.Key.Key_Up:
                tc.movePosition(tc.MoveOperation.PreviousBlock, tc.MoveMode.MoveAnchor)
                self.setTextCursor(tc)

            # moving cursor to the next text block
            elif e.key() == Qt.Key.Key_Down:
                tc.movePosition(tc.MoveOperation.NextBlock, tc.MoveMode.MoveAnchor)
                self.setTextCursor(tc)

            # add numerotation
            # TODO: could be largely improved, customized numerotation, automatic determination of sub numering, etc
            elif e.key() == Qt.Key.Key_N:
                tc = self.textCursor()

                # we get the current selection as html
                html = self.extractTextFragment(tc.selection().toHtml(), wide=True)

                res, cnt = '', 0
                # every line patching pattern
                for line in html.split('\n'):
                    line_res = self.re_textblock.sub(fr'\1\2 <span style=" font-family:\'{G.__font__}\'; font-size:15pt; font-weight:600; color:#267dff;">{cnt})</span> \5\6<', line, count=1)
                    res += line_res
                    # ignoring the empty paragraphs
                    if '-qt-paragraph-type:empty;' not in line:
                        cnt += 1

                # updating the selection
                tc.insertHtml(res)

                # since we're done with change, leaving
                return

            # add bullets
            elif e.key() == Qt.Key.Key_B:
                tc = self.textCursor()

                # getting the current selection as html
                html = self.extractTextFragment(tc.selection().toHtml(), wide=True)

                res = ''
                for line in html.split('\n'):
                    line_res = self.re_textblock.sub(fr'\1\2 <span style=" font-family:\'{G.__font__}\'; font-size:15pt; font-weight:600; color:#267dff;">%s</span> \5\6<' % u'\u2022', line, count=1)
                    res += line_res

                tc.insertHtml(res)
                return

            # if we call some of the existing shortcuts... forward to parent
            # TODO: dynamically load the existing shortcuts
            elif e.key() in (Qt.Key.Key_H, Qt.Key.Key_V, Qt.Key.Key_R,
                             Qt.Key.Key_F, Qt.Key.Key_C, Qt.Key.Key_G,
                             Qt.Key.Key_A, Qt.Key.Key_E, Qt.Key.Key_S):
                super(self._win.__class__, self._win).keyPressEvent(e)

            else:
                super(Typer, self).keyPressEvent(e)

        # same for Control modifier... forward to parent
        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() in (Qt.Key.Key_G, Qt.Key.Key_S):
            super(self._win.__class__, self._win).keyPressEvent(e)

        # some style to apply
        # TODO: need to be stored in external library / user defined
        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_B:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold)    # bold

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_Q:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold, QColor(22, 155, 76))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_W:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold, QColor(38, 125, 255))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_D:
            self.applyStyle(None, None, QColor(68, 156, 205))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_I:
            self.applyStyle(lambda x: x.italic(), lambda y: y.setItalic)    # italic

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_U:
            self.applyStyle(lambda x: x.underline(), lambda y: y.setUnderline)  # underline

        elif modifiers == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_H:
            # inserts a custom bullet (for Quran tafsir purpose, ayat separator)
            self.textCursor().insertHtml("""<span style=" font-family:'AGA Arabesque'; font-size:10pt; color:#9622D3;">_</span>""")

        # forwarding to parent to jump through pages
        elif e.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            super(self._win.__class__, self._win).keyPressEvent(e)

        # once return is pressed
        elif e.key() == Qt.Key.Key_Return:
            # we cleanup the previous block
            tc.select(tc.SelectionType.BlockUnderCursor)
            indent = tc.blockFormat().indent()
            text = tc.selectedText()
            text = text.replace("\u2029", "")

            # first we make sure our block doesn't contains spelling errors
            if tc.block().userData().state != G.State_Correction:
                # and imports all word to our frequency list
                splitted_text = text.split(" ")
                for i, word_text in enumerate(splitted_text[1:]):
                    try:
                        assert len(word_text) <= 3
                        assert word_text[0] not in string.ascii_letters

                        for char in G.new_word_keys.values():
                            # skipping the word if contains bad characters
                            if char in word_text:
                                raise IndexError

                    except (AssertionError, IndexError):
                        continue

                    else:
                        word = S.LocalSettings.Dict.Word(word_text, previous=splitted_text[i])
                        S.LOCAL.DICT.add(word)

            # forward to superclass
            super(Typer, self).keyPressEvent(e)

            # light save settings
            S.LOCAL.saveVisualSettings()

            # apply the default style to the new paragraph
            tc = self.textCursor()
            tc.select(tc.SelectionType.BlockUnderCursor)
            Styles.Default.applyStyle(tc)
            block = tc.blockFormat()
            block.setIndent(indent)
            tc.setBlockFormat(block)

        elif not (e.key() == Qt.Key.Key_Tab and self.auto_complete_available):
            # forward Tab only if we're sure there is no autocomplete to do
            super(Typer, self).keyPressEvent(e)

        # we refresh the 'next character'
        ntc = self.textCursor()
        ntc.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        # we check if next character exists to prevent useless autocompletion display
        # encoding as unicode to make sure that next_char is empty, EOL was considered
        # as a character
        next_character = ntc.selectedText()

        if self.auto_complete_available:
            tc = self.textCursor()
            tc.select(tc.SelectionType.WordUnderCursor)
            self.word = tc.selectedText()

            # getting the previous character
            ptc = self.textCursor()
            ptc.movePosition(QTextCursor.PreviousWord, QTextCursor.MoveMode.MoveAnchor, 2)
            ptc.select(ptc.SelectionType.WordUnderCursor)
            # we check if next character exists to prevent useless autocompletion display
            previous_word = ptc.selectedText()

            word = S.LocalSettings.Dict.Word(self.word, previous=previous_word)
            candidate = S.LOCAL.DICT.find(word)

            # if there is a candidate, we draw the autocomplete_label
            # we also require that the next character is a new word character (' ' or ", etc...)
            # OR that the cursor is at the end of the line
            if candidate and len(candidate) > len(self.word) and \
                    (next_character in G.new_word_keys.values() or tc.positionInBlock() == (tc.block().length() - 1)):
                rect: QRectF
                rect = self.cursorRect(self.textCursor())
                res = candidate[len(self.word):]

                # placing the label where the textCursor is
                self.auto_complete_label.setFont(tc.charFormat().font())
                fm = QFontMetrics(self.auto_complete_label.font())
                w = fm.boundingRect(res).width() + 10

                rect.setWidth(w)
                rect.translate(2, 0)
                self.auto_complete_label.setGeometry(rect)
                self.auto_complete_label.setText(res)
                self.auto_complete_label.show()

            # if no candidate, hiding
            else:
                self.auto_complete_label.hide()

        # finally, if Tab was pressed and there is an auto complete suggestion active
        if e.key() == Qt.Key.Key_Tab and self.auto_complete_available and self.auto_complete_label.isVisible():
            # inserting the suggestion
            self.insertPlainText(self.auto_complete_label.text())

            # resetting the auto_complete label
            self.auto_complete_label.setText('')
            self.auto_complete_label.hide()
            self.word = ""

            # update cursor
            tc = self.textCursor()
            tc.select(tc.SelectionType.WordUnderCursor)

            # adding a space since the previous word should be complete
            # if the next character is in the new word characters, we skip the space after
            if next_character not in G.new_word_keys.values():
                self.insertPlainText(" ")

            self.new_word = True

        # if there is a character we update the changed state
        if len(e.text()):
            self.contentEdited.emit()

    def insertNote(self):
        """
        adding a note in the current cursor's place
        """
        c = self.textCursor()
        warning_format = '\u26A0 %s \u26A0️'
        # TODO: this could be way better

        # if no text was provided we ask for it
        if not c.hasSelection():
            text, ok = QInputDialog.getText(self, 'Insert Warning', 'Content :')

            # inserting the given text to to warning_format
            if ok:
                self.insertHtml(warning_format % str(text))
        else:
            self.insertHtml(warning_format % str(c.selectedText()))

        # rebuild the summary view
        self.contentChanged.emit()

    def applyOverallBlock(self, func):
        """
        apply a given function to every blocks in selection
        :param func: the function to apply
        """
        tc = self.textCursor()

        tc.beginEditBlock()
        # getting the blocks boundary
        start_block = self.document().findBlock(tc.selectionStart()).blockNumber()
        end_block = self.document().findBlock(tc.selectionEnd()).blockNumber()

        # applying the function for every block in range
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            func(block)

        tc.endEditBlock()

    def offsetIndent(self, direction: int, block: QTextBlock):
        """
        indent of unindent the given block
        :param direction: positive indents, negative unindent
        :param block: the block to indent
        """
        # placing the cursor if ever the block was called for somewhere else than the KeyPress event
        tc = self.textCursor()
        tc.setPosition(block.position(), tc.MoveMode.MoveAnchor)

        # increment the current indent level
        bf = tc.blockFormat()
        bf.setIndent(bf.indent() + direction)

        tc.setBlockFormat(bf)

    @G.debug
    def applyStyle(self, check_function, apply_function, color=None):
        """
        this little function applies a simple style to the selection
        :param check_function: this function checks if the style's is applied or not
        :param apply_function: this function applies the style, the function is something like lambda x: x.setBold
        :param color: if we want to assign a QColor
        """
        if check_function and apply_function:
            # getting the previous character
            tc = self.textCursor()
            tc.movePosition(tc.MoveOperation.Right, tc.MoveMode.MoveAnchor)

            # check if function returns true
            checked = check_function(tc.charFormat().font())

        # get the current character format
        tc = self.textCursor()
        cf = tc.charFormat()
        f = cf.font()

        if color:
            # getting this default QTextCharFormat to know which foreground default color is used by the app
            default = QTextCharFormat()
            # toggling to color
            cf.setForeground(color if color != cf.foreground() else default.foreground())

        if check_function and apply_function:
            # apply the function by toggle the 'checked' state
            apply_function(f)(not checked)

        # apply the resulting font and char format
        cf.setFont(f)
        tc.setCharFormat(cf)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasText():
            self.insertPlainText(source.text())

    @G.debug
    def toggleFormat(self, style: TyperStyle = None, block: QTextBlock = None):
        """
        Toggle a block format between the given one and the default one
        FIXME: also applies to the previous paragraph
        :param style: the style to apply / unapply
        :param block: the block to apply the style
        """
        tc = self.textCursor()

        # if block is defined, moving to the first char
        if block:
            tc.setPosition(block.position() + 1, tc.MoveMode.MoveAnchor)

        # clear selection and select the current block
        tc.clearSelection()
        tc.select(tc.SelectionType.BlockUnderCursor)

        b, t = tc.blockFormat(), tc.charFormat()

        # check if style corresponding based on the matching userState
        if style and style != tc.block():
            style.applyStyle(b, t)
            tc.setBlockFormat(b)
            tc.setCharFormat(t)

            # apply to the current block's userstate the uniqid value of the style
            # (this data goes in the HTML code and will be retrieved when loading
            # the document again in sha Allah)
            tc.block().setUserState(style.id)

        # revert to the default style
        else:
            tc.setBlockFormat(self.default_blockFormat)
            tc.setCharFormat(self.default_textFormat)
            tc.block().setUserState(0)

    def insertAyat(self, s, v, cmd=''):
        """
        Insert a verse to text document
        :param s: surat number
        :param v: a list of all verses
        :param cmd: the command to get these verse, like 2:4-6
        """
        # getting the block under cursor,
        tc = self.textCursor()
        tc.beginEditBlock()
        tc.select(tc.SelectionType.BlockUnderCursor)

        # if block has no length
        l = len(tc.selectedText())

        # preparing the ayat paragraph for upcoming styling
        if len(v) and not l:
            res = "﴿ %s " % ' ۝ '.join(v)

        # this will insert the ayat(s) in-line
        elif len(v):
            res = (
                      "<span style='font-weight:600; color:#169b4c;'>﴾ %s ﴿</span> &#x200e; (%s %s)" if l else "﴿ %s ﴾ (%s %s)") % (
                      ' ۝ '.join(v),
                      QuranWorker.QuranQuote.surats[s].arabic,
                      translitteration.get_arabic_numbers(cmd, not l)
                  )

        # otherwise (len(v) == 0) we just print the surat's name
        else:
            res = QuranWorker.QuranQuote.surats[s].arabic

        # printing in a new paragraph
        if not l:
            if len(v):
                # just adding a separator if ayat is inserted
                path = QUrl(r"./rsc/ayat_separator_LD.png")
                self.insertHtml(f"<p><img src='{path.toString()}'></p><p>{res}</p>")

                # before and after applied the "ayat" style
                self.toggleFormat(Styles.Ayat)
                self.insertHtml(f"<p>﴾</p><p>({QuranWorker.QuranQuote.surats[s].arabic} {translitteration.get_arabic_numbers(cmd, not l)})</p>")
                self.toggleFormat(Styles.Ayat)

                # applying some style to the text block
                default = QTextCharFormat()

                tc.select(tc.SelectionType.BlockUnderCursor)
                cf = tc.charFormat()
                f = cf.font()
                f.setBold(False)

                color = QColor(38, 125, 255)
                if color:
                    cf.setForeground(color if color != cf.foreground() else default.foreground())

                cf.setFont(f)
                tc.setCharFormat(cf)
                tc.clearSelection()

                # inserting an empty block
                tc.insertBlock()

            # otherwise we insert a block of text and decorators for a new surat
            else:
                self.insertHtml("<center><p><img src='%s'></p></center>" % r"./rsc/surat_sep_0_LD.png")
                tc.insertBlock()

                self.insertHtml(f"<center><p>{res}</p></center>")

                self.toggleFormat(Styles.SuratAR)
                tc.insertBlock()

                self.insertHtml("<center><p><img src='%s'></p></center>" % r"./rsc/surat_sep_1_LD.png")
                tc.insertBlock()

                self.insertHtml(f"<center><p>{QuranWorker.QuranQuote.surats[s].name} ({int(QuranWorker.QuranQuote.surats[s].order)})</p></center>")
                self.toggleFormat(Styles.SuratFR)
                tc.insertBlock()

                self.insertHtml("<center><p><img src='%s'></p></center>" % r"./rsc/surat_sep_2_LD.png")
                self.toggleFormat(Styles.SuratOrnament)
                tc.insertBlock()

        # if this is an inline insert, revert to normal
        else:
            cf = self.currentCharFormat()

            # getting the default font color
            default = QTextCharFormat()
            cf.setForeground(default.foreground())

            f = self.currentFont()
            f.setBold(False)
            cf.setFont(f)

            # insert the HTML styled block of text
            self.insertHtml(res)

            self.setCurrentCharFormat(cf)

        tc.endEditBlock()

    @G.log
    def insertBookSource(self, obj: S.LocalSettings.BookMap.Kitab | S.LocalSettings.BookMap.Bab | S.LocalSettings.BookMap.Hadith):
        tc = self.textCursor()
        tc.beginEditBlock()

        if isinstance(obj, S.LocalSettings.BookMap.Kitab):
            self.insertPlainText(obj.name)
            self.toggleFormat(Styles.Kitab)
            tc.insertBlock()

        elif isinstance(obj, S.LocalSettings.BookMap.Bab):
            self.insertPlainText(obj.name)
            self.toggleFormat(Styles.Bab)
            tc.insertBlock()

        tc.endEditBlock()

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

    def quoteText(self, quote):
        """
        Adding the char around the selection
        :param quote: the quote character, either " ' ( or [
        """
        # getting the HTML code of the selection
        html = self.extractTextFragment(self.textCursor().selection().toHtml())

        # an equivalence list of the quote characters
        eq = {
            "(": ")",
            "'": "'",
            '"': '"',
            "[": "]"
        }

        # if we quote through " we automatically make the text italic and uppercase the first char
        # TODO: implement in user settings
        if quote == '"':

            # we try to uppercase the first char after the ending of an HTML tag, it'll return 1 to the var "n"
            # if it matche something
            res, n = re.subn(r">(\w)", lambda x: x.group().upper(), html, count=1)

            # otherwise (means we don't have HTML tags at the beggining of our fragment), we uppercase the first char
            if not n:
                res = html.capitalize()

            # italic everything inside the selection
            res = re.sub(r"^(<span.*?>)?(.*?)(</span>)?$", r'<i>\1"\2"</span></i>', res)

        else:
            # making a simple quoting if this is not "
            res = f"{quote}{html}{eq[quote]}"

        # insert the new char
        self.textCursor().insertHtml(res)

    @staticmethod
    def correctWord(action: QAction):
        """
        insert word's correction based on data
        :param action: the QAction called from the popup menu
        :var tc: the QTextCursor
        """
        tc, word = action.data()
        tc.insertHtml(word)

    def addWord(self, word: str, state):
        """
        add a new word to the dictionary
        :param word: new word
        :param state: just the state sent by the signal
        """
        f = open(self._win.dictionnary.dict_path, 'a', encoding='utf-8')

        # adding a new line for the word and a frequency of 1
        f.write(f'\n{word}\t1')
        f.close()

        # reloading the dictionary
        self._win.dictionnary.start()

    def contextMenuEvent(self, e: QContextMenuEvent):
        """
        Displays the popup menu
        TODO: reorder, hide header when useless, etc
        :param e: context menu event
        """
        # getting the current global pos of the cursor
        global_pos = self.mapToGlobal(e.pos())
        pos = e.pos()

        # create a standard context menu on the pos
        try:
            menu = self.createStandardContextMenu(pos)
        except TypeError as e:
            G.exception(e)
            menu = self.createStandardContextMenu()

        # allow the user to add a separator, this one will be used later when exporting as PDF, it marks
        # the text displayed on the column along the PDF page preview
        addseparator = QAction('Add translation separator', menu)
        addseparator.triggered.connect(lambda: self.insertHtml('<hr />'))
        menu.insertAction(menu.actions()[0], addseparator)

        # getting the word
        tc = self.cursorForPosition(pos)
        tc.select(QTextCursor.WordUnderCursor)
        text = tc.selectedText()

        # getting the block
        c_block = self.cursorForPosition(pos)
        c_block.select(QTextCursor.BlockUnderCursor)
        block = c_block.block()

        # insert a separator to the beginning
        menu.insertSeparator(menu.actions()[0])

        # if its recognized as an audio (thanks to the Highlighter class)
        if block.userData().state == G.State_Audio:

            # extract the correct filename
            # TODO: Change it, this should just display an icon then reading some hidden value containable in the HTML
            audio_match = re.match(u'.*?\u266C(.*?)\u266C.*?', block.text())
            audio_path = G.user_path(f"Music/.typer_records/{audio_match.groups()[0].strip()}.wav")

            def removeAudio(path: str, cursor_pos: QPoint):
                """
                remove the current audio file
                :param path: the filename
                :param cursor_pos: the cursor position where the popup has been submitted
                """
                # require confirmation to delete
                dialog = QMessageBox.question(
                    None,
                    "Typer - remove audio file",
                    "<b>Remove audio file</b> in record folder also ?\n<i>%s</i>" % path,
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )

                if dialog == QMessageBox.Yes:
                    try:
                        os.remove(path)

                    except PermissionError as exp:
                        G.exception(exp)
                        QMessageBox.critical(
                            None,
                            "Typer - Failed to remove file",
                            "Can't remove file, still opened ? \n <i>%s</i>" % path,
                            QMessageBox.StandardButton.Ok
                        )

                # if the user says "No", we just remove the text from the document
                if dialog != QMessageBox.Cancel:
                    c = self.cursorForPosition(cursor_pos)
                    c.select(QTextCursor.BlockUnderCursor)
                    c.removeSelectedText()

            menu.insertSeparator(menu.actions()[0])

            # adding the remove audio menu
            delete_audio_menu = QAction('Remove audio', menu)
            delete_audio_menu.triggered.connect(partial(removeAudio, audio_path, pos))
            menu.insertAction(menu.actions()[0], delete_audio_menu)

            # adding the play audio menu
            audio_menu = QAction('Open audio', menu)
            audio_menu.triggered.connect(lambda: os.startfile(audio_path))
            menu.insertAction(menu.actions()[0], audio_menu)

        # adding a section "Edit" for suggestion, dictionary ops
        menu.insertSeparator(menu.actions()[0])
        conj_sep = QAction('Edit', menu)
        conj_sep.setDisabled(True)
        menu.insertAction(menu.actions()[0], conj_sep)

        # if the block's flagged as incorrect
        if block.userData().state == G.State_Correction:

            # we add suggestions for the given word
            solution_menu = QMenu(f'Suggestions for "{text}"', menu)
            cnt = self.buildSpellMenu(text, tc, solution_menu)

            # add the word to the dictionary if its not (flagged as incorrect means its not in the dictionary
            addword_menu = QAction(f'Add "{text}" to dictionary', menu)
            addword_menu.setData(text)
            menu.insertAction(menu.actions()[0], addword_menu)
            addword_menu.triggered.connect(partial(self.addWord, text))

            # if suggestions for the word are at least one we display the menu
            if cnt >= 1:
                menu.insertMenu(menu.actions()[0], solution_menu)

        # adding synonyms suggestions
        synonym_menu = QMenu(f'Synonyms for "{text}"', menu)
        cnt = self.buildSynMenu(text, tc, synonym_menu)

        # if we got some synonyms
        if cnt >= 1:
            menu.insertMenu(menu.actions()[0], synonym_menu)

        # if word's flagged as a verb
        # TODO: add it as a signal to enable / disable a button in the Toolbar
        # TODO: batch the forms in a frozenset
        is_verb = self.cursor.execute(f'SELECT source FROM conjugaison WHERE forme="{text}"').fetchone()

        # if selection is a verb, display the menu...
        if is_verb:
            open_conjugate_menu = QAction('Conjugate...', menu)
            open_conjugate_menu.triggered.connect(partial(self.openConjugate, tc, is_verb[0]))
            menu.insertAction(menu.actions()[0], open_conjugate_menu)

        # adding a header
        menu.insertSeparator(menu.actions()[0])
        conj_sep = QAction('Language', menu)
        conj_sep.setDisabled(True)
        menu.insertAction(menu.actions()[0], conj_sep)

        # displaying the final popup menu
        menu.exec_(global_pos)

    def openConjugate(self, cursor: QTextCursor, word: str, state: bool):
        """
        Show up the Conjugate dialog
        :param cursor: the current word's textCursor
        :param word: the verb
        :param state: got by the signal
        """
        # display the dialog
        self.conjugateDialog.load(cursor, word)
        self.conjugateDialog.show()

    def buildSynMenu(self, word: str, cursor: QTextCursor, menu: QMenu):
        """
        Generate the synonyms menu from the db
        TODO: maybe this should return a list of synonyms, and the main function add them in the popup menu
        :param word: the word we want to search the synonyms for
        :param cursor: the textCursor
        :param menu: the source popupmenu
        :return: the length of synonyms found
        """
        def synonym(w: str) -> set:
            """
            get all synonyms for the current word and all words this one is a synonym for
            TODO: maybe that's redundant ? compare
            :param w: the word
            :return: a set of the synonyms
            """
            s = set()
            # 'synonyme' field search all synonyms for the word
            # 'mot' field search all words this word is a synonym for
            for field in ('synonyme', 'mot'):
                res = self.cursor.execute(f'SELECT {field} FROM synonyme WHERE mot="{w}"').fetchall()

                # extending the set with results
                s.update(set([a[0] for a in res]))

            return s

        # getting the synonyms
        synonyms = synonym(word)

        # if no synonyms found, we try to get the original form of the word
        # TODO: search only if word is a verb, make a reusable function
        if not len(synonyms):
            try:
                # if we found the current word in 'forme' field it means the word is a conjugated form of a verbe
                source, mode, temps, id = self.cursor.execute(
                    f'SELECT source, mode, temps, id FROM conjugaison WHERE forme="{word}"').fetchone()

            except TypeError:
                pass

            # since its a conjugated form, we search all synonyms of the orignal verb, then re-apply the same
            # conjugation to the synonyms found
            else:
                syns = ", ".join([f'"{s}"' for s in synonym(source)])
                conjugated_syns = self.cursor.execute(
                    f'SELECT forme FROM conjugaison WHERE source IN ({syns}) AND mode={mode} AND temps={temps} AND id={id}')
                synonyms.update([a[0] for a in conjugated_syns.fetchall()])

        # adding results to menu
        self.insertItemsToMenu(synonyms, cursor, menu)

        return len(synonyms)

    def buildSpellMenu(self, text: str, cursor: QTextCursor, menu: QMenu):
        """
        Create a menu for the current corrections
        :param text: the word to correct
        :param cursor: the current textCursor
        :param menu: the menu to append the results
        :return: the length of the suggestions
        """

        # looking for corrections
        suggestions = self.symspell.lookup(text, ignore_token=self.re_ignoretoken, max_edit_distance=2,
                                           verbosity=Verbosity.CLOSEST, include_unknown=False, transfer_casing=False)

        # adding results to menu
        self.insertItemsToMenu([a.term for a in suggestions], cursor, menu)

        return len(suggestions)

    def insertItemsToMenu(self, terms: set | list, cursor: QTextCursor, menu: QMenu):
        """
        Add the items to the given menu setting the cursor as data
        :param terms: the items to iter
        :param cursor: the textCursor as data
        :param menu: the QMenu to insert
        """
        # looping through items
        for solution in terms:
            action = QAction(solution, menu)

            # adding the cursor as a userData
            action.setData((cursor, solution))
            menu.addAction(action)

        # for all these action trigger the correctWord function
        if menu.actions():
            menu.triggered.connect(self.correctWord)

    def canInsertFromMimeData(self, source):
        """
        Allows the paste of image in the document
        :param source: MimeData source
        :return: ability to insert
        """
        # overrides if the source is an image
        if source.hasImage():
            return True

        # otherwise return the normal behavior
        else:
            return super(Typer, self).canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        """
        Overrides the insertFromMimeData
        :param source: the MimeData source
        """
        # special behavior if we have an image
        # TODO: should be different, maybe only accept vector images ? maybe ask for a filename path ?
        if source.hasImage():
            image = QImage(QVariant(source.imageData()).value())

            # convert the image as a bytearray to source
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, 'PNG')
            img_str = ba.toBase64().data()

            # insert the image data
            cursor = self.textCursor()
            cursor.insertHtml(f'<img style="width:100%" src="data:image/png;base64,{img_str.decode()}" />')

        # continue with the default behavior
        super(Typer, self).insertFromMimeData(source)


class TyperHighlighter(QSyntaxHighlighter):
    """
    A simple Highlighter
    """
    typer: Typer

    # defining some formats
    err_format = QTextCharFormat()
    err_format.setUnderlineColor(Qt.red)
    err_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)

    audio_format = QTextCharFormat()
    audio_format.setForeground(QColor(255, 125, 35))

    ref_format = QTextCharFormat()
    ref_format.setForeground(QColor(255, 35, 45))
    ref_format.setFontWeight(800)

    def __init__(self, parent=None, *args):
        super(TyperHighlighter, self).__init__(*args)
        self.typer = parent

    def highlightBlock(self, text):
        """
        Overridden QSyntaxHighlighter method to apply the highlight
        """
        # abort if no parent or not yet loaded ressources
        if not self.typer or (self.typer and not self.typer.symspell):
            return

        def tokenize(body_text: str) -> (int, str):
            """
            this tokenize the text with a rule
            :param body_text: the whole text we want to tokenize
            :return: yield the index of the word and the word itself
            """
            index = 0
            # TODO: this split regex should be an re.unescape(''.join(G.escape...) ???
            for word_match in re.split(r"[ \-\.\,:;!?\"\'\(\)\[\]]", body_text):
                yield index, word_match

                # increments the current text's index
                index += len(word_match) + 1

        # we define a default BlockUser State data scanning the words
        data = QTextBlockUserData()
        data.state = state = G.State_Default

        for idx, word in tokenize(text):
            # if word is a music symbol this means we have an audio file, flagging as
            if word == '♬':
                self.setFormat(idx, len(word), self.audio_format)
                state = G.State_Audio

            # a word with # around is a reference
            # TODO: should match a regex pattern, same for the audio
            elif word.startswith("#") and word.endswith("#"):
                self.setFormat(idx, len(word), self.ref_format)
                state = G.State_Reference

            # otherwise we check if word' spelling is invalid
            else:
                try:
                    # first make sure the word's length is correct
                    assert len(word) > 1

                    # now getting the word correction
                    suggestions = self.typer.symspell.lookup(word, ignore_token=Typer.re_ignoretoken,
                                                             max_edit_distance=2, verbosity=Verbosity.TOP,
                                                             include_unknown=False, transfer_casing=False)

                    # abort if word's already in the dictionary
                    assert suggestions[0].term != word

                    # if we reach this point it means the word is incorrect and have some spell suggestions
                    self.setFormat(idx, len(word), self.err_format)
                    state = G.State_Correction

                except (AssertionError, IndexError):
                    pass

            # finally setting the data state
            data.state = state

        # applying the data
        self.setCurrentBlockUserData(data)
