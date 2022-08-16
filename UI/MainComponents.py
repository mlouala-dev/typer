# بسم الله الرحمان الرحيم
import time
from functools import partial
from math import floor

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from tools.styles import Styles
from tools import G


class SplashScreen(QWidget):
    """
    A Splash screen widget to display loading progress
    """
    def __init__(self, parent=None, title=''):
        super(SplashScreen, self).__init__(parent)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        bg = QLabel(self)
        bg.setPixmap(G.rsc("splash_screen.jpg"))
        bg.setGeometry(0, 0, 700, 384)

        self.title = QLabel(title, parent=self)
        self.title.setFont(G.get_font(1.9, italic=True))
        self.title.setGeometry(260, 30, 500, 30)
        self.title.setStyleSheet("color:#00B2FF;")

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setGeometry(0, 385, 700, 6)
        self.progress_bar.setStyleSheet("""QProgressBar:horizontal {
background: white;
}
QProgressBar::chunk:horizontal {
background: qlineargradient(x1: 0, y1: 0.5, x2: 1, y2: 0.5, stop: 0 #0054AA, stop: 1 #00B2FF);
}""")

        self.message = QLabel("Initializing...", parent=self)
        self.message.setFont(G.get_font(1.9))
        self.message.setGeometry(20, 340, 700, 30)
        self.message.setStyleSheet("color:black;")
        self.setFixedSize(700, 390)

    @G.debug
    def progress(self, v=0, msg=""):
        """
        Update slashscreen's progress
        :param v: progress value
        :param msg: additionnal message
        """
        self.message.setText(msg)
        self.progress_bar.setValue(int(v))

        # force window's update
        QApplication.processEvents()

        # give us the time to see what happend
        time.sleep(0.01)


class TitleBar(QFrame):
    """
    A wrapper to get a custom window's title bar
    """
    # style in format : (bar's height, stylesheet)

    default_style = (32, "QFrame#TitleBar { background:#363636;border-top:2px solid grey; }")
    maximized_style = (30, "QFrame#TitleBar { background:#363636; }")

    def __init__(self, parent: QMainWindow = None):
        self.win = parent
        super(TitleBar, self).__init__(parent)

        height, style = self.default_style
        self.setFixedHeight(height)
        self.setMouseTracking(True)
        self.setObjectName('TitleBar')
        self.setStyleSheet(style)

        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)

        ico = QLabel("")
        ico.setPixmap(G.pixmap('ico.png', size=28))
        ico.setFixedSize(28, 28)

        self.window_title = QLabel("Window's title")
        self.window_title.setFont(G.get_font(1.3))
        self.window_title.setStyleSheet("color:#2a82da;")
        self.window_title.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.window_title.setFixedHeight(30)

        self.min_button = QPushButton('\u268A')
        self.min_button.setStyleSheet("QPushButton:hover{background:#2a82da;}")
        self.max_button = QPushButton('\u271B')
        self.max_button.setStyleSheet("QPushButton:hover{background:orange;}")
        self.close_button = QPushButton('\u2715')
        self.close_button.setStyleSheet("QPushButton:hover{background:red;}")

        layout.addWidget(ico, 0)
        layout.addWidget(self.window_title, 1)
        for b in (self.min_button, self.max_button, self.close_button):
            b.setFixedWidth(50)
            layout.addWidget(b, 0)

        self.setLayout(layout)

        # SIGNALS
        self.max_button.clicked.connect(self.toggleMaximized)

        # USER DEFINED
        self.start = QPoint(0, 0)
        self.pressing = False

    def toggleMaximized(self):
        state = self.win.isMaximized()
        height, style = self.default_style if state else self.maximized_style

        if not state:
            self.win.showMaximized()
        else:
            self.win.showNormal()

        # making some visual ajustements
        self.setStyleSheet(style)
        self.setFixedHeight(height)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        self.toggleMaximized()

        super(TitleBar, self).mouseDoubleClickEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        """
        Forward mouse event and catch click
        """
        self.start = self.mapToGlobal(e.pos())
        self.pressing = True

    def mouseMoveEvent(self, e: QMouseEvent):
        """
        Move the window
        FIXME: replace the window under the cursor : offset
        """

        if self.pressing and not self.win.isMaximized():
            # getting position's offset
            end = self.mapToGlobal(e.pos())
            movement = end - self.start

            # moving the window
            self.win.setGeometry(
                self.mapToGlobal(movement).x(),
                self.mapToGlobal(movement).y(),
                self.win.width(),
                self.win.height()
            )

            self.start = end

    def mouseReleaseEvent(self, e: QMouseEvent):
        """
        if cursor hit the top of screen, maximize
        """
        # getting position relative to screen for multiscreen
        y = QApplication.desktop().cursor().pos().y()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        delta = y - QApplication.desktop().screenGeometry(screen).y()

        if delta == 0:
            self.toggleMaximized()

        # setting pressed state
        self.pressing = False

    def setTitle(self, title=""):
        """
        Reimplement setTitle
        """
        self.window_title.setText(title)


class Toolbar(QToolBar):
    """
    The window's toolbar
    """
    class Tool(QToolButton):
        """
        Basic Toolbutton with custom style
        """
        def __init__(self, icon: str, hint: str = '', shortcut='', action=None, defaultState=True, parent=None):
            super(Toolbar.Tool, self).__init__(parent)

            # some UI ajustments
            self.setFixedSize(30, 30)
            self.setAutoRaise(False)

            # if shortcut specified, we assign it and update the hint
            if shortcut != '':
                self.setShortcut(shortcut)
                hint += f' ({shortcut})'

            # settings from the tools dict
            self.setIcon(G.icon(icon))
            self.setToolTip(hint)
            self.setEnabled(defaultState)

            if action is not None:
                self.clicked.connect(action)

    class Separator:
        pass

    def __init__(self, parent=None):
        self._win = parent
        super(Toolbar, self).__init__(parent)

        # basic ui settings
        self.setContentsMargins(1, 1, 1, 1)
        self.setFixedHeight(40)

        # we'll store all buttons here for future access
        # here we stored the different buttons present in toolbar,
        # TODO: needs to change the way the tools are stored and toolbars defined

        # this is gonna to be filled when calling the insertButtons func in sha Allah
        self.buttons = {}

        left_buttons = {
            'new': Toolbar.Tool(
                icon="Page",
                hint="New project...",
                action=self._win.newProjectDialog,
                shortcut='Ctrl+N'
            ),
            'open': Toolbar.Tool(
                icon="Open-Folder",
                hint="Open project...",
                action=self._win.openProjectDialog,
                shortcut='Ctrl+O'
            ),
            'save': Toolbar.Tool(
                icon="Page-Save",
                hint="Save project...",
                action=self._win.saveProject,
                shortcut='Ctrl+S',
                defaultState=False
            ),
            'saveas': Toolbar.Tool(
                icon="Save-As",
                hint="Save as project...",
                action=self._win.saveAsProject,
                shortcut='Ctrl+Shift+S',
                defaultState=False
            ),
            'sep0': Toolbar.Separator,
            'ref': Toolbar.Tool(
                icon="Book-Link",
                hint="Load reference...",
                action=self._win.loadReferenceDialog,
                shortcut='Ctrl+R'
            ),
            'sep1': Toolbar.Separator,
            'search': Toolbar.Tool(
                icon="Search-Plus",
                hint="Search...",
                action=self._win.find_dialog.show,
                shortcut='Ctrl+F'
            ),
            'navigator': Toolbar.Tool(
                icon="List",
                hint="Open Navigator...",
                action=self._win.navigatorDialog,
                shortcut='Alt+E'
            ),
            'sep4': Toolbar.Separator,
            'audio': Toolbar.Tool(
                icon="Microphone",
                hint="Start Listening...",
                action=self._win.recordAudio,
                shortcut='Alt+A'
            ),
            'note': Toolbar.Tool(
                icon="Note-Add",
                hint="Insert Note...",
                action=self._win.typer.insertNote,
                shortcut='Alt+Z'
            ),
            'pdf': Toolbar.Tool(
                icon="File-Extension-Pdf",
                hint="Export Pdf...",
                action=self._win.exportDialog,
                shortcut='Alt+V'
            ),
            'sep3': Toolbar.Separator,
            'viewer': Toolbar.Tool(
                icon="Book-Picture",
                hint="Display viewer...",
                action=partial(self._win.toggleWidgetDisplay, self._win.viewer_frame),
                shortcut='Alt+R',
                defaultState=False
            ),
            'bookmark': Toolbar.Tool(
                icon="Application-Side-List",
                hint="Summary panel...",
                action=partial(self._win.toggleWidgetDisplay, self._win.summary_view),
                shortcut='F2'
            ),
            'sep2': Toolbar.Separator,
            'settings': Toolbar.Tool(
                icon="Setting-Tools",
                hint="Settings...",
                action=self._win.settings_dialog.show
            )
        }
        right_buttons = {
            'quran_search': Toolbar.Tool(
                icon="Book",
                hint="Search in Quran...",
                action=self._win.quran_search.show,
                shortcut='Alt+F'
            ),
            'quran_insert': Toolbar.Tool(
                icon="Book-Go",
                hint="Insert from / Jump to Quran...",
                action=self._win.QuranDialog,
                shortcut='Alt+C'
            ),
            'book_jumper': Toolbar.Tool(
                icon="Book-Spelling",
                hint="Insert from / Jump to Source Book...",
                action=self._win.jumper.show,
                shortcut='Alt+S'
            ),
            'hadith_search': Toolbar.Tool(
                icon="Book-Keeping",
                hint="Search in hadith database...",
                action=self._win.hadith_dialog.show,
                shortcut='Alt+H'
            )
        }

        self.insertButtons(left_buttons)

        # <3
        basmallah = QLabel('بسم الله الرحمان الرحيم')
        basmallah.setAlignment(Qt.AlignmentFlag.AlignCenter)
        basmallah.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        basmallah.setFont(G.get_font(1.2))

        self.addWidget(basmallah)

        self.insertButtons(right_buttons)

    def insertButtons(self, buttons: dict):
        """
        Insert the given list of buttons depending of the type
        :param buttons: a list of buttons
        """

        # looping through all left buttons
        for key, tool in buttons.items():
            if tool is Toolbar.Separator:
                self.addSeparator()
                self.addSeparator()

            else:
                self.addWidget(tool)
                self.buttons[key] = tool


class Summary(QTreeWidget):
    """
    Display a tree view of the main parts of the current page
    TODO : amélioré le visuel comme SublimeText ou PhpStorm ? Pas panneau latéral
    """
    clicked = pyqtSignal(int)

    def __init__(self, parent: QMainWindow = None):
        # UI
        super(Summary, self).__init__(parent)
        self.win = parent
        self.setMaximumWidth(400)
        self.setHeaderHidden(True)

        # SIGNALS
        self.itemClicked.connect(self.summaryClick)

        # USER DEFINED
        # page's resume
        self.summary = {}

    def findClosest(self, block: int) -> QTreeWidgetItem:
        """
        Return the closest block found in self.summary from the blockNumber
        :param block: block's number we are looking for
        :return: closest QTreeWidget's object
        :rtype: QTreeWidgetItem
        """
        previous = None

        # we look for the closest block
        if block in self.summary:
            previous = block
        else:
            for b in self.summary:
                if b > block:
                    break
                previous = b
        best_block = previous

        if previous is not None:
            # searching through item's children to find the closest one
            if len(self.summary[previous]['children']):
                for b in self.summary[previous]['children']:
                    if b > block:
                        break
                    best_block = b

            if best_block == previous:
                return self.summary[previous]['item']
            else:
                return self.summary[previous]['children'][best_block]['item']

    def updateSummaryHighLight(self):
        """
        Automatically select the current closest block selected in the document
        """
        # abort if hidden
        if self.isHidden():
            return

        n = self.win.currentCursor().block().blockNumber()

        # we search for the closest one
        item = self.findClosest(n)

        # then display it
        if item:
            # now we're sure we've found something, unselect the previous one
            self.clearSelection()

            # select the new one
            self.scrollToItem(item)
            item.setSelected(True)

    def summaryClick(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Call widget's signal
        :param item: Selected item
        :param column: Selected item's column
        """
        self.clicked.emit(item.data(0, Qt.UserRole))

    def build(self, document: QTextDocument):
        """
        Rebuild the treeView depending based on current document
        :param document: the current open text document
        """

        def emptyChild(b: QTextBlock) -> dict:
            """
            Returns a simple dictionnary for the given block
            """
            return {'text': b.text(), 'item': None, 'children': {}}

        # resetting everything to zero
        self.clear()
        self.summary.clear()
        self.summary = {0: {'text': "", 'children': {}}}
        last_header = 0
        last_title = 0

        # looping through document's blocks
        for i in range(document.blockCount()):
            block = document.findBlockByNumber(i)
            # if the block's style is a primary one (Alt+1 style)
            if block.userState() in (Styles.Header.id, Styles.Ayat.id):
                self.summary[i] = emptyChild(block)
                # for subchildren
                last_header = i

            # else if secondary (Alt+2 style)
            elif Styles.Title.id == block.userState():
                self.summary[last_header]['children'][i] = emptyChild(block)
                # for subchildren
                last_title = i

            # else if tertiary (Alt+3 style)
            elif Styles.Subtitle.id == block.userState():
                # if it doesn't have a secondary as parent, attach to the upper one
                try:
                    self.summary[last_header]['children'][last_title]['children'][i] = block.text()

                except KeyError:
                    self.summary[last_header]['children'][i] = emptyChild(block)

        font = G.get_font()

        def new(data: int | str, label: str = '', parent: QTreeWidgetItem = None) -> QTreeWidgetItem:
            """
            Create a new QTreeWidgetItem and attach it if a parent widget is provided
            """
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, data)
            item.setFont(0, font)

            # if a parent is provided, we parent to it, otherwise we parent to root
            if parent:
                parent.addChild(item)

            else:
                self.addTopLevelItem(item)

            return item

        # now we have our plan, lets make it as widgets

        for header in self.summary:
            # primary
            header_item = new(header, label=self.summary[header]['text'])
            self.summary[header]['item'] = header_item

            # secondary
            for children in self.summary[header]['children']:
                title_item = new(children, label=self.summary[header]['children'][children]['text'], parent=header_item)
                self.summary[header]['children'][children]['item'] = title_item

                # tertiary
                for subchildren in self.summary[header]['children'][children]['children']:
                    new(
                        subchildren,
                        label=self.summary[header]['children'][children]['children'][subchildren],
                        parent=title_item
                    )

        # now we've filled the treeview with basic elements, we add the notes

        notes = {}
        font.setBold(True)
        highlight = QTextCursor(document)

        while not highlight.isNull() and not highlight.atEnd():

            # we look to the warning character inserted before each note
            highlight = document.find('\u26A0', highlight)

            if not highlight.isNull():
                nb = highlight.blockNumber()
                if nb not in notes:
                    # when we get a note, we search the closest item in the treeview
                    notes[nb] = {
                        'closest': self.findClosest(highlight.blockNumber()),
                        'items': []
                    }

                    # until it's closed
                    txt = highlight.block().text().split('\u26A0')

                    # now we add all notes by pair of \u26A0 (before and after)
                    for i, p in enumerate(txt):
                        if i % 2:
                            notes[nb]['items'].append(p)

        # now we have all the notes we append to the treeview

        for nb in notes:
            for child in notes[nb]['items']:
                new(notes[nb]['closest'].data(0, Qt.UserRole), label='\u26A0 - %s' % child, parent=notes[nb]['closest'])

        # setting the view to expanded

        self.expandAll()


class StatusBar(QStatusBar):
    """
    The statusbar widget, display the app state, if recording's running, saving state, etc...
    """
    class VolumeBar(QProgressBar):
        """
        The volume bar for the audio recording
        """
        def __init__(self, parent: QWidget = None):
            super(StatusBar.VolumeBar, self).__init__(parent)
            p = QPalette()
            p.setColor(p.Highlight, QColor(0, 255, 0))
            self.setPalette(p)

    def __init__(self, parent: QWidget = None):
        super(StatusBar, self).__init__(parent)
        self.setFixedHeight(30)

        # UI stuffs
        self.page_label = QLabel(self)
        self.page_label.setText("")
        self.page_label.setVisible(False)

        self.connection_status_icon = QLabel(self)
        self.connection_status_icon.setPixmap(G.pixmap("Link", size=21))
        self.connection_status = QLabel("Connected to...")

        self.record_status = QLabel("Recording (00:00) ...", parent=self)
        self.record_status_icon = QLabel(self)
        self.record_status_icon.setPixmap(G.pixmap("Control-Play-Blue", size=21))

        self.record_volume = StatusBar.VolumeBar(self)
        self.record_volume.setOrientation(Qt.Vertical)
        self.record_volume.setFixedWidth(20)
        self.record_volume.setTextVisible(False)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignRight)
        self.label.setText("")

        self.connection_status_icon.hide()
        self.connection_status.hide()
        self.record_status.hide()
        self.record_status_icon.hide()
        self.record_volume.hide()

        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(300)

        self.not_saved_icon = QLabel(self)
        self.not_saved_icon.setPixmap(G.pixmap("Bullet-Red", size=21))
        self.not_saved_icon.hide()
        self.saving_icon = QLabel(self)
        self.saving_icon.setPixmap(G.pixmap("Bullet-Orange", size=21))
        self.saving_icon.hide()
        self.saved_icon = QLabel(self)
        self.saved_icon.setPixmap(G.pixmap("Bullet-Green", size=21))

        self.addPermanentWidget(self.page_label, 1)
        self.addPermanentWidget(self.connection_status_icon, 0)
        self.addPermanentWidget(self.connection_status, 0)
        self.addPermanentWidget(self.record_status_icon, 0)
        self.addPermanentWidget(self.record_volume, 0)
        self.addPermanentWidget(self.record_status, 0)
        self.addPermanentWidget(self.label, 1)
        self.addPermanentWidget(self.progress, 1)
        self.addPermanentWidget(self.not_saved_icon, 0)
        self.addPermanentWidget(self.saving_icon, 0)
        self.addPermanentWidget(self.saved_icon, 0)

    def updateStatus(self, val: int = 0, msg: str = '') -> None:
        """
        Update progress bar
        :param val: Progress value
        :type val: int | float
        :param msg: Additional Label
        """

        # surrounding the text label with spaces to make sure
        self.label.setText(f'  {msg}  ')
        self.progress.setValue(int(val))

        # Forcing ui's redraw
        self.repaint()
        QApplication.processEvents()

    def updateSavedState(self, state: int):
        """
        Display or hide a small red bullet to indicates if file is saved or no
        0: not saved
        1: saving
        2: saved
        :param state: the save status
        """
        save_status = [self.not_saved_icon, self.saving_icon, self.saved_icon]
        for i, status in enumerate(save_status):
            status.setVisible(state == i)

    def updateRecording(self, sec: int):
        """
        Calculate and display recording time
        :param sec: time in second to convert to <min:sec>
        """
        # FIXME: fail when calculating big values ??
        self.record_status.setText(f"Recording ({floor(sec / 60.0):02}:{sec % 59:02})...")

    def setRecordingState(self, state: bool):
        """
        Display or hide the audio recording widgets
        :param state: recording state
        """
        self.record_status_icon.setVisible(state)
        self.record_status.setVisible(state)
        self.record_volume.setVisible(state)

    @G.log
    def setConnection(self, file: str | bool = False):
        """
        Update the connection (PDF) status and display the widget if needed
        :param file: the PDF file name
        """
        if file:
            self.connection_status.setText(f'Connected to <i>{file}</i>')

        # making widgets visible if file is defined
        self.connection_status.setVisible(bool(file))
        self.connection_status_icon.setVisible(bool(file))

    @G.log
    def updatePage(self, page: int = 1):
        """
        Update the page number and display the widget if needed
        :param page: page number
        """
        # checking if label is visible
        try:
            assert self.page_label.isVisible()

        except AssertionError:
            self.page_label.setVisible(True)

        finally:
            # finally update the QLabel
            self.page_label.setText(f'Page {page}')
