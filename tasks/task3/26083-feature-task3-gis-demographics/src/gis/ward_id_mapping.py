"""
Single stable ward_id source of truth for Task 3.

Per the Playbook correction audit (G3): the processed GeoJSON output and
the vulnerability CSV output must key off exactly the same ward_id for a
given ward, and every downstream join (Task 4 health risk, Task 6 GIS
API) must resolve wards through this one mapping rather than deriving
IDs independently in more than one place.

`ward_loader.load_tgrac_ward_layer` is the only place that MINTS a
ward_id (from WARD_ID / ward_id / OBJECTID, falling back to a stable
GHMC_W{idx:03d} scheme). Everything else — spatial_join, vulnerability,
and any script that writes GeoJSON or CSV — must resolve ward_id via
this module instead of re-deriving it, so the mapping cannot drift
between outputs.
"""
from __future__ import annotations

from typing import Iterable


def build_ward_id_index(wards: Iterable[dict]) -> dict:
    """
    Build a ward_id -> ward record index from records already produced by
    `ward_loader.load_tgrac_ward_layer`. This is the one canonical lookup
    every downstream writer (GeoJSON export, vulnerability CSV export,
    Task 4 join) should use, so both outputs stay keyed on identical ids.
    """
    index: dict = {}
    for ward in wards:
        ward_id = ward.get("ward_id")
        if not ward_id:
            continue
        if ward_id in index:
            raise ValueError(f"duplicate_ward_id_detected ward_id={ward_id}")
        index[ward_id] = ward
    return index


def assert_consistent_ward_ids(*ward_id_sets: Iterable[str]) -> None:
    """
    Verify two or more collections of ward_id values (e.g. the ids present
    in the processed GeoJSON vs. the ids present in ward_vulnerability.csv)
    reference the same stable set. Raises ValueError naming the mismatch
    instead of silently allowing two outputs to disagree.
    """
    sets = [set(s) for s in ward_id_sets]
    if not sets:
        return
    base = sets[0]
    for i, s in enumerate(sets[1:], start=2):
        if s != base:
            missing_from_base = s - base
            missing_from_other = base - s
            raise ValueError(
                "ward_id_mapping_mismatch "
                f"set1_only={sorted(missing_from_other)} "
                f"set{i}_only={sorted(missing_from_base)}"
            )
