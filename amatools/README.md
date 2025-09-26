# AMATOOLS
**amatools** is a set of utilities to command-line running model inference WSI files, 
parsing model analyzed metadata, and compiling metadata into database/csv.  
### Features
-**amaconfig**: initiate loguru.Logger, configuration for working machine
-**amacsvdb**: metadata ↔️ sqlite3 database / CSV  
-**amautility**: utility functions during processes of inference and analysis
-**modelWSI**: functions to model inference, convert WSI to MED files  
-**queryMED**: analyze metadata.json in MED file, crop specified file from MED file  
-**parseAIX**: retrieve metadata from AIX file, metadata average calculation, cells/traits count

### Usage (command prompt)
#### run model inference
```
ama-go -o inference -f <path-to-wsi> -m <model-name> -v <*decart-version*>
```
#### analyze inference metadata from .aix files (MPP is needed)
```
ama-go -o analysis -f <path-to-aix>
[note] 
    - <path-to-aix> should contains .med files as well
```

[ama-go parameters]  
`-d` or `--destpath`: destination folder to store output files
`-f` or `--wsifolder`: folder contains WSI files for model inference, .aix/.med files for analysis  
`-j` or `--configjson`: configuration json file of working machine
`-m` or `--modelname`: model product name, e.g. AIxURO, AIxTHY
`-o` or `--option`: action to perform, e.g. inference, analysis  
`-p` or `--decartpath`: folder path of decart installation
`-v` or `--decartversion`: decart version, e.g. 2.7.4

### Version
| Date | Version | Description |
|----------|---------|-------------|
| 2025-09-26 | 0.0.5 | add function to extract single layer images from .med file |
| 2025-09-25 | 0.0.4 | main features: model inference, parse metadata to database/csv |

### © 2025 AIxMed, Inc. All Rights Reserved
