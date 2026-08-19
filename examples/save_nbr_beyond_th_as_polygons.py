import geopandas as gpd
from datetime import datetime
from rasterio.features import shapes
from shapely.geometry import shape
from pathlib import Path
import rasterio
import numpy as np
import sys
from shapely.geometry import Polygon,MultiPolygon

def create_burn_mask(nbr_path, threshold=-0.2):
    print(f"NBR Path: {nbr_path}")
    with rasterio.open(nbr_path) as src:
        nbr = src.read(1)
        
        nodata = src.nodata

        nbr[nbr == nodata] = 999

        burn_mask = (nbr < threshold) & (~np.isnan(nbr)) # burned areas

        return burn_mask, src.transform, src.crs
        
def mask_to_polygons(mask, transform):
    polygons = []

    for geom, value in shapes(mask.astype("uint8"), transform=transform):
        if value == 1:
            polygons.append(shape(geom))

    return polygons
    
def extract_datetime(safe_name):
    #S2A_MSIL2A_20260616T161701_N0512_R140_T17TMG_20260617T040935
    parts = safe_name.split("_")

    dt_str = parts[2]  # '20260616T161701'

    dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")

    return dt
    
def save_polygons(polygons, crs, output_path, safe_name):
    dt = extract_datetime(safe_name)

    gdf = gpd.GeoDataFrame(
        {
            "geometry": polygons,
            "scene_id": safe_name,
            "acq_date": dt.date(),
            "acq_time": dt.time()
        },
        crs=crs
    )

    gdf.to_file(output_path)

def merge_polygons(output_shp):

    gdf = gpd.read_file(output_shp)
    
    distance = 500  # meters

    # Expand polygons
    buffered = gdf.buffer(distance)

    # Merge overlapping buffers
    merged = buffered.union_all()  # GeoPandas >= 1.0
    
    #Simplify the edges
    outer = merged.simplify(
        tolerance=500,
        preserve_topology=True
    )
    
    # Shrink back
    shrunk = outer.buffer(-distance)

    if isinstance(shrunk, Polygon):
        shrunk = Polygon(shrunk.exterior)

    elif isinstance(shrunk, MultiPolygon):
        shrunk = MultiPolygon(
            Polygon(poly.exterior)
            for poly in shrunk.geoms
        )
    
    result = gpd.GeoDataFrame(
        geometry=[shrunk],
        crs=gdf.crs
        )

    merged_polygons = output_shp.parent / "burn_polygons_merged_simpl.shp"
    result.to_file(merged_polygons)

def convert_nbr_as_polygons(nbr_path, fireProjectName, safe_filename):
    #safe_filename = "S2B_MSIL2A_20260702T175909_N0512_R041_T14VMH_20260702T214234"
    input_dir = Path("/mnt/data/Result_Images/Input_COG_Images/") / fireProjectName / safe_filename
    output_dir = Path("/mnt/data/Result_Images/NBR_Polygon_SHP/") / fireProjectName / safe_filename 
    output_dir.mkdir(parents=True, exist_ok=True)
    output_shp = output_dir / "burn_polygons.shp"
    print(f"NBR Path: {nbr_path}")    
    mask, transform, crs = create_burn_mask(nbr_path)

    polygons = mask_to_polygons(mask, transform)

    save_polygons(polygons, crs, output_shp, safe_filename)
    merge_polygons(output_shp)
    print("✅ Polygon file created:", output_shp)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Please provide the NBR Path")
    nbr_path = sys.argv[1]
    fireProjectName = sys.argv[2]
    safe_filename = sys.argv[3]
    convert_nbr_as_polygons(nbr_path, fireProjectName, safe_filename)
