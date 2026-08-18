from pathlib import Path
import save_activeFire_as_polygonsTools as firePolygonsTools
import boto3
import traceback
from urllib.parse import urlparse
from pathlib import PurePosixPath

s3 = boto3.client("s3")

count = 0

def lambda_handler(event, context):
    aws_account_id = context.invoked_function_arn.split(":")[4]  
    try:
        if 'Records' in event.keys():
            # If the event is a record from S3, then it will be a list of records
            #   from S3.  Each record will be a dictionary with the bucket name
            #   and key of the file that triggered the event.
            records = event.get('Records')
            count = 0 
            for rec in records:
                bucket_name = rec['s3']['bucket']['name']
                obj = rec['s3']['object']
                fn = obj.get('key') #fn for foldername/filename
                print(f"bucket_name: {bucket_name}")
                print(f"obj: {obj}") 
                print(f"key: {fn}")
                if fn.endswith("cog.tif"):
                    s3_uri = f"s3://{bucket_name}/{fn}"
                    cog_file = PurePosixPath(urlparse(s3_uri).path)
                count = count + 1
                print(f"File number {count}: Name of cog file is: {cog_file}")
                safeFileName = cog_file.parent.name
                fireProjectName = "August_14_FirePolygon_Test_FromLambda"
                firePolygonsTools.convert_firePixels_as_polygons(cog_file, fireProjectName,safeFileName)
                print(f"------------------------------------------------------------------------------------------------------------------")
    except Exception as e:
        trc_back = traceback.format_exc()
        print(trc_back)
        return {'event': event, 'Error': str(e), 'Traceback': trc_back}
