'''
auxfuncs contains 3 major sub-functions:
   (1) monitor scanner folders
   (2) update DeCart config.yaml and command line running DeCart 
'''
import os, sys
import glob
import shutil
import json, yaml
import time
import win32wnet, pywintypes
from .taskfunc import stopDeCart, restartDeCart
from .metafunc import saveInferenceResult2CSV
from loguru import logger

##---------------------------------------------------------
# 📝 logging to %localappdata% using loguru
##---------------------------------------------------------
def MonitorLogger(logfname=None, loglevel=None):
    log_level = 'TRACE' if (not loglevel) or loglevel.lower() not in ['info', 'debug', 'error'] else loglevel 
    if not logfname:
        logfname = 'watchwsi-debug.log'
    logfolder = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi')
    if os.path.exists(logfolder) == False:
        os.makedirs(logfolder)
    log_fname = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi', logfname)
    logformat = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <blue>Line {line: >4} ({file}):</blue> | <b>{message}</b>"
    #logger.add(sys.stdout, level=log_level, format=logformat, colorize=True, backtrace=True, diagnose=True)
    logger.add(log_fname, rotation='4 MB', level=log_level, format=logformat, colorize=False, backtrace=True, diagnose=True)

##---------------------------------------------------------
## configuration for this machine, should be customized for each machine
##---------------------------------------------------------
def initConfig4WatchWSI(thisconfig=None, isCmdRunningDeCart=False):
    if not thisconfig:
        dbfolder = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi', 'config-watchwsi.json')
        configfile = thisconfig if os.path.exists(dbfolder) else None
    if configfile:
        ## init environment based on configuration file
        args = None
        if os.path.exists(configfile) == False:
            logger.error(f'{configfile} does not exist, please contact with service team')
            return None
        try:
            with open(configfile, 'r', encoding='utf-8') as conf:
                args = json.load(conf)
        except FileNotFoundError:
            logger.error(f'{configfile} was not found')
        except json.JSONDecodeError:
            logger.error(f'{configfile} contains invalid JSON')
        except Exception as e:
            logger.error(f'an unexpected error occurred: {e}')
    else:
        ## default environment settings
        args = {
            'driveX': 'X:',
            'driveY': 'Y:',
            "homeX": "\\\\192.168.42.31\\autoinference",
            "userX": "Aperio", 
            "passX": "Sc@nscope123",
            "homeY": "\\\\192.168.42.33\\Auto Inference Backup",
            "userY": "aibadmin",
            "passY": "aibadmin12345",
            'home_qcapi': r"E:\ama_qcapi\this_scanner",
            "home_qcdb": r'E:\ama_qcapi\this_scanner\dbmeta'
	        "driveXhome": "X:\\CCH_scanner",
            "driveYhome": "Y:\\CCH_scanner\\medaix",
            "decartpath": r"C:\Program Files\WindowsApps\com.aixmed.decart_2.8.14.0_x64__pkjfmh18q18h8",
            "decart_ver": "2.8.14",
            "decart_exe": "C:\\Program Files\\WindowsApps\\com.aixmed.decart_2.8.14.0_x64__pkjfmh18q18h8\\decart.exe",
            "decartyaml": "C:\\Users\\AIX 0256\\AppData\\Roaming\\DeCart\\config.yaml"
        }
        # check folders are available
        if os.path.exists(args['driveX']) == False or os.path.exists(args['driveY']) == False:
            logger.error('working folders should be available before running watching folders')
            return None
    # local working folders
    args['foldermedaix'] = os.path.join(args['home_qcapi'], 'medaix')
    if os.path.exists(args['foldermedaix']) == False:
        os.makedirs(args['foldermedaix'])
    args['folderdecart'] = os.path.join(args['home_qcapi'], 'watchwsi')
    if os.path.exists(args['folderdecart']) == False:
        os.makedirs(args['folderdecart'])
    args['folderwsifile'] = os.path.join(args['home_qcapi'], 'wsifile')
    if os.path.exists(args['folderwsifile']) == False:
        os.makedirs(args['folderwsifile'])
    logger.trace('[watchwsi] working environment settings')

    if isCmdRunningDeCart:
        ## check config.yaml
        thisyaml = args['decartyaml']
        try:
            with open(thisyaml, 'r') as thisyaml:
                conf = yaml.load(thisyaml, Loader=yaml.FullLoader)
        except Exception as e:
            logger.error(f'an unexpected error occurred while loading (decart_config): {e}')
        if os.path.exists(conf['watch']) == False:
            logger.error(f'DeCart watch folder conf[watch] does not exist')
            args['decartwatch'] = ''
        else:
            args['decartwatch'] = conf['watch']
    else:
        args['decartwatch'] = os.path.join(args['home_qcapi'], 'watchwsi')
        args['dbname_QC_URO'] = 'demo_DBQC_URO.db'
        args['dbname_QC_THY'] = 'demo_DBQC_THY.db'

    return args

##---------------------------------------------------------
## update config.yaml (model / watch folder)
##---------------------------------------------------------
def updateRunningDeCartConfig(decartYaml, decartEXE, thismodel=None, watchfolder=None):
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

## -------------------------------------------------------------- 
##  map //{ip}/filepath to local drive (Windows only) 
## -------------------------------------------------------------- 
def mapWindowsPCasLocalDrive(drive_letter, dir4scanned_wsi, username, password):
    if os.path.exists(drive_letter) == False:    ## check if already connected
        #win32wnet.WNetAddConnection2(0, drive_letter, dir4scanned_wsi, None, username, password)
        #logger.info(f'{dir4scanned_wsi} is connected to {drive_letter}')
        domap = True
    else:
        if os.path.exists(dir4scanned_wsi) == False:
            logger.trace(f'{drive_letter} probably not connected to {dir4scanned_wsi}, try to re-connect')
            win32wnet.WNetCancelConnection2(drive_letter, 1, True)
            domap = True
        else:
            logger.info(f'{dir4scanned_wsi} is accessible, no need to re-connect')
            domap = False
    if domap:
        try:
            win32wnet.WNetAddConnection2(0, drive_letter, dir4scanned_wsi, None, username, password)
        except pywintypes.error as e:
            logger.error(f'connection error: {e}')
        else:
            logger.info(f'{dir4scanned_wsi} is connected to {drive_letter}')

##---------------------------------------------------------
## monitor changes in folders: scanner shared folder and
## decart watch folder
##---------------------------------------------------------
def backupAnalyzedImageFiles(srcpath, dstpath, modelname, backuptype):
    mlist = glob.glob(os.path.join(srcpath, '*.med'))
    backup_medaix = os.path.join(dstpath, modelname.lower())
    if os.path.isdir(backup_medaix) == False:
        os.mkdir(backup_medaix)
    for ii in range(len(mlist)):
        mfile = os.path.basename(mlist[ii])
        afile = mfile.replace('.med', '.aix')
        if os.path.isfile(os.path.join(srcpath, afile)) == False:
            logger.warning(f'{os.path.join(srcpath, afile)} does not exist!')
        else:
            if backuptype.lower() == 'copy':
                shutil.copy(os.path.join(srcpath, mfile), os.path.join(backup_medaix, mfile))
                shutil.copy(os.path.join(srcpath, afile), os.path.join(backup_medaix, afile))
            elif backuptype.lower() == 'move':
                shutil.move(os.path.join(srcpath, mfile), os.path.join(backup_medaix, mfile))
                shutil.move(os.path.join(srcpath, afile), os.path.join(backup_medaix, afile))
                #logger.trace(f'{mfile} was moved to {dstpath}')
    logger.info(f'{len(mlist)} .med/.aix files were moved to {dstpath}')

def startMonitorFolders(configfile, logfile):
    MonitorLogger(logfname=logfile)
    ## init environment
    args = initConfig4WatchWSI(thisconfig, isCmdRunningDeCart=True)
    # connect scanner local storage to X and Y:
    mapWindowsPCasLocalDrive(args['driveX'], args['homeX'], args['userX'], args['passX'])
    mapWindowsPCasLocalDrive(args['driveY'], args['homeY'], args['userY'], args['passY'])
    ## monitor scanner shared folders
    scannerURO = os.path.join(args['driveXhome'], 'aixuro')
    scannerTHY = os.path.join(args['driveXhome'], 'aixthy')
    ## monitor decart watch folder
    decartWatch = args['decartwatch']
    #print(decartWatch)
    if os.path.exists(scannerURO) == False or \
       os.path.exists(scannerTHY) == False or \
       os.path.exists(decartWatch) == False:
        #qclog('ERROR', 'one of scanner watch folders or decart watch folder does not exist')
        logger.error('one of scanner watch folders or decart watch folder does not exist')
        return False
    ## monitor decart DONE folder
    srcMEDAIX = decartWatch if cmdRunningDeCart else os.path.join(decartWatch, 'done')
    dstMEDAIX = args['driveYhome']
    folderHome = args['home_qcapi']
    folderBackup = args['foldermedaix']
    folderWSIbackup = args['folderwsifile']
    MONITORED_WSI = ['svs', 'ndpi', 'mrxs', 'tif', 'zip']
    while True:
        bWSIfound = False
        ## monitor AIxURO folder first
        whichmodel = 'AIxURO'
        anchortime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        #logger.trace(f"👀 Monitoring changes in: {scannerURO}, copy files created after {anchor_time}, model is {whichmodel}")
        flist = glob.glob(os.path.join(scannerURO, '*'))
        for file in flist:
            wsitype = os.path.splitext(file)[1].lower()[1:]
            if os.path.isfile(file) and wsitype in MONITORED_WSI:
            ## found, then copy to destination folder
            try:
                shutil.copy(file, decartWatch)
                if wsitype == 'mrxs':
                    dirmrxs = os.path.splitext(file)[0]
                    shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                logger.trace(f"Copied: {os.path.basename(file)} → {decartWatch}")
                bWSIfound = True
            except Exception as e:
                logger.error(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
        ## WSI files found
        if bWSIfound:
            t0 = time.perf_counter()
            logger.trace(f"➾ start {whichmodel} inference at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())}")
            ## manually running model inference
            aixmeta = doModelInference(decartWatch, modelname=whichmodel)
            ## save metadata of model inference analysis results
            if len(aixmeta) > 0:
                logger.info(f'processed {len(aixmeta)} urine slides with {time.perf_counter()-t0:0.6f} seconds')
                saveInferenceResult2CSV(aixmeta, os.path.join(folderHome, 'csvmeta'))
            ## backup WSI files and .med/.aix files
            backupAnalyzedImageFiles(decartWatch, whichmodel, args['driveYhome'], 'move')
            ## insert metadata into database
            thismodel = whichmodel.lower()
            backup_medaix = os.path.join(args['driveYhome'], thismodel)
            #dbfname = args['dbname_QC_URO']
            saveAnalyzedMetadata2DB4QC(aixmeta, backup_medaix, os.path.join(args['home'], 'dbmeta'), args['dbname_QC_URO'])
            ## remove WSI files
            wsilist = glob.glob(os.path.join(decartWatch, '*'))
            for wfile in wsilist:
                wsitype = os.path.splitext(wfile)[1].lower()[1:]
                if os.path.isfile(wfile) and wsitype in MONITORED_WSI:
                    wsiname = os.path.basename(wfile)
                    os.remove(wfile)    ## alternatively, move to a specified backup folder
                    if wsitype == 'zip':    ## 'mrxs':
                        mrxsdir = os.path.splitext(wsiname)[0]
                        #shutil.rmtree(os.path.join(WORK_FOLDER, mrxsdir))
                        os.remove(f'{mrxsdir}.zip')
                    ## temporary, in test phase
                    for ii in range(len(folders_to_watch)):
                        dfile = os.path.join(folders_to_watch[ii], wsiname)
                        if os.path.isfile(dfile):
                            os.remove(dfile)
                            if wsitype == 'mrxs':
                                mrxsdir = os.path.splitext(wsiname)[0]
                                if os.path.exist(mrxsdir):
                                    shutil.rmtree(os.path.join(folders_to_watch[ii], mrxsdir))
            logger.trace(f'{len(wsilist)} WSI files was been deleted!')
            logger.info(f'{len(aixmeta)} urine WSI files were processed')
            bWSIfound = False
        ##====================================================================##
        ## monitor AIxTHY folder
        whichmodel = 'AIxTHY'
        flist = glob.glob(os.path.join(scannerTHY, '*'))
        for file in flist:
            wsitype = os.path.splitext(file)[1].lower()[1:]
            if os.path.isfile(file) and wsitype in MONITORED_WSI:
            ## found, then copy to destination folder
            try:
                shutil.copy(file, decartWatch)
                if wsitype == 'mrxs':
                    dirmrxs = os.path.splitext(file)[0]
                    shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                logger.trace(f"Copied: {os.path.basename(file)} → {decartWatch}")
                bWSIfound = True
            except Exception as e:
                logger.error(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
        ## WSI files found
        if bWSIfound:
            t0 = time.perf_counter()
            logger.trace(f"➾ start {whichmodel} inference at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())}")
            ## manually running model inference
            aixmeta = doModelInference(decartWatch, modelname=whichmodel)
            ## save metadata of model inference analysis results
            if len(aixmeta) > 0:
                logger.info(f'processed {len(aixmeta)} urine slides with {time.perf_counter()-t0:0.6f} seconds')
                saveInferenceResult2CSV(aixmeta, os.path.join(folderHome, 'csvmeta'))
            ## backup WSI files and .med/.aix files
            backupAnalyzedImageFiles(decartWatch, whichmodel, args['driveYhome'], 'move')
            ## insert metadata into database
            thismodel = whichmodel.lower()
            backup_medaix = os.path.join(args['driveYhome'], thismodel)
            #dbfname = args['dbname_QC_URO']
            saveAnalyzedMetadata2DB4QC(aixmeta, backup_medaix, os.path.join(args['home'], 'dbmeta'), args['dbname_QC_THY'])
            ## remove WSI files
            wsilist = glob.glob(os.path.join(decartWatch, '*'))
            for wfile in wsilist:
                wsitype = os.path.splitext(wfile)[1].lower()[1:]
                if os.path.isfile(wfile) and wsitype in MONITORED_WSI:
                    wsiname = os.path.basename(wfile)
                    os.remove(wfile)    ## alternatively, move to a specified backup folder
                    if wsitype == 'zip':    ## 'mrxs':
                        mrxsdir = os.path.splitext(wsiname)[0]
                        #shutil.rmtree(os.path.join(WORK_FOLDER, mrxsdir))
                        os.remove(f'{mrxsdir}.zip')
                    ## temporary, in test phase
                    for ii in range(len(folders_to_watch)):
                        dfile = os.path.join(folders_to_watch[ii], wsiname)
                        if os.path.isfile(dfile):
                            os.remove(dfile)
                            if wsitype == 'mrxs':
                                mrxsdir = os.path.splitext(wsiname)[0]
                                if os.path.exist(mrxsdir):
                                    shutil.rmtree(os.path.join(folders_to_watch[ii], mrxsdir))
            logger.trace(f'{len(wsilist)} WSI files was been deleted!')
            logger.info(f'{len(aixmeta)} thyroid WSI files were processed')
        ##
        time.sleep(300)     ## wait 5 minutes for nothing  

def startMonitorDeCartFolders(configfile, logfile):
    MonitorLogger(logfname=logfile)
    ## init environment
    args = initConfig4WatchWSI(thisconfig)
    # connect Leica Aperio AT2 to X:
    username, password = args['userX'], args['passX']
    wsi_home = args['homeX']
    drive_wsi = args['driveX']
    mapWindowsPCasLocalDrive(drive_wsi, wsi_home, username, password)
    # connect scanner local storage to Y:
    mapWindowsPCasLocalDrive(args['driveY'], args['homeY'], args['userY'], args['passY'])
    ## monitor scanner shared folders
    scannerURO = os.path.join(args['driveXhome'], 'aixuro')
    scannerTHY = os.path.join(args['driveXhome'], 'aixthy')
    ## monitor decart watch folder
    decartWatch = args['decartwatch']
    #print(decartWatch)
    if os.path.exists(scannerURO) == False or \
       os.path.exists(scannerTHY) == False or \
       os.path.exists(decartWatch) == False:
        #qclog('ERROR', 'one of scanner watch folders or decart watch folder does not exist')
        logger.error('one of scanner watch folders or decart watch folder does not exist')
        return False
    ## monitor decart DONE folder
    srcMEDAIX = decartWatch if cmdRunningDeCart else os.path.join(decartWatch, 'done')
    dstMEDAIX = args['driveYhome']
    folderHome = args['home_qcapi']
    folderBackup = args['foldermedaix']
    folderWSIbackup = args['folderwsifile']
    MONITORED_WSI = ['svs', 'ndpi', 'mrxs', 'tif']
    startwatch_aixuro = time.time()
    startwatch_aixthy = time.time()
    ## forever watch loop
    #qclog('TRACE', f"👀 Monitoring scanner folders", 'startMonitorFolders')
    logger.trace(f"👀 Monitoring scanner folders", 'startMonitorFolders')
    configYAML = args['decartyaml']
    while True:
        bWSIfound = False
        # monitor aixuro folder in scanner
        whichmodel = 'AIxURO'
        thistime = time.time()
        anchor_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(thistime))
        #logger.trace(f"👀 Monitoring changes in: {scannerURO}, copy files created after {anchor_time}, model is {whichmodel}")
        flist = glob.glob(os.path.join(scannerURO, '*'))
        howmany = len(flist)
        if howmany > 0:
            t0 = time.perf_counter()
            #qclog('TRACE', f'found {howmany} urine slide images')
            logger.trace(f'found {howmany} urine slide images')
            if updateDeCartConfig(configYAML, args['decart_exe'], thismodel='AIxURO'):
                logger.info('model product has been changed to AIxURO')
                #qclog('INFO', 'model product has been changed to AIxURO')
            else:
                logger.error('something wrong while updating model to AIxURO')
                print('[ERROR] STOP watchwsi.exe')
                break
            for file in flist:
                wsitype = os.path.splitext(file)[1].lower()[1:]
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    ## found, then copy to destination folder
                    try:
                        shutil.copy(file, decartWatch)
                        if wsitype == 'mrxs':
                            dirmrxs = os.path.splitext(file)[0]
                            shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                        #qclog('TRACE', f"Copied: {os.path.basename(file)} → {decartWatch}")
                        logger.trace(f"Copied: {os.path.basename(file)} → {decartWatch}")
                        bWSIfound = True
                    except Exception as e:
                        #qclog('ERROR', f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
                        logger.error(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
        if bWSIfound:
            #time.sleep(300*howmany)     ## wait for model inference, estimated 5 minutes per slide
            while True:
                medfile = glob.glob(os.path.join(srcMEDAIX, '*.med'))
                logger.trace(f"{len(medfile)} of {howmany} urine WSI were analyzed")
                if len(medfile) == howmany:
                    break
                time.sleep(60)
            startwatch_aixuro = thistime
            ## copy .med/.aix to local backup folder
            backupAnalyzedImageFiles(srcMEDAIX, folderBackup, 'AIxURO', 'copy')
            backupAnalyzedImageFiles(srcMEDAIX, dstMEDAIX, 'AIxURO', 'move')
            ## move wsi files to local backup folder, for now
            backupURO = os.path.join(folderWSIbackup, 'aixuro')
            if os.path.exists(backupURO) == False:
                os.makedirs(backupURO)
            for file in flist:
                shutil.move(file, os.path.join(backupURO, os.path.basename(file)))
            #qclog('INFO', f'processed {howmany} urine slides with {time.perf_counter()-t0:0.6f} seconds')
            logger.info(f'processed {howmany} urine slides with {time.perf_counter()-t0:0.6f} seconds')
        ## check decart DONE folder
        mlist = glob.glob(os.path.join(srcMEDAIX, 'done'))
        if len(mlist):
            logger.warning('some .med/.aix still exist in DeCart done folder')
            break
        #
        ### sleep another 10 minutes
        time.sleep(600)
        #
        # monitor aixthy folder in scanner
        bWSIfound = False
        whichmodel = 'AIxTHY'
        thistime = time.time()
        anchor_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(thistime))
        #logger.trace(f"👀 Monitoring changes in: {scannerTHY}, copy files created after {anchor_time}, model is {whichmodel}")
        flist = glob.glob(os.path.join(scannerTHY, '*'))
        howmany = len(flist)
        if howmany > 0:
            t0 = time.perf_counter()
            logger.trace(f'found {howmany} thyroid slide images')
            if updateDeCartConfig(configYAML, args['decart_exe'], thismodel='AIxTHY'):
                logger.info('model product has been changed to AIxTHY')
            else:
                logger.error('something wrong while updating model to AIxTHY')
                print('[ERROR] STOP watchwsi.exe')
                break
            for file in flist:
                wsitype = os.path.splitext(file)[1].lower()[1:]
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    ## found, then copy to destination folder
                    try:
                        shutil.copy(file, decartWatch)
                        if wsitype == 'mrxs':
                            dirmrxs = os.path.splitext(file)[0]
                            shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                        logger.trace(f"Copied: {os.path.basename(file)} → {decartWatch}")
                        bWSIfound = True
                    except Exception as e:
                        logger.trace(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
        if bWSIfound:
            #time.sleep(300*howmany)     ## wait for model inference, estimated 5 minutes per slide
            while True:
                medfile = glob.glob(os.path.join(srcMEDAIX, '*.med'))
                logger.trace(f"{len(medfile)} of {howmany} thyroid WSI were analyzed")
                if len(medfile) == howmany:
                    break
                time.sleep(60)
            startwatch_aixthy = thistime
            ## copy .med/.aix to local backup folder
            backupAnalyzedImageFiles(srcMEDAIX, folderBackup, 'AIxTHY', 'copy')
            backupAnalyzedImageFiles(srcMEDAIX, dstMEDAIX, 'AIxTHY', 'move')
            ## move wsi files to local backup folder, for now
            backupTHY = os.path.join(folderWSIbackup, 'aixthy')
            if os.path.exists(backupTHY) == False:
                os.makedirs(backupTHY)
            for file in flist:
                shutil.move(file, os.path.join(backupTHY, os.path.basename(file)))
            logger.info(f'processed {howmany} thyroid slides with {time.perf_counter()-t0:0.6f} seconds')
        ## check decart DONE folder
        mlist = glob.glob(os.path.join(srcMEDAIX, 'done'))
        if len(mlist):
            logger.warning('some .med/.aix still exist in DeCart done folder')
            break
        ### sleep another 10 minutes
        time.sleep(600)

