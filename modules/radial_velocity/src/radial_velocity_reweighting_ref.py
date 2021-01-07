# Standard dependencies
"""
    This module defines class `RadialVelocityReweightingRef` which inherits from `KPF_Primitive` and provides
    methods to perform the event on radial velocity reweighting ratio table creation in the recipe.

    Attributes:
        RadialVelocityReweightingRef

    Description:
        * Method `__init__`:

            RadialVelocityReweightingRef constructor, the following arguments are passed to `__init__`,

                - `action (keckdrpframework.models.action.Action)`: `action.args` contains positional arguments and
                  keyword arguments passed by the `RadialVelocityReweightingRef` event issued in the recipe:

                    - `action.args[0] (list|str)`: List of files (or numpy.ndarray) or one single file for reweighting.
                    - `action.args[1] (str)`: Reweighting method.
                    - `action.args[2] (int)`: Total order from the ccf data to build the reweighting template.
                    - `action.args['ccf_hdu_index'] (int)`: The HDU index in fits file for the HDU with ccf data.
                      Defaults to 12.
                    - `action.args['ccf_start_index'] (int)`: The order index that the first row of ccf_data is
                      associated with. Defaults to 0.
                    - `action.args['is_ratio_data'] (boolean)`: If the file is a csv file containing the ratio for
                      reweighting ccf orders. Defaults to False.

                - `context (keckdrpframework.models.processing_context.ProcessingContext)`: `context.config_path`
                  contains the path of the config file defined for the module of radial velocity in the master
                  config file associated with the recipe.

            and the following attributes are defined to initialize the object,

                - `files (List)`: list of files to find the reference template for rewighting.
                - `reweighting_method (str)`: Reweighting method.
                - `total_order (int)`: Total order to build the reweighting reference.
                - `ccf_hdu_index (int)`: hdu index for ccf.
                - `ccf_start_index (int)`: The order index that the first row of ccf_data is associated with.
                - `config_path (str)`: Path of config file for radial velocity.
                - `config (configparser.ConfigParser)`: Config context.
                - `logger (logging.Logger)`: Instance of logging.Logger.

        * Method `__perform`:

            RadialVelocityReweightingRef returns the result in `Arguments` object containing an instance of
            numpy.ndarray as for the reweighting reference and the ratio result is written into a file in csv
            format if `ccf_ratio_file` is set in the action arguments.

         * Note:
            The event input tentatively uses ccf data in the format of KPF1 object. It will be refactored into KPF2
            style when level2 data model is implemented.

    Usage:
        For the recipe, the make reweighting ratio table is issued like::

            :
            reweighting_ref =  RadialVelocityReweightingRef(list_files, 'ccf_max', 116, ccf_hdu_index=12,
                                ccf_start_index=0, ccf_ratio_file=<file path>)
            :
"""

import configparser
import numpy as np
from astropy.io import fits
import os.path
import pandas as pd

# Pipeline dependencies
from kpfpipe.primitives.core import KPF_Primitive

# External dependencies
from keckdrpframework.models.action import Action
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.processing_context import ProcessingContext

from modules.radial_velocity.src.alg import RadialVelocityAlg

DEFAULT_CFG_PATH = 'modules/radial_velocity/configs/default.cfg'


class RadialVelocityReweightingRef(KPF_Primitive):
    def __init__(self,
                 action: Action,
                 context: ProcessingContext) -> None:
        # Initialize parent class
        KPF_Primitive.__init__(self, action, context)
        args_keys = [item for item in action.args.iter_kw() if item != "name"]

        self.files = []
        if isinstance(action.args[0], str):
            self.files.append(action.args[0])
        elif isinstance(action.args[0], list):
            self.files.extend(action.args[0])

        self.reweighting_method = action.args[1]
        self.total_order = action.args[2]
        self.ccf_hdu_index = action.args['ccf_hdu_index'] if 'ccf_hdu_index' in args_keys else 12
        self.ccf_start_index = action.args['ccf_start_index'] if 'ccf_start_index' in args_keys else 0
        self.is_ratio_data = action.args['is_ratio_data'] if 'is_ratio_data' in args_keys else False
        self.ccf_ratio_file = action.args['ccf_ratio_file'] if 'ccf_ratio_file' in args_keys else ''

        # input configuration
        self.config = configparser.ConfigParser()
        try:
            self.config_path = context.config_path['radial_velocity']
        except:
            self.config_path = DEFAULT_CFG_PATH

        self.config.read(self.config_path)

        # start a logger
        self.logger = None
        # self.logger = start_logger(self.__class__.__name__, self.config_path)
        if not self.logger:
            self.logger = self.context.logger
        self.logger.info('Loading config from: {}'.format(self.config_path))

    def _pre_condition(self) -> bool:
        """
        Check for some necessary pre conditions
        """
        # input argument must be KPF0
        success = isinstance(self.files, list) and len(self.files) > 0 and \
                  (self.reweighting_method in ['ccf_max', 'ccf_mean', 'ccf_steps'])

        return success

    def _post_condition(self) -> bool:
        """
        check for some necessary post condition
        """
        return True

    def _perform(self):
        """
        Primitive action - find radial velocity rewighting reference

        Returns:
            pandas.DataFrame as a reweighting ratio table or a ccf reference from observation template
        """

        def get_template_observation(f, hdu_index, msg, is_ratio=False):
            r_ccf = None
            if isinstance(f, str):
                if msg:
                    assert(os.path.exists(f), msg+':' + f + " doesn't exist")
                else:
                    assert(os.path.exists(f))
                if is_ratio:
                    ratio_pd = pd.read_csv(f)
                    r_ccf = ratio_pd.values
                else:
                    hdu_list = fits.open(f)
                    ccf_data = hdu_list[hdu_index].data
                    r_ccf = pd.DataFrame(ccf_data).values if isinstance(ccf_data, fits.fitsrec.FITS_rec) else ccf_data
            else:
                r_ccf = pd.DataFrame(f).valuse if isinstance(f, fits.fitsrec.FITS_rec) else f

            if msg:
                assert(r_ccf is not None,  msg)
            else:
                assert(r_ccf is not None)
            return r_ccf

        ccf_ref = None
        if self.reweighting_method == 'ccf_steps':
            ccf_ref = get_template_observation(self.files[0], self.ccf_hdu_index,
                                               'template observation error')

        elif self.is_ratio_data:                    # get ratio from a csv file directly or 2d array
            ccf_ref = get_template_observation(self.files[0], self.ccf_hdu_index,
                                               "ratio table from template error", is_ratio=True)
        else:
            m_file = []
            m_ccf_ref = []

            # assume the first row of ccf data from each file is for order of self.ccf_start_idx
            # and in total min(self.total_order, total rows of ccf data) are selected for making the ratio table

            for i in range(len(self.files)):
                ccf_file = self.files[i]
                ccf_ref = get_template_observation(ccf_file, self.ccf_hdu_index, "observation with ccf error")
                m_ccf_ref.append(ccf_ref)

                t_order = min(np.shape(ccf_ref)[0], self.total_order)
                if self.reweighting_method == 'ccf_max':
                    m_file.append(np.max([np.nanpercentile(ccf_ref[od, :], 95) for od in range(t_order)]))
                elif self.reweighting_method == 'ccf_mean':
                    m_file.append(np.max([np.nanmean(ccf_ref[od, :]) for od in range(t_order)]))

            # find the maximum among all files and get the ccf data of the file with the maximum ccf
            tmp_idx = np.where(m_file == np.nanmax(m_file))[0]
            ccf_ref = m_ccf_ref[tmp_idx[0]]
            t_order = min(np.shape(ccf_ref)[0], self.total_order)

            ccf_df = RadialVelocityAlg.make_reweighting_ratio_table(ccf_ref, self.ccf_start_index,
                                                                    self.ccf_start_index + t_order - 1,
                                                                    self.reweighting_method, max_ratio = 1.0,
                                                                    output_csv=self.ccf_ratio_file)

            ccf_ref = ccf_df.values

        if self.logger:
            self.logger.info("RadialVelocityReweightingRef: done")

        return Arguments(ccf_ref)


