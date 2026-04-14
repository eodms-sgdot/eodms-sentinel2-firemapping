from dateutil.parser import isoparse
import math
import geopandas as gpd
import pandas as pd
from datetime import datetime, timedelta
import requests
import stackstac
import pystac_client
import os
import rasterio
import csv

# Load the shapefile
shapefile_path = "./data/NFDB_poly_20210707_large_fires.shp"
gdf = gpd.read_file(shapefile_path)
gdf_latlon = gdf.to_crs(epsg=4326)

# Download assets
def download_s2_data(s2FileItem, assetName, download_dir):
    asset = s2FileItem.assets[assetName]  # for NBR
    url = asset.href
    filename = os.path.join(download_dir, f"{s2FileItem.id}_{assetName}.tif")
    response = requests.get(url)
    print(f"Downloading {filename}...")
    with open(filename, "wb") as f:
        f.write(response.content)
    print("Download complete.")
    
def search_in_stac_api(bbox, reported_date):
    stac_api_url = 'https://earth-search.aws.element84.com/v1'
    #start_date = reported_date - timedelta(days=15)
    start_date = reported_date + timedelta(days=30)
    stac_start_date = f"{start_date:%Y-%m-%d}T00:00:00Z"
    end_date = reported_date + timedelta(days=60)
    stac_end_date = f"{end_date:%Y-%m-%d}T23:59:59Z"
    max_cloud = 30.0  # percent
    print("starting to search in stac api url")
    print(f"bbox is: {bbox}")
    stac_catalog = pystac_client.Client.open(stac_api_url)
    #optional parameter - intersects instead of bbox
    results = stac_catalog.search(collections=["sentinel-2-l2a"], 
                datetime=[stac_start_date,stac_end_date], 
                bbox=bbox, 
                query={
                    "eo:cloud_cover": {"lte": max_cloud}
                        })
    return results

def process_polygon(polygon, SIZE_HA, SRC_AGENCY, REP_DATE, OUT_DATE):
    print(f"bbox: {polygon.bounds}")
    print(f"Src_Agency: {SRC_AGENCY} Size_ha: {SIZE_HA} Reported_Date: {REP_DATE} Out_Date: {OUT_DATE}")
    bbox = polygon.bounds  
    results = search_in_stac_api(bbox, REP_DATE)
    #search_in_ogc_api(bbox, REP_DATE)
    return results
    
#Have a record of the image collected for each polygon - as a .csv file
resDataFileName = "./Results/postFireImageForNBR.csv"
with open(resDataFileName, mode='w', newline='') as file:
    writer = csv.writer(file)
    # Usage example:
    col_headers = [['FIRE_ID', 'REP_DATE', 'PostFireS2FileName', 'CloudCover', 'BestDate']]
    writer.writerows(col_headers)
    
def write_to_csv(filename, data):
    # 'w' mode creates/overwrites the file, 'a' will append
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        # data should be an iterable of iterables (e.g., list of lists)
        writer.writerows(data)

# -------------------------------------------------
# SCORING FUNCTION
# -------------------------------------------------
def score_item(item, Reported_Date):
    """
    Ranking score:
    1) Temporal distance to reference date (days)
    2) Cloud cover (%)
    """
    item_date = isoparse(item.datetime.isoformat())
    cloud = item.properties.get("eo:cloud_cover", math.inf)
    item_date_only = item_date.date()
    days_from_target = abs((item_date_only - Reported_Date).days)
    print(f"Considering: {item.id} with {days_from_target} days from reported date of fire and {cloud} % cloud") 
    return (cloud, days_from_target)# if you have cloud first, priority would be for cloud in minimalizing

# -------------------------------------------------
# SELECT BEST REFERENCE IMAGE
# -------------------------------------------------
def select_the_best(items, REP_DATE):
    best_item = min(
        items,
        key=lambda item: score_item(item, REP_DATE)
    )
    return best_item

# Iterate through each row (polygon) in the GeoDataFrame
count = 0
print(f"Processing wildfire polygons for year: 2020")        
for idx, row in gdf_latlon.iterrows():
    geometry = row.geometry
    REP_YEAR = row['YEAR']
    if REP_YEAR == 2020:
        #print(f"YEAR:{REP_YEAR}")
        FIRE_ID = row['FIRE_ID']     
        REP_DATE = row['REP_DATE']  # Replace with actual attribute name
        REP_DATE = REP_DATE.date()
        OUT_DATE = row['OUT_DATE'] # pd.isna doesnt work for NaT, is None, IS NULL, =='' doesnt work either, 
        OUT_DATE = OUT_DATE.date()
        SIZE_HA = row['SIZE_HA']
        SRC_AGENCY = row['SRC_AGENCY']        
        if SIZE_HA > 200 and SRC_AGENCY == 'BC':
            s2FileItems = process_polygon(geometry, SIZE_HA, SRC_AGENCY, REP_DATE, OUT_DATE)
            #items = list(s2FileItems.get_items()) # get_items() deprecated
            items = list(s2FileItems.items())
            if not items:
                print(f"No cloud-free images found for: {FIRE_ID}")
            else:
                best_item = select_the_best(items, REP_DATE)
                s2FileItem = best_item
                CloudCover = best_item.properties['eo:cloud_cover']
                BestDate = best_item.datetime.date()
                s2FileName = best_item.id
                print(f"Decision: For {FIRE_ID} reported on {REP_DATE}:")
                print(f"{s2FileName} is the best resource given {CloudCover} % cloud and closest on {BestDate}")
                #------------------------------------------------------------------------------
                # We are going to use the same method as before to download 
                # So we assign the best_item as the s2FilItem then follow the download process
                #------------------------------------------------------------------------------
                
                s2FileNmLower = s2FileName.lower()
                s2FilePath = f"./downloadedData/Sentinel2/stac_api_data/{FIRE_ID}/PostFireImage/{s2FileNmLower}"
                download_dir = s2FilePath
                os.makedirs(download_dir, exist_ok=True)
                                
                # List of Sentinel‑2 asset names you want to download
                asset_names = [
                    "swir22",
                    "nir08",
                    "red",
                    "rededge2",
                    "rededge3",
                    "scl",
                    "visual"
                ]              
                for asset_name in asset_names:
                    if asset_name in s2FileItem.assets:
                        download_s2_data(s2FileItem, asset_name, download_dir)
                    else:
                        print(f"Asset {asset_name} not found in item {s2FileItem.id}")
                              
                table_data = [[FIRE_ID, REP_DATE, s2FileName, CloudCover, BestDate]]
                write_to_csv(resDataFileName, table_data)
               
                
              