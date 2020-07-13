# Standard dependencies 
import configparser
import pandas as pd
import copy
import numpy as np

# Pipeline dependencies
from kpfpipe.logger import start_logger
from kpfpipe.primitives.level0 import KPF0_Primitive
from kpfpipe.models.level0 import KPF0

# External dependencies
from keckdrpframework.models.action import Action
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.processing_context import ProcessingContext

# Local dependencies
from modules.order_trace.src.alg import OrderTraceAlg

# Global read-only variables
DEFAULT_CFG_PATH = 'modules/order_trace/configs/default.cfg'

class OrderTrace(KPF0_Primitive):

    def __init__(self, 
                 action: Action,
                 context: ProcessingContext) -> None:
        '''
        Example KPF module
        '''
        # Initialize parent class
        KPF0_Primitive.__init__(self, action, context)

        # input argument 
        self.input = action.args[0]
        self.flat_data = self.input.data
        # input configuration
        self.config = configparser.ConfigParser()
        try:
            self.config_path = context.config_path['order_trace']
        except:
            self.config_path = DEFAULT_CFG_PATH
        self.config.read(self.config_path)

        # start a logger
        self.logger = start_logger(self.__class__.__name__, self.config_path)
        if not self.logger:
            self.logger = self.context.logger
        self.logger.info('Loading config from: {}'.format(self.config_path))

        # Order trace algorithm setup 
        self.alg = OrderTraceAlg(self.flat_data, config=self.config, logger=self.logger)


    def _pre_condition(self) -> bool:
        '''
        Check for some necessary pre conditions
        '''
        # input argument must be KPF0
        success = isinstance(self.input, KPF0) and \
            isinstance(self.input.data, np.ndarray)

        return success

    def _post_condition(self) -> bool:
        '''
        check for some necessary post condition
        '''
        return True

    def _perform(self) -> None:
        """
        This primitive's action
        """
        # 1) Locate cluster
        if self.logger:
            self.logger.info("OrderTrace: locating cluster...")
        cluster_xy = self.alg.locate_clusters()

        # 2) assign cluster id and do basic cleaning
        if self.logger:
            self.logger.info("OrderTrace: assigning cluster id and cleaning...")
        x, y, index = self.alg.form_clusters(cluster_xy['x'], cluster_xy['y'])

        power = self.alg.get_poly_degree()
        # 3) advanced cleaning and border cleaning
        if self.logger:
            self.logger.info("OrderTrace: advanced cleaning...")
        new_x, new_y, new_index, all_status = self.alg.advanced_cluster_cleaning_handler(index, x, y)
        new_x, new_y, new_index = self.alg.clean_clusters_on_borders(new_x, new_y, new_index)

        # 5) Merge cluster
        if self.logger:
            self.logger.info("OrderTrace: merging cluster...")
        c_x, c_y, c_index = self.alg.merge_clusters_and_clean(new_index, new_x, new_y)

        # 6) Find width
        if self.logger:
            self.logger.info("OrderTrace: finding width...")
        all_widths, cluster_coeffs = self.alg.find_all_cluster_widths(c_index, c_x, c_y, power_for_width_estimation=3)

        if self.logger:
            self.logger.info("OrderTrace: writing cluster into dataframe...")
        df = self.alg.write_cluster_info_to_dataframe(all_widths, cluster_coeffs)
        assert(isinstance(df, pd.DataFrame))
        
        self.input.create_extension('ORDER TRACE RESULT')
        self.input.extension['ORDER TRACE RESULT'] = df

        self.input.header['ORDER TRACE RESULT']['POLY DEGREE'] = self.alg.get_poly_degree()

        self.input.receipt_add_entry('OrderTrace', f'config_path={self.config_path}', 'PASS')
        if self.logger:
            self.logger.info("OrderTrace: Receipt written")

        if self.logger:
            self.logger.info("OrderTrace: Done!")

        return Arguments(self.input)
