# An example pipeline that is used to test the template fitting 
# algorithm module. 
import os
import sys
import importlib
import configparser as cp
import logging
import glob
from dotenv.main import load_dotenv

from kpfpipe.logger import start_logger

# AST recipe support
import ast
from kpfpipe.pipelines.kpf_parse_ast import KpfPipelineNodeVisitor
import kpfpipe.config.pipeline_config as cfg

# KeckDRPFramework dependencies
from keckdrpframework.pipelines.base_pipeline import BasePipeline
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.action import Action
from keckdrpframework.models.processing_context import ProcessingContext


class KPFPipeline(BasePipeline):
    """
    Pipeline to Process KPF data using the KeckDRPFramework
    
    Args:
        context (ProcessingContext): context class provided by the framework
    
    Attributes:
        event_table (dictionary): table of actions known to framework. All primitives must be registered here.
    
    Note: 
        The correct operation of the recipe visitor depends on action.args being KpfArguments, which
        is an extension (class derived from) the Keck DRPF Arguments class.  All pipeline primitives must use
        KpfArguments rather than simply Arguments for their return values.  They will also get input arguments
        packaged as KpfArguments. 
    """

    # Modification: 
    name = 'KPF-Pipe'
    event_table = {
        # action_name: (name_of_callable, current_state, next_event_name)
        'start_recipe': ('start_recipe', 'starting recipe', None), 
        'resume_recipe': ('resume_recipe', 'resuming recipe', None),
        'to_fits': ('to_fits', 'processing', 'resume_recipe'),
        'kpf0_from_fits': ('kpf0_from_fits', 'processing', 'resume_recipe'),
        'kpf1_from_fits': ('kpf1_from_fits', 'processing', 'resume_recipe'),
        'kpf2_from_fits': ('kpf2_from_fits', 'processing', 'resume_recipe'),
        'exit': ('exit_loop', 'exiting...', None)
        }
    

    def __init__(self, context: ProcessingContext):
        BasePipeline.__init__(self, context)
        load_dotenv()
    
    def _register_recipe_builtins(self):
        """ register some built-in functions for the recipe to use """
        self._recipe_visitor.register_builtin('int', int, 1)
        self._recipe_visitor.register_builtin('float', float, 1)
        self._recipe_visitor.register_builtin('str', str, 1)
        self._recipe_visitor.register_builtin('len', len, 1)
        self._recipe_visitor.register_builtin('find_files', glob.glob, 1)
        self._recipe_visitor.register_builtin('split', os.path.split, 1)
        self._recipe_visitor.register_builtin('splitext', os.path.splitext, 1)
        self._recipe_visitor.register_builtin('dirname', os.path.dirname, 1)

    def _preload_env(self):
        """ preload environment variables using dotenv """
        """
        env_values = dotenv_values()
        for key in env_values:
            self.context.logger.debug(f"_preload_env: {key} <- {env_values.get(key)}")
            self._recipe_visitor.load_env_value(key, env_values.get(key))
        """
        for key in os.environ:
            self.context.logger.debug(f"_preload_env: {key} <- {os.environ.get(key)}")
            self._recipe_visitor.load_env_value(key, os.environ.get(key))

    def start(self, configfile: str) -> None:
        '''
        Initialize the customized pipeline.
        Customized in that it sets up logger and configurations differently 
        from how the BasePipeline does.

        Args: 
            config (ConfigParser): containing pipeline configuration
        '''
        ## setup pipeline configuration 
        # Technically the pipeline's configuration is stored in self.context as 
        # a ConfigClass() defined by keckDRP. But we will be using configParser

        self.logger = start_logger(self.name, configfile)
        self.logger.info('Logger started')

        ## Setup argument
        try: 
            self.config = cfg.ConfigClass()
            self.config.read(configfile)
            arg = self.config._sections['ARGUMENT']
        except KeyError:
            raise IOError('cannot find [ARGUMENT] section in config')
        self.context.arg = arg

        ## Setup primitive-specific configs:
        self.context.config_path = self.config._sections['MODULES']
        self.logger.info('Finished initializing Pipeline')

    def start_recipe(self, action, context):
        """
        Starts evaluating the recipe file (Python syntax) specified in context.config.run.recipe.
        All actions are executed consecutively in the high priority queue

        Args:
            action (keckdrpframework.models.action.Action): Keck DRPF Action object
            context (keckdrpframework.models.ProcessingContext.ProcessingContext): Keck DRPF ProcessingContext object
        """
        recipe_file = action.args.recipe
        with open(recipe_file) as f:
            fstr = f.read()
            self._recipe_ast = ast.parse(fstr)
        self._recipe_visitor = KpfPipelineNodeVisitor(pipeline=self, context=context)
        self._register_recipe_builtins()
        ## set up environment
        try:
            self._preload_env()
        except Exception as e:
            self.logger.error(f"KPF-Pipeline couldn't load environment due to exception {e}")
        
        self._recipe_visitor.visit(self._recipe_ast)
        return Arguments(name="start_recipe_return")

    def exit_loop(self, action, context):
        """
        Force the Keck DRP Framework to exit the infinite loop

        Args:
            action (keckdrpframework.models.action.Action): Keck DRPF Action object
            context (keckdrpframework.models.ProcessingContext.ProcessingContext): Keck DRPF ProcessingContext object
        """
        self.logger.info("exiting pipeline...")
        # os._exit(0)

    # reentry after call

    def resume_recipe(self, action: Action, context: ProcessingContext):
        """
        Continues evaluating the recipe started in start_recipe().

        Args:
            action (keckdrpframework.models.action.Action): Keck DRPF Action object
            context (keckdrpframework.models.ProcessingContext.ProcessingContext): Keck DRPF ProcessingContext object
        """
        # pick up the recipe processing where we left off
        self.logger.debug("resume_recipe")
        self._recipe_visitor.returning_from_call = True
        self._recipe_visitor.awaiting_call_return = False
        self._recipe_visitor.call_output = action.args # framework put previous output here
        self._recipe_visitor.visit(self._recipe_ast)
        return Arguments(name="resume_recipe_return")  # nothing to actually return, but meet the Framework requirement
