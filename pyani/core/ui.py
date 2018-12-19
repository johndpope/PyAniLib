import os

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
YELLOW = QtGui.QColor(234, 192, 25)
RED = QtGui.QColor(216, 81, 81)


# try to set to unicode - based off what QDesigner does
try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


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

    def get_selection(self):
        '''
        Getter function to return the selected files / folders as a list
        :return a list of files and folders selected in the file dialog
        '''
        return self.selectedFiles


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
        self.__col_space = 150
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
                    # resize to the text, then pad to get a good width
                    self.resizeColumnToContents(col_index)
                    if col_index < root_item.col_count()-1:
                        self.setColumnWidth(col_index, self.columnWidth(col_index) + self.__col_space)
                    else:
                        self.setColumnWidth(col_index, self.columnWidth(col_index))
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
                            # resize to the text, then pad to get a good width
                            self.resizeColumnToContents(col_index)
                            # don't add padding on last column, not needed and just adds horizontal scroll bar
                            if col_index < child_item.col_count()-1:
                                self.setColumnWidth(col_index, self.columnWidth(col_index) + self.__col_space)
                            else:
                                self.setColumnWidth(col_index, self.columnWidth(col_index))
                            child.setTextColor(col_index, child_item.color(col_index))
                            child.setText(col_index, child_item.text(col_index))
                        child.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    parent.setCheckState(0, QtCore.Qt.Unchecked)
            if expand:
                self.expandAll()

    def get_tree_checked(self):
        """
        Finds the selected tree members
        :return: a list of the checked items
        """
        checked = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self, QtWidgets.QTreeWidgetItemIterator.Checked)
        while iterator.value():
            item = iterator.value()
            checked.append(item.text(0))
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