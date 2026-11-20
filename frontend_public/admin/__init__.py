# -*- coding: utf-8 -*-

from __future__ import annotations

from frontend_public.admin.boards import BoardMemberAdmin
from frontend_public.admin.boards import ExplorerMemberAdmin
from frontend_public.admin.boards import ScientificMemberAdmin
from frontend_public.admin.boards import TechnicalMemberAdmin
from frontend_public.admin.supporters import OrganizationSupporterAdmin
from frontend_public.admin.supporters import PersonSupporterAdmin

__all__ = [
    "BoardMemberAdmin",
    "ExplorerMemberAdmin",
    "OrganizationSupporterAdmin",
    "PersonSupporterAdmin",
    "ScientificMemberAdmin",
    "TechnicalMemberAdmin",
]
