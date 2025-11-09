import os
from library.filesystem import MOUNT_PATH
import logging
from functions.appFunctions import getAllUserDownloads
import shutil
from functions.openrouterNaming import suggest_strm_name

def generateFolderPath(data: dict):
    """
    Takes in a user download and returns the folder path for the download.

    Series (Year)/Season XX/Title SXXEXX.ext
    Movie (Year)/Title (Year).ext

    """
    root_folder = data.get("metadata_rootfoldername", None)
    metadata_foldername = data.get("metadata_foldername", None)

    if not root_folder and not metadata_foldername:
        return None

    if data.get("metadata_mediatype") == "series":
        folder_path = os.path.join(
            root_folder,
            metadata_foldername,
        )
    elif data.get("metadata_mediatype") == "movie":
        folder_path = os.path.join(
            root_folder
        )

    elif data.get("metadata_mediatype") == "anime":
        folder_path = os.path.join(
            root_folder,
            metadata_foldername,
        )
    else:
        folder_path = os.path.join(
            root_folder
        )
    return folder_path

def generateStremFile(file_path: str, url: str, download: dict):
    if file_path is None or not download:
        return
    file_name = download.get("metadata_filename") or download.get("file_name")
    if not file_name:
        logging.debug("Skipping download with missing file name.")
        return
    media_type = (download.get("metadata_mediatype") or "movie").lower()
    if media_type == "movie":
        type_folder = "movies"
    elif media_type in ("series", "anime"):
        type_folder = "series"
    else:
        type_folder = "movies"

    full_path = os.path.join(MOUNT_PATH, type_folder, file_path)

    try:
        os.makedirs(full_path, exist_ok=True)
        with open(f"{full_path}/{file_name}.strm", "w") as file:
            file.write(url)
        logging.debug(f"Created strm file: {full_path}/{file_name}.strm")
        return True
    except OSError as e:
        logging.error(f"Error creating strm file (likely bad or missing permissions): {e}")
        return False
    except FileNotFoundError as e:
        logging.error(f"Error creating strm file (likely bad naming scheme of file): {e}")
        return False
    except Exception as e:
        logging.error(f"Error creating strm file: {e}")
        return False


def _apply_openrouter_naming(download: dict) -> dict:
    suggestion = suggest_strm_name(download)
    if not suggestion:
        return download
    updated = False
    filename = suggestion.get("filename")
    if filename:
        download["metadata_filename"] = filename
        updated = True
    media_type = suggestion.get("media_type")
    if media_type:
        download["metadata_mediatype"] = media_type
        updated = True
    if updated:
        logging.debug(
            "OpenRouter normalized download %s -> %s (%s)",
            download.get("file_name"),
            download.get("metadata_filename"),
            download.get("metadata_mediatype"),
        )
    return download

def runStrm():
    all_downloads = getAllUserDownloads()
    for download in all_downloads:
        download = _apply_openrouter_naming(download)
        file_path = generateFolderPath(download)
        if file_path is None:
            continue
        generateStremFile(file_path, download.get("download_link"), download)

    logging.debug(f"Updated {len(all_downloads)} strm files.")

def unmountStrm():
    """
    Deletes all strm files and any subfolders in the mount path for cleaning up.
    """
    folders = [
        MOUNT_PATH,
        os.path.join(MOUNT_PATH, "movies"),
        os.path.join(MOUNT_PATH, "series"),
    ]
    for folder in folders:
        if os.path.exists(folder):
            logging.debug(f"Folder {folder} already exists. Deleting...")
            for item in os.listdir(folder):
                item_path = os.path.join(folder, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
