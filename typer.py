# بسم الله الرحمان الرحيم
import sys
import os
import html

from datetime import datetime
from functools import partial

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from UI import QuranWorker, Editor
from UI.HadithWorker import HadithSearch
from UI.Modules import Settings, TopicsBar, Navigator, GlobalSearch, Exporter
from UI.MainComponents import StatusBar, Summary, TitleBar, Toolbar, SplashScreen

from tools import G, PDF, Threads


# Exception catch for Qt

def except_hook(cls, exception, traceback):
    G.error_exception(exception, traceback)
    sys.__excepthook__(cls, exception, traceback)


sys.excepthook = except_hook

# TODO: liens de références :
# TODO: rajouter au début https://leporteurdesavoir.fr/wp-content/uploads/frise-chronologique-vie-prophete.png
# TODO: rajouter dans l'introduction récit des prophète chaine génération des prophètes ?
# TODO: https://media.kenanaonline.com/photos/1238014/1238014670/1238014670.jpg?1301706366
# TODO: http://arab-ency.com.sy/img/res/2255/1.jpg

# TODO: reorder the RSC folder and update link everywhere : database / images / icons


class TyperWIN(QMainWindow):
    """
    The main window's class
    """
    db_file: QSqlDatabase
    db_backup: QSqlDatabase
    _file: str
    _book = dict()
    _version = G.__ver__
    _variant = f"{G.__app__} Quran"

    # TODO: settings needs improvement with an external settings manager to load / save / handle
    _settings = {
        'reference': '',
        'connect_to_ref': 0
    }
    dark_mode = True

    # the dbs
    db_backup = None    # a copy of the current file if it crashes or fails
    db_file = None  # where we store the app settings etc

    modified = set()    # a list of all the modified page

    def __init__(self):
        super(TyperWIN, self).__init__()
        _splash = SplashScreen()
        _splash.show()
        _layout = QGridLayout(self)

        self.setFont(G.get_font(1.2))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowIcon(QIcon(G.rsc_path("ico.png")))

        _splash.progress(10, "Loading dictionnary...")
        self.dictionnary = Threads.Dictionnary()
        self.dictionnary.finished.connect(self.spellBuilt)

        _splash.progress(25, "Loading settings...")
        self.dictionnary.start()

        self._file = None

        self.page_nb = 0
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(1000)

        self.container = QWidget(self)
        self.summary_view = Summary(self)
        self.typer = Editor.Typer(self)
        self.viewer = PDF.Viewer(self)

        self.viewer_frame = QWidget(self)
        viewer_frame_layout = QVBoxLayout(self.viewer_frame)
        viewer_frame_layout.addWidget(self.viewer)

        self.topic_display = TopicsBar(self)
        viewer_frame_layout.setContentsMargins(0, 0, 0, 0)
        viewer_frame_layout.setSpacing(0)
        viewer_frame_layout.addWidget(self.topic_display)
        self.topic_display.topic_dialog.valid.connect(self.saveTopics)
        self.viewer_frame.setMaximumWidth(600)

        _splash.progress(40, "Loading QuranQuote...")
        self.quran_quote = QuranWorker.QuranQuote(self)

        _splash.progress(45, "Loading QuranSearch...")
        self.quran_search = QuranWorker.QuranSearch(self)
        self.find_dialog = GlobalSearch(self)
        self.settings_dialog = Settings(self, self.typer)

        _splash.progress(50, "Loading Navigator...")
        self.navigator = Navigator(self)
        self.exporter = Exporter(self)

        self.viewer_frame.hide()
        self.summary_view.hide()

        self.toolbar = Toolbar(self)

        _splash.progress(55, "Loading UI...")
        self.typer.cursorPositionChanged.connect(self.summary_view.updateSummaryHighLight)
        self.summary_view.clicked.connect(self.updateTextCursor)
        self.typer.textChanged.connect(self.setModified)

        _splash.progress(55, "Loading UI Window Title...")
        self.window_title = TitleBar(self)

        _splash.progress(55, "Loading UI Main Layout...")
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.viewer_frame)
        splitter.addWidget(self.typer)
        splitter.addWidget(self.summary_view)
        splitter.setStretchFactor(0, 33)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 20)

        _splash.progress(55, "Loading UI Status Bar...")
        self.statusbar = StatusBar()

        _splash.progress(70, "Loading Audio Recorder...")
        self.audio_recorder = Threads.AudioWorker()
        self.recording = False

        # Main layout operations
        _layout.addWidget(self.window_title)
        _layout.addWidget(self.toolbar)
        _layout.addWidget(splitter)
        _layout.setRowStretch(0, 0)
        _layout.setRowStretch(1, 0)
        _layout.setRowStretch(2, 1)
        _layout.setColumnStretch(0, 1)
        _layout.setSpacing(0)
        _layout.setContentsMargins(0, 0, 0, 0)

        self.container.setLayout(_layout)
        self.setStatusBar(self.statusbar)
        self.setCentralWidget(self.container)
        self.setBaseSize(600, 800)

        self.toolbar.buttons['save'].setDisabled(True)

        _splash.progress(75, "Applying dark theme...")
        if self.dark_mode:
            self.setDarkMode()

        self.modified.clear()

        # DATABASES

        _splash.progress(85, "Loading Quran's database...")
        with G.SQLConnection('quran.db') as db:
            _splash.progress(95, "Init Quran's widget...")
            self.quran_quote.init_db(db)

        _splash.progress(100, 'Quran loaded, backup database activation...')

        # TODO: Automatic loading of last opened file ?

        _splash.deleteLater()

        # SIGNALS
        self.navigator.goto.connect(self.goTo)

        self.audio_recorder.audio_pike.connect(self.statusbar.record_volume.setValue)
        self.audio_recorder.progress.connect(lambda x: self.statusbar.updateRecording(x))

        self.viewer.documentLoaded.connect(partial(self.statusbar.updateStatus, 100, "Reference Loaded"))
        self.viewer.pageChanged.connect(self.changePage)
        self.viewer.pageChanged.connect(self.statusbar.updatePage)
        self.viewer.pageChanged.connect(self.topic_display.changePage)
        self.exporter.PDF_exporter.progress.connect(self.statusbar.updateStatus)

        def insertReference(s, v):
            self.typer.insertPlainText(f"(#_REF_{s}_{v}_#)")

        self.quran_quote.result_insert.connect(self.typer.insertAyat)
        self.quran_quote.result_reference.connect(insertReference)
        self.quran_search.result_insert.connect(lambda s, v: self.typer.insertAyat(*self.quran_quote.query(f'{s}:{v}')))
        self.quran_search.result_reference.connect(insertReference)
        self.quran_search.result_goto.connect(self.goToReference)

        self.typer.contentChanged.connect(partial(self.summary_view.build, self.typer.document()))
        self.typer.contentChanged.connect(self.summary_view.updateSummaryHighLight)

        self.window_title.min_button.clicked.connect(self.showMinimized)
        self.window_title.close_button.clicked.connect(self.close)
        self.windowTitleChanged.connect(self.window_title.setTitle)

        self.setWindowTitle(f'{self._variant} v{G.__ver__}')

        super(TyperWIN, self).show()
        self.typer.setFocus()

        # if app ran from a file opening, loads it
        if len(sys.argv) == 2:
            self.openProject(sys.argv[1])

    # FILE OPERATION

    def newProjectDialog(self):
        """
        Display dialog to create a new project
        """

        # we first make sure that changes has been saved
        if self.checkChanges():
            # markin file as saving
            self.statusbar.updateSavedState(1)

            # open new file dialog
            dialog = QFileDialog(None, "New Project", G.__abs_path__)
            dialog.setFileMode(dialog.AnyFile)
            dialog.setDefaultSuffix(G.__ext__)
            dialog.setNameFilter(f"Typer Files (*.{G.__ext__});;All files (*.*)")
            dialog.setAcceptMode(dialog.AcceptSave)

            if dialog.exec_() == dialog.Accepted:
                filename = dialog.selectedFiles()
                filename = filename[0]

                # init a new database for the file
                self.makeDB(filename)
                self._file = filename

                # reset some ui's settings
                self.viewer_frame.hide()
                self.toolbar.buttons['viewer'].setDisabled(True)

                # marks file as saved
                self.statusbar.updateSavedState(2)

    def openProjectDialog(self):
        """
        Display dialog to open an existing project
        """
        # we first make sure that changes has been saved
        if self.checkChanges():

            dialog = QFileDialog(None, "Open a project", G.__abs_path__)
            dialog.setFileMode(dialog.ExistingFile)
            dialog.setDefaultSuffix(G.__ext__)
            dialog.setNameFilter(f"Typer Files (*.{G.__ext__});;All files (*.*)")
            dialog.setAcceptMode(dialog.AcceptOpen)

            if dialog.exec_() == dialog.Accepted:
                filename = dialog.selectedFiles()
                filename = filename[0]

                self.openProject(filename)

                # Some UI settings
                self.toolbar.buttons['viewer'].setDisabled(False)
                self.toolbar.buttons['save'].setDisabled(True)

    def openProject(self, filename):
        """
        Open a project
        """

        # marking file as saving
        self.statusbar.updateSavedState(1)
        self.modified.clear()

        self._file = filename
        nice_name = os.path.splitext(os.path.split(filename)[1])[0]

        self.updateStatus(15, 'Reconnecting DB...')
        self.reconnectDBFile()
        self.updateStatus(30, 'Loading project')
        self.loadBook()
        self.updateStatus(50, 'Loading settings')
        self.loadSettings()
        self.updateStatus(85, 'Loading book')
        self.loadProject()

        self.setWindowTitle(f'{nice_name} - {self._variant} v{G.__ver__}')

        # we mark the file as saved since it's freshly loaded
        self.statusbar.updateSavedState(2)

        self.updateStatus(100, f'{nice_name} successfully loaded')

    @G.log
    def backup(self):
        """
        make a vacuum of the current file into backup.db, in case of crash of fail at save
        TODO: autosave of the current page ?
        """
        self.updateStatus(0, 'Backup done')

        cwd = G.rsc_path('backup.db')
        # we first try to remove the old backup file
        try:
            os.remove(cwd)

        except FileNotFoundError as e:
            G.exception(e)

        # now we vacuum our file in it
        self.db_file.exec_(f"VACUUM main INTO '{cwd}';")

        self.updateStatus(100, 'Backup done')

    def loadProject(self):
        """
        Load a project file
        """
        # check if the current page exists in the book
        if self.page_nb in self._book:
            self.typer.clear()

            self.typer.setHtml(self._book[self.page_nb])

            # positioning the cursor in the last saved position
            tc = self.typer.textCursor()
            tc.movePosition(tc.MoveOperation.End, tc.MoveMode.MoveAnchor)
            self.typer.setTextCursor(tc)
            tc.select(tc.SelectionType.BlockUnderCursor)

            # rebuild the summary (F2)
            self.summary_view.build(self.typer.document())

        self.statusbar.updateStatus(100, "Book loaded")

    def saveProject(self):
        """
        Save current project and create a new file if needed
        """
        G.warning('saving Project')
        # if file hasn't been saved yet : ask for file
        if not self.db_file:
            self.newProjectDialog()
            return

        # marking file as saving
        self.statusbar.updateSavedState(1)

        # make sure the file's db is connected
        self.reconnectDBFile()
        self.backup()

        # save current page
        self._book[self.page_nb] = self.typer.toHtml()

        # get total modified page for progress display
        delta, total = 100 / max(1, len(self.modified)), 0

        for page in self.modified:
            if len(self.typer.toPlainText()) and page in self._book:
                q = self.db_file.exec_(f'SELECT * FROM book WHERE page={page}')
                q.next()

                # make sure we can get our page back
                quoted_page = html.escape(self._book[page])

                # update the page in db if existing
                if q.value(0):
                    self.db_file.exec_(f'UPDATE book SET text="{quoted_page}" WHERE page={page}')

                # else create new one
                else:
                    self.db_file.exec_(f'INSERT INTO book (text, page) VALUES ("{quoted_page}", {page})')

                self.statusbar.updateStatus(total, f'Page {page} saved')
                total += delta

        # update widgets
        self.statusbar.updateSavedState(2)
        self.toolbar.buttons['save'].setDisabled(True)

        # final save process
        self.modified.clear()
        self.saveSettings()
        self.statusbar.updateStatus(100, "Book saved")

    @G.log
    def reconnectDBFile(self) -> QSqlDatabase:
        """
        if DB is closed / disconnected, we check the the state
        :return: None if file doesn't exists
        """
        if self._file and os.path.isfile(self._file):
            connection = QSqlDatabase.addDatabase("QSQLITE")
            connection.setDatabaseName(self._file)
            self.db_file = connection.database()

            return self.db_file

    # REFERENCE

    @G.log
    def goTo(self, page: int = None):
        """
        Move to the given page
        """

        # If no page is specified then ask where we want to go
        if page is None:
            page, ok = QInputDialog.getInt(
                self,
                "Go to page ?",
                "Page :",
                value=self.page_nb,
                min=0,
                max=self.viewer.doc.page_count - 1
            )
        else:
            # making same state as if QInputDialog was filled
            ok = True

            # closing the navigator before updating
            if self.navigator.isVisible():
                self.navigator.close()

        # updating the PDF view
        if ok:
            self.viewer.current_page = page
            self.viewer.load_page(page)

    @G.log
    def goToReference(self, s, v, cmd=''):
        """
        Working with the Quran, we ignore the first two parameters which come from QuranWorker.QuranQuote
        and are not used here.
        :param cmd: with format  int:int
        """
        with G.SQLConnection("quran.db") as db:
            # if the 'cmd' option isn't specified
            if cmd != '':
                s, v = cmd.split(':')

            # we get the page where the ayat is in the Quran
            # FIXME: need adjustment, database in inaccurate
            q = db.exec_(f"SELECT page FROM pages WHERE surat={s} AND verse>={v}")
            q.next()
            page = q.value(0) + 1

            # load PDF's page
            self.viewer.load_page(page)

            # if the PDF is "connected" then update the current document
            if self._settings['connect_to_ref']:
                self.changePage(page)

    def loadReferenceDialog(self):
        """
        Open a dialog to load a new reference (PDF)
        """
        # if file hasn't been saved yet : ask for file
        if not self.db_file:
            res = QMessageBox.critical(
                None,
                "File's not saved",
                "<b>File's not saved</b>, you need to save file first",
                buttons=QMessageBox.Cancel,
                defaultButton=QMessageBox.Ok
            )

            if res == QMessageBox.Cancel:
                return

            self.newProjectDialog()

        current_dir = os.path.dirname(self._file)

        dialog = QFileDialog(None, "Open a reference's PDF", current_dir)
        dialog.setFileMode(dialog.ExistingFile)
        dialog.setDefaultSuffix("pdf")
        dialog.setNameFilter("Pdf Files (*.pdf)")
        dialog.setAcceptMode(dialog.AcceptOpen)

        if dialog.exec_() == dialog.Accepted:
            self._settings['reference'] = filename = dialog.selectedFiles()[0]

            # we first check if the reference PDF is in same folder as project,
            # if so, we make the path relative, otherwise absolute

            if filename.startswith(current_dir):
                filename = filename.replace(current_dir, '')

            # we add some new reference parameters
            self._settings.update({'reference': filename, 'page': 0})

            self.saveProject()
            self.loadReference()

            self.db_file.exec_('''
            CREATE TABLE "topics" (
                "name"	TEXT,
                "page"	INTEGER,
                "domain"	TEXT    DEFAULT 'theme'
            )
            ''')

            self.viewer_frame.show()
            self.saveSettings()

    @G.log
    def loadReference(self):
        """
        Load the current reference in settings
        """
        path = self._settings['reference']

        if path != '':
            # check if path is relative '/...' or absolute
            if path.startswith('/'):
                path = G.abs_path(path[1:])

            # load the topics linked to the page
            self.topic_display.load_topics(self.reconnectDBFile())

            try:
                # trying to open the PDF and load in the viewer
                self.viewer.load_doc(path)
                self.viewer.load_page(int(self._settings['page']))

                self.toolbar.buttons['viewer'].setDisabled(False)
                self.statusbar.setConnection(os.path.basename(path))

            except RuntimeError as e:
                G.exception(e)
                # if any error occurs
                QMessageBox.critical(
                    None,
                    "Typer - Can't open reference",
                    f"<b>Can't open reference</b><br><i>{repr(e)}</i>",
                )
                self.viewer_frame.hide()
                return

        else:
            # if ever path isn't valid we hide the PDF viewer
            self.viewer_frame.hide()
            self.toolbar.buttons['viewer'].setDisabled(True)

    @G.log
    def changePage(self, page: int):
        """
        Update the current page
        """
        # we first save the current page to book
        if self._settings['connect_to_ref'] and len(self.typer.toPlainText()):
            self._book[self.page_nb] = self.typer.toHtml()

        self.typer.clear()

        self.page_nb = page

        # load the current page if exists
        try:
            self.typer.document().setHtml(self._book[self.page_nb])
            self.typer.ensureCursorVisible()

        except KeyError:
            pass

        self.statusbar.updatePage(page)
        self.saveCurrentPage(page)

        return True

    # SETTINGS

    @G.log
    def setSettings(self, setting: str, state: str | int):
        """
        Apply setting
        :param setting: setting's name
        :param state: setting's attribute
        """
        if setting in self._settings:
            self._settings[setting] = state

        self.saveSettings()

        # set the current page as modified
        self.setModified()

    @G.log
    def loadSettings(self):
        """
        Load current settings from current project
        """

        # we first load the project's words dictionnary
        w = dict()
        try:
            q = self.db_file.exec_("SELECT * FROM dict")
        except AttributeError as e:
            G.exception(e)
            return

        # we reset the occurence list of the text editor
        self.typer.occurences.clear()
        self.typer.occurences['news'] = set()
        self.typer.occurences['updated'] = set()

        while q.next():
            # we get the word and its occurence
            word, value = q.value(0), q.value(1)

            # we get the first three characters and store the candidates
            try:
                self.typer.occurences[word[:3]]["candidates"][word] = value
            except KeyError as e:
                self.typer.occurences[word[:3]] = {
                    "best": word,
                    "candidates": {
                        word: value
                    }
                }

        # now we load the rest of settings
        q = self.db_file.exec_("SELECT * FROM settings")
        self._settings.clear()
        while q.next():
            self._settings[q.value('field')] = q.value('value')

        # we update the widgets' visibility
        self.summary_view.setVisible(bool(self._settings['summary_visible']))
        self.viewer_frame.setVisible(bool(self._settings['viewer_visible']))

        # if it's not connected to a PDF reference, we update the viewer and current page
        if not self._settings['connect_to_ref']:
            if len(self._book) > 1:
                QMessageBox.warning(
                    None,
                    "Bad data",
                    """<b>Inconsistent data</b>, the file isn't connected to it's reference but more than one
                    page is filled, all data will be added to the first page.""",
                    defaultButton=QMessageBox.Ok
                )

            # otherwise we switch the current page to 0
            self.changePage(0)

            for page in self._book:
                # we update the first page with the rest of the book
                if page != 0:
                    self._book[0] += self._book.pop(page)
                    break

        self.loadReference()

        # we update the cursor
        cursor = self.typer.textCursor()
        cursor.setPosition(self._settings['last_position'], cursor.MoveMode.MoveAnchor)

        self.typer.ensureCursorVisible()
        self.typer.setTextCursor(cursor)

    @G.log
    def saveSettings(self):
        """
        Save current settings and occurence list
        :return:
        """
        words = self.typer.occurences
        G.warning('SAVING', self._settings)

        # getting the step of progress
        # FIXME: actually not used since it take a lot of ressource to refresh the UI..
        try:
            length = sum(map(lambda x: len(x['candidates']), [words[y] for y in words if len(y) == 3]))
            s = 0, 100 / float(length)
        except ZeroDivisionError:
            s = 100
        finally:
            p = 0

        # we first check if database is still connected
        self.reconnectDBFile()

        # and we appends all fresh words
        for root in words:
            if len(root) == 3:
                for word in words[root]["candidates"]:
                    occurence = words[root]["candidates"][word]
                    # adding new occurence word
                    if word in words["news"]:
                        self.db_file.exec_(f'INSERT INTO dict (occurence, word) VALUES ({occurence}, "{word}")')

                    # if the word was already in the occurence list database, just update the occurence num
                    elif word in words["updated"]:
                        self.db_file.exec_(f'UPDATE dict SET occurence={occurence} WHERE word="{word}"')

                    # increment step progress
                    # TODO: updating the progressBar was slowing the process, update every 10 words ?
                    # p += s

        words["news"].clear()
        words["updated"].clear()

        # check if database is still connected
        # FIXME: why the db disconnects ?
        self.reconnectDBFile()

        # saving other settings
        self.db_file.exec_(f"UPDATE settings SET value=\"{self._settings['reference']}\" WHERE field='reference'")
        self.db_file.exec_(f"UPDATE settings SET value=\"{self._settings['connect_to_ref']}\" WHERE field='connect_to_ref'")

        self.saveVisibilitySettings()
        self.saveCurrentPage(self.page_nb)

        # making a backup of the current file
        # self.backup()

    @G.log
    def saveVisibilitySettings(self):
        """
        Only save the visibility settings of the UI, to make sure it's fast enough to be seamless
        """
        try:
            self.db_file.exec_(f"UPDATE settings SET value={self.typer.textCursor().position()} WHERE field='last_position'")
            self.db_file.exec_(f"UPDATE settings SET value='{int(self.summary_view.isVisible())}' WHERE field='summary_visible'")
            self.db_file.exec_(f"UPDATE settings SET value='{int(self.viewer_frame.isVisible())}' WHERE field='viewer_visible'")

        except AttributeError as e:
            G.exception(e)
            # we kind of force the save of these settings, bullet proof !
            pass

    @G.log
    def saveCurrentPage(self, page: int):
        """
        Light function to only update current page in project settings
        :param page: page settings to update
        """
        self.db_file.exec_(f"UPDATE settings SET value={page} WHERE field='page'")

    # BOOK

    @G.log
    def loadBook(self):
        """
        Load pages' data from the project file
        """
        try:
            self.typer.clear()
            self._book.clear()

            # append each page from the SQL db
            q = self.db_file.exec_("SELECT * FROM book")

            while q.next():
                self._book[q.value('page')] = html.unescape(q.value('text'))

        except AttributeError as e:
            G.exception(e)
            pass

    @G.log
    def saveTopics(self, topic_add: list, topic_delete: list):
        """
        Update the topics for the current page
        :param topic_add: list of topics to be added
        :param topic_delete: list of topics to be deleted
        """
        # we first make sure the db is connected
        self.reconnectDBFile()

        # loop to remove all topics from list
        for topic in topic_delete:
            self.db_file.exec_(f"DELETE FROM topics WHERE name=\"{topic}\" AND context={self.page_nb}")

        # loop to add all topics from list
        for topic in topic_add:
            q = self.db_file.exec_(f"SELECT * FROM topics WHERE name=\"{topic}\" AND context={self.page_nb}").next()

            # if the topic doesn't exist on this page, we add it
            if not q:
                self.db_file.exec_(f"INSERT INTO topics ('name', 'page') VALUES (\"{topic}\", {self.page_nb})")

    # OTHER

    def setModified(self):
        """
        Update which page will need to be saved and marked as modified
        """
        self.modified.add(self.page_nb)

        # displaying the red bullet to indicates file isn't saved
        self.statusbar.updateSavedState(0)

        # save button now enabled
        self.toolbar.buttons['save'].setDisabled(False)

    @G.log
    def makeDB(self, filename):
        """
        First creation of a new project database
        :param filename: file's path
        """

        # if we reached this point, means that user confirmed overwrite of file
        if os.path.isfile(filename):
            try:
                os.remove(filename)

            except PermissionError as e:
                G.exception(e)

                QMessageBox.critical(
                    None,
                    "Typer - Can't override",
                    "<b>Can't override file</b> : \n%s" % e.strerror,
                )

                return

        # if successfully flushed we create the db
        connection = QSqlDatabase.addDatabase("QSQLITE")
        connection.setDatabaseName(filename)

        # just checking if the db has been opened
        if not connection.open():
            QMessageBox.critical(
                None,
                "Typer - DB Error",
                "<b>Database Error</b> :\n %s" % connection.lastError().databaseText(),
            )

            return

        query = QSqlQuery()
        # we defined the automatic vaccum of the SQLLite file to prevent big size
        query.exec_('''PRAGMA auto_vacuum = '1';''')

        query.exec_('''
        CREATE TABLE "book" (
            "id"	INTEGER UNIQUE,
            "text"	BLOB,
            "page"	INTEGER DEFAULT 1,
            PRIMARY KEY("id" AUTOINCREMENT)
        )''')

        query.exec_('''
        CREATE TABLE "pages" (
            "id"	INTEGER UNIQUE,
            "name"	TEXT,
            PRIMARY KEY("id" AUTOINCREMENT)
        )''')

        query.exec_('''
        CREATE TABLE "dict" (
            "word"	TEXT,
            "occurence"	INTEGER
        )''')

        query.exec_('''
        CREATE TABLE "settings" (
            "field"	TEXT,
            "value"	INTEGER
        )''')

        # the default settings
        # TODO: Change
        settings = {
            'last_position': '0',
            'summary_visible': '0',
            'reference': '',
            'page': '0',
            'connect_to_ref': '0',
            'viewer_visible': '0',
            'dark_mode': '1'
        }

        for stg in settings:
            query.exec_(f"INSERT INTO settings ('field', 'value') VALUES ('{stg}', '{settings[stg]}');")

        # adding the current page to the db
        self._book[0] = self.typer.toHtml()
        query.exec_(f"INSERT INTO book (text, page) VALUES ('{html.escape(self._book[0])}', 0)")

    @G.debug
    def checkChanges(self):
        """
        Checking if changes has been done, returns true if everythin went fine
        """
        # check the modified list and reconnect the database if it's disconnected
        if len(self.modified) and self.reconnectDBFile():

            dialog = QMessageBox.critical(
                None,
                "Typer - changes not saved",
                "<b>Changes not saved</b>, continue ?",
                buttons=QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel
            )

            # now we can ask for save
            if dialog in (QMessageBox.Save, QMessageBox.No):
                if dialog == QMessageBox.Save:
                    self.saveProject()

                return True

        else:
            return True

    def spellBuilt(self):
        """
        Load or reload the realtime spellchecker's database
        """
        self.typer.symspell = self.dictionnary.sympell

        # then we call the rehighlight of the current page
        self.typer.syntaxhighlighter.rehighlight()

    def recordAudio(self):
        """
        Start or stop an audio record and insert a marker in the document
        TODO: editable naming convention
        """

        # if the current file is saved and
        if not self.recording and self.reconnectDBFile() and len(self.db_file.tables()):
            self.updateStatus(0, 'Start recording')

            # we define the audio file's name
            now = datetime.now()
            now_format = now.strftime("%d-%m-%Y_%H-%M-%S")

            # we extract the current file name
            file_name = os.path.split(self.db_file.databaseName())[1].split(".")[0]
            self.audio_recorder.filename = f"{file_name}_{now_format}_{now}"

            # starting audio record
            self.audio_recorder.start()

            # and insert the marker in document
            # TODO: nice marker as icon and store data hidden (Paragraph User data ?)
            cursor = self.typer.textCursor()
            cursor.select(QTextCursor.WordUnderCursor)
            cursor.insertBlock()

            self.typer.insertHtml(f"<p>\u266C {self.audio_recorder.filename} \u266C</p>")

        # otherwise if it's already in record mode, we stop
        elif self.recording:
            self.updateStatus(0, 'Record Stopped')
            self.audio_recorder.stop()

        # else (means we aren't recording AND file is'nt saved
        else:
            return

        self.recording = not self.recording
        self.statusbar.setRecordingState(self.recording)

    # UI

    def exportDialog(self):
        """
        Preparing the PDF export
        """

        # We forward all wanted settings to the TyperExport module
        self.exporter.settings.update({
            'book': self._book,
            'typer': self.typer,
            'viewer': self.viewer,
            'topics': self.topic_display.topics,
            'dark_mode': self.dark_mode,
            'multi_page': self._settings['connect_to_ref']
        })

        # then display export's dialog
        self.exporter.show()

    def navigatorDialog(self):
        """
        A simple function which prepare the Navigator
        """
        self.navigator.buildMap(self._book)
        self.navigator.show()

    def QuranDialog(self):
        """
        Function to open the Quran Insert / Jump dialog
        """

        # making sure the quran db is connected
        with G.SQLConnection('quran.db') as db:
            self.quran_quote.show()
            self.quran_quote.init_db(db)

    def hadithDialog(self):
        """
        Function to open the Hadith search dialog
        """
        # declaring the dialog
        dial = HadithSearch(self)

        with G.SQLConnection('hadith.db') as db:
            dial.show()
            dial.init_db(db)
            dial.result_click.connect(self.typer.insertHtml)

    def toggleWidgetDisplay(self, widget: QWidget):
        """
        Show / Hide the given widget
        """
        if widget == self.viewer_frame and self._settings['reference'] != '' or widget != self.viewer_frame:
            # toggle visibility
            widget.setVisible(not widget.isVisible())

            # just update few settings to keep seamless
            self.saveVisibilitySettings()

    def setDarkMode(self):
        """
        Active the darkmode by changing the palette
        TODO: Enable toggling
        """
        QApplication.setStyle(QStyleFactory.create("Fusion"))
        darkPalette = QPalette()
        darkColor = QColor(45, 45, 45)
        disabledColor = QColor(127, 127, 127)
        darkPalette.setColor(QPalette.ColorRole.Window, darkColor)
        darkPalette.setColor(QPalette.ColorRole.WindowText, Qt.white)
        darkPalette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 18))

        darkPalette.setColor(QPalette.ColorRole.AlternateBase, darkColor)
        darkPalette.setColor(QPalette.ColorRole.ToolTipBase, Qt.white)
        darkPalette.setColor(QPalette.ColorRole.ToolTipText, Qt.white)
        darkPalette.setColor(QPalette.ColorRole.Text, Qt.white)

        darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabledColor)
        darkPalette.setColor(QPalette.ColorRole.Button, darkColor)
        darkPalette.setColor(QPalette.ColorRole.ButtonText, Qt.white)
        darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabledColor)
        darkPalette.setColor(QPalette.ColorRole.BrightText, Qt.red)
        darkPalette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))

        darkPalette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        darkPalette.setColor(QPalette.ColorRole.HighlightedText, Qt.black)
        darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabledColor)

        QApplication.setPalette(darkPalette)
        self.setStyleSheet("""QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; """)

        self.typer.setStyleSheet('''
            background: #fff4d5;
            color: #313539;
        ''')
        # custom style for scollbars
        self.typer.setStyleSheet('''
QTextEdit {
    background: #1b1b1b;
    color: #a9b7c6;
    selection-background-color: #214283;
}
img { width:100%; }
QScrollBar {
  border: none;
  background: rgb(38, 45, 68);
  border-radius: 0px;
}
QScrollBar:vertical {
    width: 14px;
    margin: 15px 0 15px 0;
}
QScrollBar:horizontal {
    height: 14px;
    margin: 0 15px 0 15px;
}

/*  HANDLE BAR VERTICAL */
QScrollBar::handle {
  background-color: rgb(71, 80, 122);
  border-radius: 7px;
}
QScrollBar::handle:vertical { min-height: 30px; }
QScrollBar::handle:horizontal { min-width: 30px; }

QScrollBar::handle:hover{ background-color: #214283; }
QScrollBar::handle:pressed { background-color: #1d5bd5; }

/* BTN TOP - SCROLLBAR */
QScrollBar::sub-line {
  border: none;
  background-color: rgb(55, 59, 90);
  subcontrol-origin: margin;
  border-top-left-radius: 7px;
}
QScrollBar::sub-line:vertical {
  height: 15px;
  border-top-right-radius: 7px;
  subcontrol-position: top;
}
QScrollBar::sub-line:horizontal {
  width: 15px;
  border-bottom-left-radius: 7px;
  subcontrol-position: left;
}
QScrollBar::sub-line:hover { background-color: #214283; }
QScrollBar::sub-line:pressed { background-color: #1d5bd5; }

/* BTN BOTTOM - SCROLLBAR */
QScrollBar::add-line:vertical {
  border: none;
  background-color: rgb(55, 59, 90);
  height: 15px;
  border-bottom-left-radius: 7px;
  border-bottom-right-radius: 7px;
  subcontrol-position: bottom;
  subcontrol-origin: margin;
}
QScrollBar::add-line:vertical:hover { background-color: #214283; }
QScrollBar::add-line:vertical:pressed { background-color: #1d5bd5; }

/* RESET ARROW */
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical { background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
''')

    def currentCursor(self) -> QTextCursor:
        """
        Get the current cursor from the document
        """
        return self.typer.textCursor()

    def updateTextCursor(self, line: int):
        """
        Update the document and move to the wanted line
        """
        tc = QTextCursor(self.typer.document().findBlockByLineNumber(line))
        tc.movePosition(tc.EndOfBlock)

        # update textCursor
        self.typer.setTextCursor(tc)

    @G.debug
    def updateStatus(self, val=0, msg=''):
        """
        Update the statusbar
        :param val: Progress value
        :param msg: Message (additional)
        """
        self.statusbar.updateStatus(val, msg)

    # INHERIT

    def keyPressEvent(self, e: QKeyEvent):
        """
        Handle the key pressed in the main UI, forwards some to the document editor,
        and receive some from the document editor
        ! Some of these shortcut are handled by the MainComponents.Toolbar widget
        """
        super(TyperWIN, self).keyPressEvent(e)

        # forwarding the event to the toolbar to shortcut
        super(Toolbar, self.toolbar).keyPressEvent(e)

        # we get the status of Ctrl Alt or Shift, etc
        modifiers = QApplication.keyboardModifiers()

        # All the Control modifiers
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if e.key() == Qt.Key.Key_G:
                self.goTo()

        # Override the page_up and page_down to switch between project's pages
        elif e.key() == Qt.Key.Key_PageUp:
            # if Shift modifier pressed, it will search for the closest filled page in book
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                keys = [i for i in sorted(self._book.keys()) if i < self.viewer.current_page]
                target = keys[-1] if len(keys) else self.viewer.current_page
            else:
                target = max(0, self.viewer.current_page - 1)

            self.viewer.load_page(target)
            if self._settings['connect_to_ref'] == 1:
                self.changePage(target)

        elif e.key() == Qt.Key.Key_PageDown:
            # if Shift modifier pressed, it will search for the closest filled page in book
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                keys = [i for i in sorted(self._book.keys()) if i > self.viewer.current_page]
                target = keys[0] if len(keys) else self.viewer.current_page
            else:
                target = min(self.viewer.current_page + 1, self.viewer.doc.page_count - 1)

            self.viewer.load_page(target)
            if self._settings['connect_to_ref'] == 1:
                self.changePage(target)

    def closeEvent(self, e: QCloseEvent) -> None:
        """
        Preventing the app to close if not saved
        """

        if len(self.modified):

            # we display a dialog to ask user choice
            res = QMessageBox.warning(
                None,
                "File's not saved",
                "<b>File's not saved</b>, would you like to save before closing ?",
                buttons=QMessageBox.Cancel | QMessageBox.No | QMessageBox.Save,
                defaultButton=QMessageBox.Save
            )

            if res == QMessageBox.Save:
                self.saveProject()

            # if used wants to cancel we abort the save
            elif res == QMessageBox.Cancel:
                e.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # checking if the current font is available in the system,
    # otherwise we load it from rsc/fonts folder
    # we also check for every additional fonts needed and listed in G.__additional_font__
    for font in G.__additional_fonts__:

        # checking if font is available
        if font not in QFontDatabase().families():
            G.warning(f'"{font}" font unavailable, loading from resource folder')

            # if not we load the ttf resource file
            QFontDatabase.addApplicationFont(G.rsc(f'{font}.ttf'))

        # we add the variants of the font if specified

    win = TyperWIN()

    app.exec_()