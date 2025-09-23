import os, sys
import glob
import shutil
from loguru import logger
import yaml, json
import time
from datetime import timedelta
import gzip
import platform
import subprocess
from pathlib import Path

## -------------------------------------------------------------- 
##  global preset working folders 
## -------------------------------------------------------------- 
## 
qcxPATH = {
    'driveXhome': 'X:\\CCH_scanner',            # scanner shared folder
    'driveYhome': 'Y:\\CCH_scanner\\medaix',    # on-premise image storage
    'qcapi_home': 'E:\ama_qcapi\this_scanner',  # local working folders
    'decart_exe': "C:\\Program Files\\WindowsApps\\com.aixmed.decart_2.8.14.0_x64__pkjfmh18q18h8",
    'decartyaml': "C:\\ProgramData\\DeCart\\config.yaml"
}

def initConfig4QCAPI(configfile=None):
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

def getTargetCellsFromAIX(aixfile):
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
                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellslist = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
    return aixinfo, cellslist, cellsCount

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

## analyze QC reference data based on preset criteria
def getQCreferenceMetadata(medfile, medpath):
    ## magic number for urine criteria
    magic_suspicious, magic_atypical = 6, 8
    ##
    aixmeta = {}
    aixmeta['medname'] = medfile
    aixmeta['medpath'] = medpath
    aixfile = os.path.join(medpath, f'{medfile}.aix')
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
    return aixmeta

##---------------------------------------------------------
## find .med/.aix with os.scandir()
##---------------------------------------------------------
class listMEDAIX:
    def __init__(self, toppath=None):
        self.uromedaix = []
        self.thymedaix = []

    def scanMEDAIX(self, slidetype):
        ## find all sub-directories in toppath
        t0 = time.perf_counter()
        if slidetype.lower() == 'urine':
            self.uromedaix.clear()
            medpath = os.path.join(qcxPATH['driveYhome'], 'aixuro')
            topdir = Path(medpath)
            allimg = topdir.rglob('*.med')
            self.uromedaix = [str(med) for med in allimg if med.is_file() and Path(str(med).replace('.med', '.aix')).is_file()]
            howmany = len(self.uromedaix)
        elif slidetype.lower() == 'thyroid':
            self.thymedaix.clear()
            medpath = os.path.join(qcxPATH['driveYhome'], 'aixthy')
            topdir = Path(medpath)
            allimg = topdir.rglob('*.med')
            self.thymedaix = [str(med) for med in allimg if med.is_file() and Path(str(med).replace('.med', '.aix')).is_file()]
            howmany = len(self.thymedaix)
        consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
        logger.info(f'found {howmany} analyzed images in {medpath} with {consumed_time[:-3]}')

    def getAllSlides(self, slidetype):
        if slidetype.lower() == 'urine':
            return self.uromedaix
        elif slidetype.lower() == 'thyroid':
            return self.thymedaix
        else:
            return []

    def findAllSlideName(self, slidetype):
        t0 = time.perf_counter()
        if slidetype == 'urine':
            if len(self.uromedaix) == 0:
                self.scanMEDAIX(slidetype)
            namelist = []
            for med in self.uromedaix:
                namelist.append(os.path.splitext(os.path.basename(med))[0])
        elif slidetype == 'thyroid':
            if len(self.thymedaix) == 0:
                self.scanMEDAIX(slidetype)
            namelist = []
            for med in self.thymedaix:
                namelist.append(os.path.splitext(os.path.basename(med))[0])

        consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
        logger.info(f'found {len(namelist)} {slidetype} slides with {consumed_time[:-3]}')
        return namelist

    def findSlide(self, slidetype, slideid):
        if slidetype.lower() == 'urine':
            filteredslides = filter(lambda x: slideid in x, self.uromedaix)
        elif slidetype.lower() == 'thyroid':
            filteredslides = filter(lambda x: slideid in x, self.thymedaix)
        else:
            return []

        foundslides = []
        for med in filteredslides:
            medpath, medname = os.path.split(med)
            medfile = {'path': medpath, 'name': os.path.splitext(medname)[0]}
            foundslides.append(medfile)
        if len(foundslides) > 1:
            logger.warning(f'found {len(foundslides)} {slideid}.med in {slidetype} slides')

        qcmeta = []
        for thisfile in foundslides:
            aixmeta = getQCreferenceMetadata(thisfile['name'], thisfile['path'])
            qcmeta.append(aixmeta)
        return qcmeta

def searchSlideInFileList(slide_type, slide_name, filelist=None):
    global uroMEDAIX, thyMEDAIX

    filesfound = []
    if not filelist:
        filelist = uroMEDAIX if slide_type == 'urine' else thyMEDAIX
    logger.debug(f'{slide_name}, total {len(filelist)} files in cache')
    for thisfile in filelist:
        if thisfile['name'] == slide_name:
            filesfound.append(thisfile)
    logger.info(f'found {len(filesfound)} {slide_name}')
    return filesfound

def findSlideInDirectories(slidetype, toppath):
    global uroMEDAIX, thyMEDAIX

    t0 = time.perf_counter()
    ## find all sub-directories in toppath
    pathlist = []
    for path, _, _ in os.walk(toppath):
        pathlist.append(path)
    ##
    allslides = uroMEDAIX if slidetype == 'urine' else thyMEDAIX
    allslides = []
    for thispath in pathlist:
        filelist = os.scandir(thispath)
        for thisfile in filelist:
            if thisfile.is_file() and os.path.splitext(thisfile.name)[1].lower() == '.med':
                medfile = {}
                if os.path.exists(thisfile.path.replace('.med', '.aix')):
                    medfile['name'] = os.path.splitext(thisfile.name)[0]
                    medfile['path'] = thispath
                    allslides.append(medfile)
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    logger.info(f'found {len(allslides)} analyzed images in {toppath} with {consumed_time[:-3]}')
    return allslides

def findAnalyzedMEDAIX(slidetype, slideid, toppath):
    ## find all sub-directories in toppath
    allfound = MEDLIST.findSlide(slidetype, slideid)
    if len(allfound) == 0:      ## reset MEDLIST if can't find the slideid at first search
        if slidetype.lower() == 'urine':
            MEDLIST.scanMEDAIX(os.path.join(toppath, 'aixuro'), MEDLIST.uromedaix)
        elif slidetype.lower() == 'thyroid':
            MEDLIST.scanMEDAIX(os.path.join(toppath, 'aixthy'), MEDLIST.thymedaix)
        allfound = MEDLIST.findSlide(slidetype, slideid)
    if len(allfound) > 1:
        logger.warning(f'found {len(allfound)} {slideid}.med in {toppath} and subdirectories')
    ##
    qcmeta = []
    for thisfile in allfound:
        aixmeta = getQCreferenceMetadata(thisfile['name'], thisfile['path'])
        qcmeta.append(aixmeta)
    return qcmeta

##---------------------------------------------------------
## query slidename of all analyzed images
##---------------------------------------------------------
def queryAllSlideName(slide_type):
    folderAnalyzed = qcxPATH['driveYhome']
    if slide_type.lower() == 'urine':
        folder = os.path.join(folderAnalyzed, 'aixuro')
    elif slide_type.lower() == 'thyroid':
        folder = os.path.join(folderAnalyzed, 'aixthy')
    logger.trace(f'starting queryAllSlideName({slide_type})...')
    t0 = time.perf_counter()
    medfiles = glob.glob(os.path.join(folder, '*.med'))
    namelist = []
    for _, fmed in enumerate(medfiles):
        faix = fmed.replace('.med', '.aix')
        #logger.trace(f'{fmed} <=> {faix}')
        if os.path.exists(faix):
            namelist.append(os.path.splitext(os.path.basename(fmed))[0])
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    logger.info(f'found {len(namelist)} {slide_type} slides with {consumed_time[:-3]}')
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
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    logger.info(f'found QC reference data for {slide_type} slides {slide_id} with {consumed_time[:-3]}')
    return aixmeta

def queryQCresult_from_images(slide_type, slide_id):
    folderAnalyzed = qcxPATH['driveYhome']
    if slide_type.lower() == 'urine':
        toppath = os.path.join(folderAnalyzed, 'aixuro')
    elif slide_type.lower() == 'thyroid':
        toppath = os.path.join(folderAnalyzed, 'aixthy')
    logger.trace(f'starting queryQCresult_from_images({slide_type}, {slide_id})...')
    ##
    t0 = time.perf_counter()
    foundslide = findAnalyzedMEDAIX(slide_type, slide_id, toppath)
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    logger.info(f'found {len(foundslide)} QC reference data for {slide_type} slides {slide_id} with {consumed_time[:-3]}')
    return foundslide[0]

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
