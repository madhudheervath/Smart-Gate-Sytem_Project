# 📍 Campus Location Settings - Complete Guide

## Overview

The Location Settings feature allows admins to configure the GPS coordinates and geofencing parameters for the campus. Students will automatically use these configured settings for location validation during daily entry.

---

## 🎯 Features

### For Admins:
- ✅ Set campus name
- ✅ Configure GPS coordinates (latitude/longitude)
- ✅ Set geofencing radius (in kilometers)
- ✅ Enable/disable GPS validation
- ✅ Use current location (auto-detect)
- ✅ Real-time preview of settings

### For Students:
- ✅ Automatically fetch campus location
- ✅ Validate location against configured settings
- ✅ No manual configuration needed

---

## 🚀 How It Works

### Backend:
1. **location_settings.py** - Manages location configuration
2. **location_settings.json** - Stores location data (auto-created)
3. **API endpoints** - Get/update location settings
4. **geofence.py** - Uses configured location for validation

### Frontend:
1. **admin/location.html** - Admin interface for configuration
2. **Student portal** - Fetches and uses configured location

---

## 📖 Usage Guide

### For Admins:

#### Access Location Settings:
1. Login to **Admin Portal**
2. Click **"📍 Configure Campus Location"** button
3. You'll see the current location settings

#### Configure Location:

**Method 1: Manual Entry**
1. Enter campus name (e.g., "Main Campus", "College Campus")
2. Enter latitude (e.g., 31.7768)
3. Enter longitude (e.g., 77.0144)
4. Set radius in kilometers (e.g., 2.0)
5. Click **"💾 Save Location Settings"**

**Method 2: Auto-Detect (Recommended)**
1. Go to the physical campus location
2. Click **"📍 Use My Location"** button
3. Allow browser to access your location
4. Coordinates will be auto-filled
5. Adjust radius if needed
6. Click **"💾 Save Location Settings"**

#### Enable/Disable Geofencing:
- Toggle the **"Enable GPS Geofencing"** switch
- When **enabled**: Students must be within radius for daily entry
- When **disabled**: Location validation is skipped

---

## 🔧 Configuration File

Location settings are stored in:
```
backend/location_settings.json
```

**Example:**
```json
{
  "campus_name": "Campus",
  "latitude": 31.7768,
  "longitude": 77.0144,
  "radius_km": 2.0,
  "enabled": true
}
```

**Default Values:**
- Campus Name: "Campus"
- Latitude: 31.7768
- Longitude: 77.0144
- Radius: 2.0 km
- Enabled: true

---

## 🌐 API Endpoints

### 1. Get Location Settings (Admin)
```
GET /api/admin/location
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "campus_name": "Campus",
  "latitude": 31.7768,
  "longitude": 77.0144,
  "radius_km": 2.0,
  "enabled": true
}
```

### 2. Update Location Settings (Admin)
```
POST /api/admin/location
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "campus_name": "Main Campus",
  "latitude": 31.7768,
  "longitude": 77.0144,
  "radius_km": 2.5,
  "enabled": true
}
```

**Response:**
```json
{
  "message": "Location settings updated successfully",
  "settings": { ... }
}
```

### 3. Get Location Settings (Public - for students)
```
GET /api/location
```

**Response:**
```json
{
  "enabled": true,
  "campus_name": "Campus",
  "latitude": 31.7768,
  "longitude": 77.0144,
  "radius_km": 2.0
}
```

---

## 💻 Code Integration

### Backend - Using Configured Location:

```python
from geofence import Geofence

# Initialize geofence (automatically uses configured location)
geo = Geofence(use_polygon=False)

# Check if location is inside campus
is_valid = geo.is_inside(latitude=user_lat, longitude=user_lon)

# Get distance to campus
distance = geo.get_distance_to_campus(user_lat, user_lon)
```

### Frontend - Fetching Location:

```javascript
// Fetch campus location settings
const response = await fetch('/api/location');
const location = await response.json();

console.log(location.campus_name);  // "Campus"
console.log(location.latitude);      // 31.7768
console.log(location.longitude);     // 77.0144
console.log(location.radius_km);     // 2.0
```

---

## 🗺️ Finding Campus Coordinates

### Method 1: Google Maps
1. Go to https://maps.google.com
2. Search for your campus
3. Right-click on the center point
4. Click coordinates to copy
5. Format: Latitude, Longitude

### Method 2: GPS Device
1. Use GPS-enabled device
2. Stand at campus center
3. Record coordinates
4. Use in settings

### Method 3: Mobile Phone
1. Open Google Maps on phone
2. Long-press on campus center
3. Coordinates appear at top
4. Copy and use

---

## 📏 Choosing Radius

### Recommendations:

**Small Campus** (< 1 sq km):
- Radius: 0.5 - 1.0 km
- Covers main buildings

**Medium Campus** (1-4 sq km):
- Radius: 1.0 - 2.0 km
- Covers most areas

**Large Campus** (> 4 sq km):
- Radius: 2.0 - 5.0 km
- Covers entire campus

**Testing Tip:**
- Start with larger radius
- Test with students
- Gradually reduce if needed

---

## 🔒 Security Considerations

### Admin Access Only:
- ✅ Only admins can change location settings
- ✅ Settings require authentication
- ✅ Changes are logged

### Student Access:
- ✅ Students can only read location (not modify)
- ✅ Used for validation only
- ✅ Cannot bypass geofencing

---

## 🐛 Troubleshooting

### Issue: "Geofencing is not enabled"
**Solution:**
```bash
pip install shapely geopy
```

### Issue: Location not updating
**Solution:**
1. Check if location_settings.json exists
2. Verify file permissions
3. Restart server after changes

### Issue: Students outside radius
**Solution:**
1. Increase radius in settings
2. Verify campus center coordinates
3. Test with admin's location first

### Issue: Auto-detect not working
**Solution:**
1. Enable location in browser settings
2. Use HTTPS (required for geolocation)
3. Try manual entry instead

---

## 📊 Best Practices

### 1. Test Before Production:
- Set location with admin
- Test with test student account
- Verify radius is appropriate

### 2. Communicate Changes:
- Notify students of location requirements
- Provide support for location issues
- Have fallback for location failures

### 3. Monitor Usage:
- Check logs for location errors
- Adjust radius based on feedback
- Review failed validations

### 4. Backup Settings:
- Keep record of coordinates
- Document radius decisions
- Note any customizations

---

## 🎯 Example Scenarios

### Scenario 1: New Campus Setup
```
1. Admin logs in
2. Goes to Location Settings
3. Clicks "Use My Location" at campus center
4. Sets radius to 2.0 km
5. Enables geofencing
6. Saves settings
7. Tests with student account
```

### Scenario 2: Multiple Buildings
```
1. Identify geometric center
2. Measure distance to farthest building
3. Set radius slightly larger
4. Test from each building
5. Adjust if needed
```

### Scenario 3: Temporary Disable
```
1. Admin goes to Location Settings
2. Toggles "Enable GPS Geofencing" OFF
3. Saves settings
4. Students can now use system without location
5. Re-enable when ready
```

---

## 📝 Testing Checklist

### Admin Testing:
- [ ] Can access location settings page
- [ ] Can view current settings
- [ ] Can update location manually
- [ ] Can use auto-detect
- [ ] Can enable/disable geofencing
- [ ] Changes are saved
- [ ] Settings persist after reload

### Student Testing:
- [ ] Can fetch location settings
- [ ] Location validation works
- [ ] Within radius: passes validation
- [ ] Outside radius: fails validation
- [ ] Disabled geofencing: always passes

---

## 🎉 Summary

The Location Settings feature provides:
- ✅ **Flexible** - Easy to configure for any campus
- ✅ **User-friendly** - Admin interface with auto-detect
- ✅ **Automatic** - Students use configured location
- ✅ **Secure** - Admin-only configuration
- ✅ **Reliable** - Persistent storage in JSON file

---

## 📞 Support

For issues or questions:
1. Check this guide
2. Verify API endpoints are accessible
3. Check server logs
4. Test with default coordinates

---

**Location Settings make your Smart Gate System adaptable to any campus!** 🎓📍
