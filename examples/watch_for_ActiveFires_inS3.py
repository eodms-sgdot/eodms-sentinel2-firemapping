import boto3
import time # used only in time.sleep(30) last line
from datetime import datetime, timezone, timedelta
import subprocess
import sys
import shutil
import ForestFire_Opn_Tools as fireTools
import os
s3 = boto3.client("s3")

bucket = "sentinel-products-ca-mirror"
now = datetime.now(timezone.utc)
prefix = now.strftime("Sentinel-2/S2MSI2A/%Y/%m/%d/")
#if you want from 2 days ago, write manual date here, if it has been cloudy today
prefix = "Sentinel-2/S2MSI2A/2026/07/23/"

# ---------------------------------------------
# Function to watch for s3 data arriving
# ---------------------------------------------        
def start_watching():
    #Modify this to a proper project name, and find files in that folder
    fireProjectName = "July_30_ActiveFireRecord_Test_Of_July_23"
    bands = ["B12"]
    #--------------------------------------------------------------------------
    # Here we set the start time and end time for searching the AWS for zip, instead of STAC
    #-----------------------------------------------------------------------------
    # start from "now minus buffer"
    last_check = datetime.now(timezone.utc) - timedelta(minutes=5)
   
    #if you want from 2 days ago, since it has been cloudy
    target_day = (datetime.now(timezone.utc) - timedelta(days=8)).date()

    start_time = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
    end_time = datetime.combine(target_day, datetime.max.time(), tzinfo=timezone.utc)

    print("Time is: ", datetime.now(timezone.utc))
    print("Last check is 5 minutes ago: ", last_check)
    print("Checking in folder: ", prefix)

    filtered_links = [] # to filter for MSIL2A for example, so we can use specific products and not all of them
    
    #---------------------------------------------------------------------------------------------------------------------------------------------------------
    # Here we are searching the AWS for zip, instead of STAC, assuming to process only 1000, but re-run every 5 minutes, so never could be more than 1000
    #--------------------------------------------------------------------------------------------------------------------------------------------------------
    while True:
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=1000
        )
        #-------------------------------------------------------------------------------------------------------------------------------------------------------
        #If you dont see any data, most likely the prefix date has to be changed - try yesterday's date if its morning
        #-------------------------------------------------------------------------------------------------------------------------------------------------------
        if "Contents" in response:
            count = 0
            
            
            print("Only images with active fire values - detected with SWIR > 10000 will be used to create fire map and recorded in a csv for reference")
            activeFireRecords = (f"./Process_Records/{fireProjectName}_%Y_%m_%d_activeFireRecords.csv")
            activeFireFileName= now.strftime(activeFireRecords)
            fireTools.start_a_new_activeFire_csv_record(activeFireFileName)
            
            for obj in response["Contents"]:
                cog_format = {} # to store all bands in a product in a list of lists, one by one, here, and a list in Jupyter lab.
                #print(obj["LastModified"] )
                #if obj["LastModified"] > last_check:
                #if you want from 2 days ago, since it has been cloudy

                product_link = f"https://sentinel-products-ca-mirror.s3.ca-central-1.amazonaws.com/{obj['Key']}"
                #print("Product Link:", product_link)
                
                #remember feature.get("properties", {}) will not work, since we arent getting STAC json here from DB
                ProcessDateTime = datetime.now()
                S2FileName = product_link.split("/Sentinel-2/")[1]
                if "MSIL2A" in product_link:
                #if start_time <= obj["LastModified"] <= end_time:
                    count = count + 1
                    # these asterisks help separate the log for each file processed
                    print("**************************************************************************************************")
                    print(count, ": New file:", obj["Key"])

                    inputDataDir, cloudPercent, crs = fireTools.process_product_link(product_link, fireProjectName)
                    safeFileName_withSAFE_Ext = os.path.basename(inputDataDir)
                    safeFileName = os.path.splitext(safeFileName_withSAFE_Ext)[0]

                    print(f"Starting to create COGS for only B12 bands in {inputDataDir} to detect active Fire")
                    print(f"Safe file name is: {safeFileName}")
                    cog_format[safeFileName] = fireTools.get_bands_as_cogs(bands,inputDataDir, fireProjectName)     
                    print(f"Done with storing inputs as COGs, so deleting {inputDataDir} having completed creating maps (cloud = {cloudPercent}%)")
                    shutil.rmtree(inputDataDir)
                    #---------------------------------------------------------------------------------------------------------------------------------------
                    numberOfFilesProcessed = 0
                    for product, cog_list in cog_format.items():
                        print(f"Product is {product}")
                        
                        B12_cog = cog_list.get("B12")
                        activeFirePixels = fireTools.findIfActiveFire(B12_cog)

                        if (activeFirePixels > 0): 
                            numberOfFilesProcessed = numberOfFilesProcessed + 1
                            ProcessDateTime = datetime.now()
                            S2FileName = product
                            Decision = "check fire composites"
                            table_data = [[ProcessDateTime, fireProjectName, product, cloudPercent, activeFirePixels, Decision]]
                            fireTools.write_to_csv(activeFireFileName, table_data)
                            print(f"Number of files with active fire that were processed to create fire composites are: {numberOfFilesProcessed}")
                        else:
                            inputCogPath = "/mnt/data/Result_Images/Input_COG_Images/" + fireProjectName + "/" + product
                            print(f"Deleting input COG {inputCogPath} because number of active fire pixels was only {activeFirePixels} ")
                            shutil.rmtree(inputCogPath)
        else:
            print(f"Failed to retrieve features. Status code: {response.status_code}")
        

        last_check = datetime.now(timezone.utc)
        time.sleep(30)
        
if __name__ == "__main__":
    start_watching()
