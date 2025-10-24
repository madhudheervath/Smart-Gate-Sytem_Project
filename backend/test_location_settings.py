#!/usr/bin/env python3
"""
Test script to verify location settings can be saved
"""
import location_settings

print("=" * 60)
print("Testing Location Settings Module")
print("=" * 60)

# Test 1: Get default settings
print("\n1. Testing get_location_settings()...")
settings = location_settings.get_location_settings()
print(f"   ✓ Current settings: {settings}")

# Test 2: Update location
print("\n2. Testing update_location()...")
try:
    new_settings = location_settings.update_location(
        campus_name="Test Campus",
        latitude=31.784136,
        longitude=76.995256,
        radius_km=2.0,
        enabled=True
    )
    print(f"   ✓ Updated successfully!")
    print(f"   ✓ New settings: {new_settings}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Read back the settings
print("\n3. Testing if settings persist...")
settings = location_settings.get_location_settings()
print(f"   ✓ Read back: {settings}")

# Test 4: Check file location
print(f"\n4. Settings file location:")
print(f"   {location_settings.SETTINGS_FILE}")

import os
if os.path.exists(location_settings.SETTINGS_FILE):
    print(f"   ✓ File exists")
    print(f"   ✓ Readable: {os.access(location_settings.SETTINGS_FILE, os.R_OK)}")
    print(f"   ✓ Writable: {os.access(location_settings.SETTINGS_FILE, os.W_OK)}")
else:
    print(f"   ✗ File does not exist")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
