import time
import subprocess
import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

#for the subprocess
import geopandas as gpd

WATCH_FOLDER = r"..\EODMS_FireS2_Opn\sentinel_2_data"   # <-- change this to your folder path


# ---------------------------------------------
# Function to call another Python script
# ---------------------------------------------
def call_create_fireMap(folder_path):
    print(f"[CALLING SCRIPT] Passing folder to external script: {folder_path}")

    # Example: run another_script.py and pass folder_path as an argument
    subprocess.run(
        [sys.executable, "create_fireMap.py", folder_path],
        check=True
    )

class ZipFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Check if the created item is a directory
        if event.is_directory:       
            folder_path = "./sentinel_2_data/" + os.path.basename(event.src_path)
            print(f"New folder created: {folder_path}")
            call_create_fireMap(folder_path)
        """Trigger function when a new file is created."""
        if not event.is_directory and event.src_path.endswith(".zip"):
            zip_name = os.path.basename(event.src_path)
            print(f"New ZIP file detected: {zip_name}")

def start_watching(folder_path):
    event_handler = ZipFileHandler()
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=False)
    
    print(f"Watching for new ZIP files in: {folder_path}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    start_watching(WATCH_FOLDER)