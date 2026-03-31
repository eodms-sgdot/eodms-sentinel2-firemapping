import os
import json
import geopandas as gpd
import requests

import io
import zipfile

import rasterio
from rasterio.shutil import copy as rio_copy
from rasterio.enums import Resampling

import matplotlib.pyplot as plt
import numpy as np

import sys


# Utility functions
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


def find_band_jp2file_make_cog(directory_to_search, band_to_search):
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

    # Output COG file path
    output_cog = band_file_dir + "/" + band_filename + "_cog.tif"

    # Define COG profile
    cog_profile = {
        'driver': 'COG',
        'compress': 'deflate',
        'blocksize': 512,
        'overview_resampling': Resampling.nearest
    }

    # Convert JP2 to COG
    rio_copy(input_jp2, output_cog,  **cog_profile)

    print(f"Converted {input_jp2} to Cloud Optimized GeoTIFF: {output_cog}")
    return output_cog

def plot_RGB_cog(rgb, start_directory):
    # Normalize to [0, 1] for display
    rgb_normalized = rgb.astype(np.float32)
    rgb_normalized /= rgb_normalized.max()

    # Plot using matplotlib
    plt.figure(figsize=(10, 10))
    plt.imshow(rgb_normalized)
    plt.title("RGB Composite")
    plt.axis('off')
    #plt.show()
    
    # Save as JPG
    filename = os.path.basename(start_directory)
    filename_noExt = os.path.splitext(filename)[0]
    outputImgPath = "./" + "Result_Images" + "/" + "FireComposite_Images" + "/" + filename_noExt + "_B12B8AB04_asRGB.jpg"
    plt.savefig(outputImgPath, format="jpg", dpi=300)


def plot_band_cog(band_cog_file, start_directory):
    # Path to your COG file
    cog_path = band_cog_file

    # Open and read the first band
    with rasterio.open(cog_path) as src:
        band1 = src.read(1)

    # Plot the band
    plt.figure(figsize=(10, 8))
    plt.imshow(band1, cmap='gray')
    #aoi_gdf.to_crs(utm_crs).plot(ax=axes[0], facecolor='none', edgecolor='brown', linewidth=2)
    plt.colorbar(label='Pixel values')
    plt.title('Single Band Visualization of COG')
    plt.xlabel('Column Index')
    plt.ylabel('Row Index')
    #plt.show()
    
    # Save as JPG
    filename = os.path.basename(start_directory)
    filename_noExt = os.path.splitext(filename)[0]
    outputImgPath = "./" + "Result_Images" + "/" + "SWIR_Images" + "/" + filename_noExt +  "_SWIR.jpg"
    plt.savefig(outputImgPath, format="jpg", dpi=300)


def main():
    if len(sys.argv) < 2:
        print("Usage: python another_script.py <folder_path>")
        return

    folder_path = sys.argv[1]
    print(f"External script received folder: {folder_path}")
    start_directory = folder_path
    print ("directory is " + start_directory)
    img_data_path = find_img_data_dir(start_directory)
    # Add whatever processing logic you want here
    # Example:
    # process_files_in(folder_path)
    if img_data_path:
        print(f"'img_data' directory found at: {img_data_path}")
    else:
        print("No 'img_data' directory found.")   
    band_to_search = "_B12"
    B12_cog = find_band_jp2file_make_cog(img_data_path, band_to_search)

    band_to_search = "_B8A"
    B8A_cog = find_band_jp2file_make_cog(img_data_path, band_to_search)

    #B04 is found both in 10m resolution and 20m resolution
    #we need to get all bands in same resolution so use the one at 20m resolution
    img_data_path = img_data_path + "/R20m"
    band_to_search = "_B04"
    B04_cog = find_band_jp2file_make_cog(img_data_path, band_to_search)

    # Load each band from its respective COG file
    with rasterio.open(B12_cog) as red_src:
        red = red_src.read(1)

    with rasterio.open(B8A_cog) as green_src:
        green = green_src.read(1)

    with rasterio.open(B04_cog) as blue_src:
        blue = blue_src.read(1)

    # Stack into RGB format
    rgb = np.stack([red, green, blue], axis=-1)
    
    plot_RGB_cog(rgb, start_directory)
    #plot_band_cog(B8A_cog) # NIR
    plot_band_cog(B12_cog, start_directory) # SWIR

if __name__ == "__main__":
    main()
