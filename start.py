#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import os
import sys
import atexit
import ctypes

from carqueries import utils

try:
    from qtpy import QtGui, QtWidgets
except Exception:
    # exception defined inside qtpy is raised here ;_;
    HAS_QT = False
else:
    HAS_QT = True
        
# ---------------------------------------------------------------------------- #
# -- GLOBALS ----------------------------------------------------------------- #

# reasonable guess for maximum file handles
MAX_HANDLES = 1000

# ---------------------------------------------------------------------------- #
# -- FUNCTIONS --------------------------------------------------------------- #

def safe_exit(exitcode):
    """
    Causes python to exit without garbage-collecting. This is a
    workaround for  common errors than occur in PyQt and PySide
    on exit.
    """
    atexit._run_exitfuncs()
    # close file handles
    if sys.platform != 'darwin':
        os.closerange(3, MAX_HANDLES)
    else:
        for fd in range(3, MAX_HANDLES):
            # trying to close 7 produces an illegal
            # instruction on the Mac.
            if fd != 7:  
                os.close(fd)
    os._exit(exitcode)


def get_palette():
    """
    Gets the default palette for the car queries application.
    """
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(75,75,75))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(55, 55, 55))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(100, 100, 100))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(65, 65, 65))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(85, 85, 85))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(255, 100, 10))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(255, 100, 10))
    palette.setColor(QtGui.QPalette.HighlightedText, 
                     QtGui.QColor(220, 220, 220))
    return palette

# ---------------------------------------------------------------------------- #
# -- APPLICATION ENTRY ------------------------------------------------------- #

def main():
    """
    Main application entry point. 
    """
    if utils.IS_WINDOWS:
        app_id = u'twc.carquiries.1' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        
    if not HAS_QT:
        if utils.IS_WINDOWS:
            # popup a generic Windows error message.
            msg = u'Missing requirement PyQt or PySide.'
            title = u'Missing Requirements'
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0)
        else:
            # Other systems such as Linux simply print to a terminal.
            sys.stderr.write('Missing requirement PyQt or PySide.\n')
        return 1

    # import here to ensure Qt has been successfully found and imported.
    from carqueries.windows import MainWindow
    application = QtWidgets.QApplication(list(sys.argv))
    application.setWindowIcon(utils.get_window_icon())
    application.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
    application.setPalette(get_palette())
    #application.setStyleSheet('')

    window = MainWindow()
    window.show()

    # enter application loop
    application.exec_()
    return 0

if __name__ == '__main__':
    safe_exit(main())