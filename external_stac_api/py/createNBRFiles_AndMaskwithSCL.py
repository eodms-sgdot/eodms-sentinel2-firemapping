# --------------------------------------------------
# IMPORTANT: Run this code is Osgeo4W shell to be able to use gdal or choose rasterio methods.
# --------------------------------------------------

#from osgeo import gdal # You need to run this in OSGEO4W Shell script, because gdal isnt easy to install in v-env
# Enable exceptions (future-proof, removes warning)
#gdal.UseExceptions()

from pathlib import Path
import numpy as np
import rasterio
import matplotlib.pyplot as plt
import os

def CreateNBRFiles(scenes): 
    for scene_id, bands in scenes.items():

        # Ensure all required bands exist
        if not {"nir8a", "swir22"} <= bands.keys():
            print(f"Skipping {scene_id}: missing bands")
            continue
        nbr_scene_dir = input_dir / f"{scene_id}"
        os.makedirs(nbr_scene_dir, exist_ok=True)
        nbr_path = nbr_scene_dir / f"{scene_id}_NBR.tif"

        print(f"Building NBR: {nbr_path.name}")
        # --------------------------------------------------
        # Input bands
        # --------------------------------------------------
        B08_path = bands["nir8a"]
        B12_path = bands["swir22"]

        # --------------------------------------------------
        # Open datasets
        # --------------------------------------------------
        with rasterio.open(B08_path) as ds_B08:
            b08 = ds_B08.read(1).astype(np.float32)
            profile = ds_B08.profile.copy()
        with rasterio.open(B12_path) as ds_B12:
            b12 = ds_B12.read(1).astype(np.float32)


        # --------------------------------------------------
        # Avoid division by zero
        # --------------------------------------------------
        eps = 1e-10
        denominator = np.maximum(b08 + b12, eps)

        # --------------------------------------------------
        # NBR calculation
        # --------------------------------------------------
        nbr = (b08 - b12) / denominator

        # --------------------------------------------------
        # Write output GeoTIFF
        # --------------------------------------------------
        
        profile.update(
            driver="GTiff",
            dtype=rasterio.float32,
            count=1,
            compress="LZW"
        )

        with rasterio.open(nbr_path, "w", **profile) as out_ds:
            pass  # data will be written later using out_ds.write(...)
            out_ds.write(nbr, 1)
    print("Done creating NBR Files.")
    
# --------------------------------------------------
# Start build the scene set with all bands for creating NBR file
# --------------------------------------------------
input_dir = Path(
    r"C:\NRCanWorkData\EODMS_CCRS\EODMS_FireS2_Res\Sentinel2\stac_api_data"
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
		
    else:
        continue

    scenes.setdefault(scene_id, {})[band] = tif

# --------------------------------------------------
# Create NBR Files
# --------------------------------------------------
CreateNBRFiles(scenes)

# --------------------------------------------------
# Create a Mask using the SCL file classifications
# --------------------------------------------------
# Sentinel-2 SCL vegetation class
VEGETATION_CLASS = 4
NON_VEGETATED = 5 #important to capture this because after fire this might be barren land
UNCLASSIFIED = 6 #important to capture this because after fire this may be ashes hence unclassified may be

def CreateNBRWithVegMask(scenes):
    for scene_id, bands in scenes.items():
        print(f"Scene_ID is: {scene_id}")
        # Ensure all required bands exist
        #if not {"scl", "NBR"} <= bands.keys():
        #    print(f"Skipping {scene_id}: missing bands")
        #    continue
        # ------------------------------------------------------------------
        # File paths
        # ------------------------------------------------------------------
        nbr_scene_dir = input_dir / f"{scene_id}"
        os.makedirs(nbr_scene_dir, exist_ok=True)
        nbr_path = nbr_scene_dir / f"{scene_id}_NBR.tif"
        scl_path = nbr_scene_dir / f"{scene_id}_scl.tif"
        nbrVegMask_path = nbr_scene_dir / f"{scene_id}_NBRVegMask.tif"
        print(f"Building NBR: {nbr_path.name}")

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
        # Read NBR and apply mask
        # ------------------------------------------------------------------
        with rasterio.open(nbr_path) as nbr_src:
            nbr = nbr_src.read(1)
            nbr_meta = nbr_src.meta.copy()
            nbr_nodata = nbr_src.nodata

        # Ensure nodata value exists
        if nbr_nodata is None:
            nbr_nodata = -9999
            nbr_meta["nodata"] = nbr_nodata

        # Apply mask
        nbr_veg = np.where(mask, nbr, nbr_nodata)
        # True where SCL is 4, 5, or 7
        
        
        # ------------------------------------------------------------------
        # Write masked NBR to disk
        # ------------------------------------------------------------------
        nbr_meta.update({
            "dtype": nbr_veg.dtype,
            "count": 1
        })

        with rasterio.open(nbrVegMask_path, "w", **nbr_meta) as dst:
            dst.write(nbr_veg, 1)

        print("Vegetation-masked NBR saved to:", nbrVegMask_path)
 
# -----------------------------------------------------------------------------
# Build scenes only with the pre created NBR files and the SCL to initiate masking
# --------------------------------------------------------------------------------
for tif in tifs:
    name = tif.name.lower()

    if name.endswith("_scl.tif"):
        scene_id = name.replace("_scl.tif", "")
        band = "scl"
    elif name.endswith("_NBR.tif"):
        scene_id = name.replace("_NBR.tif", "")
        band = "NBR"
    else:
        continue

    scenes.setdefault(scene_id, {})[band] = tif

# --------------------------------------------------
# Create NBR Files masked with the classes 4,5,7
# --------------------------------------------------
CreateNBRWithVegMask(scenes)