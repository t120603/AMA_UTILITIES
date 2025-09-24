import os, sys
import glob
import shutil
from loguru import logger
import yaml, json
import time
import gzip
import platform
import subprocess
import shapely
from .qcdbfunc import saveInferenceMetadata2DB

## -------------------------------------------------------------- 
##  global preset working folders 
## -------------------------------------------------------------- 
## 
qcxPATH = {
    'driveXhome': 'X:\\CCH_scanner',            # scanner shared folder
    'driveYhome': 'Y:\\CCH_scanner\\medaix',    # on-premise image storage
    'qcapi_home': 'E:\ama_qcapi\this_scanner',  # local working folders
    'decart_exe': "C:\\Program Files\\WindowsApps\\com.aixmed.decart_2.7.4.0_x64__pkjfmh18q18h8",
    'decartyaml': "C:\\ProgramData\\DeCart\\config.yaml"
}

def initConfig4QCAPI(configfile=None):
    if not configfile:
        backuplog = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi', 'qcapi-debug.log')
        configfile = logbackup if os.path.exists(logbackup) else None
    if configfile:
        if os.path.exists(configfile) == False:
            logger.error(f'{configfile} does not exist, please contact with service team')
        else:
            try:
                with open(configfile, 'r', encoding='utf-8') as conf:
                    args = json.load(conf)
            except FileNotFoundError:
                logger.error(f'{configfile} was not found')
            except json.JSONDecodeError:
                logger.error(f'{configfile} contains invalid JSON')
            except Exception as e:
                logger.error(f'an unexpected error occurred: {str(e)}')
            # update global qcxPATH
            if args.get('driveXhome'):
                qcxPATH['driveXhome'] = args['driveXhome']
            if args.get('driveYhome'):
                qcxPATH['driveYhome'] = args['driveYhome']
            if args.get('qcapi_home'):
                qcxPATH['qcapi_home'] = args['qcapi_home']
            if args.get('decart_exe'):
                qcxPATH['decart_exe'] = args['decart_exe']
            if args.get('decartyaml'):
                qcxPATH['decartyaml'] = args['decartyaml']
    return True

##---------------------------------------------------------
# 📝 logging to %localappdata% using loguru
##---------------------------------------------------------
def initLogger(logfname=None, level=None):
    if (not level) or (isinstance(level, str) and level not in ['INFO', 'DEBUG', 'ERROR']):
        log_level = 'TRACE'
    else:
        log_level = level
    # log file existed?
    if not logfname or os.path.exists(logfname) == False:   # using default logfile
        logpath = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi')
        if os.path.isdir(logpath) == False:
            os.makedirs(logpath)
        logfile = os.path.join(logpath, 'qcapi-debug.log')
    else:
        logfile = logfname

    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <blue>Line {line: >4} ({file}):</blue> | <b>{message}</b>"
    #logger.add(sys.stdout, level=log_level, format=log_format, colorize=True, backtrace=True, diagnose=True)
    logger.add(logfname, rotation='4 MB', level=log_level, format=log_format, colorize=False, backtrace=True, diagnose=True)

## -------------------------------------------------------------- 
##  utilities for retrieving metadata from .aix 
## -------------------------------------------------------------- 
def calculateCellArea(segments, thismpp=None):
    mpp = 0.25 if not thismpp else thismpp
    convex = []
    for i, xy in enumerate(segments):
        x, y = xy
        convex.append((x*mpp, y*mpp))
    thiscell = shapely.geometry.Polygon(convex)
    return thiscell.area

##---------------------------------------------------------
## parse .aix
##---------------------------------------------------------
def getMetadataFromAIX(aixfile):
    gaix = gzip.GzipFile(mode='rb', fileobj=open(aixfile, 'rb'))
    aixdata = gaix.read()
    gaix.close()
    aixjson = json.loads(aixdata)
    ## here is for decart version 2.x.x
    aixinfo = aixjson.get('model', {})
    aixcell = aixjson.get('graph', {})
    return aixinfo, aixcell

def getTargetCellsFromAIX(aixfile, mpp=None):
    aixinfo, aixcell = getMetadataFromAIX(aixfile)
    thismodel = aixinfo.get('Model')
    allCells = []
    if thismodel == 'AIxURO':
        categories = ['background', 'nuclei', 'suspicious', 'atypical', 'benign',
                      'other', 'tissue', 'degenerated']
        cellsCount = [0 for _ in range(len(categories))]
        nulltags = [0.0 for _ in range(14)]
        for jj in range(len(aixcell)):
            thiscell = {}
            cbody = aixcell[jj][1].get('children', '')
            if cbody == '':
                continue
            for kk in range(len(cbody)):
                cdata = cbody[kk][1].get('data', '')
                if cdata == '':
                    continue
                category = cdata.get('category', -1)
                if category >= 0 and category <= len(categories):
                    cellsCount[category] += 1
                else:
                    logger.error(f'{os.path.basename(aixfile)} has unknown cell category (ID: {category})')
                thiscell['cellname'] = cbody[kk][1]['name']
                thiscell['category'] = category
                thiscell['segments'] = cbody[kk][1]['segments']
                thiscell['ncratio'] = cdata.get('ncRatio', 0.0)
                thiscell['cellarea'] = 0.0 if not mpp else calculateCellArea(thiscell['segments'], mpp)
                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellslist = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
        ## whatif too old version of AIxURO model ???
        if 'ModelArchitect' in aixinfo:
            ## decart 2.0.x and decart 2.1.x
            numNuclei, numAtypical, numBenign = cellsCount[3], cellsCount[1], cellsCount[0]
            cellsCount[0], cellsCount[4] = 0, numBenign
            cellsCount[1], cellsCount[3] = numNuclei, numAtypical
            logger.warning(f"{os.path.basename(aixfile)} was inference with {aixinfo.get('Model')}_{aixinfo.get('ModelVersion')}")
    elif thismodel == 'AIxTHY':
        if aixinfo['ModelVersion'][:6] in ['2025.2']:
            categories = ['background', 'follicular', 'oncocytic', 'epithelioid', 'lymphocytes', 
                          'histiocytes', 'colloid', 'unknown']
        else:
            categories = ['background', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes', 
                          'colloid', 'multinucleatedGaint', 'psammomaBodies']
        cellsCount = [0 for _ in range(len(categories))]
        nulltags = [0.0 for _ in range(20)]
        for jj in range(len(aixcell)):
            thiscell = {}
            cbody = aixcell[jj][1].get('children', '')
            if cbody == '':
                continue
            for kk in range(len(cbody)):
                cdata = cbody[kk][1].get('data', '')
                if cdata == '':
                    continue
                category = cdata.get('category', -1)
                if category >= 0 and category <= len(categories):
                    cellsCount[category] += 1
                else:
                    logger.error(f'{os.path.basename(aixfile)} has unknown cell category (ID: {category})')
                thiscell['cellname'] = cbody[kk][1]['name']
                thiscell['category'] = category
                thiscell['segments'] = cbody[kk][1]['segments']
                thiscell['cellarea'] = 0.0 if not mpp else calculateCellArea(thiscell['segmenets'], mpp)
                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellslist = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
    return aixinfo, cellslist, cellsCount

## average of NC ratio and Nuclei area of suspicious/atypical cells
def getUROaverageOfSAcells(tclist):
    sumSncratio, sumAncratio = 0.0, 0.0
    sumSnucarea, sumAnucarea = 0, 0
    countS, countA = 0, 0
    for i in range(len(tclist)):
        if tclist[i]['category'] == 2:
            celltype = 'suspicious'
        elif tclist[i]['category'] == 3:
            celltype = 'atypical'
        else:
            continue
        nucleiArea = tclist[i]['cellarea']*tclist[i]['ncratio']
        if celltype == 'suspicious':
            sumSncratio += tclist[i]['ncratio']
            sumSnucarea += nucleiArea
            countS += 1
        else:
            sumAncratio += tclist[i]['ncratio']
            sumAnucarea += nucleiArea
            countA += 1
    if countS > 0:
        avgSncratio = sumSncratio / countS
        avgSnucarea = sumSnucarea / countS
    else:
        avgSncratio, avgSnucarea = 0.0, 0.0
    if countA > 0:
        avgAncratio = sumAncratio / countA
        avgAnucarea = sumAnucarea / countA
    else:
        avgAncratio, avgAnucarea = 0.0, 0.0
    return avgSncratio, avgSnucarea, avgAncratio, avgAnucarea

## count/analyze the cell information in AIxURO model
def getUROaverageOfTopCells(tclist, topNum=24, suspiciousOnly=True):
    acells = [] ## list of atypical cells
    scells = [] ## list of suspicious cells
    tcells = [] ## list of TOP number of cells to return
    for i in range(len(tclist)):
        if tclist[i]['category'] == 2 or tclist[i]['category'] == 3:
            thiscell = (tclist[i]['cellname'],
                        tclist[i]['score'],
                        tclist[i]['probability'],
                        tclist[i]['ncratio'],
                        tclist[i]['cellarea']*tclist[i]['ncratio'])
            if tclist[i]['category'] == 2:
                scells.append(thiscell)
            else:
                acells.append(thiscell)
    ## sort cell list
    scells.sort(key=lambda x: x[1], reverse=True)
    acells.sort(key=lambda x: x[1], reverse=True)
    ## TOP number of cells
    topCells = []
    cellCount = 0
    sumNCratio, sumNucarea = 0.0, 0.0
    ## 
    for i in range(len(scells)):
        sumNCratio += scells[i][3]
        sumNucarea += scells[i][4]
        cellCount += 1
        tcells.append(scells[i])
        if cellCount >= topNum:
            break
    if cellCount < topNum and suspiciousOnly == False:
        for i in range(len(acells)):
            sumNCratio += acells[i][3]
            sumNucarea += acells[i][4]
            cellCount += 1
            tcells.append(acells[i])
            if cellCount >= topNum:
                break
    if cellCount > 0:
        avgNCratio = sumNCratio / cellCount
        avgNucarea = sumNucarea / cellCount
    else:
        avgNCratio, avgNucarea = 0.0, 0.0
    return tcells, avgNCratio, avgNucarea

def countNumberOfTHYtraits(tclist, maxTraits, threshold=0.4):
    traitCount = [0 for i in range(maxTraits)]
    howmany = len(tclist)
    if howmany == 0:
        logger.error(f'empty cell list in countNumberOfTHYtraits()')
        return traitCount
    for i in range(howmany):
        celltraits = tclist[i]['traits']
        for j in range(len(tclist[i]['traits'])):
            if celltraits[j] >= threshold:
                traitCount[j] += 1
    return traitCount

##---------------------------------------------------------
## query slidename of all analyzed images
##---------------------------------------------------------
def queryAllSlideName(slide_type, thisdb=None):
    namelist = []
    if thisdb:
        if slide_type.lower() == 'urine':
            tblname = 'QCxURO'
        elif slide_type.lower() == 'thyroid':
            tblname = 'QCxTHY'
        logger.trace(f'[queryAllSlideName] {thisdb}: {tblname}')
        t0 = time.perf_counter()
        try:
            with sqlite3.connect(thisdb) as dbconn:
                cur = dbconn.cursor()
                cur.execute(f'SELECT slidelabel FROM {tblname}')
                rows = cur.fetchall()
                for row in rows:
                    namelist.append(row[0])
        except sqlite3.OperationalError as e:
            logger.error(f'something wrong when querying all the slide name, {e}')
    else:
        folderAnalyzed = qcxPATH['driveYhome']
        if slide_type.lower() == 'urine':
            folder = os.path.join(folderAnalyzed, 'aixuro')
        elif slide_type.lower() == 'thyroid':
            folder = os.path.join(folderAnalyzed, 'aixthy')
        logger.trace(f'starting queryAllSlideName({slide_type})...')
        t0 = time.perf_counter()
        medfiles = glob.glob(os.path.join(folder, '*.med'))
        for _, fmed in enumerate(medfiles):
            faix = fmed.replace('.med', '.aix')
            #logger.trace(f'{fmed} <=> {faix}')
            if os.path.exists(faix):
                namelist.append(os.path.splitext(os.path.basename(fmed))[0])
    logger.info(f'found {len(namelist)} {slide_type} slides with {time.perf_counter()-t0:0.6f} seconds')
    return namelist

def queryQCresult4slide(slide_type, slide_id):
    ## magic number for urine criteria
    magic_suspicious, magic_atypical = 6, 8
    ##
    folderAnalyzed = qcxPATH['driveYhome']
    aixmeta = {}
    aixmeta['medname'] = f'{slide_id}.med'
    if slide_type.lower() == 'urine':
        aixmeta['medpath'] = os.path.join(folderAnalyzed, 'aixuro')
    elif slide_type.lower() == 'thyroid':
        aixmeta['medpath'] = os.path.join(folderAnalyzed, 'aixthy')
    logger.trace(f'starting queryQCresult4slide({slide_type}, {slide_id})...')
    ##
    t0 = time.perf_counter()
    medfile = os.path.join(aixmeta['medpath'], aixmeta['medname'])
    if os.path.exists(medfile) == False:
        return {}
    
    aixfile = medfile.replace('.med', '.aix')
    aixinfo, cellslist, cellscount = getTargetCellsFromAIX(aixfile)
    if aixinfo['Model'] == 'AIxURO':
        aixmeta['rawdata'] = f'found {cellscount[2]} suspicious cells, {cellscount[3]} atypical cells'
        if cellscount[2] >= magic_suspicious:
            if cellscount[3] >= magic_atypical:
                aixmeta['signal1'], aixmeta['signal2'] = 'red', 'red'
                aixmeta['refnote'] = 'High likelihood of SHGUC or HGUC diagnosis'
            else:
                aixmeta['signal1'], aixmeta['signal2'] = 'red', 'green'
                aixmeta['refnote'] = 'Extreme and rare case, less likely in real world'
        else:
            if cellscount[3] >= magic_atypical:
                aixmeta['signal1'], aixmeta['signal2'] = 'green', 'red'
                aixmeta['refnote'] = 'Possible diagnosis of AUC; clinical information may be referenced to support the diagnosis'
            else:
                aixmeta['signal1'], aixmeta['signal2'] = 'green', 'green'
                aixmeta['refnote'] = 'Likely benign (NHGUC); may be excluded from further review'
    elif aixinfo['Model'] == 'AIxTHY':
        ## QC criteria for thyroid image is not defined yet, here is only for test
        sum_of_follicular = sum(cellscount[j] for j in range(1, len(cellscount)))
        percentage_of_follicular = 0.0 if sum_of_follicular == 0 else cellscount[1]/sum_of_follicular
        aixmeta['rawdata'] = f'{cellscount[1]} follicular cells: {cellscount[2]} ontocytic/hurthle cells; '
        NUMofTags = 20 if aixinfo['ModelVersion'][:6] in ['2025.2'] else 8
        traits = countNumberOfTHYtraits(cellslist, NUMofTags)
        if '2025.2' in aixinfo['ModelVersion']:
            traits_criteria = traits[2] > 0
            aixmeta['rawdata'] += f'Microfollicles: {traits[2]}'
        elif '2024.2' in aixinfo['ModelVersion']:
            traits_criteria = traits[0] > 0 and traits[1] > 0
            aixmeta['rawdata'] += f'hyperchromasia: {traits[0]}, clumpedchromtin: {traits[1]}'
        #
        aixmeta['signal1'] = 'red' if percentage_of_follicular > 0.7 else 'green'
        aixmeta['signal2'] = 'red' if traits_criteria else 'green'
        aixmeta['refnote'] = 'interpretation guideline is under construction'
    logger.info(f'found QC reference data for {slide_type} slides {slide_id} with {time.perf_counter()-t0:0.6f} seconds')
    return aixmeta

def queryQCresultfromDB(slide_type, slide_id, thisdb):
    ## magic number for urine criteria 
    magic_suspicious, magic_atypical = 6, 8
    ##
    if slide_type.lower() == 'urine':
        #dbname = 'demo_qcxuro.db'
        tblname = 'QCxURO'
    elif slide_type.lower() == 'thyroid':
        #dbname = 'demo_qcxthy.db'
        tblname = 'QCxTHY'
    #thisdb = os.path.join(qcxDBpath, dbname)
    metajson = []
    try:
        with sqlite3.connect(thisdb) as dbconn:
            cur = dbconn.cursor()
            cur.execute(f'SELECT * FROM {tblname} WHERE slidelabel = "{slide_id}"')
            rows = cur.fetchall()
            for row in rows:
                thismeta = {}
                if slide_type.lower() == 'urine':
                    thismeta['medname'] = row[16]
                    thismeta['medpath'] = row[17]
                    thismeta['aixdata'] = f'{row[4]} suspicious cells, {row[5]} atypical cells'
                    if row[4] >= magic_suspicious:
                        if row[5] >= magic_atypical:
                            thismeta['qcalert1'], thismeta['qcalert2'] = 'red', 'red'
                            thismeta['interpretation'] = 'High likelihood of SHGUC or HGUC diagnosis'
                        else:
                            thismeta['qcalert1'], thismeta['qcalert2'] = 'red', 'green'
                            thismeta['interpretation'] = 'Extreme and rare case, less likely in real world'
                    else:
                        if row[5] >= magic_atypical:
                            thismeta['qcalert1'], thismeta['qcalert2'] = 'green', 'red'
                            thismeta['interpretation'] = 'Possible diagnosis of AUC; clinical information may be referenced to support the diagnosis'
                        else:
                            thismeta['qcalert1'], thismeta['qcalert2'] = 'green', 'green'
                            thismeta['interpretation'] = 'Likely benign (NHGUC); may be excluded from further review'
                elif slide_type.lower() == 'thyroid':
                    sum_of_follicular = sum(row[j] for j in range(4, 10))
                    percentage_of_follicular = 0.0 if sum_of_follicular == 0 else row[4] / sum_of_follicular
                    thismeta['medname'] = row[32]
                    thismeta['medpath'] = row[33]
                    thismeta['aixdata'] = f'{row[10]} follicular cells: {row[11]} ontocytic/hurthle cells; '
                    if '2024.2' in row[31]:     # model version
                        traits_criteria = row[10] > 0 and row[11] > 0
                        thismeta['aixdata'] += f'hyperchromasia: {row[10]}, clumpedchromtin: {row[11]}'
                    elif '2025.2' in row[31]:
                        traits_criteria = row[12] > 0
                        thismeta['aixdata'] += f'Microfollicles: {row[12]}'
                    if percentage_of_follicular > 0.7 and traits_criteria:
                        thismeta['qcalert1'], thismeta['qcalert2'] = 'red', 'green'
                    else:
                        thismeta['qcalert1'], thismeta['qcalert2'] = 'green', 'green'
                    thismeta['interpretation'] = 'interpretation guideline is under construction'

                if len(thismeta):
                   metajson.append(thismeta)
    except sqlite3.OperationalError as e:
        logger.error(f'something wrong when querying slide {slide_id}, {e}')
    if len(metajson) > 1:
        logger.warning(f'more than one slide {slide_id} found in database, please check!')
    return metajson

## -------------------------------------------------------------- 
##  read .aix and metadata.json, save analysis metadata to 
##  sqlite3 database for QC workflow
## -------------------------------------------------------------- 
def saveAnalysisMetadata2DB4QC(slidelabel, qcdbname, watchfolder=''):
    if watchfolder == '':
        watchfolder = os.path.join(getModelWatchFolder(), 'done')
    thismed = os.path.join(watchfolder, f'{slidelabel}.med')
    if os.path.isfile(thismed) == False:
        logger.error(f'{slidelabel}.med file does not exist in {watchfolder}!')
        return
    thisaix = thismed.replace('.med', '.aix')
    if os.path.isfile(thisaix) == False:
        logger.error(f'[ERROR] {slidelabel}.aix file does not exist in {watchfolder}!')
        return
    ## which model
    medjson = getMetadataFromMED(thismed)
    thismpp = medjson.get('MPP', 0.0)
    aixinfo, cellcount, cellslist = getCellsInfoFromAIX(thisaix, thismpp)
    modelProduct = aixinfo.get('Model', 'unknown')
    modelVersion = aixinfo.get('ModelVersion', 'unknown')
    ## check database
    ##dbpath = aux.getConfig()['dbpath']
    '''
    if modelProduct.lower() == 'aixuro':
        dbname = os.path.join(qcxDBpath, 'demo_qcxuro.db')
    elif modelProduct.lower() == 'aixthy':
        dbname = os.path.join(qcxDBpath, 'demo_qcxthy.db')
    else:
        logger.warning(f'[WARNING] there is no database for model {modelProduct}')
        return
    '''
    ## add metadata into database
    medata = {}
    medata['label']  = slidelabel
    medata['zlayer'] = medjson['SizeZ']
    medata['zfocus'] = 0 if medata['zlayer'] == 1 else medjson.get('BestFocusLayer', 0)
    medata['similarity'] = aixinfo.get('SimilarityDegree', 0.0)
    medata['modeln'], medata['modelv'] = modelProduct, modelVersion
    medata['medfile'] = f'{slidelabel}.med'
    medata['medpath'] = watchfolder

    saveInferenceMetadata2DB(medata, cellcount, cellslist, qcdbname)

##---------------------------------------------------------
## subprocess.Popen to launch CytoInsights, activate watch folders
##---------------------------------------------------------
def launchCytoInsights(fname):
    if platform.system() != 'Windows':
        logger.error('[ERROR] launch CytoInsights in Windows only')
    viewer = r'C:\Program Files\AIxMed Cytology Viewer\AIxMed Cytology Viewer.exe'
    if os.path.exists(viewer) == False:
        viewerpath = glob.glob(r'C:\Program Files\WindowsApps\cyto*')
        viewer = f'{viewerpath[0]}\\app\\CytoInsights.exe'
        logger.trace(viewer)
        if os.path.exists(viewer) == False:
            logger.error('CytoInsights does not exist!')
        #subprocess.Popen(['explorer.exe', fname], shell=True)
        subprocess.Popen(['start', '', fname], shell=True)
    else:
        subprocess.Popen([viewer, fname])

def activateWatchFolders(watchbin=None, configfile=None):
    if platform.system() != 'Windows':
        logger.error('only works in Windows environment')
        return False

    watchthis = 'watch-wsi.exe' if not watchbin else watchbin
    if os.path.exists(watchthis):
        if configfile:
            thisconfig = configfile
        else:
            configpath = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi')
            if os.path.exists(os.path.join(configpath, 'config-watchwsi.json')):
                thisconfig = os.path.join(configpath, 'config-watchwsi.json')
            elif os.path.exists(os.path.join(configpath, 'config-qcapi-cch.json')):
                thisconfig = os.path.join(configpath, 'config-qcapi-cch.json')
            else:
                thisconfig = ''
        if thisconfig:
            cmdstr = [watchthis, "-p", thisconfig]
        else:
            cmdstr = [watchthis]
        logger.trace(f'start running {watchthis}')
        subprocess.Popen(cmdstr)
    else:
        logger.error(f'{watchthis} doese not exist!!')
        return False
    return True

'''
    traits of AIxTHY 2025.2-xxxx
        ['Papillary', 'NuclearCrowding', 'Microfollicles', 'FlatUniform',           ## architectureTraits
         'NuclearEnlargement', 'MultinucleatedGiantCell', 'Degenerated', 'Normal',  ## morphologicFeatures
         'Pseudoinclusions', 'Grooving', 'MarginalMicronucleoli',                   ## papillarythyroid
         'ClumpingChromatin', 'ProminentNucleoli',                                  ## eptheloid
         'Plasmacytoid', 'SaltAndPepper', 'Binucleation', 'Spindle',                ## medullarythyroid
         'LightnessEffect', 'DryingArtifact', 'Unfocused']                          ## artifactEffects
    traits of AIxTHY 2024.2-0625
        ['hyperchromasia', 'clumpedchromtin', 'irregularmembrane', 'pyknotic', 'lightnesseffect', 
         'dryingartifact', 'degenerated', 'smudged', 'unfocused', 'unfocused', 
         'binuclei', 'normal', 'FibrovascularCore', 'NuclearPlemorphism']
'''
