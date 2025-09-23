# AMA_WATCH
**AMA_WATCH** is an utility for fulfilling automatically model inference process on premise workflow.  
**AMA_WATCH** will monitor the change on scanner shared folder which contains recent scanned WSI files, move those scanned WSI files to working folder in service wotkstation.  Next, trigger AIxMed model, **AIxURO** or **AIxTHY** depends on WSI category is urine slide or thyroid slide respectively.  At last, move analyzed image files, **.med**/**.aix** files, into on premise image storage. 
**AMA_WATCH** needs to customize the configuration settings based on on-premise working environment.  

### Release
| App Name | Version | Description |
|----------|---------|-------------|
| watch-wsi | 0.1.x | for integrating with CCH QC workflow, copy WSI files into DeCart watch folder, move analyzed image files (*.med / *.aix) to on-premise image storage |
| watch-wsi | 0.0.x | for integrating with CCH QC workflow, command line running model inference, move analyzed image files (*.med / *.aix) to on-premise image storage, save inference metadata in sqlite3 database |

### © 2025 AIxMed, Inc. All Rights Reserved
