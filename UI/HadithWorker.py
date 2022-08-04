# بسم الله الرحمان الرحيم
import math
import win32api
import re

from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from UI.BasicElements import ListWidget, SearchField, LineLayout, RadioGroupBox, AyatModelItem, NumberModelItem, \
    MultiLineModelItem

from tools import G

class HadithSearch(QDialog):
    db: QSqlDatabase
    result_click = pyqtSignal(str)

    def __init__(self, parent=None):
        super(HadithSearch, self).__init__(parent)
        self._win = parent
        self.init_db()
        self.main_layout = QVBoxLayout(self)

        self.search_field = SearchField(self)
        self.search_field.keyPressed.connect(self.preview)
        self.search_field.setFont(G.get_font(2))

        self.search = QPushButton("Search")
        self.search.clicked.connect(self.preview)

        self.search_modes = RadioGroupBox(direction=QHBoxLayout(),
                                          title='Search modes',
                                          widgets=(
                                              "Arabic text",
                                              "French text",
                                              "Rawi (arabic)",
                                              "Rawi (french)"
                                          ))

        self.main_layout.addLayout(LineLayout(self, self.search_field, self.search))
        self.main_layout.addLayout(LineLayout(self, self.search_modes))

        hint_label = QLabel("<b>Click</b> to insert arabic, <b>Ctrl+Click</b> insert french")
        self.main_layout.addWidget(hint_label)

        self.result_label = QLabel(self)
        self.main_layout.addWidget(self.result_label)

        self.hadith_font = QFont('KFGQPC Uthman Taha Naskh', pointSize=13)
        ayat_model_ar = AyatModelItem(font=self.hadith_font)
        ayat_model_fr = MultiLineModelItem(font=QFont('Calibri', pointSize=10))
        delegate_model = NumberModelItem()
        self.result_view = ListWidget(self,
                                      models=(
                                          ayat_model_ar,
                                          ayat_model_fr,
                                          delegate_model,
                                          delegate_model
                                        )
                                      )
        self.result_view.setHeaderLabels(['hadith', 'hadith arabic', 'grade', 'rawi'])
        self.result_view.setContentsMargins(3, 3, 3, 3)
        self.result_view.itemClicked.connect(self.itemClicked)

        self.main_layout.addWidget(self.result_view)
        self.result_view.setColumnCount(4)
        self.setFixedHeight(800)
        self.setFixedWidth(1300)
        self.result_view.setColumnWidth(0, 500)
        self.result_view.setColumnWidth(1, 500)
        self.result_view.setColumnWidth(2, 100)
        self.result_view.setColumnWidth(3, 150)

    def itemClicked(self, item: QTreeWidgetItem, column: int):
        modifiers = QApplication.keyboardModifiers()

        data_id = 2 if modifiers == Qt.KeyboardModifier.ControlModifier else 1
        hadith, grade, takhrij = item.data(data_id, Qt.ItemDataRole.UserRole)
        hadith = re.sub(r"« (.*) »", r'<b>"\1"</b>', hadith)
        hadith = re.sub(r"« (.*?) »", r"<i>'\1'</i>", hadith)
        if data_id == 2:
            hadith = re.sub(r"[Ḥḥ]", "H", hadith)
            hadith = re.sub(r"[Ḍḍ]", "D", hadith)
            hadith = re.sub(r"[Ṭṭ]", "T", hadith)
            hadith = re.sub(r"[Ẓẓ]", "Z", hadith)
            hadith = re.sub(r"[Ṣṣ]", "S", hadith)
            hadith = hadith.replace("(qu'Allah l'agrée)", r'<img src="D:/Script/Typer\rsc/ra_LD.png" />')
            hadith = hadith.replace("’", "'")
            hadith = hadith.replace("ʽ", "'")
            hadith = re.sub(r"\{\( (.*) \)\}", r'''<span style=" font-family:'Microsoft Uighur'; font-size:15pt; font-weight:600; color:#169b4c;">\1</span>''', hadith)
        else:
            hadith = re.sub(r"\{ (.*) \}", r'''<span style=" font-family:'Microsoft Uighur'; font-size:15pt; font-weight:600; color:#169b4c;">\1</span>''', hadith)
        res = f"{hadith} - {takhrij[0].lower()}{takhrij[1:]} <i>({grade})</i>"

        self.result_click.emit(res)
        self.close()

    def init_db(self, db_rsc=None):
        if __name__ == "__main__":
            from PyQt5.QtSql import QSqlDatabase
            connection = QSqlDatabase.addDatabase("QSQLITE")
            connection.setConnectOptions('QSQLITE_ENABLE_REGEXP')
            connection.setDatabaseName("../rsc/hadith.db")
            db_rsc = QSqlDatabase.database()

        self.db = db_rsc

    def preview(self, e: QKeyEvent):
        if (e is False or e.key() == Qt.Key.Key_Return) and len(self.search_field.text()):
            txt = self.search_field.text()
            sel = self.search_modes.selectionIndex()

            field = ["hadith_text_ar", "hadith_text", "takhrij_ar", "takhrij"]
            clean_txt = re.sub(r'[ًٌٍَُِّْ]', '', txt)
            # clean_txt = re.sub(r'([' + ''.join(arabic_hurufs) + '])', r'\1[ًٌٍَُِّْ]{0,2}?', clean_txt)
            q = self.db.exec_(f'SELECT * FROM hadith WHERE {field[sel]} REGEXP "{clean_txt}" ORDER BY id ASC')
            self.result_view.clear()
            self.result_view.show()

            result_count = 0
            result_diff_count = set()

            while q.next():
                fm = QFontMetrics(self.hadith_font)
                w = self.result_view.columnWidth(0)
                nl = math.ceil(fm.width(q.value('hadith_text_ar')) / w)
                hadith_ar = q.value("hadith_text_ar").replace("-صلى الله عليه وسلم-", "ﷺ")
                hadith_fr = q.value("hadith_text").replace("(sur lui la paix et le salut)", "ﷺ")
                grade_ar = q.value("grade_ar").replace(".", "")
                grade_fr = q.value("grade").replace(".", "")
                takhrij_ar = q.value("takhrij_ar").replace(".", "")
                takhrij_fr = q.value("takhrij").replace(".", "")
                item = QTreeWidgetItem(self.result_view, [
                    hadith_ar,
                    hadith_fr,
                    grade_ar,
                    takhrij_ar
                ])
                item.setData(1, Qt.ItemDataRole.UserRole, [hadith_ar, grade_ar, takhrij_ar])
                item.setData(2, Qt.ItemDataRole.UserRole, [hadith_fr, grade_fr, takhrij_fr])
                item.setSizeHint(2, QSize(w, nl * 40 + 15))
                result_count += 1
                result_diff_count.add(q.value(0))

            self.result_label.setText('%d occurences found in %d different hadiths' % (result_count, len(result_diff_count)))

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.search_field.setText('')
        self.result_label.setText('')
        self.result_view.clear()
        self.db.close()
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