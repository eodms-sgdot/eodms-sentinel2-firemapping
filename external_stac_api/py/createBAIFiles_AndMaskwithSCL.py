# --------------------------------------------------
# IMPORTANT: Run this code is Osgeo4W shell to be able to use gdal or choose rasterio methods.
# --------------------------------------------------

#from osgeo import gdal # You need to run this in OSGEO4W Shell script, because gdal isnt easy to install in v-env
# Enable exceptions (future-proof, removes warning)
#gdal.UseExceptions()

from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt
import os

def CreateBAIFiles(scenes): 
    for scene_id, bands in scenes.items():
        # Ensure all required bands exist
        if not {"nir8a"} <= bands.keys():
            print(f"Skipping {scene_id}: missing nir8a band")
            continue
        elif not {"swir22"}  <= bands.keys():
            print(f"Skipping {scene_id}: missing swir22 band")
            continue
        elif not {"red", "rededge2", "rededge3"}  <= bands.keys():
            print(f"Skipping {scene_id}: missing red bands")
            continue
        """
        if not {"nir8a", "swir22", "red", "rededge2", "rededge3"} <= bands.keys():
            print(f"Skipping {scene_id}: missing bands")
            continue
        """
        bai_scene_dir = input_dir / f"{scene_id}"
        os.makedirs(bai_scene_dir, exist_ok=True)
        bai_path = bai_scene_dir / f"{scene_id}_BAI.tif"

        print(f"Building BAI: {bai_path.name}")
        # --------------------------------------------------
        # Input bands
        # --------------------------------------------------
        B08_path = bands["nir8a"]
        B12_path = bands["swir22"]
        B06_path =  bands["rededge2"]
        B07_path =  bands["rededge3"]

        # --------------------------------------------------
        # Open datasets
        # --------------------------------------------------
        with rasterio.open(B08_path) as ds_B08:
            b08 = ds_B08.read(1).astype(np.float32) #B8A is B08 in external stac api
            profile = ds_B08.profile.copy()
        with rasterio.open(B12_path) as ds_B12:
            b12 = ds_B12.read(1).astype(np.float32)
        with rasterio.open(B06_path) as ds_B06:
            b06 = ds_B06.read(1).astype(np.float32)
        with rasterio.open(B07_path) as ds_B07:
            b07 = ds_B07.read(1).astype(np.float32)
        
        # --------------------------------------------------
        # RED BAND is of higher resolution 10m.
        # It has to be converted to 20m.
        # --------------------------------------------------        
        B04_10m_path =  bands["red"]

        # Open the 20m reference bands
        with rasterio.open(B06_path) as ref_ds:
            ref_transform = ref_ds.transform
            ref_crs = ref_ds.crs
            ref_width = ref_ds.width
            ref_height = ref_ds.height
            ref_profile = ref_ds.profile
        
        # Open the 10m band
        with rasterio.open(B04_10m_path) as src_ds:
            src_data = src_ds.read(1)
            src_transform = src_ds.transform
            src_crs = src_ds.crs

        # Resample 10m to 20m       
        b04_20m = np.zeros((ref_height, ref_width), dtype=np.float32)

        reproject(
            source=src_data,
            destination=b04_20m,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear
        )
        
        #Write the resampled file as a geotiff for later use with 20m resolution
        out_profile = ref_profile.copy()
        out_profile.update(
            dtype=rasterio.float32,
            count=1,
            compress="LZW"
        )
        
        b04_20m_path = bai_scene_dir / f"{scene_id}_b04_20m.tif"
        with rasterio.open(b04_20m_path, "w", **out_profile) as dst:
            dst.write(b04_20m, 1)

        # --------------------------------------------------
        # Avoid invalid math
        # --------------------------------------------------
        eps = 1e-10

        b04_20m = np.maximum(b04_20m, eps)
        #b12_b8a_sum = np.maximum(b12 + b8a, eps) 
        b12_b08_sum = np.maximum(b12 + b08, eps) #B8A is B08 in external stac api
        # --------------------------------------------------
        # Burnt Area Index calculation
        # --------------------------------------------------
        BAIndex = (
            (1.0 - np.sqrt((b06 * b07 * b08) / b04_20m)) #B8A is B08 in external stac api
            *
            ((b12 - b08) / np.sqrt(b12_b08_sum) + 1.0) #B8A is B08 in external stac api
        )

        # --------------------------------------------------
        # Write output GeoTIFF
        # --------------------------------------------------
        
        profile.update(
            driver="GTiff",
            dtype=rasterio.float32,
            count=1,
            compress="LZW"
        )

        with rasterio.open(bai_path, "w", **profile) as out_ds:
            out_ds.write(BAIndex, 1)
    print("Done writing BAIndex files.")
    
# --------------------------------------------------
# Start build the scene set with all bands for creating BAI file
# --------------------------------------------------
input_dir = Path(
    r"..\Sentinel2\stac_api_data"
)

# --------------------------------------------------
# Find all candidate files
# --------------------------------------------------
tifs = list(input_dir.rglob("*.tif"))

# Dictionary: {scene_id: {band: path}}
scenes = {}

for tif in tifs:
    name = tif.name.lower()

    #if name.endswith("_nir8a.tif"):
    if name.endswith("_nir08.tif"): # in external stac its called nir08
        #scene_id = name.replace("_nir8a.tif", "")
        scene_id = name.replace("_nir08.tif", "") # in external stac its called nir08
        band = "nir8a"

    elif name.endswith("_swir22.tif"):
        scene_id = name.replace("_swir22.tif", "")
        band = "swir22"

    elif name.endswith("_red.tif"):
        scene_id = name.replace("_red.tif", "")
        band = "red"
		
    elif name.endswith("_rededge2.tif"):
        scene_id = name.replace("_rededge2.tif", "")
        band = "rededge2"
        
    elif name.endswith("_rededge3.tif"):
        scene_id = name.replace("_rededge3.tif", "")
        band = "rededge3"
        
    else:
        continue

    scenes.setdefault(scene_id, {})[band] = tif

print("Ready with all bands going to create BAI Files")
# --------------------------------------------------
# Create BAI Files
# --------------------------------------------------
#CreateBAIFiles(scenes)

# --------------------------------------------------
# Create a Mask using the SCL file classifications
# --------------------------------------------------
# Sentinel-2 SCL vegetation class
VEGETATION_CLASS = 4
NON_VEGETATED = 5 #important to capture this because after fire this might be barren land
UNCLASSIFIED = 6 #important to capture this because after fire this may be ashes hence unclassified may be

def CreateBAIWithVegMask(scenes):
    for scene_id, bands in scenes.items():
        print(f"Scene_ID is: {scene_id}")
        # Ensure all required bands exist
        if not {"scl"} <= bands.keys():
            print(f"Skipping {scene_id}: missing scl band")
            continue
        elif not {"BAI"} <= bands.keys():
            print(f"Skipping {scene_id}: missing BAI band")
            continue
        # ------------------------------------------------------------------
        # File paths
        # ------------------------------------------------------------------
        bai_scene_dir = input_dir / f"{scene_id}"
        os.makedirs(bai_scene_dir, exist_ok=True)
        bai_path = bai_scene_dir / f"{scene_id}_BAI.tif"
        scl_path = bai_scene_dir / f"{scene_id}_scl.tif"
        baiVegMask_path = bai_scene_dir / f"{scene_id}_BAIVegMask.tif"
        print(f"Building BAI Masked Product: {baiVegMask_path.name}")

        # ------------------------------------------------------------------
        # Read SCL and create vegetation mask
        # ------------------------------------------------------------------
        with rasterio.open(scl_path) as scl_src:
            scl = scl_src.read(1)
            scl_meta = scl_src.meta.copy()

        # Create boolean mask: True where vegetation
        #veg_mask = scl == VEGETATION_CLASS
        
        # SCL classes to KEEP
        KEEP_CLASSES = [4, 5, 7] #Veg, bare earth, unclassified
        mask = np.isin(scl, KEEP_CLASSES)


        # ------------------------------------------------------------------
        # Read BAI and apply mask
        # ------------------------------------------------------------------
        with rasterio.open(bai_path) as bai_src:
            bai = bai_src.read(1)
            bai_meta = bai_src.meta.copy()
            bai_nodata = bai_src.nodata

        # Ensure nodata value exists
        if bai_nodata is None:
            bai_nodata = -9999
            bai_meta["nodata"] = bai_nodata

        # Apply mask
        bai_veg = np.where(mask, bai, bai_nodata)
        # True where SCL is 4, 5, or 7
        
        
        # ------------------------------------------------------------------
        # Write masked BAI to disk
        # ------------------------------------------------------------------
        bai_meta.update({
            "dtype": bai_veg.dtype,
            "count": 1
        })

        with rasterio.open(baiVegMask_path, "w", **bai_meta) as bai_dst:
            bai_dst.write(bai_veg, 1)

        print("Vegetation-masked BAI saved to:", baiVegMask_path)
 
# -----------------------------------------------------------------------------
# Build scenes only with the pre created BAI files and the SCL to initiate masking
# --------------------------------------------------------------------------------
for tif in tifs:
    name = tif.name.lower()

    if name.endswith("_scl.tif"):
        scene_id = name.replace("_scl.tif", "")
        band = "scl"
    elif name.endswith("_bai.tif"):
        scene_id = name.replace("_bai.tif", "")
        band = "BAI"
    else:
        continue

    scenes.setdefault(scene_id, {})[band] = tif

# --------------------------------------------------
# Create BAI Files masked with the classes 4,5,7
# --------------------------------------------------
CreateBAIWithVegMask(scenes)