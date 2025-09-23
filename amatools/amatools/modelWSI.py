## amatools.modelWSI:
##   (1) command-line run model inference, and save the analyzed metadata to a CSV (and database) 
##
import os
import glob
import subprocess
import time
from datetime import datetime, timedelta
from loguru import logger
from func_timeout import func_set_timeout, FunctionTimedOut
from tqdm import tqdm
from .amaconfig import pcENV
from .amautility import updateDeCartConfig, replaceSpace2underscore, parseDeCartLog
from .amautility import dumpMetadata2stdout
from .amacsvdb import saveInferenceResult2CSV
from .queryMED import getMetadataFromMED
from .parseAIX import getCellsInfoFromAIX
from .parseAIX import getUROaverageOfSAcells, getUROaverageOfTopCells
from .parseAIX import countNumberOfUROtraits, countNumberOfTHYtraits
from .parseAIX import NUM_TOP, CRITERA_TRAIT, NUM_TRAIT_THY

##---------------------------------------------------------
## global variables, secret data, and criteria of 'score'
##---------------------------------------------------------
## global variables
PC_ARGS = pcENV()

##---------------------------------------------------------
## sub-functions for retrieving metadata from .med/.aix 
##---------------------------------------------------------
# get scanner information from metadata.json 
def readMakerAndDeviceFromMED(medjson):
    maker = medjson.get('Vendor', '')
    scanner = medjson['Scanner'] if maker == '' else f'{maker}'
    if medjson.get('ScannerModel', '') != '':
        scanner += f' ({medjson["ScannerModel"]})'
    elif medjson.get('ScannerType', '') != '':
        scanner += f' ({medjson["ScannerType"]})'
    elif medjson.get('ScanScopeId', '') != '':
        scanner += f' ({medjson["ScanScopeId"]})'
    elif medjson.get('ScannerModel', '') != '':
        scanner += f' ({medjson["ScannerModel"]})'
    return scanner

# collect analysis metadata from .med and .aix
def collectAnalysisMetadata(whichWSI):
    thismeta = {}
    medjson = getMetadataFromMED(f'{whichWSI}.med')
    aix_model, cellCount, cellsList = getCellsInfoFromAIX(f'{whichWSI}.aix', medjson['MPP'])
    thismeta['wsifname'] = os.path.split(whichWSI)[1]
    thismeta['scanner'] = readMakerAndDeviceFromMED(medjson)
    thismeta['mpp'], thismeta['icc'] = medjson['MPP'], medjson.get('IccProfile', '')
    thismeta['width'], thismeta['height'] = medjson['Width'], medjson['Height']
    thismeta['sizez'] = medjson['SizeZ']
    thismeta['bestfocuslayer'] = medjson.get('BestFocusLayer', 0)
    thismeta['modelname'], thismeta['modelversion'] = aix_model['Model'], aix_model['ModelVersion']
    thismeta['cellCount'] = cellCount
    thismeta['similarity'] = aix_model.get('SimilarityDegree', 0.0)
    if aix_model['Model'] == 'AIxURO':
        averageAREA = getUROaverageOfSAcells(cellsList)
        thismeta['avgsncratio'] = averageAREA['suspicious']['nc_ratio']
        thismeta['avgscelarea'] = averageAREA['suspicious']['cell_area']
        thismeta['avgsnucarea'] = averageAREA['suspicious']['nuclei_area']
        thismeta['avgancratio'] = averageAREA['atypical']['nc_ratio']
        thismeta['avgacelarea'] = averageAREA['atypical']['cell_area']
        thismeta['avganucarea'] = averageAREA['atypical']['nuclei_area']
        _, averageTOP = getUROaverageOfTopCells(cellsList, NUM_TOP, True)
        thismeta['topncratio'] = averageTOP['nc_ratio']
        thismeta['topcelarea'] = averageTOP['cell_area']
        thismeta['topnucarea'] = averageTOP['nuclei_area']
    else:   # 'AIXTHY'
        thismeta['traits'] = countNumberOfTHYtraits(cellsList, NUM_TRAIT_THY, CRITERA_TRAIT)
    return thismeta

## ---------- ---------- ---------- ----------
## 🖥️ command-line run model inference
## ---------- ---------- ---------- ----------
@func_set_timeout(86400)    ## in case of model inference takes too long time for more than 11 layers
def gotoModelInference(wsifiles, bin_decart, doneFolder, metaRecords, bVer1Model=False):
    if os.environ.get('DC_SINGLE_PLANE', None) != None:
        os.environ.pop('DC_SINGLE_PLANE')
    spos = bin_decart.index('decart')
    decart_version = os.path.split(bin_decart)[0][spos+6:]
    #if bVer1Model == False:
    #    bin_decart += ' -verbose -w'
    for ii, wsf in enumerate(wsifiles):
        workpath, wsifname = os.path.split(wsf)
        shortname, extension = os.path.splitext(wsifname)
        if extension.lower() in ['.tif', '.tiff']:
            os.environ['DC_EXTENDED_FORMAT'] = '1'
        #cmd_decart = f'{bin_decart} {wsf}'
        #logger.info(cmd_decart)
        sdt = datetime.now()
        logger.info(f"start model inference for {wsf} ({ii+1} of {len(wsifiles)}) from {sdt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} ...")
        #os.system(cmd_decart)
        try:
            if bVer1Model == False:
                logger.info(f'{bin_decart} -verbose -w {wsf}')
                decartlog = subprocess.run([bin_decart, "-verbose", "-w", wsf], capture_output=True, text=True)
            else:
                logger.info(f'{bin_decart} {wsf}')
        except subprocess.CalledProcessError as e:
            logger.error(f'failed while inference {os.path.basename(wsf)}, error: {e}')
            continue
        edt = datetime.now()
        logger.info(f'finish model inference for {wsf} at {edt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}...')
        analysis_timestamp = edt.timestamp() - sdt.timestamp()
        ##
        convert_timestamp, inference_timestamp = parseDeCartLog(decartlog.stdout)
        lines = decartlog.stdout.split('\n')
        for _, line in enumerate(lines):
            if line:
                logger.info(f'{line}')
        if convert_timestamp == 0 and inference_timestamp == 0:
            logger.warning(f'something wrong happened while model inference {os.path.basename(wsf)}')
        ## check .med file
        medfile = os.path.join(workpath, doneFolder, f'{shortname}.med')
        aixfile = os.path.join(workpath, doneFolder, f'{shortname}.aix')
        if not os.path.exists(medfile) or not os.path.exists(aixfile):
            logger.error(f'{medfile} does not exist!', 'ERROR')
            return
        ## collect model analysis metadata
        thismeta = collectAnalysisMetadata(os.path.splitext(medfile)[0])
        #### filesize
        if extension.lower() == '.mrxs':
            mrxspath = os.path.join(workpath, shortname)
            totalfsize = sum(os.path.getsize(f'{mrxspath}\\{fd}') for fd in os.listdir(mrxspath) if os.path.isfile(f'{mrxspath}\\{fd}'))
        else:
            totalfsize = os.path.getsize(wsf)
        wsifsize = round(totalfsize/(1024*1024), 4)     ## in MB
        medfsize = round((os.path.getsize(medfile)+os.path.getsize(aixfile))/(1024*1024), 4)     ## in MB
        thismeta['wsifname'] = wsifname
        thismeta['wsifsize'] = wsifsize
        thismeta['medfsize'] = medfsize
        thismeta['decart_version'] = decart_version
        thismeta['execution_date'] = int(sdt.timestamp())
        thismeta['convert_timestamp'] = convert_timestamp
        thismeta['inference_timestamp'] = inference_timestamp
        thismeta['analysis_timestamp'] = analysis_timestamp
        metaRecords.append(thismeta)

def cmdModelInference(wsipath, model_name=None, decart_version=None, config_file=None):
    # configuration
    PC_ARGS.loadConfigJson(config_file) if config_file else PC_ARGS.defaultConfig()
    modelname = model_name if model_name else 'AIxURO'
    #if not os.path.exists(wsipath):
    if not os.path.isdir(wsipath):
        logger.error(f'{wsipath} is not a folder!  unable to proceed model inference')
        return
    decart_ver = decart_version if decart_version else PC_ARGS.envConfig['decart_ver']
    if decart_ver != PC_ARGS.envConfig['decart_ver']:
        decart_dir = os.path.join(os.path.split(PC_ARGS.envConfig['decartpath'])[0], f'decart{decart_ver}')
    else:
        decart_dir = PC_ARGS.envConfig['decartpath']
    decart_exe = os.path.join(decart_dir, 'decart.exe')
    if os.path.exists(decart_exe) == False:
        logger.error(f'amatools needs to know the folder of DeCart application for running model inference, failed to find {decart_exe}')
        return
    ## check model version
    bVer1Model = True if decart_ver in ['1.5.4', '1.6.3', '2.0.7', '2.1.2'] else False
    if bVer1Model:
        logger.warning(f'amatools does not support model inference by model version earlier than 2023-Q1 version ({decart_ver})')
        return
    doneFolder = '' if decart_ver[:5] in ['2.7.3', '2.7.4', '2.7.5'] else 'done'
    cmd_decart = decart_exe
    medaix_metadata = []    ## metadata of model inference analysis results
    ## get the list of WSI files to be processed
    t0 = time.perf_counter()
    wsifiles, medfiles, zipfiles = [], [], []    ## zip files for DICOM format or zipped MRXS format
    foundfiles = glob.glob(os.path.join(wsipath, '*'))
    for fd in tqdm(foundfiles, desc=f'collecting WSI files in {wsipath}'):
        if os.path.isfile(fd) == False:
            continue
        wsiformat = os.path.splitext(fd)[1][1:].lower()
        #print({fd}, {wsiformat})
        if wsiformat in ['svs', 'ndpi', 'mrxs', 'bif', 'tif', 'tiff']:
            wsifiles.append(replaceSpace2underscore(fd))
        elif wsiformat == 'zip':    ## DICOM or zipped MRXS
            zipfiles.append(replaceSpace2underscore(fd))
        elif wsiformat == 'med':
            medfiles.append(replaceSpace2underscore(fd))
    if len(wsifiles) == 0 and len(zipfiles) == 0 and len(medfiles) == 0:
        logger.error(f'No WSI files found in {wsipath}!')
        return
    ## do model inference
    ##-- update c:\programdata\decart\config.yaml, if needs
    if updateDeCartConfig(modelname, PC_ARGS.envConfig['decartyaml']):
        logger.info(f'Update DeCart model preset to {modelname}')
    #### do inference for each WSI file, piority: WSI > zip > med    
    #cmd_decart += '-verbose -w '
    howmanywsi = len(wsifiles)
    if howmanywsi > 0:
        logger.trace(f'➡️ model inference using decart{decart_ver} model:{modelname} for {howmanywsi} WSI files...')
        gotoModelInference(wsifiles, cmd_decart, doneFolder, medaix_metadata)
    howmanyzip = len(zipfiles)
    if howmanyzip > 0:
        logger.trace(f'🔄 model inference using decart{decart_ver} model:{modelname} for {howmanyzip} ZIP files...')
        gotoModelInference(zipfiles, cmd_decart, doneFolder, medaix_metadata)
    howmanymed = len(medfiles)
    if howmanymed > 0:
        logger.trace(f'🔁 model inference using decart{decart_ver} model:{modelname} for {howmanymed} MED files...')
        gotoModelInference(medfiles, cmd_decart, doneFolder, medaix_metadata)
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    logger.info(f'processed {howmanywsi+howmanyzip+howmanyzip} slides with {consumed_time[:-3]}')
    logger.info(f'{modelname} model inference {wsipath} completed!')
    ## save metadata of model inference analysis results
    if len(medaix_metadata):
        saveInferenceResult2CSV(medaix_metadata, wsipath)
        ## dump partial metadata to stdout
        dumpMetadata2stdout(medaix_metadata)
    logger.trace(f'[inference] {modelname} model inference {wsipath} completed!')

