"""
Tests for the single stable ward_id mapping (Playbook gate G3): the
processed GeoJSON and the vulnerability CSV must key off the same ids.
"""
from __future__ import annotations

import csv
import json

import pytest

from src.gis.ward_id_mapping import assert_consistent_ward_ids, build_ward_id_index


def test_build_ward_id_index_basic():
    wards = [{"ward_id": "GHMC_W001", "ward_name": "A"}, {"ward_id": "GHMC_W002", "ward_name": "B"}]
    idx = build_ward_id_index(wards)
    assert set(idx) == {"GHMC_W001", "GHMC_W002"}


def test_build_ward_id_index_rejects_duplicates():
    wards = [{"ward_id": "GHMC_W001"}, {"ward_id": "GHMC_W001"}]
    with pytest.raises(ValueError):
        build_ward_id_index(wards)


def test_assert_consistent_ward_ids_passes_for_matching_sets():
    assert_consistent_ward_ids(["A", "B"], ["A", "B"])


def test_assert_consistent_ward_ids_raises_on_mismatch():
    with pytest.raises(ValueError):
        assert_consistent_ward_ids(["A", "B"], ["A", "C"])


def test_processed_geojson_and_csv_ward_ids_are_the_same_set():
    """
    Integration-level check against the actual immutable processed
    outputs shipped with this task: the GeoJSON and the CSV must use the
    same ward_id scheme (same ids present), per gate G3.
    """
    with open("data/processed/gis/hyderabad_wards.geojson") as f:
        geo = json.load(f)
    geo_ids = {
        (f.get("properties") or f.get("attributes") or {}).get("ward_id")
        for f in geo.get("features", [])
    }
    geo_ids.discard(None)

    with open("data/processed/vulnerability/ward_vulnerability.csv") as f:
        csv_ids = {row["ward_id"] for row in csv.DictReader(f)}

    assert_consistent_ward_ids(geo_ids, csv_ids)
