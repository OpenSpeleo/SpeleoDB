#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class Lazy:
    def __new__(cls, realcls, args, kwargs):
        # Use the real class's __new__ to get a new object instance.
        obj = realcls.__new__(realcls, *args, **kwargs)
        # Replace the class with Lazy until reified.
        obj.__class__ = cls
        # Store info we need to reify object.
        obj.__lazy_info = (realcls, args, kwargs)
        return obj

    # enddef

    def __getattr__(self, name):
        # print("Getting attribute: {}".format(name))
        (realcls, args, kwargs) = self.__lazy_info
        self.__dict__.clear()
        # print("Performing class switch.")
        self.__class__ = realcls
        # print("Calling init.")
        self.__init__(*args, **kwargs)
        # print("Returning actual value.")
        return getattr(self, name)

    # enddef

    def __repr__(self):
        (realcls, args, kwargs) = self.__lazy_info
        return f"Lazy{realcls}{(args, kwargs)}"


class LazySingletonMetaClass(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = Lazy(cls, args, kwargs)

        return cls._instances[cls]


class SingletonMetaClass(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]
