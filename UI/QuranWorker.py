# بسم الله الرحمان الرحيم
import math
import win32api
import re

from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from tools.translitteration import arabic_hurufs, translitterate, get_arabic_numbers
from UI.BasicElements import ListWidget, SearchField, AyatModelItem, NumberModelItem
from tools import G


class QuranQuote(QDialog):
    """
    This provides a simple dialog where you can type some verse or surat reference, for example :
    typing "2:2" or "baq:2" will return the second verse of the surat Baqarah
    typing "2" or "baq" will return the title of the second surat of the Holy Quran
    """
    db: QSqlDatabase
    result_insert = pyqtSignal(int, list, str)
    result_reference = pyqtSignal(str, str)
    result_goto = pyqtSignal(int, int)
    surats = list()

    class Surat:
        def __init__(self, order: int, name: str, arabic: str, reveal: int, place: str):
            self.order = order
            self.name = name
            self.arabic = arabic
            self.reveal = reveal
            self.place = place
            self.ayat = []

    def __init__(self, parent=None):
        super(QuranQuote, self).__init__(parent)
        self.setWindowTitle('Insert from / Jump to Quran')
        self.setWindowIcon(G.icon('Book-Go'))

        # some UI settings
        self.setFixedWidth(400)

        self.search_field = SearchField(self)
        self.search_field.keyPressed.connect(self.preview)
        self.search_field.setFont(G.get_font(2))
        self.result_title = QLabel(self)
        self.result_title.setFont(G.get_font(2))
        self.result_ayat = QLabel(self)
        self.result_ayat.setFont(G.get_font(1.6))

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.search_field)
        self.main_layout.addWidget(self.result_title)
        self.main_layout.addWidget(self.result_ayat)
        self.main_layout.setSpacing(0)

        if __name__ == "__main__":
            self.init_db()

    def init_db(self, db_rsc: QSqlDatabase = None):
        """
        Basic initialization of the database and store quran data in local
        TODO: Store it globally
        :param db_rsc: the QSqlDatabase object
        :return:
        """
        # for local testing
        if __name__ == "__main__":
            from PyQt5.QtSql import QSqlDatabase
            connection = QSqlDatabase.addDatabase("QSQLITE")
            connection.setDatabaseName("../rsc/quran.db")
            db_rsc = QSqlDatabase.database()

        # otherwise we get it from parent
        self.db = db_rsc

        q = self.db.exec_("SELECT * FROM surats")

        # we get all surats infos
        while q.next():
            self.surats.append(
                QuranQuote.Surat(
                    order=int(q.value('Order')),
                    name=q.value('Name'),
                    arabic=q.value('Arabic'),
                    reveal=int(q.value('Revelation')),
                    place=q.value('Place'),
                )
            )

        # then the same for verses
        q = self.db.exec_("SELECT * FROM quran ORDER BY ayat")
        while q.next():
            self.surats[q.value(0) - 1].ayat.append(q.value(2))

    def preview(self, e):
        """
        Return a preview of the result for the given command
        """
        cmd = self.search_field.text()
        if len(cmd):
            s, v, cmd = self.query(cmd)
            # giving some basics info for the surat

            try:
                # returns a resume of the sourat
                place = "مدينية" if self.surats[s].place == "Madina" else "مكية"
                self.result_title.setText(f"{self.surats[s].arabic} - {place} ({get_arabic_numbers(str(len(self.surats[s].ayat)))} آيات)")
            except IndexError:
                self.result_title.setText('')

            if len(v):
                self.result_ayat.show()
                # if the search return ayat we join them with the ayat separator character
                self.result_ayat.setText(" ۝ ".join(v))

            else:
                self.result_ayat.hide()
        else:
            self.result_title.setText("")

    def formatted(self, s: int, v: list, cmd: str) -> str:
        """
        Returns the text insered in the text when it's inserted
        :param s: surat's index
        :param v: list of verses
        :param cmd: the original command which produced this result
        :return: a formatted representation of s:v
        """
        if len(v):
            # &#x200e; represents a force rtl character
            res = f"﴾ {' ۝ '.join(v)} ﴿ &#x200e; ({self.surats[s].arabic} {get_arabic_numbers(cmd)})"
        else:
            # if there is no verses we just return the surat's arabic name
            res = self.surats[s].arabic

        return res

    def query(self, command: str) -> tuple:
        """
        Search in the database to return the correct surat and verse depending on command, in format of
        "2:4" : verse 4 of surat 2
        or
        "baq:4" : verse 4 of surat 2 (baqara)
        or
        "2:4-8" : verses 4 to 8 of surat 2
        :param command: the search to perform
        :return list in form [surat: int, verses: list, command: str]
        """
        # setting some defaults
        surat = 1
        verses = []
        s = None

        def get_surat_no_by_name(text: str) -> int:
            """
            a simple search function to find the surat by name
            :return: the surat's number
            """
            with G.SQLConnection('quran.db') as db:
                q = db.exec_(f"SELECT * FROM surats WHERE Name LIKE '%{text}%'")

                # getting the first result
                q.next()

                return q.value("Order")

        # if there is a ':' it means the command's looking for verses in a surat
        if ":" in command:

            # extracting each component of the command
            s, v = command.split(":")

            # if none of them are empty
            if len(s) and len(v):
                try:
                    # if the first character of the surat's part of the command is an alpha, the user
                    # is probably looking for a surat by its name
                    if s[0].isalpha():
                        src = s
                        s = get_surat_no_by_name(src)

                        # reformatting the command for the final output
                        command = command.replace(src, str(s))

                    # abort if surat no is not in range
                    if int(s) not in range(1, 115):
                        raise ValueError

                    # if there is a '-' in the verse's part of the command it means we're looking for a
                    # range of verses not just one
                    if "-" in v:
                        # verse_begin to verse_end
                        vb, ve = v.split("-")

                        verses.extend(self.surats[int(s) - 1].ayat[int(vb) - 1: int(ve)])

                    else:
                        verses.append(self.surats[int(s) - 1].ayat[int(v) - 1])

                except ValueError:
                    # this exception will be raised in case :
                    # the surat' no is not in range,
                    # verses no are not in range
                    pass

        # final cleanup for the surat's number
        try:
            # if the command doesn't contains a ':'
            if command[0].isalpha() and not s:
                s = get_surat_no_by_name(command)
                command = s

            if int(s) not in range(1, 115):
                raise ValueError

            surat = int(s) - 1

        except (NameError, TypeError):
            # if it's just a number this exception will be triggered
            surat = int(command) - 1

        except ValueError:
            pass

        return surat, verses, str(command)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """
        Overrides method to forward the result to signal if Enter is pressed
        """
        if e.key() == Qt.Key.Key_Return:

            # finalizing the result before signal emission
            cmd = self.search_field.text()
            res = self.query(cmd)

            # if commands returns something viable
            if res:

                # getting status for Alt, Ctrl and Shift
                modifiers = QApplication.keyboardModifiers()

                if modifiers == Qt.KeyboardModifier.AltModifier:
                    self.result_reference.emit(*res[2].split(':'))

                # we make it goes to the address surat:verse
                elif modifiers == Qt.KeyboardModifier.ControlModifier:
                    self.result_goto.emit(*[int(r) for r in res[2].split(':')])

                else:
                    self.result_insert.emit(*res)

                self.close()

        super(QuranQuote, self).keyPressEvent(e)

    def closeEvent(self, a0: QCloseEvent) -> None:
        # resetting everything to zero
        self.search_field.setText('')
        self.result_title.setText('')
        self.result_ayat.setText('')

        self.db.close()

        super(QuranQuote, self).closeEvent(a0)


class QuranSearch(QDialog):
    """
    Provides a dialog to perform search within the Quran
    """
    db: QSqlDatabase
    result_insert = pyqtSignal(int, int)
    result_reference = pyqtSignal(int, int)
    result_goto = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super(QuranSearch, self).__init__(parent)
        self.setWindowTitle('Search in Quran')
        self.setWindowIcon(G.icon('Book'))

        self.setFont(G.get_font(1.4))
        self._win = parent

        # UI stuff
        self.main_layout = QVBoxLayout(self)

        self.search_field = SearchField(self)
        self.search_field.keyPressed.connect(self.preview)
        self.search_field.setFont(G.get_font(2))

        self.header_layout = QHBoxLayout(self)
        self.header_layout.addWidget(self.search_field)

        self.main_layout.addLayout(self.header_layout)

        # TODO: store all these text in a __lang__ library
        hint_label = QLabel("<b>Click</b> to insert, <b>Ctrl+Click</b> to jump to, <b>Alt+Click</b> to insert reference")
        self.main_layout.addWidget(hint_label)

        self.result_label = QLabel(self)
        self.main_layout.addWidget(self.result_label)

        # defining the model of the cells
        # working font : KFGQPC Uthman Taha Naskh', pointSize=13
        ayat_model_ar = AyatModelItem(font=G.get_font(2))
        num_model = NumberModelItem()
        self.result_view = ListWidget(self, models=(ayat_model_ar, num_model, num_model))
        self.result_view.setHeaderLabels(['text', 'verse(s)', 'surat'])
        self.result_view.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.result_view.setContentsMargins(3, 3, 3, 3)
        self.result_view.itemClicked.connect(self.itemClicked)

        self.main_layout.addWidget(self.result_view)
        self.result_view.setColumnCount(3)
        self.setFixedWidth(900)
        self.result_view.setColumnWidth(0, 650)
        self.result_view.setColumnWidth(1, 25)
        self.result_view.setColumnWidth(2, 25)

    def itemClicked(self, item: QTreeWidgetItem, column: int):
        """
        Triggered when item is clicked
        """
        # getting status for Alt, Ctrl and Shift
        modifiers = QApplication.keyboardModifiers()

        # getting value of the surat and verse's numbers
        address = (item.data(2, Qt.ItemDataRole.UserRole), item.data(1, Qt.ItemDataRole.UserRole))

        # we make it goes to the address surat:verse
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            self.result_goto.emit(*address)

        # we make it insert a reference to the page surat:verse
        elif modifiers == Qt.KeyboardModifier.AltModifier:
            self.result_reference.emit(*address)

        # otherwise we format it
        else:
            self.result_insert.emit(*address)

        self.close()

    def preview(self, e: QKeyEvent):
        """
        Retrieving all verses which matches with *search* without considering the harakats / tashkil
        """
        # we open the db locally since we just need it here
        with G.SQLConnection('quran.db') as db:
            if e.key() == Qt.Key.Key_Return and len(self.search_field.text()):
                txt = self.search_field.text()

                # even that we changed the keyboard layout, if user still want to search in translitterate mode...
                if len(txt) and (('A' <= txt[0] <= 'Z') or ('a' <= txt[0] <= 'z')):
                    txt = translitterate(txt)

                # cleaning all harakats
                clean_txt = re.sub(r'[ًٌٍَُِّْ]', '', txt)

                # making the regex search pattern to match all harakats for each arabic character
                clean_txt = re.sub(f'([{"".join(arabic_hurufs)}])', r'\1[ًٌٍَُِّْ]{0,2}', clean_txt)

                # searching in db
                q = db.exec_('SELECT * FROM quran WHERE text REGEXP "%s" ORDER BY surat ASC' % clean_txt)
                self.result_view.clear()
                self.result_view.show()

                result_count = 0
                result_diff_count = set()

                while q.next():
                    # we try to guess the final height the cell should have depending on length of verse,
                    # this is just an approximation based on text bounding box
                    fm = QFontMetrics(G.get_font(2))
                    w = self.result_view.columnWidth(0)

                    # with the text's bounding box width we try to guess the number on lines
                    nl = max(1, math.floor((fm.width(q.value('Text')) + 50) / w))

                    # then we store all data in the QTreeWidgetItem
                    surat = q.value(1)
                    verse = q.value(0)
                    item = QTreeWidgetItem(self.result_view, [q.value('Text'),
                                                              get_arabic_numbers(surat),
                                                              get_arabic_numbers(verse)])
                    item.setData(1, Qt.ItemDataRole.UserRole, surat)
                    item.setData(2, Qt.ItemDataRole.UserRole, verse)

                    # assigning custom height
                    item.setSizeHint(2, QSize(w, nl * 50))

                    result_count += 1
                    result_diff_count.add(q.value(0))

                # enlarge a lil bit if there is many results
                if result_count >= 3:
                    self.setMinimumHeight(600)

                self.result_label.setText(f'{result_count} verses found in {len(result_diff_count)} different surats')

                # forcing the columns' resize TODO: check setting of headercolumns to prevent automatic resize
                self.result_view.setColumnWidth(0, 600)
                self.result_view.setColumnWidth(1, 25)
                self.result_view.setColumnWidth(2, 25)

    def closeEvent(self, a0: QCloseEvent) -> None:
        """
        Override closeEvent to return key as origin
        TODO: store the original keyboard layout somewhere
        """
        # resetting the fields
        self.search_field.setText('')
        self.result_label.setText('')
        self.result_view.clear()

        # revert the keyboard layout
        win32api.LoadKeyboardLayout('0000040c', 1)
        super(QuranSearch, self).closeEvent(a0)

    def hideEvent(self, *args, **kwargs):
        """
        In case of hiding we also revert the keyboard's layout
        """
        win32api.LoadKeyboardLayout('0000040c', 1)
        super(QuranSearch, self).hideEvent(*args, **kwargs)

    def show(self):
        """
        When dialog pops up we automatically change the keyboard to AR Saudia
        :return:
        """
        # setting the keyboard layout
        win32api.LoadKeyboardLayout('00000401', 1)

        super(QuranSearch, self).show()

        # setting autofocus after showing the dialog
        self.search_field.setFocus()


if __name__ == "__main__":
    import sys

    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)

    sys.excepthook = except_hook

    app = QApplication(sys.argv)
    editor = QuranSearch()
    editor.show()
    app.exec_()
