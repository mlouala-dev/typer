# بسم الله الرحمان الرحيم
import copy
import os
import re
import html
import sqlite3
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from functools import partial

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from UI.BasicElements import LineLayout, ListWidget, AyatModelItem, NumberModelItem, SearchField
from tools import G, S, T
from tools.PDF import PDF_Exporter


class BreadCrumbs(QWidget):
    goto = pyqtSignal(int)

    class Level(QLabel):
        colors = ['267dff', '73c3ff', 'ffffff']
        hoverChanged = pyqtSignal(bool)
        clicked = pyqtSignal(QMouseEvent, int, int)

        def __init__(self, level=1, parent=None):
            self.level = level
            self.last = level == 3
            self.hover = False
            self.nextHover = False
            self.t = ''
            self.n = -1

            super().__init__('', parent)
            self.setContentsMargins(10, 3, 25, 1)
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            self.setMouseTracking(True)

        def mousePressEvent(self, e: QMouseEvent):
            if e.button() == 1:
                self.clicked.emit(e, self.level, self.n)

        def enterEvent(self, e):
            self.hover = True
            self.hoverChanged.emit(True)
            self.repaint()

        def leaveEvent(self, e):
            self.hover = False
            self.hoverChanged.emit(False)
            self.repaint()

        def formatText(self, text=''):
            num = f'{self.n}.&#x200e; ' if self.n != -1 else ''
            return f'{num}<b><span style="color:#{self.colors[self.level - 1]}">{text}</span></b>'

        def setText(self, p_str):
            self.t = p_str
            super().setText(self.formatText(self.t))

        def setNum(self, num):
            self.n = num
            super().setText(self.formatText(self.t))

        def nextStateChanged(self, state):
            self.nextHover = state
            self.repaint()

        def paintEvent(self, event):
            palette: QPalette
            palette = self.palette()
            default_bg = QBrush(palette.base())
            on_color = QBrush(palette.alternateBase())
            on_line = palette.alternateBase() if not self.hover else palette.highlight()
            button_color = on_color if self.hover else default_bg
            qp = QPainter(self)
            qp.setRenderHint(QPainter.Antialiasing)
            qp.setPen(Qt.NoPen)
            qp.setBrush(button_color)
            if self.level == 1:
                qp.drawRoundedRect(QRect(0, 0, self.width() // 2 + 15, self.height()), 15, 15)
            else:
                qp.drawRect(QRect(0, 0, self.width() // 2, self.height()))

            if not self.last:
                qp.setBrush(default_bg if not self.nextHover else on_color)
                qp.drawRect(QRect(self.width() // 2, 0, self.width() // 2 + 5, self.height()))

            qp.setBrush(button_color)
            qp.drawPolygon(QPolygon([
                QPoint(self.width() // 2, -10),
                QPoint(self.width() // 2, self.height() + 10),
                QPoint(self.width() - 20, self.height() + 10),
                QPoint(self.width(), self.height() // 2),
                QPoint(self.width() - 20, -10)
            ]), Qt.OddEvenFill)

            qp.setPen(QPen(on_line, 3))
            qp.drawLines([QLine(
                    QPoint(self.width() - 20, self.height() + 10),
                    QPoint(self.width(), self.height() // 2)
                ), QLine(
                    QPoint(self.width(), self.height() // 2),
                    QPoint(self.width() - 20, -10)
                )
            ])

            super().paintEvent(event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(G.get_font(1.2))
        self.setFixedHeight(30)
        self.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout()
        self.setMouseTracking(True)

        self.l1 = BreadCrumbs.Level(1)
        self.l1.clicked.connect(self.crumbPressed)
        self.l2 = BreadCrumbs.Level(2)
        self.l2.clicked.connect(self.crumbPressed)
        self.l3 = BreadCrumbs.Level(3)
        self.l2.hoverChanged.connect(self.l1.nextStateChanged)
        self.l3.hoverChanged.connect(self.l2.nextStateChanged)

        self.levels = [self.l1, self.l2, self.l3]

        layout.addWidget(self.l1, stretch=0)
        layout.addWidget(self.l2, stretch=0)
        layout.addWidget(self.l3, stretch=0)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        self.setLayout(layout)

    def setLevel(self, level: int, text: str = '', num: int = -1):
        self.levels[level - 1].setHidden(text == '')
        self.levels[level - 1].setText(text)
        self.levels[level - 1].setNum(num)

    def crumbPressed(self, e: QMouseEvent, level: int, num: int = -1):
        global_pos = self.mapToGlobal(e.pos())
        menu = QMenu()

        if level == 1:
            for kitab in S.LOCAL.BOOKMAP.kutub.values():
                action = QAction(f'{kitab.id}.\u200e{kitab.name} ({int(kitab.page)})', menu)
                if kitab.id == num:
                    action.setIcon(G.icon('Accept'))
                action.triggered.connect(partial(self.goto.emit, int(kitab.page) - 1))
                menu.addAction(action)

        elif level == 2:
            kitab = S.LOCAL.BOOKMAP.getKitab(S.LOCAL.BOOKMAP.pages[S.LOCAL.page].kid)
            for bab in kitab.abwab:
                action = QAction(f'{bab.id}.\u200e{bab.name} ({int(bab.page)})', menu)
                if bab.id == num:
                    action.setIcon(G.icon('Accept'))
                action.triggered.connect(partial(self.goto.emit, int(bab.page) - 1))
                menu.addAction(action)

        menu.exec_(global_pos)

    @G.log
    def updatePage(self, page):
        if S.LOCAL.PDF:
            p = S.LOCAL.BOOKMAP.getPage(page)

            try:
                k = S.LOCAL.BOOKMAP.getKitab(p.kid)
                kitab = k.name
            except KeyError:
                kitab = ''

            try:
                b = S.LOCAL.BOOKMAP.getKitab(p.kid).getBab(p.bid)
                bab = b.name
            except KeyError:
                bab = ''

            if len(p.hids):
                h = S.LOCAL.BOOKMAP.getHadithByPage(page)[0]
                hadith = h.content
                hadith_num = h.sub_id
                if len(hadith) > 30:
                    hadith = f'{hadith[:30]} (...)'
            else:
                hadith = ''
                hadith_num = -1

            self.setLevel(1, kitab, p.kid)
            self.setLevel(2, bab, p.bid)
            self.setLevel(3, hadith, hadith_num)


class TopicsBar(QWidget):
    """
    The panel display the current topics for the given page
    """
    def __init__(self, parent=None):
        super(TopicsBar, self).__init__(parent)
        # FIXME:atm the domains doesn't work
        self.current_page = 0
        self.topic_dialog = TopicsDialog(parent, self)

        self.setMaximumWidth(600)
        self.setFixedHeight(50)
        self.setContentsMargins(0, 0, 0, 0)

        topic_layout = QHBoxLayout()
        self.topic_overview = QLabel("")
        self.topic_overview.setFont(G.get_font(1.2))

        self.topic_edit = QPushButton("...")
        self.topic_edit.setFixedWidth(45)
        self.topic_edit.clicked.connect(self.topic_dialog.showTopics)

        self.topics_settings = QPushButton(G.icon('Setting-Tools'), "")
        self.topics_settings.setFixedWidth(45)

        topic_layout.addWidget(self.topic_overview, 0)
        topic_layout.addWidget(self.topic_edit, 0)
        topic_layout.addWidget(self.topics_settings, 0)
        topic_layout.setStretch(1, 0)
        topic_layout.setContentsMargins(10, 0, 10, 0)
        topic_layout.setSpacing(0)

        self.setLayout(topic_layout)

    def changePage(self, page=0):
        # we update the panel's label with a list of all the topics
        try:
            self.topic_overview.setText(', '.join(map(str, sorted(S.LOCAL.TOPICS.pages[page]))))

        except KeyError as e:
            G.exception(e)
            self.topic_overview.setText('')

        # defining the current page
        self.current_page = page


class TopicsDialog(QDialog):
    """
    This allows you to pick the topics linked with the current page
    """
    reference: TopicsBar

    class TopicFind(QLineEdit):
        """
        a simple lineEdit search widget
        """
        def __init__(self, parent=None):
            super(TopicsDialog.TopicFind, self).__init__(parent)

        def keyPressEvent(self, e: QKeyEvent):
            """
            Overrides the keypress event
            """
            # if user valids by pressing Enter we add the currently highlighted topic,
            if e.key() == Qt.Key.Key_Return:
                self.parent().updateTopics()

            # otherwise we update the list
            else:
                super(TopicsDialog.TopicFind, self).keyPressEvent(e)

    def __init__(self, parent=None, reference=None):
        super(TopicsDialog, self).__init__(parent)
        # internal process
        self.reference = reference
        self.original_topics = set()

        # UI
        self.pointer_rect = QRect(0, 30, 1, 1)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        self.setContentsMargins(5, 5, 5, 5)
        self.setFixedWidth(400)
        self.setFixedHeight(400)
        self.find_field = TopicsDialog.TopicFind(self)
        self.find_field.textChanged.connect(self.filterTopics)
        main_layout.addLayout(LineLayout(self, 'Find / Add : ', self.find_field))

        self.topic_list = QListView(self)
        self.topic_list.doubleClicked.connect(self.updateTopics)
        self.model = QStandardItemModel(self.topic_list)

        self.topic_list.setModel(self.model)
        main_layout.addWidget(self.topic_list)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.ok = QPushButton('OK')
        self.ok.pressed.connect(self.validForm)
        self.cancel = QPushButton('Cancel')
        self.cancel.pressed.connect(self.cancelForm)
        main_layout.addLayout(LineLayout(self, self.ok, self.cancel))

    def validForm(self):
        """
        Valid the current list of topics and update the settings
        """
        # reloading the same page for the TopicsBar
        self.reference.changePage(self.reference.current_page)

        # making no duplicate list of the topics
        new = frozenset(S.LOCAL.TOPICS.pages[self.reference.current_page])    # the ones we need to add
        old = frozenset(self.original_topics)   # the ones we need to remove

        # updating signals
        S.LOCAL.saveTopics(list(new.difference(old)), list(old.difference(new)))
        super(TopicsDialog, self).close()

    def cancelForm(self):
        """
        Cancel the current changes
        """
        # revert to self.original_topics
        # self.reference.topics['pages'][self.reference.current_page] = self.original_topics

        # reloading the same page
        # self.reference.changePage(self.reference.current_page)
        super(TopicsDialog, self).close()

    def showTopics(self):
        """
        It displays the topics in the list
        :return:
        """
        self.find_field.setText("")

        # make a copy of the original topics from reference
        try:
            self.original_topics = copy.copy(S.LOCAL.TOPICS.pages[self.reference.current_page])
        except KeyError:
            pass

        # visual ops
        self.filterTopics()
        self.show()

    def filterTopics(self, text_filter=''):
        """
        Filter the view depending on the given filter
        :param text_filter: the text we filter through
        """

        # extending the res array with all the topics by page
        res = set()

        for page_topics in S.LOCAL.TOPICS.pages.values():
            res.update(page_topics)

        # visual settings for result's display
        font = G.get_font(1.4)
        extra_font = G.get_font(1.4, weight=400, italic=True)

        self.model.clear()
        i = 1
        # through this list of topics
        for t in sorted(frozenset(res)):
            t: S.LOCAL.TOPICS.Topic

            if S.LOCAL.page in S.LOCAL.TOPICS.pages:
                # this should display all topics, but we only need the ones for the current page
                if text_filter == '' and t not in S.LOCAL.TOPICS.pages[S.LOCAL.page]:
                    continue

                # this will display irrelevant topics
                if text_filter != '' and t in S.LOCAL.TOPICS.pages[S.LOCAL.page]:
                    continue

            # standard display if no filter active
            if text_filter == '':
                item = QStandardItem(t.name)
                item.setFont(font)

            # custom display if filter's active
            else:
                item = QStandardItem(t.name)
                item.setFont(extra_font)
                item.setForeground(QColor(125, 125, 125))

            # if text_filter matches current topic
            if text_filter in t.name:
                # adding the item
                self.model.appendRow(item)

                if i == 1:
                    self.topic_list.setCurrentIndex(self.model.index(0, 0))

                i += 1

    def updateTopics(self):
        """
        update the current topics
        :return:
        """
        # determining the name of the topic we'll add
        try:
            item_text = self.model.itemFromIndex(self.topic_list.selectedIndexes()[0]).text()

        # if there is no selection, setting the topic name based on the search field
        except IndexError:
            item_text = self.find_field.text()

        # upgrading the lists
        S.LOCAL.TOPICS.addTopic(item_text, 'theme', S.LOCAL.page)

        self.find_field.clear()
        self.filterTopics()

    def keyPressEvent(self, e:QKeyEvent):
        """
        Overrides keyPress to catch the Delete button pressed
        """
        if e.key() == Qt.Key.Key_Delete:
            try:
                # getting the currently selected
                text = self.model.itemFromIndex(self.topic_list.selectedIndexes()[0]).text()

                # updating the variables
                S.LOCAL.TOPICS.removeTopicFromPage(text, S.LOCAL.page)
                self.find_field.clear()

                # now refresh the topics' list
                self.filterTopics()
                e.ignore()

            except IndexError:
                pass

        elif e.key() == Qt.Key.Key_Tab:
            try:
                print(self.model.itemFromIndex(self.topic_list.rootIndex()).text())
            except IndexError:
                print('no item')

        super(TopicsDialog, self).keyPressEvent(e)


class GlobalSearch(QDialog):
    """
    A complex search dialog
    """
    # arbitrary parameters to catch some characters before and after for visual feedback
    # in the list it will display results as "lorem <i>ipsum</i> dolor met" highlighting
    # the current match
    head_len = 20
    tail_len = 50

    re_harakat = re.compile("[" + "|".join("ًٌٍَُِّْ") + "]")

    def __init__(self, parent=None):
        # here we'll copy the current project to perform our search
        self._book = {}

        super(GlobalSearch, self).__init__(parent)

        self.setFixedSize(800, 600)
        self.setWindowTitle("Find & Replace")
        self.setWindowIcon(G.icon("Google-Custom-Search"))
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        widgets_layout = QVBoxLayout(self)
        widgets_layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(widgets_layout)
        self.find_field = QLineEdit()
        self.replace_check = QCheckBox("Replace : ")
        self.replace_field = QLineEdit()
        self.replace_check.stateChanged.connect(self.replace_field.setEnabled)
        self.replace_field.setDisabled(True)
        widgets_layout.addLayout(LineLayout(self, 'Find : ', self.find_field, self.replace_check, self.replace_field))

        self.regex_check = QCheckBox("Regexp")
        self.word_check = QCheckBox("Whole word")
        self.case_check = QCheckBox("Case sensitive")
        self.harakat_check = QCheckBox("Ignore harakat")
        self.page_search_check = QCheckBox("Search in Page")
        self.code_search_check = QCheckBox("Search in HTML Code")
        widgets_layout.addLayout(LineLayout(self, self.regex_check, self.word_check, self.case_check,
                                            self.harakat_check, self.page_search_check, self.code_search_check))

        ayat_model_ar = AyatModelItem(font=G.get_font(1.4))
        num_model = NumberModelItem()
        self.result_list = ListWidget(self, models=(ayat_model_ar, num_model))
        self.result_list.setColumnCount(2)
        self.result_list.setColumnWidth(0, self.width() - 100)
        self.result_list.setColumnWidth(1, 100)
        self.result_list.itemClicked.connect(self.itemClicked)

        widgets_layout.addWidget(self.result_list, stretch=1)

        self.result_label = QLabel()
        widgets_layout.addWidget(self.result_label)

        self.search_button = QPushButton(G.icon('Search-Plus'), " Search")
        self.search_button.clicked.connect(self.search)
        self.replace_button = QPushButton(G.icon('Text-Replace'), "Replace")
        self.replace_button.clicked.connect(self.replace)

        widgets_layout.addLayout(LineLayout(self, self.search_button, self.replace_button))

        self.progress = QProgressBar()
        self.progress.setFixedHeight(5)
        self.progress.setTextVisible(False)
        main_layout.addLayout(widgets_layout, 1)
        main_layout.addWidget(self.progress, 0)

    def get_page(self, page: str) -> str:
        """
        Basic cleanup of the page, actually just used to remove all HTML tags
        :param page: the page's html code
        :return: the reformatted page
        """
        if not self.code_search_check.isChecked():
            # matching all tags between < />
            # TODO: update, maybe by loading a plainText version of the page ?
            page = re.sub(r"<.*?>", "", page)

        return page

    def get_needle(self, needle: str) -> str:
        """
        Performs some tweaks on the search needle
        :param needle: the search needle
        :return: a correctly formed pattern based on the options
        """
        exit_chars = "|".join(T.Keys.NewWord.values())

        # if regex we just get it has it is
        if self.regex_check.isChecked():
            search_pattern = needle

        # if there is no replacement needed we convert the search needle to a regex one
        elif not self.replace_check.isChecked():

            # escaping all special characters
            needle = re.escape(needle)

            # if "match only word" is checked
            if self.word_check.isChecked():
                search_pattern = fr"(^|.{{0,{self.head_len - 1}}}[{exit_chars}])({needle})([{exit_chars}].{{0,{self.tail_len - 1}}}|$)"

            # otherwise we make sure we get character before and after for visual feedback
            else:
                search_pattern = fr"(.{{0,{self.head_len}}})({needle})(.{{0,{self.tail_len}}})"

        # if replacement is active we only match the needed needle
        else:
            # escaping all special characters
            needle = re.escape(needle)

            # head and tail to make sure complete words
            if self.word_check.isChecked():
                search_pattern = fr"(^|{exit_chars})({needle})({exit_chars}|$)"

            else:
                search_pattern = fr"{needle}"

        return search_pattern

    def get_search_field(self):
        """
        returns the current search domain, restraining to the active page only if checked
        """
        if not self.page_search_check.isChecked():
            return self._book

        else:
            # getting the active page
            current_page = self.parent().page_nb
            return {current_page: self._book[current_page]}

    def search_in_doc(self, needle: str, replacement=None) -> [tuple]:
        """
        perform a search using the Qt QDocument search feature
        :param needle: the search needle
        :param replacement: replacement text
        """
        results = list()
        new_book = {}
        total, perc = 0, 100.0 / len(self._book)
        search_options = QTextDocument.FindFlags(0)

        # applies the flag to the QTextDocument
        for widget, flag in zip(
                [self.case_check, self.word_check],
                [QTextDocument.FindCaseSensitively, QTextDocument.FindWholeWords]
        ):
            if widget.isChecked():
                search_options |= flag

        # preparing the search needle
        search_needle = QRegExp(needle) if self.regex_check.isChecked() else needle

        # for every page in the current domain of research
        for page in self.get_search_field():
            pos = 0

            # removing all harakats of the doc if checked
            page_content = self.re_harakat.sub("", self._book[page]) if self.harakat_check.isChecked() else self._book[page]

            # creating a temporary QTextDocument to load the page
            _doc = QTextDocument()
            _doc.setHtml(page_content)

            # while we find occurence
            while pos != -1:
                res = _doc.find(search_needle, pos, options=search_options)
                pos = res.position()

                # pos -1 means we hit the end of document
                if pos != -1:
                    # FIXME: this won't work with a regex pattern since we use the length of the needle
                    # getting the characters before, the match, and characters after
                    text = (
                        res.block().text()[max(0, res.positionInBlock() - self.head_len):res.positionInBlock()],
                        res.block().text()[res.positionInBlock(): res.positionInBlock() + len(needle)],
                        res.block().text()[res.positionInBlock() + len(needle):
                                           min(len(res.block().text()), res.positionInBlock() + self.tail_len)]
                    )

                    # if replacement text us provided
                    if replacement is not None:

                        # popping the old text
                        res.removeSelectedText()

                        # then insert the new one
                        res.insertText(replacement)

                        # and update the book
                        new_book[page] = res.document().toHtml()

                    # storing every match
                    results.append((page, text, res.position()))

            total += perc
            self.progress.setValue(int(total))

        # if replacement wanted we update the book
        if replacement is not None:
            self._book.update(new_book)

        return results

    def search_in_code(self, needle: str) -> [tuple]:
        """
        Performs a hardcode search by ourselves
        :param needle: the serach needle
        :return: a list of result tuples
        """
        results = list()
        total, perc = 0, 100.0 / len(self._book)

        # settings regex flags depending on options checked
        flags = re.M
        if not self.case_check.isChecked():
            flags |= re.I

        # for every page in the current domain of research
        for page in self.get_search_field():

            # formatting our pattern
            search_pattern = self.get_needle(needle)

            # formatting our page
            page_content = self.re_harakat.sub("", self._book[page]) if self.harakat_check.isChecked() else self._book[page]

            # perform the regex search
            match = re.findall(search_pattern, page_content, flags)

            if match:
                # append all the results to the results' list,
                # the regex pattern will return 3 groups
                for m in match:
                    results.append((page, m, None))

            total += perc
            self.progress.setValue(int(total))

        return results

    def replace_in_code(self, needle: str, replacement: str) -> (int, int):
        """
        Same as the search_in_code but replacing
        :param needle: the search needle pattern
        :param replacement: the replacement pattern
        :return: a tuple of the number of changes and new book's length
        """
        new_book = {}
        changes = 0
        total, perc = 0, 100.0 / len(self._book)

        # for every page of the book
        for page in self._book:
            total += perc
            self.progress.setValue(int(total))

            # returns the page updated and the changes operated
            new_book[page], change = re.subn(
                self.get_needle(needle),
                replacement,
                self.get_page(self._book[page])
            )
            changes += change

        # updating the book with the page modified
        self._book.update(new_book)

        return changes, len(new_book)

    def format_result(self, result: list) -> str:
        """
        Format the results we got from the search_in_doc or search_in_code to the list
        :param result: a tuple of three elements : (page, text, position)
        :return: formatted result : (before match)(match)(after match)
        """
        # extract results
        h, n, t = result

        # beginning of result
        head = ("..." + " ".join(h.split(" ")[1:])) if len(h) == self.head_len else h

        # ending of result
        tail = (" ".join(t.split(" ")[:-1]) + "...") if len(t) == self.tail_len else t

        return "".join([head, n, tail])

    def search(self):
        """
        The main search wrapper which call the sub functions
        """
        pages = set()

        # cleaning the list of results
        self.result_list.clear()

        # if we need to search in the whole document including HTML code
        if self.code_search_check.isChecked():
            results = self.search_in_code(self.find_field.text())

        # otherwise we just perform a QTextDocument search
        else:
            results = self.search_in_doc(self.find_field.text())

        # for every result, we format them
        for page, result, obj in sorted(results, key=lambda x: x[0]):
            res = self.format_result(result)

            # if HTML code is going to be displayed we unescape it first
            if not self.code_search_check.isChecked():
                res = html.unescape(res)

            # adding the item widget to the list
            item = QTreeWidgetItem([res, str(page)])
            item.setData(2, 0, obj)
            self.result_list.addTopLevelItem(item)

            # updating pages for result
            pages.add(page)

        # displaying a light report of search result
        self.result_label.setText(f'"{self.find_field.text()}" found {len(results)} time in {len(pages)} pages')

    def replace(self):
        """
        The main replace wrapper which call the sub functions
        """

        # cleaning list of results
        self.result_list.clear()

        # if ever the function is called without the replace is checked
        if not self.replace_check.isChecked():
            self.result_label.setText("No replacement text found")
            self.progress.setValue(0)
            return

        else:
            # the both needle and replace patterns
            needle, replacement = self.find_field.text(), self.replace_field.text()

            # performs the needed sub function
            if self.code_search_check.isChecked():
                changes, pages = self.replace_in_code(needle, replacement)

            else:
                changes, pages = 0, set()

                # unlike the replace_in_code function we need to extract the count results by ourselves
                for p, r, o in self.search_in_doc(needle, replacement):
                    pages.add(p)
                    changes += 1

                pages = len(pages)

            # displaying a light report of replace
            self.result_label.setText(f'"{needle}" replaced by "{replacement}" {changes} time in {pages} pages')

            # updating parent's elements
            # TODO: replace all this stuff by a signal
            page = self.parent().page_nb

            # updating the current document page
            if page in self._book:
                self.parent().typer.setHtml(self._book[page])

            self.parent()._book.update(self._book)
            self.parent().modified.update(set(self._book.keys()))
            self.parent().changePage(page)

    def itemClicked(self, item: QTreeWidgetItem):
        """
        if an element is clicked in the list, we go to the page
        """
        # gettin QTreeWidget data
        pos = item.data(2, 0)

        # if page changing worked
        if self.parent().changePage(int(item.text(1))):
            # we move inside the document
            tc = self.parent().typer.textCursor()
            tc.setPosition(pos, QTextCursor.MoveMode.MoveAnchor)
            tc.select(QTextCursor.SelectionType.WordUnderCursor)

            self.parent().typer.setTextCursor(tc)
            self.parent().typer.ensureCursorVisible()

    def show(self):
        """
        Getting the last book from parent when showing up
        :return:
        """
        self._book = self.parent()._book

        super(GlobalSearch, self).show()


class Settings(QDialog):
    """
    A settings window
    TODO: everything needs to be done here, should be in two parts ; globals, and for the current doc
    """
    _win: QMainWindow
    _doc: QTextDocument
    _typer: QTextEdit
    verbose_eq = [CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET]

    def __init__(self, parent=None, typer=None):
        super(Settings, self).__init__(parent)
        self._win = parent
        self._typer = typer
        self._doc = self._typer.document()
        self.setFixedSize(600, 500)

        document_layout = QGridLayout()
        document_layout.setAlignment(Qt.AlignTop)

        # GLOBAL SETTINGS
        self.group_global = QGroupBox('Global Settings')
        self.group_global_layout = QVBoxLayout()
        self.group_global_layout.setAlignment(Qt.AlignTop)
        self.group_global.setLayout(self.group_global_layout)

        self.theme, = self.addOption('Themes', self.group_global_layout, QComboBox())
        themes = [s for s in S.GLOBAL.themes.keys()]
        self.theme.addItems(themes)
        self.theme.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'theme'))

        self.audio_record_path, self.audio_record_path_browse = self.addOption('Audio Record Path', self.group_global_layout, QLabel(), QPushButton('...'))
        self.audio_record_path_browse.setFixedWidth(35)
        self.audio_record_path_browse.clicked.connect(partial(self.updateGlobalSettings, 'audio_record_path'))

        self.audio_devices, = self.addOption('Audio Input Devices', self.group_global_layout, QComboBox())
        self.audio_devices.addItems(G.audio_input_devices_names)
        self.audio_devices.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'audio_input_device'))

        self.audio_sample_rate, = self.addOption('Audio Sample Rate', self.group_global_layout, QComboBox())
        self.sample_rates = [8000, 16000, 24000, 48000]
        self.audio_sample_rate.addItems(map(str, self.sample_rates))
        self.audio_sample_rate.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'audio_sample_rate'))

        self.update_default_path_box = self.addGlobalOption('update_default_path', 'Update default path')
        self.toolbar = self.addGlobalOption('toolbar', 'Main toolbar visible')
        self.text_toolbar = self.addGlobalOption('text_toolbar', 'Text toolbar visible')

        self.auto_load_box = self.addGlobalOption('auto_load', 'Automatically load previous file')

        self.verbose_level, = self.addOption('Verbose Level', self.group_global_layout, QComboBox())
        self.verbose_level.addItems(['critical', 'error', 'warning', 'info', 'debug', 'silent'])
        self.verbose_level.setCurrentIndex(self.verbose_eq.index(G.__debug_level__))
        self.verbose_level.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'verbose_level'))

        # LOCAL SETTINGS
        self.group_local = QGroupBox('Local Settings')
        self.group_local_layout = QVBoxLayout()
        self.group_local_layout.setAlignment(Qt.AlignTop)
        self.group_local.setLayout(self.group_local_layout)

        self.connected_box = self.addLocalOption('connected', 'Connect to PDF\'s pages')

        self.viewer_external_box = self.addLocalOption('viewer_external', 'External PDF Viewer Frame')

        self.viewer_invert_box = self.addLocalOption('viewer_invert', 'Invert PDF Viewer Colors')

        document_layout.addWidget(self.group_global)
        document_layout.addWidget(self.group_local)
        self.setLayout(document_layout)

    @staticmethod
    def addOption(nice_name: str, layout: QVBoxLayout, *objs):
        layout.addLayout(LineLayout(None, nice_name, *objs))
        return objs

    def addLocalOption(self, name: str, nice_name: str):
        checkbox, = self.addOption(nice_name, self.group_local_layout, QCheckBox())
        checkbox.clicked.connect(partial(self.updateLocalSettings, name))
        return checkbox

    def addGlobalOption(self, name: str, nice_name: str):
        checkbox, = self.addOption(nice_name, self.group_global_layout, QCheckBox())
        checkbox.clicked.connect(partial(self.updateGlobalSettings, name))
        return checkbox

    def updateLocalSettings(self, domain, state):
        """
        TODO: change everything, we should call a function like that but trigger signals to the parent instead
        """
        if isinstance(state, bool):
            state = int(state)
        if domain in ('connected', 'viewer_external', 'viewer_invert'):
            if state and not S.LOCAL.PDF:
                QMessageBox.critical(
                    None,
                    "Typer - No reference",
                    "There is <b>no reference</b> linked to the current project.",
                )
                return

        if domain == 'connected':
            S.LOCAL.connected = state
            if state:
                self._win.changePage(S.LOCAL.page)

            elif not state:
                self._win.typer.document().setHtml(S.LOCAL.BOOK[0])

        elif domain == 'viewer_external':
            S.LOCAL.viewer_external = state
            self._win.dockViewer(not state)

        elif domain == 'viewer_invert':
            S.LOCAL.viewer_invert = state
            self._win.viewer.redrawPixmap(self._win.viewer.current_page)

        S.LOCAL.saveSetting(domain)

    def updateGlobalSettings(self, domain, state):
        """
        TODO: cf Local remarks
        """
        if domain == 'verbose_level':
            G.__debug_level__ = self.verbose_eq[state]
            G.logger.setLevel(self.verbose_eq[state])

        elif domain == 'theme':
            S.GLOBAL.setTheme(self.theme.itemText(state))

        elif domain == 'update_default_path':
            S.GLOBAL.update_default_path = state

        elif domain == 'auto_load':
            S.GLOBAL.auto_load = state

        elif domain == 'toolbar':
            S.GLOBAL.toolbar = state
            self._win.toolbar.setVisible(state)

        elif domain == 'text_toolbar':
            S.GLOBAL.text_toolbar = state
            self._win.text_toolbar.setVisible(state)

        elif domain == 'audio_input_device':
            S.GLOBAL.audio_input_device = self.audio_devices.itemText(state)

        elif domain == 'audio_sample_rate':
            sample_rate = int(self.audio_sample_rate.itemText(state))
            if sample_rate > G.audio_input_devices[S.GLOBAL.audio_input_device]['sample']:
                QMessageBox.critical(
                    None,
                    "Too big sample rate",
                    f"""<b>Sample rate {sample_rate} for the device '{S.GLOBAL.audio_input_device}' too big</b>, 
                    reversing to 16k...""",
                    defaultButton=QMessageBox.Ok
                )
                sample_rate = 16000

            S.GLOBAL.audio_sample_rate = sample_rate

        elif domain == 'audio_record_path':
            dialog = QFileDialog(None, 'Audio Record Path', S.GLOBAL.audio_record_path)

            # we define some defaults settings used by all our file dialogs
            dialog.setFileMode(QFileDialog.FileMode.DirectoryOnly)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

            if dialog.exec_() == QFileDialog.Accepted:
                S.GLOBAL.setAudioRecordPath(dialog.selectedFiles()[0])
                self.audio_record_path.setText(S.GLOBAL.audio_record_path)

        if domain != 'verbose_level':
            S.GLOBAL.saveSetting(domain)

    def show(self):
        self.theme.setCurrentIndex(list(S.GLOBAL.themes.keys()).index(S.GLOBAL.theme))
        self.toolbar.setChecked(S.GLOBAL.toolbar)
        self.text_toolbar.setChecked(S.GLOBAL.text_toolbar)
        self.audio_record_path.setText(S.GLOBAL.audio_record_path)
        self.audio_devices.setCurrentIndex(G.audio_input_devices_names.index(S.GLOBAL.audio_input_device))
        self.audio_sample_rate.setCurrentIndex(self.sample_rates.index(S.GLOBAL.audio_sample_rate))
        self.update_default_path_box.setChecked(S.GLOBAL.update_default_path)
        self.auto_load_box.setChecked(S.GLOBAL.auto_load)

        self.connected_box.setChecked(S.LOCAL.connected)
        self.connected_box.setEnabled(S.LOCAL.hasPDF())
        self.viewer_external_box.setChecked(S.LOCAL.viewer_external)
        self.viewer_external_box.setEnabled(S.LOCAL.hasPDF())

        super(Settings, self).show()


class Navigator(QDialog):
    """
    It displays a resume list of the pages typed inside a whole PDF : for instance :
     if we typed pages 5 to 10 and 45 to 60 it'll display a list of theses two blocks
     with buttons allowing to directly go at the beginning or end of the block
    """
    goto = pyqtSignal(int)

    def __init__(self, parent):
        super(Navigator, self).__init__(parent)

        # UI stuffs
        self.setFixedSize(550, 600)
        self.main_layout = QVBoxLayout()
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.setWindowTitle('TyperNavigator')
        self.setWindowIcon(G.icon('List'))

        self.title = QLabel()
        self.main_layout.addWidget(self.title, 1)

    def addLine(self, start, end, start_title='', end_title=''):
        """
        after we got every parameters of the line, we add all the widgets in a new QHBoxLayout
        :param start: the start page's number
        :param end: the end page's number
        :param start_title: the name of the start surat
        :param end_title: name of the ending surat
        """
        line = QHBoxLayout()

        # if page range is wider than 1
        if start != end:
            label = QLabel(f'[{start} ... {end}]')

            # here we add to buttons, for beginning and end
            goto_start = QPushButton(f'Start ({start_title})')
            goto_start.pressed.connect(partial(self.goto.emit, start))
            goto_end = QPushButton(f'End ({end_title})')
            goto_end.pressed.connect(partial(self.goto.emit, end))

            # ui stuff
            line.addWidget(label, 1)
            line.addWidget(goto_start, 0)
            line.addWidget(goto_end, 0)

        # if begin == end
        else:
            # then we just add one button to go to the corresponding page
            label = QLabel(f'{start}')
            goto = QPushButton(f'Go to ({start_title})')
            goto.pressed.connect(partial(self.goto.emit, start))

            # ui stuff
            line.addWidget(label, 1)
            line.addWidget(goto, 0)

        # adding the new line to the layout
        self.main_layout.addLayout(line, 0)

    def buildMap(self):
        """
        this scan the given book dict and determine the corresponding pages' blocks
        """
        # abort if there is no page
        if not S.LOCAL.BOOK or not len(S.LOCAL.BOOK):
            return

        # this should delete everything but doesn't work completly
        # FIXME: QLabel artifacts
        # looping through all layout children
        for i in reversed(range(self.main_layout.count())):
            try:
                self.main_layout.itemAt(i).layout().setParent(None)

            except AttributeError:
                pass

        # we find all the surats names
        header_matcher = re.compile(r'-state:(97|981|982);.*?ff;\">(.*?)<', re.MULTILINE)

        # preparing the vars
        pages = set()
        pages_title = {}

        # create a temporary QTextDocument to store the HTML code of the page
        tmp_doc = QTextDocument()

        # for every page, we store to the temp doc
        for i in S.LOCAL.BOOK:
            tmp_doc.setHtml(S.LOCAL.BOOK[i])

            # we try to find all surats
            match_surat = header_matcher.findall(S.LOCAL.BOOK[i])

            # if ever we got one or more, adding the last in the page
            if match_surat:
                pages_title[i] = match_surat[-1][1]

            # getting all non-empty page
            # TODO: improve empty page detection with the function in PDF library
            if tmp_doc.toPlainText() != '':
                pages.add(i)

        # we'll store every blocks we meet, in a tuple
        blocks = [[0, 0, '', '']]
        i = 0
        current_title = ''

        # for every pages from 0 to the max value
        while i <= max(pages):

            # if page exists
            if i in pages:
                # and there is a surat in it
                if i in pages_title:
                    current_title = pages_title[i]

                # this means a new block has started since the previous one was empty
                if (i - 1) not in pages:
                    blocks[-1][0] = i
                    blocks[-1][2] = current_title

                # expanding the current block whatsoever
                blocks[-1][1] = i
                blocks[-1][3] = current_title

            # if the previous one was not empty and the current one is, we 'cut' the current block
            # and append a new one to the list so it'll be the current one (blocks[-1])
            elif (i - 1) in pages:
                blocks.append([0, 0, '', ''])

            i += 1

        # displays light resume of the operation
        self.title.setText(f'{len(pages)} pages filled, {len(blocks)} blocks')

        # expanding size for every block
        self.setFixedHeight(len(blocks) * 35 + 35)

        # adding the widgets
        for block in blocks:
            self.addLine(*block)


class Exporter(QDialog):
    """
    This dialog allows the user to pick a PDF file for export, and some settings
    it also provide a live log of what's happening
    """
    def __init__(self, parent: QMainWindow):
        super(Exporter, self).__init__(parent)
        # getting an instance of the PDF Exporter
        self.PDF_exporter = PDF_Exporter()
        self.PDF_exporter.finished.connect(self.post_treatment)
        self.setFont(parent.font())

        # the widget's settings, where we store book's datas, etc
        self.settings = {
            'book': {},
            'viewer': None,
            'topics': {},
            'dark_mode': False,
            'multi_page': False,
            'previous_export': None
        }

        # UI stuffs
        self.setFixedSize(550, 700)
        self.main_layout = QVBoxLayout()
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.setWindowTitle('TyperExport')
        self.setWindowIcon(G.icon("File-Extension-Pdf"))

        self.path_line = QLineEdit()
        if self.settings['previous_export']:
            self.path_line.setText(self.settings['previous_export'])

        self.path_browse = QPushButton("...")
        self.path_browse.clicked.connect(self.pick_file)

        self.print_quality = QCheckBox("High Quality Export : ")

        self.zoom_factor = QDoubleSpinBox(minimum=0.5, value=1.1, maximum=4.0)

        self.min_range = QSpinBox()
        self.max_range = QSpinBox()

        self.open_at_finish = QCheckBox("Open file when export finishes")
        self.open_at_finish.setChecked(True)
        self.log = QPlainTextEdit()

        def log_update(x):
            """
            just inserting line and scrolling to the end of the log
            :param x: log line
            """
            self.log.insertPlainText(f"{x}\n")
            self.log.ensureCursorVisible()

        self.PDF_exporter.log.connect(log_update)

        self.B_cancel = QPushButton("Cancel")
        self.B_cancel.clicked.connect(self.close)
        self.B_export = QPushButton("Export")
        self.B_export.clicked.connect(self.export)

        self.main_layout.addLayout(LineLayout(self, "Path : ", self.path_line, self.path_browse))
        self.main_layout.addLayout(LineLayout(self, self.print_quality, "Zoom factor : ", self.zoom_factor))
        self.main_layout.addLayout(LineLayout(self, "Start Page : ", self.min_range, "End Page : ", self.max_range))
        self.main_layout.addWidget(self.log)
        self.main_layout.setStretchFactor(self.log, 1)
        self.main_layout.addLayout(LineLayout(self, self.open_at_finish))
        self.main_layout.addLayout(LineLayout(self, self.B_cancel, self.B_export))

    def export(self):
        """
        Start the export process of the PDF
        """

        # if the palette was a dark one, we turn it black and white for printing
        if self.settings['dark_mode']:
            palette = QApplication.palette()
            palette.setColor(QPalette.ColorRole.Text, Qt.black)
            QApplication.setPalette(palette)

        self.log.clear()

        # forwarding some settings to the PDF Exporter
        self.PDF_exporter.settings.update({
            'path': self.path_line.text(),
            'factor': self.zoom_factor.value(),
            'hq': self.print_quality.isChecked()
        })

        # some additional params if we export multiple page
        if self.settings['multi_page']:
            self.PDF_exporter.settings.update({
                'book': self.settings['book'],
                'viewer': self.settings['viewer'],
                'topics': self.settings['topics'],
                'range': (self.min_range.value(), self.max_range.value() + 1)
            })
            self.PDF_exporter.run()

        # otherwise we create a temporary QTextDocument for the export
        else:
            doc = QTextDocument()
            doc.setHtml(self.settings['typer'].toHtml())
            self.PDF_exporter.single_page_export(doc)

        # when export's done, we revert to dark mode
        if self.settings['dark_mode']:
            palette.setColor(QPalette.ColorRole.Text, Qt.white)
            QApplication.setPalette(palette)

    def pick_file(self):
        """
        Opens a dialog to select the PDF filepath
        """
        dialog = QFileDialog(None, "Pick saved PDF's filepath", S.GLOBAL.default_path)
        dialog.setFileMode(dialog.AnyFile)
        dialog.setDefaultSuffix("pdf")
        dialog.setNameFilter("PDF Files (*.pdf)")
        dialog.setAcceptMode(dialog.AcceptSave)

        if dialog.exec_() == dialog.Accepted:
            filename = dialog.selectedFiles()
            self.path_line.setText(filename[0])
            self.PDF_exporter.path = filename[0]

    def post_treatment(self):
        """
        Performs some post treatment to store the settings used
        :FIXME open at finish don't work
        """
        if self.open_at_finish.isChecked():
            os.startfile(self.path_line.text(), 'open')

        # storing the previous export
        self.settings['previous_export'] = self.path_line.text()

    def show(self):
        """
        Update the min and max page spinners before displaying the dialog
        """
        try:
            # if we can get consistent values from the book
            mini, maxi = min(self.settings['book'].keys()), max(self.settings['book'].keys())

            # and min and max are not the same
            assert mini == maxi

        except (ValueError, AssertionError):
            # otherwise we disable this feature
            self.min_range.setDisabled(True)
            self.max_range.setDisabled(True)

        else:
            # setting the values
            for item in (self.min_range, self.max_range):
                item.setMinimum(mini)
                item.setMaximum(maxi)
            self.min_range.setValue(mini)
            self.max_range.setValue(maxi)

        self.log.clear()

        super(Exporter, self).show()


class Conjugate(QDialog):
    """
    A dialog showing all the conjugation table of the given verb
    """
    def __init__(self, parent, database: sqlite3.Connection):
        super(Conjugate, self).__init__(parent)
        self.temps = []
        self.modes = []
        self.heads = []

        # original general ressource for the conjugation, temps, modes, etc
        # TODO: update with the current wrapper in G.SQLConnection ?? or at least G.new_connection
        self.database = database
        self.cursor = database.cursor()
        temps = self.cursor.execute(f'SELECT value FROM ref WHERE field="temps" ORDER BY id ASC').fetchall()

        for t in temps:
            self.temps.extend([tmp.replace(' ', '<br>') for tmp in t])

        modes = self.cursor.execute(f'SELECT value FROM ref WHERE field="mode" ORDER BY id ASC').fetchall()
        for m in modes:
            self.modes.extend(m)

        heads = self.cursor.execute(f'SELECT value FROM ref WHERE field="head" ORDER BY id ASC').fetchall()
        for h in heads:
            self.heads.extend(h)

        # the current text cursor in the document
        self.textCursor = QTextCursor()

        # UI stuffs
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.sub_content = QLabel(self)
        self.sub_content.linkActivated.connect(self.setWord)

        self.scrollable = QScrollArea(self)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self.sub_content)
        self.scrollable.setWidget(widget)
        self.scrollable.setWidgetResizable(True)

        self.main_layout.addWidget(self.scrollable)

        self.setMinimumSize(1200, 500)

    def setWord(self, word):
        """
        add the word
        :param word: the word to insert
        """
        self.textCursor.insertHtml(word)

        self.hide()
        self.close()

    def load(self, cursor, verb):
        """
        loading the current verb conjugate table
        :param cursor: update the document text cursor for before insertion
        :param verb: the verb to display conjugation table
        """
        # update the text Cursor before
        self.textCursor = cursor

        html_text = ''  # where we'll insert the final html code
        h1 = -1         # the current mode level : Indicatif, Subjonctif, etc
        h2 = -1         # the current temps level : Présent, Passé...
        modes = {}

        req = self.cursor.execute(f'SELECT forme, head, mode, temps, id FROM conjugaison WHERE source="{verb}"')

        # for every conjugation
        for forme, head, mode, temps, i in req.fetchall():
            # if we changed the mode
            if mode != h1:
                h1 = mode
                modes[h1] = {}

            # if we changed the temps
            if temps != h2:
                h2 = temps
                modes[h1][h2] = {
                    'head_lines': {},
                    'lines': {}
                }

            modes[h1][h2]['head_lines'][i] = head
            modes[h1][h2]['lines'][i] = forme

        # then for every mode (Indicatif, Subjonctif, etc...)
        for mode, conjugation_table in modes.items():
            # we add a main header for the temps
            html_text += f'<h2 style="padding:3px;margin:3px">{self.modes[mode]}</h2>'

            # we get the maximum number of rows for the current conjugation_table to add the same number in every temps
            m = 0
            for t in conjugation_table:
                mx = max(conjugation_table[t]['lines'].keys())
                if mx > m:
                    m = mx

            # creating empty lines
            lines = {i: '' for i in range(m + 2)}

            sub_html = '<table>\n'

            # for every temps we edit the line
            for temps in conjugation_table:

                # adding a header for the temps
                lines[0] += f'<td style="padding:10px 0 0 0;">'
                lines[0] += f'<h3 style="padding:10px 0 0 0;">{self.temps[temps]}</h3></td>'
                lines[0] += "<td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</td>"

                # we try to append the line if the person exists in the conjugation table
                for line in range(m + 1):
                    try:
                        lines[line + 1] += f"<td>{self.heads[conjugation_table[temps]['head_lines'][line]]}"
                        lines[line + 1] += f"<a href='{conjugation_table[temps]['lines'][line]}'>"
                        lines[line + 1] += f"{conjugation_table[temps]['lines'][line]}</a></td>"

                    except KeyError:
                        lines[line + 1] += "<td></td>"

                    lines[line + 1] += "<td></td>"

            # finalizing the table
            sub_html += "<tr>" + "</tr>\n<tr>".join([lines[a] for a in lines]) + "</tr>\n</table><br>"
            html_text += sub_html

        # display the complete conjugation table
        self.sub_content.setText(html_text)


class Jumper(QDialog):
    """
    A new class to handle the navigation within the PDF, if data 'book.db' is provided it will be able to
    insert / jump / reference a given data in formats :
        {kitab}:{bab}:{hadith} : insert the given hadith (in local format, ie : the 6th hadith of the given bab)
        {kitab}:{bab} : insert the name of the bab
        {kitab} : just insert the name of the kitab
        {bab} : just insert the name of the bab
        {hadith} : by absolute numeration insert the hadith
    the {kitab} and {bab} can be typed as integer or translitterated arabic or arabic with or without harakat
    """

    result_goto = pyqtSignal(int)
    result_insert = pyqtSignal(object)

    def __init__(self, parent):
        # UI
        super(Jumper, self).__init__(parent)
        self.setWindowTitle('Source Book Jumper')
        self.setWindowIcon(G.icon('Book-Spelling'))

        self.setFixedWidth(400)
        self.search_field = SearchField(self)
        self.search_field.keyPressed.connect(self.preview)

        self.search_field.setFont(G.get_font(2))
        self.result_title = QLabel(self)
        self.result_title.setFont(G.get_font(2))

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.search_field)
        self.main_layout.addWidget(self.result_title)
        self.main_layout.setSpacing(0)

    def preview(self):
        self.result_title.setText(S.LOCAL.BOOKMAP.getTextResult(self.search_field.text()))

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """
        Overrides method to forward the result to signal if Enter is pressed
        """
        if e.key() == Qt.Key.Key_Return:

            # finalizing the result before signal emission
            cmd = self.search_field.text()

            # getting status for Alt, Ctrl and Shift
            modifiers = QApplication.keyboardModifiers()

            # TODO: isnert adress
            # if modifiers == Qt.KeyboardModifier.AltModifier:
            #     self.result_reference.emit(*res[2].split(':'))

            # we make it goes to the address surat:verse
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                self.result_goto.emit(S.LOCAL.BOOKMAP.getPageResult(cmd).page - 1)

            else:
                self.result_insert.emit(S.LOCAL.BOOKMAP.getObjectResult(cmd))

            self.close()

        super(Jumper, self).keyPressEvent(e)
