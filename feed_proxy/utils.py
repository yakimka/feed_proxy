import importlib
import logging
from collections import UserDict


def load_class(full_class_string):
    """Dynamically load a class from a string
    """

    class_data = full_class_string.split(".")
    module_path = ".".join(class_data[:-1])
    class_str = class_data[-1]

    module = importlib.import_module(module_path)
    return getattr(module, class_str)


class AttrDict(UserDict):
    def __getattr__(self, item):
        try:
            return self.data[item]
        except KeyError:
            raise AttributeError(f"'AttrDict' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        if key in ['data']:
            super().__setattr__(key, value)
        else:
            self.data[key] = value


class CompactFormatter(logging.Formatter):
    """Leave class name only
    """
    def format(self, record):
        record.name = record.name.rpartition('.')[-1]
        return super().format(record)


def make_logger(name, *, handler, level):
    """Create the root logger
    """
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def class_logger(path, classname):
    """Return logger for a class
    """
    return logging.getLogger(path).getChild(classname)
