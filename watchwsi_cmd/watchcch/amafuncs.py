##---------------------------------------------------------------------------------------------
# functions for model inference, metadata analysis, and update analyzed metadata to database
# 
#   v1.00, 2025-08-07, QC reference for clinical cytopathlogical workflow in CCH, Philip Wu
# Copyrights(c) 2025, AIxMed Inc.
##---------------------------------------------------------------------------------------------
import os, glob
from datetime import datetime
from func_timeout import func_set_timeout, FunctionTimedOut
import yaml, json
import subprocess
from loguru import logger
from .asarlib import AsarFile
import gzip
import shapely.geometry
from .metafunc import getUROaverageOfSAcells, getUROaverageOfTopCells
from .taskfunc import stopDeCart, restartDeCart

##---------------------------------------------------------
## configuration for this machine, should be customized for each machine
##---------------------------------------------------------
def getConfig(config=None):
    if not config:
        ## default config-amaqc.json in %localappdata%
        config = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi', 'config-watchwsi.json')
        if os.path.exists(config) == False:
            logger.error('default config-watchwsi.json does not exist, please contact with service team')
            return {}

    try:
        with open(config, 'r', encoding='utf-8') as conf:
            args = json.load(conf)
    except FileNotFoundError:
        logger.error(f'{config} was not found')
    except json.JSONDecodeError:
        logger.error(f'{config} contains invalid JSON')
    except Exception as e:
        logger.error(f'an unexpected error occurred: {e}')
    return args

##---------------------------------------------------------
## update 'preset' if necessary, without re-start DeCart
##---------------------------------------------------------
def updateDeCartConfigOnly(thismodel, decartYaml):
    conf = None
    try:
        with open(decartYaml, 'r') as curyaml:
            conf = yaml.load(curyaml, Loader=yaml.FullLoader)
    except FileNotFoundError:
        logger.error(f'{decartYaml} does not exist')
    except Exception as e:
        logger.error(f'an unexpected error occurred: {e}')

    if conf and conf['preset'].lower() != thismodel.lower():
        conf['preset'] = thismodel.lower()
        with open(decartYaml, 'w') as newyaml:
            yaml.dump(conf, newyaml)
        return True
    return False

##---------------------------------------------------------
## update config.yaml (model / watch folder), re-start DeCart
##---------------------------------------------------------
def updateDeCartConfig(decartYaml, decartEXE, thismodel=None, watchfolder=None):
    conf = None
    try:
        with open(decartYaml, 'r') as curyaml:
            conf = yaml.load(curyaml, Loader=yaml.FullLoader)
    except FileNotFoundError:
        logger.error(f'{decartYaml} does not exist')
    except Exception as e:
        logger.error(f'an unexpected error occurred: {e}')

    bUpdate = False
    is_a_service = True if 'ProgramData' in decartYaml else False
    if conf:
        if thismodel and conf['preset'].lower() != thismodel.lower():
            conf['preset'] = thismodel.lower()
            bUpdate = True
        if watchfolder and os.path.exists(watchfolder):
            conf['watch'] = watchfolder
            bUpdate = True
        if bUpdate:
            ## STOP DeCart service (2.7.x) or END DeCart process (2.8.x)
            stopDeCart(is_a_service)
            time.sleep(10)
            # update decart.yaml
            with open(decartYaml, 'w') as newyaml:
                yaml.dump(conf, newyaml)
            time.sleep(10)
            ## restart DeCart
            restartDeCart(is_a_service, decartEXE)
            #
        return True
    else:
        return False

##---------------------------------------------------------
## parse image conversion timestamp and inference timestamp from subprocess.run()
##---------------------------------------------------------
def parseDeCartLog(logtext):
    rows = logtext.split('\n')
    tformat = '%Y-%m-%dT%H:%M:%S'
    ts = []
    for _, rr in enumerate(rows):
        if rr:
            if ('convert ' in rr) or ('processed' in rr): 
                dt = datetime.strptime(rr[5:24], tformat)
                ts.append(dt.timestamp())
    # calculate conversion time and inference time
    if len(ts) != 3:    ## something wrong happened while model inference
        if len(ts) == 1:        ## inference .med file
            dt = datetime.strptime(rows[0][5:24], tformat)
            return 0, ts[0]-dt.timestamp()
        else:
            return 0, 0
    else:
        return (ts[1]-ts[0]), (ts[2]-ts[1])        

## ---------- ---------- ---------- ----------
## replace ' ' with '_' in the filename
## ---------- ---------- ---------- ----------
def replaceSpace2underscore(fname):
    thisfile = fname
    if ' ' in fname:
        mpath, mfile = os.path.split(fname)
        tmpfile = mfile.replace(' ', '_')
        thisfile = os.path.join(mpath, tmpfile)
        os.rename(fname, thisfile)
    return thisfile

## ---------- ---------- ---------- ----------
## utilities to prcess .med file
## ---------- ---------- ---------- ----------
def getMetadataFromMED(medfile):
    with AsarFile(medfile) as thismed:
        mdata = thismed.read_file('metadata.json')
    metajson = json.loads(mdata)
    return metajson

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

## ---------- ---------- ---------- ----------
## utilities to prcess .aix file
## ---------- ---------- ---------- ----------
def calculateCellArea(segments, thismpp=None):
    mpp = 0.25 if not thismpp else thismpp
    convex = []
    for i, xy in enumerate(segments):
        x, y = xy
        convex.append((x*mpp, y*mpp))
    thiscell = shapely.geometry.Polygon(convex)
    return thiscell.area

## Reads an AIX file and returns a dictionary with the model information.
def getModelInfoFromAIX(aixfile, save2json=None):
    gaix = gzip.GzipFile(mode='rb', fileobj=open(aixfile, 'rb'))
    aixdata = gaix.read()
    gaix.close()
    aixjson = json.loads(aixdata)
    ## save 2 json file for debugging
    if save2json:
        sortname = os.path.splitext(os.path.basename(aixfile))[0]
        with open(f'{sortname}.json', 'w') as jsonobj:
            json.dump(aixjson, jsonobj, indent=4)
    ## here is for decart version 2.x.x
    aixinfo = aixjson.get('model', {})
    aixcell = aixjson.get('graph', {})
    return aixinfo, aixcell

def getCellsInfoFromAIX(aixfile, mpp=None):
    aixinfo, aixcell = getModelInfoFromAIX(aixfile)
    whichmodel = aixinfo.get('Model', 'unknown')
    allCells = []
    if whichmodel == 'AIxURO':
        ## return getAixuroCellInfo(aixfile)
        typeName = ['background', 'nuclei', 'suspicious', 'atypical', 'benign',
                    'other', 'tissue', 'degenerated']
        cellCount = [0 for i in range(len(typeName))]
        nulltags = [0.0 for _ in range(14)]
        ## get all the cell information
        for jj in range(len(aixcell)):
            cbody = aixcell[jj][1].get('children', '')
            if cbody == '':
                continue
            for kk in range(len(cbody)):
                cdata = cbody[kk][1].get('data', '')
                if cdata == '':
                    continue
                thiscell = {}
                category = cdata.get('category', -1)
                if category >= 0 and category < len(typeName):
                    cellCount[category] += 1
                else:
                    logger.error(f'{os.path.basename(aixfile)} has unknown cell type ID:{category}.')
                thiscell['cellname'] = cbody[kk][1]['name']
                #thiscell['category'] = typeName[category] if 'ModelArchitect' not in aixinfo else specialCase(category)
                thiscell['category'] = category
                thiscell['segments'] = cbody[kk][1]['segments']
                thiscell['ncratio']  = cdata.get('ncRatio', 0.0)
                thiscell['cellarea'] = 0.0 if not mpp else calculateCellArea(thiscell['segments'], mpp)
                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellsList = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
        ## check whether 'modelArch' is in the cell information, if yes, revised some categories
        if 'ModelArchitect' in aixinfo:  ## decart 2.0.x and decart 2.1.x
            numNuclei, numAtypical, numBenign = cellCount[3], cellCount[1], cellCount[0]
            cellCount[0], cellCount[4] = 0, numBenign
            cellCount[1], cellCount[3] = numNuclei, numAtypical
        return aixinfo, cellCount, cellsList
    elif whichmodel == 'AIxTHY':
        ##return getAixthyCellInfo(aixfile)
        if aixinfo['ModelVersion'][:6] in ['2025.2']:
            typeName = ['background', 'follicular', 'oncocytic', 'epithelioid', 'lymphocytes', 
                        'histiocytes', 'colloid', 'unknown']
        else:
            typeName = ['background', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes', 
                        'colloid', 'multinucleatedGaint', 'psammomaBodies']
        objCount = [0 for i in range(len(typeName))]
        nulltags = [0.0 for _ in range(20)]
        ## get all the cell information
        for jj in range(len(aixcell)):
            cbody = aixcell[jj][1].get('children', '')
            if cbody == '':
                continue
            for kk in range(len(cbody)):
                cdata = cbody[kk][1].get('data', '')
                if cdata == '':
                    continue
                thiscell = {}
                category = cdata.get('category', -1)
                if category >= 0 and category < len(typeName):
                    objCount[category] += 1
                else:
                    logger.error(f'{os.path.basename(aixfile)} has unknown cell type ID:{category}.')
                thiscell['cellname'] = cbody[kk][1]['name']
                thiscell['category'] = category
                thiscell['segments'] = cbody[kk][1]['segments']
                thiscell['cellarea'] = 0.0 if not mpp else calculateCellArea(thiscell['segments'], mpp)
                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellsList = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
        return aixinfo, objCount, cellsList
    else:
        logger.error(f'{os.path.basename(aixfile)} is not analyzed by AIxURO or AIxTHY model.')
        return aixinfo, [], []

## ---------- ---------- ---------- ----------
## collect model inference metadata
## ---------- ---------- ---------- ----------
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
        thismeta['savgncratio'], thismeta['savgnucarea'], thismeta['aavgncratio'], thismeta['aavgnucarea'] = getUROaverageOfSAcells(cellsList)
        _, thismeta['avgtop24ncratio'], thismeta['avgtop24nucarea'] = getUROaverageOfTopCells(cellsList)
    else:   # 'AIXTHY'
        thismeta['traits'] = countNumberOfTHYtraits(cellsList, 20)
    return thismeta

##---------------------------------------------------------
## command line running decart
##---------------------------------------------------------
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
        logger.info(f"Start model inference for {wsf} ({ii+1} of {len(wsifiles)}) from {sdt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} ...")
        #os.system(cmd_decart)
        try:
            if bVer1Model == False:
                logger.info(f'{bin_decart} -verbose -w {wsf}')
                decartlog = subprocess.run([bin_decart, "-verbose", "-w", wsf], capture_output=True, text=True)
            else:
                logger.info('does not support out-to-date model inference')
        except subprocess.CalledProcessError as e:
            logger.error(f'failed while inference {os.path.basename(wsf)}, error: {e}')
            continue
        edt = datetime.now()
        logger.info(f'Finish model inference for {wsf} at {edt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}...')
        analysis_timestamp = edt.timestamp() - sdt.timestamp()
        convert_timestamp, inference_timestamp = parseDeCartLog(decartlog.stdout)
        lines = decartlog.stdout.split('\n')
        for _, line in enumerate(lines):
            if line:
                logger.info(line)
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

def doModelInference(wsipath, modelname='AIxURO', decart_version='2.7.4'):
    if not os.path.exists(wsipath):
        logger.error(f'{wsipath} does not exist!')
        return
    ## configuration settings
    args = getConfig()
    decartVersion = args['decart_ver']
    dir_decart = args['decartpath']
    bVer1Model = True if decartVersion in ['1.5.4', '1.6.3', '2.0.7', '2.1.2'] else False
    doneFolder = '' if decartVersion[:5] in ['2.7.3', '2.7.4', '2.7.5'] else 'done'
    cmd_decart = args['decart_exe']
    medaix_metadata = []    ## metadata of model inference analysis results
    ## get the list of WSI files to be processed
    wsifiles, medfiles, zipfiles = [], [], []    ## zip files for DICOM format or zipped MRXS format
    wsilist = glob.glob(os.path.join(wsipath, '*'))
    for _, fd in enumerate(wsilist):
        if os.path.isfile(fd) == False:
            continue
        wsiformat = os.path.splitext(fd)[1][1:].lower()
        #print({fd}, {wsiformat})
        if wsiformat in ['svs', 'ndpi', 'mrxs', 'bif', 'tif', 'tiff']:
            wsifiles.append(replaceSpace2underscore(fd))
        '''
        elif wsiformat == 'med':
            medfiles.append(replaceSpace2underscore(fd))
        elif wsiformat == 'zip':    ## DICOM or zipped MRXS
            zipfiles.append(replaceSpace2underscore(fd))
        '''
    if len(wsifiles) == 0 and len(zipfiles) == 0 and len(medfiles) == 0:
        logger.error(f'No WSI files found in {wsipath}!')
        return []
    ## do model inference
    #### update c:\programdata\decart\config.yaml, if needs
    if os.path.exists(args['decartyaml']) == False:
        logger.error('DeCart config.yaml does not exist, please contact with service team')
        return []
    if updateDeCartConfigOnly(modelname, args['decartyaml']):
        logger.info(f'Update DeCart model preset to {modelname}')
    #### do inference for each WSI file, piority: WSI > zip > med    
    if bVer1Model:
        pass
    else:
        #cmd_decart += '-verbose -w '
        howmanywsi = len(wsifiles)
        if howmanywsi > 0:
            logger.trace(f'Start model inference using decart{decart_version} model:{modelname} for {howmanywsi} WSI files...')
            gotoModelInference(wsifiles, cmd_decart, doneFolder, medaix_metadata)
        '''
        howmanyzip = len(zipfiles)
        if howmanyzip > 0:
            logger.trace(f'Start model inference using decart{decart_version} model:{modelname} for {howmanyzip} ZIP files...')
            gotoModelInference(zipfiles, cmd_decart, doneFolder, medaix_metadata)
        howmanymed = len(medfiles)
        if howmanymed > 0:
            logger.trace(f'Start model inference using decart{decart_version} model:{modelname} for {howmanymed} MED files...')
            gotoModelInference(medfiles, cmd_decart, doneFolder, medaix_metadata)
        '''
    logger.info(f'{modelname} model inference {wsipath} completed!')

    return medaix_metadata
