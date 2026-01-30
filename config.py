# config.py - Central configuration for GIS routing comparison project

# =============================================================================
# BOUNDING BOX: Districts 1, 2, 3 - Ho Chi Minh City
# =============================================================================
# District 1 (Quận 1): 10.762-10.787 lat, 106.680-106.710 lon
# District 2 (Quận 2): 10.770-10.820 lat, 106.720-106.760 lon (now Thủ Đức)
# District 3 (Quận 3): 10.775-10.800 lat, 106.665-106.695 lon

MIN_LON = 106.665
MIN_LAT = 10.762
MAX_LON = 106.760
MAX_LAT = 10.820

# Bounding box as tuple (for osmium: min_lon,min_lat,max_lon,max_lat)
BBOX = (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)
BBOX_STR = f"{MIN_LON},{MIN_LAT},{MAX_LON},{MAX_LAT}"

# =============================================================================
# VALHALLA ENDPOINTS
# =============================================================================
VALHALLA_2018 = "http://localhost:8004"
VALHALLA_2025 = "http://localhost:8005"

# =============================================================================
# ROUTING CONFIGURATION
# =============================================================================
# Costing profile: "auto" = car-only routing
# Excludes: footway, pedestrian, path, cycleway, steps, bridleway
# Includes: motorway, trunk, primary, secondary, tertiary, residential, service
COSTING = "auto"

# =============================================================================
# FILE PATHS
# =============================================================================
POINTS_CSV = "points.csv"
POINTS_DATA_CSV = "points_data.csv"
MATRIX_2018_CSV = "matrix_2018.csv"
MATRIX_2025_CSV = "matrix_2025.csv"
MATRIX_DELTA_CSV = "matrix_delta.csv"

# =============================================================================
# TIMEOUTS
# =============================================================================
LOCATE_TIMEOUT = 15
ROUTE_TIMEOUT = 90
MATRIX_TIMEOUT = 600
