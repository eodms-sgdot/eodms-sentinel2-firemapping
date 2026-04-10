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
shapefile_path = "C:/NRCanWorkData/EODMS_CCRS/EODMS_Jupyter_data/NFDB_poly_large_fires/NFDB_poly_20210707_large_fires.shp"
gdf = gpd.read_file(shapefile_path)
gdf_latlon = gdf.to_crs(epsg=4326)

# Download assets
#download_dir = r"C:\NRCanWorkData\EODMS_CCRS\EODMS_Jupyter_Data\Sentinel2\BC_2020_LargeFires200Ha"
#os.makedirs(download_dir, exist_ok=True)
def download_s2_data(s2FileItem, assetName, download_dir):
    asset = s2FileItem.assets[assetName]  # for NBR
    url = asset.href
    filename = os.path.join(download_dir, f"{s2FileItem.id}_{assetName}.tif")
    response = requests.get(url)
    print(f"Downloading {filename}...")
    with open(filename, "wb") as f:
        f.write(response.content)
    #filename_fireComposite_VRT = os.path.join(download_dir, f"{item.id}_fireComposite.tif.vrt")
    #make_fireComposite_VRT_withGDAL(filename_swir22, filename_nir8A, filename_red, filename_fireComposite_VRT)
    print("Download complete.")

def search_in_stac_api(bbox, reported_date):
    stac_api_url = 'https://earth-search.aws.element84.com/v1'
    stac_start_date = f"{reported_date:%Y-%m-%d}T00:00:00Z"
    end_date = reported_date + timedelta(days=7)
    stac_end_date = f"{end_date:%Y-%m-%d}T23:59:59Z"
    print("starting to search in stac api url")
    print(f"bbox is: {bbox}")
    stac_catalog = pystac_client.Client.open(stac_api_url)
    results = stac_catalog.search(collections=["sentinel-2-l2a"], datetime=[stac_start_date,stac_end_date], bbox=bbox)
    return results
    
 # Define your custom function
def process_polygon(polygon, SIZE_HA, SRC_AGENCY, REP_DATE, OUT_DATE):
    # Example operation: print area and attributes
    #print(f"Area: {polygon.area}")
    print(f"bbox: {polygon.bounds}")
    print(f"Src_Agency: {SRC_AGENCY} Size_ha: {SIZE_HA} Reported_Date: {REP_DATE} Out_Date: {OUT_DATE}")
    bbox = polygon.bounds
    
    results = search_in_stac_api(bbox, REP_DATE)
    #search_in_ogc_api(bbox, REP_DATE)
    return results

#Have a record of the image collected for each polygon - as a .csv file
resDataFileName = "C:/NRCanWorkData/EODMS_CCRS/EODMS_FireS2_Res/Results/resultsImgAnalyzed.csv"
with open(resDataFileName, mode='w', newline='') as file:
    writer = csv.writer(file)
    # Usage example:
    col_headers = [['FIRE_ID', 'SIZE_HA', 'SRC_AGENCY', 'REP_DATE', 'OUT_DATE', 'S2FileName']]
    writer.writerows(col_headers)

def write_to_csv(filename, data):
    # 'w' mode creates/overwrites the file
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        # data should be an iterable of iterables (e.g., list of lists)
        writer.writerows(data)

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
            for s2FileItem in s2FileItems.items():
                s2FileName = s2FileItem.id
                s2FileNmLower = s2FileName.lower()
                s2FilePath = f"C:/NRCanWorkData/EODMS_CCRS/EODMS_FireS2_Res/Sentinel2/stac_api_data/{s2FileNmLower}"
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
                table_data = [[FIRE_ID, SIZE_HA, SRC_AGENCY, REP_DATE, OUT_DATE, s2FileName]]
                write_to_csv(resDataFileName, table_data)

            count = count + 1
            #print(f"{count}: Src_Agency: {SRC_AGENCY} Size_ha: {SIZE_HA} Reported_Date: {REP_DATE} Out_Date: {OUT_DATE}")
print(f"Total number of polygons is:  {count}")