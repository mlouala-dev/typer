# بسم الله الرحمان الرحيم
import sys
import os
import time

from functools import partial
from shutil import copyfile

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from UI import QuranWorker, Editor
from UI.HadithWorker import HadithSearch
from UI.Dialogs import Settings, Navigator, GlobalSearch, Exporter, Jumper
from UI.Components import StatusBar, Summary, TitleBar, MainToolbar, SplashScreen, TextToolbar, TopicsBar, BreadCrumbs

from tools import G, PDF, Audio, S, T

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

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
    _file: str
    _version = G.__ver__
    _variant = ''
    _title = f"{G.__app__} {_variant}"

    modified = set()    # a list of all the modified page

    def __init__(self):
        super(TyperWIN, self).__init__()
        _splash = SplashScreen(self, title=f'{self._variant} v{self._version}')
        _splash.show()
        _layout = QGridLayout(self)

        self.setFont(G.get_font())
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowIcon(QIcon(":/ico"))
        self.setFocusPolicy(Qt.StrongFocus)

        _splash.progress(7, "Loading settings...")
        self._file = None

        self.page_nb = 0
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(1000)

        _splash.progress(10, "Loading Hadith Database...")
        self.container = QWidget(self)
        self.summary_view = Summary(self)
        G.SHORTCUT['bookmark'].register(self, partial(self.toggleWidgetDisplay, self.summary_view))
        self.typer = Editor.Typer(self)
        G.SHORTCUT['bold'].register(self)
        G.SHORTCUT['italic'].register(self)
        G.SHORTCUT['underline'].register(self)
        G.SHORTCUT['h1'].register(self)
        G.SHORTCUT['h2'].register(self)
        G.SHORTCUT['h3'].register(self)
        G.SHORTCUT['h4'].register(self)
        G.SHORTCUT['aleft'].register(self)
        G.SHORTCUT['acenter'].register(self)
        G.SHORTCUT['aright'].register(self)
        G.SHORTCUT['ajustify'].register(self)

        self.viewer = PDF.Viewer(self)
        self.topic_display = TopicsBar(self)
        self.viewer_frame = PDF.ViewerFrame(self.viewer, self.topic_display)
        G.SHORTCUT['viewer'].register(self, partial(self.toggleWidgetDisplay, self.viewer_frame))

        _splash.progress(15, "Loading Hadith Database...")
        self.hadith_dialog = HadithSearch(self)
        G.SHORTCUT['hadith_search'].register(self, self.hadith_dialog.show)

        _splash.progress(45, "Loading QuranQuote...")
        self.quran_quote = QuranWorker.QuranQuote(self)

        _splash.progress(50, "Loading QuranSearch...")
        self.quran_search = QuranWorker.QuranSearch(self)
        G.SHORTCUT['quran_search'].register(self, self.quran_search.show)
        self.find_dialog = GlobalSearch(self)
        G.SHORTCUT['find'].register(self, self.find_dialog.show)
        self.settings_dialog = Settings(self, self.typer)
        G.SHORTCUT['settings'].register(self, self.settings_dialog.show)

        _splash.progress(53, "Loading Navigator...")
        self.navigator = Navigator(self)
        G.SHORTCUT['navigator'].register(self, self.navigatorDialog)
        self.exporter = Exporter(self)
        self.jumper = Jumper(self)
        G.SHORTCUT['book_jumper'].register(self, self.jumper.show)

        self.viewer_frame.hide()
        self.summary_view.hide()

        # connecting the shortcuts
        G.SHORTCUT['new'].register(self, self.newProjectDialog)
        G.SHORTCUT['open'].register(self, self.openProjectDialog)
        G.SHORTCUT['save'].register(self, self.saveProject)
        G.SHORTCUT['saveas'].register(self, self.saveAsProject)
        G.SHORTCUT['ref'].register(self, self.loadReferenceDialog)
        G.SHORTCUT['digest'].register(self, self.digestText)
        G.SHORTCUT['listen'].register(self, self.recordAudio)
        G.SHORTCUT['note'].register(self, self.typer.insertNote)
        G.SHORTCUT['pdf'].register(self, self.exportPDFDialog)
        G.SHORTCUT['html'].register(self, self.exportHTMLDialog)
        G.SHORTCUT['quran_insert'].register(self, self.QuranDialog)

        self.toolbar = MainToolbar(self)
        self.text_toolbar = TextToolbar(self)
        self.breadcrumbs = BreadCrumbs(self)
        self.breadcrumbs.setHidden(True)

        _splash.progress(55, "Loading UI Window Title...")
        self.window_title = TitleBar(self)

        _splash.progress(60, "Loading UI Main Layout...")
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.insertWidget(0, self.viewer_frame)
        self.splitter.addWidget(self.typer)
        self.splitter.addWidget(self.summary_view)
        self.splitter.setStretchFactor(0, 33)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 20)

        _splash.progress(65, "Loading UI Status Bar...")
        self.statusbar = StatusBar()

        _splash.progress(70, "Loading Audio Recorder...")
        self.audio_recorder = Audio.AudioWorker()
        self.recording = False

        # Main layout operations
        _layout.addWidget(self.window_title)
        _layout.addWidget(self.toolbar)
        _layout.addWidget(self.text_toolbar)
        _layout.addWidget(self.breadcrumbs)
        _layout.addWidget(self.splitter)
        _layout.setRowStretch(0, 0)
        _layout.setRowStretch(1, 0)
        _layout.setRowStretch(2, 0)
        _layout.setRowStretch(3, 0)
        _layout.setRowStretch(4, 1)
        _layout.setColumnStretch(0, 1)
        _layout.setSpacing(0)
        _layout.setContentsMargins(0, 0, 0, 0)

        self.container.setLayout(_layout)
        self.setStatusBar(self.statusbar)
        self.setCentralWidget(self.container)
        self.setBaseSize(600, 800)

        _splash.progress(75, "Loading global settings...")
        S.GLOBAL.loadSettings()
        S.GLOBAL.step.connect(self.statusbar.updateStatus)
        S.LOCAL.step.connect(self.statusbar.updateStatus)
        S.POOL.state.connect(self.statusbar.loadingState)
        S.LOCAL.pageChanged.connect(self.changePage)
        S.LOCAL.pageChanged.connect(self.viewer.load_page)
        S.LOCAL.pageChanged.connect(lambda x: self.viewer_frame.setWindowTitle(f'Page {x}'))

        self.modified.clear()

        # DATABASES
        if not S.LOCAL.BOOKMAP.active:
            self.toolbar.buttons['book_jumper'].setEnabled(False)

        # additional books data (for other variants)
        _splash.progress(85, "Loading Quran's database...")

        with G.SQLConnection('quran.db') as db:
            self.quran_quote.init_db(db)
            _splash.progress(95, "Init Quran's widget...")

        _splash.progress(95, "Quran loaded, final checkups...")
        if S.GLOBAL.audio_input_device not in G.audio_input_devices_names:
            QMessageBox.critical(
                None,
                "Device not found",
                f"""<b>Audio input device '{S.GLOBAL.audio_input_device}' not found</b>, settings reverted to default : 
                '{G.audio_input_devices_names[0]}'""",
                defaultButton=QMessageBox.Ok
            )

            S.GLOBAL.audio_input_device = G.audio_input_devices_names[0]
            S.GLOBAL.saveSetting('audio_input_device')
        self.toolbar.setVisible(S.GLOBAL.toolbar)
        self.text_toolbar.setVisible(S.GLOBAL.text_toolbar)

        _splash.progress(100, 'Opening...')

        _splash.deleteLater()

        # SIGNALS
        T.SPELL.finished.connect(self.typer.W_syntaxHighlighter.rehighlight)
        T.SPELL.build()

        self.typer.contentEdited.connect(self.setModified)
        self.summary_view.clicked.connect(self.updateTextCursor)

        self.audio_recorder.audio_pike.connect(self.statusbar.record_volume.setValue)
        self.audio_recorder.progress.connect(lambda x: self.statusbar.updateRecording(x))
        self.audio_recorder.finished.connect(lambda: S.POOL.start(Audio.AudioConverter(self.audio_recorder.filename)))

        self.viewer.documentLoaded.connect(partial(self.statusbar.updateStatus, 100, "Reference Loaded"))
        self.exporter.PDF_exporter.progress.connect(self.statusbar.updateStatus)

        def insertReference(s, v):
            self.typer.insertPlainText(f"(#_REF_{s}_{v}_#)")

        self.quran_quote.result_insert.connect(self.typer.insertAyat)
        self.quran_quote.result_reference.connect(insertReference)
        self.quran_quote.result_goto.connect(self.goToReference)
        self.quran_search.result_insert.connect(lambda s, v: self.typer.insertAyat(*self.quran_quote.query(f'{s}:{v}')))
        self.quran_search.result_reference.connect(insertReference)
        self.quran_search.result_goto.connect(self.goToReference)

        self.jumper.result_insert.connect(self.typer.insertBookSource)
        self.jumper.result_ref.connect(self.typer.insertBookReference)
        self.hadith_dialog.result_click.connect(self.typer.insertHtml)

        self.typer.contentChanged.connect(partial(self.summary_view.build, self.typer.document()))
        self.typer.contentChanged.connect(self.summary_view.updateSummaryHighLight)
        self.typer.cursorPositionChanged.connect(self.summary_view.updateSummaryHighLight)

        self.window_title.min_button.clicked.connect(self.showMinimized)
        self.window_title.close_button.clicked.connect(self.close)
        self.window_title.geometryChanged.connect(self.bakeGeometry)
        self.windowTitleChanged.connect(self.window_title.setTitle)

        self.setWindowTitle(f'{self._title} v{G.__ver__}')

        super(TyperWIN, self).show()
        self.typer.setFocus()

        S.POOL.start(S.GLOBAL.AUDIOMAP)

        if S.GLOBAL.auto_load and len(S.GLOBAL.last_file):
            self.openProject(S.GLOBAL.last_file)

        elif len(sys.argv) == 2:
            # if app ran from a file opening, loads it
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
            dialog = self.defaultDialogContext('New Project', path=S.GLOBAL.default_path)

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
            dialog = self.defaultDialogContext('Open a project',
                                               path=S.GLOBAL.default_path,
                                               filemode=QFileDialog.ExistingFile,
                                               acceptmode=QFileDialog.AcceptMode.AcceptOpen)

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

            self.typer.setHtml(S.LOCAL.BOOK[self.page_nb].content)
            self.typer.textCursor().setPosition(S.LOCAL.BOOK[self.page_nb].cursor)
            self.typer.ensureCursorVisible()

            # rebuild the summary (F2)
            self.summary_view.build(self.typer.document())

        # flagging as not modified
        self.modified.clear()
        self.statusbar.updateStatus(100, f"Book loaded from <i>'{self.getFilesName()}'</i>'")

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
        self.saveCurrentPage()

        S.LOCAL.BOOK.saveAllPage()

        # update widgets
        self.statusbar.updateSavedState(2)
        self.toolbar.buttons['save'].setDisabled(True)

        # final save process
        self.saveSettings()
        self.statusbar.updateStatus(100, f"Book saved to <i>'{self.getFilesName()}'</i>'")

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
            S.LOCAL.page = page

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
                S.LOCAL.page = page

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

        dialog = QFileDialog(None, "Open a reference's PDF", S.GLOBAL.default_path)
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
        self.typer.disableAudioMap()

        if S.LOCAL.connected and len(self.typer.toPlainText()):
            self.saveCurrentPage()

        elif len(self.typer.toPlainText()):
            self.saveCurrentPage(0)

        self.page_nb = page

        if not S.LOCAL.connected:
            page = 0

        else:
            self.topic_display.changePage(page)

        self.typer.clear()

        # load the current page if exists
        try:
            self.typer.setHtml(S.LOCAL.BOOK[page].content)
            tc = self.typer.textCursor()
            tc.setPosition(S.LOCAL.BOOK[page].cursor)
            self.typer.setTextCursor(tc)
            self.typer.ensureCursorVisible()

        except KeyError:
            pass

        self.statusbar.updatePage(self.page_nb)
        self.breadcrumbs.updatePage(self.page_nb)

        self.typer.enableAudioMap()

        return True

    # SETTINGS

    @G.log
    def loadSettings(self):
        """
        Load current settings from current project
        """

        # we update the visual settings
        self.summary_view.setVisible(S.LOCAL.isSummaryVisible())
        self.viewer_frame.setVisible(S.LOCAL.isViewerVisible())

        self.setGeometry(*S.LOCAL.geometry)
        self.window_title.setMaximized(S.LOCAL.maximized)

        self.dockViewer(not S.LOCAL.viewer_external)
        self.breadcrumbs.setVisible(S.LOCAL.BOOKMAP.active)

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

        if S.LOCAL.audio_map:
            self.typer.enableAudioMap()
        else:
            self.typer.disableAudioMap()

    @G.log
    def saveSettings(self):
        """
        Save current settings and occurence list
        """
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

    def saveCurrentPage(self, page: int = -1):
        if page < 0:
            page = self.page_nb

        try:
            S.LOCAL.BOOK[self.page_nb].content = self.typer.toHtml()
            S.LOCAL.BOOK[self.page_nb].cursor = self.typer.textCursor().position()

        except KeyError:
            S.LOCAL.BOOK[self.page_nb] = S.LOCAL.BOOK.Page(
                self.typer.toHtml(),
                self.typer.textCursor().position()
            )

    def setModified(self):
        """
        Update which page will need to be saved and marked as modified
        """

        try:
            assert S.LOCAL.BOOK[S.LOCAL.page].content != self.typer.toHtml()

        except KeyError:
            S.LOCAL.setModifiedFlag()

        except AssertionError:
            S.LOCAL.unsetModifiedFlag()

        else:
            S.LOCAL.setModifiedFlag()

        finally:
            state = S.LOCAL.isModified()
            # displaying the bullet to indicates file's state
            self.statusbar.updateSavedState(0 if state else 2)

            # save button now enabled
            self.toolbar.buttons['save'].setDisabled(not state)
            self.toolbar.buttons['saveas'].setDisabled(not state)

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
        S.LOCAL.BOOK[0].content = self.typer.toHtml()
        S.LOCAL.BOOK[0].cursor = self.typer.textCursor().position()
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

    def recordAudio(self):
        """
        Start or stop an audio record and insert a marker in the document
        TODO: editable naming convention
        """

        # if the current file is saved and
        if not self.recording:
            if len(S.LOCAL.filename):
                filename = os.path.splitext(os.path.basename(S.LOCAL.filename))[0]
            else:
                filename = 'untitled'
            self.updateStatus(0, 'Start recording')

            # we define the audio file's name
            epoch_time = str(time.time()).replace('.', '_')
            epoch_data = f'<img src="audio_record_{epoch_time}" width="0" height="{int(self.typer.fontMetrics().height())}" />'
            # we extract the current file name
            self.audio_recorder.filename = str(epoch_time)

            # starting audio record
            self.audio_recorder.start()

            # and insert the marker in document
            # TODO: nice marker as icon and store data hidden (Paragraph User data ?)
            self.typer.insertPlainText(' ')
            self.typer.insertHtml(f'\u266A{epoch_data}')
            self.typer.insertPlainText(' ')

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

    def digestText(self):
        """
        raise a dialog to browse to a reference file to learn words
        """
        dialog = QFileDialog(None, 'Digest a text', S.GLOBAL.default_path)

        # we define some defaults settings used by all our file dialogs
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setDefaultSuffix(G.__ext__)
        dialog.setNameFilter(f"Digestable Files (*.{G.__ext__} *.txt);;Typer Files (*.{G.__ext__});;Text Files (*.txt)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

        if dialog.exec_() == QFileDialog.Accepted:
            filename = dialog.selectedFiles()
            filename = filename[0]
            self.updateStatus(0, 'Digesting')

            if os.path.splitext(filename)[-1] == f'.{G.__ext__}':
                import sqlite3

                db = sqlite3.connect(filename)
                cursor = db.cursor()
                source_dict = S.LOCAL.Dict(db, cursor)

                S.POOL.waitForDone()

                worker = S.LOCAL.DICT.Worker(
                    source_dict.words,
                    S.LOCAL.DICT.updateFromExisting,
                    existing={
                        'words': S.LOCAL.DICT.words,
                        'hashes': S.LOCAL.DICT.hashes,
                        'word_roots': S.LOCAL.DICT.word_roots,
                        'word_wide_roots': S.LOCAL.DICT.word_wide_roots
                    }
                )

                S.POOL.start(worker, uniq='digest')

            else:
                with open(filename, mode="r", encoding="utf-8") as f:
                    content = []
                    for line in f.readlines():
                        if T.SPELL.block_check(line):
                            content.append(line)

                    S.LOCAL.DICT.digest('\n'.join(content))

            self.updateStatus(90, 'Saving')

            self.updateStatus(100, 'Digested')

    # UI

    def exportPDFDialog(self):
        """
        Preparing the PDF export
        """

        # We forward all wanted settings to the TyperExport module
        self.exporter.settings.update({
            'typer': self.typer,
            'viewer': self.viewer
        })

        # then display export's dialog
        self.exporter.show()

    def exportHTMLDialog(self):
        tc = self.typer.textCursor()
        bf = tc.blockFormat()
        bf.setAlignment(Qt.AlignCenter)
        tc.setBlockFormat(bf)
        # for page in S.LOCAL.BOOK:
        #     if page <= 50:
        #         continue
        #     if page >= 79:
        #         break
        #     content = S.LOCAL.BOOK[page]
        #     content = re.sub('<img.*?>', '', content)
        #     content = content.replace('text-indent:10px;', '')
        #     content = re.sub(r'-qt-block-indent:(?P<val>\d+);', 'text-indent: \g<val>0px;', content)
        #     with open(G.rsc('ali_imran.html'), 'a', encoding='utf-8') as f:
        #         f.write(f'{content}\n')
        # pass

    def navigatorDialog(self):
        """
        A simple function which prepare the Navigator
        """
        self.navigator = Navigator(self)
        self.navigator.buildMap()
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
    def defaultDialogContext(title='',
                             path=S.GLOBAL.default_path,
                             filemode=QFileDialog.AnyFile,
                             acceptmode=QFileDialog.AcceptMode.AcceptSave) -> QFileDialog:
        """
        Returns a dialog with the default we use, file ext, file mode, etc..
        :param title: the dialog's title
        :param path: the dialog's default start path
        :param filemode: dialog's filemode, Any or Existing
        :param acceptmode: specify which buttons displayed
        :return: a QFileDialog widget
        """
        dialog = QFileDialog(None, title, path)

        # we define some defaults settings used by all our file dialogs
        dialog.setFileMode(filemode)
        dialog.setDefaultSuffix(G.__ext__)
        dialog.setNameFilter(f"Typer Files (*.{G.__ext__});;All files (*.*)")
        dialog.setAcceptMode(acceptmode)

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

    def applicationStateChanged(self, state) -> None:
        """
        Catch the app state changed
        :param state: app state either focusOut (state=2) or focusIn (state=4)
        """
        # if focusIn we force the external widgets to also be raised
        if state == 4 and S.LOCAL.viewer_external and S.LOCAL.viewer:
            self.viewer_frame.raise_()
            self.typer.setFocus()

    # INHERIT
    def showMaximized(self):
        # saving geometry state before maxizing
        self.bakeGeometry()
        super(TyperWIN, self).showMaximized()

        self.typer.graphAudioMap()

    def keyPressEvent(self, e: QKeyEvent):
        """
        Handle the key pressed in the main UI, forwards some to the document editor,
        and receive some from the document editor
        ! Some of these shortcut are handled by the MainComponents.Toolbar widget
        """
        super().keyPressEvent(e)

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

        elif e.key() == Qt.Key.Key_PageDown and S.LOCAL.BOOK:
            # if Shift modifier pressed, it will search for the closest filled page in book
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                keys = [i for i in S.LOCAL.BOOK if i > self.viewer.current_page]
                target = keys[0] if len(keys) else self.viewer.current_page
            else:
                target = min(self.viewer.current_page + 1, self.viewer.doc.page_count - 1)

            S.LOCAL.page = target

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

        self.updateStatus(20, 'Saving geometry...')
        self.bakeGeometry()
        S.LOCAL.saveVisualSettings()

        self.updateStatus(30, 'Saving geometry...')
        if S.LOCAL.viewer_external:
            self.viewer_frame.close()

        self.updateStatus(50, 'Saving geometry...')
        if S.LOCAL.PDF:
            try:
                self.viewer.doc.close()
            except ValueError:
                pass
            finally:
                os.unlink(S.LOCAL.PDF)

        self.updateStatus(80, 'Abording tasks...')
        S.POOL.clear()
        S.POOL.waitForDone()

        self.updateStatus(90, 'Releasing files...')
        for file in S.LIB.files.values():
            os.unlink(file)


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
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
    app.applicationStateChanged.connect(win.applicationStateChanged)

    app.exec_()
