import os
import geopandas as gpd
import requests
import math
import io
import zipfile

import rasterio
from rasterio.shutil import copy as rio_copy
from rasterio.enums import Resampling

#import matplotlib.pyplot as plt
import numpy as np

#For finding cloud level
import xml.etree.ElementTree as ET
import glob
import shutil # to delete if cloud level is more than 30%
import stat #for read only deletions
import csv # for cloud level records

def bbox_from_point(lat, lon, half_size_km=1):
    # Convert km to degrees
    d_lat = half_size_km / 111.0
    d_lon = half_size_km / (111.0 * math.cos(math.radians(lat)))

    min_lat = lat - d_lat
    max_lat = lat + d_lat
    min_lon = lon - d_lon
    max_lon = lon + d_lon

    return [min_lon, min_lat, max_lon, max_lat]
    
 # Utility functions
def get_bbox(geojson_path):
    """Extracts bounding box coordinates from an input vector data file"""
    gdf = gpd.read_file(geojson_path) # you can use a .shp file also here directly

    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    bbox = tuple([float(b) for b in gdf.total_bounds])

    return bbox

# ---------------------------------------------
# Function to find cloud percentage to decide whether to create firemap
# ---------------------------------------------
def find_cloud_level(start_directory):
    
    xml_file = None

    for root, dirs, files in os.walk(start_directory):
        for file in files:
            if file in ("MTD_MSIL2A.xml", "MTD_MSIL1C.xml"):
                xml_file = os.path.join(root, file)
                break
        if xml_file: #you get inspire.xml in this not useful - check above logic
            break
    #"MTD_MSIL2A.xml"
    #--- 1. Find product XML (cloud info) ---
    print(f"-------- Extracting cloud level info from {xml_file}")
    tree = ET.parse(xml_file)
    root = tree.getroot()
    cloud = float(root.find(".//Cloud_Coverage_Assessment").text)
    
    # MTD_TL.xml
     #--- 2. Find product XML (CRS info) ---
    tile_xml = glob.glob(os.path.join(start_directory, "**", "MTD_TL.xml"), recursive=True)

    crs = None
    if tile_xml:
        tree = ET.parse(tile_xml[0])
        root = tree.getroot()
        #crs = root.find(".//HORIZONTAL_CS_CODE").text
        
        # handle namespace
        ns = {'n1': root.tag.split('}')[0].strip('{')}

        node = root.find(".//n1:HORIZONTAL_CS_CODE", ns)
        if node is None:  # fallback if namespace not required
            node = root.find(".//HORIZONTAL_CS_CODE")

        if node is not None:
            crs = node.text   # e.g. "EPSG:32632"
        
    #print (f"-------- CRS of this image is: {crs}")
    if cloud < 30:
        print("-------- ✅ Keep this scene")
    else:
        print("-------- ❌ Too cloudy")
    return crs,cloud

# ---------------------------------------------
# Function to download the s3 data locally to process and get cloud and crs from XML before July 20 2026
# ---------------------------------------------
def process_product_link(product_link, firename):
    zip_url = product_link
    # Directory to extract files to
    extract_to = "./sentinel_2_data/2026_Fires/" + firename
    # Download and extract a sentinel 2 SAFE zip
    os.makedirs(extract_to, exist_ok=True)

    # Extract all files
    zip_name = os.path.splitext(os.path.basename(zip_url))[0]
    # Download and extract
    response = requests.get(zip_url)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(extract_to)
        start_directory = extract_to + "/" + zip_name + ".SAFE"
        print(f"-------- Files extracted to '{start_directory}' ")
        crs, cloud_level = find_cloud_level(start_directory)
        return start_directory, cloud_level, crs
    else:
        print(f"Failed to download ZIP file. Status code: {response.status_code}")
        return none

# ---------------------------------------------
# Function to download the s3 data locally to process, cloud cover property directly from STAC
# ---------------------------------------------
def process_prod_link(product_link, firename):
    zip_url = product_link
    # Directory to extract files to
    extract_to = "./sentinel_2_data/2026_Fires/" + firename
    # Download and extract a sentinel 2 SAFE zip
    os.makedirs(extract_to, exist_ok=True)

    # Extract all files
    zip_name = os.path.splitext(os.path.basename(zip_url))[0]
    # Download and extract
    response = requests.get(zip_url)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(extract_to)
        start_directory = extract_to + "/" + zip_name + ".SAFE"
        print(f"-------- Files extracted to '{start_directory}' ")
        #cloud_level from property
        #crs from rasterio.open function
        #crs, cloud_level = find_cloud_level(start_directory)
        return start_directory
    else:
        print(f"Failed to download ZIP file. Status code: {response.status_code}")
        return none

def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)
# download functions stop until there
# now process function starts
def find_img_data_dir(start_path):
    for root, dirs, files in os.walk(start_path):
        if "IMG_DATA" in dirs:
            return os.path.join(root, "IMG_DATA")
    return None

def find_file_by_band_name(search_dir, band_to_search):
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if band_to_search in file:
                #return os.path.join(root, file)
                return root, file
    return None

def find_band_jp2file_make_cog(directory_to_search, band_to_search, safeFileName, firename):
    band_file_dir, found_file = find_file_by_band_name(directory_to_search, band_to_search)
    band_filename = os.path.splitext(os.path.basename(found_file))[0]
    if found_file:
        print(f"File found: {found_file}")
        print(f"Base name of file: {band_filename}")
        print(f"Directory of file: {band_file_dir}")
    else:
        print("No matching file found.")
     # Input JP2 file path
    input_jp2 = band_file_dir + "/" + band_filename + ".jp2"
    
    with rasterio.open(input_jp2) as src:
        jp2_crs = src.crs
        cog_profile = src.profile.copy()

    #print(f"JP2 CRS is {jp2_crs}")

    # Output COG file path
    output_dir = os.path.join(".", "Result_Images", "Input_COG_Images", firename, safeFileName)
    
    # Create folders if they don't exist
    os.makedirs(output_dir, exist_ok=True)

    
    output_cog = os.path.join(
        output_dir,
        band_filename + "_cog.tif"
    )
    
    # Define COG profile
    cog_profile.update = {
        'driver': 'COG',
        'compress': 'deflate',
        'blocksize': 512,
        'overview_resampling': Resampling.nearest
    }

    # Convert JP2 to COG
    rio_copy(input_jp2, output_cog,  **cog_profile)

    print(f"Converted {input_jp2} to Cloud Optimized GeoTIFF: {output_cog}")
    return output_cog

def get_bands_as_cogs(bands, inputDataDir, firename):
    img_data_path = find_img_data_dir(inputDataDir)
    safeFileName_withSAFE_Ext = os.path.basename(inputDataDir)
    safeFileName = os.path.splitext(safeFileName_withSAFE_Ext)[0]
    if img_data_path:
        print(f"'img_data' directory found at: {img_data_path}")
    else:
        print("No 'img_data' directory found.")
    
    results = {}
    
    for band in bands:
        if band == "B04":
            path = img_data_path + "/R20m"
        else:
            path = img_data_path
    
        results[band] = find_band_jp2file_make_cog(path, band, safeFileName, firename)
        
    return results
    
def makeRGBComposite(red_band, green_band, blue_band):
    # Load each band from its respective COG file
    with rasterio.open(red_band) as red_src:
        red = red_src.read(1)
        #print(f"The CRS of the COG file is {red_src.crs}")
        #to resample B09 (using B12 - red)from 60m to 20m
        ref_profile = red_src.profile
        ref_transform = red_src.transform
        ref_shape = (red_src.height, red_src.width)
    
    
    with rasterio.open(green_band) as green_src:
        green = green_src.read(1)
    #with rasterio.open(B8A_cog) as green_src:
        #green = green_src.read(1)
    
    #resample from 60m to 20m using B12 profile
    with rasterio.open(blue_band) as blue_src:
        blue = blue_src.read(
            1,
            out_shape=ref_shape,
            resampling=Resampling.bilinear  # or nearest
        )
    #with rasterio.open(B04_cog) as blue_src:
        #blue = blue_src.read(1)
    
    # Stack into RGB format
    rgb = np.stack([red, green, blue], axis=-1)
    rgb_forTif = np.stack([red, green, blue], axis=0)
    return rgb, rgb_forTif
    
def save_to_GeoTif(rgb_forTif, compositeType, output_dir, profile_ref_cog):
    #output_dir already includes the correct path
    #filename = os.path.basename(start_directory)
    #filename_noExt = os.path.splitext(filename)[0]
    #output_dir = os.path.join(".", "Result_Images", "FireComposite_Images", filename_noExt)
    
    #print(f"the profile cog file is: {profile_ref_cog}")
    
    productNameDerive = os.path.basename(profile_ref_cog)
    productNameToAdd = productNameDerive.split("_B")[0]

    # Create folders if they don't exist
    os.makedirs(output_dir, exist_ok=True)

    
    RGB_output_path = os.path.join(
        output_dir,
        productNameToAdd + "_" + compositeType + "_cog.tif"
    )

    B12_cog = profile_ref_cog
    with rasterio.open(B12_cog) as src:
        profile = src.profile

    profile.update(
        driver="GTiff",
        count=3,
        dtype=rgb_forTif.dtype,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        compress="deflate",
        interleave="pixel"
    )

    with rasterio.open(RGB_output_path, "w", **profile) as dst:
        dst.write(rgb_forTif)

        # Build overviews (important for COG)
        dst.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.average)
        dst.update_tags(ns="rio_overview", resampling="average")

    print(f"Saved {compositeType} - RGB GeoTiff to: {RGB_output_path}")
    return RGB_output_path
#------------------------------------------------------------------------------
# Function to have a record of the image collected for each polygon - as a .csv file
#-------------------------------------------------------------------------------
def start_a_new_csv_record(resDataFileName):
    
    # Create parent directory if it doesn't exist
    os.makedirs(os.path.dirname(resDataFileName), exist_ok=True)
    
    with open(resDataFileName, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Usage example: When we are running the code, For what project purpose, Which files got downloaded, what was the cloud, did we process it or not
        col_headers = [['ProcessDateTime', 'FireProjectName', 'S2FileName', 'CloudPercent', 'Decision']]
        writer.writerows(col_headers)

def write_to_csv(filename, data):
    # 'w' mode creates/overwrites the file
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        # data should be an iterable of iterables (e.g., list of lists)
        writer.writerows(data)