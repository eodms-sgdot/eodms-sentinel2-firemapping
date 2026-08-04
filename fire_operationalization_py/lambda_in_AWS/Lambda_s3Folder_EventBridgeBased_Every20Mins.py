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

def get_s2_zip_files(bucket_name, s3_folder):

        # Initialize the S3 client
        s3_client = boto3.client('s3')
        
        # Create a paginator for ListObjectsV2
        paginator = s3_client.get_paginator('list_objects_v2')
        
        # Configure the prefix (folder path)
        # Ensure the prefix does not start with a '/'
        prefix = s3_folder.lstrip('/')
        
        images = []
        
        # Page through the results safely
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    # Check if the object ends with the specified string
                    if key.endswith('.zip'):
                        print(f"key is {key}")
                        images.append(key)
        return images

def lambda_handler(event, context):
    aws_account_id = context.invoked_function_arn.split(":")[4]
    print(f"event: {event}")
    print(f"context: {context}")
    now = datetime.now(timezone.utc)
    s3_folder_today = now.strftime("Sentinel-2/S2MSI2A/%Y/%m/%d/")
    #bucket_name and s3_folder can be sent from test
    bucket_name = event.get('bucket_name', "sentinel-products-ca-mirror")
    s3_folder = event.get('s3_folder', s3_folder_today)
    
    #if you want from 2 days ago, write manual date here, if it has been cloudy today
    #s3_folder= "Sentinel-2/S2MSI2A/2026/07/23/"
    #Modify this to a proper project name, and find files in that folder
    fireProjectName = "Lambda_Function_s3Folder_ActiveFireRecord_Test"
    bands = ["B12"]
    
    activeFireRecords = (f"Process_Records/{fireProjectName}_%Y_%m_%d_s3Folder_activeFireRecords.csv")
    activeFireFileName= now.strftime(activeFireRecords)
    activeFireTools.start_a_new_activeFire_csv_record(activeFireFileName)
    #--------------------------------------------------------------------------
    # Here we set the start time and end time for searching the AWS for zip
    #-----------------------------------------------------------------------------
    # start from "now minus buffer - 20 mins ideal, since lambda can run max 15 minutes" 
    start_time = datetime.now(timezone.utc)
    last_check = start_time - timedelta(minutes=20)
    INTERVAL = 20 * 60 # 20 minutes #to decide how many seconds to sleep after process complets
    """        
    #if you want from 2 days ago, since it has been cloudy
    target_day = (datetime.now(timezone.utc) - timedelta(days=8)).date()
    #if you want between two different days
    start_time = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
    end_time = datetime.combine(target_day, datetime.max.time(), tzinfo=timezone.utc)
    """
    print("Time is: ", datetime.now(timezone.utc))
    print("Last check is 20 minutes ago: ", last_check)
    prefix = s3_folder.lstrip('/')
    print("Checking in folder: ", prefix)
    filtered_links = [] # to filter for MSIL2A for example, so we can use specific products and not all of them 
    try:
        while True:
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=100 # assuming only 100 gets dumped every 5 minutes
            )
            #-------------------------------------------------------------------------------------------------------------------------------------------------------
            #If you dont see any data, most likely the prefix date has to be changed - try yesterday's date if its morning
            #-------------------------------------------------------------------------------------------------------------------------------------------------------
            if "Contents" in response:
                count = 0
                print("Only images with active fire values - detected with SWIR > 10000 will be used to create fire map and recorded in a csv for reference")
                #starting to process zip file to see if there is active fire
                numberOfFilesProcessed = 0
                for obj in response["Contents"]:
                    product_link = f"https://sentinel-products-ca-mirror.s3.ca-central-1.amazonaws.com/{obj['Key']}"
                    print("Product Link:", product_link)  
                    cog_format = {} # to store all bands in a product in a list of lists, one by one, here, and a list in Jupyter lab.
                    if obj["LastModified"] > last_check and "MSIL2A" in product_link:
                    #if "MSIL2A" in product_link:
                        count = count + 1
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

                            if (activeFirePixels > 0): 
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
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)
    except Exception:
        trc_back = traceback.format_exc()
        return {'event': event, 'Error': trc_back}