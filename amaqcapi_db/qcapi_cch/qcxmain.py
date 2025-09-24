import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .qcdbfunc import qcxQCDB
from .qcxfuncs import initLogger, initConfig4QCAPI
from .qcxfuncs import queryAllSlideName, queryQCresult4slide, queryQCresultfromDB
from .qcxfuncs import launchCytoInsights, activateWatchFolders
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

3. query the analyzed metadata with slide_id and slide_type  
    *Request URL*:  
    http://{ip-address}:5025/v0/slideinfo/urine?slide_id=K32400376     
 
**Note**  
- slide_id: most likely is the slide label name  
- slide_type: can be either '**urine**' or '**thyroid**'
- QC reference data from sqlite3 database which analyzed within model inference process  
"""

app = FastAPI(
    title = 'API for querying QC reference informantion',
    description = Description_QCAPI_CCH,
    version = '0.0.4'
)
# define the list of allowed origins
origins = [
    "http://localhost",
    "http://localhost:5025"
]
# add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,     # allow cookies and authorization headers
    allow_methods=["*"],
    allow_headers=["*"],
)
# initiate DB path, should update after setting configuration
qcxDBpath = qcxQCDB(r'E:\ama_qcapi\this_scanner\db4qc', 'qcxuro_debug.db', 'qcxthy_debug.db')

##---------------------------------------------------------
## QCAPIs
##    v0: query data from sqlite3 database
##    v1: query data by parsing .aix file
##---------------------------------------------------------
@app.get('/v0/allslides/{slide_type}')
async def get_all_slides(slide_type: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'there is no slide for {slide_type} slides')
        raise HTTPException(status_code=404, detail=f'there is no slide for {slide_type} slides')
    logger.info(f'get_all_slides({slide_type})')
    whichdb = qcxDBpath.get_qcdb_name(slide_type)
    allSlides = queryAllSlideName(slide_type, whichdb)
    return allSlides

@app.get('/v1/allslides/{slide_type}')
async def get_all_slides(slide_type: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'there is no slide for {slide_type} slides')
        raise HTTPException(status_code=404, detail=f'there is no slide for {slide_type} slides')
    logger.info(f'get_all_slides({slide_type})')
    allSlides = queryAllSlideName(slide_type)
    return allSlides

@app.get('/v0/slide/{slide_type}')
async def get_slide_qc_result(slide_type: str, slide_id: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'{slide_type} {slide_id} can not be found')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')
    whichdb = qcxDBpath.get_qcdb_name(slide_type)
    logger.info(f'starting get_slides_qc_result({slide_type}, {slide_id}) ...')
    qcresult = queryQCresultfromDB(slide_type, slide_id, whichdb)
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

@app.get('/v1/slide/{slide_type}')
async def get_slide_qc_result(slide_type: str, slide_id: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'{slide_type} {slide_id} can not be found')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')
    logger.info(f'starting get_slides_qc_result({slide_type}, {slide_id}) ...')
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

@app.get('/v0/slideinfo/{slide_type}')
async def get_slide_analyzed_metadata(slide_type: str, slide_id: str):
    if slide_type.lower() not in ['urine', 'thyroid']:
        logger.error(f'{slide_type} {slide_id} can not be found')
        raise HTTPException(status_code=404, detail=f'{slide_type} {slide_id} can not be found')
    logger.info(f'get_slide_analyzed_metadata({slide_type}, {slide_id})')
    whichdb = qcxDBpath.get_qcdb_name(slide_type)
    slidemeta = querySlideAnalyzedMetadata(slide_id, slide_type, whichdb)
    if slidemeta == '':
        logger.error(f'can not find any metadata for slide {slide_id}')
        raise HTTPException(status_code=404, detail=f'can not find any metadata for slide {slide_id}')
    return slidemeta

##---------------------------------------------------------
## private APIs
##---------------------------------------------------------
@app.get('/openmed/{file_type}', include_in_schema=False)
async def open_med_file(file_type: str, medfile: str):
    if file_type.lower() in ['med', 'aix']:
        logger.info(f'open_med_file({file_type}, {medfile})')
        launchCytoInsights(medfile)
    return None

@app.get('/dbpath/{act}', include_in_schema=False)
async def set_qcdb_path(act: str, db_path: str):
    if os.path.exists(db_path) == False:
        logger.error(f'{db_path} does not exist')
        raise HTTPException(status_code=404, detail=f'{db_path} does not exist')
    qcxDBpath.set_qcdb_path(db_path)
    logger.info(f'set_qcdb_path({db_path}) completed')
    return None

@app.get('/dbname/{slide_type}', include_in_schema=False)
async def set_qcdb_name(slide_type: str, db_name: str):
    if os.path.exists(os.path.join(qcxDBpath.get_qcdb_path(slide_type), db_name)) == False:
        logger.warning(f'{db_name} does not exist')
        #raise HTTPException(status_code=404, detail=f'{db_name} does not exist')
    qcxDBpath.set_qcdb_name(slide_type, db_name)
    logger.info(f'set_qcdb_name({slide_type}, {db_path}) completed')
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

