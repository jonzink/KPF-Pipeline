# kpf_parse_ast.py

from ast import NodeVisitor, iter_fields, parse
import _ast
from collections.abc import Iterable
from queue import Queue
import os
# from kpfpipe.pipelines.FauxLevel0Primitives import read_data, Normalize, NoiseReduce, Spectrum1D

from keckdrpframework.models.action import Action
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.processing_context import ProcessingContext
import configparser as cp

class RecipeError(Exception):
    """ Special recipe exception """

class KpfPipelineNodeVisitor(NodeVisitor):
    """
    Node visitor to convert KPF pipeline recipes expressed in python syntax
    into operations on the KPF Framework.
    """

    def __init__(self, pipeline=None, context=None):
        NodeVisitor.__init__(self)
        # instantiate the parameters dict
        self._params = None
        # instantiate the environment dict
        self._env = {}
        # store and load stacks
        # (implemented as lists; use append() and pop())
        self._store = list()
        self._load = list()
        # KPF framework items
        self.pipeline = pipeline
        self.context = context
        # local state flags
        self.awaiting_call_return = False
        self.returning_from_call = False
        self._reset_visited_states = False
        # value returned by primitive executed by framework
        self.call_output = None
        self._builtins = {}
        self.subrecipe_depth = 0

    def register_builtin(self, key, func, nargs):
        """
        Register a function so that it can be called from a recipe without using the framework
        Items are tuples (function, number of input args)
        """
        self._builtins[key] = (func, nargs)

    def load_env_value(self, key, value):
        self._env[key] = value
    
    def visit_Module(self, node):
        """
        Module node
        A Module node is always at the top of an AST tree returned
        by ast.parse(), and there is only one, so we initialize
        or reset things here, and clean up (releasing allocated
        memory) at the end.
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_started', False)
            for item in node.body:
                self.visit(item)
            if self.subrecipe_depth == 0:
                self._params = None # let storage get collected
            return
        self.pipeline.logger.info(f"Module: subrecipe_depth = {self.subrecipe_depth}")
        if not getattr(node, 'kpf_started', False):
            if self.subrecipe_depth == 0:
                self._params = {}
            setattr(node, 'kpf_started', True)
        for item in node.body:
            self.visit(item)
            if self.awaiting_call_return:
                return
        if self.subrecipe_depth == 0:
            self._params = None # let allocated memory get collected

    def visit_ImportFrom(self, node):
        """
        import primitives and add them to the pipeline's event_table
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            for name in node.names:
                self.visit(name)
            return
        if not getattr(node, 'kpf_completed', False):
            module = node.module
            # append the module path to the framework's primitive_path
            self.context.config.primitive_path = tuple([*self.context.config.primitive_path, module])
            loadQSizeBefore = len(self._load)
            for name in node.names:
                self.visit(name)
                if len(self._load) > loadQSizeBefore:
                    # import the named primitive
                    # This comes as a 2-element tuple from visit_alias
                    #
                    # just add the name to the event_table for now
                    # But we should ensure that the name exists in the module and is Callable
                    tup = self._load.pop()
                    # create an event_table entry that returns control
                    # to the pipeline after running
                    self.pipeline.event_table[tup[0]] = (tup[0], "Processing", "resume_recipe")
                    self.pipeline.logger.info(f"Added {tup[0]} from {module} to event_table")
            setattr(node, 'kpf_completed', True)

    def visit_alias(self, node):
        """
        alias node
        These only appear in import clauses
        Implement by putting name and asname on _load stack as tuple.
        ImportFrom handles the heavy lifting
        Note: asname is currently not supported and is ignored.
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            return
        if not getattr(node, 'kpf_completed', False):
            self._load.append((node.name, node.asname))
            self.pipeline.logger.debug(f"alias: {node.name} as {node.asname}")
            setattr(node, 'kpf_completed', True)
    
    def visit_Name(self, node):
        """
        Implementation of Name node
        A Name can occur on either the left or right side of an assignment.
        If it's on the left side the context is Store, and the Name is the
        variable name into which to store a value.  We push that variable name
        on the _store stack.
        If the Name is on the right side, e.g. as part of an expression,
        we look up the name in our params dict, and push the corresponding
        value on the _load stack.  If the name is not found, None is pushed
        on the _load stack.

        WARNING: The same instance of a Name can appear as different nodes in a AST,
        so nothing should be stored in the node as a node-specific attribute.
        """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(f"Name: {node.id}")
        if isinstance(node.ctx, _ast.Store):
            self.pipeline.logger.debug(f"Name is storing {node.id}")
            self._store.append(node.id)
        elif isinstance(node.ctx, _ast.Load):
            if node.id == "None":
                value = None
            elif node.id == "config":
                if self.pipeline != None and hasattr(self.pipeline, "config"):
                    value = self.pipeline.config
                else:
                    self.pipeline.logger.error(f"Name: No context or context has no config attribute")
                    raise Exception(f"Name: No context or context has no config attribute")
            elif self._env.get(node.id):
                value = self._env.get(node.id)
            else:
                try:
                    value = self._params[node.id]
                except KeyError:
                    # self.pipeline.logger.error(
                    #     f"Name {node.id} on line {node.lineno} of recipe not defined.")
                    raise RecipeError(
                        f"Name {node.id} on line {node.lineno} of recipe not defined.  Recipe environment: {self._env}.  Python environment: {os.environ}")
            self.pipeline.logger.debug(f"Name is loading {value} from {node.id}")
            self._load.append(value)
        else:
            raise RecipeError(
                f"visit_Name: on recipe line {node.lineno}, ctx is unexpected type: {type(node.ctx)}")
    
    def visit_For(self, node):
        """
        Implement the For node

        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            setattr(node, 'kpf_started', False)
            if hasattr(node, 'kpf_params'):
                delattr(node, 'kpf_params')
            self.visit(node.target)
            self.visit(node.iter)
            for subnode in node.body:
                self.visit(subnode)
            return
            
        if not getattr(node, 'kpf_completed', False):
            if not getattr(node, 'kpf_started', False):
                params = {}
                storeQSizeBefore = len(self._store)
                self.visit(node.target)
                if self.awaiting_call_return:
                    return
                if len(self._store) > storeQSizeBefore:
                    target = self._store.pop()
                    params['target'] = target             
                loadQSizeBefore = len(self._load)
                self.visit(node.iter)
                args = []
                if len(self._load) - loadQSizeBefore == 1:
                    item = self._load.pop()
                    if isinstance(item, Iterable):
                        self.pipeline.logger.debug(f"For: Popping first list item, {item}, of type {type(item)}")
                        args = item
                    else:
                        args.insert(0, item)
                while len(self._load) > loadQSizeBefore:
                    # pick up any additional items
                    item = self._load.pop()
                    self.pipeline.logger.debug(f"For: next list item is {item} of type {type(item)}")
                    args.insert(0, item)
                args_iter = iter(list(args))
                try:
                    current_arg = next(args_iter)
                    self.pipeline.logger.debug(f"For: first call to next returned {current_arg} of type {type(current_arg)}")
                except StopIteration:
                    current_arg = None
                params['args_iter'] = args_iter
                params['current_arg'] = current_arg
                setattr(node, 'kpf_params', params)
                setattr(node, 'kpf_started', True)
            else:
                params = getattr(node, 'kpf_params', None)
                assert(params is not None)
                target = params.get('target')
                args_iter = params.get('args_iter')
                current_arg = params.get('current_arg')
            while current_arg is not None:
                self.pipeline.logger.debug(f"For: in while loop with current_arg {current_arg}, type {type(current_arg)}")
                self._params[target] = current_arg
                for subnode in node.body:
                    self.visit(subnode)
                    if self.awaiting_call_return:
                        return
                # reset the node visited states for all nodes
                # underneath this "for" loop to set up for the
                # next iteration of the loop.
                self.pipeline.logger.debug("For: resetting visited states before looping")
                for subnode in node.body:
                    self.reset_visited_states(subnode)
                # iterate by updating current_arg (and the arg iterator)
                try:
                    current_arg = next(args_iter)
                    params['current_arg'] = current_arg
                except StopIteration:
                    break
                self.pipeline.logger.info(f"Starting For loop on recipe line {node.lineno} with arg {current_arg}")
            setattr(node, 'kpf_completed', True)

    
    def visit_Assign(self, node):
        """
        Assign one or more constant or calculated values to named variables
        The variable names come from the _store stack, while the values
        come from the _load stack.
        Calls to visit() may set self._awaiting_call_return, in which case
        we need to immediately return, and pick up where we left off later,
        completing the assignment.  This typically happens when there is
        a call to a processing primitive, which is queued up on the
        framework's event queue.  See also resume_recipe().
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            setattr(node, 'kpf_completed_targets', False)
            setattr(node, 'kpf_completed_values', False)
            if hasattr(node, 'kpf_storeQSizeBefore'):
                delattr(node, 'kpf_storeQSizeBefore')
            if hasattr(node, 'kpf_num_targets'):
                delattr(node, 'kpf_num_targets')
            for target in node.targets:
                self.visit(target)
            self.visit(node.value)
            return
        if not getattr(node, 'kpf_completed', False):
            loadQSizeBefore = len(self._load)
            storeQSizeBefore = len(self._store)
            if not getattr(node, 'kpf_completed_targets', False):
                setattr(node, 'kpf_storeQSizeBefore', storeQSizeBefore)
                for target in node.targets:
                    self.visit(target)
                    if self.awaiting_call_return:
                        return
                num_store_targets = len(self._store[storeQSizeBefore:])
                setattr(node, "kpf_num_targets", num_store_targets)
                setattr(node, 'kpf_completed_targets', True)
            else:
                num_store_targets = getattr(node, 'kpf_num_targets', 0)
            if not getattr(node, 'kpf_completed_values', False):
                self.visit(node.value)
                if self.awaiting_call_return:
                    return
                setattr(node, 'kpf_completed_values', True)
            while num_store_targets > 0 and len(self._load) > loadQSizeBefore:
                target = self._store.pop()
                self.pipeline.logger.debug(f"Assign: assignment target is {target}")
                if target == '_':
                    self._load.pop() # discard
                else:
                    self._params[target] = self._load.pop()
                    self.pipeline.logger.info(f"Assign: {target} <- {self._params[target]}, type: {self._params[target].__class__.__name__}")
                num_store_targets -= 1
            had_error = False
            while len(self._store) > storeQSizeBefore:
                had_error = True
                self.pipeline.logger.error(
                    f"Assign: unfilled target: {self._store.pop()} on line {node.lineno} of recipe.")
            while len(self._load) > loadQSizeBefore:
                had_error = True
                self.pipeline.logger.error(
                    f"Assign: unused value: {self._load.pop()} on line {node.lineno} of recipe.")
            if had_error:
                raise RecipeError(
                    f"Error during assignment on line {node.lineno} of recipe.  See log for details.")
            setattr(node, 'kpf_completed', True)

    # UnaryOp and the unary operators
    
    def visit_UnaryOp(self, node):
        """
        implement UnaryOp
        We don't support calls in unaryOp expressions, so we don't
        bother guarding for self.awaiting_call_return here, nor in
        the following Unary Operators
        """
        if self._reset_visited_states:
            self.visit(node.operand)
            self.visit(node.op)
            return
        self.pipeline.logger.debug(f"UnaryOp:")
        self.visit(node.operand)
        self.visit(node.op)

    # Unary Operators

    def _unary_op_impl(self, node, name, func):
        """ Helper function containing common implementation of unary operators. """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(name)
        if len(self._load) == 0:
            raise RecipeError(
                f"Unary operator {name} invoked on recipe line {name.lineno} with no argument")
        self._load.append(func(self._load.pop()))

    def visit_UAdd(self, node):
        """ implement UAdd """
        self._unary_op_impl(node, "UAdd", lambda x : x)

    def visit_USub(self, node):
        """ implement USub """
        self._unary_op_impl(node, "USub", lambda x : -x)

    def visit_Not(self, node):
        """ implement UNot """
        self._unary_op_impl(node, "Not", lambda x : not x)

    # BinOp and the binary operators

    def visit_BinOp(self, node):
        """
        BinOp
        """
        if self._reset_visited_states:
            self.visit(node.right)
            self.visit(node.left)
            self.visit(node.op)
            return
        self.pipeline.logger.debug("BinOp:")
        # right before left because they're being pushed on a stack, so left comes off first
        self.visit(node.right)
        self.visit(node.left)
        self.visit(node.op)

    # binary operators

    def _binary_op_impl(self, node, name, func):
        """ Helper function containing common implementation of binary operators. """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(name)
        if len(self._load) < 2:
            raise RecipeError(
                f"Binary operator {name} invoked on recipe line {node.lineno} " +
                f"with insufficient number of arguments {len(self._load)}")
        self._load.append(func(self._load.pop(), self._load.pop()))

    def visit_Add(self, node):
        """ implement the addition operator """
        self._binary_op_impl(node, "Add", lambda x, y: x + y)

    def visit_Sub(self, node):
        """ implement the subtraction operator """
        self._binary_op_impl(node, "Sub", lambda x, y: x - y)
    
    def visit_Mult(self, node):
        """ implement the multiplication operator """
        self._binary_op_impl(node, "Mult", lambda x, y: x * y)
    
    def visit_Div(self, node):
        """ implement the division operator """
        self._binary_op_impl(node, "Div", lambda x, y: x / y)
    
    # Comparison operators

    def _compare_op_impl(self, node, name, func):
        """ Helper function containing common implementation of comparison operators. """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(name)
        if len(self._load) < 2:
            raise RecipeError(
                f"Comparison operator {name} invoked on line {node.lineno} " +
                f"with less than two arguments: {len(self._load)}")
        self._load.append(func(self._load.pop(), self._load.pop()))

    def visit_Eq(self, node):
        """ implement Eq comparison operator """
        self._compare_op_impl(node, "Eq", lambda x, y: x == y)
    
    def visit_NotEq(self, node):
        """ implement NotEq comparison operator """
        self._compare_op_impl(node, "NotEq", lambda x, y: x != y)
    
    def visit_Lt(self, node):
        """ implement Lt comparison operator """
        self._compare_op_impl(node, "Lt", lambda x, y: x < y)
    
    def visit_LtE(self, node):
        """ implement LtE comparison operator """
        self._compare_op_impl(node, "LtE", lambda x, y: x <= y)
    
    def visit_Gt(self, node):
        """ implement Gt comparison operator """
        self._compare_op_impl(node, "Gt", lambda x, y: x > y)
    
    def visit_GtE(self, node):
        """ implement GtE comparison operator """
        self._compare_op_impl(node, "GtE", lambda x, y: x >= y)
    
    def visit_Is(self, node):
        """ implement Is comparison operator """
        self._compare_op_impl(node, "Is", lambda x, y: x is y)
    
    def visit_IsNot(self, node):
        """ implement IsNot comparison operator """
        self._compare_op_impl(node, "IsNot", lambda x, y: not (x is y))

    def visit_In(self, node):
        """ implement In comparison operator """
        self._compare_op_impl(node, "In", lambda x, y: x in y)
    
    # TODO: implement visit_In and visit_NotIn.  Depends on support for Tuple and maybe others

    def visit_Call(self, node):
        """
        Implement function call
        The arguments are pulled from the _load stack into a list.
        Targets are put on the _store stack.
        After the call has been pushed to the framework's event queue,
        we set our awaiting_call_return flag and return.  That flag
        causes immediate returns all the way up the call stack.
        When the primitive has been run by the framework, the next
        primitive will be our "resume_recipe", which will set the
        returning_from_call flag and start traversing the AST tree
        from the top again.  Because of the various kpf_completed
        attributes set on nodes of the tree, processing will quickly
        get back to here, where the output of the primitive will be
        pushed on the _load stack, becoming the result of the call.
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            for arg in node.args:
                self.visit(arg)
            return
        self.pipeline.logger.debug(f"Call: {node.func.id} on recipe line {node.lineno}; kpf_completed is {getattr(node, 'kpf_completed', False)}")
        if node.func.id == 'invoke_subrecipe':
            subrecipe = getattr(node, '_kpf_subrecipe', None)
            if not subrecipe:
                self.pipeline.logger.debug(f"invoke_subrecipe: opening and parsing recipe file {node.args[0].s}")
                # TODO: do some argument checking here
                with open(node.args[0].s) as f:
                    fstr = f.read()
                    subrecipe = parse(fstr)
                node._kpf_subrecipe = subrecipe
            else:
                self.pipeline.logger.debug(f"invoke_subrecipe: found existing subrecipe of type {type(subrecipe)}")
            saved_depth = self.subrecipe_depth
            self.subrecipe_depth = self.subrecipe_depth + 1
            self.visit(subrecipe)
            self.subrecipe_depth = saved_depth
            if self.awaiting_call_return:
                return
        elif not getattr(node, 'kpf_completed', False):
            if not self.returning_from_call:
                # Build and queue up the called function and arguments
                # as a pipeline event.
                # The "next_event" item in the event_table, populated
                # by visit_ImportFrom, will ensure that the recipe
                # processing will continue by making resume_recipe
                # the next scheduled event primative.
                # add keyword arguments
                kwargs = {}
                for kwnode in node.keywords:
                    self.visit(kwnode)
                    tup = self._load.pop()
                    kwargs[tup[0]] = tup[1]
                if node.func.id in self._builtins.keys():
                    func, nargs = self._builtins[node.func.id]
                    if len(node.args) != nargs:
                        self.pipeline.logger.error(f"Call to {node.func.id} takes exactly {nargs} args, got {len(node.args)} on recipe line {node.lineno}")
                        raise RecipeError(f"Call to {node.func.id} takes exactly one arg, got {len(node.args)} on recipe line {node.lineno}")
                    arglist = []
                    for ix in range(nargs-1, -1, -1): # down through range because _load is a LIFO stack
                        self.visit(node.args[ix])
                        arglist.append(self._load.pop())
                    results = func(*arglist, **kwargs)
                    if isinstance(results, tuple):
                        self.pipeline.logger.debug(f"Call (builtin): returned tuple, unpacking")
                        for item in results:
                            self.pipeline.logger.debug(f"Call (builtin): appending {item} of type {type(item)} to _load")
                            self._load.append(item)
                    else:
                        self.pipeline.logger.debug(f"Call (builtin): appending {results} of type {type(results)} to _load")
                        self._load.append(results)
                else:
                    event_args = Arguments(name=node.func.id+"_args", **kwargs)
                    # add positional arguments
                    for argnode in node.args:
                        self.visit(argnode)
                        event_args.append(self._load.pop())
                    self.context.append_event(node.func.id, event_args)
                    self.pipeline.logger.info(f"Queued {node.func.id} with args {str(event_args)}; awaiting return.")
                    #
                    self.awaiting_call_return = True
                    return
            else:
                # returning from a call (pipeline event):
                # Get any returned values, stored by resume_recipe() in self.call_output,
                # and push them on the _load stack for Assign (or whatever) to handle.
                self.pipeline.logger.debug(f"Call on recipe line {node.lineno} returned output {self.call_output}")
                if isinstance(self.call_output, Arguments):
                    # got output that we can deal with, otherwise, ignore the returned value
                    for ix in range(len(self.call_output)):
                        self._load.append(self.call_output[ix])
                self.call_output = None
                self.returning_from_call = False
            setattr(node, 'kpf_completed', True)

    def visit_keyword(self, node):
        """
        implement keyword as follows:
        Since this only occurs in the context of keyword arguments in a
        call signature, we can generate tuples of (keyword, value)
        """
        if self._reset_visited_states:
            return
        # let the value node put the value on the _load stack
        self.visit(node.value)
        val = self._load.pop()
        self.pipeline.logger.debug(f"keyword: {val}")
        self._load.append((node.arg, val))

    def visit_Compare(self, node):
        """
        Implement Compare as follows:
        visiting "left" and "comparators" puts values on the _load stack.
        visiting "ops" evaluates some comparison operator, and puts the result
        on the _load stack as a Bool.
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            for item in node.comparators:
                self.visit(item)
            self.visit(node.left)
            for op in node.ops:
                self.visit(op)
            return
        if not getattr(node, 'kpf_completed', False):
            self.pipeline.logger.debug(f"Compare")
            loadQSizeBefore = len(self._load)
            # comparators before left because they're going on a stack, so left can be pulled first
            for item in node.comparators:
                self.visit(item)
            self.visit(node.left)
            for op in node.ops:
                self.visit(op)
            setattr(node, 'kpf_completed', True)

    def visit_If(self, node):
        """
        Implementation of If
        Evaluate the test and visit one of the two branches, body or orelse.
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            setattr(node, 'kpf_completed_test', False)
            if hasattr(node, 'kpf_boolResult'):
                delattr(node, 'kpf_boolResult')
            self.visit(node.test)
            for item in node.body:
                self.visit(item)
            for item in node.orelse:
                self.visit(item)
            return
        if not getattr(node, 'kpf_completed', False):
            if not getattr(node, 'kpf_completed_test', False):
                loadQSizeBefore = len(self._load)
                self.visit(node.test)
                if len(self._load) <= loadQSizeBefore:
                    raise RecipeError(
                        f"visit_If: on recipe line {node.lineno}, test didn't push a result on the _load stack")
                boolResult = self._load.pop()
                self.pipeline.logger.info(f"If condition on recipe line {node.lineno} was {boolResult}")
                setattr(node, 'kpf_boolResult', boolResult)
                setattr(node, 'kpf_completed_test', True)
            else:
                boolResult = getattr(node, 'kpf_boolResult')
            if boolResult:
                self.pipeline.logger.debug(
                    f"If on recipe line {node.lineno} pushing and visiting Ifso")
                for item in node.body:
                    self.visit(item)
                    if self.awaiting_call_return:
                        return
            else:
                self.pipeline.logger.debug(
                    f"If on recipe line {node.lineno} pushing and visiting Else")
                for item in node.orelse:
                    self.visit(item)
                    if self.awaiting_call_return:
                        return
            setattr(node, 'kpf_completed', True)

    def visit_List(self, node):
        """
        List node
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            for elt in node.elts:
                self.visit(elt)
            return
        self.pipeline.logger.debug(f"List")
        if not getattr(node, "kpf_completed", False):
            l = []
            loadDepth = len(self._load)
            for elt in node.elts:
                self.visit(elt)
                if len(self._load) > loadDepth:
                    l.append(self._load.pop())
                else:
                    raise RecipeException("List: expected item to append to list, but none was found")
            self._load.append(l)
            setattr(node, "kpf_completed", True)
    
    def visit_Tuple(self, node):
        """
        Tuple node
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            return
        self.pipeline.logger.debug(f"Tuple")
        if not getattr(node, "kpf_completed", False):
            for elt in node.elts:
                self.visit(elt)
            setattr(node, "kpf_completed", True)
        
    def visit_NameConstant(self, node):
        """
        NameConstant
        implement name constant by putting on the _load stack
        """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(f"NameConstant: {node.value}")
        #ctx of NameConstant is always Load
        self._load.append(node.value)
    
    def visit_Num(self, node):
        """
        Num
        implement numeric constant by putting it on the _load stack

        NB: An instance of Num can appear as different nodes in the same AST,
        so we can't store node specific information as an attribute.
        """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(f"Num: {node.n}")
        # ctx of Num is always Load
        self._load.append(node.n)

    def visit_Str(self, node):
        """
        Str node
        TODO: I'm not sure what to do with a multiline comment expressed as Str
        """
        if self._reset_visited_states:
            return
        self.pipeline.logger.debug(f"Str: {node.s}")
        # ctx of Str is always Load
        self._load.append(node.s)
    
    def visit_Expr(self, node):
        """
        Expr node
        """
        if self._reset_visited_states:
            setattr(node, 'kpf_completed', False)
            self.visit(node.value)
            return
        if not getattr(node, 'kpf_completed', False):
            self.visit(node.value)
            if self.awaiting_call_return:
                return
            setattr(node, 'kpf_complted', True)
    
    def visit_Attribute(self, node):
        """ Attribute node -- handle dictionary attribute """
        if self._reset_visited_states:
            return
        self.visit(node.value)
        obj = self._load.pop()
        if isinstance(node.ctx, _ast.Load):
            try:
                value = obj.getValue(node.attr)
                # print(f"Attribute: value is {type(value)}: {value}")
            except (KeyError, AttributeError):
                self.pipeline.logger.error(
                    f"Object {obj} on line {node.lineno} of recipe has no attribute {node.attr}.")
                raise RecipeError(
                    f"Object {obj} on line {node.lineno} of recipe has no attribute {node.attr}.")
            self.pipeline.logger.debug(f"Name is loading {value} from {node.attr}")
            self._load.append(value)
        elif isinstance(node.ctx, _ast.Store):
            self.pipeline.logger.error(
                f"Assigning to dictionary attribute on line {node.lineno} not supported")
            raise RecipeError(
                f"Assigning to dictionary attribute on line {node.lineno} not supported")
    
    def visit_Subscript(self, node):
        """ Subscript node """
        if self._reset_visited_states:
            return
        if isinstance(node.ctx, _ast.Load):
            self.visit(node.value)
            value = self._load.pop()
            self.visit(node.slice)
            sliceName = self._load.pop()
            self._load.append(value[sliceName])
        elif isinstance(node.ctx, _astStore):
            self.pipeline.logger.error(
                f"Assigning to subscript {node.sliceName} on recipe line {node.lineno} not supported")
            raise RecipeError(
                f"Assigning to subscript {node.sliceName} on recipe line {node.lineno} not supported")
    
    def visit_Index(self, node):
        """ Index node """
        if self._reset_visited_states:
            return
        self.visit(node.value)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        self.pipeline.logger.error(
            f"generic_visit: got unsupported node {node.__class__.__name__}")
        raise RecipeError(
            f"Unsupported language feature: {node.__class__.__name__}")
    
    def reset_visited_states(self, node):
        """
        Resets kpf_completed and other attributes of this and all subnodes,
        e.g. so that a for loop can iterate with a fresh start.
        """
        self._reset_visited_states = True
        self.awaiting_call_return = False
        self.returning_from_call = False
        self.call_output = None
        self.visit(node)
        self._load.clear()
        self._store.clear()
        self._reset_visited_states = False