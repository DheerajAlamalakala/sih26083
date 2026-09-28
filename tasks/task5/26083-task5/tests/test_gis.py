import unittest
from src.gis.ward_loader import load_tgrac_ward_layer


class TestTask3GISPipeline(unittest.TestCase):

  def setUp(self):
    self.raw_path = "data/raw/gis/ghmc_wards_census_2021.json"
    self.wards = load_tgrac_ward_layer(self.raw_path)

  def test_ward_loader_count(self):
    """Verify that all 155 wards are loaded correctly."""
    self.assertGreater(
        len(self.wards), 0, "Ward loader returned empty ward list."
    )
    self.assertEqual(len(self.wards), 155, f"Expected 155 wards, got {len(self.wards)}")

  def test_ward_loader_geometry_validity(self):
    """Verify geometry contains valid spatial rings or standard GeoJSON polygon types."""
    for ward in self.wards:
      geom = ward.get("geometry", {})
      # Validate Esri JSON ('rings') or GeoJSON ('type' / 'coordinates')
      has_esri_rings = "rings" in geom and len(geom["rings"]) > 0
      has_geojson_type = geom.get("type") in ["Polygon", "MultiPolygon"]

      self.assertTrue(
          has_esri_rings or has_geojson_type,
          f"Ward {ward['ward_id']} missing valid geometry definition.",
      )

  def test_required_contract_fields(self):
    """Verify all Task 3 contract fields are present."""
    required_keys = [
        "ward_id",
        "ward_name",
        "zone_name",
        "geometry",
        "source_vintage",
        "data_source",
    ]
    for ward in self.wards:
      for key in required_keys:
        self.assertIn(
            key,
            ward,
            f"Ward record missing required contract field: {key}",
        )


if __name__ == "__main__":
  unittest.main()