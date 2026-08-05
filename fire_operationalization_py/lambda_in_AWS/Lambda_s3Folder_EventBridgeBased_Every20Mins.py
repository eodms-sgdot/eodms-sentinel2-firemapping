import boto3
import time # used only in time.sleep(30) last line
from datetime import datetime, timezone, timedelta
import subprocess
import sys
import shutil
import activeFire_FilterTools as activeFireTools
import os
import traceback
s3 = boto3.client("s3")

def lambda_handler(event, context):
    aws_account_id = context.invoked_function_arn.split(":")[4]
    print(f"event: {event}")
    print(f"context: {context}")
    now = datetime.now(timezone.utc)
    s3_folder_today = now.strftime("Sentinel-2/S2MSI2A/%Y/%m/%d/")
    #since yesterdays data can be loaded upto today morning, we need to have two days in prefix
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    s3_folder_yesterday = yesterday.strftime("Sentinel-2/S2MSI2A/%Y/%m/%d/")

    #bucket_name and s3_folder can be sent from test
    bucket_name = event.get('bucket_name', "sentinel-products-ca-mirror")
    s3_folder_today = event.get('s3_folder_today', s3_folder_today)
    s3_folder_yesterday = event.get('s3_folder_yesterday', s3_folder_yesterday)

    prefixes = [
        s3_folder_today,
        s3_folder_yesterday
        ]
    #this way we will pick up August 4th data that got loaded on August 5th morning
    
    #Modify this to a proper project name, and find files in that folder
    fireProjectName = "Lambda_Function_s3Folder_ActiveFireRecord_Test"
    bands = ["B12"]
    # We shouldnt a create a new csv for every lambda run, we should append records to the same one!
    activeFireRecords = (f"Process_Records/{fireProjectName}_2026_08_05_s3Folder_activeFireRecords.csv")
    #activeFireRecords = (f"Process_Records/{fireProjectName}_%Y_%m_%d_s3Folder_activeFireRecords.csv")
    #activeFireFileName= now.strftime(activeFireRecords)
    #activeFireTools.start_a_new_activeFire_csv_record(activeFireFileName)
    #--------------------------------------------------------------------------
    # Here we set the start time and end time for searching the AWS for zip
    #-----------------------------------------------------------------------------
    # start from "now minus buffer - 20 mins ideal, since lambda can run max 15 minutes" 
    start_time = datetime.now(timezone.utc)
    last_check = start_time - timedelta(minutes=20)
    INTERVAL = 20 * 60 # 20 minutes #to decide how many seconds to sleep after process complets
    print("Time is: ", datetime.now(timezone.utc))
    print("Last check is 20 minutes ago: ", last_check)

    filtered_links = [] # to filter for MSIL2A for example, so we can use specific products and not all of them 
    try:
        objects_today_yesterday = []
        print("--------- contents for the today --------------------")
        for prefix in prefixes:
            print(f"Checking for {prefix}")
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=1000) # in a day there is usually 600 - 800 images, we will process only the last 20 minutes ones)
            num_objects = len(response.get("Contents", []))
            print("Number of Objects in ", prefix, ": ", num_objects)
            if "Contents" in response:
                objects_today_yesterday.extend(response.get("Contents", []))
                print("IsTruncated, if more than 1000:", response.get("IsTruncated"))  # True if more objects exist beyond MaxKeys
                print("--------- contents for the yesterday --------------------")
        print(f"Total number of objects for today and  yesterday: {len(objects_today_yesterday)}")
        if len(objects_today_yesterday) > 0:
            recent_objects = [
                obj
                for obj in objects_today_yesterday
                if obj["LastModified"] >= last_check]            
            print(f"Found {len(recent_objects)} recent objects")
            count = 0
            print("Purpose: Images with active fire values - detected with SWIR > 10000 will be used to create fire map and recorded in a csv for reference")
            print(f"Files processed: Images loaded between {last_check} and {start_time}")
            #starting to process zip file to see if there is active fire
            numberOfFilesProcessed = 0
            #for obj in response["Contents"]: dont have to process all 1000
            for obj in recent_objects:
                cog_format = {} # to store all bands in a product in a list of lists, one by one, here, and a list in Jupyter lab.
                product_link = f"https://sentinel-products-ca-mirror.s3.ca-central-1.amazonaws.com/{obj['Key']}"
                #if obj["LastModified"] > last_check and "MSIL2A" in product_link:
                if "MSIL2A" in product_link:
                    count = count + 1
                    #print("Product Link:", product_link)  
                    ProcessDateTime = datetime.now()
                    S2FileName = product_link.split("/Sentinel-2/")[1]
                    # these asterisks help separate the log for each file processed
                    print("**************************************************************************************************")
                    print(count, ": New file:", {obj['Key']})

                    inputDataDir, cloudPercent, crs = activeFireTools.process_product_link(product_link, fireProjectName)
                    safeFileName_withSAFE_Ext = os.path.basename(inputDataDir)
                    safeFileName = os.path.splitext(safeFileName_withSAFE_Ext)[0]

                    print(f"Starting to create COGS for only B12 bands in {inputDataDir} to detect active Fire")
                    print(f"Safe file name is: {safeFileName}")
                    cog_format[safeFileName] = activeFireTools.get_bands_as_cogs(bands,inputDataDir, fireProjectName)     
                    print(f"Done with storing inputs as COGs, so deleting {inputDataDir} having completed creating maps (cloud = {cloudPercent}%)")
                    shutil.rmtree(inputDataDir)
                    #---------------------------------------------------------------------------------------------------------------------------------------
                    for product, cog_list in cog_format.items():
                        print(f"Product is {product}")
                        
                        B12_cog = cog_list.get("B12")
                        activeFirePixels = activeFireTools.findIfActiveFire(B12_cog)

                        if (activeFirePixels > 10): 
                            numberOfFilesProcessed = numberOfFilesProcessed + 1
                            ProcessDateTime = datetime.now()
                            S2FileName = product
                            Decision = "check fire composites"
                            table_data = [ProcessDateTime, fireProjectName, product, cloudPercent, activeFirePixels, Decision]
                            activeFireTools.write_to_csv(activeFireFileName, table_data)
                            print(f"Number of files with active fire that were processed to create fire composites are: {numberOfFilesProcessed}")
                        else:
                            inputCogPath = "/tmp/Result_Images/Input_COG_Images/" + fireProjectName + "/" + product 
                            print(f"Deleting input COG {inputCogPath} because number of active fire pixels was only {activeFirePixels} ")
                            shutil.rmtree(inputCogPath)
        else:
            print(f"Failed to retrieve features. {response.status_code}")
        # if the process takes eight minutes, it will sleep 12 minutes - for every 20 minute check
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        print(f"Time taken to complete the process {elapsed} seconds")
        #sleep_time = max(0, INTERVAL - elapsed)
        #time.sleep(sleep_time) # no point to this, since in 15 minutes lambda will end - keeping it any way
    except Exception:
        trc_back = traceback.format_exc()
        return {'event': event, 'Error': trc_back}
