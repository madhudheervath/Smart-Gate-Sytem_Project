"""
Location Settings Management
Allows admin to configure campus location for GPS geofencing
"""
import json
import os
from typing import Dict, Optional

# Get the directory where this file is located (backend directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "location_settings.json")

DEFAULT_LOCATION = {
    "campus_name": "Campus",
    "latitude": 31.7768,
    "longitude": 77.0144,
    "radius_km": 2.0,
    "enabled": True
}

def get_location_settings() -> Dict:
    """Get current location settings"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading location settings: {e}")
            return DEFAULT_LOCATION
    return DEFAULT_LOCATION

def save_location_settings(settings: Dict) -> bool:
    """Save location settings"""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        # Write the settings
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        
        print(f"✅ Location settings saved successfully to {SETTINGS_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving location settings: {e}")
        print(f"   Attempted to save to: {SETTINGS_FILE}")
        import traceback
        traceback.print_exc()
        return False

def update_location(latitude: float, longitude: float, radius_km: float = 2.0, 
                   campus_name: str = "Campus", enabled: bool = True) -> Dict:
    """Update location settings"""
    settings = {
        "campus_name": campus_name,
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "enabled": enabled
    }
    
    print(f"📝 Attempting to save location settings:")
    print(f"   Campus: {campus_name}")
    print(f"   Lat/Lon: {latitude}, {longitude}")
    print(f"   Radius: {radius_km} km")
    print(f"   Enabled: {enabled}")
    
    if save_location_settings(settings):
        print("✅ Location settings updated successfully!")
        return settings
    else:
        error_msg = f"Failed to save location settings to {SETTINGS_FILE}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)

def is_geofencing_enabled() -> bool:
    """Check if geofencing is enabled"""
    settings = get_location_settings()
    return settings.get("enabled", True)

def get_campus_location() -> tuple:
    """Get campus center coordinates"""
    settings = get_location_settings()
    return (settings.get("latitude", 31.7768), settings.get("longitude", 77.0144))

def get_campus_radius() -> float:
    """Get campus radius in kilometers"""
    settings = get_location_settings()
    return settings.get("radius_km", 2.0)
