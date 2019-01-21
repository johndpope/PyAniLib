import os
import sys
import logging
import pyani.core.util
import pyani.core.error_logging

logger = logging.getLogger()

# set the environment variable to use a specific wrapper
# it can be set to pyqt, pyqt5, pyside or pyside2 (not implemented yet)
# you do not need to use QtPy to set this variable
os.environ['QT_API'] = 'pyqt'
# import from QtPy instead of doing it directly
# note that QtPy always uses PyQt5 API
from qtpy import QtGui, QtWidgets, QtCore
# qtpy doesn't have fileDialog, so grab from PyQT4
from PyQt4.QtGui import QFileDialog


GOLD = "#be9117"
GREEN = "#397d42"
CYAN = "#429db6"
WHITE = "#ffffff"
YELLOW = QtGui.QColor(234, 192, 25)
RED = QtGui.QColor(216, 81, 81)


# try to set to unicode - based off what QDesigner does
try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


class AniQMainWindow(QtWidgets.QMainWindow):
    """
    Builds a QMain Window with the given title, icon and optional width and height
    Provides the main window widget, called self.main_win
    Provides the main layout for the window - self.main_layout which is a QVBoxlayout
    Adds two ui elements, version as a Qlabel and a help link to documentation as a Qlabel at the top of the window
    Handles version management displaying a message when updates are available
    Drag and drop support
    Creates a msg window class variable which allows apps to display pop up dialog warnings,
    errors, info, etc.. - uses pyani.core.ui.QtMsgWindow class
    Provides some spacing and font widgets:
        self.titles : 14 pt size font bold
        self.bold_font : a bold font - default QT pt size
        self.v_spacer = QSpacerItem 35 px high
        self.empty_space = QSpacerItem with width 1 px and height 1 px
        self.horizontal_spacer = QSpacerItem 50 px width
        self.title_vert_spacer = QSpacerItem 15 px high
    :param win_title : the window's title as a string
    :param win_icon : absolute path to a png or icon (.ico) file
    :param app_mngr : an AniAppMngr class object for managing applications
    :param width : optional width of the window
    :param height: optional height of the window
    :param error_logging : optional error log (pyani.core.error_logging.ErrorLogging object) from trying
    to create logging in main program
    """
    def __init__(self, win_title, win_icon, app_mngr, width=600, height=600, error_logging=None):
        super(AniQMainWindow, self).__init__()

        # if no error logging object, create a dummy object to grab the root log dir. Don't need a real app name
        # to get this
        if not error_logging:
            error_logging = pyani.core.error_logging.ErrorLogging("Generic App")
            log_name = error_logging.root_log_dir
        else:
            log_name = error_logging.log_file_name

        # setup version management
        self.app_manager = app_mngr
        self.version = self.app_manager.user_version
        self.vers_label = QtWidgets.QLabel()
        self.vers_update = QtWidgets.QLabel()

        # help links - http://172.18.10.11:8090/display/KB/{app name} - spaces use +, so Py+Shoot or Py+App+Mngr
        self.help_page_label = QtWidgets.QLabel(
            "<a href=\"{0}\"><span style=\" text-decoration: none; color:{1}\">"
            "Click here for the application documentation</a>".format(self.app_manager.app_doc_page, WHITE)
        )
        # path to help icon
        self.help_icon = os.path.normpath(
            "C:\Users\Patrick\PycharmProjects\PyAniTools\Resources_Shared\help_icon_32.png"
        )

        # setup title and icon
        self.win_utils = QtWindowUtil(self)
        self.setWindowTitle(win_title)
        self.win_utils.set_win_icon(win_icon)

        # main widget for window
        self.main_win = QtWidgets.QWidget()

        # pop-up windows
        self.msg_win = QtMsgWindow(self)
        self.progress_win = QtMsgWindow(self)

        # version management - check version data
        # check if app manager had an error loading version data. If so then display message to user.
        if self.version is None or self.app_manager.latest_version is None:
            self.vers_update.setText("")
            self.vers_label.setText("Could not load version data. See log.")
            self.vers_label.setStyleSheet("color:{0};".format(RED.name()))
            self.msg_win.show_warning_msg(
                "Version Warning",
                "There was a problem loading the version information. You can continue, but please "
                "file a jira and attach the latest log file from here {0}.".format(log_name)
            )
        # check if the app manager is the latest version, if not show message for update
        elif not self.app_manager.is_latest():
            self.vers_update.setText(
                "<a href=\"#update\"><span style=\" text-decoration: none; color:{0}\">There is a newer version, "
                "click here to update.</span></a>".format(RED.name())
            )
            self.vers_label.setText("Version {0}".format(self.version))
            self.vers_label.setStyleSheet("color:{0};".format(RED.name()))
        # latest version
        else:
            self.vers_update.setText("")
            self.vers_label.setText("Version {0}".format(self.version))

        # error and message logging
        self.log = []

        # common ui elements

        # set font size and style for title labels
        self.titles = QtGui.QFont()
        self.titles.setPointSize(14)
        self.titles.setBold(True)
        self.bold_font = QtGui.QFont()
        self.bold_font.setBold(True)
        # spacer to use between sections
        self.v_spacer = QtWidgets.QSpacerItem(0, 35)
        self.empty_space = QtWidgets.QSpacerItem(1, 1)
        self.horizontal_spacer = QtWidgets.QSpacerItem(50, 0)
        self.title_vert_spacer = QtWidgets.QSpacerItem(0, 15)

        # main layout
        self.main_layout = QtWidgets.QVBoxLayout()
        # create the layout and add version, plus create signals/slots
        self._build_ui()
        # set default window size
        self.resize(width, height)
        # center the window
        center(self)

    def add_layout_to_win(self):
        """Adds the main layout to the window, called by inheriting classes
        """
        # add the layout to the main app widget
        self.main_win.setLayout(self.main_layout)

    def create_layout(self):
        """Virtual function, require implementation, call add_layout_to_win at end to add main layout
        to the main window
        """
        raise NotImplementedError()

    def set_slots(self):
        """Virtual function, require implementation
        """
        raise NotImplementedError()

    def dragEnterEvent(self, e):
        """
        provides an event which is sent to the target widget as dragging action enters it.
        :param e: mime data of the event
        """
        if e.mimeData().hasUrls:
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        """
        called used when the drag and drop action is in progress.
        :param e: mime data of the event
        """
        if e.mimeData().hasUrls:
            e.accept()
        else:
            e.ignore()

    @staticmethod
    def drop_event_wrapper(e, func):
        """
        wraps functionality of dropEvent(e), generic use lets other windows use drag and drop with
        whatever function they need. passes list of files to the function func
        To use implement dropEvent(self, e) in deriving class, and call this function passing the mime data e and
        function func which takes a list of string filenames. also set call self.setAcceptsDrops(True)
        :param e: mime data of the event
        :param func : function to call to process mime data, should accept a list of strings representing filenames
        """
        if e.mimeData().hasUrls:
            e.setDropAction(QtCore.Qt.CopyAction)
            e.accept()
            # Workaround for OSx dragging and dropping
            file_names = []
            for url in e.mimeData().urls():
                file_names.append(str(url.toLocalFile()))
            func(file_names)
        else:
            e.ignore()

    def _update_app(self):
        """Launches external app updater and closes this app.
        displays error if encountered, otherwise exits application
        """
        error_msg = pyani.core.util.launch_app(self.app_manager.updater_app, "")
        if error_msg:
            self.msg_win.show_error_msg("Update Error", error_msg)
        else:
            sys.exit(0)

    def _help_link(self):
        """Launch default browser and load application doc page
        """
        link = QtCore.QUrl(self.app_manager.app_doc_page)

        QtGui.QDesktopServices.openUrl(link)

    def _build_ui(self):
        """Builds the UI widgets, slots and layout
        """
        self._create_layout()
        self._set_slots()
        self.setCentralWidget(self.main_win)

    def _create_layout(self):
        """Adds version widget to main layout
        """
        # add version to right side of screen
        # set font size and style for title labels
        version_font = QtGui.QFont()
        version_font.setPointSize(10)
        version_font.setBold(True)
        help_font = QtGui.QFont()
        help_font.setPointSize(10)

        self.vers_label.setFont(version_font)
        self.help_page_label.setFont(help_font)
        h_layout_vers = QtWidgets.QHBoxLayout()

        pic = QtWidgets.QLabel()
        pic.setPixmap(QtGui.QPixmap(self.help_icon))
        h_layout_vers.addWidget(pic)
        h_layout_vers.addWidget(self.help_page_label)
        h_layout_vers.addStretch(1)
        h_layout_vers.addWidget(self.vers_label)
        self.main_layout.addLayout(h_layout_vers)
        h_layout_vers_update = QtWidgets.QHBoxLayout()
        h_layout_vers_update.addStretch(1)
        h_layout_vers_update.addWidget(self.vers_update)
        self.main_layout.addLayout(h_layout_vers_update)

    def _set_slots(self):
        """Set the link clicked signal for version update text and help link
        """
        self.vers_update.linkActivated.connect(self._update_app)
        self.help_page_label.linkActivated.connect(self._help_link)

    def _log_error(self, error):
        """
        Simple utility to format errors and append to a list
        :param error: the error as a string
        """
        self.log.append("<font color={0}>{1}</font>".format(pyani.core.ui.RED.name(), error))


class FileDialog(QFileDialog):
    '''
    This function allows both files and folders to be selected. QFileDialog doesn't support
    this functionality in pyqt 4.

    Usage:

    dialog = FileDialog.FileDialog()
    dialog.exec_()
    get selection - returns a list
    selection = dialog.get_selection()
    '''
    def __init__(self, *args, **kwargs):
        super(FileDialog, self).__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.selectedFiles = []

        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.ExistingFiles)

        # get all buttons and find one labeled open, connect custom event
        btns = self.findChildren(QtWidgets.QPushButton)
        self.openBtn = [x for x in btns if 'open' in str(x.text()).lower()][0]
        self.openBtn.clicked.disconnect()
        self.openBtn.clicked.connect(self.open_clicked)

        # grab the tree view
        self.tree = self.findChild(QtWidgets.QTreeView)

    def open_clicked(self):
        '''
        Gets the selection in the file dialog window. Stores selection in a class variable.
        :arg: self : Just the class
        '''
        indices = self.tree.selectionModel().selectedIndexes()
        files = []
        for i in indices:
            if i.column() == 0:
                item = i.data()
                # this is needed to handle script conversion to standalone exe. Item executed
                # via python is a string, but is a QVariant in standalone exe. So first check
                # for a QVariant, then convert that to a string which gives a QString. Convert that
                # to python string using str()
                if isinstance(item, QtCore.QVariant):
                    itemName = str(item.toString())
                else:
                    itemName = str(item)
                files.append(os.path.join(str(self.directory().absolutePath()), itemName))
        self.selectedFiles = files
        self.close()
        logger.info("File dialog class un-normalized selection: {0}".format(", ".join(self.selectedFiles)))

    def get_selection(self):
        '''
        Getter function to return the selected files / folders as a list
        :return a list of files and folders selected in the file dialog normalized to os path system convention
        and sorted
        '''
        # make sure paths get normalized so they are correct
        normalized_paths = [os.path.normpath(file_name) for file_name in self.selectedFiles]
        sorted_normalized_paths = sorted(normalized_paths)
        logger.info("File dialog class normalized selection: {0}".format(", ".join(sorted_normalized_paths)))
        # sort the paths
        return sorted_normalized_paths


class QHLine(QtWidgets.QFrame):
    """
    Creates a horizontal line
    :arg: a color in qt css style
    """
    def __init__(self, color):
        super(QHLine, self).__init__()
        # override behavior of style sheet
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setStyleSheet("background-color:{0};".format(color))

        self.setLineWidth(3)


class QtMsgWindow(QtWidgets.QMessageBox):
    """
    Class to display QtMessageBox Windows
    Takes the main window upon creation so that pop up appears over it
    """
    def __init__(self, main_win):
        super(QtMsgWindow, self).__init__()
        # create the window and tell it to parent to the main window
        self.msg_box = QtWidgets.QMessageBox(main_win)

    def hide(self):
        """Hide the msg box
        """
        self.msg_box.hide()

    def show_error_msg(self, title, msg):
        """
        Show a popup window with an error
        :param title: the window title
        :param msg: the message to the user
        """

        self._show_message_box(title, self.Critical, msg)

    def show_warning_msg(self, title, msg):
        """
        Show a popup window with a warning
        :param title: the window title
        :param msg: the message to the user
        """
        self._show_message_box(title, self.Warning, msg)

    def show_question_msg(self, title, msg):
        """
        Opens a qt pop-up window with a yes and no button
        :param title: the window title
        :param msg: the message to the user
        :return: True if user presses Yes, False if user presses No
        """
        response = self.msg_box.question(self, title, msg, self.Yes | self.No)
        if response == self.Yes:
            return True
        else:
            return False

    def show_info_msg(self, title, msg):
        """
        Show a popup window with information
        :param title: the window title
        :param msg: the message to the user
        """
        self._show_message_box(title, self.Information, msg)

    def show_msg(self, title, msg):
        self.msg_box.setWindowTitle(title)
        self.msg_box.setIcon(self.NoIcon)
        self.msg_box.setText(msg)
        self.msg_box.setStandardButtons(self.msg_box.NoButton)
        self.msg_box.show()

    def _show_message_box(self, title, icon, msg):
        """
        Show a popup window
        :param title: the window title
        :param icon: icon to show - information, warning, critical, etc...
        :param msg: the message to the user
        """
        self.msg_box.setWindowTitle(title)
        self.msg_box.setIcon(icon)
        self.msg_box.setText(msg)
        self.msg_box.setStandardButtons(self.msg_box.Ok)
        self.msg_box.show()


class QtWindowUtil:
    """
    Class of utility functions common to all qt windows
    Takes the main window
    """

    def __init__(self, main_win):
        self.__win = main_win

    def set_win_icon(self, img):
        """
        Sets the window icon
        :param img: path to an image for the icon
        """
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(_fromUtf8(img)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.__win.setWindowIcon(icon)


class CheckboxTreeWidgetItem(object):
    """
    Class of tree items. represents a row of text in a qtreewidget
    Accepts a list of text (the columns) and corresponding text colors. Defaults to white if
    no color given.
    ex: items = ["text1","text2"], colors=None or colors=[None, QtCore.Qt.red]
    """
    def __init__(self, items, colors=None):
        self.__columns = []
        for index in range(0, len(items)):
            # make sure colors given and not None
            if colors:
                # get the color
                color = colors[index]
                # if color is none, set to white
                if not color:
                    color = QtCore.Qt.white
            # no colors given set to white
            else:
                color = QtCore.Qt.white
            item = {"text": items[index], "color": color}
            self.__columns.append(item)

    def col_count(self):
        """Column count - ie length of the list
        """
        return len(self.__columns)

    def text(self, index):
        """
        Text at the specified column index
        :param index: column number
        :return: the text as a string
        """
        return self.__columns[index]["text"]

    def color(self, index):
        """
        Color of the text at the specified column index
        :param index: column number
        :return: a QColor
        """
        return self.__columns[index]["color"]


class CheckboxTreeWidget(QtWidgets.QTreeWidget):
    """
    Qt tree custom class with check boxes. Supports multiple columns. Only supports one level deep, ie parent->child
    not parent->child->child....
    """
    def __init__(self, tree_items=None, columns=None, expand=True):
        """
        Builds a self.tree of checkboxes with control over text color. Note allows creation without building tree
        for when tree is built later using user selections.
        :param tree_items: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = list of CheckboxTreeWidgetItems }
        :param columns: number of columns in a tree row
        :param expand: show the tree in expanded view
        """
        super(CheckboxTreeWidget, self).__init__()
        # spacing between columns
        self.__col_space = 50
        self.build_checkbox_tree(tree_items, columns, expand)

    def build_checkbox_tree(self, tree_items, columns, expand=True):
        """
        Builds a self.tree of checkboxes with control over text color
        :param tree_items: a list of dicts, where dict is:
        { root = CheckboxTreeWidgetItem, children = list of CheckboxTreeWidgetItems }
        :param columns: number of columns in a tree row
        :param expand: show the tree in expanded view, default true
        """
        # root doesn't have any info, hide it
        self.header().hide()

        if tree_items:
            self.setColumnCount(columns)
            # go through tree and build
            for tree_item in tree_items:
                parent = QtWidgets.QTreeWidgetItem(self)
                root_item = tree_item["root"]
                # build main column rows
                for col_index in range(0, root_item.col_count()):
                    parent.setTextColor(col_index, root_item.color(col_index))
                    parent.setText(col_index, root_item.text(col_index))
                parent.setFlags(parent.flags() | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsUserCheckable)
                # build children rows if they exist - keys will be 2 if they exist
                if len(tree_item.keys()) > 1:
                    child_items = tree_item["children"]
                    for child_item in child_items:
                        child = QtWidgets.QTreeWidgetItem(parent)
                        child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
                        for col_index in range(0, child_item.col_count()):
                            child.setTextColor(col_index, child_item.color(col_index))
                            child.setText(col_index, child_item.text(col_index))
                        child.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    parent.setCheckState(0, QtCore.Qt.Unchecked)
            if expand:
                self.expandAll()
            # resize columns to fit contents better, but skip last column
            for col in range(0, columns-1):
                self.resizeColumnToContents(col)
                self.setColumnWidth(col, self.columnWidth(col) + self.__col_space)

    def get_tree_checked(self):
        """
        Finds the selected tree members
        :return: a list of the checked items
        """
        checked = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.Checked)
        while iterator.value():
            item = iterator.value()
            checked.append(str(item.text(0)))
            iterator += 1
        return checked

    def update_item(self, existing_text, updated_item):
        """
        Updates a tree item
        :param existing_text: the existing item text
        :param updated_item: the updated item as a CheckboxTreeWidgetItem
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.text(0) == existing_text:
                for col_index in range(0, updated_item.col_count()):
                    item.setTextColor(col_index, updated_item.color(col_index))
                    item.setText(col_index, updated_item.text(col_index))
            iterator += 1

    def clear_all_items(self):
        """Clear the tree
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.All)
        while iterator.value():
            iterator.value().takeChildren()
            iterator += 1
        i = self.topLevelItemCount()
        while i > -1:
            self.takeTopLevelItem(i)
            i -= 1

    def hide_items(self, item_list):
        """
        Hides rows based off the list given
        :param item_list: a list of strings where the string is the tree's first column text
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            tree_item = iterator.value()
            for item in item_list:
                if tree_item.text(0) == item:
                    tree_item.setHidden(True)
            iterator += 1

    def show_items(self, item_list):
        """
        Shows rows based off the list given
        :param item_list: a list of strings where the string is the tree's first column text
        """
        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while iterator.value():
            tree_item = iterator.value()
            for item in item_list:
                if tree_item.text(0) == item:
                    tree_item.setHidden(False)
            iterator += 1


def build_checkbox(label, state, directions):
    """
    Builds a check box with label, state and directions
    :param label: the label to the left of the check box
    :param state: True if checked, False if unchecked
    :param directions: the text when you hover over the check box
    :return: the label, check box
    """
    label = QtWidgets.QLabel(label)
    cbox = QtWidgets.QCheckBox()
    cbox.setChecked(state)
    cbox_directions = directions
    cbox.setToolTip(cbox_directions)
    return label, cbox


def center(win):
    """
    Center the window on screen where the mouse is
    :param win: the qt window to center
    """
    frame_gm = win.frameGeometry()
    screen = QtWidgets.QApplication.desktop().screenNumber(QtWidgets.QApplication.desktop().cursor().pos())
    center_point = QtWidgets.QApplication.desktop().screenGeometry(screen).center()
    frame_gm.moveCenter(center_point)
    win.move(frame_gm.topLeft())