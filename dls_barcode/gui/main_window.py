

from dls_barcode.camera.scanner_message import ScanErrorMessage
from dls_util.beeper import Beeper
import logging

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import  QThread, QTime, QTimer, pyqtSlot
from PyQt5.QtWidgets import QMessageBox

from dls_barcode.config import BarcodeConfigDialog
from dls_barcode.gui.progress_bar import ProgressBox
from dls_barcode.gui.scan_button import ScanButton
from dls_barcode.scanner_manager import ScannerManager
from dls_barcode.scanner import Scanner 
from dls_barcode.processor import SideProcessor, TopProcessor
from dls_barcode.scan.scan_result import ScanResult
from dls_util.cv.frame import Frame

from .barcode_table import BarcodeTable
from .image_frame import ImageFrame
from .menu_bar import MenuBar
from .message_box import MessageBox
from .message_factory import MessageFactory
from .record_table import ScanRecordTable


class DiamondBarcodeMainWindow(QtWidgets.QMainWindow):
    """ Main GUI window for the Barcode Scanner App.
    """

    def __init__(self, config, version, flags, *args, **kwargs):

        super().__init__(flags, *args, **kwargs)
        self._log = logging.getLogger(".".join([__name__]))

        self._config = config
        self._version = version

        # UI elements
        self._record_table = None
        self._barcode_table = None
        self._image_frame = None
        self._holder_frame = None
        self._result_frame = None
        self._scan_button = None
        self._countdown_box = None
        
        self.main_thread = QThread()
        self.processor_thread = QThread() 
        self.top_processor_thread = QThread()
        self.main_worker = None
        self._manager = ScannerManager(self._config)
        self._last_side_result = None
        self._duration = self._config.get_top_camera_tiemout()
        self.timer = QTimer()
        self.timer.setSingleShot(True) #timer which fies only once 
        self.timer.timeout.connect(self._on_time_out)
        self.processing_flag = True
        self._init_ui()

    def _init_ui(self):
        """ Create the basic elements of the user interface.
        """
        self._window_icon = QtGui.QIcon("..\\resources\\icons\\qr_code_32.png")

        self.setGeometry(50, 50, 1500, 650) #950
        self.setWindowTitle('Diamond Puck Barcode Scanner')
        self.setWindowIcon(self._window_icon)

        self._menu_bar = MenuBar(self.menuBar(), self._version, None)

        # Barcode table - lists all the barcodes in a record
        self._barcode_table = BarcodeTable(self._config)

        # Scan button - start/stop scan
        self._scan_button = ScanButton('Start/stop scan')

        # Image frame - displays image of the currently selected scan record
        self._image_frame = ImageFrame("Plate")
        self._holder_frame = ImageFrame("Holder")
        self._result_frame = ImageFrame("Result")

        # Scan record table - lists all the records in the store
        self._record_table = ScanRecordTable(self._barcode_table, self._image_frame, self._holder_frame, self._result_frame, self._config)

        # Message display
        self._message_box = MessageBox()

        # Count down display
        self._countdown_box = ProgressBox()

        # Create layout

        hbox = QtWidgets.QHBoxLayout()
        hbox.setSpacing(10)

        table_vbox = QtWidgets.QVBoxLayout()
        table_vbox.addWidget(self._record_table)
        table_vbox.addWidget(self._scan_button)

        hbox.addLayout(table_vbox)
        hbox.addWidget(self._barcode_table)
      

        img_vbox = QtWidgets.QVBoxLayout()
        img_vbox.addWidget(self._result_frame)
        
        img_hbox = QtWidgets.QHBoxLayout()
        img_hbox.addWidget(self._holder_frame)
        img_hbox.addWidget(self._image_frame)
        img_vbox.addLayout(img_hbox)

        msg_hbox = QtWidgets.QHBoxLayout()
        msg_hbox.setSpacing(10)
        msg_hbox.addWidget(self._message_box)
        msg_hbox.addWidget(self._countdown_box)

        img_vbox.addLayout(msg_hbox)

        hbox.addLayout(img_vbox)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox)

        main_widget = QtWidgets.QWidget()
        main_widget.setLayout(vbox)
        self.setCentralWidget(main_widget)

        self.show()

    def set_actions_triger(self):
        self._load_store_records()
        self._scan_button.click_action(self._on_scan_action_clicked)
        self._start_scanner()
        self._menu_bar.about_action_trigerred(self._on_about_action_clicked)
        self._menu_bar.options_action_triggered(self._on_options_action_clicked)
        self._record_table.cell_pressed_action_triggered(self._stop_scanner)

    def _stop_scanner(self):
        self._scan_button.setStartLayout()
        self.resetCountdown()
        self._kill_main_thread()
        
    def _start_scanner(self):
        self._scan_button.setStopLayout()
        self._start_main_thread()      
          
    def _on_about_action_clicked(self):
        QtWidgets.QMessageBox.about(self, 'About', "Version: " + self._version)

    def _on_scan_action_clicked(self):
        self._log.debug("MAIN: Scan menu clicked")
        if  self._scan_button.is_running():
            self._stop_scanner()
        else: 
            self._start_scanner()
            
    def _start_main_thread(self):
        self.main_thread = QThread()
        self._manager.initialise_scanner()
        self.main_worker = Scanner(self._manager.side_camera_stream,self._manager.top_camera_stream)
        self.main_worker.moveToThread(self.main_thread)
        self.main_thread.started.connect(self.main_worker.run)
        self.main_worker.new_side_frame.connect(self.displayHolderFrame)
        self.main_worker.new_top_frame.connect(self.displayPuckFrame)
        self.main_worker.finished.connect(self.main_worker.deleteLater)   
        self.main_thread.finished.connect(self.main_worker.deleteLater) 
        self.main_worker.finished.connect(self.main_thread.quit)
        self.main_worker.images_collected.connect(self.start_processor)
        self.main_worker.camera_error.connect(self.displayCameraErrorMessage)
        self.main_thread.start()
            
    def _kill_main_thread(self):
        if self.main_worker is not None:
            self.main_worker.stop()     
        self.main_thread.quit()
        self.main_thread.wait()
        self._manager.cleanup()
        
    @pyqtSlot(Frame, Frame)
    def start_processor(self, side_frame, top_frame):    
        if  not self.processor_thread.isRunning():# and not self._freeze:
                self.processor_worker = SideProcessor(self._manager.side_camera_stream, side_frame)
                self.processor_worker.moveToThread(self.processor_thread)
                self.processor_thread.started.connect(self.processor_worker.run)
                self.processor_worker.finished.connect(self.processor_thread.quit)
                self.processor_worker.finished.connect(self.processor_thread.wait)
                self.processor_thread.start()
                self.processor_worker.side_scan_error_signal.connect(self.clear_frame_display_message)
                self.processor_worker.side_result_signal.connect(self.set_new_side_code)
        if self.processing_flag:
                if not self.timer.isActive():
                   self.timer.start(self._duration*1000) # convert duration to miliseconds
                   self.startCountdown()
                   self.clear_frame()
                if not self.top_processor_thread.isRunning():
                    self.top_processor_worker = TopProcessor(self._manager.top_camera_stream, top_frame)
                    self.top_processor_worker.moveToThread(self.top_processor_thread)
                    self.top_processor_thread.started.connect(self.top_processor_worker.run)
                    self.top_processor_worker.finished.connect(self.top_processor_thread.quit)
                    self.top_processor_worker.finished.connect(self.top_processor_thread.wait)
                    self.top_processor_thread.start()
                    self.top_processor_worker.full_and_valid_signal.connect(self.set_full_and_valid_scan)
                    self.top_processor_worker.top_result_signal.connect(self.addRecordFrame)
 
    def _on_options_action_clicked(self):
        self._kill_main_thread()
        dialog = BarcodeConfigDialog(self._config)
        self._stop_scanner()
        dialog.exec_()
        
    def _on_time_out(self):
        self.processing_flag = False
        self.displayScanTimeoutMessage() # need to know more to display the correct
        self.displayPuckScanCompleteMessage()

    @pyqtSlot(ScanResult)
    def set_new_side_code(self, result): 
        result_first_barcode = result.get_first_barcode().data()
        if self._last_side_result is None:
            self._last_side_result = result
            self.processing_flag = True
        if result_first_barcode != self._last_side_result.get_first_barcode().data():
            self._last_side_result = result
            self.processing_flag = True
        
    def set_full_and_valid_scan(self): #fast track time_out
        self.timer.stop()
        self.processing_flag = False
        self.displayPuckScanCompleteMessage()
        self.scanCompleted()
                
    def closeEvent(self, event):
        """This overrides the method from the base class.
        It is called when the user closes the window from the X on the top right."""
        self._kill_main_thread()
        event.accept()

    def displayCameraErrorMessage(self):
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Critical)
        message_box.setWindowTitle("Camera Error")
        message_box.setText( MessageFactory.camera_not_found_message().content())
        configure_button = message_box.addButton("Configure", QMessageBox.ActionRole)
        message_box.addButton("Quit", QMessageBox.ActionRole)
        message_box.setEscapeButton(configure_button)
        message_box.exec_()
        if message_box.clickedButton() == configure_button:
            self._on_options_action_clicked()
            self._on_scan_action_clicked()
        else:
            self.close()

    def displayPuckScanCompleteMessage(self):
        Beeper.beep()
        self._message_box.display(MessageFactory.puck_scan_completed_message())
    
    @pyqtSlot(ScanErrorMessage)
    def displayScanErrorMessage(self, scanner_msg): 
        self._message_box.display(MessageFactory.from_scanner_message(scanner_msg))
    
    @pyqtSlot(ScanErrorMessage)
    def clear_frame_display_message(self, scanner_msg):     
        self._result_frame.clear_frame_and_set_text(scanner_msg.content())
        
    def clear_frame(self):
        self._result_frame.clear_frame()

    def displayScanTimeoutMessage(self):
        Beeper.beep()
        self._message_box.display(MessageFactory.scan_timeout_message())

    @pyqtSlot(Frame)
    def displayPuckFrame(self, frame):
        if frame is None:
            return
        self._image_frame.display_image(frame.frame_to_image())
    
    @pyqtSlot(Frame)
    def displayHolderFrame(self, frame):
        if frame is None:
            return
        self._holder_frame.display_image(frame.frame_to_image())

    def _load_store_records(self):
        self._record_table._load_store_records()
        
    
    
    @pyqtSlot(ScanResult)
    def addRecordFrame(self, top_result):
        holder_barcode = self._last_side_result.get_first_barcode().data()
        plate = top_result.plate()
        holder_image = self._last_side_result.get_frame_image()
        pins_image = top_result.get_frame_image()
        self._record_table.add_record_frame(holder_barcode, plate, holder_image, pins_image)


    def startCountdown(self):
        self._countdown_box.start_countdown(self._duration)

    def resetCountdown(self):
        self._countdown_box.reset_countdown()

    def scanCompleted(self):
        self._countdown_box.scan_completed()
        
    
