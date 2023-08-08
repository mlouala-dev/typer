# بسم الله الرحمان الرحيم
import math
import sqlite3
import re
from functools import partial

from PyQt6.QtSql import QSqlDatabase
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from UI.BasicElements import (
    ListWidget, ArabicField, LineLayout,
    AyatModelItem, MultiLineModelItem, NumberModelItem, HtmlModelItem
)
from tools import G, S, T


class Book:
    def __init__(self, idx: int = 0, name: str = ''):
        self.id = idx
        self.name = name

    def __lt__(self, other):
        return self.name < other.name

    def __gt__(self, other):
        return self.name > other.name


class Entity:
    def __init__(self, idx: int = 0, name: str = '', type: int = -1):
        self.id = idx
        self.name = name
        self.type = type

    def __hash__(self):
        return hash(self.name)

    def __lt__(self, other):
        return self.name < other.name

    def __gt__(self, other):
        return self.name > other.name


class Hadith:
    def __init__(self, hid: int, hadith: str, grade: str, book: Book, entities: set):
        self.id = hid

        self.hadith = self.clean(hadith)
        self.light = T.Arabic.clean(self.hadith)
        self.html = self.light

        self.grade = grade
        self.book = book

        self.entities = entities

    @staticmethod
    def clean(text: str):
        hadith = T.Regex.simple_quotes.sub("'", text)
        hadith = T.Regex.double_quotes.sub('"', hadith)
        hadith = T.Regex.match_SAWS.sub(" ﷺ ", hadith)

        return hadith

    def toPlainText(self):
        return f'{self.hadith} ({self.grade})'

    def toHtml(self):
        return f'{self.html}<i>({self.grade})</i>'

    def hasEntity(self, entity: Entity):
        return entity in self.entities

    def __contains__(self, item):
        # we check first character, if arabic we search in the source text,
        # otherwise the translation
        return T.Arabic.clean(item) in self.light


class EntityFilter(QComboBox):
    entitySelected = pyqtSignal(int, int)
    filterCleared = pyqtSignal(int)

    def __init__(self, arabic: bool = True, type: int = -1):
        self.type = type
        self.filter_active = False

        super().__init__()
        self.addItem('')

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        if arabic:
            edit = ArabicField()
            self.setLineEdit(edit)
            edit.setCompleter(self.completer())
        else:
            self.lineEdit().setTextMargins(20, 0, 0, 0)

        self.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.reset = QPushButton(self)
        self.reset.setIcon(G.icon('Cross'))
        self.reset.setVisible(False)
        self.reset.clicked.connect(self.setCurrentIndex)

        self.editTextChanged.connect(self.reset_visibility)
        self.currentIndexChanged.connect(self.entitySelectionChanged)

    def reset_visibility(self, text: str):
        self.filter_active = bool(len(text))
        self.reset.setVisible(self.filter_active)
        self.setStyleSheet('border: 2px solid #45ACEF;' if self.filter_active else '')

        if not self.filter_active:
            self.filterCleared.emit(self.type)

    def addEntities(self, entities: [Entity]):
        for entity in sorted(entities):
            self.addItem(entity.name, entity.id)

    def entitySelectionChanged(self, idx):
        if idx:
            self.entitySelected.emit(
                self.itemData(idx, Qt.ItemDataRole.UserRole),
                self.type
            )


class HadithSearch(QDialog):
    db: QSqlDatabase
    hadiths: [Hadith]
    loading_step = pyqtSignal(int, int)
    result_click = pyqtSignal(str)
    goto = pyqtSignal(int)

    class Loader(QRunnable):
        name = 'LoaderHadith'

        def __init__(self, cb):
            super().__init__()
            self.cb = cb

        def run(self):
            hadiths = []

            db = sqlite3.connect(G.rsc_path('hadith.db'))
            cursor = db.cursor()

            books = {i: Book(idx=i, name=n) for i, n in cursor.execute('SELECT * FROM books')}
            entities = {i: Entity(idx=i, name=n, type=t) for i, n, t in cursor.execute('SELECT * FROM entities')}

            for idx, bid, book, hadith, grade, hadith_entities in \
                    cursor.execute(f'SELECT * FROM hadiths').fetchall():

                if len(hadith_entities):
                    hadith_entities = {entities[i] for i in map(int, hadith_entities.split(';'))}
                else:
                    hadith_entities = set()

                h = Hadith(
                    bid,
                    hadith=hadith,
                    grade=grade,
                    book=books[book],
                    entities=hadith_entities
                )

                hadiths.append(h)

            self.cb(books, entities, hadiths)
            self.done(self.name)

    def __init__(self, parent=None):
        self.books = {}
        self.entities = {}
        self.hadiths = []

        super().__init__(parent)

        self.setWindowTitle('Search in hadith database')
        self.setWindowIcon(G.icon('Book-Keeping'))

        self._win = parent
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)
        self.sub_layout = QVBoxLayout(self)

        self.search_field = ArabicField(self)

        self.WB_search = QPushButton("Search")
        self.WB_search.clicked.connect(self.searchResults)

        self.sub_layout.addLayout(LineLayout(self, self.search_field, self.WB_search))

        self.WC_book_filter = EntityFilter(arabic=False, type=-1)
        self.WC_book_filter.entitySelected.connect(self.applyFilter)
        self.WC_book_filter.filterCleared.connect(self.removeFilter)
        self.WC_person_filter = EntityFilter(type=0)
        self.WC_person_filter.entitySelected.connect(self.applyFilter)
        self.WC_person_filter.filterCleared.connect(self.removeFilter)
        self.WC_location_filter = EntityFilter(type=1)
        self.WC_location_filter.entitySelected.connect(self.applyFilter)
        self.WC_location_filter.filterCleared.connect(self.removeFilter)
        self.WC_event_filter = EntityFilter(type=2)
        self.WC_event_filter.entitySelected.connect(self.applyFilter)
        self.WC_event_filter.filterCleared.connect(self.removeFilter)

        self.sub_layout.addLayout(
            LineLayout(self,
                       'Book :', self.WC_book_filter,
                       'Person :', self.WC_person_filter,
                       'Location :', self.WC_location_filter,
                       'Event :', self.WC_event_filter,
                       )
        )

        self.filters = {
            -1: None,
            0: None,
            1: None,
            2: None
        }

        self.result_label = QLabel(self)
        self.sub_layout.addWidget(self.result_label)

        self.arabic_font = G.get_font(1.5)
        self.latin_font = G.get_font(2)
        self.result_view = ListWidget(self)
        self.result_view.setHeaderLabels(['book', 'num', 'hadith', 'grade'])
        self.result_view.itemClicked.connect(self.itemClicked)

        self.sub_layout.addWidget(self.result_view)
        self.result_view.setColumnCount(4)
        # self.result_view.header().cascadingSectionResizes()

        self.progress = QProgressBar()
        self.progress.setFixedHeight(5)
        self.progress.setTextVisible(False)

        main_layout.addLayout(self.sub_layout, 1)
        main_layout.addWidget(self.progress, 0)

        S.POOL.start(self.Loader(self.refresh))

        self.propagateFont()

    def propagateFont(self):
        self.search_field.setFont(G.get_font(2))
        self.WB_search.setFont(G.get_font())
        self.WC_book_filter.setFont(G.get_font())
        self.WC_event_filter.setFont(G.get_font())
        self.WC_location_filter.setFont(G.get_font())
        self.WC_person_filter.setFont(G.get_font())

        self.arabic_font = G.get_font(1.5)
        self.latin_font = G.get_font()

        arabic_model = AyatModelItem(font=self.arabic_font)
        hadith_model = HtmlModelItem(font=self.arabic_font)
        latin_model = AyatModelItem(font=self.latin_font)
        self.result_view.applyModels((latin_model, latin_model, hadith_model, arabic_model))

    def itemClicked(self, item: QTreeWidgetItem, column: int):
        hadith: Hadith

        hid = item.data(0, Qt.ItemDataRole.UserRole)
        hadith = self.hadiths[hid]

        self.result_click.emit(hadith.toPlainText())
        self.close()

    def refresh(self, books: dict, entities: dict, hadiths: list):
        self.books.update(books)
        self.entities.update(entities)
        self.hadiths.extend(hadiths)

        for b in sorted(books.values()):
            self.WC_book_filter.addItem(b.name.capitalize(), b.id)

        self.WC_person_filter.addEntities([e for e in entities.values() if e.type == 0])
        self.WC_location_filter.addEntities([e for e in entities.values() if e.type == 1])
        self.WC_event_filter.addEntities([e for e in entities.values() if e.type == 2])

    def applyFilter(self, idx: int, type: int):
        if type == -1:
            self.filters[type] = self.books[idx]
        else:
            self.filters[type] = self.entities[idx]
        self.searchResults()

    def removeFilter(self, type: int):
        self.filters[type] = None
        self.searchResults()

    def searchResults(self):
        hadiths = self.hadiths

        if self.filters[-1]:
            hadiths = filter(lambda x: x.book == self.filters[-1], hadiths)

        def apply_filter(f: Entity, hadiths):
            for hadith in hadiths:
                if f in hadith.entities:
                    hadith.html = hadith.html.replace(
                        f.name,
                        f'<b><font style="color:#39EF7C"> {f.name} </font></b>'
                    )
                    yield hadith

        for filt in (self.filters[0], self.filters[1], self.filters[2]):
            if filt is not None:
                hadiths = apply_filter(filt, hadiths)

        hadiths = [h for h in hadiths]

        self.result_view.clear()
        needle = T.Arabic.clean(self.search_field.text())

        if len(hadiths) == len(self.hadiths) and not len(needle) or not len(hadiths):
            return

        result_count = 0
        s = 100 / (len(hadiths))

        for hid, hadith in enumerate(hadiths):
            hadith: Hadith

            if needle in hadith:
                if len(needle):
                    hadith.html = hadith.html.replace(
                        needle,
                        f'<b><font style="color:#3979FF"> {needle} </font></b>'
                    )
                fm_ar = QFontMetrics(self.arabic_font)

                rect = fm_ar.boundingRect(
                    0, 0, self.result_view.columnWidth(2), 1000,
                    Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignRight,
                    hadith.toPlainText()
                )

                item = QTreeWidgetItem(
                    self.result_view,
                    [hadith.book.name, str(hadith.id), hadith.toHtml(), hadith.grade]
               )

                # h_ar = math.floor(.8 * fm_ar.horizontalAdvance(hadith_ar) / self.result_view.columnWidth(0))
                item.setData(0, Qt.ItemDataRole.UserRole, hid)
                item.setSizeHint(2, QSize(self.result_view.columnWidth(2), rect.height() + fm_ar.height()))
                result_count += 1

                result_count += 1

            c = int(s * hid)
            if c % 2 == 0:
                self.progress.setValue(c)

        self.result_label.setText(f'{result_count} hadiths found.')

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.search_field.setText('')
        self.result_label.setText('')
        self.WC_book_filter.setCurrentIndex(0)
        self.WC_person_filter.setCurrentIndex(0)
        self.WC_location_filter.setCurrentIndex(0)
        self.WC_event_filter.setCurrentIndex(0)
        self.result_view.clear()

        super().closeEvent(a0)

    def show(self):
        super().show()
        self.search_field.setFocus()

        self.result_view.setColumnWidth(0, 50)
        self.result_view.setColumnWidth(1, 40)
        self.result_view.setColumnWidth(2, self.result_view.width() - 200)
        self.result_view.setColumnWidth(3, 110)


if __name__ == "__main__":
    import sys


    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)


    sys.excepthook = except_hook

    app = QApplication(sys.argv)
    editor = HadithSearch()
    editor.show()
    app.exec()