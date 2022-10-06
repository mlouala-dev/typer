# بسم الله الرحمان الرحيم
"""
Some very basic elements used by the UI
"""
from PyQt6.QtCore import *
from PyQt6.QtGui import QColor, QTextOption, QFont, QPainter, QKeyEvent, QFontMetrics, QMouseEvent
from PyQt6.QtWidgets import *


def get_item_color(row: int, state) -> QColor:
    """
    for alternate row color
    :param row: row's id
    :param state: the state of the QStyleOptionViewItem called when painting the itemDelegate
    :return: the background color
    """
    # alternate row coloring
    # TODO: store these settings in G
    bg = QColor(45, 45, 45) if row % 2 else QColor(32, 32, 32)

    # if mouse over
    if state & QStyle.StateFlag.State_MouseOver:
        bg = QColor(42, 130, 218)

    # if item selected
    elif state & QStyle.StateFlag.State_Selected:
        bg = QColor(42, 81, 128)

    return bg


class AyatModelItem(QStyledItemDelegate):
    """
    Custom itemDelegate for proper arabic text display and multiline
    """
    color = QColor(115, 195, 255)

    to = QTextOption()
    to.setTextDirection(Qt.LayoutDirection.RightToLeft)
    to.setWrapMode(to.WrapMode.WordWrap)

    def __init__(self, parent=None, font=QFont()):
        super().__init__(parent)
        self.font = font

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # getting the row alternate background color
        bg = get_item_color(index.row(), option.state)

        # drawing with QPainter
        painter.fillRect(option.rect, bg)
        painter.setFont(self.font)

        painter.setPen(self.color)
        newrect = QRectF(option.rect)
        newrect.setY(newrect.y() + self.font.pointSize() - 10)
        newrect.translate(10, 0)
        newrect.setWidth(newrect.width() - 20)

        painter.drawText(newrect, index.data(), option=self.to)

        # apply QPainter
        painter.save()


class MultiLineModelItem(AyatModelItem):
    """
    Same as before, for latin text
    """
    color = Qt.GlobalColor.white

    to = QTextOption()
    to.setTextDirection(Qt.LayoutDirection.LeftToRight)
    to.setWrapMode(to.WrapMode.WordWrap)


class HighlightModelItem(QStyledItemDelegate):
    color = Qt.GlobalColor.white
    highlight_color = QColor(115, 195, 255)

    def __init__(self, parent=None, font=QFont(), highlight=''):
        super().__init__(parent)
        self.font = font
        self.highlight = highlight

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # getting the row alternate background color
        bg = get_item_color(index.row(), option.state)

        # drawing with QPainter
        painter.fillRect(option.rect, bg)
        painter.setFont(self.font)

        painter.setPen(self.color)
        newrect = QRectF(option.rect)
        newrect.setY(newrect.y() + self.font.pointSize() - 10)
        newrect.setX(10)
        newrect.setWidth(newrect.width() - 20)

        text = index.data()
        try:
            start, end = index.data().split(self.highlight)
            highlight = self.highlight

            painter.setPen(self.color)
            painter.drawText(newrect, start)

            painter.setPen(self.highlight_color)
            fm = QFontMetrics(painter.font())
            newrect.setX(newrect.x() + fm.horizontalAdvance(f'{start}'))
            painter.drawText(newrect, highlight)

            painter.setPen(self.color)
            newrect.setX(newrect.x() + fm.horizontalAdvance(f'{highlight}'))
            painter.drawText(newrect, end)

        except ValueError:
            painter.setPen(self.color)
            painter.drawText(newrect, text)

        # apply QPainter
        painter.save()


class NumberModelItem(QStyledItemDelegate):
    """
    Nice arabic number display
    """
    font = QFont('Calibri')
    font.setPixelSize(23)
    to = QTextOption()
    to.setTextDirection(Qt.LayoutDirection.RightToLeft)
    to.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignHCenter)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # getting the row alternate background color
        bg = get_item_color(index.row(), option.state)

        # drawing QPainter
        painter.fillRect(option.rect, bg)
        painter.setFont(self.font)
        painter.drawText(QRectF(option.rect), index.data(), option=self.to)

        # apply QPainter
        painter.save()


class LineLayout(QHBoxLayout):
    """
    This simple layout will automatically returns a QHBoxLayout filled with the given widgets
    can also be str so it'll make a QLabel or apply to the next QCheckBox
    """
    def __init__(self, parent, *widgets):
        super(LineLayout, self).__init__(parent)

        self.widgets = []
        self.setContentsMargins(3, 1, 3, 1)

        # looping through the given widgets' list
        for i, widget in enumerate(widgets):

            # if a str is provided
            if isinstance(widget, str):
                # ignore this case because we'll use the widget in the next one since its a CheckBox
                if i < len(widgets) and isinstance(widgets[i + 1], QCheckBox):
                    continue

                # otherwise create a QLabel
                else:
                    widget = QLabel(widget, parent)

            # get the previous str and set it as text in the QCheckbox
            elif isinstance(widget, QCheckBox) and i > 0 and isinstance(widgets[i - 1], str):
                widget.setText(widgets[i - 1])

            # final append to internal list
            self.widgets.append(widget)

            # append to QLayout
            self.addWidget(widget)


class ListWidget(QTreeWidget):
    """
    This custom QTreeWidget uses a given list of QItemDelegateModel for each col
    """
    def __init__(self, parent, models=()):
        super(ListWidget, self).__init__(parent)

        # visual settings
        self.setIndentation(0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # we need that for the MouseOver option used by some models
        self.setMouseTracking(True)

        self.applyModels(models)

    def applyModels(self, models=()):
        # adding each model in the list, for each columns
        for i, model in enumerate(models):
            model.setParent(self)
            self.setItemDelegateForColumn(i, model)


class SearchField(QLineEdit):
    """
    A simple line edit to trigger the keypress event
    """
    keyPressed = pyqtSignal(QKeyEvent)

    def __init__(self, parent=None):
        super(SearchField, self).__init__(parent)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        super(SearchField, self).keyPressEvent(e)
        self.keyPressed.emit(e)


class RadioGroupBox(QGroupBox):
    """
    Will create radioButtons for every str in the list to the GroupBox
    and allows a 'selection' call to get the current active one
    """
    def __init__(self, direction: QLayout, title='', widgets: list = None):
        """
        direction determined by user so he can choose bewteen hor or vert
        :param direction: the QLayout param
        :param title:
        :param widgets:
        """
        super(RadioGroupBox, self).__init__()
        self.items = []
        self.setTitle(title)

        # adding every string as QRadioButton
        for i, widget in enumerate(widgets):
            radiobox = QRadioButton(widget)

            # check the first one
            # TODO: default selected param by name or id
            if i == 0:
                radiobox.setChecked(True)

            self.items.append(radiobox)
            direction.addWidget(radiobox)

        self.setLayout(direction)

    def selection(self) -> QRadioButton:
        """
        :return: currently selected QRadioButton
        """
        for i in self.items:
            if i.isChecked():
                return i

    def selectionIndex(self) -> int:
        """
        :return: index of the currently selected QRadioButton
        """
        return self.items.index(self.selection())
