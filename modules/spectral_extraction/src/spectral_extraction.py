# Standard dependencies
"""
    This module defines class SpectralExtraction which inherits from `KPF0_Primitive` and provides methods to perform
    the event on spectral extraction in the recipe.

    Attributes:
        SpectralExtraction

    Description:
        * Method `__init__`:

            SpectralExtraction constructor, the following arguments are passed to `__init__`,

                - `action (keckdrpframework.models.action.Action)`: `action.args` contains positional arguments and
                  keyword arguments passed by the `SpectralExtraction` event issued in the recipe:

                    - `action.args[0] (kpfpipe.models.level0.KPF0)`: Instance of `KPF0` containing spectrum data for
                      spectral extraction.
                    - `action.args[1] (kpfpipe.models.level0.KPF0)`: Instance of `KPF0` containing flat data and order
                      trace result.
                    - `action.args[2] (kpfpipe.models.level1.KPF1)`:  Instance of `KPF1` containing spectral
                      extraction results. If not existing, it is None.
                    - `action.args['order_name'] (str|list, optional)`: Name or list of names of the order to be
                      processed. Defaults to 'SCI1'.
                    - `action.args['start_order'] (int, optional)`: Index of the first order to be processed.
                      Defaults to 0.
                    - `action.args['max_result_order']: (int, optional)`: Total orders to be processed, Defaults to -1.
                    - `action.args['rectification_method']: (str, optional)`: Rectification method, '`norect`',
                      '`vertial`', or '`normal`', to rectify the curved order trace. Defaults to '`norect`',
                      meaning no rectification.
                    - `action.args['extraction_method']: (str, optional)`: Extraction method, '`sum`',
                      or '`optimal`', to extract and reducethe curved order trace, and 'rectonly' to rectify the curve
                      with no reduction. Defaults to '`optimal`', meaning optimal extraction which produces 1-D flux
                      for each order trace based on the spectrum
                      data and its variance and the weighting based on the flat data instead of doing summation on
                      the spectrum data directly.
                    - `action.args['clip_file'] (str, optional)`:  Prefix of clip file path. Defaults to None.
                      Clip file is used to store the polygon clip data for the rectification method
                      which is not NoRECT.
                    - `action.args['wavecal_fits']: (str|KPF1 optional)`: Path of the fits file or `KPF1` instance
                      containing wavelength calibration data. Defaults to None.
                    - `action.args['to_set_wavelength_cal']: (boolean, optional)`: if setting the wavelength calibration
                      values from ``action.args['wavecal_fits']``. Defaults to False.

                - `context (keckdrpframework.models.processing_context.ProcessingContext)`: `context.config_path`
                  contains the path of the config file defined for the module of spectral extraction in the master
                  config file associated with the recipe.

            and the following attributes are defined to initialize the object,

                - `input_spectrum (kpfpipe.models.level0.KPF0)`: Instance of `KPF0`, assigned by `actions.args[0]`.
                - `input_flat (kpfpipe.models.level0.KPF0)`:  Instance of `KPF0`, assigned by `actions.args[1]`.
                - `output_level1 (kpfpipe.models.level1.KPF1)`: Instance of `KPF1`, assigned by `actions.args[2]`.
                - `order_name (str)`: Name of the order to be processed.
                - `start_order (int)`: Index of the first order to be processed.
                - `max_result_order (int)`: Total orders to be processed.
                - `rectification_method (int)`: Rectification method code as defined in `SpectralExtractionAlg`.
                - `extraction_method (str)`: Extraction method code as defined in `SpectralExtractionAlg`.
                - `wavecal_fits (str)`: Path of the fits file or `KPF1` instance with wavelength calibration data.
                - `to_set_wavelength_cal`: Flag indicates if setting wavelength calibration data to wavelength
                  calibration extension from ``wavecal_fits``.
                - `config_path (str)`: Path of config file for spectral extraction.
                - `config (configparser.ConfigParser)`: Config context.
                - `logger (logging.Logger)`: Instance of logging.Logger.
                - `alg (modules.order_trace.src.alg.SpectralExtractionAlg)`: Instance of `SpectralExtractionAlg` which
                  has operation codes for the computation of spectral extraction.


        * Method `__perform`:

            SpectralExtraction returns the result in `Arguments` object which contains a level 1 data object (`KPF1`)
            with the spectral extraction results and the wavelength data tentatively transported from
            `action.args['wavecal_fits']` if there is.

    Usage:
        For the recipe, the spectral extraction event is issued like::

            :
            lev0_data = kpf0_from_fits(input_lev0_file, data_type=data_type)
            op_data = SpectralExtraction(lev0_data, lev0_flat_data,
                                        None, order_name=order_name,
                                        rectification_method=rect_method,
                                        wavecal_fits=input_lev1_file)
            :
"""


import configparser
import pandas as pd
import numpy as np

# Pipeline dependencies
# from kpfpipe.logger import start_logger
from kpfpipe.primitives.level0 import KPF0_Primitive
from kpfpipe.models.level0 import KPF0
from kpfpipe.models.level1 import KPF1

# External dependencies
from keckdrpframework.models.action import Action
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.processing_context import ProcessingContext

# Local dependencies
from modules.spectral_extraction.src.alg import SpectralExtractionAlg

# Global read-only variables
DEFAULT_CFG_PATH = 'modules/spectral_extraction/configs/default.cfg'


class SpectralExtraction(KPF0_Primitive):
    default_args_val = {
                    'order_name': 'SCI',
                    'max_result_order': -1,
                    'start_order': 0,
                    'rectification_method': 'norect',  # 'norect', 'normal', 'vertical'
                    'extraction_method': 'optimal',
                    'wavecal_fits': None,
                    'to_set_wavelength_cal': False,
                    'clip_file': None,
                    'data_extension': 'DATA',
                    'poly_degree': 3,
                    'origin': [0, 0],
                    'trace_extension': None,
                    'trace_file': None
                }

    NORMAL = 0
    VERTICAL = 1
    NoRECT = 2

    def __init__(self,
                 action: Action,
                 context: ProcessingContext) -> None:

        # Initialize parent class
        KPF0_Primitive.__init__(self, action, context)

        args_keys = [item for item in action.args.iter_kw() if item != "name"]

        # input argument
        # action.args[0] is for level 0 fits
        # action.args[1] is for level 0 flat with order trace result extension
        self.input_spectrum = action.args[0]  # kpf0 instance
        self.input_flat = action.args[1]      # kpf0 instance with flat data
        self.output_level1 = action.args[2]   # kpf1 instance already exist or None
        self.orderlet_names = self.get_args_value('orderlet_names', action.args, args_keys)
        self.max_result_order = self.get_args_value("max_result_order", action.args, args_keys)
        self.start_order = self.get_args_value("start_order", action.args, args_keys)  # for the result of order trace
        self.rectification_method = self.get_args_value("rectification_method", action.args, args_keys)
        self.extraction_method = self.get_args_value('extraction_method', action.args, args_keys)
        self.wavecal_fits = self.get_args_value('wavecal_fits', action.args, args_keys) # providing wavelength calib.
        self.to_set_wavelength_cal = self.get_args_value('to_set_wavelength_cal', action.args, args_keys) # set wave cal
        self.clip_file = self.get_args_value('clip_file', action.args, args_keys)

        data_ext = self.get_args_value('data_extension', action.args, args_keys)
        order_trace_ext = self.get_args_value('trace_extension', action.args, args_keys)
        order_trace_file = self.get_args_value('trace_file', action.args, args_keys)

        # input configuration
        self.config = configparser.ConfigParser()
        try:
            self.config_path = context.config_path['spectral_extraction']
        except:
            self.config_path = DEFAULT_CFG_PATH
        self.config.read(self.config_path)

        # start a logger
        self.logger = None
        if not self.logger:
            self.logger = self.context.logger
        self.logger.info('Loading config from: {}'.format(self.config_path))

        self.order_trace_data = None
        if order_trace_file:
            self.order_trace_data = pd.read_csv(order_trace_file, header=0, index_col=0)
            poly_degree = self.get_args_value('poly_degree', action.args, args_keys)
            origin = self.get_args_value('origin', action.args, args_keys)
            order_trace_header = {'STARTCOL': origin[0], 'STARTROW': origin[1], 'POLY_DEG': poly_degree}
        elif order_trace_ext:
            self.order_trace_data = self.input_flat[order_trace_ext]
            order_trace_header = self.input_flat.header[order_trace_ext]

        # Order trace algorithm setup
        spec_header = self.input_spectrum.header[data_ext] \
            if (self.input_spectrum is not None and hasattr(self.input_spectrum, data_ext)) else None
        self.alg = SpectralExtractionAlg(self.input_flat[data_ext] if hasattr(self.input_flat, data_ext) else None,
                                        self.input_flat.header[data_ext] if hasattr(self.input_flat, data_ext) else None,
                                        self.input_spectrum[data_ext] if hasattr(self.input_spectrum, data_ext) else None,
                                        spec_header,
                                        self.order_trace_data,
                                        order_trace_header,
                                        config=self.config, logger=self.logger,
                                        rectification_method=self.rectification_method,
                                        extraction_method=self.extraction_method,
                                        clip_file=self.clip_file)

    def _pre_condition(self) -> bool:
        """
        Check for some necessary pre conditions
        """
        # input argument must be KPF0
        success = isinstance(self.input_flat, KPF0) and isinstance(self.input_spectrum, KPF0) and \
                  (self.order_trace_data is not None)

        return success

    def _post_condition(self) -> bool:
        """
        Check for some necessary post conditions
        """
        return True

    def _perform(self):
        """
        Primitive action -
        perform spectral extraction by calling method `extract_spectrum` from SpectralExtractionAlg and create an instance
        of level 1 data (KPF1) to contain the analysis result.

        Returns:
            Level 1 data containing spectral extraction result.

        """
        # rectification_method: SpectralExtractAlg.NoRECT(fastest) SpectralExtractAlg.VERTICAL, SpectralExtractAlg.NORMAL
        # extraction_method: 'optimal' (default), 'sum'

        if self.logger:
            self.logger.info("SpectralExtraction: rectifying and extracting order...")

        ins = self.alg.get_instrument().upper()

        kpf1_sample = None
        kpf0_sample = None
        if self.wavecal_fits is not None:     # get the header and wavecal from this fits
            if isinstance(self.wavecal_fits, str):
                kpf1_sample = KPF1.from_fits(self.wavecal_fits, ins)
            elif isinstance(self.wavecal_fits, KPF1):
                kpf1_sample = self.wavecal_fits
            elif isinstance(self.wavecal_fits, KPF0):
                kpf0_sample = self.wavecal_fits

        all_order_names = self.orderlet_names if type(self.orderlet_names) is list else [self.orderlet_names]

        all_o_sets = []
        s_order = self.start_order if self.start_order is not None else 0

        for order_name in all_order_names:
            o_set = self.alg.get_order_set(order_name)
            if o_set.size > 0:
                o_set = self.get_order_set(o_set, s_order)
            all_o_sets.append(o_set)

        order_to_process = min([len(a_set) for a_set in all_o_sets])

        for idx, order_name in enumerate(all_order_names):
            o_set = all_o_sets[idx][0:order_to_process]
            opt_ext_result = self.alg.extract_spectrum(order_set=o_set)

            assert('spectral_extraction_result' in opt_ext_result and
                   isinstance(opt_ext_result['spectral_extraction_result'], pd.DataFrame))

            data_df = opt_ext_result['spectral_extraction_result']
            self.output_level1 = self.construct_level1_data(data_df, ins, kpf1_sample,
                                                            order_name, self.output_level1)
            self.add_wavecal_to_level1_data(self.output_level1, order_name, kpf1_sample, kpf0_sample)

        if self.output_level1 is not None:
            self.output_level1.receipt_add_entry('SpectralExtraction', self.__module__,
                                                 f'orderlettes={" ".join(all_order_names)}', 'PASS')
        if self.logger:
            self.logger.info("SpectralExtraction: Receipt written")

        if self.logger:
            self.logger.info("SpectralExtraction: Done for orders " + " ".join(all_order_names) + "!")

        return Arguments(self.output_level1)

    def get_order_set(self, o_set, s_order):
        e_order = min(self.max_result_order, len(o_set)) \
            if (self.max_result_order is not None and self.max_result_order > 0) else o_set.size

        o_set_ary = o_set[0:e_order] + s_order

        return o_set_ary[np.where(o_set_ary < self.alg.get_spectrum_order())]

    def construct_level1_data(self, op_result, ins, level1_sample: KPF1, order_name: str, output_level1:KPF1):
        update_primary_header = False if level1_sample is None or ins != 'NEID' else True
        if output_level1 is not None:
            kpf1_obj = output_level1
        else:
            kpf1_obj = KPF1()

        if op_result is not None:
            total_order, width = np.shape(op_result.values)
        else:
            total_order = 0

        def get_data_extensions_on(order_name, ins):
            if ins in ['NEID', 'KPF'] and 'FLUX' in order_name:
                ext_name = [order_name, order_name.replace('FLUX', 'VAR'),
                            order_name.replace('FLUX', 'WAVE')]
            else:
                ext_name = [order_name, order_name.replace('FLUX', 'VAR'),
                            order_name.replace('FLUX', 'WAVE')] if 'FLUX' in order_name else [order_name]
            return ext_name

        # if no data in op_result, not build data extension and the associated header

        if total_order > 0:
            ext_names = get_data_extensions_on(order_name, ins)
            data_ext_name = ext_names[0]

            # data = op_result.values
            kpf1_obj[data_ext_name] = op_result.values

            for att in op_result.attrs:
                kpf1_obj.header[data_ext_name][att] = op_result.attrs[att]

            if len(ext_names) > 1:   # init var and wave extension if there is
                for ext_idx in range(1, 3):
                    if not hasattr(kpf1_obj, ext_names[ext_idx]) or \
                            np.size(getattr(kpf1_obj, ext_names[ext_idx])) == 0:  # no ext name yet or zero size
                        zero_data = np.zeros((total_order, width))
                        kpf1_obj[ext_names[ext_idx]] = zero_data

            # for neid data:
            if update_primary_header and level1_sample is not None and hasattr(kpf1_obj, data_ext_name):
                sample_primary_header = level1_sample.header['PRIMARY']
                if sample_primary_header is not None:
                    for h_key in ['SSBZ100', 'SSBJD100']:
                        kpf1_obj.header[data_ext_name][h_key] = sample_primary_header[h_key]

        return kpf1_obj

    def add_wavecal_to_level1_data(self, level1_obj: KPF1, order_name: str, level1_sample: KPF1, level0_sample: KPF0):
        if level1_sample is None and level0_sample is None:
            return False
        ins = self.alg.get_instrument()

        def get_extension_on(order_name, ext_type):
            if ext_type != 'FLUX':
                ext_name = order_name.replace('FLUX', ext_type) if 'FLUX' in order_name else None
            else:    # temporary setting, need more instrument information
                ext_name = order_name
            return ext_name

        # check if wavelength calibration extension exists in level 1 or level 0 sample
        if level1_sample is not None:
            data_ext_name = get_extension_on(order_name, 'FLUX')
            if (not hasattr(level1_sample, data_ext_name)) or \
               (not hasattr(level1_obj, data_ext_name)):
                return False

        wave_ext_name = get_extension_on(order_name, 'WAVE')
        if wave_ext_name is None:
            return False

        if level1_sample is not None:                  # get header of wavelength cal from level 1 data
            wave_header = level1_sample.header[wave_ext_name]
        else:                                          # get header of wavelength cal. from level 0 data
            wave_header = level0_sample.header['DATA']
            if wave_header is not None:
                wave_header['EXTNAME']= wave_ext_name
        if wave_header is None:
            return False

        level1_obj.header[wave_ext_name] = wave_header   # assign the item or set?

        if not self.to_set_wavelength_cal:  # no data setting
            return True

        if level1_sample is not None:   # assume wavelength calibration data is from level1 sample
            wave_data = getattr(level1_sample, wave_ext_name) if hasattr(level1_sample, wave_ext_name) else None
        else:    # assume wavelength calibration data is in level0 sample, need update ???
            wave_data = getattr(level0_sample, 'DATA') if hasattr(level0_sample, 'DATA') else None

        if wave_data is None:               # data setting error
            return False

        if ins == 'KPF':
            wave_data = wave_data * 1000.0

        wave_start = 0
        wave_end = min(np.shape(wave_data)[0], np.shape(getattr(level1_obj, wave_ext_name))[0])
        wave_arr = getattr(level1_obj, wave_ext_name)
        wave_arr[wave_start:wave_end, :] = wave_data[wave_start:wave_end, :]
        return True

    def get_args_value(self, key: str, args: Arguments, args_keys: list):
        if key in args_keys:
            v = args[key]
        else:
            v = self.default_args_val[key]

        if key == 'rectification_method':
            if v is not None and isinstance(v, str):
                if v.lower() == 'normal':
                    method = SpectralExtractionAlg.NORMAL
                elif v.lower() == 'vertical':
                    method = SpectralExtractionAlg.VERTICAL
                else:
                    method = SpectralExtractionAlg.NoRECT
            else:
                method = SpectralExtractionAlg.NoRECT
        elif key == 'extraction_method':
            if v is not None and isinstance(v, str):
                if 'sum' in v.lower():
                    method = SpectralExtractionAlg.SUM
                else:
                    method = SpectralExtractionAlg.OPTIMAL
            else:
                method = SpectralExtractionAlg.OPTIMAL
        else:
            if key == 'data_extension' or key == 'trace_extension':
                if v is None:
                    v = self.default_args_val[key]

            return v

        return method