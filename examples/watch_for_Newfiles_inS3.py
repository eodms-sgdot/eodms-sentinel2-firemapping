import boto3
import time # used only in time.sleep(30) last line
from datetime import datetime, timezone, timedelta
import subprocess
import sys
import shutil
import ForestFire_Opn_Tools as fireTools
import os
import createNBRFiles_AndMaskwithSCL_eodmsCOG as createNBRFiles
import save_nbr_beyond_th_as_polygons as nbr_as_polygons
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
    fireProjectName = "July_14_Test"
    bands = ["B12", "B11", "B09", "B8A", "B04", "SCL"]
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
            cog_format = {} # to store all bands in a product in a list of lists
            #remember response.json get features wont work, since these are zip lists and not STAC response.
            
            print("Download is saved if cloud level less than 30%, to create fire map, or its deleted")
            addFireProjectName_andProcessingDate = (f"./Process_Records/{fireProjectName}_%Y_%m_%d_processRecords.csv")
            resDataFileName= now.strftime(addFireProjectName_andProcessingDate)
            fireTools.start_a_new_csv_record(resDataFileName) 

            print("Only images with active fire values - detected with SWIR > 10000 will be used to create fire map and recorded in a csv for reference")
            activeFireRecords = (f"./Process_Records/{fireProjectName}_%Y_%m_%d_activeFireRecords.csv")
            activeFireFileName= now.strftime(activeFireRecords)
            fireTools.start_a_new_csv_record(activeFireFileName)

            for obj in response["Contents"]:
                cog_format = {} # to store all bands in a product in a list of lists - here only 1, since one by one.
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
                    if cloudPercent < 30:
                        Decision = "Create fire map"
                        print("Cloud level less than 30%, so going to create fire map")
                        filtered_links.append(inputDataDir)
                        print(f"Starting to create COGS for bands in {inputDataDir}")
                        cog_format[safeFileName] = fireTools.get_bands_as_cogs(bands,inputDataDir, fireProjectName) 
                        #print(cog_format[product])
                        print(f"Done with storing inputs as COGs, so deleting {inputDataDir} having completed creating maps (cloud = {cloudPercent}%)")
                        shutil.rmtree(inputDataDir)
                        #---------------------------------------------------------------------------------------------------------------------------------------
                        print(f"Starting to create Fire Composites for {inputDataDir} ")
                        output_dir_fireProj = "/mnt/data/Result_Images/FireComposite_Images/" + fireProjectName 
                        print(f"If previous results are open in QGIS, close the project, otherwise it cant overwrite!")

                        numberOfFilesProcessed = 0 #keeping count of files with active fire pixels

                        for product, cog_list in cog_format.items():
                            output_dir = output_dir_fireProj + "/" + product
                            compositeType = "B12B8AB04_RGB"
                            B12_cog = cog_list.get("B12")
                            print(f"The current B12_cog: {B12_cog}")
                            activeFirePixels = fireTools.findIfActiveFire(B12_cog)
                            if (activeFirePixels > 0): 
                                numberOfFilesProcessed = numberOfFilesProcessed + 1
                                ProcessDateTime = datetime.now()
                                S2FileName = product
                                Decision = "check fire composites"
                                table_data = [[ProcessDateTime, fireProjectName, product, activeFirePixels, Decision]]
                                fireTools.write_to_csv(activeFireFileName, table_data)

                                B8A_cog = cog_list.get("B8A")
                                B04_cog = cog_list.get("B04")
                                B11_cog = cog_list.get("B11")
                                B09_cog = cog_list.get("B09")
                                if not all([B12_cog, B8A_cog, B04_cog, B11_cog, B09_cog]):
                                    print(f"Missing bands for product {product}")

                        if (activeFirePixels > 0): 
							#Only we need JPG files resembling Jupyter Lab visualization
                        	#plot_band_cog(B8A_cog, inputDataDir) # NIR
                        	#plot_band_cog(B12_cog, inputDataDir) # SWIR
                         
                        	#Standard FireComposite 
                        	compositeType = "B04B8AB12_RGB"
                        	rgb, rgb_forTif = fireTools.makeRGBComposite(B12_cog, B8A_cog, B04_cog)
                        	#Fire_RGB_COG = fireTools.save_to_GeoTif(rgb_forTif, B12_cog, inputDataDir, outputdir_zipname, compositeType)
                        	Fire_RGB_COG = fireTools.save_to_GeoTif(rgb_forTif, compositeType, output_dir, B12_cog)
                        	#Only we need JPG files resembling Jupyter Lab visualization
                        	#plot_RGB_cog(rgb, inputDataDir)
                        
                        	#Ashlin Richardson Method
                        	compositeType = "B12B11AB09_RGB"
                        	rgb, rgb_forTif = fireTools.makeRGBComposite(B12_cog, B11_cog, B09_cog)
                        	#Fire_RGB_AR_COG = fireTools.save_to_GeoTif(rgb_forTif, B12_cog, inputDataDir, outputdir_zipname, compositeType)
                        	Fire_RGB_AR_COG = fireTools.save_to_GeoTif(rgb_forTif, compositeType, output_dir, B12_cog)
                        	#Only we need JPG files resembling Jupyter Lab visualization
                        	#plot_RGB_cog(rgb, inputDataDir)
                        	print(f"Going to create NBR with Veg Mask for {product}:")
                        	nbrVegMask_path = createNBRFiles.createNBR(fireProjectName, product)
                        	print(f"Going to convert NBR with Veg Mask for {nbrVegMask_path}: as polygons and save in a shape file")
                        	nbr_as_polygons.convert_nbr_as_polygons(nbrVegMask_path, fireProjectName, product)
                        	inputCogPath = "/mnt/data/Result_Images/Input_COG_Images/" + fireProjectName + "/" + product 
                        	fireCompPath = "/mnt/data/Result_Images/FireComposite_Images/" + fireProjectName + "/" + product
                        	print(f"Completed all steps for this {product} and removing the local files {inputCogPath}")
                        	shutil.rmtree(inputCogPath)
                        	shutil.rmtree(fireCompPath)
                            #print(f"Number of files with active fire that were processed to create fire composites are: {numberOfFilesProcessed}")
                        else:
                            print(f"There was no active fire pixels in this {product} and hence not processing it for firemaps!")
                    else:
                        Decision = "Dont create fire map"
                        Decision = "Dont create fire map"
                        print(f"Deleting {inputDataDir} (cloud = {cloudPercent}%)")
                        shutil.rmtree(inputDataDir)
                    table_data = [[ProcessDateTime, fireProjectName, S2FileName, cloudPercent, Decision]]
                    fireTools.write_to_csv(resDataFileName, table_data)
            print("Download of all ", count, " level 2A features completed")    
            for product_link in filtered_links:
                print(product_link)
            print("Completed storing all bands of all products with good cloud level, as COG files to create fire maps")
        else:
            print(f"Failed to retrieve features. Status code: {response.status_code}")
        

        last_check = datetime.now(timezone.utc)
        time.sleep(30)
        
if __name__ == "__main__":
    start_watching()
