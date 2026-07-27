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
import sys 
#-------------------------------------------------------------
# This code uses the COG tif created from SAFE files at EODMS
# So the band names would be different from the element 84 sets
# nir8a = B8A
# swir22 = B12
#-------------------------------------------------------------
def CreateNBRFiles(scenes, output_dir):     
    for scene_id, bands in scenes.items():
        # Ensure all required bands exist
        if not {"b8a", "b12"} <= bands.keys():
            print(f"Skipping {scene_id}: missing bands")
            continue

        # --------------------------------------------------
        # Input bands
        # --------------------------------------------------
        b8a_path = bands["b8a"]
        b12_path = bands["b12"]
        
        # --------------------------------------------------
        # Output NBR to the same location
        # --------------------------------------------------
        nbr_scene_dir = b8a_path.parent
        #nbr_scene_dir = output_dir / f"{scene_id}"
        #os.makedirs(nbr_scene_dir, exist_ok=True)
        nbr_path = output_dir / f"{scene_id}_NBR.tif"
        os.makedirs(output_dir, exist_ok=True)
        print(f"Building NBR: {nbr_path.name}")
        # --------------------------------------------------
        # Open datasets
        # --------------------------------------------------
        with rasterio.open(b8a_path) as ds_b8a:
            b8a = ds_b8a.read(1).astype(np.float32)
            profile = ds_b8a.profile.copy()
        with rasterio.open(b12_path) as ds_b12:
            b12 = ds_b12.read(1).astype(np.float32)


        # --------------------------------------------------
        # Avoid division by zero
        # --------------------------------------------------
        eps = 1e-10
        denominator = np.maximum(b8a + b12, eps)

        # --------------------------------------------------
        # NBR calculation
        # --------------------------------------------------
        nbr = (b8a - b12) / denominator

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
    print(f"Done creating NBR Files and saved in {output_dir}.")

def CreateNBRWithVegMask(scenes, output_dir):
    for scene_id, bands in scenes.items():
        print(f"Scene_ID is: {scene_id}")
        # Ensure all required bands exist
        #if not {"scl", "NBR"} <= bands.keys():
        #    print(f"Skipping {scene_id}: missing bands")
        #    continue
        # ------------------------------------------------------------------
        # File paths
        # ------------------------------------------------------------------
        # --------------------------------------------------
        # Output NBR to the same location
        # --------------------------------------------------
        scl_path = bands["scl"]
        nbr_scene_dir = scl_path.parent
        os.makedirs(nbr_scene_dir, exist_ok=True)
        nbr_path = output_dir / f"{scene_id}_NBR.tif"
        #scl_path = nbr_scene_dir / f"{scene_id}_SCL_20m_cog.tif"
        nbrVegMask_path = output_dir / f"{scene_id}_NBRMaskedCls4_5_7.tif"
        #os.makedirs(nbrVegMask_path, exist_ok=True)
        print(f"Masking NBR: {nbr_path.name}")

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

        print("Classes 4,5,7 masked NBR saved to:", nbrVegMask_path)
        return nbrVegMask_path

def createNBR(fireProjectName, outputdir_zipname):
    print("Running NBR processing...")
    # your code
    
    # --------------------------------------------------
    # Start build the scene set with all bands for creating NBR file
    # --------------------------------------------------
    input_dir = Path(".", "Result_Images", "Input_COG_Images", fireProjectName, outputdir_zipname)
    #input_dir = Path(f"./Result_Images/Input_COG_Images/{outputdir_zipname}")
    print(f"input directory: {input_dir}")
    output_dir = Path(".", "Result_Images", "NBR_Images", fireProjectName, outputdir_zipname)
    #output_dir = Path(f"./Result_Images/NBR_Images/{outputdir_zipname}")
    print(f"output directory: {output_dir}")
    # --------------------------------------------------
    # Find all candidate files
    # --------------------------------------------------
    tifs = list(input_dir.rglob("*.tif"))
    print("Tifs that were found are:")
    print(tifs)
    # Dictionary: {scene_id: {band: path}}
    scenes = {}

    for tif in tifs:
        name = tif.name.lower() #lower case recommended
        #if name.endswith("_nir8a.tif"):
        if name.endswith("_b8a_20m_cog.tif"): # in external stac its called nir08
            #scene_id = name.replace("_nir8a.tif", "")
            scene_id = name.replace("_b8a_20m_cog.tif", "") # in external stac its called nir08
            band = "b8a"

        elif name.endswith("_b12_20m_cog.tif"):
            scene_id = name.replace("_b12_20m_cog.tif", "")
            band = "b12"

        elif name.endswith("_b04_20m_cog.tif"):
            scene_id = name.replace("_b04_20m_cog.tif", "")
            band = "b04"
            
        else:
            continue

        scenes.setdefault(scene_id, {})[band] = tif
        print(scenes)

    # --------------------------------------------------
    # Create NBR Files
    # --------------------------------------------------
    CreateNBRFiles(scenes, output_dir)

    # --------------------------------------------------
    # Create a Mask using the SCL file classifications
    # --------------------------------------------------
    # Sentinel-2 SCL vegetation class
    VEGETATION_CLASS = 4
    NON_VEGETATED = 5 #important to capture this because after fire this might be barren land
    UNCLASSIFIED = 6 #important to capture this because after fire this may be ashes hence unclassified may be
 
    # -----------------------------------------------------------------------------
    # Build scenes only with the pre created NBR files and the SCL to initiate masking
    # --------------------------------------------------------------------------------
    for tif in tifs:
        name = tif.name.lower()

        if name.endswith("_scl_20m_cog.tif"):
            scene_id = name.replace("_scl_20m_cog.tif", "")
            band = "scl"
        elif name.endswith("_nbr.tif"):
            scene_id = name.replace("_nbr.tif", "")
            band = "NBR"
        else:
            continue

        scenes.setdefault(scene_id, {})[band] = tif

    # --------------------------------------------------
    # Create NBR Files masked with the classes 4,5,7
    # --------------------------------------------------
    nbrVegMask_path = CreateNBRWithVegMask(scenes, output_dir)
    return nbrVegMask_path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise ValueError("Please provide the fire Project Name and the SAFE folder name")
    fireProjectName = sys.argv[1]
    outputdir_zipname = sys.argv[2]
    createNBR(fireProjectName, outputdir_zipname)
