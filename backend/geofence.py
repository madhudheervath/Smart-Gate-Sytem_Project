"""
GPS Geofencing Module
Validates student location against campus boundaries
"""
from shapely.geometry import Point, Polygon
from geopy.distance import geodesic
from typing import Tuple, Optional
import json

# Campus Geofence
# Format: List of [latitude, longitude] points defining campus boundary
DEFAULT_CAMPUS_POLYGON = [
    [31.7745, 77.0095],  # North-West corner
    [31.7780, 77.0095],  # North-East corner
    [31.7780, 77.0190],  # South-East corner
    [31.7745, 77.0190],  # South-West corner
    [31.7745, 77.0095],  # Back to start (close polygon)
]

# Alternative: Circular geofence (RECOMMENDED)
# Campus center coordinates (default values)
CAMPUS_CENTER = (31.7768, 77.0144)  # Latitude, Longitude of campus center
CAMPUS_RADIUS_KM = 2.0  # 2 km radius to cover entire campus area

def get_campus_settings():
    """Get campus location from settings file or use defaults"""
    try:
        import location_settings
        settings = location_settings.get_location_settings()
        center = (settings.get('latitude', 31.7768), settings.get('longitude', 77.0144))
        radius = settings.get('radius_km', 2.0)
        return center, radius
    except:
        return CAMPUS_CENTER, CAMPUS_RADIUS_KM

class Geofence:
    """GPS Geofencing handler"""
    
    def __init__(self, use_polygon: bool = False):
        """
        Initialize geofence
        
        Args:
            use_polygon: If True, use polygon boundary. If False, use circular boundary (default)
        """
        self.use_polygon = use_polygon
        if use_polygon:
            # Create Shapely polygon from coordinates
            self.polygon = Polygon([(lat, lon) for lat, lon in DEFAULT_CAMPUS_POLYGON])
        else:
            # Use configured location settings or defaults
            pass # Settings loaded dynamically on check
    
    def _refresh_settings(self):
        """Reload settings from file"""
        if not self.use_polygon:
            self.center, self.radius_km = get_campus_settings()
    
    def is_inside(self, latitude: float, longitude: float) -> bool:
        """
        Check if coordinates are inside campus geofence
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            
        Returns:
            True if inside campus boundary, False otherwise
        """
        if self.use_polygon:
            # Check polygon containment
            point = Point(latitude, longitude)
            return self.polygon.contains(point)
        else:
            # Check circular boundary
            self._refresh_settings()
            student_location = (latitude, longitude)
            distance_km = geodesic(self.center, student_location).kilometers
            return distance_km <= self.radius_km
    
    def get_distance_to_campus(self, latitude: float, longitude: float) -> float:
        """
        Calculate distance from point to campus center (in km)
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            
        Returns:
            Distance in kilometers
        """
        self._refresh_settings()
        student_location = (latitude, longitude)
        campus_center = self.center if not self.use_polygon else (
            sum(p[0] for p in DEFAULT_CAMPUS_POLYGON) / len(DEFAULT_CAMPUS_POLYGON),
            sum(p[1] for p in DEFAULT_CAMPUS_POLYGON) / len(DEFAULT_CAMPUS_POLYGON)
        )
        return geodesic(campus_center, student_location).kilometers
    
    def validate_location(self, latitude: float, longitude: float, 
                         buffer_meters: int = 50) -> Tuple[bool, str, dict]:
        """
        Validate location with detailed response
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            buffer_meters: Extra buffer to account for GPS inaccuracy (default 50m)
            
        Returns:
            Tuple of (is_valid: bool, message: str, details: dict)
        """
        # Check basic validity
        if not self._is_valid_coordinate(latitude, longitude):
            return False, "Invalid GPS coordinates", {
                "latitude": latitude,
                "longitude": longitude,
                "inside": False,
                "distance_km": None
            }
        
        # Check geofence
        is_inside = self.is_inside(latitude, longitude)
        distance_km = self.get_distance_to_campus(latitude, longitude)
        
        # Apply buffer for GPS inaccuracy
        buffer_km = buffer_meters / 1000.0
        inside_with_buffer = is_inside or distance_km <= (self.radius_km + buffer_km if not self.use_polygon else buffer_km)
        
        details = {
            "latitude": latitude,
            "longitude": longitude,
            "inside": is_inside,
            "inside_with_buffer": inside_with_buffer,
            "distance_km": round(distance_km, 3),
            "distance_meters": round(distance_km * 1000, 1)
        }
        
        if inside_with_buffer:
            if is_inside:
                message = "Location verified: Inside campus"
            else:
                message = f"Location verified: Near campus ({details['distance_meters']}m from center)"
            return True, message, details
        else:
            message = f"Location denied: Outside campus ({details['distance_km']:.2f} km away)"
            return False, message, details
    
    @staticmethod
    def _is_valid_coordinate(latitude: float, longitude: float) -> bool:
        """Validate coordinate ranges"""
        return -90 <= latitude <= 90 and -180 <= longitude <= 180

def create_custom_geofence(coordinates: list) -> Geofence:
    """
    Create a custom polygon geofence from coordinates
    
    Args:
        coordinates: List of [lat, lon] pairs
        
    Returns:
        Geofence instance
    """
    global DEFAULT_CAMPUS_POLYGON
    DEFAULT_CAMPUS_POLYGON = coordinates
    return Geofence(use_polygon=True)

def create_circular_geofence(center_lat: float, center_lon: float, radius_km: float) -> Geofence:
    """
    Create a circular geofence
    
    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        radius_km: Radius in kilometers
        
    Returns:
        Geofence instance
    """
    global CAMPUS_CENTER, CAMPUS_RADIUS_KM
    CAMPUS_CENTER = (center_lat, center_lon)
    CAMPUS_RADIUS_KM = radius_km
    return Geofence(use_polygon=False)

# Global geofence instance (can be reconfigured)
campus_geofence = Geofence(use_polygon=False)  # Default to circular

def validate_student_location(latitude: float, longitude: float) -> Tuple[bool, str, dict]:
    """
    Convenience function to validate student location
    
    Args:
        latitude: GPS latitude
        longitude: GPS longitude
        
    Returns:
        Tuple of (is_valid, message, details)
    """
    return campus_geofence.validate_location(latitude, longitude)
