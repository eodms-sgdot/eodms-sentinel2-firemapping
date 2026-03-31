The set of python code can be used to automate fire mapping.
There is a trigger function to be placed in the folder where the zip files for Sentinel 2 gets dropped - zip_watcher.py, 
  and this can be turned into a lambda function in S3.
If we dont want to set a trigger, but download the zip files for specific dates and locations, we can use - dl_zipFiles.py
  this runs in the staging OGC API for now, downloads the zip file to a specific directory - that can be turned into a parameter if needed.
The create_fireMap.py, converts the .JP2 to COG (because we want to eventually use COG STAC methods) 
  and then makes RGB plots - as in the .ipynb and saves them as .JPG for quick verification like thumbnails.
  and can make Normalized Burnt Ratio (NBR) and Burnt Area Index 2 (BAI2) - the standard fire maps using Sentinel 2
  - there is an option to save individual bands like SWIR22 as a jpg plot if we want to have a quick view of the phenomenon.
