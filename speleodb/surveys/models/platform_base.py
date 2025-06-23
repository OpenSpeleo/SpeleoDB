# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.utils.django_base_models import BaseIntegerChoices


class SurveyPlatformEnum(BaseIntegerChoices):
    WEB = (0, "WEB")
    ARIANE = (1, "ARIANE")
