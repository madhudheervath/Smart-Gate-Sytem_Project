"""
test_geofence.py — 5 cases for GPS geofencing validation.

UC06: inside campus, outside campus, invalid coordinates, buffer zone, polygon mode.
"""

import pytest
from geofence import Geofence, validate_student_location, DEFAULT_CAMPUS_POLYGON, CAMPUS_CENTER, CAMPUS_RADIUS_KM


CAMPUS_LAT, CAMPUS_LON = CAMPUS_CENTER
RADIUS_KM = CAMPUS_RADIUS_KM


class TestCircularGeofence:
    def setup_method(self):
        # Build a fresh circular fence using only the module-level defaults,
        # bypassing the dynamic location_settings file that may differ.
        self.fence = Geofence(use_polygon=False)
        # Prevent _refresh_settings from overwriting our known-good center/radius
        # (it reads location_settings.json which may store different coordinates)
        self.fence._refresh_settings = lambda: None
        self.fence.center = (CAMPUS_LAT, CAMPUS_LON)
        self.fence.radius_km = RADIUS_KM

    def test_inside_campus_returns_valid(self):
        # Campus center is always inside its own boundary
        is_valid, message, details = self.fence.validate_location(CAMPUS_LAT, CAMPUS_LON)
        assert is_valid is True
        assert details["inside"] is True

    def test_outside_campus_returns_invalid(self):
        # ~111 km north — well outside any reasonable campus radius
        far_lat = CAMPUS_LAT + 1.0
        is_valid, message, details = self.fence.validate_location(far_lat, CAMPUS_LON)
        assert is_valid is False
        assert "outside" in message.lower() or details["inside"] is False

    def test_invalid_coordinates_rejected(self):
        is_valid, message, details = self.fence.validate_location(999.0, 999.0)
        assert is_valid is False
        assert "invalid" in message.lower()

    def test_buffer_zone_accepted(self):
        import geopy.distance
        # Place point exactly at the boundary (0 buffer). With 100 m buffer it must pass.
        dest = geopy.distance.distance(kilometers=RADIUS_KM).destination(
            (CAMPUS_LAT, CAMPUS_LON), bearing=0
        )
        is_valid, message, details = self.fence.validate_location(
            dest.latitude, dest.longitude, buffer_meters=200
        )
        assert is_valid is True, f"Boundary point with 200 m buffer should be accepted: {message}"


class TestPolygonGeofence:
    def test_polygon_mode_inside(self):
        fence = Geofence(use_polygon=True)
        # Centroid of DEFAULT_CAMPUS_POLYGON — guaranteed inside
        lats = [p[0] for p in DEFAULT_CAMPUS_POLYGON]
        lons = [p[1] for p in DEFAULT_CAMPUS_POLYGON]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        assert fence.is_inside(center_lat, center_lon) is True
