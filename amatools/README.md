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
#### extract single layer from .med file
```
/* extract best focus layer from .med files */
ama-go -o extract -f <path-to-med-folder> -d <path-to-dest-folder>
/* extract layer#m to layer#n from specified .med file */
ama-go -o extract -f <full-med-filename> -l <m>-<n> -d <path-to-dest-folder>
[note] 
    - default to extract BestFocusLayer if not specified layers
    - set modelname will trigger model inference after single layer extraction
```
#### replace label with qrcode in .med file
```
ama-go -o qrcode -f <path-to-med-folder>
[note] 
    - default to extract BestFocusLayer if not specified layers
    - set modelname will trigger model inference after single layer extraction
```
#### retrieve metadata and crop cell image of top N cells
```
ama-go -o readtopN -f <fullpath-med&aix-file>
```

[ama-go parameters]  
`-d` or `--destpath`: destination folder to store output files
`-f` or `--wsifolder`: folder contains WSI files for model inference, .aix/.med files for analysis  
`-j` or `--configjson`: configuration json file of working machine
`-l` or `--layers`: layer#(from, to) to extract single layer, e.g. 0-8
`-m` or `--modelname`: model product name, e.g. AIxURO, AIxTHY
`-o` or `--option`: action to perform, e.g. inference, analysis  
`-p` or `--decartpath`: folder path of decart installation
`-v` or `--decartversion`: decart version, e.g. 2.7.4

### Version
| Date | Version | Description |
|----------|---------|-------------|
| 2025-10-06 | 0.0.6 | added feature: retrieve metadata and crop cell image of top N cells, and output to a HTML file |
| 2025-09-28 | 0.0.5 | added features: extract single layer from .med file, pack multiple layers to .med file, replace label with qrcode |
| 2025-09-25 | 0.0.4 | main features: model inference, parse metadata to database/csv |

### © 2025 AIxMed, Inc. All Rights Reserved
