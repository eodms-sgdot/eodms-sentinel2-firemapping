import os
import requests
import io
import zipfile

import rasterio
from rasterio.shutil import copy as rio_copy
from rasterio.enums import Resampling

import boto3
from io import StringIO
import csv 
# for cloud level records
import xml.etree.ElementTree as ET
import glob

#for counting active fire pixels
import numpy as np

s3 = boto3.client("s3")
bucket_name = "s2-fire-ard"

def start_a_new_activeFire_csv_record(resDataFileName):
    s3_key = resDataFileName
    csv_buffer = StringIO() #RAM buffer
    writer = csv.writer(csv_buffer)
    writer.writerow([
    'ProcessDateTime',
    'FireProjectName',
    'S2FileName',
    'CloudPercent',
    'activeFirePixels',
    'Decision'
    ])

    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
        )
    print(f"CSV created in s3://{bucket_name}/{s3_key}")   

def write_to_csv(filename, data):
    key = filename

    # Read existing CSV
    obj = s3.get_object(Bucket=bucket_name, Key=key)
    existing_csv = obj['Body'].read().decode('utf-8')

    # Load into buffer
    buffer = StringIO(existing_csv)

    # Move cursor to end
    buffer.seek(0, 2)

    writer = csv.writer(buffer)

    writer.writerow(data)
    # Upload updated CSV
    s3.put_object(
    Bucket=bucket_name,
    Key=key,
    Body=buffer.getvalue(),
    ContentType='text/csv'
    )
# ---------------------------------------------
# Function to download the s3 data locally to process
# ---------------------------------------------
def process_product_link(product_link, firename):
    zip_url = product_link
    # Directory to extract files to
    extract_to = f"/tmp/sentinel_2_data/2026_Fires/{firename}"
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
# Function to find the image data directory in the .SAFE folder
# Called by get_bands_as_cogs(...)
# Returns img_data path
# ---------------------------------------------
def find_img_data_dir(start_path):
    for root, dirs, files in os.walk(start_path):
        if "IMG_DATA" in dirs:
            return os.path.join(root, "IMG_DATA")
    return None

# ---------------------------------------------
# Function to find the specific band inside image data directory in the .SAFE folder
# Called by find_band_jp2file_make_cog(..)
# Returns band_file_root_directory and band_file
# ---------------------------------------------
def find_file_by_band_name(search_dir, band_to_search):
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if band_to_search in file:
                #return os.path.join(root, file)
                return root, file
    return None

# ---------------------------------------------
# Function to find the band in the image data directory and make .jp2 into .cog
# Called by get_bands_as_cogs(...)
# Returns .cog of the band_file
# ---------------------------------------------
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
    
    #with rasterio.open(input_jp2) as src:
        #jp2_crs = src.crs
    
     # Output COG file path
    output_dir = (
    f"/tmp/Result_Images/Input_COG_Images/{firename}/{safeFileName}")
    # Create folders if they don't exist
    os.makedirs(output_dir, exist_ok=True)

    local_output_cog = os.path.join(
        output_dir,
        band_filename + "_cog.tif"
    )

    # Convert JP2 to COG
    rio_copy(
        input_jp2, 
        local_output_cog, 
        driver = 'COG',
        compress = 'deflate',
        blocksize = 512,
        overview_resampling = Resampling.nearest
        )
    print(f"Converted {input_jp2} to Cloud Optimized GeoTIFF: {local_output_cog}")
    numberOfActiveFirePixels = findIfActiveFire(local_output_cog)
    date_str = safeFileName[11:19] # 20260804
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]
    if numberOfActiveFirePixels > 10:
        print("Saving COG to S3 for analysis because there is more than (10 pixels) 100 sq.m of active fire")    
        s3.upload_file(
            local_output_cog,
            "s2-fire-ard",
            f"Result_Images/Input_COG_Images/{year}/{month}/{day}/{safeFileName}/{band_filename}_cog.tif"
            )
    return local_output_cog

# ---------------------------------------------
# Function to return a list of cog band files after converting .jp2 in SAFE into .cog
# Called by watch_function (...)
# Returns a list of .cog of the bands
# ---------------------------------------------        
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
    print(f"-------- Extracting cloud level info from {xml_file}")
    tree = ET.parse(xml_file)
    root = tree.getroot()
    cloud = float(root.find(".//Cloud_Coverage_Assessment").text)
    
    # --- 1. Find product XML (cloud info) ---
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
        print("-------- ✅ Cloud less than 30%")
    else:
        print("-------- ❌ Too cloudy")
    return crs,cloud
    
def findIfActiveFire(SWIR_band_12):
    threshold = 10000 #expecting that there is active fire above this value
    with rasterio.open(SWIR_band_12) as src:
        data = src.read(1, masked=True)       
        countOfFirePixels = np.count_nonzero(data > threshold)
        if countOfFirePixels > 10: 
             print(f"Active Fire Detected in more than 100 sq.m: Pixels above {threshold}: {countOfFirePixels}")
        else:
            print(f"No active fire greater than 100 sq.m in this image. Count of fire pixels: {countOfFirePixels}")
        return countOfFirePixels