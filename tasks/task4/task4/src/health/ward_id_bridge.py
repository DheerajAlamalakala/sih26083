"""
Ward ID bridging for Task 4.

Problem: Task 2's Stage-1 thermal demo output uses ad-hoc IDs
(HYD_W001, HYD_W002, HYD_PAIR_DRY, HYD_PAIR_HUMID) covering only
4 wards. Task 3's real vulnerability data uses the authoritative
GHMC_W001..GHMC_W155 scheme from the TGRAC ward layer.

Canonical scheme: GHMC_Wxxx (Task 3's, since it's the real/official
source). This module maps whatever Task 2 currently emits onto that
scheme where possible, and marks the rest as unmatched rather than
dropping or fabricating a join.

Once Task 2 reruns Stage 1 against the real 155-ward list, this
bridge becomes a no-op (identity mapping) and can be deleted.
"""
import re
from typing import Optional

# Known demo-ward mapping (fill in / extend once you confirm which
# real ward Task 2's demo data was actually generated for; ask
# your Task 2 teammate for this if it's not documented anywhere).
KNOWN_DEMO_MAPPING = {
    "HYD_W001": "GHMC_W001",
    "HYD_W002": "GHMC_W002",
}

# Pair-demo wards (HYD_PAIR_DRY / HYD_PAIR_HUMID) are synthetic
# comparison wards invented for the "two similar-temperature wards"
# demo narrative in the playbook. They don't correspond to a real
# ward, so they're intentionally left unmapped here — treat them
# as a separate demo-only path if you want to keep that scenario.
UNMATCHED_FLAG = "WARD_ID_UNMATCHED"


def bridge_ward_id(raw_ward_id: str) -> Optional[str]:
    """Return the canonical GHMC_Wxxx id for a raw Task 2 ward_id,
    or None if there's no known mapping (caller should set
    quality_flag=UNMATCHED_FLAG and keep the row rather than drop it).
    """
    if raw_ward_id in KNOWN_DEMO_MAPPING:
        return KNOWN_DEMO_MAPPING[raw_ward_id]

    # Already canonical (post-rerun world)
    if re.fullmatch(r"GHMC_W\d{3}", raw_ward_id):
        return raw_ward_id

    return None
