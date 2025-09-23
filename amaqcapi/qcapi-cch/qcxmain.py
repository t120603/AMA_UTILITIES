import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .qcxfuncs import initLogger
from .qcxfuncs import initConfig4QCAPI
from .qcxfuncs import queryAllSlideName, queryQCresult4slide, queryQCresult_from_images
from .qcxfuncs import launchCytoInsights, activateWatchFolders
from .qcxfuncs import listMEDAIX
import site
from loguru import logger

Description_QCAPI_CCH = """
QCAPI provides the information to suggest review whole slide image if meet the criteria  
### Functions  
1. query all the available slides id with slide_type  
    *Request URL*:  
    http://{ip-address}:5025/v0/allslides/urine   

2. query the QC results and file path of slide image with slide_id and slide_type  
    *Request URL*:  
    http://{ip-address}:5025/v0/slide/urine?slide_id=K32400376   
 
**Note**  
- slide_id: most likely is the slide label name  
- slide_type: can be either '**urine**' or '**thyroid**'  
"""

app = FastAPI(
    title = 'API for querying QC reference informantion',
    description = Description_QCAPI_CCH,
    version = '0.0.1'
)
# define the list of allowed origins
origins = [
    "http://localhost",
    "http://localhost:5025",
    "http://qcapi.cch.com"
]
# add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,     # allow cookies and authorization headers
    allow_methods=["*"],
    allow_headers=["*"],
)

## global variable: list of all med files
AllMED = listMEDAIX()

##---------------------------------------------------------
## QCAPIs
##---------------------------------------------------------
@app.get('/v1/allslides/{slide_type}')
async def get_all_slides(slide_type: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'there is no slide for {slide_type} slides')
        raise HTTPException(status_code=404, detail=f'there is no slide for {slide_type} slides')
    logger.info(f'get_all_slides({slide_type})')
    allSlides = queryAllSlideName(slide_type)
    return allSlides

@app.get('/v1/slide/{slide_type}')
async def get_slide_qc_result(slide_type: str, slide_id: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'{slide_type} {slide_id} can not be found')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')
    logger.info(f'starting get_slide_qc_result({slide_type}, {slide_id}) ...')
    qcresult = queryQCresult4slide(slide_type, slide_id)
    if qcresult == {}:
        logger.error(f'can not find any metadata for {slide_type} slide {slide_id}')
        raise HTTPException(status_code=404, detail=f'can not find any metadata for {slide_type} slide {slide_id}')            

    return {
        'signal1': qcresult['signal1'],
        'signal2': qcresult['signal2'],
        'medpath': qcresult['medpath'],
        'medfile': qcresult['medname'],
        'rawdata': qcresult['rawdata'],
        'refnote': qcresult['refnote']
    }

##---------------------------------------------------------
## temporary private APIs: for a test
##---------------------------------------------------------
@app.get('/v1/findallslides/{slide_type}', include_in_schema=False)
async def find_all_slides(slide_type: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'there is no slide for {slide_type} slides')
        raise HTTPException(status_code=404, detail=f'there is no slide for {slide_type} slides')
    logger.info(f'find_all_slides({slide_type})')
    ##
    AllMED.scanMEDAIX(slide_type)
    allSlides = AllMED.findAllSlideName(slide_type)
    return allSlides

@app.get('/v1/findslide/{slide_type}', include_in_schema=False)
async def find_slides_qc_result(slide_type: str, slide_id: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'no {slide_type} slides')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')
    logger.info(f'starting find_slides_qc_result({slide_type}, {slide_id}) ...')
    qcresult = AllMED.findSlide(slide_type, slide_id)
    if len(qcresult) == 0:      ## unfound, clear cache and find again
        AllMED.scanMEDAIX(slide_type)
        qcresult = AllMED.findSlide(slide_type, slide_id)

    if len(qcresult) == 0:
        logger.error(f'{slide_type} {slide_id} can not be found')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')

    qc0 = qcresult[0]
    return {
        'signal1': qc0['signal1'],
        'signal2': qc0['signal2'],
        'medpath': qc0['medpath'],
        'medfile': qc0['medname'],
        'rawdata': qc0['rawdata'],
        'refnote': qc0['refnote']
    }

##---------------------------------------------------------
## private APIs
##---------------------------------------------------------
@app.get('/openmed/{file_type}', include_in_schema=False)
async def open_med_file(file_type: str, medfile: str):
    if file_type.lower() in ['med', 'aix']:
        logger.info(f'open_med_file({file_type}, {medfile})')
        launchCytoInsights(medfile)
    return None

@app.get('/run', include_in_schema=False)
async def activate_monitoring_wsifolder(funcname: str):
    if funcname == 'watchcch':
        user_site = site.USER_SITE      ## python site-packages
        pyscripts = os.path.join(os.path.split(user_site)[0], 'Scripts', 'watch-cch.exe')
        if os.path.exists(pyscripts) == False:
            raise HTTPException(status_code=404, detail=f'watch-cch.exe does not exist')
        logger.info(f'starting watch-cch.exe')
        activateWatchFolders(pyscripts)
    return None

##---------------------------------------------------------
## main
##---------------------------------------------------------
def startQCAPI(configFile, logFile):
    initLogger(logfname=logFile)
    # init environment
    if initConfig4QCAPI(configFile):
        ## test runing monitor folders
        user_site = site.USER_SITE      ## python site-packages
        watchwsi = os.path.join(os.path.split(user_site)[0], 'Scripts', 'watch-wsi.exe')
        if activateWatchFolders(watchwsi, configFile):
            logger.trace('start monitoring scanner wsi folders ...')
        else:
            logger.warning('unable to monitor scanner folders, contact with service team')
        #run_server()
        uvicorn.run(app, host="0.0.0.0", port=5025)
    else:
        logger.error('failed to initiate working environment')

if __name__  == '__main__':
    initLogger()
    if initConfig4QCAPI():
        ## test runing monitor folders
        user_site = site.USER_SITE      ## python site-packages
        watchwsi = os.path.join(os.path.split(user_site)[0], 'Scripts', 'watch-wsi.exe')
        if activateWatchFolders(watchwsi):
            logger.trace('start monitoring scanner wsi folders ...')
        else:
            logger.warning('unable to monitor scanner folders, contact with service team')
        #run_server()
        uvicorn.run('qcxmain:app', host='0.0.0.0', port=5025, reload=True)

