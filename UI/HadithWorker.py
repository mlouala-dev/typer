# بسم الله الرحمان الرحيم
import math
import win32api
import re

from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from UI.BasicElements import ListWidget, SearchField, LineLayout, AyatModelItem, MultiLineModelItem
from tools import G
from tools.translitteration import arabic_hurufs, clean_harakat


class Hadith:
    def __init__(self, hid: int = 0, hadith: str = '', rawi: str = '', grade: str = ''):
        self.id = hid
        self.hadith = self.clean(hadith)
        self.light_hadith = self.clean(clean_harakat(hadith))
        self.rawi = rawi
        self.grade = grade

        # the translated version
        self.hadith_trad = ''
        self.rawi_trad = ''
        self.grade_trad = ''

    def addTranslation(self, hadith: str = '', rawi: str = '', grade: str = ''):
        self.hadith_trad = self.cleanTranslation(hadith)
        self.rawi_trad = self.cleanTranslation(rawi)
        self.grade_trad = grade

    def clean(self, text: str):
        hadith = text.replace("’", "'")
        hadith = hadith.replace("ʽ", "'")
        hadith = hadith.replace("-صلى الله عليه وسلم-", "ﷺ")
        return hadith

    def cleanTranslation(self, text: str):
        hadith = re.sub(r"[Ḥḥ]", "H", self.clean(text))
        hadith = re.sub(r"[Ḍḍ]", "D", hadith)
        hadith = re.sub(r"[Ṭṭ]", "T", hadith)
        hadith = re.sub(r"[Ẓẓ]", "Z", hadith)
        hadith = re.sub(r"[Ṣṣ]", "S", hadith)
        hadith = hadith.replace("(sur lui la paix et le salut)", "ﷺ")
        return hadith

    def _source(self):
        return self.hadith, f'رواه {self.rawi}', self.grade

    def _translation(self):
        return self.hadith_trad, f'Rapporté par {self.rawi_trad}', self.grade_trad

    @staticmethod
    def formatPlainText(h, r, g):
        return f'{h} {r} ({g})'

    @staticmethod
    def formatHtml(h, r, g):
        h = re.sub(r"« (.*?) »", r'<b>"\1"</b>', h)
        h = re.sub(r"\{ (.*) \}", r'''<span style="font-weight:600; color:#169b4c;">﴾ \1 ﴿</span>''', h)
        h = re.sub(r"\{\( (.*) \)\}", r'''<span style="font-weight:600; color:#169b4c;">﴾ \1 ﴿</span>''', h)
        return f'''{h} {r} <i>({g})</i>'''

    def toPlainText(self):
        return Hadith.formatPlainText(*self._source())

    def toTranslatedPlainText(self):
        return Hadith.formatPlainText(*self._translation())

    def toHtml(self):
        return Hadith.formatHtml(*self._source())

    def toTranslatedHtml(self):
        return Hadith.formatHtml(*self._translation())

    def __contains__(self, item):
        # we check first character, if arabic we search in the source text,
        # otherwise the translation
        if item[0] in arabic_hurufs:
            return clean_harakat(item) in self.light_hadith
        else:
            return item in self.hadith_trad

    def hasRawi(self, needle):
        if needle[0] in arabic_hurufs:
            return clean_harakat(needle) in self.rawi
        else:
            return needle in self.rawi_trad


class HadithSearch(QDialog):
    db: QSqlDatabase
    hadiths: [Hadith]
    loading_step = pyqtSignal(int, int)
    result_click = pyqtSignal(str)

    def __init__(self, parent=None):
        self.hadiths = []

        super(HadithSearch, self).__init__(parent)
        self.setWindowTitle('Search in hadith database')
        self.setWindowIcon(G.icon('Book-Keeping'))

        self._win = parent
        self.main_layout = QVBoxLayout(self)

        self.search_field = SearchField(self)
        self.search_field.keyPressed.connect(self.preview)
        self.search_field.setFont(G.get_font(2))

        self.search = QPushButton("Search")
        self.search.clicked.connect(self.preview)

        self.main_layout.addLayout(LineLayout(self, self.search_field, self.search))

        self.result_label = QLabel(self)
        self.main_layout.addWidget(self.result_label)

        self.arabic_font = G.get_font(1.4)
        self.translation_font = G.get_font(1.3)
        ayat_model_ar = AyatModelItem(font=self.arabic_font)
        ayat_model_fr = MultiLineModelItem(font=self.translation_font)
        self.result_view = ListWidget(self, models=(ayat_model_ar, ayat_model_fr))
        self.result_view.setHeaderLabels(['hadith', 'hadith_arabic'])
        self.result_view.setContentsMargins(3, 3, 3, 3)
        self.result_view.itemClicked.connect(self.itemClicked)

        self.main_layout.addWidget(self.result_view)
        self.result_view.setColumnCount(2)
        self.setFixedHeight(800)
        self.setFixedWidth(1000)
        self.result_view.setColumnWidth(0, 400)
        self.result_view.setColumnWidth(1, 400)

    def itemClicked(self, item: QTreeWidgetItem, column: int):
        hadith: Hadith
        hid = item.data(1, Qt.ItemDataRole.UserRole)
        hadith = self.hadiths[hid]
        content = hadith.toHtml() if column == 0 else hadith.toTranslatedHtml()

        self.result_click.emit(content)
        self.close()

    def init_db(self, db: QSqlDatabase = None):
        """
        Loading the hadith database from hadith.db
        :param db: the QSQlDatabase object
        """
        # getting the current number of hadiths
        length = db.exec_('SELECT COUNT(*) FROM ahadith')
        length.next()

        s = int(length.value(0) / 100)  # the step
        c = 0   # current hadith count

        q = db.exec_('SELECT * FROM ahadith ORDER BY id DESC')
        while q.next():
            hadith = Hadith(
                hid=q.value('id'),
                hadith=q.value('hadith'),
                grade=q.value('grade'),
                rawi=q.value('rawi')
            )
            sq = db.exec_(f'SELECT hadith, rawi, grade FROM ahadith_trad WHERE id={hadith.id}')
            sq.next()
            hadith.addTranslation(sq.value('hadith'), sq.value('rawi'), sq.value('grade'))

            self.hadiths.append(hadith)
            if not c % s:
                self.loading_step.emit(c, int(c / s))

            c += 1

    def preview(self, e: QKeyEvent):
        if isinstance(e, QKeyEvent):
            return

        if (e is False or e.key() == Qt.Key.Key_Return) and len(self.search_field.text()):
            needle = self.search_field.text()
            result_count = 0
            for hid, hadith in enumerate(self.hadiths):
                if needle in hadith:
                    fm_ar = QFontMetrics(self.arabic_font)
                    fm_fr = QFontMetrics(self.translation_font)

                    hadith_ar = hadith.toPlainText()
                    hadith_fr = hadith.toTranslatedPlainText()
                    item = QTreeWidgetItem(self.result_view, [hadith_ar, hadith_fr])

                    h_ar = math.floor(fm_ar.width(hadith_ar) / self.result_view.columnWidth(0))
                    h_fr = math.ceil(fm_fr.width(hadith_fr) / self.result_view.columnWidth(1))

                    item.setData(1, Qt.ItemDataRole.UserRole, hid)
                    item.setSizeHint(0, QSize(self.result_view.columnWidth(0), h_ar * fm_ar.height()))
                    item.setSizeHint(1, QSize(self.result_view.columnWidth(1), h_fr * fm_fr.height()))
                    result_count += 1

            self.result_label.setText(f'{result_count} occurences found')

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.search_field.setText('')
        self.result_label.setText('')
        self.result_view.clear()
        win32api.LoadKeyboardLayout('0000040c', 1)
        super(HadithSearch, self).closeEvent(a0)

    def hideEvent(self, *args, **kwargs):
        win32api.LoadKeyboardLayout('0000040c', 1)
        super(HadithSearch, self).hideEvent(*args, **kwargs)

    def show(self):
        super(HadithSearch, self).show()
        self.search_field.setFocus()
        win32api.LoadKeyboardLayout('00000401', 1)


if __name__ == "__main__":
    import sys


    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)


    sys.excepthook = except_hook

    app = QApplication(sys.argv)
    editor = HadithSearch()
    editor.show()
    app.exec_()