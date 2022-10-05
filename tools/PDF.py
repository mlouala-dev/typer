# بسم الله الرحمان الرحيم
"""
Library for all PDF work, previz and export
TODO: migrate to https://pypi.org/project/fpdf2/
"""
import os
import time

import fitz
import re
import tempfile

from PyQt6 import QtPrintSupport
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from tools import G, S


class Viewer(QWidget):
    """
    A PDF viewer which get a pixmap from fitz (PDF operation) library
    """
    doc: fitz.Document
    win: QMainWindow
    pageChanged = pyqtSignal(int)
    documentLoaded = pyqtSignal()
    doc = None
    toc = []

    def __init__(self, parent: QMainWindow = None, **kwargs):
        super(Viewer, self).__init__(parent)
        self.win = parent
        self.current_page = 0
        self.ratio = 1
        self.pixmap = QPixmap()

        layout = QVBoxLayout(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.view = QLabel(self)
        self.view.setContentsMargins(0, 0, 0, 0)
        self.view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        layout.addWidget(self.view, stretch=1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setLayout(layout)

        # if filename is provided we load it - for debug
        if 'filename' in kwargs:
            self.load_doc(kwargs['filename'])

    def mousePressEvent(self, e: QMouseEvent):
        """
        Overrides mousePressEvent to catch the middle and right click
        """
        if e.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            menu = QMenu()
            actions = {}

            # we loop through the table of content of the pdf file
            for lvl, title, page in self.toc:
                actions[menu.addAction(title)] = page

            # and display it as a menu for fast jump
            action = menu.exec(self.mapToGlobal(e.pos()))

            # if menu is clicked, we display the corresponding page
            if action in actions:
                self.current_page = actions[action] - 1
                self.load_page(actions[action] - 1)

    def wheelEvent(self, e: QWheelEvent):
        """
        Overrides wheelEvent to switch between PDF's page
        """
        # prevent event forwarding
        e.ignore()

        # determine if we scroll up or down
        if e.angleDelta().y() > 0:

            # we clamp value to make sure we don't go out of range
            self.current_page = max(self.current_page - 1, 0)

        # scroll up
        else:
            self.current_page = min(self.current_page + 1, self.doc.page_count - 1)

        S.LOCAL.page = self.current_page

        # displaying the new page
        self.load_page()

        # emitting status
        self.pageChanged.emit(self.current_page)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        """
        Overrides mouseDoubleClickEvent
        """
        if e.button() == Qt.MouseButton.LeftButton:
            self.win.goTo()

    @G.log
    def load_doc(self):
        """
        Loading the given PDF document
        :param fn: the PDF's filename
        """
        self.doc = fitz.Document(S.LOCAL.PDF)
        self.ratio = self.doc.page_cropbox(0).width / self.doc.page_cropbox(0).height

        # extract the table of content
        self.toc = self.doc.get_toc()

        # emitting signal
        self.documentLoaded.emit()

    @G.log
    def load_page(self, *args):
        """
        Load the given page of the loaded PDF
        :param page_num: the page number
        """
        # abort if there is no document loaded

        if not self.doc:
            return

        page_num = max(min(S.LOCAL.page, self.doc.page_count - 1), 0)
        self.current_page = page_num

        # redraw pixmap
        self.redrawPixmap(page_num)

    def redrawPixmap(self, page: int):
        """
        Redraw the pixmpa for the current_page
        :param page: the page number
        """

        # we abort if the PDF document isn't set yet
        if not self.doc:
            return

        self.makePixmap(page)

        # scaling the pixmap correctly
        pixmap = self.pixmap.scaledToWidth(self.width() * 3, Qt.TransformationMode.SmoothTransformation)

        # setting it as a QLabel's Pixmap
        self.view.setPixmap(pixmap)
        self.view.setScaledContents(True)

    def makePixmap(self, page_num: int, for_printing=False) -> QPixmap:
        """
        Create a pixmap with the given print settings
        :param page_num: the pdf's page number
        :param for_printing: if we need a high resolution pixmap of the pdf's page
        :return: the page's pixmap
        """
        # we store the page's data in a var and get its width and height
        page_data = self.doc.load_page(page_num)

        # upscaling ratio for highres (300 dpi)
        ratio = 10 if for_printing else 1

        # get the pixmap from a 1:1 ratio with no alpha
        page = page_data.get_pixmap(matrix=fitz.Matrix(ratio, ratio), dpi=300, alpha=False)

        # for invertPixel
        image_format = QImage.Format.Format_RGB888

        # now we have our data we store it inside a QImage to convert as a QPixmap
        image_data = QImage(
            page.samples,
            page.width,
            page.height,
            page.stride,
            image_format
        )

        if S.LOCAL.viewer_invert:
            image_data.invertPixels()

        self.pixmap = QPixmap()
        self.pixmap.convertFromImage(image_data)

        return self.pixmap

    def resizeEvent(self, e: QResizeEvent):
        """
        Reload the page if ever the viewer is scaled
        """
        super(Viewer, self).resizeEvent(e)

        self.redrawPixmap(self.current_page)


class ViewerFrame(QWidget):
    def __init__(self, viewer: Viewer, topics_display: QWidget):
        super(ViewerFrame, self).__init__()
        self.viewer = viewer
        self.viewer.documentLoaded.connect(self.forceResize)
        self.setWindowIcon(G.icon('Book-Picture'))

        viewer_frame_layout = QVBoxLayout(self)
        viewer_frame_layout.addWidget(viewer, stretch=1)
        self.setLayout(viewer_frame_layout)

        viewer_frame_layout.setContentsMargins(0, 0, 0, 0)
        viewer_frame_layout.setSpacing(0)
        viewer_frame_layout.addWidget(topics_display, stretch=1)
        viewer_frame_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def forceResize(self):
        w, h = self.width(), int(self.width() / self.viewer.ratio)
        self.resize(QSize(w, h))

    def resizeEvent(self, e: QResizeEvent):
        w = e.size().width()
        h = int(w / self.viewer.ratio)
        e.ignore()
        self.resize(QSize(w, h))


class PDF_Exporter(QThread):
    """
    This QThread do all the PDF export magic
    TODO: this should be multithreaded and ran as a task but it crashes
    """
    empty_line_pattern = re.compile(r'^<p.*?type:empty.*?<\/p>(<\/body><\/html>)?', re.MULTILINE)

    # all theses patterns are used to format a nice looking TOC (Table Of Content)
    # and / or catch elements in text
    new_surat_no_css = "font-size:16pt; color:#999; font-weight:600;"
    old_surat_no_css = "font-size:15pt; color:#ccc; font-weight:200;"
    ayat_no_css = f"font-size:11pt; color:#9622d3; font-weight:600;"
    line_space = f"font-family:'{G.__font__}';line-height:70%;"
    surat_cell_css = f"{line_space}"
    ayat_cell_css = f"""{line_space}; padding-right:10px; padding-left:10px; border-right-style:solid;
    border-right-width:2px; border-right-color:#9622d3;"""
    title_cell_padding = "text-align:left; padding-left:20px; padding-right:10px; "
    title_cell_css = {
        1: f"{title_cell_padding}font-size:14pt; font-weight:600; {line_space}",
        2: f"{title_cell_padding}font-size:13pt; {line_space}",
        3: f"{title_cell_padding}font-size:13pt; {line_space}",
        "S": f"text-align:left; padding:10px; font-size:15pt; font-weight:600; {line_space}"
    }
    linked_title_cell_css = f"border-top:1px solid #ddd;"
    linked_page_cell_css = f"border-top:1px solid #eee;"
    page_cell_css = f"{line_space};text-align:right;"
    multipage_cell_css = f"{line_space};font-size:12pt; text-align:right;"
    page_no_css = "font-size:14pt; font-weight:600;"

    # the signals for output
    finished = pyqtSignal()
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)

    # the thread's state
    running = False

    def __init__(self):
        """
        Original code has been took from internet then tweaked
        TODO: some vars are declared outside __init__, no PEP, french var names
        """
        super(PDF_Exporter, self).__init__()

        self.margeGT = 5  # marge totale gauche en mm
        self.margeHT = 10  # marge totale haute en mm
        self.margeDT = 7  # marge totale droite en mm
        self.margeBT = 10  # marge totale basse en mm

        self.police = G.__font__  # police de caractères pour l'impression
        self.taille = 21  # taille de la police pour l'impression
        self.font = QFont(self.police, self.taille)

        self.painter = QPainter()
        self.painter.setPen(QPen(Qt.GlobalColor.black))
        # self.res = QtPrintSupport.QPrinter.ScreenResolution
        self.currentRect = QRectF(QRect(QPoint(0, 0), QSize(0, 0)))

        self.page = 0
        self.abs_page = 0
        self.title = ''

        self.progress_total = 0

        self.settings = {}
        self.topics = {}
        self.processed_pages = {}
        self.toc = ''
        self.book_map = list()

    @staticmethod
    def eval_doc(book: str) -> bool:
        """
        This function checks if the given HTML code returns some plain text or no,
        for instance <html><head></head><body><p></p></body></html> returns nothing
        :param book: the HTML code of the book
        """
        # we create a temporary QTextDocument to export it as plainText
        temp_doc = QTextDocument()
        temp_doc.setHtml(book)

        # return true if body isn't empty
        return len(temp_doc.toPlainText()) > 1

    @staticmethod
    def clean_doc(book: str) -> str:
        """
        Removing all tailing empty lines at the end of pages
        :param book: the HTML code of the book
        :return: the page without tail empty lines
        """
        # splitting the book by lines
        splitted_book = book.split('\n')
        bound = len(splitted_book) - 1

        # looping until we've removed all empty lines
        while PDF_Exporter.empty_line_pattern.match(splitted_book[bound]):
            bound -= 1

        # returning the new HTML page
        return '\n'.join(splitted_book[:bound + 1])

    @staticmethod
    def reg_px2mm(px_reg):
        """
        Converts a pixel match group to mm
        :param px_reg: pixel values matched by the regex pattern
        """
        if px_reg.group() is not None:
            return PDF_Exporter.px2mm(px_reg.groups()[0])

    @staticmethod
    def px2mm(px):
        """
        Converts a pixel value to mm
        :param px: pixel values matched by the regex pattern
        """
        return f':{int(int(px) * 7.5)}px'

    @staticmethod
    def rescale_pt(text: str, factor: int = 1) -> str:
        """
        Rescaling the point size font's values to the given factor
        :param text: the text we'll look for the point size values
        :param factor: the scale factor we want to apply
        :return: the text with all pointsize mentions rescaled
        """
        def rescale(pt):
            """
            Rescale by factor
            :param pt: point size regex group
            :return: the scaled point size
            """
            if pt.group() is not None:
                return f':{int(int(pt.groups()[0]) * factor)}pt;'

        return re.sub(r':(\d+)pt;', rescale, text)

    def mm2px(self, mm):
        """
        Converts the mm value to a pixel value, depending on resolution
        :param mm: the value in millimeter
        :return: the value in pixel
        """
        return int(mm / 25.4 * self.res)

    def replace_reference(self, m) -> str:
        """
        Works with the bookmap
        replace all found mentions in form #_REF_2_24_# by the correct page reference
        based of the snapshot we made
        :param m: the regex groups found
        :return: the formatted reference as HTML
        """
        if m.group() is not None:
            # extracting the surat no and verse no
            s, v = int(m.groups()[0]), int(m.groups()[1])

            # preparing our regex pattern
            m = re.compile(f"(^{v}$|^{v}-.*?$|^.*?-{v})")
            
            # looking for every element of the bookmap which is an ayat
            for a in [x for x in self.book_map if x['type'] == 'ayat']:

                # if it matches our search
                if a['surat_no'] == s and m.match(a['verse_no']):

                    # emitting signal for dialog's output
                    self.log.emit(f"reference {s}:{v} found")

                    # returning the formatted reference of the Surat:Verse
                    return f"<i>cf S{a['surat_no']}:V{a['verse_no']} page {a['page']}</i>"

            # otherwise, we return a formatted string in form (cf 2:4)
            self.log.emit(f"reference {s}:{v} not found")
            return f"(<i>cf S{s}:V{v}</i>)"

    def get_surat_by_page(self, page: int, first=False) -> list | str:
        """
        Works with the bookmap
        Returns all the surats present at given page
        :param page: the page number
        :param first: return the whole matchs (false) or only the first one (true)
        """
        # filtering the bookmap
        res = [y for y in [x for x in self.book_map if x['type'] == 'surat'] if y['page'] == page]

        # if first is set, getting the first one
        if first:
            return res[0] if len(res) else None

        return res

    def run(self):
        """
        FIXME: should start an multiprocessed thread of the export, but crashes
        """
        self.running = True
        self.multi_page_export(self.settings['viewer'])

    def single_page_export(self, doc: QTextDocument):
        """
        It does the magic for a single page document (not connected to PDF's pages)
        :param doc: the document we'll export
        """
        self.log.emit('Single Page Export...')
        # FIXME: this need to be updated based on the multi page export function
        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        printer.setPaperSize(self.formatpapier)
        printer.setOrientation(self.orientation)
        printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
        printer.setOutputFileName(self.settings['path'])

        font = QFont()
        font.setFamily(self.police)
        font.setPointSize(self.taille)
        paintFont = QFont(font, printer)
        doc.setDefaultFont(paintFont)

        margeG = self.mm2px(self.margeGT)
        margeH = self.mm2px(self.margeHT)
        margeD = self.mm2px(self.margeDT)
        margeB = self.mm2px(self.margeBT) + self.mm2px(10)

        printer.setPageMargins(margeG, margeH, margeD, margeB, QtPrintSupport.QPrinter.DevicePixel)

        self.rect = printer.pageRect()
        doc.setPageSize(QSizeF(QSize(self.rect.size().width(), self.rect.size().height())))

        self.rect_t = QRect(0, 0, self.rect.size().width(), self.rect.size().height())
        self.rect_b = QRect(0, self.rect.size().height() + 2, self.rect.size().width(), self.mm2px(20))

        self.contentRect = QRectF(QRect(QPoint(0, 0), doc.size().toSize()))
        self.currentRect = QRectF(QRect(QPoint(0, 0), self.rect.size()))

        self.painter = QPainter(printer)
        self.painter.save()

        for numpage in range(1, doc.pageCount() + 1):
            doc.drawContents(self.painter, QRectF(self.currentRect))
            self.currentRect.translate(0, self.currentRect.height())
            self.painter.restore()

            texte = f"Page {numpage}"
            self.painter.drawText(self.rect_b, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, texte)

            self.painter.save()

            self.painter.translate(0, -self.currentRect.height() * numpage)

            if self.currentRect.intersects(self.contentRect):
                printer.newPage()

        self.painter.restore()

        self.painter.end()

    def multi_page_export(self, pdf_viewer: Viewer):
        """
        The PDF export magic for a multipage document (which means connected to PDF's pages)
        :param book: the book dictionary
        :param pdf_viewer: a PDF viewer instance to create the Pixmaps
        :param topics: a dict of the topics, by page
        :return:
        """
        self.progress.emit(0, 'Starting PDF build..')
        self.log.emit('Multi Page Export...')

        # the first thing we do is to create a snapshot (=fast export without image) of our PDF
        # by this way we'll get the pages to create references,
        # generate TOC (Table of Content) and TOT (Table of Topics)
        self.pdf_snapshot()

        self.progress.emit(100, 'Building table of content...')

        # now we have our bookmap, we format it for a good looking export
        self.format_toc(self.book_map)

        # getting the printer PDF settings (low or highres)
        printer = self.build_pdf_context()

        # we get a version of the book without empty pages
        clean_book = [a for a in sorted(S.LOCAL.BOOK.pages()) if PDF_Exporter.eval_doc(S.LOCAL.BOOK[a].content)]
        perc = 100.0 / len(clean_book)

        # looping through every page of the book
        for page_pdf in clean_book:
            self.page = page_pdf - 1

            # abort if page isn't in specified export range
            if page_pdf not in range(*self.settings['range']):
                continue

            # if the page had topics, we add them to generate the TOT
            if page_pdf in S.LOCAL.TOPICS.pages:
                for topic in S.LOCAL.TOPICS.pages[page_pdf]:

                    # storing the page as tuple to avoid duplicates
                    if topic in self.topics:
                        self.topics[topic].add(self.abs_page)
                    else:
                        self.topics[topic] = {self.abs_page}

            # continue by drawing the page
            self.currentRect = QRectF(QRect(QPoint(0, 0), self.rect.size()))

            self.paint_quran(printer)
            self.paint_body_text(*self.processed_pages[page_pdf], printer)

            # signal emission for dialog's visual output
            self.progress_total += perc
            self.progress.emit(self.progress_total, f'PDF Export - {self.abs_page} pages done')

        printer.newPage()

        # adding the TOC and TOT at the end of the PDF
        self.paint_toc(printer)
        self.paint_tot(printer, self.format_tot())

        # finalizing stuff
        self.painter.end()
        self.progress.emit(100, 'PDF Exported ! %d pages' % self.abs_page)
        self.abs_page = 0
        self.processed_pages.clear()

        # for debug
        self.log.emit(repr(self.topics))

    def pdf_snapshot(self):
        """
        It creates a PDF snapshot (=fast export) of the given book in a temporary file in
        order to get a book's map, when the PDF is generated, we open it again and read it
        as a simple "text file" to get all the info we want
        :param book: the book's dict
        """
        # create the temporary PDF file
        fp = tempfile.mktemp()
        printer = self.build_pdf_context(fp)

        # same cleaning process as in the multi_page_export function
        clean_book = [a for a in sorted(S.LOCAL.BOOK.pages()) if PDF_Exporter.eval_doc(S.LOCAL.BOOK[a].content)]
        perc = 100.0 / len(clean_book)

        for page_pdf in clean_book:
            self.page = page_pdf - 1
            self.title = ''

            # abort if page isn't in range
            if page_pdf not in range(*self.settings['range']):
                continue

            # we store the processed page for future export of the final version, before making some
            # changes in the core text
            self.currentRect = QRectF(QRect(QPoint(0, 0), self.rect.size()))
            head, body = self.post_treatment(S.LOCAL.BOOK[page_pdf].content)
            self.processed_pages[page_pdf] = (head, body)

            # these regexs could be used to catch all ayats, but not used atm
            #
            # name_mapping = {'surat_sep_0_LD': "#x# ",
            #                 'ayat_separator_LD': '#d#'}
            #
            # body = re.sub(r'(<img src=".*?)(surat_sep_0_LD|ayat_separator_LD).png" />',
            #               lambda x: name_mapping[x.groups()[1]] + x.groups()[0] + x.groups()[1] + '.png" />',
            #               body)

            # replacing the arabic digits by normal ones
            body = re.sub(r'([٠١٢٣٤٥٦٧٨٩])', lambda x: str(list("٠١٢٣٤٥٦٧٨٩").index(x.group())), body)

            # matching the ayat elements
            body = re.sub(r'(?P<start><p.*?>)\(.*?(?P<add>\d.*\d).*?\)</span></p>',
                          r'\g<start>#A#\g<add></span></p>', body)

            # matching the title, subtitle and surat paragraphs
            f = self.settings['factor']
            body = re.sub(f'(font-size{self.rescale_pt(":17pt;", f)} font-weight:600;">)(.*?)</span>', r'\1#2#\2</span>', body)
            body = re.sub(f'(font-size{self.rescale_pt(":19pt;", f)} font-weight:600; font-style:italic;">)(.*?)</span>', r'\1#1#\2</span>', body)
            body = re.sub(f'(font-size{self.rescale_pt(":30pt;", f)} font-weight:600; color:#267dff;">)(.*?) \((\d+)\)</span>', r'\1#S#\2#\3</span>', body)

            # we draw the reformatted PDF to the temporary file
            self.paint_body_text(head, body, printer)
            self.progress_total += perc

            # emitting progress for visual
            self.progress.emit(self.progress_total, f'Creating snapshot ({int(self.progress_total)}%)')

        # now we're done with the PDF snapshot
        self.painter.restore()
        self.painter.end()
        self.progress.emit(100, 'Snapshot created')
        self.abs_page = 0

        # we can now open the PDF as "plain text"

        with fitz.open(fp) as doc:
            txt_doc = []

            # and get all the pages as text
            for page in doc:
                txt_doc.append(page.get_text())

        # deleting the pdf temporary file
        os.unlink(fp)

        surat, s, v = '', 0, 0
        is_sub = False

        # for each page of the snapshort
        for page_no, page in enumerate(txt_doc):
            for line in page.split('\n'):

                # for each line, if it matches the pattern we set before (inserting # at the beginning and end)
                if line.lstrip().startswith('#') or line.rstrip().endswith('#'):

                    # this format means we found an ayat
                    if re.match(r'.*?\d ?:\d.*?', line):
                        is_sub = False
                        # some preformatting
                        sno, v = line.replace('#', '').replace('A', '').replace(' ', '').split(':')
                        try:
                            s = int(sno)
                        except ValueError:
                            s = re.findall(r'\d+', sno)[0]

                        # storing data in the bookmap
                        self.book_map.append({
                            'type': 'ayat',
                            'surat_no': s,
                            'verse_no': v,
                            'page': page_no + 1
                        })

                    # this means we found a title or subtitle (Alt+1 or Alt+2)
                    elif line.startswith('#1') or line.startswith('#2'):
                        # some preformatting
                        rank, title = line.lstrip('#').split('#', 1)

                        # storing data in the bookmap,
                        # we remove these kind of buggy character � arabic not handled by fitz
                        self.book_map.append({
                            'type': 'title',
                            'title': re.sub(r' ?: ?$', '', title).replace('�', 'ّ').replace('#2#', '').replace('#1#', ''),
                            'surat': s,
                            'verse': v,
                            'sub': int(is_sub),
                            'rank': int(rank),
                            'page': page_no + 1
                        })

                        # if this is a subtitle we mark it as so
                        if line.startswith('#1'):
                            is_sub = True

                    # this means we found a surat
                    elif line.startswith('#S#'):
                        is_sub = False

                        # some preformatting
                        surat, sno = line.replace('#S#', '').split('#')
                        s = int(sno)
                        v = 0

                        # storing data in the bookmap
                        self.book_map.append({
                            'type': 'surat',
                            'name': surat,
                            'surat_no': s,
                            'page': page_no + 1
                        })

                    else:
                        # for debug purposes
                        self.log.emit(line)

    def format_toc(self, book_map: list):
        """
        Works with the bookmap
        This function generates the Table of Content, based on the bookmap generated by pdf_snapshot function
        :param book_map: the bookmap dict
        """
        toc = ''

        toc += '<table align="center" width="90%" cellspacing="0" cellpadding="0">\n'
        toc += '<tr>' \
               f'<td width="2%" style="{PDF_Exporter.surat_cell_css}" valign="middle">' \
               f'<span style="{PDF_Exporter.new_surat_no_css}"></span>' \
               '</td>' \
               f'<td colspan="2" style="{PDF_Exporter.linked_title_cell_css}{PDF_Exporter.title_cell_css["S"]}">Introduction</td>' \
               f'<td style="{PDF_Exporter.page_cell_css}" width="2%">' \
               f'<span style="{PDF_Exporter.page_no_css}"></span>' \
               '</td></tr>\n'

        current_verse = '0'

        # everything following just read the bookmap and returns it as a nice HTML formatted text
        for i, item in enumerate(book_map):
            if item['type'] == 'surat':
                toc += '<tr>' \
                       f'<td width="2%" style="{PDF_Exporter.surat_cell_css}">' \
                       f'<span style="{PDF_Exporter.new_surat_no_css}">{item["surat_no"]}</span>' \
                       '</td>' \
                       f'<td colspan="2" style="{PDF_Exporter.linked_title_cell_css}{PDF_Exporter.title_cell_css["S"]}">Sourate {item["name"]}</td>' \
                       f'<td style="{PDF_Exporter.page_cell_css}" width="2%">' \
                       f'<span style="{PDF_Exporter.page_no_css}">{item["page"]}</span>' \
                       '</td></tr>\n'
                current_verse = '-1'

            elif item['type'] == 'title':
                if item["verse"] == 0:
                    surat, verse = "", ""
                else:
                    surat = item["surat"]
                    verse = item["verse"]
                if i < (len(book_map) - 1) and\
                        book_map[i + 1]['type'] == 'title' and\
                        book_map[i + 1]['verse'] == item['verse'] and\
                        current_verse != item['verse']:
                    cnt = len([a for a in book_map if a['type'] == 'title'
                               and a['verse'] == item['verse']
                               and a['surat'] == item['surat']])
                    toc += '<tr>' \
                           f'<td rowspan="{cnt}" width="2%" style="{PDF_Exporter.surat_cell_css}">' \
                           f'<span style="{PDF_Exporter.old_surat_no_css}">{surat}</span>' \
                           '</td>' \
                           f'<td rowspan="{cnt}" width="2%" style="{PDF_Exporter.ayat_cell_css}">' \
                           f'<span style="{PDF_Exporter.ayat_no_css}">{verse}</span>' \
                           '</td>' \
                           f'<td style="{PDF_Exporter.linked_title_cell_css}{PDF_Exporter.title_cell_css[3 if item["sub"] else item["rank"]]}">{item["title"]}</td>' \
                           f'<td style="{PDF_Exporter.linked_page_cell_css}{PDF_Exporter.page_cell_css}" width="2%">' \
                           f'<span style="{PDF_Exporter.page_no_css}">{item["page"]}</span>' \
                           '</td></tr>\n'
                    current_verse = item['verse']
                    continue

                # if we're still in the same verse, we don't print surat no, neither verse no, neither page no
                if current_verse == item['verse']:
                    toc += '<tr>' \
                           f'<td style="{PDF_Exporter.title_cell_css[3 if item["sub"] else item["rank"]]}" colspan="2">{item["title"]}</td>' \
                           '</tr>\n'

                # otherwise it starts a new verse or surat,
                else:
                    toc += '<tr>' \
                           f'<td width="2%" style="{PDF_Exporter.surat_cell_css}">' \
                           f'<span style="{PDF_Exporter.old_surat_no_css}">{surat}</span>' \
                           '</td>' \
                           f'<td width="2%" style="{PDF_Exporter.ayat_cell_css}">' \
                           f'<span style="{PDF_Exporter.ayat_no_css}">{verse}</span>' \
                           '</td>' \
                           f'<td style="{PDF_Exporter.linked_title_cell_css}{PDF_Exporter.title_cell_css[3 if item["sub"] else item["rank"]]}">{item["title"]}</td>' \
                           f'<td style="{PDF_Exporter.linked_page_cell_css}{PDF_Exporter.page_cell_css}" width="2%">' \
                           f'<span style="{PDF_Exporter.page_no_css}">{item["page"]}</span>' \
                           '</td></tr>\n'

        toc += '<table>\n'

        # we finalize the TOC by rescaling everything depending on the scale factor
        self.toc = self.rescale_pt(toc, self.settings['factor'])

    def format_tot(self) -> dict:
        """
        This function generates the Table of Topics, a resume of all the topics mentioned in each page
        :param topics_domains: a dict of all the topics sorted by pages
        """

        # these groups are arbitrary defined
        # TODO: should be user defined inside the project
        # TODO: can't define the topic's set in the app, needs to go in the DB

        domains_set = {key: {'title': f'Index des {val}', 'topics': set(), 'doc': '<table>'} for key, val in S.LOCAL.TOPICS.Domains.items()}

        # TODO : correction orthographique classé ??

        for topic in S.LOCAL.TOPICS.topics.values():
            domains_set[topic.domain]['topics'].add(topic)

        # formatting the domain with the given topics
        for domain in domains_set:

            # simple HTML code
            doc = '<table align="center" width="90%" cellspacing="5px" cellpadding="5px">\n'
            doc += f'<tr><td colspan=2>{domains_set[domain]["title"]}</td></tr>'

            # for every lowered topic
            for topic in sorted(domains_set[domain]['topics']):
                try:
                    pages = ", ".join(map(str, sorted(self.topics[topic])))
                    doc += '<tr>' \
                           f'<td style="{PDF_Exporter.linked_title_cell_css}{PDF_Exporter.title_cell_css[2]}">{topic}</td>' \
                           f'<td style="{PDF_Exporter.linked_page_cell_css}{PDF_Exporter.multipage_cell_css}" width="40%">' \
                           f'<span style="{PDF_Exporter.page_no_css}">{pages}</span>' \
                           '</td></tr>\n'
                except KeyError:
                    pass
            doc += '</table>'

            # we finally rescale the point size by the global scale factor
            domains_set[domain]['doc'] = self.rescale_pt(doc, self.settings['factor'])

        return domains_set

    def build_topics(self) -> str:
        page = self.page + 1

        # trying to nicely format the topics for the given page
        try:
            # abort if len == 0
            assert len(S.LOCAL.TOPICS.pages[page]) > 0

            # TODO: based on a dictionnary
            topic_content = '<p><u><span style="font-size:24pt; font-weight:600; color:#c1173d">Thématiques</span></u></p>'
            topic_content += "<p style='line-height:75%;'>"

            # formatting the topic with given style TODO: needs improvement
            for topic in S.LOCAL.TOPICS.pages[page]:
                topic_content += f'<span style="font-size:{self.police}; color:#79173d;">{topic}</span><br>'

            topic_content += "</p>"

        except (KeyError, AssertionError) as e:
            topic_content = ""

        return topic_content

    def build_pdf_context(self, filename: str = None) -> QtPrintSupport.QPrinter:
        """
        Based on a tutorial found online, makes all the settings for a PDF export via a QtPrinter
        :param filename: the PDF filename output
        :return: the QPrinter
        """
        # defines all printing settings
        quality = QtPrintSupport.QPrinter.HighResolution if self.settings['hq'] else QtPrintSupport.QPrinter.ScreenResolution
        printer = QtPrintSupport.QPrinter(quality)

        # override for debug purpose
        printer.setResolution(150)

        self.res = printer.resolution()

        printer.setPaperSize(self.formatpapier)
        printer.setOrientation(self.orientation)
        printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
        printer.setOutputFileName(filename if filename else self.settings['path'])

        # convert values from mm to px
        margeG = self.mm2px(self.margeGT)
        margeH = self.mm2px(self.margeHT) + self.mm2px(10)
        margeD = self.mm2px(self.margeDT)
        margeB = self.mm2px(self.margeBT) + self.mm2px(5)

        printer.setPageMargins(margeG, margeH, margeD, margeB, QtPrintSupport.QPrinter.DevicePixel)
        self.rect = printer.pageRect()

        # the header QRect
        self.rect_t = QRect(0, -self.mm2px(15), self.rect.size().width(), self.mm2px(10))

        # the footer QRect
        self.rect_b = QRect(0, self.rect.size().height() + 2 - self.mm2px(5), self.rect.size().width(), self.mm2px(20))

        # this will be the QRect used to draw the main page
        self.currentRect = QRectF(QRect(QPoint(0, 0), self.rect.size()))

        self.painter = QPainter(printer)
        self.painter.save()

        self.abs_page = 1
        self.progress_total = 0

        return printer

    def post_treatment(self, doc: str) -> (str, str):
        """
        Some reformatting performed on the document, paragraph spacing overrides, appearance, colors..
        :param doc: the document's HTML text
        :return: the first page (with the translation) and the rest of the document
        """
        # Performs some reformatting, cleaning spaces, etc
        doc_content = re.sub(u'\u266C.*?\u266C', '', doc)
        doc_content = re.sub(r'﴿ ', r'﴿', doc_content, re.MULTILINE)
        doc_content = re.sub(r'267(.*?)(</span>﴾)', r'267\1﴾</span>', doc_content, re.MULTILINE)
        doc_content = re.sub(r' ﴾', r'﴾', doc_content, re.MULTILINE)
        doc_content, nb2 = re.subn(r'(<p align="center".*?font-size:17pt.*?)\n.*?-qt-paragraph-type:empty;.*?\n',
                                   r'\1\n<p align="justify" style="line-height:75%; -qt-paragraph-type:empty; font-size:17pt;"><br /></p>\n',
                                   doc_content, re.MULTILINE | re.DOTALL)
        doc_content = re.sub(r'(margin-top:12px;)(.*?)(ayat_separator_LD)', r'margin-top:37px;\2\3',
                             doc_content, re.MULTILINE)
        doc_content = doc_content.replace('margin-bottom:10px;', 'line-height:80%;')

        doc_content = self.rescale_pt(doc_content, self.settings['factor'])

        if self.settings['hq']:
            # if we're exporting for 300dpi, we load the HD version of images
            # TODO: generates png on the fly, use svg instead
            doc_content = doc_content.replace('_LD"', '_HD"')
            doc_content = doc_content.replace('<img style="width:100%"', '<img style="width:750%"')
            doc_content = re.sub(r':(\d+)px', self.px2mm, doc_content)

        try:
            # checking if there is an <hr> tag in the documented
            assert '<hr />' in doc_content

            # if so, we split in 3 parts
            match = re.fullmatch(r'(<!.*?<body.*?>).*?(<p.*?<hr />)(.*?)', doc_content, re.MULTILINE | re.DOTALL)
            header, translation, text_body = match.groups()

            # now we can perform some cleaning / reformatting on the translation page
            # (the one alongside the PDF page preview)
            translation = PDF_Exporter.clean_doc(header + translation + "</body></html>")
            translation = re.sub('<span.*?>|</span>', '', translation)
            # reformat the ayat's number
            translation = re.sub(r'(<p.*?style=")(.*?)(margin-top:\d+px;)(.*?">)(\d+)\. ?(.*?)</p>',
                                 r"""\1\2margin-top:10px;\4<span style=" font-family:'AGA Arabesque'; font-size:10pt; color:#9622d3;">{</span><span style="color:#9622d3;"> \5 </span><span style=" font-family:'AGA Arabesque'; font-size:10pt; color:#9622d3;">}</span> <span style=" font-family:'Microsoft Uighur'; font-size:15pt; color:#267dff; font-weight:600;">\6</span></p>""",
                                 translation)
            translation = translation.replace('line-height:80%;', 'line-height:75%;')
            translation = translation.replace('line-height:100%;', '')
            translation = re.sub(r'(<p.*?style=".*?margin-top:0px;.*?">)(.*?)</p>',
                                 fr"""\1<span style=" font-family:'{G.__font__}'; font-size:15pt; color:#267dff; font-weight:600;">\2</span></p>""", translation)
            translation = translation.replace('<hr />', '')

            final = ''

            # we catch all text "in quote" to apply quotation italic
            for line in translation.split('\n'):
                final += re.sub(r'(&quot;.*?&quot;)', r'<i>\1</i>', line, re.MULTILINE | re.DOTALL) \
                        if len(line.split("&quot;")) % 2 else line
                final += '\n'

            final_parts = []

            translation_line_split = '''<p align="justify" style=" margin-top:10px; line-height:75%; margin-left:10px; margin-right:10px; -qt-block-indent:0; text-indent:10px; -qt-user-state:0; "><span style=" font-family:'AGA Arabesque'; font-size:10pt; '''
            for i, part in enumerate(final.split(translation_line_split)):
                if i % 2 == 0:
                    part = part.replace('#267dff', '#449ccd')
                final_parts.append(part)

            translation = translation_line_split.join(final_parts)

            # repasting the document header to the text's body
            text_body = header + text_body

        # if we can't find a first part (with the translation) we store everything as the text body
        except (ValueError, AttributeError, AssertionError) as e:
            G.exception(e)
            translation = ''
            # emitting to the dialog's output
            self.log.emit(f"/!\\ NO HEAD : {self.page}")

            # all the document goes to the text body
            text_body = doc_content

        return translation, text_body

    def paint_header(self):
        """
        Draws the top of the page
        """
        self.painter.setFont(self.font)
        self.painter.drawText(self.rect_t, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter, f"Page {self.page} - {self.title}")

    def paint_footer(self):
        """
        Draws the foot of the page
        """
        self.painter.setFont(self.font)
        self.painter.drawText(self.rect_b, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter, f"Page {self.abs_page}")

    def paint_quran(self, printer: QtPrintSupport.QPrinter):
        # applying change to QPainter
        self.painter.restore()
        self.painter.save()

        # for the first page we'll fill the text only on half the page
        half_page = self.rect.size().width() // 2
        if self.page not in S.GLOBAL.QURAN.pages:
            return
        # a second document for the first translation page, half of the real page size
        quran_doc = self.createQDocument(printer)
        quran_doc.setPageSize(QSizeF(QSize(half_page - self.mm2px(3), self.rect.size().height())))

        quran_page = ''
        quran_page_content = S.GLOBAL.QURAN.getPageContent(self.page)
        multi_surat = len(quran_page_content) > 1
        for surat in quran_page_content:
            if multi_surat:
                quran_page += f'<p dir="rtl" align="center">{surat[0].surat.name}</p>'
            quran_page += '<p dir="rtl" style="line-height:75%;">'
            ayats = []
            for i, ayat in enumerate(surat):
                ayats.append(f'<span style="color:{"#267dff" if i % 2 == 0 else "#449ccd"};">{ayat.text}</span>')
            quran_page += ' <span style="color:#9622d3;">۝</span> '.join(ayats)
            quran_page += '</p>'

        self.painter.translate(half_page + self.mm2px(5), 0)

        quran_doc.setHtml(quran_page)
        quran_doc.drawContents(self.painter, QRectF(self.currentRect))

        self.painter.translate(-half_page - self.mm2px(5), 0)

        # applying change to QPainter
        self.painter.restore()
        self.painter.save()

    def paint_body_text(self, head: str, text: str, printer: QtPrintSupport.QPrinter):
        """
        The main function which paint every page of current PDF page's document
        :param head: the first translation page, the one alongside the PDF preview
        :param text: the body text we'll render in the next page
        :param printer: the QPrinter object
        """

        # first we create a QDocument on the correct format
        doc = self.createQDocument(printer)
        doc.setPageSize(QSizeF(QSize(self.rect.size().width(), self.rect.size().height())))

        # for the first page we'll fill the text only on half the page
        half_page = self.rect.size().width() // 2

        # this means we've a PDF page corresponding
        if self.page >= 1:
            # a second document for the first translation page, half of the real page size
            trad_doc = self.createQDocument(printer)
            trad_doc.setPageSize(QSizeF(QSize(half_page - self.mm2px(3), self.rect.size().height())))
            trad_doc.setHtml(head)
            trad_doc.drawContents(self.painter, QRectF(self.currentRect))

            self.painter.restore()
            self.painter.save()

            # setting the rect to draw the topics part
            rect = QRectF(QPointF(0, 0),
                          QSizeF(self.rect.size().width() // 2 - self.mm2px(10), self.rect.size().height() // 2))
            delta = QPoint(int(rect.width()) + self.mm2px(20), self.rect.size().height() // 2 + self.mm2px(10))
            #
            # # moving the painter to draw the topics' document content
            self.painter.translate(delta)

            # we create a small document where we'll paste our HTML topic document
            topic_doc = self.createQDocument(printer)
            topic_doc.setPageSize(rect.size())
            topic_doc.setHtml(self.build_topics())
            topic_doc.drawContents(self.painter, QRectF(self.currentRect))

            # restoring the painter in the correct place
            self.painter.translate(-delta)
            #
            self.painter.restore()
            self.painter.save()

            # we first get the first surat mentionned on the page to make it as title
            # if no surat starts in the current body, we keep the previous title
            i, next_surat = self.abs_page, None

            # Works with the bookmap
            # looping through every page of the current document to find a surat
            while i <= (self.abs_page + doc.pageCount()):
                sel = self.get_surat_by_page(i, first=True)
                if sel:
                    next_surat = sel['name']
                    break
                i += 1

            # if we found something we update the title before rendering
            if next_surat:
                self.title = next_surat

            # painting header & footer
            self.paint_header()
            self.paint_footer()

            # visual separator
            # TODO: can make a lot of improvement, custom footer, custom header, custom decoration...
            self.painter.setPen(QPen(QColor(25, 74, 175), self.mm2px(0.3), Qt.PenStyle.SolidLine,
                                     Qt.PenCapStyle.RoundCap))
            self.painter.drawLine(QLineF(self.currentRect.width() / 2, 0, self.currentRect.width() / 2,
                                         self.currentRect.height() - self.mm2px(5)))

            # going to the next page, the body content
            self.abs_page += 1
            printer.newPage()

        # updating the references of the body text
        doc.setHtml(PDF_Exporter.clean_doc(re.sub(r"#_?REF_(\d+)_(\d+)_?#", self.replace_reference, text, flags=re.MULTILINE)))

        # looping through all page of the current body text
        for numpage in range(1, doc.pageCount() + 1):

            # painting the page
            doc.drawContents(self.painter, QRectF(self.currentRect))

            # apply changes to QPainter
            self.painter.restore()
            self.painter.save()

            # moving the QRect to the nextPage
            self.currentRect.translate(0, self.currentRect.height())

            # if the surat changed in the current page, update title
            sel = self.get_surat_by_page(self.abs_page, first=True)
            if sel:
                self.title = sel['name']

            # we paint the header if we're not in Introduction
            if self.page >= 1:
                self.paint_header()

            # but we paint the foot wherever we are
            self.paint_footer()

            # going to the next page
            printer.newPage()
            self.abs_page += 1

            self.painter.translate(0, -self.currentRect.height() * numpage)

    def paint_toc(self, printer: QtPrintSupport.QPrinter):
        """
        This renders the TOC
        :param printer: the QPrinter for the resolution
        """
        self.progress.emit(100, 'Rendering table of content')

        # TODO: store to dictionary lib
        self.title = 'Sommaire'
        self.paint_doc(printer, self.toc)

    def paint_tot(self, printer: QtPrintSupport.QPrinter, topics: dict):
        """
        This renders the TOT for the given topics
        :param printer: the QPrinter for the resolution
        :param topics: a dict of topics
        """
        self.progress.emit(100, 'Rendering lexicon')

        # TODO: store to dictionary lib
        self.title = 'Lexiques'
        self.paint_doc(printer, "<br>".join([topic['doc'] for topic in topics.values()]))

    def paint_doc(self, printer: QtPrintSupport.QPrinter, html: str):
        """
        Here we paint the given document to the current QPainter
        :param printer: a QPrinter obj for the resolution
        :param html: the HTML document code
        """
        # creating a new document and pasting the HTML code inside
        doc = self.createQDocument(printer)
        doc.setPageSize(QSizeF(QSize(self.rect.size().width(), self.rect.size().height())))
        doc.setHtml(html)

        # preparing the QPainter
        self.painter.restore()
        self.currentRect = QRectF(QRect(QPoint(0, 0), self.rect.size()))

        # looping through page and prints it
        for numpage in range(1, doc.pageCount() + 1):
            doc.drawContents(self.painter, QRectF(self.currentRect))

            # apply changes to QPainter
            self.painter.restore()
            self.painter.save()

            self.currentRect.translate(0, self.currentRect.height())

            # we always paint the header
            self.paint_header()

            # going to the next page
            printer.newPage()
            self.abs_page += 1

            self.painter.translate(0, -self.currentRect.height() * numpage)

    def createQDocument(self, printer: QtPrintSupport.QPrinter) -> QTextDocument:
        """
        Creates a simple empty QTextDocument with some basics settings
        :param printer: the QPrinter obj for resolution
        :return: the new QTextDocument
        """
        doc = QTextDocument()

        # some basic settings we apply to every document
        doc.setDefaultFont(QFont(self.font, printer))
        doc.setIndentWidth(self.mm2px(3))
        doc.setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignmentFlag.AlignJustify))

        return doc


if __name__ == "__main__":
    import sys
    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)

    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    editor = Viewer()
    editor.show()
    editor.load_doc(r"C:\Users\mloua\Documents\Admin\ITMR_Online\Scripts\Typer\books\risaala.pdf")
    editor.load_page(editor.current_page)
    app.exec()