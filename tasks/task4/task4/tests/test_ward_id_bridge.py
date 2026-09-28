from src.health.ward_id_bridge import bridge_ward_id, UNMATCHED_FLAG

def test_known_demo_ward_maps_to_canonical():
    assert bridge_ward_id("HYD_W001") == "GHMC_W001"
    assert bridge_ward_id("HYD_W002") == "GHMC_W002"

def test_already_canonical_id_passes_through():
    assert bridge_ward_id("GHMC_W099") == "GHMC_W099"

def test_unknown_id_returns_none():
    assert bridge_ward_id("HYD_PAIR_DRY") is None
    assert bridge_ward_id("HYD_PAIR_HUMID") is None
    assert bridge_ward_id("NOT_A_WARD") is None
