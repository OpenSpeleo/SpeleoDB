# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import ScientificMember
from frontend_public.models import TechnicalMember

type PersonModel = BoardMember | TechnicalMember | ExplorerMember | ScientificMember


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class", [BoardMember, TechnicalMember, ExplorerMember, ScientificMember]
)
def test_people_order_explicit_positions_then_unordered_names(
    model_class: type[PersonModel],
) -> None:
    # Each concrete model declares its own ordering; exercise PostgreSQL's NULL order.
    for name, order in [
        ("Charlie", 3),
        ("Alice", 1),
        ("Bob", 2),
        ("Zoe", None),
        ("Adam", None),
    ]:
        model_class.objects.create(full_name=name, order=order)
    assert list(model_class.objects.values_list("full_name", flat=True)) == [
        "Alice",
        "Bob",
        "Charlie",
        "Adam",
        "Zoe",
    ]


def test_photo_url_uses_public_storage_and_handles_missing_photo() -> None:
    person = BoardMember(photo="test_photo.jpg")
    assert person.get_photo_url() == person.photo.storage.url("test_photo.jpg")
    person.photo = None
    assert person.get_photo_url() is None
