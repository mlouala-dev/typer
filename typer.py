# بسم الله الرحمان الرحيم
import sys
import os
import html

from datetime import datetime
from functools import partial
from shutil import copyfile

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from UI import QuranWorker, Editor
from UI.HadithWorker import HadithSearch
from UI.Modules import Settings, Navigator, GlobalSearch, Exporter, Jumper, TopicsBar
from UI.MainComponents import StatusBar, Summary, TitleBar, Toolbar, SplashScreen

from tools import G, PDF, Threads, S

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
    _variant = 'Mishkaat'
    _title = f"{G.__app__} {_variant}"


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
        _splash = SplashScreen(self, title=f'{self._variant} v{self._version}')
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
        self.topic_display = TopicsBar(self)
        self.viewer_frame = PDF.ViewerFrame(self.viewer, self.topic_display)

        _splash.progress(30, "Loading Hadith Database...")
        self.hadith_dialog = HadithSearch(self)
        with G.SQLConnection('hadith.db') as db:
            self.hadith_dialog.init_db(db)

        _splash.progress(40, "Loading QuranQuote...")
        self.quran_quote = QuranWorker.QuranQuote(self)

        _splash.progress(45, "Loading QuranSearch...")
        self.quran_search = QuranWorker.QuranSearch(self)
        self.find_dialog = GlobalSearch(self)
        self.settings_dialog = Settings(self, self.typer)

        _splash.progress(50, "Loading Navigator...")
        self.navigator = Navigator(self)
        self.exporter = Exporter(self)
        self.jumper = Jumper(self)

        self.viewer_frame.hide()
        self.summary_view.hide()

        self.toolbar = Toolbar(self)

        _splash.progress(55, "Loading UI Window Title...")
        self.window_title = TitleBar(self)

        _splash.progress(55, "Loading UI Main Layout...")
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.insertWidget(0, self.viewer_frame)
        self.splitter.addWidget(self.typer)
        self.splitter.addWidget(self.summary_view)
        self.splitter.setStretchFactor(0, 33)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 20)

        _splash.progress(55, "Loading UI Status Bar...")
        self.statusbar = StatusBar()

        _splash.progress(70, "Loading Audio Recorder...")
        self.audio_recorder = Threads.AudioWorker()
        self.recording = False

        # Main layout operations
        _layout.addWidget(self.window_title)
        _layout.addWidget(self.toolbar)
        _layout.addWidget(self.splitter)
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

        _splash.progress(75, "Applying dark theme...")
        if self.dark_mode:
            self.setDarkMode()

        self.modified.clear()

        # DATABASES
        if not S.LOCAL.BOOKMAP.active:
            self.toolbar.buttons['book_jumper'].setEnabled(False)

        # additional books data (for other variants)
        _splash.progress(85, "Loading Quran's database...")

        with G.SQLConnection('quran.db') as db:
            _splash.progress(95, "Init Quran's widget...")
            self.quran_quote.init_db(db)

        _splash.progress(100, 'Quran loaded, backup database activation...')


        # TODO: Automatic loading of last opened file ?

        _splash.deleteLater()

        # SIGNALS
        self.typer.cursorPositionChanged.connect(self.summary_view.updateSummaryHighLight)
        self.summary_view.clicked.connect(self.updateTextCursor)
        self.typer.contentEdited.connect(self.setModified)

        self.navigator.goto.connect(self.goTo)

        self.audio_recorder.audio_pike.connect(self.statusbar.record_volume.setValue)
        self.audio_recorder.progress.connect(lambda x: self.statusbar.updateRecording(x))

        self.viewer.documentLoaded.connect(partial(self.statusbar.updateStatus, 100, "Reference Loaded"))
        self.viewer.pageChanged.connect(self.changePage)
        self.exporter.PDF_exporter.progress.connect(self.statusbar.updateStatus)

        def insertReference(s, v):
            self.typer.insertPlainText(f"(#_REF_{s}_{v}_#)")

        self.quran_quote.result_insert.connect(self.typer.insertAyat)
        self.quran_quote.result_reference.connect(insertReference)
        self.quran_quote.result_goto.connect(self.goToReference)
        self.quran_search.result_insert.connect(lambda s, v: self.typer.insertAyat(*self.quran_quote.query(f'{s}:{v}')))
        self.quran_search.result_reference.connect(insertReference)
        self.quran_search.result_goto.connect(self.goToReference)

        self.jumper.result_goto.connect(self.changePage)
        self.jumper.result_goto.connect(self.viewer.load_page)
        self.jumper.result_insert.connect(self.typer.insertBookSource)
        self.hadith_dialog.result_click.connect(self.typer.insertHtml)

        self.typer.contentChanged.connect(partial(self.summary_view.build, self.typer.document()))
        self.typer.contentChanged.connect(self.summary_view.updateSummaryHighLight)

        self.window_title.min_button.clicked.connect(self.showMinimized)
        self.window_title.close_button.clicked.connect(self.close)
        self.window_title.geometryChanged.connect(self.bakeGeometry)
        self.windowTitleChanged.connect(self.window_title.setTitle)

        self.setWindowTitle(f'{self._title} v{G.__ver__}')

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
            dialog = self.defaultDialogContext('New Project')

            if dialog.exec_() == QFileDialog.Accepted:
                filename = dialog.selectedFiles()
                filename = filename[0]

                # init a new database for the file
                self.createNewFile(filename)
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

            # creating the dialog
            dialog = self.defaultDialogContext('Open a project', filemode=QFileDialog.ExistingFile)

            if dialog.exec_() == QFileDialog.Accepted:
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

        self._file = filename

        self.updateStatus(30, 'Loading project')
        S.LOCAL.loadSettings(self._file)
        self.updateStatus(50, 'Loading settings')
        self.loadSettings()
        self.updateStatus(85, 'Loading book')
        self.loadProject()

        self.updateTitle()

        # we mark the file as saved since it's freshly loaded
        self.statusbar.updateSavedState(2)

    def loadProject(self):
        """
        Load a project file
        """
        # check if the current page exists in the book
        if self.page_nb in S.LOCAL.BOOK:
            self.typer.clear()

            self.typer.setHtml(S.LOCAL.BOOK[self.page_nb])

            # positioning the cursor in the last saved position
            tc = self.typer.textCursor()
            tc.movePosition(tc.MoveOperation.End, tc.MoveMode.MoveAnchor)
            self.typer.setTextCursor(tc)

            # rebuild the summary (F2)
            self.summary_view.build(self.typer.document())

        # flagging as not modified
        self.modified.clear()
        self.statusbar.updateStatus(100, f"Book loaded from '<i>{self.getFilesName()}</i>'")

    def saveAsProject(self):
        """
        Open the save dialog to get the filepath where we'll clone our project
        """

        # querying new file's name
        dialog = self.defaultDialogContext('Save Project As...', path=os.path.dirname(self._file))

        if dialog.exec_() == QFileDialog.Accepted:
            new_file_path = dialog.selectedFiles()[0]

            # we'll simply clone the old file, and save everything to the new
            copyfile(self._file, new_file_path)

            # updating the protected _file attr
            self._file = new_file_path

            self.updateTitle()

            # and finally save to the new file
            self.saveProject()

    def saveProject(self):
        """
        Save current project and create a new file if needed
        """

        # if file hasn't been saved yet : ask for file
        if not S.LOCAL.db:
            self.newProjectDialog()
            return

        # marking file as saving
        self.statusbar.updateSavedState(1)

        # make sure the file's db is connected
        S.LOCAL.backup()

        # save current page
        S.LOCAL.BOOK[self.page_nb] = self.typer.toHtml()
        S.LOCAL.BOOK.saveAllPage()

        # update widgets
        self.statusbar.updateSavedState(2)
        self.toolbar.buttons['save'].setDisabled(True)

        # final save process
        self.saveSettings()
        self.statusbar.updateStatus(100, f"Book saved to '<i>{self.getFilesName()}</i>'")

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
            self.changePage(page)
            self.viewer.load_page()

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
            if S.LOCAL.connected:
                self.changePage(page)

    def loadReferenceDialog(self):
        """
        Open a dialog to load a new reference (PDF)
        """
        # if file hasn't been saved yet : ask for file
        if not S.LOCAL.db:
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

        current_dir = os.path.dirname(S.LOCAL.filename)

        dialog = QFileDialog(None, "Open a reference's PDF", current_dir)
        dialog.setFileMode(dialog.ExistingFile)
        dialog.setDefaultSuffix("pdf")
        dialog.setNameFilter("PDF Files (*.pdf)")
        dialog.setAcceptMode(dialog.AcceptOpen)

        if dialog.exec_() == dialog.Accepted:
            filename = dialog.selectedFiles()[0]

            S.LOCAL.digestPDF(filename)

            self.saveProject()
            self.loadReference()

            self.updateStatus(90, 'PDF Connected and Loaded')
            self.viewer_frame.show()
            self.saveSettings()

    @G.log
    def loadReference(self):
        """
        Load the current reference in settings
        """

        if S.LOCAL.PDF:
            try:
                # trying to open the PDF and load in the viewer
                self.viewer.load_doc()
                self.viewer.load_page()

                self.toolbar.buttons['viewer'].setDisabled(False)
                self.statusbar.setConnection(S.LOCAL.pdf_name)

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
        if S.LOCAL.connected and len(self.typer.toPlainText()):
            S.LOCAL.BOOK[self.page_nb] = self.typer.toHtml()

        elif len(self.typer.toPlainText()):
            S.LOCAL.BOOK[0] = self.typer.toHtml()

        self.page_nb = page

        if not S.LOCAL.connected:
            page = 0

        else:
            self.topic_display.changePage(page)

        self.typer.clear()

        # load the current page if exists
        try:
            self.typer.document().setHtml(S.LOCAL.BOOK[page])
            self.typer.ensureCursorVisible()

        except KeyError:
            pass

        self.statusbar.updatePage(self.page_nb)
        S.LOCAL.page = self.page_nb

        return True

    # SETTINGS

    @G.log
    def loadSettings(self):
        """
        Load current settings from current project
        """

        # we reset the occurence list of the text editor
        self.typer.occurences.clear()
        self.typer.occurences['news'] = set()
        self.typer.occurences['updated'] = set()

        for word, num in S.LOCAL.DICT.items():
            # we get the first three characters and store the candidates
            try:
                self.typer.occurences[word[:3]]["candidates"][word] = num
            except KeyError as e:
                self.typer.occurences[word[:3]] = {
                    "best": word,
                    "candidates": {
                        word: num
                    }
                }

        # we update the visual settings
        self.summary_view.setVisible(S.LOCAL.isSummaryVisible())
        self.viewer_frame.setVisible(S.LOCAL.isViewerVisible())

        self.setGeometry(*S.LOCAL.geometry)

        if S.LOCAL.maximized:
            self.showMaximized()

        self.dockViewer(not S.LOCAL.viewer_external)

        # if it's not connected to a PDF reference, we update the viewer and current page
        if not S.LOCAL.connected:
            if len(S.LOCAL.BOOK) > 1:
                QMessageBox.warning(
                    None,
                    "Bad data",
                    """<b>Inconsistent data</b>, the file isn't connected to it's reference but more than one
                    page is filled, all data will be added to the first page.""",
                    defaultButton=QMessageBox.Ok
                )

        self.changePage(S.LOCAL.page)
        self.loadReference()

        self.toolbar.buttons['book_jumper'].setEnabled(S.LOCAL.BOOKMAP.active)

        # we update the cursor
        cursor = self.typer.textCursor()
        cursor.setPosition(S.LOCAL.position, cursor.MoveMode.MoveAnchor)

        self.typer.ensureCursorVisible()
        self.typer.setTextCursor(cursor)

    @G.log
    def saveSettings(self):
        """
        Save current settings and occurence list
        """
        words = self.typer.occurences

        # and we append all fresh words
        for root in words:
            if len(root) == 3:
                for word in words[root]["candidates"]:
                    occurence = words[root]["candidates"][word]
                    # adding new occurence word
                    if word in words["news"]:
                        S.LOCAL.addDictEntry(word, occurence)

                    # if the word was already in the occurence list database, just update the occurence num
                    elif word in words["updated"]:
                        S.LOCAL.updateDictEntry(word, occurence)

        words["news"].clear()
        words["updated"].clear()

        S.LOCAL.page = self.page_nb
        S.LOCAL.saveAllSettings()

        self.saveVisibilitySettings()

        # making a backup of the current file
        S.LOCAL.backup()

    @G.log
    def saveVisibilitySettings(self):
        """
        Only save the visibility settings of the UI, to make sure it's fast enough to be seamless
        """
        S.LOCAL.position = self.typer.textCursor().position()
        S.LOCAL.summary = self.summary_view.isVisible()
        S.LOCAL.viewer = self.viewer_frame.isVisible()

        S.LOCAL.saveVisualSettings()

    # OTHER

    def setModified(self):
        """
        Update which page will need to be saved and marked as modified
        """

        try:
            assert S.LOCAL.BOOK[S.LOCAL.page] != self.typer.toHtml()
        except KeyError:
            pass
        except AssertionError:
            return
        finally:
            # displaying the red bullet to indicates file isn't saved
            S.LOCAL.setModifiedFlag()
            self.statusbar.updateSavedState(0)

            # save button now enabled
            self.toolbar.buttons['save'].setDisabled(False)
            self.toolbar.buttons['saveas'].setDisabled(False)

    @G.log
    def createNewFile(self, filename):
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

        S.LOCAL.createSettings(filename)

        # adding the current page to the db
        S.LOCAL.BOOK[0] = self.typer.toHtml()
        S.LOCAL.BOOK.savePage(0)

    @G.debug
    def checkChanges(self):
        """
        Checking if changes has been done, returns true if everythin went fine
        """
        # check the modified list
        if S.LOCAL.isModified():
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

    def getFilesName(self):
        """
        Returns the nice name of the currently opened file or 'Untitled'
        :return:
        """
        if self._file:
            # getting the name of the file without ext
            return os.path.splitext(os.path.split(self._file)[1])[0]

        else:
            return 'Untitled'

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
            'dark_mode': self.dark_mode
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

    def toggleWidgetDisplay(self, widget: QWidget):
        """
        Show / Hide the given widget
        """
        if widget == self.viewer_frame and S.LOCAL.PDF or widget != self.viewer_frame:
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

    def updateTitle(self):
        """
        Update the titleBar with the file's name and variant
        """

        self.setWindowTitle(f'{self.getFilesName()} - {self._title} v{G.__ver__}')

    @staticmethod
    def defaultDialogContext(title='', path=G.__abs_path__, filemode=QFileDialog.AnyFile) -> QFileDialog:
        """
        Returns a dialog with the default we use, file ext, file mode, etc..
        :param title: the dialog's title
        :param path: the dialog's default start path
        :param filemode: dialog's filemode, Any or Existing
        :return: a QFileDialog widget
        """
        dialog = QFileDialog(None, title, path)

        # we define some defaults settings used by all our file dialogs
        dialog.setFileMode(filemode)
        dialog.setDefaultSuffix(G.__ext__)
        dialog.setNameFilter(f"Typer Files (*.{G.__ext__});;All files (*.*)")
        dialog.setAcceptMode(dialog.AcceptSave)

        return dialog

    @G.debug
    def bakeGeometry(self):
        if not self.isMaximized():
            geo = self.geometry()
            S.LOCAL.geometry = (geo.left(), geo.top(), geo.width(), geo.height())

        S.LOCAL.maximized = self.isMaximized()

        if not self.viewer_frame.parent():
            vgeo = self.viewer_frame.geometry()

            S.LOCAL.viewer_geometry = (vgeo.left(), vgeo.top(), vgeo.width(), vgeo.height())

    def dockViewer(self, state: bool):
        self.viewer_frame.hide()

        if state:
            self.splitter.insertWidget(0, self.viewer_frame)
            self.viewer_frame.setMaximumWidth(int(self.width() / 3))
        else:
            self.viewer_frame.setParent(None)
            self.viewer_frame.setGeometry(*S.LOCAL.viewer_geometry)
            self.viewer_frame.setMaximumWidth(QWIDGETSIZE_MAX)

        self.viewer_frame.show()

    # INHERIT
    def showMaximized(self):
        # saving geometry state before maxizing
        self.bakeGeometry()
        super(TyperWIN, self).showMaximized()

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

        elif modifiers == Qt.KeyboardModifier.AltModifier:
            if e.key() == Qt.Key.Key_S:
                self.jumper.show()

        # Override the page_up and page_down to switch between project's pages
        elif e.key() == Qt.Key.Key_PageUp and S.LOCAL.BOOK:
            # if Shift modifier pressed, it will search for the closest filled page in book
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                keys = [i for i in S.LOCAL.BOOK if i < self.viewer.current_page]
                target = keys[-1] if len(keys) else self.viewer.current_page
            else:
                target = max(0, self.viewer.current_page - 1)

            S.LOCAL.page = target

            self.viewer.load_page()

            if S.LOCAL.connected:
                self.changePage(target)

        elif e.key() == Qt.Key.Key_PageDown and S.LOCAL.BOOK:
            # if Shift modifier pressed, it will search for the closest filled page in book
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                keys = [i for i in S.LOCAL.BOOK if i > self.viewer.current_page]
                target = keys[0] if len(keys) else self.viewer.current_page
            else:
                target = min(self.viewer.current_page + 1, self.viewer.doc.page_count - 1)

            S.LOCAL.page = target

            self.viewer.load_page()

            if S.LOCAL.connected:
                self.changePage(target)

    def closeEvent(self, e: QCloseEvent) -> None:
        """
        Preventing the app to close if not saved
        """

        if S.LOCAL.isModified() or (len(self.typer.toPlainText()) and not len(S.LOCAL.BOOK)):

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
                return

        self.bakeGeometry()
        S.LOCAL.saveVisualSettings()

        if S.LOCAL.viewer_external:
            self.viewer_frame.close()

        if S.LOCAL.PDF:
            try:
                self.viewer.doc.close()
            except ValueError:
                pass
            finally:
                os.unlink(S.LOCAL.PDF)


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