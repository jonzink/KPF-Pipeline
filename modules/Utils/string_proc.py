from kpfpipe.primitives.core import KPF_Primitive

# External dependencies
from keckdrpframework.models.action import Action
from keckdrpframework.models.arguments import Arguments
from keckdrpframework.models.processing_context import ProcessingContext


class str_replace(KPF_Primitive):
    """
    This primitive does string replacement

    Description:
        - `action (keckdrpframework.models.action.Action)`: `action.args` contains positional arguments and
                  keyword arguments passed by the `str_replace` event issued in the recipe:

            - `action.args[0] (string)`: string with old value to be replaced with new value.
            - `action.args[1] (string)`: old value string to be replaced.
            - `action.args[2] (string)`: new value replacement
    """

    def __init__(self,
                 action: Action,
                 context: ProcessingContext) -> None:
        KPF_Primitive.__init__(self, action, context)

    def _pre_condition(self) -> bool:
        success = len(self.action.args) >= 3 and isinstance(self.action.args[0], str) and \
                  isinstance(self.action.args[1], str) and isinstance(self.action.args[2], str)

        return success

    def _post_condition(self) -> bool:
        return True

    def _perform(self):
        original_value = self.action.args[0]
        old_value = self.action.args[1]
        new_value = self.action.args[2]

        new_string = original_value.replace(old_value, new_value)
        return Arguments(new_string)


class date_from_kpffile(KPF_Primitive):
    """
    This primitive does string replacement

    Description:
        - `action (keckdrpframework.models.action.Action)`: `action.args` contains positional arguments and
                  keyword arguments passed by the `str_replace` event issued in the recipe:

            - `action.args[0] (string)`: filename in kpf format
    """

    def __init__(self,
                 action: Action,
                 context: ProcessingContext) -> None:
        KPF_Primitive.__init__(self, action, context)
        self.logger = self.context.logger

    def _pre_condition(self) -> bool:
        success = len(self.action.args) == 1 and isinstance(self.action.args[0], str)
        return success

    def _post_condition(self) -> bool:
        return True

    def _perform(self):
        f_name = self.action.args[0]
        first_key = 'KP.'
        date_format = 'YYYYMMDD'
        first_idx = f_name.find(first_key)
        date_str = ""
        if first_idx >= 0:
            start_idx = first_idx + len(first_key)
            date_str = f_name[start_idx:start_idx+len(date_format)]

        if not date_str:
            if self.logger:
                self.logger.info("can not find date from flat file name, " + f_name)
        else:
            if self.logger:
                self.logger.info("flat file is from " + date_str)

        return Arguments(date_str)