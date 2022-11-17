# بسم الله الرحمان الرحيم
import math
import win32api
import sqlite3
import re

from PyQt6.QtSql import QSqlDatabase
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from UI.BasicElements import ListWidget, ArabicField, LineLayout, AyatModelItem, MultiLineModelItem
from tools import G, S, T


class Hadith:
    def __init__(self, hid: int = 0, hadith: str = '', rawi: str = '', grade: str = ''):
        self.id = hid
        self.hadith = self.clean(hadith)
        self.light_hadith = self.clean(T.Arabic.clean_harakats(hadith))
        self.rawi = rawi
        self.grade = grade

        # the translated version
        self.hadith_trad = ''
        self.rawi_trad = ''
        self.grade_trad = ''

    def addTranslation(self, hadith: str = '', rawi: str = '', grade: str = ''):
        self.hadith_trad = self.cleanTranslation(hadith) if hadith else ''
        self.rawi_trad = self.cleanTranslation(rawi) if rawi else ''
        self.grade_trad = grade if grade else ''

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
        return self.hadith_trad, f'Rapporté par {self.rawi_trad}' if len(self.rawi_trad) else '', self.grade_trad

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
        if item[0] in T.Arabic.hurufs:
            return T.Arabic.clean_harakats(item) in self.light_hadith
        else:
            return item in self.hadith_trad

    def hasRawi(self, needle):
        if needle[0] in T.Arabic.hurufs:
            return T.Arabic.clean_harakats(needle) in self.rawi
        else:
            return needle in self.rawi_trad


class HadithSearch(QDialog):
    db: QSqlDatabase
    hadiths: [Hadith]
    loading_step = pyqtSignal(int, int)
    result_click = pyqtSignal(str)
    goto = pyqtSignal(int)

    class Worker(QRunnable):
        name = 'HadithSearch'

        def __init__(self, callback_fn, start=0, end=0):
            super().__init__()

            self.bounds = (start, end)

            self.callback_fn = callback_fn
            self.hadiths = []

        def run(self):
            db = sqlite3.connect(G.rsc_path('hadith.db'))
            cursor = db.cursor()

            req = cursor.execute(f'SELECT * FROM hadiths WHERE id BETWEEN ? AND ?', self.bounds).fetchall()
            db.close()

            for i, hadith, grade, rawi, hadith_fr, grade_fr, rawi_fr in req:
                if hadith is not None:
                    h = Hadith(hid=i, hadith=hadith, grade=grade, rawi=rawi)
                    h.addTranslation(hadith_fr, rawi_fr, grade_fr)

                    self.hadiths.append(h)

            self.callback_fn(self.hadiths)

            self.done(self.name)

    def __init__(self, parent=None):
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
        self.search_field.keyPressed.connect(self.preview)

        self.search = QPushButton("Search")
        self.search.clicked.connect(self.preview)

        self.sub_layout.addLayout(LineLayout(self, self.search_field, self.search))

        self.result_label = QLabel(self)
        self.sub_layout.addWidget(self.result_label)

        self.arabic_font = G.get_font(1.5)
        self.translation_font = G.get_font(1.3)
        self.result_view = ListWidget(self)
        self.result_view.setHeaderLabels(['hadith', 'hadith_arabic'])
        self.result_view.setContentsMargins(3, 3, 3, 3)
        self.result_view.itemClicked.connect(self.itemClicked)

        self.sub_layout.addWidget(self.result_view)
        self.result_view.setColumnCount(2)
        self.setFixedHeight(800)
        self.setMinimumWidth(800)
        self.result_view.setColumnWidth(0, 400)
        self.result_view.setColumnWidth(1, 400)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(5)
        self.progress.setTextVisible(False)

        main_layout.addLayout(self.sub_layout, 1)
        main_layout.addWidget(self.progress, 0)

        db = sqlite3.connect(G.rsc_path('hadith.db'))
        cursor = db.cursor()
        cnt = cursor.execute('SELECT COUNT(id) FROM hadiths').fetchone()[0]
        db.close()

        prev, step = 0, cnt // S.POOL.maxThreadCount()

        for i in range(step, cnt, step):
            worker = self.Worker(self.updateHadith, start=prev, end=i)
            S.POOL.start(worker)
            prev = i

        self.propagateFont()

    def propagateFont(self):
        self.search_field.setFont(G.get_font(2))

        self.arabic_font = G.get_font(1.5)
        self.translation_font = G.get_font(1.3)
        ayat_model_ar = AyatModelItem(font=self.arabic_font)
        ayat_model_fr = MultiLineModelItem(font=self.translation_font)
        self.result_view.applyModels((ayat_model_ar, ayat_model_fr))

    def itemClicked(self, item: QTreeWidgetItem, column: int):
        hadith: Hadith
        domain = item.data(0, Qt.ItemDataRole.UserRole)
        hid = item.data(1, Qt.ItemDataRole.UserRole)

        hadith = self.hadiths[hid] if domain == 'hadith' else S.LOCAL.BOOKMAP.datas[hid]
        content = hadith.toHtml() if column == 0 or domain == 'bookmap' else hadith.toTranslatedHtml()

        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier and domain == 'bookmap':
            self.goto.emit(S.LOCAL.BOOKMAP.getHadithPage(hid).page)
        else:
            self.result_click.emit(content)

        self.close()

    def updateHadith(self, hadiths):
        self.hadiths.extend(hadiths)

    def preview(self, e: QKeyEvent):
        if isinstance(e, QKeyEvent):
            return

        if (e is False or e.key() == Qt.Key.Key_Return) and len(self.search_field.text()):
            needle = self.search_field.text()

            result_count = 0
            s = 100 / (len(self.hadiths) + len(S.LOCAL.BOOKMAP.datas))

            self.result_view.clear()

            self.result_label.setText(f'<i>Searching...</i>')

            for domain_name, domain in (('hadith', self.hadiths), ('bookmap', S.LOCAL.BOOKMAP.datas)):
                for hid, hadith in enumerate(domain):
                    if needle in hadith:
                        fm_ar = QFontMetrics(self.arabic_font)

                        if domain_name == 'hadith':
                            fm_fr = QFontMetrics(self.translation_font)
                            hadith_ar = hadith.toPlainText()
                            hadith_fr = hadith.toTranslatedPlainText()
                            h_fr = math.ceil(.8 * fm_fr.horizontalAdvance(hadith_fr) / self.result_view.columnWidth(1))
                            h_fr *= fm_fr.height()
                        else:
                            hadith_ar = hadith.content
                            hadith_fr = ''
                            h_fr = 1

                        item = QTreeWidgetItem(self.result_view, [hadith_ar, hadith_fr])

                        h_ar = math.floor(.8 * fm_ar.horizontalAdvance(hadith_ar) / self.result_view.columnWidth(0))

                        item.setData(0, Qt.ItemDataRole.UserRole, domain_name)
                        item.setData(1, Qt.ItemDataRole.UserRole, hid)
                        item.setSizeHint(0, QSize(self.result_view.columnWidth(0), h_ar * fm_ar.height()))
                        item.setSizeHint(1, QSize(self.result_view.columnWidth(1), h_fr))
                        result_count += 1

                    c = int(s * hid)
                    if c % 2 == 0:
                        self.progress.setValue(c)

            self.result_label.setText(f'{result_count} occurences found')

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.search_field.setText('')
        self.result_label.setText('')
        self.result_view.clear()

        super(HadithSearch, self).closeEvent(a0)

    def show(self):
        super(HadithSearch, self).show()
        self.search_field.setFocus()


if __name__ == "__main__":
    import sys


    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)


    sys.excepthook = except_hook

    app = QApplication(sys.argv)
    editor = HadithSearch()
    editor.show()
    app.exec()