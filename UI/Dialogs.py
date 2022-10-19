# بسم الله الرحمان الرحيم
import copy
import re
import html
import sqlite3
import win32api
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from functools import partial

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from UI.BasicElements import LineLayout, ListWidget, HighlightModelItem, NumberModelItem, SearchField, \
    MultiLineModelItem, ArabicField
from tools import G, S, T
from tools.PDF import PDF_Exporter
from tools.translitteration import arabic_hurufs


class TopicsDialog(QDialog):
    """
    This allows you to pick the topics linked with the current page
    """
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
        self.setFont(G.get_font())
        self.fm = QFontMetrics(self.font())

        self.pointer_rect = QRect(0, 30, 1, 1)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        self.setContentsMargins(5, 5, 5, 5)
        self.setFixedWidth(600)
        self.setFixedHeight(400)
        self.find_field = TopicsDialog.TopicFind(self)
        self.find_field.textChanged.connect(self.filterTopics)
        main_layout.addLayout(LineLayout(self, 'Find / Add : ', self.find_field))

        self.model = MultiLineModelItem(font=G.get_font(1.4))
        self.topic_list = ListWidget(self, models=[self.model])
        self.topic_list.setColumnCount(2)
        self.topic_list.setHeaderLabels(['Topic', 'Domain'])
        self.topic_list.itemDoubleClicked.connect(self.addTopic)
        self.topic_list.setColumnWidth(0, self.width() // 3 * 2 - 20)
        self.topic_list.setColumnWidth(1, self.width() // 3)

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

        self.find_field.setFocus()

    def filterTopics(self, text_filter=''):
        """
        Filter the view depending on the given filter
        :param text_filter: the text we filter through
        """

        # extending the res array with all the topics by page
        self.topic_list.clear()

        if text_filter == '':
            try:
                for topic in sorted(S.LOCAL.TOPICS.pages[S.LOCAL.page]):
                    self.addTopicItem(topic.name, topic.domain)

            except KeyError:
                S.LOCAL.TOPICS.pages[S.LOCAL.page] = set()

        else:
            for topic_name in filter(lambda x: text_filter in x, S.LOCAL.TOPICS.topics.keys()):
                topic = S.LOCAL.TOPICS.topics[topic_name]
                self.addTopicItem(topic.name, topic.domain)

        h = self.topic_list.topLevelItemCount()
        self.setFixedHeight(150 + h * self.fm.height())

    def addTopicItem(self, topic, domain):
        item = QTreeWidgetItem([topic])

        domain_applier = QComboBox(self.topic_list)
        domain_applier.setFixedWidth(self.topic_list.columnWidth(1))
        domain_applier.addItems(S.LOCAL.TOPICS.Domains.values())
        domain_applier.setCurrentIndex(list(S.LOCAL.TOPICS.Domains.keys()).index(domain))
        domain_applier.currentIndexChanged.connect(partial(self.changeDomain, topic))

        # adding the item
        self.topic_list.addTopLevelItem(item)
        self.topic_list.setItemWidget(item, 1, domain_applier)

        h = round((self.fm.width(topic) + 20) / self.topic_list.columnWidth(0))

        item.setSizeHint(0, QSize(self.topic_list.columnWidth(0), h * self.fm.height()))

        return item

    def addTopic(self, item: QTreeWidgetItem, col: int):
        if col == 0:
            topic = S.LOCAL.TOPICS.getTopic(item.text(0))
            S.LOCAL.TOPICS.pages[S.LOCAL.page].add(topic)

            self.find_field.setText('')
            self.filterTopics()

    def changeDomain(self, topic: str, index: int):
        new_domain = list(S.LOCAL.TOPICS.Domains.keys())[index]
        S.LOCAL.changeTopicDomain(topic, new_domain)

    def updateTopics(self):
        """
        update the current topics
        :return:
        """
        # determining the name of the topic we'll add
        try:
            item_text = self.topic_list.selectedItems()[0].text(0)
            domain = S.LOCAL.TOPICS.getTopic(item_text).domain

        # if there is no selection, setting the topic name based on the search field
        except IndexError:
            item_text = self.find_field.text()
            domain = list(S.LOCAL.TOPICS.Domains.keys())[0]

        # upgrading the lists
        S.LOCAL.TOPICS.addTopic(item_text, domain, S.LOCAL.page)

        self.find_field.clear()
        self.filterTopics()

    def keyPressEvent(self, e:QKeyEvent):
        """
        Overrides keyPress to catch the Delete button pressed
        """
        if e.key() == Qt.Key.Key_Delete:
            try:
                # getting the currently selected
                text = self.topic_list.selectedItems()[0].text(0)
                print(text)
                print(text.__class__)

                # updating the variables
                S.LOCAL.TOPICS.removeTopicFromPage(text, S.LOCAL.page)

            except IndexError:
                pass

            finally:
                self.find_field.clear()

                # now refresh the topics' list
                self.filterTopics()
                e.ignore()

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
        self.setWindowTitle(G.SHORTCUT['find'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['find'].icon_name))
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

        self.result_list = ListWidget(self)
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

        self.propagateFont()

    def propagateFont(self):
        self.setFont(G.get_font())
        ayat_model_ar = HighlightModelItem(font=G.get_font(1.4))
        num_model = NumberModelItem()
        self.result_list.applyModels((ayat_model_ar, num_model))

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
        total = 0

        try:
            perc = 100.0 / len(self._book)

        except ZeroDivisionError:
            perc = 100.0

        search_options = QTextDocument.FindFlags(0)

        # applies the flag to the QTextDocument
        for widget, flag in zip(
                [self.case_check, self.word_check],
                [QTextDocument.FindCaseSensitively, QTextDocument.FindWholeWords]
        ):
            if widget.isChecked():
                search_options |= flag

        # preparing the search needle
        search_needle = QRegularExpression(needle) if self.regex_check.isChecked() else needle

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

        # we define a new highlighted model
        model = HighlightModelItem(font=G.get_font(1.4), highlight=self.find_field.text())
        model.setParent(self)
        self.result_list.setItemDelegateForColumn(0, model)

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
            item.setSizeHint(0, QSize(self.result_list.columnWidth(0), 30))
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

            # updating the current document page
            if S.LOCAL.page in self._book:
                self.parent().typer.setHtml(self._book[S.LOCAL.page])

            S.LOCAL.BOOK.update(self._book)

    def itemClicked(self, item: QTreeWidgetItem):
        """
        if an element is clicked in the list, we go to the page
        """
        # gettin QTreeWidget data
        pos = item.data(2, 0)

        S.LOCAL.page = int(item.text(1))

        if pos:
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
        self._book = copy.copy(S.LOCAL.BOOK.getBook())

        super(GlobalSearch, self).show()
        self.find_field.setFocus()


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

        self.setWindowTitle(G.SHORTCUT['settings'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['settings'].icon_name))

        self._win = parent
        self._typer = typer
        self._doc = self._typer.document()
        self.setFixedSize(600, 500)

        L_main = QGridLayout()
        L_main.setAlignment(Qt.AlignmentFlag.AlignTop)
        L_main.setSpacing(0)
        L_main.setContentsMargins(2, 2, 2, 2)

        # GLOBAL SETTINGS
        self.G_global = QGroupBox('Global Settings')
        self.L_global = QVBoxLayout()
        self.L_global.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.L_global.setSpacing(0)
        self.L_global.setContentsMargins(2, 2, 2, 2)
        self.G_global.setLayout(self.L_global)

        self.theme, = self.addOption('Themes', self.L_global, QComboBox())
        themes = [s for s in S.GLOBAL.themes.keys()]
        self.theme.addItems(themes)
        self.theme.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'theme'))

        self.minimum_word_length, = self.addOption(
            "Minimum Auto-suggestion Word's length",
            self.L_global,
            QSpinBox()
        )
        self.minimum_word_length.valueChanged.connect(partial(self.updateGlobalSettings, 'minimum_word_length'))

        self.font_families = QFontDatabase.families()
        self.arabic_font_family, = self.addOption(
            'Arabic Font',
            self.L_global,
            QComboBox()
        )
        self.arabic_font_family.addItems(self.font_families)
        self.arabic_font_family.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'arabic_font_family'))

        self.latin_font_family, = self.addOption(
            'Latin Font',
            self.L_global,
            QComboBox()
        )
        self.latin_font_family.addItems(self.font_families)
        self.latin_font_family.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'latin_font_family'))

        self.audio_record_path, self.audio_record_path_browse = self.addOption(
            'Audio Record Path',
            self.L_global,
            QLabel(),
            QPushButton('...')
        )
        self.audio_record_path_browse.setFixedWidth(35)
        self.audio_record_path_browse.clicked.connect(partial(self.updateGlobalSettings, 'audio_record_path'))

        self.audio_devices, = self.addOption(
            'Audio Input Devices',
            self.L_global,
            QComboBox()
        )
        self.audio_devices.addItems(G.audio_input_devices_names)
        self.audio_devices.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'audio_input_device'))

        self.audio_sample_rate, = self.addOption(
            'Audio Sample Rate',
            self.L_global,
            QComboBox()
        )
        self.sample_rates = [8000, 16000, 24000, 48000]
        self.audio_sample_rate.addItems(map(str, self.sample_rates))
        self.audio_sample_rate.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'audio_sample_rate'))

        self.update_default_path_box = self.addGlobalOption('update_default_path', 'Update default path')
        self.toolbar = self.addGlobalOption('toolbar', 'Main toolbar visible')
        self.text_toolbar = self.addGlobalOption('text_toolbar', 'Text toolbar visible')

        self.auto_load_box = self.addGlobalOption('auto_load', 'Automatically load previous file')

        self.verbose_level, = self.addOption(
            'Verbose Level',
            self.L_global,
            QComboBox()
        )
        self.verbose_level.addItems(['critical', 'error', 'warning', 'info', 'debug', 'silent'])
        self.verbose_level.setCurrentIndex(self.verbose_eq.index(G.__debug_level__))
        self.verbose_level.currentIndexChanged.connect(partial(self.updateGlobalSettings, 'verbose_level'))

        # LOCAL SETTINGS
        self.G_local = QGroupBox('Local Settings')
        self.L_local = QVBoxLayout()
        self.L_local.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.L_local.setSpacing(0)
        self.L_local.setContentsMargins(2, 2, 2, 2)
        self.G_local.setLayout(self.L_local)

        self.connected_box = self.addLocalOption('connected', 'Connect to PDF\'s pages')
        self.audio_map = self.addLocalOption('audio_map', 'Display Audio Map')
        self.viewer_external_box = self.addLocalOption('viewer_external', 'External PDF Viewer Frame')
        self.viewer_invert_box = self.addLocalOption('viewer_invert', 'Invert PDF Viewer Colors')

        L_main.addWidget(self.G_global)
        L_main.addWidget(self.G_local)
        self.setLayout(L_main)

    @staticmethod
    def addOption(nice_name: str, layout: QVBoxLayout, *objs):
        layout.addLayout(LineLayout(None, nice_name, *objs))
        return objs

    def addLocalOption(self, name: str, nice_name: str):
        checkbox, = self.addOption(nice_name, self.L_local, QCheckBox())
        checkbox.clicked.connect(partial(self.updateLocalSettings, name))
        return checkbox

    def addGlobalOption(self, name: str, nice_name: str):
        checkbox, = self.addOption(nice_name, self.L_global, QCheckBox())
        checkbox.clicked.connect(partial(self.updateGlobalSettings, name))
        return checkbox

    def updateLocalSettings(self, domain, state):
        """
        TODO: change everything, we should call a function like that but trigger signals to the parent instead
        """
        if isinstance(state, bool):
            state = int(state)

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
                self._win.typer.document().setHtml(S.LOCAL.BOOK[0].content)
                tc = self._win.typer.textCursor()
                tc.setPosition(S.LOCAL.BOOK[0].cursor)
                self._win.typer.setTextCursor(tc)
                self._win.typer.ensureCursorVisible()

        elif domain == 'viewer_external':
            S.LOCAL.viewer_external = state
            self._win.dockViewer(not state)

        elif domain == 'audio_map':
            S.LOCAL.W_audioMap = state
            if state:
                self._win.typer.enableAudioMap()
            else:
                self._win.typer.disableAudioMap()

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

        elif domain == 'minimum_word_length':
            S.LOCAL.DICT.save()
            S.GLOBAL.minimum_word_length = state
            S.LOCAL.DICT = S.LOCAL.Dict(S.LOCAL.db, S.LOCAL.cursor)

        elif domain == 'arabic_font_family':
            S.GLOBAL.arabic_font_family = self.arabic_font_family.itemText(state)
            self._win.refreshUI()

        elif domain == 'latin_font_family':
            S.GLOBAL.latin_font_family = self.latin_font_family.itemText(state)
            self._win.refreshUI()

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
                    defaultButton=QMessageBox.StandardButton.Ok
                )
                sample_rate = 16000

            S.GLOBAL.audio_sample_rate = sample_rate

        elif domain == 'audio_record_path':
            dialog = QFileDialog(None, 'Audio Record Path', S.GLOBAL.audio_record_path)

            # we define some defaults settings used by all our file dialogs
            dialog.setFileMode(QFileDialog.FileMode.DirectoryOnly)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

            if dialog.exec() == QFileDialog.Accepted:
                S.GLOBAL.setAudioRecordPath(dialog.selectedFiles()[0])
                self.audio_record_path.setText(S.GLOBAL.audio_record_path)

        if domain != 'verbose_level':
            S.GLOBAL.saveSetting(domain)

    def show(self):
        self.theme.setCurrentIndex(list(S.GLOBAL.themes.keys()).index(S.GLOBAL.theme))
        self.toolbar.setChecked(S.GLOBAL.toolbar)
        self.text_toolbar.setChecked(S.GLOBAL.text_toolbar)
        self.arabic_font_family.setCurrentIndex(self.font_families.index(S.GLOBAL.arabic_font_family))
        self.latin_font_family.setCurrentIndex(self.font_families.index(S.GLOBAL.latin_font_family))
        self.audio_record_path.setText(S.GLOBAL.audio_record_path)
        self.audio_devices.setCurrentIndex(G.audio_input_devices_names.index(S.GLOBAL.audio_input_device))
        self.audio_sample_rate.setCurrentIndex(self.sample_rates.index(S.GLOBAL.audio_sample_rate))
        self.update_default_path_box.setChecked(S.GLOBAL.update_default_path)
        self.auto_load_box.setChecked(S.GLOBAL.auto_load)
        self.minimum_word_length.setValue(S.GLOBAL.minimum_word_length)

        self.audio_map.setChecked(S.LOCAL.audio_map)
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
    def __init__(self, parent):
        super(Navigator, self).__init__(parent)

        # UI stuffs
        self.setFixedSize(550, 600)
        self.L_main = QVBoxLayout()
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.L_main)

        self.setWindowTitle(G.SHORTCUT['navigator'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['navigator'].icon_name))

        self.WL_title = QLabel()
        self.WL_title.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.L_main.addWidget(self.WL_title, 1)

        self.propagateFont()

    def propagateFont(self):
        self.setFont(G.get_font())

    def addLine(self, start, end, start_title='', end_title=''):
        """
        after we got every parameters of the line, we add all the widgets in a new QHBoxLayout
        :param start: the start page's number
        :param end: the end page's number
        :param start_title: the name of the start surat
        :param end_title: name of the ending surat
        """
        line = QHBoxLayout()

        def goto_page(page):
            S.LOCAL.page = page

        # if page range is wider than 1
        if start != end:
            label = QLabel(f'[{start} ... {end}]')

            # here we add to buttons, for beginning and end
            goto_start = QPushButton(f'Start ({start_title})')
            goto_start.pressed.connect(partial(goto_page, start))
            goto_end = QPushButton(f'End ({end_title})')
            goto_end.pressed.connect(partial(goto_page, end))

            # ui stuff
            line.addWidget(label, 1)
            line.addWidget(goto_start, 0)
            line.addWidget(goto_end, 0)

        # if begin == end
        else:
            # then we just add one button to go to the corresponding page
            label = QLabel(f'{start}')
            goto = QPushButton(f'Go to ({start_title})')
            goto.pressed.connect(partial(goto_page, start))

            # ui stuff
            line.addWidget(label, 1)
            line.addWidget(goto, 0)

        # adding the new line to the layout
        self.L_main.addLayout(line, 0)

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
        for i in reversed(range(self.L_main.count())):
            try:
                self.L_main.itemAt(i).layout().setParent(None)

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
            tmp_doc.setHtml(S.LOCAL.BOOK[i].content)

            # we try to find all surats
            match_surat = header_matcher.findall(S.LOCAL.BOOK[i].content)

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
        self.WL_title.setText(f'{len(pages)} pages filled, {len(blocks)} blocks')

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

        # the widget's settings, where we store book's datas, etc
        self.settings = {
            'viewer': None,
            'previous_export': None
        }

        # UI stuffs
        self.setFixedSize(550, 700)
        self.L_main = QVBoxLayout()
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.L_main)

        self.setWindowTitle(G.SHORTCUT['pdf'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['pdf'].icon_name))

        self.WI_path = QLineEdit()
        if self.settings['previous_export']:
            self.WI_path.setText(self.settings['previous_export'])

        self.B_browse = QPushButton("...")
        self.B_browse.clicked.connect(self.pick_file)

        self.WC_quality = QCheckBox("High Quality Export : ")

        self.W_zoomFactor = QDoubleSpinBox(minimum=0.5, value=1.1, maximum=4.0)

        self.WI_minRange = QSpinBox()
        self.WI_maxRange = QSpinBox()

        self.WC_openAtFinish = QCheckBox("Open file when export finishes")
        self.WC_openAtFinish.setChecked(True)
        self.W_log = QPlainTextEdit()

        def log_update(x):
            """
            just inserting line and scrolling to the end of the log
            :param x: log line
            """
            self.W_log.insertPlainText(f"{x}\n")
            self.W_log.ensureCursorVisible()

        self.PDF_exporter.log.connect(log_update)

        self.B_cancel = QPushButton("Cancel")
        self.B_cancel.clicked.connect(self.close)
        self.B_export = QPushButton("Export")
        self.B_export.clicked.connect(self.export)

        self.L_main.addLayout(LineLayout(self, "Path : ", self.WI_path, self.B_browse))
        self.L_main.addLayout(LineLayout(self, self.WC_quality, "Zoom factor : ", self.W_zoomFactor))
        self.L_main.addLayout(LineLayout(self, "Start Page : ", self.WI_minRange, "End Page : ", self.WI_maxRange))
        self.L_main.addWidget(self.W_log)
        self.L_main.setStretchFactor(self.W_log, 1)
        self.L_main.addLayout(LineLayout(self, self.WC_openAtFinish))
        self.L_main.addLayout(LineLayout(self, self.B_cancel, self.B_export))

        self.propagateFont()

    def propagateFont(self):
        self.setFont(G.get_font())

    def export(self):
        """
        Start the export process of the PDF
        """

        # if the palette was a dark one, we turn it black and white for printing
        if S.GLOBAL.theme == 'dark':
            palette = QApplication.palette()
            palette.setColor(QPalette.ColorRole.Text, Qt.black)
            QApplication.setPalette(palette)
            palette.setColor(QPalette.ColorRole.Text, QColor(169, 183, 198))
            self.setPalette(palette)

        self.W_log.clear()

        # forwarding some settings to the PDF Exporter
        self.PDF_exporter.settings.update({
            'path': self.WI_path.text(),
            'factor': self.W_zoomFactor.value(),
            'hq': self.WC_quality.isChecked()
        })

        # some additional params if we export multiple page
        if S.LOCAL.hasPDF() and S.LOCAL.connected:
            self.PDF_exporter.settings.update({
                'viewer': self.settings['viewer'],
                'range': (self.WI_minRange.value(), self.WI_maxRange.value() + 1)
            })
            self.PDF_exporter.run()

        # otherwise we create a temporary QTextDocument for the export
        else:
            doc = QTextDocument()
            doc.setHtml(self.settings['typer'].toHtml())
            self.PDF_exporter.single_page_export(doc)

        # when export's done, we revert to dark mode
        if S.GLOBAL.theme == 'dark':
            QApplication.setPalette(palette)

    def pick_file(self):
        """
        Opens a dialog to select the PDF filepath
        """
        dialog = QFileDialog(None, "Pick saved PDF's filepath", S.GLOBAL.default_path)
        dialog.setFileMode(dialog.FileMode.AnyFile)
        dialog.setDefaultSuffix("pdf")
        dialog.setNameFilter("PDF Files (*.pdf)")
        dialog.setAcceptMode(dialog.AcceptMode.AcceptSave)

        if dialog.exec() == dialog.AcceptMode.Accepted:
            filename = dialog.selectedFiles()
            self.WI_path.setText(filename[0])
            self.PDF_exporter.path = filename[0]

    def post_treatment(self):
        """
        Performs some post treatment to store the settings used
        """
        if self.WC_openAtFinish.isChecked():
            win32api.ShellExecute(0, "open", self.WI_path.text(), '', None, 1)

        # storing the previous export
        self.settings['previous_export'] = self.WI_path.text()

    def show(self):
        """
        Update the min and max page spinners before displaying the dialog
        """
        try:
            # if we can get consistent values from the book
            mini, maxi = S.LOCAL.BOOK.minPageNumber(), S.LOCAL.BOOK.maxPageNumber()
            # and min and max are not the same
            assert mini != maxi

        except (ValueError, AssertionError) as e:
            G.exception(e)
            # otherwise we disable this feature
            self.WI_minRange.setDisabled(True)
            self.WI_maxRange.setDisabled(True)

        else:
            # setting the values
            for item in (self.WI_minRange, self.WI_maxRange):
                item.setMinimum(mini)
                item.setMaximum(maxi)

            self.WI_minRange.setValue(mini)
            self.WI_maxRange.setValue(maxi)

        self.W_log.clear()

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
        self.L_main = QVBoxLayout()
        self.setLayout(self.L_main)

        self.WL_subContent = QLabel(self)
        self.WL_subContent.linkActivated.connect(self.setWord)

        self.W_scrollArea = QScrollArea(self)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self.WL_subContent)
        self.W_scrollArea.setWidget(widget)
        self.W_scrollArea.setWidgetResizable(True)

        self.L_main.addWidget(self.W_scrollArea)

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
        self.WL_subContent.setText(html_text)


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

    result_insert = pyqtSignal(object)
    result_ref = pyqtSignal(object)

    def __init__(self, parent):
        # UI
        super(Jumper, self).__init__(parent)
        self.setWindowTitle(G.SHORTCUT['book_jumper'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['book_jumper'].icon_name))

        self.setFixedWidth(400)
        self.WI_searchField = SearchField(self)
        self.WI_searchField.keyPressed.connect(self.preview)

        self.WL_result = QLabel(self)

        self.L_main = QVBoxLayout(self)
        self.L_main.addWidget(self.WI_searchField)
        self.L_main.addWidget(self.WL_result)
        self.L_main.setSpacing(0)

        self.propagateFont()

    def propagateFont(self):
        self.WI_searchField.setFont(G.get_font(2))
        self.WL_result.setFont(G.get_font(2))

    def preview(self):
        self.WL_result.setText(S.LOCAL.BOOKMAP.getTextResult(self.WI_searchField.text()))

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """
        Overrides method to forward the result to signal if Enter is pressed
        """
        if e.key() == Qt.Key.Key_Return:

            # finalizing the result before signal emission
            cmd = self.WI_searchField.text()

            # getting status for Alt, Ctrl and Shift
            modifiers = QApplication.keyboardModifiers()

            # TODO: isnert adress
            # if modifiers == Qt.KeyboardModifier.AltModifier:
            #     self.result_reference.emit(*res[2].split(':'))

            # we make it goes to the address surat:verse
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                S.LOCAL.page = S.LOCAL.BOOKMAP.getPageResult(cmd).page - 1
            elif modifiers == Qt.KeyboardModifier.AltModifier:
                self.result_ref.emit(S.LOCAL.BOOKMAP.getObjectResult(cmd))
            else:
                self.result_insert.emit(S.LOCAL.BOOKMAP.getObjectResult(cmd))

            self.close()

        super(Jumper, self).keyPressEvent(e)


class DateTimePickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)
        self.setModal(True)
        L_main = QVBoxLayout()

        self.W_datetimePicker = QDateTimeEdit(self)
        self.W_datetimePicker.setCalendarPopup(True)
        self.W_datetimePicker.setDateTime(QDateTime.currentDateTime())

        W_buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        W_buttonBox.accepted.connect(self.accept)
        W_buttonBox.rejected.connect(self.reject)

        L_main.addWidget(self.W_datetimePicker)
        L_main.addWidget(W_buttonBox)
        self.setLayout(L_main)

    # get current date and time from the dialog
    def dateTime(self):
        return self.W_datetimePicker.dateTime()

    # static method to create the dialog and return (date, time, accepted)
    @staticmethod
    def getDateTime(parent=None, t: int = 0):
        dialog = DateTimePickerDialog(parent)
        if t:
            dialog.W_datetimePicker.setDateTime(QDateTime.fromSecsSinceEpoch(t))

        result = dialog.exec()
        date = dialog.dateTime()

        return date.toMSecsSinceEpoch() / 1000, result


class LexiconView(QDialog):
    class View(QTextEdit):
        def __init__(self, parent=None):
            self._parent = parent
            super().__init__()

            for child in self.children():
                if child.metaObject().className() == 'QWidgetTextControl':
                    child.setProperty('openExternalLinks', True)

        def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
            tc = self.cursorForPosition(e.pos())
            tc.select(QTextCursor.SelectionType.WordUnderCursor)
            self._parent.search(tc.selectedText())

    class History(list):
        def __init__(self):
            super().__init__()
            self.cursor = 0

        def move(self, direction=1):
            temp_cursor = self.cursor + direction
            self.cursor = max(0, min(temp_cursor, len(self) - 1))

        def next(self):
            self.move(1)

        def previous(self):
            self.move(-1)

        def add_squash(self, value: str):
            for i in range(len(self)-1, self.cursor, -1):
                self.pop(i)
            self.append(value)
            self.cursor = len(self) - 1

        def current(self):
            return self[self.cursor]

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(G.SHORTCUT['lexicon'].hint)
        self.setWindowIcon(G.icon(G.SHORTCUT['lexicon'].icon_name))

        self.setMinimumWidth(700)
        self.setMinimumHeight(700)

        L_main = QVBoxLayout()
        self.history = self.History()
        self.W_search = ArabicField()
        self.completer = QCompleter()
        self.W_search.setCompleter(self.completer)
        self.W_search.returnPressed.connect(self.search)
        self.C_by_root = QCheckBox()
        self.C_by_root.setText('By Root')

        def update_string_list(state):
            model = QStringListModel()
            if state:
                model.setStringList([a for a in S.GLOBAL.LEXICON.by_root.keys()])
            else:
                model.setStringList([a for a in S.GLOBAL.LEXICON.by_bareword.keys()])
            self.completer.setModel(model)

        self.C_by_root.stateChanged.connect(update_string_list)
        self.W_highlight = ArabicField()
        self.W_highlight.textChanged.connect(self.highlight)
        self.W_view = self.View(self)
        self.W_syntaxHighlighter = self.Highlighter(self.W_view.document())

        L_main.addLayout(LineLayout(
            None,
            'Search :',
            self.W_search,
            self.C_by_root,
            'Sub-highlight',
            self.W_highlight,
        ))
        L_main.addWidget(self.W_view)
        self.setLayout(L_main)

        self.setDocumentStyleSheet()

    def search(self, needle='', silent=False):
        needle = self.W_search.text() if needle == '' else needle
        if len(needle):
            self.W_syntaxHighlighter.needle = needle

            if self.C_by_root.isChecked():
                res = S.GLOBAL.LEXICON.find_by_root(needle)
            else:
                res = S.GLOBAL.LEXICON.find(needle)

            if not res:
                QMessageBox.critical(
                    None,
                    "Can't find root",
                    f"""'{needle}' not found, check search settings""",
                    defaultButton=QMessageBox.StandardButton.Ok
                )
            else:
                if len(res):
                    if not silent:
                        self.history.add_squash(needle)
                    self.W_view.setHtml(res)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.XButton2:
            self.history.next()
            self.W_search.setText(self.history.current())
            self.search(self.history.current(), silent=True)
        elif e.button() == Qt.MouseButton.XButton1:
            self.history.previous()
            self.W_search.setText(self.history.current())
            self.search(self.history.current(), silent=True)
        super().mousePressEvent(e)

    def highlight(self, needle=''):
        if len(needle):
            self.W_syntaxHighlighter.highlight_needle = needle
            self.W_syntaxHighlighter.rehighlight()

    def setDocumentStyleSheet(self):
        self.W_view.document().setDefaultStyleSheet(f'''
        body {{
            margin-left:5px;
            margin-top:5px;
            margin-right:5px;
            margin-bottom:5px;
        }}
        cite {{ 
            font-weight:600;
            font-size:30px;
            font-style: normal;
        }}
        i {{
            color:{self.palette().highlight().color().name()};
        }}
        samp, tt, code {{
            font-family:'{S.GLOBAL.latin_font_family}'; 
            font-size:{S.GLOBAL.font_size + 5}px;
            font-style: normal;
        }}
        samp {{ 
            font-size:{S.GLOBAL.font_size}px;
            font-style: italic;
        }}
        tt {{
            color:{self.palette().shadow().color().name()};
        }}
        code {{
            font-weight: 600;
            color:#
        }}
        ''')

    def show(self) -> None:
        self.W_search.setFocus()
        model = QStringListModel()
        model.setStringList([a for a in S.GLOBAL.LEXICON.by_bareword.keys()])
        self.completer.setModel(model)
        super(LexiconView, self).show()

    def propagateFont(self):
        self.setFont(G.get_font())
        self.W_search.setFont(self.font())

        self.setDocumentStyleSheet()

    class Highlighter(QSyntaxHighlighter):
        """
        A simple Highlighter
        """
        # defining some formats
        highlight = QTextCharFormat()
        highlight.setFontWeight(600)
        highlight.setForeground(QBrush(QColor(68, 156, 205)))

        subhighlight = QTextCharFormat()
        subhighlight.setBackground(S.GLOBAL.themes[S.GLOBAL.theme].palette.highlight())
        subhighlight.setForeground(S.GLOBAL.themes[S.GLOBAL.theme].palette.brightText())

        def __init__(self, *args):
            self.re_needle = re.compile('^$')
            self.re_sub = re.compile('^$')
            super().__init__(*args)

        @property
        def needle(self):
            pass

        @needle.setter
        def needle(self, value):
            formatted_needle = T.Regex.arabic_harakat.sub('', value)
            formatted_needle = re.sub(f'([{"".join(arabic_hurufs)}])', r'\1[ًٌٍَُِّْ]{0,2}', formatted_needle)
            self.re_needle = re.compile(formatted_needle)

        @property
        def highlight_needle(self):
            pass

        @highlight_needle.setter
        def highlight_needle(self, value):
            formatted_needle = T.Regex.arabic_harakat.sub('', value)
            formatted_needle = re.sub(f'([{"".join(arabic_hurufs)}])', r'\1[ًٌٍَُِّْ]{0,2}', formatted_needle)
            self.re_sub = re.compile(formatted_needle)

        def highlightBlock(self, text):
            """
            Overridden QSyntaxHighlighter method to apply the highlight
            """
            if not T.SPELL.loaded:
                return

            def tokenize(body_text: str) -> (int, str):
                """
                this tokenize the text with a rule
                :param body_text: the whole text we want to tokenize
                :return: yield the index of the word and the word itself
                """
                index = 0
                # TODO: this split regex should be an re.unescape(''.join(G.escape...) ???
                for word_match in T.Regex.highlight_split.split(body_text):
                    yield index, word_match

                    # increments the current text's index
                    index += len(word_match) + 1

            for idx, word in tokenize(text):
                if len(self.re_needle.findall(word)):
                    self.setFormat(idx, len(word), self.highlight)

                if len(self.re_sub.findall(word)):
                    self.setFormat(idx, len(word), self.subhighlight)

                pass
