from pathlib import Path
import rasterio
import numpy as np

# --------------------------------------------------
# ROOT DIRECTORY
# --------------------------------------------------

root_dir = Path("./downloadedData/Sentinel2/stac_api_data/")

# --------------------------------------------------
# LOOP OVER FIRE_ID FOLDERS
# --------------------------------------------------

for fire_dir in root_dir.iterdir():
    if not fire_dir.is_dir():
        continue

    fire_id = fire_dir.name
    ref_dir = fire_dir / "RefImage"
    post_dir = fire_dir / "PostFireImage"
    out_dir = fire_dir / "dNBR"
    if not ref_dir.exists() or not post_dir.exists():
        print(f"⚠️ Skipping {fire_id}: missing RefImg or PostFireImg")
        continue

    out_dir.mkdir(exist_ok=True)

    print(f"\n🔥 Processing Fire_ID: {fire_id}")

    # --------------------------------------------------
    # FIND MATCHING NBR FILES
    # --------------------------------------------------
    for f in ref_dir.rglob("*_NBRVegMask.tif"):
        ref_files = f.name
        ref_path = f
    for f in post_dir.rglob("*_NBRVegMask.tif"):
        post_files = f.name
        post_path = f
        
        out_path = out_dir / f"{fire_id}_dNBR.tif"
        print(f"  → ref_path: {ref_path}")
        print(f"  → post_path: {post_path}")
        print(f"  → dNBR: {out_path}")

        with rasterio.open(ref_path) as ref_src, rasterio.open(post_path) as post_src:

            # ---- alignment checks ----
            if ref_src.shape != post_src.shape:
                raise ValueError(f"Shape mismatch in {fire_id} for {fname}")

            if ref_src.transform != post_src.transform:
                raise ValueError(f"Transform mismatch in {fire_id} for {fname}")

            # ---- read data ----
            ref_nbr = ref_src.read(1).astype("float32")
            post_nbr = post_src.read(1).astype("float32")

            nodata = ref_src.nodata

            # ---- dNBR calculation ----
            dnbr = ref_nbr - post_nbr

            if nodata is not None:
                mask = (ref_nbr == nodata) | (post_nbr == nodata)
                dnbr[mask] = nodata

            # ---- output profile ----
            profile = ref_src.profile
            profile.update(
                dtype="float32",
                count=1,
                compress="lzw"
            )

            # ---- write file ----
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(dnbr, 1)

        print(f"    ✅ Written: {out_path.name}")