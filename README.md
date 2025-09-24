# AMA_UTILITIES
**ama_utilities** is a set of Python packages to provide some workflows for AIxMED model inference service deployment, e.g. model inference automation service and APIs for querying analysis metadata; for specified tasks to facilitate in-house research projects, e.g. running model inference WSI files, 
parsing model analyzed metadata and compiling metadata into database/csv.  
### Features
| Task | Description |
|------|-------------|
|**amaqcapi**| API service to query analysis metadata for QC reference |  
|**amaqcapi_db**| API service to query analysis metadata for QC reference from a datebase |
|**amatools**| command-line running model inference, analyze inference metadata, extract single layer from multiple layers of wsi files, crop and compare tiles fro multiple layers of .med files |
|**watchwsi**| monitor scanner folders, move those scanned WSI files to DeCart watch folder, and move the analyzed .med/.aix files to image storage |  
|**watchedi_cmd**| monitor scanner folders, command-line running model inference, save inference metadata to database, and move the analyzed /med/.aix files to image storage |  

### © 2025 AIxMed, Inc. All Rights Reserved
