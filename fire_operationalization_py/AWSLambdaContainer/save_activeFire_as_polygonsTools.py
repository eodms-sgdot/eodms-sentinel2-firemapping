import geopandas as gpd
from datetime import datetime
from rasterio.features import shapes
from shapely.geometry import shape
from pathlib import Path
from urllib.parse import urlparse
from pathlib import PurePosixPath
import rasterio
import numpy as np
import sys
from shapely.geometry import Polygon,MultiPolygon
import boto3
s3 = boto3.client("s3")

def create_burn_mask(B12_path, threshold=10000):
    with rasterio.open(B12_path) as src:
        b12 = src.read(1)
        
        nodata = src.nodata

        b12[b12 == nodata] = 999

        burn_mask = (b12 > threshold) & (~np.isnan(b12)) # burned areas

        return burn_mask, src.transform, src.crs
        
def mask_to_polygons(mask, transform):
    polygons = []

    for geom, value in shapes(mask.astype("uint8"), transform=transform):
        if value == 1:
            polygons.append(shape(geom))

    return polygons
    
def extract_datetime(safe_name):
    #S2A_MSIL2A_20260616T161701_N0512_R140_T17TMG_20260617T040935
    #print(f"Safe name is {safe_name}")
    parts = safe_name.split("_")
    
    dt_str = parts[2]  # '20260616T161701'
    #print(f"part to split is {dt_str}")
    dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")

    return dt
    
def save_polygons(polygons, crs, fireProjectName, safe_filename):
    output_dir = Path("/tmp/Result_Images/ActiveFire_Polygon_SHP/") / fireProjectName / safe_filename 
    pixelTo_shp = output_dir / "suspectedFire_polygons.shp"
    dt = extract_datetime(safe_filename)

    gdf = gpd.GeoDataFrame(
        {
            "geometry": polygons,
            "scene_id": safe_filename,
            "acq_date": dt.date(),
            "acq_time": dt.time()
        },
        crs=crs
    )
    # UTM units are metres
    gdf["area_sqm"] = gdf.geometry.area
    gdf["area_ha"] = gdf.geometry.area / 10000
    if gdf["area_ha"].max() > 0.5: #atleast one polygon is bigger
        output_dir.mkdir(parents=True, exist_ok=True)
        gdf.to_file(pixelTo_shp)
        date_str = safe_filename[11:19] # 20260804
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        s3.upload_file(
            pixelTo_shp,
            "s2-fire-ard",
            f"Result_Images/Input_COG_Images/{year}/{month}/{day}/{safe_filename}/suspectedFire_polygons.shp"
            )
        print("✅ Polygon file created:", pixelTo_shp)
    else:
        print("No larger than 0.5ha polygons here, could be false alarm!")


def merge_polygons(pixelTo_shp, crs, safe_filename, merged_polygons):

    gdf = gpd.read_file(pixelTo_shp)
    
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
    dt = extract_datetime(safe_filename)
    result = gpd.GeoDataFrame ({
        "geometry": [shrunk],
        "scene_id": safe_filename,
        "acq_date": dt.date(),
        "acq_time": dt.time()
        },
        crs=gdf.crs)
    # explode multipart geometry into individual polygons
    parts = result.explode(index_parts=False)
    has_large_polygon = (parts.geometry.area / 5000 > 1).any()

    if has_large_polygon:
        result.to_file(merged_polygons)
    else:
        print("No larger than 1ha polygons here, could be false alarm!")
        
def convert_firePixels_as_polygons(b12_path, fireProjectName, safe_filename):
    #safe_filename = "S2B_MSIL2A_20260702T175909_N0512_R041_T14VMH_20260702T214234"
    input_dir = Path("/tmp/Result_Images/Input_COG_Images/") / fireProjectName / safe_filename
    s3_b12_path = f"s3://s2-fire-ard{b12_path}"
    print(f"B12 Path is: {s3_b12_path}")  
    mask, transform, crs = create_burn_mask(s3_b12_path)

    polygons = mask_to_polygons(mask, transform)

    save_polygons(polygons, crs, fireProjectName, safe_filename)
    #merged_polygons = pixelTo_shp.parent / "burn_polygons_merged_simpl.shp"
    #merge_polygons(pixelTo_shp, crs, safe_filename, merged_polygons)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Please provide the NBR Path")
    b12_path = sys.argv[1]
    fireProjectName = sys.argv[2]
    safe_filename = sys.argv[3]
    convert_firePixels_as_polygons(b12_path, fireProjectName, safe_filename)
