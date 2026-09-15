"""Cache contention must end in a storage fallback after bounded backoff."""

from __future__ import annotations

from unittest.mock import call
from unittest.mock import patch

import pytest

from speleodb.api.v2.views.gis_view import _load_normalized_features


@pytest.mark.parametrize("cache_recovers", [False, True])
def test_cache_lock_wait_is_bounded_and_exponential(cache_recovers: bool) -> None:
    with (
        patch("speleodb.api.v2.views.gis_view.cache") as cache,
        patch("speleodb.api.v2.views.gis_view.time.sleep") as sleep,
        patch(
            "speleodb.api.v2.views.gis_view._read_normalized_features_from_storage",
            return_value=[],
        ) as read,
        patch("speleodb.api.v2.views.gis_view._cache_features_if_under_limit"),
        patch("speleodb.api.v2.views.gis_view._cache_index_if_features_cached"),
    ):
        cache.add.return_value = False
        cache.get.return_value = None
        if cache_recovers:
            cache.get.side_effect = [None, None, []]
        assert _load_normalized_features("commit-sha") == []
    expected: list[float] = (
        [0.1, 0.2] if cache_recovers else [0.1, 0.2, 0.4, 0.8, 1, 1, 1]
    )
    assert sleep.call_args_list == [call(delay) for delay in expected]
    assert cache.get.call_count == len(expected) + 1
    if cache_recovers:
        read.assert_not_called()
    else:
        read.assert_called_once_with("commit-sha")
