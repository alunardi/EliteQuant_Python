#!/usr/bin/env python
# http://stackoverflow.com/questions/9957195/updating-gui-elements-in-multithreaded-pyqt
from __future__ import absolute_import, division, print_function

import sys
import os
import webbrowser
import psutil
from PyQt5 import QtCore, QtWidgets, QtGui
from source.event.event import EventType
from .ui_market_window import MarketWindow
from source.event.event import GeneralEvent
from source.strategy.mystrategy import strategy_list
from source.event.live_event_engine import LiveEventEngine
from source.event.client_mq import ClientMq

class MainWindow(QtWidgets.QMainWindow):
    general_msg_signal = QtCore.pyqtSignal(GeneralEvent)
    def __init__(self, config):
        super(MainWindow, self).__init__()

        ## member variables
        self._config = config
        self._widget_dict = {}
        self.central_widget = None
        self.market_window = None
        self.order_window = None
        self.message_window = None
        self.transaction_window = None
        self.Position_window = None
        self.strategy_window = None

        ## 0. read config file
        self._symbols = self._config['tickers']

        ## 1. set up gui windows
        self.setGeometry(50,50,600,400)
        self.setWindowTitle("EliteQuant_Python")
        self.setWindowIcon(QtGui.QIcon("logo.ico"))
        self.init_menu()
        self.init_status_bar()
        self.init_central_area()

        ## 2. event engine
        self._events_engine = LiveEventEngine()

        ## 3. client mq
        self._client_mq = ClientMq(self._events_engine)

        ## 3. read strategies
        self.strategies = strategy_list.keys()

        ## 9. wire up event handlers
        self._events_engine.register_handler(EventType.TICK, self.market_window.tick_signal.emit)
        self._events_engine.register_handler(EventType.GENERAL, self.general_msg_signal.emit)
        self.general_msg_signal.connect(self.add_message)

        ## 10. start
        self._events_engine.start()
        self._client_mq.start()

    def init_menu(self):
        menubar = self.menuBar()

        sysMenu = menubar.addMenu('&File')
        # open folder
        sys_folderAction = QtWidgets.QAction('&Folder', self)
        sys_folderAction.setStatusTip('Open Folder')
        sys_folderAction.triggered.connect(self.open_proj_folder)
        sysMenu.addAction(sys_folderAction)

        sysMenu.addSeparator()

        # sys|exit
        sys_exitAction = QtWidgets.QAction('&Exit', self)
        sys_exitAction.setShortcut('Ctrl+Q')
        sys_exitAction.setStatusTip('Exit application')
        sys_exitAction.triggered.connect(self.close)
        sysMenu.addAction(sys_exitAction)

    def init_status_bar(self):
        self.statusthread = StatusThread()
        self.statusthread.status_update.connect(self.update_status_bar)
        self.statusthread.start()

    def init_central_area(self):
        self.central_widget = QtWidgets.QWidget()

        hbox = QtWidgets.QHBoxLayout()

        #-------------------------------- Top Left ------------------------------------------#
        topleft = MarketWindow(self._symbols)
        self.market_window = topleft

        # -------------------------------- Top right ------------------------------------------#
        topright = QtWidgets.QFrame()
        topright.setFrameShape(QtWidgets.QFrame.StyledPanel)
        place_order_layout = QtWidgets.QFormLayout()
        self.sym = QtWidgets.QLineEdit()
        self.quantity = QtWidgets.QLineEdit()
        self.btn_order = QtWidgets.QPushButton('Place Order')
        self.btn_order.clicked.connect(self.place_order)
        place_order_layout.addRow('Symbol', self.sym)
        place_order_layout.addRow('Quantity', self.quantity)
        place_order_layout.addRow(self.btn_order)
        topright.setLayout(place_order_layout)

        # -------------------------------- bottom Left ------------------------------------------#
        bottomleft = QtWidgets.QTabWidget()
        tab1 = QtWidgets.QWidget()
        tab2 = QtWidgets.QWidget()
        tab3 = QtWidgets.QWidget()
        bottomleft.addTab(tab1, "Message")
        bottomleft.addTab(tab2, "Transaction")
        bottomleft.addTab(tab3, "Position")

        self.message_window = QtWidgets.QTextEdit()
        self.message_window.setReadOnly(True)
        self.message_window.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.message_window.moveCursor(QtGui.QTextCursor.End)
        msg_scroll_bar = self.message_window.verticalScrollBar()
        msg_scroll_bar.setValue(msg_scroll_bar.maximum())
        tab1_layout = QtWidgets.QVBoxLayout()
        tab1_layout.addWidget(self.message_window)
        tab1.setLayout(tab1_layout)

        self.transaction_window = QtWidgets.QTableWidget()
        tab2_layout = QtWidgets.QVBoxLayout()
        tab2_layout.addWidget(self.transaction_window)
        tab2.setLayout(tab2_layout)

        self.position_window = QtWidgets.QTableWidget()
        tab3_layout = QtWidgets.QVBoxLayout()
        tab3_layout.addWidget(self.position_window)
        tab3.setLayout(tab3_layout)

        # -------------------------------- bottom right ------------------------------------------#
        bottomright = QtWidgets.QFrame()
        bottomright.setFrameShape(QtWidgets.QFrame.StyledPanel)

        splitter1 = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter1.addWidget(topleft)
        splitter1.addWidget(topright)
        splitter1.setSizes([400,100])

        splitter2 = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter2.addWidget(bottomleft)
        splitter2.addWidget(bottomright)
        splitter2.setSizes([400, 100])

        splitter3 = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter3.addWidget(splitter1)
        splitter3.addWidget(splitter2)
        splitter3.setSizes([400, 100])

        hbox.addWidget(splitter3)
        self.central_widget.setLayout(hbox)
        self.setCentralWidget(self.central_widget)

    def update_status_bar(self, message):
        self.statusBar().showMessage(message)

    def add_message(self, general_event):
        self.message_window.append(general_event.content)

    def open_proj_folder(self):
        webbrowser.open('d:/workspace/elitequant_python/')

    def place_order(self):
        s = str(self.sym.text())
        q = str(self.quantity.text())
        msg = 'o|MKT|' + s + '|' + q
        print('send msg: ' + msg)
        self._client_mq._msg_sock.send(msg, flags=1)

    def closeEvent(self, a0: QtGui.QCloseEvent):
        print('closing main window')
        self._events_engine.stop()
        self._client_mq.stop()

class StatusThread(QtCore.QThread):
    status_update = QtCore.pyqtSignal(str)

    def __init__(self):
        QtCore.QThread.__init__(self)

    def run(self):
        while True:
            cpuPercent = psutil.cpu_percent()
            memoryPercent = psutil.virtual_memory().percent
            self.status_update.emit('CPU Usage: ' + str(cpuPercent) + '% Memory Usage: ' + str(memoryPercent) + '%')
            self.sleep(1)