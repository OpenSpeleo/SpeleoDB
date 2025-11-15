# -*- coding: utf-8 -*-

# NOTE: We need to preserve this exact import order to prevent import loops.
# ruff: noqa: I001

# Plugin / App related Models
from speleodb.plugins.models.annoucement import PublicAnnoucement
from speleodb.plugins.models.plugin_release import PluginRelease


__all__ = ["PluginRelease", "PublicAnnoucement"]
