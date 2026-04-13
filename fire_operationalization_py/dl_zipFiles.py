import os
import json
import geopandas as gpd
import requests

import io
import zipfile

#import rasterio
#from rasterio.shutil import copy as rio_copy
#from rasterio.enums import Resampling

#import matplotlib.pyplot as plt
import numpy as np

# Utility functions
def get_bbox(geojson_path):
    """Extracts bounding box coordinates from an input vector data file"""
    gdf = gpd.read_file(geojson_path) # you can use a .shp file also here directly

    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    bbox = tuple([float(b) for b in gdf.total_bounds])

    return bbox
	
# Use City of Ottawa urban boundary as test AOI
#geojson_path = './ottawa_urban_boundary.geojson'
#Exported the sentinel2 footprints from the QGIS file as geojson
geojson_path = './FireNearFlinFlonMay302025.geojson'
#geojson_path = './nwt_example.geojson'
aoi_gdf = gpd.read_file(geojson_path)
utm_crs = aoi_gdf.estimate_utm_crs().to_epsg()
bbox = get_bbox(geojson_path)
print(bbox)

# Filter assets by imaging date
start_date = '2025-06-03T00:00:00Z'
end_date = '2025-06-03T23:59:59Z'

# Open EODMS STAC catalog and explore available collections
ogc_api_url = 'https://www.eodms-sgdot.nrcan-rncan.gc.ca/search/
# Construct the collections endpoint
collections_url = f"{ogc_api_url}/collections"
# Send a GET request to the collections endpoint
response = requests.get(collections_url)
if response.status_code == 200:
    collections = response.json() 
    print("Collections available in the OGC API:")
    num_collections = len(collections.get("collections", []))
    print(f"Number of collections: {num_collections}")
    for collection in collections.get("collections", []):
        print(f"- {collection.get('id')}: {collection.get('title')}")
else:  
    print(f"Failed to retrieve collections. Status code: {response.status_code}")

# List all items in RCM-ARD collection that intersect with area of interest within date range
#collection_id = 'Sentinel2'
#collection_id = 'S2_L2A'
collection_id = 'sentinel2'
datetime_range = f"{start_date}/{end_date}"

# Construct the search URL
search_url = f"{ogc_api_url}/collections/{collection_id}/items" #items.json for qgis
print(search_url)

# Set query parameters
# Observe that a limit has been set
params = {
    "datetime": datetime_range, #capital D for ms4w - Datetime
     "bbox":",".join(map(str, bbox)),
     "limit":1
}
print(params)

# Download and extract a sentinel 2 SAFE zip
if not os.path.exists('./sentinel_2_data'):
    os.mkdir('./sentinel_2_data')
# Directory to extract files to
extract_to = "./sentinel_2_data"

# Create the directory if it doesn't exist
os.makedirs(extract_to, exist_ok=True)
# Extract all files

def process_product_link(product_link):
    zip_url = product_link
    zip_name = os.path.splitext(os.path.basename(zip_url))[0]
    # Download and extract
    response = requests.get(zip_url)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(extract_to)
        #print(f"Files extracted to '{extract_to}' '{zip_name}'")
        start_directory = extract_to + "/" + zip_name + ".SAFE"
        print(f"Files extracted to '{start_directory}' ")
    else:
        print(f"Failed to download ZIP file. Status code: {response.status_code}")
        
# Make the request
response = requests.get(search_url, params=params)
desired_properties = ["producttype", "acquisition_start", "product_link"]
# Check and parse the response
if response.status_code == 200:
    features = response.json().get("features", [])
    print(f"Found {len(features)} features between {start_date} and {end_date}.")
    print("Product Type","       ", "Acquisition start","          ", "Product Link", )
    for feature in features[:100]:      
        properties = feature.get("properties", {})
        product_type = properties.get('producttype')
        acquisition_start = properties.get('acquisition_start')
        product_link = properties.get('product_link')
        print(product_type,"       ", acquisition_start,"          ", product_link)
        process_product_link(product_link)
else:
    print(f"Failed to retrieve features. Status code: {response.status_code}")
#print(product_link)



#Using one of the results for the perfect demo
#product_link = "https://sentinel-products-ca-mirror.s3.ca-central-1.amazonaws.com/Sentinel-2/S2MSI2A/2025/06/02/S2C_MSIL2A_20250602T175931_N0511_R041_T13UFA_20250602T225512.zip"



