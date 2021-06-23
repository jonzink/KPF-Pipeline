from kpfpipe.models.level0 import KPF0
from keckdrpframework.models.arguments import Arguments

class FlatFieldingAlg:
    """
    Flat division calculation.

    This module defines 'FlatFielding' and methods to perform flat-fielding by dividing a raw data frame by a master
    flat frame.

    Args:
        rawimage (np.ndarray): The FITS raw data.
        config (configparser.ConfigParser): Config context.
        logger (logging.Logger): Instance of logging.Logger.
    
    Attributes:
        rawimage (np.ndarray): From parameter 'rawimage'.
    
    Raises:
        Exception: If raw image and flat frame don't have the same dimensions
    """

    def __init__(self, rawimage, ffi_exts, config=None, logger=None):
        """
        Inits FlatFielding class with raw data, config, logger.

        Args:
            rawimage (np.ndarray): The FITS raw data.
            ffi_exts (np.ndarray): The extensions in L0 FITS files where FFIs (full frame images) are stored. 
            config (configparser.ConfigParser, optional): Config context. Defaults to None.
            logger (logging.Lobber, optional): Instance of logging.Logger. Defaults to None.
        """
        self.rawimage=rawimage
        self.ffi_exts=ffi_exts
        self.config=config
        self.logger=logger

    def flat_fielding(self,masterflat):
        """
            Divides L0 data by master flat.
            In pipeline terms: inputs two L0 files, outputs one L0 file. 

        Args:
            masterflat (np.ndarray): The FITS master flat data.

        Raises:
            Exception: If raw image and flat frame don't have the same dimensions.
        """
        for no,ffi in enumerate(self.ffi_exts):
            if self.rawimage[ffi].data.shape==masterflat[no+1].data.shape:
                print ("Flat .fits Dimensions Equal, Check Passed")
            else:
                raise Exception ("Flat .fits Dimensions NOT Equal! Check Failed")
    
            self.rawimage[ffi].data=self.rawimage[ffi].data/self.masterflat[no+1].data
            #ext no+1 for mflat because there is a primary ext coded into the masterflat currently
            
    def get(self):
        """Returns flat-corrected raw image result.

        Returns:
            self.rawimage: The flat-corrected data.
        """
        return self.rawimage
    