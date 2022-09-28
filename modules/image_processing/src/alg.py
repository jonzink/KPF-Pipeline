#packages
import numpy as np
import matplotlib.pyplot as plt
from modules.Utils.frame_subtract import FrameSubtract
from modules.Utils.config_parser import ConfigHandler
from kpfpipe.models.level0 import KPF0
from keckdrpframework.models.arguments import Arguments

class ImageProcessingAlg:
    """
    Bias subtraction calculation.

    This module defines 'BiasSubtraction' and methods to perform bias subtraction by subtracting a master bias frame from the raw data frame.  
    
    Attributes:
        rawimage (np.ndarray): From parameter 'rawimage'.
        ffi_exts (list): From parameter 'ffi_exts'.
        quicklook (bool): From parameter 'quicklook'.
        data_type (str): From parameter 'data_type'.
        config (configparser.ConfigParser, optional): From parameter 'config'.
        logger (logging.Logger, optional): From parameter 'logger'.
    
    Raises:
        Exception: If raw image and bias frame don't have the same dimensions.
    """

    def __init__(self,rawimage,ffi_exts,quicklook,data_type,config=None,logger=None):
        """Inits BiasSubtraction class with raw data, config, logger.

        Args:
            rawimage (np.ndarray): The FITS raw data.
            ffi_exts (list): The extensions in L0 FITS files where FFIs (full frame images) are stored.
            quicklook (bool): If true, quicklook pipeline version of bias subtraction is run, outputting information and plots.
            data_type (str): Instrument name, currently choice between KPF and NEID.
            config (configparser.ConfigParser, optional): Config context. Defaults to None.
            logger (logging.Logger, optional): Instance of logging.Logger. Defaults to None.
        """
        self.rawimage=rawimage
        self.ffi_exts=ffi_exts
        self.quicklook=quicklook
        self.data_type=data_type
        self.config=config
        self.logger=logger
        
    def bias_subtraction(self,masterbias):
        """Subtracts bias data from raw data.
        In pipeline terms: inputs two L0 files, produces one L0 file. 

        Args:
            masterbias (FITS File): The master bias data.
        """
        # if self.quicklook == False:
        for ffi in self.ffi_exts:
            # sub_init = FrameSubtract(self.rawimage,masterbias,self.ffi_exts,'bias')
            # subbed_raw_file = sub_init.subtraction()
            self.rawimage[ffi] = self.rawimage[ffi] - masterbias[ffi]
            #self.rawimage[ffi] = subbed_raw_file[ffi]
        
        # if self.quicklook == False: 
        #     if self.data_type == 'KPF':
        #         for ffi in self.ffi_exts:
        #             print(self.rawimage.info)
        #             print(masterbias.info())
        #             assert self.rawimage[ffi].shape==masterbias[ffi].shape, "Bias .fits Dimensions NOT Equal! Check failed"
        #             #self.rawimage[ffi].data=self.rawimage[ffi].data-masterbias[ffi].data
        #             minus_bias = self.rawimage[ffi]-masterbias[ffi]
        #             self.rawimage[ffi] = minus_bias
    
    def dark_subtraction(self,dark_frame):
        """Performs dark frame subtraction. 
        In pipeline terms: inputs two L0 files, produces one L0 file. 

        Args:
            dark_frame (FITS File): L0 FITS file object

        """
        
        for ffi in self.ffi_exts:
            # assert self.rawimage[ffi].data.shape==dark_frame[ffi].data.shape, "Dark frame dimensions don't match raw image. Check failed."
            assert self.rawimage.header['PRIMARY']['EXPTIME'] == dark_frame.header['PRIMARY']['EXPTIME'], "Dark frame and raw image don't match in exposure time. Check failed."
            #minus_dark = self.rawimage[ffi]-dark_frame[ffi]
            # sub_init = FrameSubtract(self.raw_image,dark_frame,self.ffi_exts,'dark')
            # subbed_raw_file = sub_init.subtraction()
            self.rawimage[ffi] = self.rawimage[ffi] - dark_frame[ffi]
            
    def get(self):
        """Returns bias-corrected raw image result.

        Returns:
            self.rawimage: The bias-corrected data.
        """
        return self.rawimage
            
#quicklook TODO: raise flag when counts are significantly diff from master bias, identify bad pixels
        