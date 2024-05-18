#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

############################## Option MODEL ###################################


class Option(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    value = EncryptedCharField(max_length=255, default="")

    def __str__(self):
        return self.name

    def __repr__(self):
        value = f"`{self.value}`" if settings.DEBUG else "<ENCRYPTED>"
        return f"[{self.__class__.__name__}: `{self.name}`]: {value}"

    def as_bool(self):
        return self.value.lower() in [
            "true",
            "1",
            "t",
            "y",
            "yes",
            "yeah",
            "yup",
            "certainly",
            "uh-huh",
        ]

    @classmethod
    @lru_cache(100)
    def get(cls, name):
        return cls.objects.get(name=name)

    @classmethod
    def get_or_empty(cls, name):
        try:
            return cls.get(name=name)
        except ObjectDoesNotExist:
            return ""
