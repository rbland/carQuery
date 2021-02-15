#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import webbrowser

from qtpy import QtGui, QtCore, QtWidgets

from carqueries import utils
from carqueries.session import Session, AutoQuery
from carqueries.views import TreeRow, TreeView
from carqueries.auto import AutoMake, AutoMake, AutoRecord, Distance, RecordSort

# ---------------------------------------------------------------------------- #
# -- FUNCTIONS --------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #
# -- CLASSES ----------------------------------------------------------------- #

class MainWindow(QtWidgets.QMainWindow):
    """
    The main application.
    """
    MENU_CSS = """
QMenuBar {
    background-color: #444;
}

QMenuBar::item {
    background: #444;
}

QMenuBar::item:selected {
    background: #999;
}

QMenu {
    background-color: #444;
}

QMenu::item:selected {
    background-color: #999;
}

"""
    def __init__(self, parent=None):
        """
        Initialization.
        """
        self.session = Session()
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle('Car Querier')
        self.resize(1300, 800)
        self.move(200, 200)
        self.widget = QtWidgets.QWidget(self)
        self.vlayout = QtWidgets.QVBoxLayout(self.widget)
        self.setCentralWidget(self.widget)
        menu = QtWidgets.QMenuBar(self)
        menu.setStyleSheet(self.MENU_CSS)
        file_menu = menu.addMenu('File')
        file_menu.addAction('&Save', self.save_session,
                            QtGui.QKeySequence('Ctrl+S'))
        file_menu.addAction('&Load', self.load_session,
                            QtGui.QKeySequence('Ctrl+L'))
        file_menu.addAction('&Quit', self.close,
                            QtGui.QKeySequence('Ctrl+Q'))

        filter_menu = menu.addMenu('Filters')
        args = ('Show Hidden', self.show_hidden,
                QtGui.QKeySequence('Ctrl+Shift+H'))
        self.show_hidden_action = filter_menu.addAction(*args)
        self.show_hidden_action.setCheckable(True)
        self.show_hidden_action.setChecked(False)
        filter_menu.addAction('&Hide Selected', self.hide_selected,
                            QtGui.QKeySequence('Ctrl+H'))
        filter_menu.addAction('&Unhide Selected', self.unhide_selected,
                            QtGui.QKeySequence('Ctrl+U'))
        filter_menu.addAction('&Unhide All', self.unhide_all,
                            QtGui.QKeySequence('Ctrl+Shift+U'))
        self.setMenuBar(menu)
        self.setWindowIcon(utils.get_window_icon())

        #self.populate_btn = QtGui.QPushButton('Populate...', self)
        #self.vlayout.addWidget(self.populate_btn)
        self.tree = TreeView()
        self.vlayout.addWidget(self.tree)
        query = AutoQuery.defaults(self.session)
        self.tree.set_model(self.session.populate(query))

    def show_hidden(self):
        """
        Shows hidden entries.
        """
        self.tree.proxy.show_hidden = self.show_hidden_action.isChecked()
        self.tree.proxy.reset()

    def hide_selected(self):
        """
        Hides the selected rows.
        """
        for row in self.tree.get_selected_rows():
            row.set_hidden(True)
        self.tree.proxy.invalidateFilter()

    def unhide_selected(self):
        """
        Hides the selected rows.
        """
        for row in self.tree.get_selected_rows():
            row.set_hidden(False)
        self.tree.update()

    def unhide_all(self):
        """
        Unhides all rows.
        """
        for row in self.manager.iter_tree():
            row.set_hidden(False)
        self.tree.proxy.reset()

    def save_session(self):
        """
        """
        self.manager.save()

    def load_session(self):
        """
        """
        raise NotImplementedError


class QueryWindow(QtWidgets.QWidget):
    """
    A window for specifying the parameters of a car query.
    """
    def __init__(self):
        QtWidgets.QWidget.__init__(self)