import enum

from . import sub, pybind

class Foo:
    def a_method(self):
        pass

    @property
    def a_property(self):
        pass

    class Enum(enum.Enum):
        A_VALUE = 1
        ANOTHER = 2

def a_function():
    pass

def func_with_params(a, b):
    pass
