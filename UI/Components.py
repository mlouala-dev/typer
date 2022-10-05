# بسم الله الرحمان الرحيم
import time
from functools import partial
from math import floor

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from tools.styles import Styles
from tools import G, S
from UI.Dialogs import TopicsDialog


class SplashScreen(QWidget):
    """
    A Splash screen widget to display loading progress
    """
    def __init__(self, parent=None, title=''):
        super(SplashScreen, self).__init__(parent)
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        bg = QLabel(self)
        bg.setPixmap(QPixmap("typer:splash_screen.jpg"))
        bg.setGeometry(0, 0, 700, 384)

        # a label displaying the current version / variant of the app
        # we force parent since we set the geometry manually
        self.title = QLabel(title, parent=self)
        self.title.setFont(G.get_font(2.4, italic=True))
        self.title.setGeometry(260, 30, 500, 30)
        self.title.setStyleSheet("color:#ccc;")

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

    default_style = (32, "QFrame#TitleBar { border-top:2px solid grey; }")
    maximized_style = (30, "QFrame#TitleBar { border:0; }")
    geometryChanged = pyqtSignal()

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
        ico.setPixmap(G.pixmap('ico', size=25))
        ico.setFixedSize(28, 28)

        self.window_title = QLabel("Window's title")
        self.window_title.setStyleSheet('color:#2a82da;')
        self.window_title.setFont(G.get_font(1.3))
        self.window_title.setObjectName('WindowTitle')
        self.window_title.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.window_title.setFixedHeight(30)

        self.min_button = QPushButton('\u268A')
        self.min_button.setStyleSheet("QPushButton{border:0;}QPushButton:hover{background:#2a82da;border:0;}")
        self.max_button = QPushButton('\u271B')
        self.max_button.setStyleSheet("QPushButton{border:0;}QPushButton:hover{background:orange;border:0;}")
        self.close_button = QPushButton('\u2715')
        self.close_button.setStyleSheet("QPushButton{border:0;}QPushButton:hover{background:red;border:0;}")

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

    def setMaximized(self, state=True):
        # loading a style tuple
        height, style = self.maximized_style if state else self.default_style

        if state:
            self.win.showMaximized()
        else:
            self.win.showNormal()

        # making some visual ajustements
        self.setFixedHeight(height)
        self.setStyleSheet(style)

    def toggleMaximized(self):
        state = not self.win.isMaximized()
        self.setMaximized(state)

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
        y = self.mapToGlobal(e.pos()).y()
        screen = QApplication.screenAt(self.mapToGlobal(e.pos()))
        delta = y - screen.geometry().y()

        if delta == 0:
            self.toggleMaximized()

        # setting pressed state
        self.pressing = False

        # emit signal to save the geometry settings
        self.geometryChanged.emit()

    def setTitle(self, title=""):
        """
        Reimplement setTitle
        """
        self.window_title.setText(title)


class Toolbar(QToolBar):
    def __init__(self, parent=None):
        self._win = parent
        super().__init__(parent)

        # basic ui settings
        self.setContentsMargins(1, 1, 1, 1)
        self.setFixedHeight(30)

        # we'll store all buttons here for future access
        # here we stored the different buttons present in toolbar,
        # TODO: needs to change the way the tools are stored and toolbars defined

        # this is gonna to be filled when calling the insertButtons func in sha Allah
        self.buttons = {}

    def insertButton(self, tool: QAction):
        """
        Insert the given list of buttons depending of the type
        :param buttons: a list of buttons
        """

        # looping through all left buttons
        b = QToolButton()

        b.setFixedSize(self.height() - 2, self.height() - 2)
        b.setAutoRaise(True)

        b.setIcon(tool.icon())
        b.setToolTip(tool.text())
        b.setEnabled(tool.isEnabled())

        b.clicked.connect(tool.trigger)

        self.addWidget(b)
        self.buttons[tool.objectName()] = b


class MainToolbar(Toolbar):
    """
    The window's toolbar
    """
    def __init__(self, *args):
        super().__init__(*args)

        self.insertButton(G.SHORTCUT['new'])
        self.insertButton(G.SHORTCUT['open'])
        self.insertButton(G.SHORTCUT['save'])
        self.insertButton(G.SHORTCUT['saveas'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['ref'])
        self.insertButton(G.SHORTCUT['digest'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['pdf'])
        self.insertButton(G.SHORTCUT['html'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['find'])
        self.insertButton(G.SHORTCUT['listen'])
        self.insertButton(G.SHORTCUT['note'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['navigator'])
        self.insertButton(G.SHORTCUT['viewer'])
        self.insertButton(G.SHORTCUT['bookmark'])
        self.insertButton(G.SHORTCUT['settings'])

        # <3
        basmallah = QLabel('بسم الله الرحمان الرحيم')
        basmallah.setAlignment(Qt.AlignmentFlag.AlignCenter)
        basmallah.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        basmallah.setFont(G.get_font())

        self.addWidget(basmallah)

        self.insertButton(G.SHORTCUT['quran_search'])
        self.insertButton(G.SHORTCUT['quran_insert'])
        self.insertButton(G.SHORTCUT['book_jumper'])
        self.insertButton(G.SHORTCUT['hadith_search'])


class TextToolbar(Toolbar):
    def __init__(self, *args):
        super().__init__(*args)

        self.setFixedHeight(20)
        self.insertButton(G.SHORTCUT['bold'])
        self.insertButton(G.SHORTCUT['italic'])
        self.insertButton(G.SHORTCUT['underline'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['h1'])
        self.insertButton(G.SHORTCUT['h2'])
        self.insertButton(G.SHORTCUT['h3'])
        self.insertButton(G.SHORTCUT['h4'])
        self.addSeparator()
        self.insertButton(G.SHORTCUT['aleft'])
        self.insertButton(G.SHORTCUT['acenter'])
        self.insertButton(G.SHORTCUT['aright'])
        self.insertButton(G.SHORTCUT['ajustify'])


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

        # abort if hidden
        if self.isHidden():
            return

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
            item.setData(0, Qt.ItemDataRole.UserRole, data)
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
                new(notes[nb]['closest'].data(0, Qt.ItemDataRole.UserRole), label='\u26A0 - %s' % child, parent=notes[nb]['closest'])

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
            p.setColor(p.ColorRole.Highlight, QColor(0, 255, 0))
            self.setPalette(p)

    def __init__(self, parent: QWidget = None):
        super(StatusBar, self).__init__(parent)
        self.setFixedHeight(30)
        self.setContentsMargins(10, 0, 0, 2)
        self.layout().setAlignment(Qt.AlignmentFlag.AlignTop)

        # UI stuffs
        self.page_label = QLabel(self)
        self.page_label.setText("")
        self.page_label.setVisible(False)

        self.connection_status_icon = QLabel(self)
        self.connection_status_icon.setPixmap(G.pixmap("Link", size=21))
        self.connection_status = QLabel("Connected to...")

        self.record_status = QLabel("Recording (00:00) ...", parent=self)

        self.record_volume = StatusBar.VolumeBar(self)
        self.record_volume.setOrientation(Qt.Orientation.Vertical)
        self.record_volume.setFixedWidth(20)
        self.record_volume.setTextVisible(False)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.label.setText("")

        self.connection_status_icon.hide()
        self.connection_status.hide()
        self.record_status.hide()
        self.record_volume.hide()

        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(300)

        self.processing_blink_state = True
        self.timer_id = 0
        self.processing_icon = QLabel(self)
        self.processing_icon.setPixmap(G.pixmap(f"icons:Apple-Half.png", size=19))
        self.processing_icon.setToolTipDuration(1000)
        self.processing_icon.hide()
        self.not_saved_icon = QLabel(self)
        self.not_saved_icon.setPixmap(G.pixmap("icons:Bullet-Red.png", size=21))
        self.not_saved_icon.hide()
        self.saving_icon = QLabel(self)
        self.saving_icon.setPixmap(G.pixmap("icons:Bullet-Orange.png", size=21))
        self.saving_icon.hide()
        self.saved_icon = QLabel(self)
        self.saved_icon.setPixmap(G.pixmap("icons:Bullet-Green.png", size=21))

        self.addPermanentWidget(self.processing_icon, 0)
        self.addPermanentWidget(self.page_label, 1)
        self.addPermanentWidget(self.connection_status_icon, 0)
        self.addPermanentWidget(self.connection_status, 0)
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

        self.label.setText(f'{msg}')
        self.progress.setValue(int(val))

        # Forcing ui's redraw
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
        self.record_status.setVisible(state)
        self.record_volume.setVisible(state)

    def timerEvent(self, a0: QTimerEvent) -> None:
        self.processing_blink_state = not self.processing_blink_state
        self.processing_icon.setPixmap(G.pixmap(f"icons:Apple{'' if self.processing_blink_state else '-Half'}.png", size=19))

    def loadingState(self, state: int):
        if state <= 0:
            self.processing_icon.hide()
            self.killTimer(self.timer_id)
            return

        elif self.processing_icon.isHidden():
            self.processing_icon.show()
            self.timer_id = self.startTimer(1000)

        joblist = "\n".join(S.POOL.jobs)
        self.processing_icon.setToolTip(f'Active threads ({S.POOL.activeThreadCount()}) :\n{joblist}')

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


class BreadCrumbs(QWidget):
    goto = pyqtSignal(int)

    class Level(QLabel):
        colors = ['267dff', '73c3ff', 'ffffff']
        hoverChanged = pyqtSignal(bool)
        clicked = pyqtSignal(QMouseEvent, int, int)

        def __init__(self, level=1, parent=None):
            self.level = level
            self.last = level == 3
            self.hover = False
            self.nextHover = False
            self.t = ''
            self.n = -1

            super().__init__('', parent)
            self.setContentsMargins(10, 3, 25, 1)
            self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.setMouseTracking(True)

        def mousePressEvent(self, e: QMouseEvent):
            if e.button() == 1:
                self.clicked.emit(e, self.level, self.n)

        def enterEvent(self, e):
            self.hover = True
            self.hoverChanged.emit(True)
            self.repaint()

        def leaveEvent(self, e):
            self.hover = False
            self.hoverChanged.emit(False)
            self.repaint()

        def formatText(self, text=''):
            num = f'{self.n}.&#x200e; ' if self.n != -1 else ''
            return f'{num}<b><span style="color:#{self.colors[self.level - 1]}">{text}</span></b>'

        def setText(self, p_str):
            self.t = p_str
            super().setText(self.formatText(self.t))

        def setNum(self, num):
            self.n = num
            super().setText(self.formatText(self.t))

        def nextStateChanged(self, state):
            self.nextHover = state
            self.repaint()

        def paintEvent(self, event):
            palette: QPalette
            palette = self.palette()
            default_bg = QBrush(palette.base())
            on_color = QBrush(palette.alternateBase())
            on_line = palette.alternateBase() if not self.hover else palette.highlight()
            button_color = on_color if self.hover else default_bg
            qp = QPainter(self)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.setPen(Qt.PenStyle.NoPen)
            qp.setBrush(button_color)
            if self.level == 1:
                qp.drawRoundedRect(QRect(0, 0, self.width() // 2 + 15, self.height()), 15, 15)
            else:
                qp.drawRect(QRect(0, 0, self.width() // 2, self.height()))

            if not self.last:
                qp.setBrush(default_bg if not self.nextHover else on_color)
                qp.drawRect(QRect(self.width() // 2, 0, self.width() // 2 + 5, self.height()))

            qp.setBrush(button_color)
            qp.drawPolygon(QPolygon([
                QPoint(self.width() // 2, -10),
                QPoint(self.width() // 2, self.height() + 10),
                QPoint(self.width() - 20, self.height() + 10),
                QPoint(self.width(), self.height() // 2),
                QPoint(self.width() - 20, -10)
            ]), Qt.FillRule.OddEvenFill)

            qp.setPen(QPen(on_line, 3))
            qp.drawLines([QLine(
                    QPoint(self.width() - 20, self.height() + 10),
                    QPoint(self.width(), self.height() // 2)
                ), QLine(
                    QPoint(self.width(), self.height() // 2),
                    QPoint(self.width() - 20, -10)
                )
            ])

            super().paintEvent(event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(G.get_font())
        self.setFixedHeight(40)
        self.setContentsMargins(0, 5, 0, 3)
        layout = QHBoxLayout()
        self.setMouseTracking(True)

        self.l1 = BreadCrumbs.Level(1)
        self.l1.clicked.connect(self.crumbPressed)
        self.l2 = BreadCrumbs.Level(2)
        self.l2.clicked.connect(self.crumbPressed)
        self.l3 = BreadCrumbs.Level(3)
        self.l2.hoverChanged.connect(self.l1.nextStateChanged)
        self.l3.hoverChanged.connect(self.l2.nextStateChanged)

        self.levels = [self.l1, self.l2, self.l3]

        layout.addWidget(self.l1, stretch=0)
        layout.addWidget(self.l2, stretch=0)
        layout.addWidget(self.l3, stretch=0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        self.setLayout(layout)

    def setLevel(self, level: int, text: str = '', num: int = -1):
        self.levels[level - 1].setHidden(text == '')
        self.levels[level - 1].setText(text)
        self.levels[level - 1].setNum(num)

    def crumbPressed(self, e: QMouseEvent, level: int, num: int = -1):
        global_pos = self.mapToGlobal(e.pos())
        menu = QMenu()

        def goto(page):
            S.LOCAL.page = page

        if level == 1:
            for kitab in S.LOCAL.BOOKMAP.kutub.values():
                action = QAction(f'{kitab.id}.\u200e{kitab.name} ({int(kitab.page)})', menu)
                if kitab.id == num:
                    action.setIcon(G.icon('Accept'))
                action.triggered.connect(partial(goto, int(kitab.page) + 1))
                menu.addAction(action)

        elif level == 2:
            kitab = S.LOCAL.BOOKMAP.getKitab(S.LOCAL.BOOKMAP.pages[S.LOCAL.page].kid)
            for bab in kitab.abwab:
                action = QAction(f'{bab.id}.\u200e{bab.name} ({int(bab.page)})', menu)
                if bab.id == num:
                    action.setIcon(G.icon('Accept'))
                action.triggered.connect(partial(goto, int(bab.page) + 1))
                menu.addAction(action)

        menu.exec(global_pos)

    @G.log
    def updatePage(self, page):
        if S.LOCAL.PDF:
            p = S.LOCAL.BOOKMAP.getPage(page)

            try:
                k = S.LOCAL.BOOKMAP.getKitab(p.kid)
                kitab = k.name
            except KeyError:
                kitab = ''

            except AttributeError:
                return

            try:
                b = S.LOCAL.BOOKMAP.getKitab(p.kid).getBab(p.bid)
                bab = b.name
            except KeyError:
                bab = ''

            if len(p.hids):
                h = S.LOCAL.BOOKMAP.getHadithByPage(page)[0]
                hadith = h.content
                hadith_num = h.sub_id
                if len(hadith) > 30:
                    hadith = f'{hadith[:30]} (...)'
            else:
                hadith = ''
                hadith_num = -1

            self.setLevel(1, kitab, p.kid)
            self.setLevel(2, bab, p.bid)
            self.setLevel(3, hadith, hadith_num)


class TopicsBar(QWidget):
    """
    The panel display the current topics for the given page
    """
    def __init__(self, parent=None):
        super(TopicsBar, self).__init__(parent)
        self.current_page = 0
        self.topic_dialog = TopicsDialog(parent, self)

        self.setMaximumWidth(600)
        self.setFixedHeight(50)
        self.setContentsMargins(0, 0, 0, 0)

        topic_layout = QHBoxLayout()
        self.topic_overview = QLabel("")
        self.topic_overview.setFont(G.get_font())

        self.topic_edit = QPushButton("...")
        self.topic_edit.setFixedWidth(45)
        self.topic_edit.clicked.connect(self.topic_dialog.showTopics)

        self.topics_settings = QPushButton(G.icon('Setting-Tools'), "")
        self.topics_settings.setFixedWidth(45)

        topic_layout.addWidget(self.topic_overview, 0)
        topic_layout.addWidget(self.topic_edit, 0)
        topic_layout.addWidget(self.topics_settings, 0)
        topic_layout.setStretch(1, 0)
        topic_layout.setContentsMargins(10, 0, 10, 0)
        topic_layout.setSpacing(0)

        self.setLayout(topic_layout)

    def changePage(self, page=0):
        # we update the panel's label with a list of all the topics
        try:
            self.topic_overview.setText(', '.join(map(str, sorted(S.LOCAL.TOPICS.pages[page]))))

        except KeyError as e:
            G.exception(e)
            self.topic_overview.setText('')

        # defining the current page
        self.current_page = page
