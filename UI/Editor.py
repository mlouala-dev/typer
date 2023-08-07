# بسم الله الرحمان الرحيم
import re
import string
import os
import sqlite3
from time import time, localtime, strftime
from functools import partial
from symspellpy import Verbosity

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from UI import QuranWorker
from UI.Dialogs import Conjugate, DateTimePickerDialog
from tools.styles import Styles, Styles_Shortcut, TyperStyle
from tools import G, T, S, translitteration, Audio


class Typer(QTextEdit):
    """
    The main widget after the window, this is the one which display what used is typing, providing some
    interfacing with the other tools like right click menus & shortcuts
    """
    _win: QMainWindow

    symspell = None
    auto_complete = False
    auto_complete_available = True

    # used to automatically superscript some patterns
    re_numbering = re.compile(r'((1)(ers?|ères?))|((\d+)([èe]mes?))')
    re_textblock = re.compile(r'(.*?>)( +)?[-\u2022]?(<span.*?>\d\)</span>)?( +)?([\w\d]+)(.*?)<', flags=re.IGNORECASE)
    prophet_match = ('Muhammad', 'Prophète', 'Messager')
    Allah_match = ('Allah', 'Dieu')
    ThanaaWaMadh = {
        'aas': 'e',
        'ra': 'h',
        'raha': 'i',
        'rahuma': 'j',
        'rahum': 'k'
    }

    contentChanged = pyqtSignal()
    contentEdited = pyqtSignal()

    def __init__(self, parent=None):
        super(Typer, self).__init__(parent)
        self._win = parent
        self.anchor = None
        children = self.children()

        for child in children:
            if child.metaObject().className() == 'QWidgetTextControl':
                child.setProperty('openExternalLinks', True)

        # preparing the Conjugate dialog
        self.dictionary = sqlite3.connect(G.rsc_path("lang.db"))
        self.cursor = self.dictionary.cursor()
        self.D_conjugate = Conjugate(self._win, self.dictionary)

        # will expand since the others have fixed widths
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # autocomplete label
        self.WL_autoComplete = QLabel(self)
        self.WL_autoComplete.hide()
        self.WL_autoComplete.setStyleSheet("""
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

        def opacity_effect(opacity=1.0):
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(opacity)
            return effect

        self.WL_autoComplete_effect = partial(opacity_effect, .9)
        self.WL_autoComplete_lighteffect = partial(opacity_effect, .3)
        self.WL_autoComplete.setGraphicsEffect(self.WL_autoComplete_effect())

        # we should never need a horizontal scrollbar since the text is wrapped
        self.horizontalScrollBar().setDisabled(True)
        self.horizontalScrollBar().hide()

        # this is the current word
        self._word = ''
        self.tense = None
        # we measure time spent to type a word
        self.word_time = time()

        self.new_word = True

        self.translitteration_bound = None
        self.translitterate_mode = False

        self.default_blockFormat = QTextBlockFormat()
        self.default_font = G.get_font()
        self.default_textFormat = QTextCharFormat()
        self.initFormatting()

        self.document().blockCountChanged.connect(self.contentChanged.emit)

        # applying a simple syntax highlighter
        self.W_syntaxHighlighter = TyperHighlighter(self, self.document())

        self.W_audioMap = TyperAudioMap(self)
        self.enableAudioMap()

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

    def textOperation(self, text_cursor=None, operation=None):
        """
        performs operation such as next_char previous_char etc
        """
        try:
            text_cursor.NextCharacter
        except AttributeError:
            text_cursor = self.textCursor()
        finally:
            text_cursor.movePosition(operation, QTextCursor.MoveMode.KeepAnchor)

        return text_cursor.selectedText()

    @property
    def next_character(self) -> str:
        try:
            return self.textOperation(self.textCursor(), operation=QTextCursor.MoveOperation.NextCharacter)[0]
        except IndexError:
            return ''

    @property
    def previous_character(self) -> str:
        try:
            return self.textOperation(self.textCursor(), operation=QTextCursor.MoveOperation.PreviousCharacter)[0]
        except IndexError:
            return ''

    @property
    def next_word(self, *args) -> str:
        return self.textOperation(*args, operation=QTextCursor.MoveOperation.NextWord)

    @property
    def previous_word(self, *args) -> str:
        return self.textOperation(*args, operation=QTextCursor.MoveOperation.PreviousWord)

    def guessTense(self):
        tc = self.textCursor()
        tc.movePosition(tc.MoveOperation.StartOfBlock, tc.MoveMode.KeepAnchor, 1)
        hard_split = T.Regex.Predikt_hard_split.split(tc.selectedText())[-1]
        words = T.Regex.Predikt_soft_split.split(hard_split)
        sentence = ' '.join((('',) + tuple(words))[-2:])

        S.GLOBAL.PREDIKT.analyze(sentence)

    def applyTense(self, tense):
        self.tense = tense if tense else None

    def loadPage(self, page: int = 0):
        try:
            self.setHtml(S.LOCAL.BOOK[page].content)
            tc = self.textCursor()
            tc.setPosition(S.LOCAL.BOOK[page].cursor)
            self.setTextCursor(tc)
            self.ensureCursorVisible()

            def forward_analysis(*args, **kwargs):
                S.GLOBAL.CORPUS.get_solutions(*args, **kwargs)
                self.W_syntaxHighlighter.rehighlight()
                self.update()

            S.POOL.start(
                S.GLOBAL.CORPUS.Analyze(
                    T.Regex.tokenize(self.toPlainText()),
                    S.GLOBAL.CORPUS,
                    forward_analysis
                ),
                uniq='grammar_note'
            )

        except KeyError:
            pass

    def initFormatting(self):
        self.default_blockFormat = QTextBlockFormat()
        T.QOperator.ApplyDefault.BlockFormat(self.default_blockFormat)

        self.default_font = G.get_font()
        self.WL_autoComplete.setFont(self.default_font)
        T.QOperator.ApplyDefault.Font(self.default_font)
        metrics = QFontMetrics(self.default_font)
        T.HTML.default_height = metrics.ascent()

        self.setFont(self.default_font)
        self.setCurrentFont(self.default_font)

        self.default_textFormat = QTextCharFormat()
        self.default_textFormat.setFont(self.default_font)
        # self.default_textFormat.setProperty(8167, [G.__font__])
        self.setCurrentCharFormat(self.default_textFormat)

        T.QOperator.ApplyDefault.Document(self.document(), self.default_font)
        self.document().setDefaultStyleSheet(T.QOperator.ApplyDefault.DocumentStyleSheet())
        self.document().setDocumentMargin(10)
        self.textCursor().setBlockFormat(self.default_blockFormat)

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

        self.solveAudioMap()

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
        text = tc.selectedText()

        # if block has no length
        l = len(text)
        if l == 2 and text[0] == '\u2029' and not T.TEXT.is_audio_tag(text[1]):
            l = 0

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
            try:
                res = QuranWorker.QuranQuote.surats[s].arabic
            except IndexError:
                tc.endEditBlock()
                return

        # printing in a new paragraph
        if not l:
            if len(v):
                # just adding a separator if ayat is inserted
                self.insertHtml(f"<p><img src=':/ayat_separator_LD'></p><p>{res}</p>")

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
                self.insertHtml("<center><p><img src=':/surat_sep_0_LD'></p></center>")
                tc.insertBlock()

                self.insertHtml(f"<center><p>{res}</p></center>")

                self.toggleFormat(Styles.SuratAR)
                tc.insertBlock()

                self.insertHtml("<center><p><img src=':/surat_sep_1_LD'></p></center>")
                tc.insertBlock()

                self.insertHtml(f"<center><p>{QuranWorker.QuranQuote.surats[s].name} ({int(QuranWorker.QuranQuote.surats[s].order)})</p></center>")
                self.toggleFormat(Styles.SuratFR)
                tc.insertBlock()

                self.insertHtml("<center><p><img src=':/surat_sep_2_LD'></p></center>")
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

    def insertBookSource(self, obj: S.LocalSettings.BookMap.Kitab | S.LocalSettings.BookMap.Bab | S.LocalSettings.BookMap.Hadith):
        tc = self.textCursor()
        tc.select(tc.SelectionType.BlockUnderCursor)
        # if block has no length
        is_empty_block = not len(tc.selectedText().
                                 replace(chr(T.TextOperator.audio_char), '').
                                 replace(chr(T.TextOperator.para_char), ''))
        tc = self.textCursor()
        tc.beginEditBlock()

        if is_empty_block:
            if isinstance(obj, S.LocalSettings.BookMap.Hadith):
                tc.movePosition(tc.MoveOperation.StartOfBlock, tc.MoveMode.MoveAnchor)
                tc.movePosition(tc.MoveOperation.EndOfBlock, tc.MoveMode.KeepAnchor)
                self.insertHtml(obj.toHtml())

            else:
                tc.insertBlock()

                if isinstance(obj, S.LocalSettings.BookMap.Kitab):
                    self.insertPlainText(obj.name)
                    self.toggleFormat(Styles.Kitab)

                elif isinstance(obj, S.LocalSettings.BookMap.Bab):
                    self.insertPlainText(obj.name)
                    self.toggleFormat(Styles.Bab)

                T.HTML.insertParagraphTime(tc)

            self.insertHtml(f'''<p align="justify" style="-qt-paragraph-type:empty; font-family:'{G.__la_font__}'; font-size:{G.__font_size__}pt;"><br /></p>''')

        else:
            reset_style = '<span style=""> </span>'

            if isinstance(obj, S.LocalSettings.BookMap.Kitab):
                self.insertHtml(f'<span style="color:#267dff; font-weight:600;">{obj.name}</span>{reset_style}')

            elif isinstance(obj, S.LocalSettings.BookMap.Bab):
                self.insertHtml(f'<span style="color:#73c3ff;">({obj.id}) {obj.name}</span>{reset_style}')

            elif isinstance(obj, S.LocalSettings.BookMap.Hadith):
                self.insertHtml(f'{obj.id} [{obj.sub_id}] {obj.toHtml()}{reset_style}')

        tc.endEditBlock()

    def insertBookReference(self, obj: S.LocalSettings.BookMap.Kitab | S.LocalSettings.BookMap.Bab | S.LocalSettings.BookMap.Hadith):
        """
        Insert a reference tag in text for page xref
        """

        if isinstance(obj, S.LocalSettings.BookMap.Kitab):
            r = obj.id

        elif isinstance(obj, S.LocalSettings.BookMap.Bab):
            r = f'{obj.kid}_{obj.id}'

        elif isinstance(obj, S.LocalSettings.BookMap.Hadith):
            r = f'{obj.id}'

        self.textCursor().insertText(f'#_REF_{r}_#')

    def quoteText(self, quote):
        """
        Adding the char around the selection
        :param quote: the quote character, either " ' ( or [
        """
        # getting the HTML code of the selection
        html = T.HTML.extractTextFragment(self.textCursor().selection().toHtml())

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

    def displayPrediction(self):
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        self.word = tc.selectedText()

        # print('CURRENT WORD', self.word)
        tc = self.textCursor()
        tc.movePosition(tc.MoveOperation.StartOfBlock, tc.MoveMode.KeepAnchor, 1)
        # print('PREVIOUS 2 WORDS', tc.selectedText())
        # previous two words
        last_words = tc.selectedText()

        try:
            hard_split = T.Regex.Predikt_hard_split.split(last_words)[-1]
            hard_split = hard_split[0].lower() + hard_split[1:]
            words = T.Regex.Predikt_soft_split.split(hard_split)
            words_tuple = (('', '',) + tuple(words))[-3:]
            tail, word = words_tuple[:-1] + ('', '',), words_tuple[-1]

            assert (not T.Regex.Predikt_ignore_token.match(''.join(tail + (word,))))
            candidate = S.GLOBAL.CORPUS.predict(*tail[:2], word, not len(self.word))

        except (AssertionError, IndexError):
            candidate, word = None, self.word

        if word in self.prophet_match:
            candidate = f'{word} ﷺ'
        elif word in self.Allah_match:
            candidate = f'{word} ﷻ'

        # if there is a candidate, we draw the autocomplete_label
        # we also require that the next character is a new word character (' ' or ", etc...)
        # OR that the cursor is at the end of the line
        if candidate:
            rect = self.cursorRect(self.textCursor())
            res = candidate[len(word):]

            # placing the label where the textCursor is
            self.WL_autoComplete.setFont(tc.charFormat().font())
            fm = QFontMetrics(self.WL_autoComplete.font())
            w = fm.boundingRect(res).width() + 10

            rect.setWidth(w)
            rect.translate(2, 0)
            self.WL_autoComplete.setGeometry(rect)
            self.WL_autoComplete.setText(res)
            self.WL_autoComplete.show()

        # if no candidate, hiding
        else:
            self.WL_autoComplete.hide()

    @staticmethod
    def correctWord(action: QAction):
        """
        insert word's correction based on data
        :param action: the QAction called from the popup menu
        :var tc: the QTextCursor
        """
        tc, word = action.data()
        tc.insertHtml(word)

    def applyDefaultDocument(self, doc: QTextDocument):
        doc.setDefaultFont(self.default_font)
        doc.setIndentWidth(10)
        doc.setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignLeft))

    # AUDIO MAP

    def enableAudioMap(self):
        if not S.LOCAL.audio_map:
            return

        self.W_audioMap.show()
        self.document().blockCountChanged.connect(self.graphAudioMap)
        self.document().blockCountChanged.connect(self.solveAudioMap)
        # self.document().documentLayout().documentSizeChanged.connect(self.graphAudioMap)
        self.verticalScrollBar().valueChanged.connect(self.W_audioMap.update)
        self.graphAudioMap()
        self.solveAudioMap()

    def disableAudioMap(self):
        if not S.LOCAL.audio_map:
            return

        self.W_audioMap.hide()

        try:
            self.document().blockCountChanged.disconnect(self.graphAudioMap)
            self.document().blockCountChanged.disconnect(self.solveAudioMap)
            # self.document().documentLayout().documentSizeChanged.disconnect(self.graphAudioMap)
            self.verticalScrollBar().valueChanged.disconnect(self.W_audioMap.update)

        except TypeError:
            pass

    def graphAudioMap(self):
        if not S.LOCAL.audio_map:
            return

        html = self.toHtml()
        if html != self.W_audioMap.page and len(self.toPlainText().strip()):
            self.W_audioMap.page = html
            S.POOL.start(Audio.graphBlockMap(self.document(), self.W_audioMap.setMap), uniq='graph')

    def solveAudioMap(self):
        if S.LOCAL.audio_map and len(self.W_audioMap.map):
            S.POOL.start(Audio.solveAudioMapping(self.toHtml(), self.W_audioMap.addSolver), uniq='solve')

    # MENUS

    def openConjugate(self, cursor: QTextCursor, word: str, state: bool):
        """
        Show up the Conjugate dialog
        :param cursor: the current word's textCursor
        :param word: the verb
        :param state: got by the signal
        """
        # display the dialog
        self.D_conjugate.load(cursor, word)
        self.D_conjugate.show()

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
            res = self.cursor.execute(f'SELECT entry, synonym FROM synonymes WHERE entry="{w}" OR synonym="{w}"').fetchall()
            for a, b in res:
                if a == w:
                    s.add(b)
                if b == w:
                    s.add(a)
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
        suggestions = T.SPELL.lookup(text, max_edit_distance=2, verbosity=Verbosity.CLOSEST,
                                     include_unknown=False, transfer_casing=False)

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
            action.triggered.connect(partial(self.correctWord, action))
            # adding the cursor as a userData
            action.setData((cursor, solution))
            menu.addAction(action)

    def upvoteGrammar(self, s: S.GLOBAL.CORPUS.Solution, text:str):
        x1 = s.x1 if isinstance(s.x1, S.GLOBAL.CORPUS.Solution) else S.GLOBAL.CORPUS.Solution(role=s.x1)
        x2 = s.x2 if isinstance(s.x2, S.GLOBAL.CORPUS.Solution) else S.GLOBAL.CORPUS.Solution(role=s.x2)
        z = s.z if isinstance(s.z, S.GLOBAL.CORPUS.Solution) else S.GLOBAL.CORPUS.Solution(role=s.z)

        x1, x2, y, z = x1.role, x2.role, s.role, z.role
        scheme = '\n'.join([S.GLOBAL.CORPUS.morphs[n] for n in [x1, x2, y, z]])
        res = QMessageBox.warning(
            None,
            "Upvote grammar",
            f"Do you want to upvote the current grammar scheme ? \n {scheme}",
            buttons=QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            defaultButton=QMessageBox.StandardButton.Yes
        )

        if res == QMessageBox.StandardButton.Yes:
            S.GLOBAL.CORPUS.upvote_grammar(x1, x2, y, z)
            S.POOL.start(
                S.GLOBAL.CORPUS.Analyze(
                    T.Regex.tokenize(text),
                    S.GLOBAL.CORPUS,
                    S.GLOBAL.CORPUS.get_solutions
                ),
                uniq='grammar_note'
            )
            self.W_syntaxHighlighter.rehighlight()

    # OVERRIDES

    def mousePressEvent(self, e: QMouseEvent) -> None:
        """
        When mouse is pressed we check what word we have and what we can do
        """

        modifiers = QApplication.keyboardModifiers()

        self.anchor = self.anchorAt(e.pos())
        if self.anchor:
            QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)

        # if alt modifier is on we directly display the word corrections
        if modifiers == Qt.KeyboardModifier.AltModifier:
            c = self.cursorForPosition(e.pos())
            c.select(QTextCursor.SelectionType.WordUnderCursor)
            text = c.selectedText()

            solution_menu = QMenu(f'Suggestions for {text}', self)

            # appending all the suggestions for the given word
            self.buildSpellMenu(text, c, solution_menu)

            solution_menu.exec(self.mapToGlobal(e.pos()))

        # otherwise we pop the classic popupmenu
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        """
        implentation for hyperlinks
        """
        if self.anchor:
            QDesktopServices.openUrl(QUrl(self.anchor))
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            self.anchor = None
        else:
            super().mouseReleaseEvent(e)

    @G.log
    def keyPressEvent(self, e: QKeyEvent) -> None:
        """
        The main function, handle every thing when a letter is typed
        """
        tc: QTextCursor

        # we check if next character exists to prevent useless autocompletion display
        next_character = self.next_character
        previous_character = self.previous_character

        self.auto_complete_available = bool(not len(next_character.strip()))
        if not self.auto_complete_available:
            self.WL_autoComplete.hide()

        key, current_text = e.key(), e.text()
        modifiers = QApplication.keyboardModifiers()

        # getting the current word
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        self.word = tc.selectedText()

        lowered_text = self.word.lower()

        if self.translitterate_mode:
            if current_text in translitteration.accepted_letters or \
                    key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Right,
                            Qt.Key.Key_Left, Qt.Key.Key_twosuperior, Qt.Key.Key_Home,
                            Qt.Key.Key_End):
                pass
            else:
                return

        # ARABIC GLYPHS #
        if lowered_text in ("sws", "saws", "jj", "aas", "ra", 'raha', 'rahuma', 'rahum') and key in T.Keys.Exits:
            # a glyph for Salla Allahu 'alayhi wa sallam
            if lowered_text in ("sws", "saws"):
                tc.insertText("ﷺ" + current_text)

            # a glyph for Jalla Jalaaluhu
            elif lowered_text == "jj":
                tc.insertText("ﷻ" + current_text)

            # for the other case we need images... until we implement the ThanaaWaMadh font
            else:
                # adding it as a HTML special font
                tc.insertHtml(f'''<span style="font-family:'ThanaaWaMadh';">{self.ThanaaWaMadh[lowered_text]}</span><span style=" font-family:'{G.__la_font__}'; font-size:normal;">{current_text}</span>''')

            # setting word to null
            self.word = ""

            return

        # if it matches our regex for 1st 1er 2nd 34eme etc
        is_number = self.re_numbering.match(self.word)

        # if the user corrected the ى manually, we update the text database
        if current_text == "ى" and (next_character in T.Keys.NewWord.values() or len(next_character) == 0):
            translitteration.append_to_dict(self.word + "ى")

        # it makes the 'st' 'er' to superscript
        elif is_number and key in T.Keys.NewWord:
            # getting the groups from the regex match
            num = int(is_number.groups()[1] or is_number.groups()[4])
            sup = is_number.groups()[2] or is_number.groups()[5]

            # and insert the next char to force the <sup> tag to be closed
            tc.insertHtml(f"{num}<sup>{sup}</sup><span>{current_text}</span>")

            # since we added the current char, no need to continue
            return

        # Quote text
        elif key in T.Keys.Quotes and len(self.textCursor().selectedText()):
            self.quoteText(current_text)
            return

        # brackets override, this mean that < and > will become [ and ] useful when typing a translation
        # and need to insert a translation note
        elif key in [60, 62]:   # 60 is < and 62 >

            # the replacement pattern
            eq = {60: "[", 62: "]"}
            # if there is a selection, we apply quote to it
            if len(self.textCursor().selectedText()):
                self.quoteText("[")

            # otherwise we just override the < and >
            else:
                self.textCursor().insertText(eq[key])

            # since we added what we want from this event, abort
            return

        # if we're not typing translitteration and we are at the end of the document
        elif not self.translitterate_mode and (len(next_character) == 0 or next_character == '\u2029'):
            if len(self.word):

                # if we start a new word
                if key in T.Keys.NewWord:
                    # we measure the time it took to type the previous word and applies an automatic
                    # correction if ratio is under a given value
                    ratio = (time() - self.word_time) / len(self.word)

                    # needs to be implemented in settings and should be customizable by user
                    if ratio <= 0.15 and not self.word[0].isupper():
                        # applies an automatic spell correction, the ignore token to be sure we don't try
                        # to correct the digits, proper names or glyphs
                        suggestions = T.SPELL.lookup(self.word, max_edit_distance=1, verbosity=Verbosity.TOP,
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
                    # self.guessTense()

        if key == Qt.Key.Key_twosuperior and modifiers == Qt.KeyboardModifier.NoModifier:
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
                    self.insertHtml(u"<span style='font-weight:bold; color:orange;'>\u2026 </span>")

                # otherwise we just add a character to force the style to return to format
                else:
                    self.insertHtml("<span style='font-weight:normal;'>'</span>")

                    # selecting all the text, from the first special character to the end
                    tc.setPosition(tc.position(), tc.MoveMode.MoveAnchor)
                    tc.movePosition(tc.MoveOperation.Left, tc.MoveMode.KeepAnchor,
                                    tc.position() - self.translitteration_bound)
                    txt = tc.selectedText()[2:-1]

                    tc.removeSelectedText()

                    if len(txt):
                        # translitterate what's between the head and tail characters
                        tc.insertText(translitteration.translitterate(txt))
            return

        # resetting timing if backspace pressed for more accurate ratio
        if key == Qt.Key.Key_Backspace and len(previous_character):

            if T.TEXT.is_audio_tag(previous_character):
                super().keyPressEvent(e)

            self.word_time = time()

        elif key == Qt.Key.Key_Delete and len(next_character):
            if T.TEXT.is_audio_tag(next_character):
                super().keyPressEvent(e)

        elif key == Qt.Key.Key_Return:
            # insert time anchor before inserting new line
            if tc.block().length() > 2:
                T.HTML.insertParagraphTime(self.textCursor())

            if tc.block().userData():
                # we cleanup the previous block
                tc.select(tc.SelectionType.BlockUnderCursor)
                indent = tc.blockFormat().indent()

                # # first we make sure our block doesn't contains spelling errors
                # if tc.block().userData().state != G.State_Correction:
                #     # and imports all word to our frequency list
                #     # we split the paragraph in phrase, so the previous word suggestion will be coherent
                #     S.LOCAL.DICT.digest(tc.selectedText().replace("\u2029", ""))
                # S.GLOBAL.PREDIKT.digest(tc.selectedText().replace("\u2029", ""))

                # forward to superclass
                tc = self.textCursor()
                block = tc.blockFormat()
                block.setIndent(indent)
                tc.insertBlock(block)

                # light save settings
                S.LOCAL.saveVisualSettings()

                # # apply the default style to the new paragraph

                T.HTML.insertParagraphTime(self.textCursor())
                return

        elif key == Qt.Key.Key_Home and modifiers == Qt.KeyboardModifier.NoModifier:
            block = tc.block()
            if block.text().startswith(chr(T.TEXT.audio_char)):
                tc.setPosition(block.position() + 1, tc.MoveMode.MoveAnchor)
                self.setTextCursor(tc)
                return

        elif key == Qt.Key.Key_Left and previous_character:
            if T.TEXT.is_audio_tag(previous_character):
                super().keyPressEvent(e)

        elif key == Qt.Key.Key_Right and next_character:
            if T.TEXT.is_audio_tag(next_character):
                super().keyPressEvent(e)

        # handling some special shortcuts
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):

            # to copy the HTML code of the selection
            if key == Qt.Key.Key_C:
                tc = self.textCursor()
                QApplication.clipboard().setText(tc.selection().toHtml())

            # to paste the clipboard as HTML
            elif key == Qt.Key.Key_V:
                self.insertHtml(QApplication.clipboard().text())
                self.contentChanged.emit()

            # to cut HTML code
            elif key == Qt.Key.Key_X:
                tc = self.textCursor()
                QApplication.clipboard().setText(tc.selection().toHtml())
                tc.removeSelectedText()
                self.contentChanged.emit()

            # insert a force RTL character
            elif key == Qt.Key.Key_E:
                self.insertHtml('&#x200e;')

            elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Underscore):
                self.zoom(5 if key == Qt.Key.Key_Plus else -5)

            # otherwise we just consider it a normal command
            else:
                super(Typer, self).keyPressEvent(e)

            return

        elif (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
            super(self._win.__class__, self._win).keyPressEvent(e)

        # the alt modifier is used to apply some fast styles
        elif modifiers == Qt.KeyboardModifier.AltModifier:
            # the main title shortcut
            if key in Styles_Shortcut:  # Alt+1

                # apply the style to the whold text block
                self.applyOverallBlock(partial(self.toggleFormat, Styles_Shortcut[key]))

                # and update parent's widget(s)
                self.contentChanged.emit()

            # unindent the text block
            elif key == Qt.Key.Key_Left:
                self.applyOverallBlock(partial(self.offsetIndent, -1))

            # indent the text block
            elif key == Qt.Key.Key_Right:
                self.applyOverallBlock(partial(self.offsetIndent, 1))

            # moving cursor to the previous text block
            elif key == Qt.Key.Key_Up:
                tc.movePosition(tc.MoveOperation.PreviousBlock, tc.MoveMode.MoveAnchor)
                self.setTextCursor(tc)

            # moving cursor to the next text block
            elif key == Qt.Key.Key_Down:
                tc.movePosition(tc.MoveOperation.NextBlock, tc.MoveMode.MoveAnchor)
                self.setTextCursor(tc)

            # add numerotation
            # TODO: could be largely improved, customized numerotation, automatic determination of sub numering, etc
            elif key in (Qt.Key.Key_B, Qt.Key.Key_N):
                tc = self.textCursor()
                b1, b2 = tc.selectionStart(), tc.selectionEnd()
                s, e = min(b1, b2), max(b1, b2)

                tc.setPosition(s, tc.MoveMode.MoveAnchor)
                tc.movePosition(tc.MoveOperation.StartOfBlock, tc.MoveMode.MoveAnchor)
                tc.setPosition(e, tc.MoveMode.KeepAnchor)
                tc.movePosition(tc.MoveOperation.EndOfBlock, tc.MoveMode.KeepAnchor)

                style = QTextListFormat()
                style.setStyle(QTextListFormat.Style.ListDisc if key == Qt.Key.Key_B else QTextListFormat.Style.ListDecimal)
                style.setNumberSuffix(')')

                previous = self.textCursor()
                previous.movePosition(previous.MoveOperation.PreviousBlock, tc.MoveMode.MoveAnchor)
                previous_list = previous.currentList()

                if previous_list:
                    # TODO: implement advanced list management
                    # if (tc.block().blockFormat().indent() + 1) == previous_list.format().indent():
                    #     previous_list.add(tc.block())
                    # elif (tc.block().blockFormat().indent() + 1) < previous_list.format().indent():
                    #     print(previous_list)

                    if tc.block().blockFormat().indent() >= previous_list.format().indent():
                        if previous_list.format().style() == QTextListFormat.Style.ListDecimal and key == Qt.Key.Key_N:
                            root_numbering = previous.block().textList().blockList().index(previous.block()) + 1
                            style.setNumberPrefix(f'{root_numbering}.')
                            style.setStyle(QTextListFormat.Style.ListUpperAlpha)

                        elif previous_list.format().style() == QTextListFormat.Style.ListDisc and key == Qt.Key.Key_B:
                            style.setStyle(QTextListFormat.Style.ListSquare)
                # if previous_list:
                #     if (tc.block().blockFormat().indent() + 1) != previous_list.format().indent():
                #         list = tc.createList(style)
                # else:

                list = tc.createList(style)

                return

            # if we call some of the existing shortcuts... forward to parent
            # TODO: dynamically load the existing shortcuts
            elif key in (Qt.Key.Key_H, Qt.Key.Key_V, Qt.Key.Key_R,
                         Qt.Key.Key_F, Qt.Key.Key_C, Qt.Key.Key_G,
                         Qt.Key.Key_A, Qt.Key.Key_E, Qt.Key.Key_S):
                super(self._win.__class__, self._win).keyPressEvent(e)

            else:
                super(Typer, self).keyPressEvent(e)

            return

        # same for Control modifier... forward to parent
        elif modifiers == Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_G, Qt.Key.Key_S):
            super(self._win.__class__, self._win).keyPressEvent(e)

        # some style to apply
        # TODO: need to be stored in external library / user defined
        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_B:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold)    # bold

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Q:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold, QColor(22, 155, 76))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_W:
            self.applyStyle(lambda x: x.bold(), lambda y: y.setBold, QColor(38, 125, 255))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D:
            self.applyStyle(None, None, QColor(68, 156, 205))

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_I:
            self.applyStyle(lambda x: x.italic(), lambda y: y.setItalic)    # italic

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_U:
            self.applyStyle(lambda x: x.underline(), lambda y: y.setUnderline)  # underline

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_H:
            # inserts a custom bullet (for Quran tafsir purpose, ayat separator)
            tc = self.textCursor()
            tc.beginEditBlock()
            bullet = '<span style="color:#9622d3;">\u06de</span>'

            # we first determine if we need extra spaces or no
            if self.textCursor().positionInBlock() != 0 and previous_character not in string.whitespace:
                tc.insertText(' ')

            next_char = self.next_character
            if not len(next_char) or next_char not in string.whitespace:
                bullet = f'{bullet} '

            tc.insertHtml(bullet)
            tc.endEditBlock()
            return

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_Equal, Qt.Key.Key_Minus):
            self.zoom(1 if current_text == '=' else -1)

        # forwarding to parent to jump through pages
        elif key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            return super(self._win.__class__, self._win).keyPressEvent(e)

        if not (key == Qt.Key.Key_Tab and self.auto_complete_available):
            # forward Tab only if we're sure there is no autocomplete to do
            super().keyPressEvent(e)

        if self.auto_complete_available:
            self.WL_autoComplete.setGraphicsEffect(self.WL_autoComplete_effect())
            self.displayPrediction()

        # finally, if Tab was pressed and there is an auto complete suggestion active
        if key == Qt.Key.Key_Tab and self.auto_complete_available and self.WL_autoComplete.isVisible():
            # inserting the suggestion
            self.insertPlainText(self.WL_autoComplete.text())

            # resetting the auto_complete label
            # self.WL_autoComplete.setText('')
            # self.WL_autoComplete.hide()
            self.word = ""

            # update cursor
            tc = self.textCursor()
            tc.select(tc.SelectionType.WordUnderCursor)

            if next_character not in T.Keys.NewWord.values() and \
                    tc.selectedText() not in self.prophet_match and \
                    tc.selectedText() not in self.Allah_match:
                # adding a space since the previous word should be complete
                # if the next character is in the new word characters, we skip the space after
                self.insertPlainText(" ")

            self.new_word = True
            self.WL_autoComplete.setGraphicsEffect(self.WL_autoComplete_lighteffect())
            self.displayPrediction()
            # self.guessTense()

        # if there is a character we update the changed state
        if len(current_text):
            self.contentEdited.emit()

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
            return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasImage():
            # special behavior if we have an image
            # TODO: should be different, maybe only accept vector images ? maybe ask for a filename path ?
            image = QImage(QVariant(source.imageData()).value())

            # convert the image as a bytearray to source
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, 'PNG')
            img_str = ba.toBase64().data()

            # insert the image data
            cursor = self.textCursor()
            cursor.insertHtml(f'<img style="width:100%" src="data:image/png;base64,{img_str.decode()}" />')

        # continue with the default behavior
        super().insertFromMimeData(source)

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
            M_main = self.createStandardContextMenu(pos)

        except TypeError as e:
            G.exception(e)
            M_main = self.createStandardContextMenu()

        # allow the user to add a separator, this one will be used later when exporting as PDF, it marks
        # the text displayed on the column along the PDF page preview

        M_main.insertSeparator(M_main.actions()[0])

        A_addSeparator = QAction('Add translation separator', M_main)
        A_addSeparator.triggered.connect(lambda: self.insertHtml('<hr />'))
        M_main.insertAction(M_main.actions()[0], A_addSeparator)

        # getting the word
        tc = self.cursorForPosition(pos)
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        text = tc.selectedText()
        html_text = T.HTML.extractTextFragment(tc.selection().toHtml())

        p = tc.positionInBlock()
        tc.select(tc.SelectionType.BlockUnderCursor)
        block_text = tc.selectedText()
        block_text = '.'.join([(s[0].lower() + s[1:]) if len(s) else '' for s in T.Regex.Predikt_hard_split.split(block_text)])
        tokenized_block_text = [token for token in T.Regex.tokenize(block_text)]

        # getting the block
        c_block = self.cursorForPosition(pos)
        c_block.select(QTextCursor.SelectionType.BlockUnderCursor)
        block = c_block.block()
        html_block = T.HTML.extractTextFragment(c_block.selection().toHtml())

        if S.LOCAL.audio_map:
            block_audio = self.W_audioMap.getSolver(block.blockNumber())
            if block_audio > -1:
                paragraph_realtime = T.HTML.paragraphTime(html_block)
                A_openAudioAtTime = QAction(f"Open audio at time", M_main)
                A_openAudioAtTime.triggered.connect(partial(S.GLOBAL.AUDIOMAP.play, block_audio, paragraph_realtime))
                M_main.insertAction(M_main.actions()[0], A_openAudioAtTime)

        if T.HTML.hasParagraphTime(html_block):
            paragraph_realtime = T.HTML.paragraphTime(html_block)
            paragraph_time = strftime('%Y-%m-%d %H:%M:%S', localtime(paragraph_realtime))

            A_editDateTime = QAction('Edit datetime anchor', M_main)

            def edit_paragraph_time():
                epoch, ok = DateTimePickerDialog.getDateTime(t=paragraph_realtime)
                if ok:
                    previous_pos = self.textCursor().position()

                    html = self.toHtml()
                    html = html.replace(str(paragraph_realtime), str(int(epoch)))
                    self.setHtml(html)

                    tc = self.textCursor()
                    tc.setPosition(previous_pos)
                    self.setTextCursor(tc)
                    self.ensureCursorVisible()

                    self.solveAudioMap()

            A_editDateTime.triggered.connect(edit_paragraph_time)
            M_main.insertAction(M_main.actions()[0], A_editDateTime)

            A_dateTime = QAction(f"Datetime : {paragraph_time}", M_main)
            A_dateTime.setDisabled(True)
            M_main.insertAction(M_main.actions()[0], A_dateTime)

        else:
            A_setDateTime = QAction('Set datetime anchor', M_main)

            def edit_paragraph_time():
                epoch, ok = DateTimePickerDialog.getDateTime()
                if ok:
                    T.HTML.insertParagraphTime(self.textCursor(), t=int(epoch))
                    self.solveAudioMap()
            A_setDateTime.triggered.connect(edit_paragraph_time)
            M_main.insertAction(M_main.actions()[0], A_setDateTime)

        # insert a separator to the beginning
        M_main.insertSeparator(M_main.actions()[0])

        # if its recognized as an audio (thanks to the Highlighter class)
        if T.Regex.src_audio_path.match(html_text):
            # extract the correct filename
            audio_file = T.Regex.src_audio_path.sub(r'\1', html_text)
            audio_path = os.path.join(S.GLOBAL.audio_record_path, f'{audio_file}.ogg')

            def removeAudio(path: str, cursor_pos: QPoint):
                """
                remove the current audio file
                :param path: the filename
                :param cursor_pos: the cursor position where the popup has been submitted
                """
                # require confirmation to delete
                dialog = QMessageBox.question(
                    None,
                    f"{G.__app__} - Remove audio file",
                    f"<b>Remove audio file</b> in record folder also ?\n<i>{path}</i>",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )

                if dialog == QMessageBox.StandardButton.Yes:
                    try:
                        os.remove(path)

                    except PermissionError as exp:
                        G.exception(exp)
                        QMessageBox.critical(
                            None,
                            f"{G.__app__} - Failed to remove file",
                            f"Can't remove file, still opened ?\n<i>{path}</i>",
                            QMessageBox.StandardButton.Ok
                        )

                # if the user says "No", we just remove the text from the document
                if dialog != QMessageBox.StandardButton.Cancel:
                    c = self.cursorForPosition(cursor_pos)
                    c.select(QTextCursor.SelectionType.WordUnderCursor)
                    c.removeSelectedText()

            M_main.insertSeparator(M_main.actions()[0])

            # adding the remove audio menu
            A_removeAudio = QAction('Remove audio', M_main)
            A_removeAudio.triggered.connect(partial(removeAudio, audio_path, pos))
            M_main.insertAction(M_main.actions()[0], A_removeAudio)

            # adding the play audio menu
            if '_' in audio_file:
                real_time = int(audio_file.split('_')[0])
            else:
                real_time = S.GLOBAL.audio_record_epoch + int(audio_file)
            time_str = strftime('%Y-%m-%d %H:%M:%S', localtime(real_time))
            A_openAudio = QAction(f'Open audio ({time_str})', M_main)
            A_openAudio.triggered.connect(lambda: os.startfile(audio_path))
            M_main.insertAction(M_main.actions()[0], A_openAudio)

            AS_audioRecord = QAction('Audio Record', M_main)
            AS_audioRecord.setDisabled(True)
            M_main.insertAction(M_main.actions()[0], AS_audioRecord)

        checked = T.SPELL.word_check(text)

        tc = self.cursorForPosition(pos)
        tc.select(QTextCursor.SelectionType.WordUnderCursor)

        # if the block's flagged as incorrect
        if block.userData().state == G.State_Correction and not checked:
            # we add suggestions for the given word
            M_suggestions = QMenu(f'Suggestions for "{text}"', M_main)
            cnt = self.buildSpellMenu(text, tc, M_suggestions)

            # add the word to the dictionary if it's not (flagged as incorrect means its not in the dictionary
            A_addWord = QAction(f'Add "{text}" to dictionary', M_main)
            A_addWord.setData(text)
            M_main.insertAction(M_main.actions()[0], A_addWord)
            A_addWord.triggered.connect(partial(T.SPELL.add, text))

            # if suggestions for the word are at least one we display the menu
            if cnt >= 1:
                M_main.insertMenu(M_main.actions()[0], M_suggestions)

        x1, x2, y, z = None, None, None, None
        for i, x2, y, z in tokenized_block_text:
            if (i + len(text)) >= p >= i:
                break
            x1 = x2

        if S.GLOBAL.check_grammar:
            solutions = S.GLOBAL.CORPUS.solve(x1, x2, y, z)

            if solutions:
                original_tc = self.cursorForPosition(pos)
                original_tc.select(QTextCursor.SelectionType.WordUnderCursor)

                M_grammar = QMenu(f'Grammar for "{text}"', M_main)

                if len(solutions['lemma']):
                    M_grammar.addSeparator()
                    self.insertItemsToMenu(
                        [c for c in solutions['lemma']],
                        original_tc,
                        M_grammar
                    )

                if len(solutions['roles']):
                    M_grammar.addSeparator()
                    self.insertItemsToMenu(
                        [c for c in solutions['roles']],
                        original_tc,
                        M_grammar
                    )

                if len(solutions['ancestors']):
                    M_grammar.addSeparator()
                    self.insertItemsToMenu(
                        [c for c in solutions['ancestors']],
                        original_tc,
                        M_grammar
                    )

                A_upvote_grammar = QAction('Upvote grammar')
                A_upvote_grammar.triggered.connect(partial(
                    self.upvoteGrammar,
                    S.GLOBAL.CORPUS.get_solution(x1, x2, y, z),
                    block_text
                ))
                M_grammar.insertAction(M_grammar.actions()[0], A_upvote_grammar)

                M_main.insertMenu(M_main.actions()[0], M_grammar)

        if checked:
            # adding synonyms suggestions
            M_synonyms = QMenu(f'Synonyms for "{text}"', M_main)
            cnt = self.buildSynMenu(text, tc, M_synonyms)

            # if we got some synonyms
            if cnt >= 1:
                M_main.insertMenu(M_main.actions()[0], M_synonyms)

            # if word's flagged as a verb
            # TODO: add it as a signal to enable / disable a button in the Toolbar
            # TODO: batch the forms in a frozenset
            is_verb = self.cursor.execute(f'SELECT source FROM conjugaison WHERE forme="{text}"').fetchone()

            # if selection is a verb, display the menu...
            if is_verb:
                A_conjugate = QAction('Conjugate...', M_main)
                A_conjugate.triggered.connect(partial(self.openConjugate, tc, is_verb[0]))
                M_main.insertAction(M_main.actions()[0], A_conjugate)

        # adding a section "Edit" for suggestion, dictionary ops
        M_main.insertSeparator(M_main.actions()[0])
        AS_audioRecord = QAction('Lang', M_main)
        AS_audioRecord.setDisabled(True)
        M_main.insertAction(M_main.actions()[0], AS_audioRecord)

        # displaying the final popup menu
        M_main.exec(global_pos)

    def clear(self):
        super().clear()
        self.textCursor().setBlockFormat(self.default_blockFormat)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        self.W_audioMap.resize(5, a0.size().height())
        super().resizeEvent(a0)
        self.graphAudioMap()
        self.solveAudioMap()

    def wheelEvent(self, e: QWheelEvent) -> None:
        if e.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.zoom(1 if e.angleDelta().y() > 0 else -1)

        super().wheelEvent(e)
        self.W_audioMap.update()

    def zoom(self, direction=1):
        temp_page = S.LOCAL.BOOK.Page(
            T.Regex.complete_page_filter(self.toHtml()),
            self.textCursor().position()
        )

        G.__font_size__ += direction

        T.Regex.update()
        self.document().setDefaultStyleSheet(T.QOperator.ApplyDefault.DocumentStyleSheet())
        self.setHtml(temp_page.content)

        tc = self.textCursor()
        tc.setPosition(temp_page.cursor)
        self.setTextCursor(tc)
        self.ensureCursorVisible()

        S.GLOBAL.font_size = G.__font_size__
        S.GLOBAL.saveSetting('font_size')


class TyperHighlighter(QSyntaxHighlighter):
    """
    A simple Highlighter
    """
    typer: Typer

    # defining some formats
    err_format = QTextCharFormat()
    err_format.setUnderlineColor(Qt.GlobalColor.red)
    err_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

    audio_format = QTextCharFormat()
    audio_format.setForeground(QColor(255, 125, 35))
    audio_format.setTextOutline(QPen(QColor(255, 125, 35), 1))

    ref_format = QTextCharFormat()
    ref_format.setForeground(QColor(255, 35, 45))
    ref_format.setFontWeight(800)

    grammar_format = {}
    grammar_colors = [
        QColor(6, 24, 38),
        QColor(31, 48, 17),
        QColor(51, 37, 15),
        QColor(72, 12, 35)
    ]
    for n in range(1, 5):
        grammar_format[n] = QTextCharFormat()
        grammar_format[n].setBackground(grammar_colors[n - 1])
        # grammar_format[n].setUnderlineColor(grammar_colors[n - 1].lighter(300))
        # grammar_format[n].setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)

    def __init__(self, parent=None, *args):
        self.typer = parent
        super(TyperHighlighter, self).__init__(*args)

    def highlightBlock(self, text):
        """
        Overridden QSyntaxHighlighter method to apply the highlight
        """
        if not T.SPELL.loaded or not len(text):
            return

        # we define a default BlockUser State data scanning the words
        data = QTextBlockUserData()
        data.state = state = G.State_Default

        previous_word = None

        text = text.replace(chr(T.TEXT.para_char), '')
        text = text.replace(chr(T.TEXT.audio_char), '')

        if len(text):
            text = text[0].lower() + text[1:]

        S.POOL.start(
            S.GLOBAL.CORPUS.Analyze(
                T.Regex.tokenize(text),
                S.GLOBAL.CORPUS,
                S.GLOBAL.CORPUS.get_solutions
            ),
            uniq='grammar_note'
        )

        for pos, x, y, z in T.Regex.tokenize(text):
            if len(y) > 1:
                # a word with # around is a reference
                # TODO: should match a regex pattern, same for the audio

                solution = S.GLOBAL.CORPUS.get_solution(previous_word, x, y, z)
                # grammar_note = 0
                if solution and solution.normalized_score():
                    self.setFormat(pos, len(y), self.grammar_format[solution.normalized_score()])

                elif [*map(ord, y)] == [9834, T.TEXT.audio_char]:
                    self.setFormat(pos, len(y), self.audio_format)

                elif y.startswith("#") and y.endswith("#"):
                    self.setFormat(pos, len(y), self.ref_format)
                    state = G.State_Reference

                # otherwise we check if word' spelling is invalid
                if not T.SPELL.word_check(y):
                    # if we reach this point it means the word is incorrect and have some spell suggestions
                    self.setFormat(pos, len(y), self.err_format)

                    state = G.State_Correction

                previous_word = x

                # finally setting the data state
                data.state = state

        # applying the data
        self.setCurrentBlockUserData(data)


class TyperAudioMap(QWidget):
    def __init__(self, parent: QTextEdit = None):
        super().__init__(parent)
        self.page = ''
        self._map = {}
        self.solved = {}
        self.scrollX = 0

    @property
    def map(self):
        return self._map

    @map.setter
    def map(self, val):
        self._map = val

    def setMap(self, map: dict):
        self.map = map
        self.update()

    def addSolver(self, solver: dict):
        self.solved.clear()
        self.solved.update(solver)
        self.update()

    def getSolver(self, block_id: int):
        try:
            return self.solved[block_id]

        except KeyError:
            return -2

    def update(self) -> None:
        self.scrollX = self.parent().verticalScrollBar().value()
        super().update()

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.translate(0, -self.scrollX)

        for i, bound in enumerate(self._map.values()):
            s = self.getSolver(i)

            w = 3 if s >= -1 else 2
            c = self.palette().highlight() if s > 0 else self.palette().alternateBase()

            qp.setBrush(c)
            qp.drawRect(0, int(bound[0]), w, int(bound[1]))
