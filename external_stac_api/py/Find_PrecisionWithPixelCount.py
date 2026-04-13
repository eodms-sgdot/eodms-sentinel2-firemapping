import csv
import json
import geopandas as gpd
import pandas as pd
import rasterio
from shapely.geometry import mapping, box
from rasterio.mask import mask
import numpy as np
"""
from datetime import datetime, timedelta
import requests
import stackstac
import pystac_client
import os

"""
def bounds_to_geojson(bounds, crs=None):
    minx, miny, maxx, maxy = bounds

    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny]
            ]]
        },
        "properties": {}
    }

    if crs is not None:
        geojson["crs"] = {
            "type": "name",
            "properties": {"name": crs}
        }

    return geojson
    
def count_pixels_in_polygon(raster_path, polygon_gdf):
    """
    Counts pixels in a raster > threshold within a polygon.
    """
    # 1. Load the polygon and the raster
    #gdf = gpd.read_file(shapefile_path)
    
    with rasterio.open(raster_path) as src:
        
        # Reproject polygon
        reprojected_polygon = polygon_gdf.to_crs(src.crs)

        # Fix invalid geometry
        reprojected_polygon["geometry"] = reprojected_polygon.geometry.make_valid()
        geom = reprojected_polygon.geometry.iloc[0]
            
        # Check overlap explicitly
        raster_extent = box(*src.bounds)
        
        if not geom.intersects(raster_extent):
            raise ValueError("Polygon does not overlap raster footprint")
        
        shapes = [mapping(geom)]
        # 2. Mask (crop) the raster with the polygon
        # nodata value is handled automatically to exclude outside areas
        out_image, out_transform = mask(src, shapes, crop=True, nodata=src.nodata)
        band_index = 1
        band = out_image[band_index - 1].astype("float32")
        
        
        if src.nodata is not None:
            band[band == src.nodata] = np.nan

        # 3. Apply threshold condition
        threshold = 0.2
        # Returns True (1) where condition is met, False (0) otherwise
        valid_pixels = (band > threshold) & (~np.isnan(band))
        
        # 4. Count pixels
        pixel_count = np.sum(valid_pixels)
        
    return pixel_count
    #return src.crs

# Load the shapefile
shapefile_path = "../data/NFDB_poly_20210707_large_fires.shp"
#gdf = gpd.read_file(shapefile_path)
gdf = gpd.read_file("../data/NFDB_poly_large_fires.gpkg", layer="NFDB_poly_large_fires_3978")
#gdf_latlon = gdf.to_crs(epsg=4326)
gdfCRS= gdf.crs

# Iterate through each row (polygon) in the GeoDataFrame
count = 0
print(f"Processing wildfire polygons for year: 2020")
resDataFileName = "../Results/resultsImgAnalyzed.csv"


#print(df.columns)
with open(resDataFileName, newline="", encoding="utf-8") as f:
    #reader = csv.DictReader(f)
    df = pd.read_csv(resDataFileName)
    df["numofpixels"] = 0
    for idx, row in df.iterrows():
        Fire_ID = row["FIRE_ID"]
        S2FileName = row["S2FileName"]

        # Example processing step
        print(f"Processing:\n  Fire_ID = {Fire_ID}\n  S2FileName = {S2FileName}")
        target_fire_id = Fire_ID  # example

        gdf_subset = gdf[gdf["FIRE_ID"] == target_fire_id]
        """
        for idx, row in gdf_subset.iterrows():
            fire_geom = row.geometry
        """
        s2FileLower = S2FileName.lower()
        NBRFilePath = f"../downloadedData/Sentinel2/stac_api_data/{s2FileLower}/{s2FileLower}_NBRVegMask.tif"
        NumOfPixels = count_pixels_in_polygon(NBRFilePath, gdf_subset)
        print(f"Number of Pixels {NumOfPixels}")
        df.at[idx, "numofpixels"] = NumOfPixels

        # call your function
        # process_bands(Fire_ID, S2FileName)
df.to_csv(resDataFileName, index=False)