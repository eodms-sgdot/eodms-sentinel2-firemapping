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
  
    try:
        if 'Records' in event.keys():
            # If the event is a record from S3, then it will be a list of records
            #   from S3.  Each record will be a dictionary with the bucket name
            #   and key of the file that triggered the event.
            records = event.get('Records')
        
            for rec in records:
                bucket_name = rec['s3']['bucket']['name']
                obj = rec['s3']['object']
                fn = obj.get('key') #fn for foldername/filename
                print(f"bucket_name: {bucket_name}")
                print(f"obj: {obj}") 
                print(f"key: {fn}")
                parts = fn.split("/")
                s3_folder = parts[0]
                prefix = "/".join(parts[1:-1])
                zipfilename = parts[-1]
                safeFileName_withSAFE_Ext = os.path.splitext(zipfilename)[0]
                print(f"Prefix: {prefix}")
                print(f"safeFileName_withSAFE_Ext: {safeFileName_withSAFE_Ext}") 

                now = datetime.now(timezone.utc)
                #Modify this to a proper project name, and find files in that folder
                fireProjectName = "Lambda_Function_ActiveFireRecord_Test"
                bands = ["B12"]
    
                filtered_links = [] # to filter for MSIL2A for example, so we can use specific products and not all of them
                count = 0
            
                print("Only images with active fire values - detected with SWIR > 10000 will be used to create fire map and recorded in a csv for reference")
                activeFireRecords = (f"Process_Records/{fireProjectName}_%Y_%m_%d_activeFireRecords.csv")
                activeFireFileName= now.strftime(activeFireRecords)
                activeFireTools.start_a_new_activeFire_csv_record(activeFireFileName)
                #starting to process zip file to see if there is active fire
                numberOfFilesProcessed = 0
                cog_format = {} # to store all bands in a product in a list of lists, one by one, here, and a list in Jupyter lab.
                product_link = f"https://sentinel-products-ca-mirror.s3.ca-central-1.amazonaws.com/{fn}"
                print("Product Link:", product_link)                
                ProcessDateTime = datetime.now()
                S2FileName = product_link.split("/Sentinel-2/")[1]
                if "MSIL2A" in product_link:
                    count = count + 1
                    # these asterisks help separate the log for each file processed
                    print("**************************************************************************************************")
                    print(count, ": New file:", fn)

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
            print(f"Failed to retrieve features.")
    except Exception:
        trc_back = traceback.format_exc()
        return {'event': event, 'Error': trc_back}
        