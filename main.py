import logging
import sys

from os.path import dirname
from sys import path

import cv2
from dls_barcode.config import BarcodeConfig
from dls_barcode.gui import DiamondBarcodeMainWindow
from dls_barcode.new_main_manager import NewMainManager
from PyQt5 import QtWidgets
import argparse
from dls_barcode.version import VERSION
from dls_util.file import FileManager

path.append(dirname(path[0]))

# Required for multiprocessing to work under PyInstaller bundling in Windows
from dls_util import multiprocessing_support


# Detect if the program is running from source or has been bundled
IS_BUNDLED = getattr(sys, 'frozen', False)
if IS_BUNDLED:
    DEFAULT_CONFIG_FILE = "./config.ini"
else:
    DEFAULT_CONFIG_FILE = "../config.ini"


def main(config_file, version):
    # Start process logge

    log = logging.getLogger(".".join([__name__]))
    log.info("CONFIG: " + config_file)

    app = QtWidgets.QApplication(sys.argv)
    config = BarcodeConfig(config_file, FileManager())
    ui = DiamondBarcodeMainWindow(config, version, None)
    
    manager = NewMainManager(config)
    ui.set_actions_triger( manager)
    result = None
    i =0
    manager.initialise_scanner()
    while  i<10:
        

        result = manager.get_result()
        
      
        if result is not None :
     
            ui.displayPuckImage(result.convert_to_gray() )
            i= i+1
             
        else:
            result = None
    manager.cleanup()
    sys.exit(app.exec_())


if __name__ == '__main__':
    # Multiprocessing support for PyInstaller bundling in Windows
    parser = argparse.ArgumentParser()
    parser.add_argument("-cf", "--config_file", type=str, default=DEFAULT_CONFIG_FILE,
                        help="The path of the configuration file (default=" + DEFAULT_CONFIG_FILE + ")")
    args = parser.parse_args()

    main(args.config_file, VERSION)
