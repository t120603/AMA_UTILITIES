'''
auxfuncs contains 3 major sub-functions:
   (1) monitor scanner folders and DeCart watch folder
   (2) update DeCart config.yaml and restart DeCart task (2.8.x) / service (2.7.x) 
'''
import os
from pathlib import Path
import glob
import shutil
import json, yaml
import time
from datetime import timedelta, datetime
import win32wnet, pywintypes
from .taskfunc import stopDeCart, restartDeCart
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
def initConfig4WatchWSI(configfile=None):
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

    return args

##---------------------------------------------------------
## check whether 'error' was in decart.log
##---------------------------------------------------------
def errorRules(line, tspos, anchor_dt):
    tf = '%Y-%m-%dT%H:%M:%S'
    #errstr = 'error: exist status 1'
    if tspos == 5:      ## decart.log
        isError = line and line[0:4] == 'time' and datetime.strptime(line[tspos:tspos+19], tf) > anchor_dt and 'error' in line
    else:       ## debug.log
        isError = line and line[0:2] == '20' and datetime.strptime(line[tspos:tspos+19], tf) > anchor_dt and 'error' in line
    return isError

def errorInDeCartlog(model2025, anchor_dt):
    if model2025:
        decartlog = Path(os.getenv('LOCALAPPDATA')) / 'decart' / 'debug.log'
        tspos = 0
    else:
        decartlog = Path(r'c:\ProgramData') / 'decart' / 'decart.log'
        tspos = 5
    if decartlog.exists() == False:
        logger.error(f'{str(decartlog)} does not exist')
        return True
    ## load decart log
    contents = decartlog.read_text()
    lines = contents.splitlines()
    tformat = '%Y-%m-%dT%H:%M:%S'
    #nowDate = datetime.now().strftime('%Y-%m-%d')
    log_today = filter(lambda x: errorRules(x, tspos, anchor_dt), lines)
    errlog = list(log_today)
    return errlog
    #errlog = []
    #for rr in todaylogs:
    #    dt = datetime.strptime(rr[tspos:tspos+19], tformat)
    #    #logger.debug(f'-{anchor_dt}-{dt}-{dt>anchor_dt}-{'error' in rr}:: {rr}')
    #    if (dt > anchor_dt):
    #        errlog.append(rr[tspos:])
    '''
    logstr = []
    for rr in lines:
        if (not model2025 and len(rr) > 5 and rr[0:4] == 'time') or (model2025 and len(rr) and rr[0:2] == '20'):
            dt = datetime.strptime(rr[tspos:tspos+19], tformat)
            logger.debug(f'-{anchor_dt}-{dt}-{dt>anchor_dt}-{'error' in rr}:: {rr}')
            if (dt > anchor_dt) and ('errro' in rr): 
                logstr.append(rr[tspos:])
    '''
    # find error that DeCart failed to model inference
    #if len(errlog) > 0:
    #    logger.debug(f'{len(errlog) errors found!)}')
    #return errlog

##---------------------------------------------------------
## update config.yaml (model / watch folder)
##---------------------------------------------------------
def updateDeCartConfig(decartYaml, decartEXE, thismodel=None, watchfolder=None):
    isOK = True
    t0 = time.perf_counter()
    conf = None
    try:
        with open(decartYaml, 'r') as curyaml:
            conf = yaml.load(curyaml, Loader=yaml.FullLoader)
    except FileNotFoundError:
        logger.error(f'{decartYaml} does not exist')
        isOK = False
    except Exception as e:
        logger.error(f'an unexpected error occurred: {e}')
        isOK = False

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
            time.sleep(30)
            ## restart DeCart
            restartDeCart(is_a_service, decartEXE)
            #
            logger.info(f'spent {timedelta(seconds=time.perf_counter()-t0)} to update config.yaml')
    if not bUpdate:
        logger.trace(f'preset is already {thismodel}, no need to update config.yaml ({time.perf_counter()-t0:,.3f} seconds)')
    return isOK

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
def backupAnalyzedImageFiles(srcpath, dstpath, wsilist, wsicompleted, modelname, backuptype):
    if os.path.exists(dstpath) == False:        ## lost connection to dstpath
        logger.error(f'lost connection to {dstpath}, unable to {backuptype} files')
        return
    #mlist = glob.glob(os.path.join(srcpath, '*.med'))
    backup_medaix = os.path.join(dstpath, modelname.lower())
    if os.path.isdir(backup_medaix) == False:
        os.mkdir(backup_medaix)
    for ii in range(len(wsicompleted)):
    ##for wsi in wsilist:
        if wsicompleted[ii] == False:
            continue
        wfile = os.path.basename(wsilist[ii])
        mfile = f'{os.path.splitext(wfile)[0]}.med'
        afile = f'{os.path.splitext(wfile)[0]}.aix'
        if os.path.isfile(os.path.join(srcpath, afile)) == False:
            logger.warning(f'{os.path.join(srcpath, afile)} does not exist!')
        else:
            if backuptype.lower() == 'copy':
                try:
                    shutil.copy(os.path.join(srcpath, mfile), os.path.join(backup_medaix, mfile))
                    shutil.copy(os.path.join(srcpath, afile), os.path.join(backup_medaix, afile))
                except PermissionError:
                    logger.error(f'insufficient permission to copy the file')
                except OSError as e:
                    logger.error(f'OS error occurred: {e}')
            elif backuptype.lower() == 'move':
                try:
                    shutil.move(os.path.join(srcpath, mfile), os.path.join(backup_medaix, mfile))
                    shutil.move(os.path.join(srcpath, afile), os.path.join(backup_medaix, afile))
                except PermissionError:
                    logger.error(f'permission denied while accessing the moving files')
                except shutil.Error as e:
                    logger.error(f'an error occurred: {e}')
                except Exception as e:
                    logger.error(f'failed to move analyzed images: {e}')
                #logger.trace(f'{mfile} was moved to {dstpath}')
    logger.info(f'{backuptype} {len(wsicompleted)} .med/.aix files to {dstpath} completed!')

##---------------------------------------------------------
## check WSI file availability using openslide-python
##---------------------------------------------------------
import openslide
from openslide import OpenSlideError

def checkWSIavailable(wsi):
    isWSI = True
    if os.path.splitext(wsi)[0].lower() == '.zip':
        logger.debug('openslide-python can not veryify *.zip WSI file')
    else:
        ## can openslide open this wsi file??
        try:
            # Attempt to open a slide file
            slide = openslide.OpenSlide(wsi)
        except FileNotFoundError:
            logger.error(f'{os.path.basename(wsi)} file was not found.')
            isWSI = False
        except OpenSlideError as e:
            logger.error(f"OpenSlideError: {e} - {os.path.basename(wsi)}")
            isWSI = False
        except Exception as e:
            logger.error(f"An unexpected error occurred ({os.path.basename(wsi)}): {e}")
            isWSI = False
    return isWSI

##---------------------------------------------------------
## check model inference completed, or not
##---------------------------------------------------------
def checkDeCartCompletion(wsilist, watchfolder, wsicompleted, model2025, dt_anchor):
    Inference_a_WSI = 10    ## roughly, 10 minutes for a 7-layer WSI file; more than 30 minutes for a 21-layer WSI
    howmanywsi = len(wsilist)
    expectedInferenceTime = howmanywsi * Inference_a_WSI * 60
    errorfound = False
    if len(wsicompleted) != howmanywsi:
        logger.error(f'({wsicompleted}) does not match wsilist length: {howmanywsi}')
        return True  # error found
    t0 = time.perf_counter()
    while True:     ## forever loop to wait for model inference completion
        if sum(wsicompleted) == howmanywsi:
            errorfound = False
            break
        else:
            for i, wsi in enumerate(wsilist):
                if wsicompleted[i] == False:
                    thiswsi = Path(wsi)
                    thisaix = Path(watchfolder) / 'done' / f'{thiswsi.stem}.aix'
                    if thisaix.exists():
                        logger.info(f'{str(thisaix)} inference completed')
                        wsicompleted[i] = True
            ## check consumed time
            consumedtime = time.perf_counter()-t0
            if consumedtime > expectedInferenceTime:
                logger.warning(f'model inference time ({consumedtime}) exceeds expected time {expectedInferenceTime} seconds; anchor is {dt_anchor}')
                errlog = errorInDeCartlog(model2025, dt_anchor)
                if len(errlog) > 0:
                    ## dump decart error messages to log
                    for errmsg in errlog:
                        logger.error(errmsg)
                    errorfound = True
                    break
                else:
                    #t0 = time.perf_counter()
                    expectedInferenceTime += (len(wsicompleted)-sum(wsicompleted)) * 10 * 60
            else:
                logger.info(f'{sum(wsicompleted)} of {len(wsicompleted)} files analysis completed')
                time.sleep(120)
    if errorfound:
        for i in range(len(wsilist)):
            fname = os.path.basename(wsilist[i])
            errorwsi = list(filter(lambda x: fname in x, errlog))
            if len(errorwsi):
                logger.debug(f'{wsilist[i]} -- {errorwsi}')
                wsicompleted[i] = False
    return errorfound

##---------------------------------------------------------
## connect to scanner/decart watch folders
##---------------------------------------------------------
def connect2scanner_and_imagestorage(args):
    # connect scanner local storage to X:
    mapWindowsPCasLocalDrive(args['driveX'], args['homeX'], args['userX'], args['passX'])
    # connect scanner local storage to Y:
    mapWindowsPCasLocalDrive(args['driveY'], args['homeY'], args['userY'], args['passY'])
    ## check the connection
    Xok = os.path.exists(args['driveXhome'])
    Yok = os.path.exists(args['driveYhome'])
    return Xok, Yok

##---------------------------------------------------------
## start monitoring scanner/decart watch folders 
##---------------------------------------------------------
def checkCopyWSIcompleted(srcwsi, dstwsi):
    filecopied = False
    escape_seconds = 0
    if checkWSIavailable(srcwsi):
        src_stat = os.stat(srcwsi)
        try:
            shutil.copy(srcwsi, dstwsi)
            filecopied = True
        except PermissionError:
            logger.error(f'insufficient permission to copy the file {os.path.basename(srcwsi)}')
        except OSError as e:
            logger.error(f'OS error occurred ({os.path.basename(srcwsi)}): {e}')
        # check the filesize is identical
        if filecopied:
            while True:
                dst_stat = os.stat(dstwsi)
                if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime <= dst_stat.st_mtime:
                    filecopied = True
                    break
                time.sleep(10)
                escape_seconds += 10
                if escape_seconds > 1200:    ## 20 minutes
                    logger.error(f'copying {srcwsi} to DeCart watch folder more than {escape_seconds} seconds!!')
    return filecopied

def OLD_checkCopyWSIcompleted(srcwsi, dstwsi):
    filecopied = False
    if checkWSIavailable(srcwsi):
        escape_seconds = 0
        shutil.copy(srcwsi, dstwsi)
        while True:
            src_stat = os.stat(srcwsi)
            dst_stat = os.stat(dstwsi)
            if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime <= dst_stat.st_mtime:
                filecopied = True
                break
            time.sleep(10)
            escape_seconds += 10
            if escape_seconds > 1200:    ## 20 minutes
                logger.error(f'copying {srcwsi} to DeCart watch folder more than {escape_seconds} seconds!!')
    return filecopied

def startMonitorFolders(configfile, logfile):
    MonitorLogger(logfname=logfile)
    ## init environment
    args = initConfig4WatchWSI(configfile)
    # connect Leica Aperio AT2 to X:, and connect scanner local storage to Y:
    connect2scanner_and_imagestorage(args)
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
    srcMEDAIX = os.path.join(decartWatch, 'done')
    dstMEDAIX = args['driveYhome']
    folderBackup = args['foldermedaix']
    folderWSIbackup = args['folderwsifile']
    MONITORED_WSI = ['svs', 'ndpi', 'mrxs', 'tif', 'zip', 'tiff']
    ## forever watch loop
    logger.trace(f"👀 Monitoring scanner folders", 'startMonitorFolders')
    configYAML = args['decartyaml']
    byebye = False
    logger.trace(f'watching urine WSI folder {scannerURO}...')
    while True:
        ## forever watch loop for urine slide till new thyroid WSI found
        while True:
            if os.path.exists(scannerURO) == False:
                logger.warning(f'lost connection to {scannerURO}, try re-connecting ...')
                ## connect scanner/image storage again (once)
                xok, yok = connect2scanner_and_imagestorage(args)
                if not xok or not yok:
                    logger.error(f'lost connection to {scannerURO}, watchwsi.exe will be shutdown')
                    byebye = True
                    break
            bWSIfound = False
            # monitor aixuro folder in scanner
            flist = glob.glob(os.path.join(scannerURO, '*'))
            wsilist = []
            for file in flist:
                wsitype = os.path.splitext(file)[1].lower()[1:]
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    wsilist.append(file)
            howmany = len(wsilist)
            if howmany > 0:
                t0 = time.perf_counter()
                #dt_anchor = datetime.now()-timedelta(seconds=1)      ## for check decart log
                anchortime = True
                logger.trace(f"found {howmany} urine slide images at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                if updateDeCartConfig(configYAML, args['decart_exe'], thismodel='AIxURO'):
                    logger.info('model product is AIxURO')
                else:
                    logger.error('something wrong while updating model to AIxURO, will stop watchwsi.exe')
                    print('[ERROR] STOP watchwsi.exe')
                    byebye = True
                    break
                filecopied = [False for _ in range(howmany)]
                for ii in range(howmany):
                    wfile = wsilist[ii]
                    wsitype = os.path.splitext(wfile)[1].lower()[1:]
                    try:
                        #shutil.copy(file, decartWatch)
                        if wsitype == 'mrxs':
                            dirmrxs = os.path.splitext(wfile)[0]
                            shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                        if checkCopyWSIcompleted(wfile, os.path.join(decartWatch, os.path.basename(wfile))):
                            if anchortime:
                                dt_anchor = datetime.now()-timedelta(seconds=0.5)      ## for check decart log
                                anchortime = False
                            logger.trace(f"Copied: {os.path.basename(wfile)} → {decartWatch}")
                            filecopied[ii] = True
                        else:
                            #wsilist.remove(file)
                            logger.debug(f'{os.path.basename(wfile)} was moved!')
                    except Exception as e:
                        logger.error(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
                howmany = sum(filecopied)
                bWSIfound = True if howmany else False
                logger.debug(f'{howmany} WSI files were copied to DeCart watch folder')
            if bWSIfound:
                logger.debug(f'start tracing decart.log from {dt_anchor} ...')
                wsicompleted = []
                for ii in range(len(filecopied)):
                    if filecopied[ii]:
                        wsicompleted.append(False)
                    else:
                        wsilist.remove(wsilist[ii])
                logger.debug(f'waiting for {len(wsicompleted)}:({len(wsilist)}) wsi files ....')
                isModel2025 = False if 'ProgramData' in configYAML else True
                errorfound = checkDeCartCompletion(wsilist, decartWatch, wsicompleted, isModel2025, dt_anchor)
                ## copy .med/.aix to local backup folder
                backupURO = os.path.join(folderWSIbackup, 'aixuro')
                if os.path.exists(backupURO) == False:
                    os.makedirs(backupURO)
                dstURO = os.path.join(dstMEDAIX, 'aixuro')
                if os.path.exists(dstURO) == False:
                    os.makedirs(dstURO)
                if errorfound:      ## partial wsi files were completed
                    logger.debug(f'result of model inference: {wsicompleted}')
                    failed_wsi = os.path.join(backupURO, 'failedWSI')
                    if os.path.exists(failed_wsi) == False:
                        os.makedirs(failed_wsi)
                    for i, file in enumerate(wsilist):
                        wfile = os.path.basename(file)
                        mfile = f'{os.path.splitext(wfile)[0]}.med'
                        afile = f'{os.path.splitext(wfile)[0]}.aix'
                        if wsicompleted[i]:
                            ## copy .med/.aix to local folder for backup
                            try:
                                shutil.copy(os.path.join(srcMEDAIX, mfile), os.path.join(backupURO, mfile))
                                shutil.copy(os.path.join(srcMEDAIX, afile), os.path.join(backupURO, afile))
                            except PermissionError:
                                logger.error(f'insufficient permission to copy the file')
                            except OSError as e:
                                logger.error(f'OS error occurred: {e}')
                            ## move .med/.aix to image storage
                            try:
                                shutil.move(os.path.join(srcMEDAIX, mfile), os.path.join(dstURO, mfile))
                                shutil.move(os.path.join(srcMEDAIX, afile), os.path.join(dstURO, afile))
                            except PermissionError:
                                logger.error(f'permission denied while accessing the moving files')
                            except shutil.Error as e:
                                logger.error(f'an error occurred: {e}')
                            except Exception as e:
                                logger.error(f'failed to move analyzed images: {e}')
                            ## local wsi backup folder
                            localwsibackup = os.path.join(folderWSIbackup, 'aixuro')
                        else:       ## decart failed to model inference this file
                            localwsibackup = os.path.join(folderWSIbackup, 'aixuro', 'failedWSI')
                            ## delete failed WSI from decart watch folder
                            failedwsi = os.path.join(decartWatch, wfile)
                            try:
                                os.unlink(failedwsi)
                                logger.trace(f'os.unlink({failedwsi})')
                            except FileNotFoundError:
                                logger.error(f'{failedwsi} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {failedwsi}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {failedwsi}: {e}')                           
                        ## move wsi files to local backup folder, for now
                        try:
                            shutil.move(file, os.path.join(localwsibackup, wfile))
                            logger.trace(f'move {file} to {os.path.join(localwsibackup, wfile)}')
                        except PermissionError:
                            logger.error(f'Permission denied when moving {file}')
                        except OSError as e:
                            logger.error(f'Error occurred while moving file: {e}')
                        ## delete if still exist
                        if os.path.exists(file):
                            try:
                                os.unlink(file)
                                logger.trace(f'os.unink({file})')
                            except FileNotFoundError:
                                logger.error(f'{file} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {file}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {file}: {e}')                           
                        ## I don't know why??
                        if os.path.exists(file):
                            logger.error(f'[FATAL] why {file} still existed !!????')
                            newfile = f'{file}.err'
                            try:
                                os.rename(file, newfile)
                            except FileExistsError:
                                logger.error("The new file name already exists.")
                            except OSError as e:
                                logger.error(f"Error: {e}")
                else:   ## all wsi files were analyzed completed
                    backupAnalyzedImageFiles(srcMEDAIX, folderBackup, flist, wsicompleted, 'AIxURO', 'copy')
                    backupAnalyzedImageFiles(srcMEDAIX, dstMEDAIX, flist, wsicompleted, 'AIxURO', 'move')
                    ## move wsi files to local backup folder, for now
                    for file in flist:
                        try:
                            shutil.move(file, os.path.join(backupURO, os.path.basename(file)))
                        except PermissionError:
                            logger.error(f'Permission denied when moving {file}')
                        except OSError as e:
                            logger.error(f'Error occurred while moving file: {e}')
                        ## delete if still exist
                        if os.path.exists(file):
                            try:
                                os.remove(file)
                            except FileNotFoundError:
                                logger.error(f'{file} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {file}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {file}: {e}')
                consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
                logger.info(f'processed {howmany} urine slides with {consumed_time[:-3]}')
            ## check decart DONE folder
            mlist = glob.glob(os.path.join(srcMEDAIX, 'done'))
            if len(mlist):
                logger.warning('some .med/.aix still exist in DeCart done folder')
                break
            ##
            ## goto thyroid loop if thyroid WSI found, or stay in urine loop
            flist = glob.glob(os.path.join(scannerTHY, '*'))
            howmany = 0
            for file in flist:
                wsitype = os.path.splitext(file)[1].lower()[1:]
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    howmany += 1
            if howmany > 0:     ## thyroid WSI found
                break
            else:
                ### sleep another 3 minutes
                time.sleep(180)
        if byebye:
            break
        #
        ## forever watch loop for urine slide till new thyroid WSI found
        logger.trace('watching urine WSI folder {scannerTHY}...')
        while True:
            if os.path.exists(scannerTHY) == False:
                logger.warning(f'lost connection to {scannerTHY}, try re-connecting ...')
                ## connect scanner/image storage again (once)
                xok, yok = connect2scanner_and_imagestorage(args)
                if not xok or not yok:
                    logger.error(f'lost connection to {scannerTHY}, watchwsi.exe will be shutdown')
                    byebye = True
                    break
            # monitor aixthy folder in scanner
            bWSIfound = False
            flist = glob.glob(os.path.join(scannerTHY, '*'))
            wsilist = []
            for file in flist:
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    wsilist.append(file)
            howmany = len(wsilist)
            if howmany > 0:
                t0 = time.perf_counter()
                #dt_anchor = datetime.now()-timedelta(seconds=1)      ## for check decart log
                anchortime = True
                logger.trace(f"found {howmany} thyroid slide image at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                if updateDeCartConfig(configYAML, args['decart_exe'], thismodel='AIxTHY'):
                    logger.info('model product is AIxTHY')
                else:
                    logger.error('something wrong while updating model to AIxTHY, will stop watchwsi.exe')
                    print('[ERROR] STOP watchwsi.exe')
                    byebye = True
                    break
                filecopied = [False for _ in range(howmany)]
                for ii in range(howmany):
                    wfile = wsilist[ii]
                    wsitype = os.path.splitext(wfile)[1].lower()[1:]
                    try:
                        #shutil.copy(file, decartWatch)
                        if wsitype == 'mrxs':
                            dirmrxs = os.path.splitext(wfile)[0]
                            shutil.copytree(dirmrxs, os.path.join(decartWatch, os.path.split(dirmrxs)[1]))
                        if checkCopyWSIcompleted(wfile, os.path.join(decartWatch, os.path.basename(wfile))):
                            if anchortime:
                                dt_anchor = datetime.now()-timedelta(seconds=0.5)      ## for check decart log
                                anchortime = False
                            logger.trace(f"Copied: {os.path.basename(wfile)} → {decartWatch}")
                            filecopied[ii] = True
                        else:
                            #wsilist.remove(file)
                            logger.debug(f'{os.path.basename(wfile)} was moved!')
                    except Exception as e:
                        logger.trace(f"Copy failed: {os.path.basename(file)} → {decartWatch} | Error: {str(e)}")
                howmany = sum(filecopied)
                bWSIfound = True if howmany else False
                logger.debug(f'{howmany} WSI files were copied to DeCart watch folder')
            if bWSIfound:
                logger.debug(f'start tracing decart.log from {dt_anchor} ...')
                wsicompleted = []
                for ii in range(len(filecopied)):
                    if filecopied[ii]:
                        wsicompleted.append(False)
                    else:
                        wsilist.remove(wsilist[ii])
                logger.debug(f'waiting for {len(wsicompleted)}:({len(wsilist)}) wsi files ....')
                isModel2025 = False if 'ProgramData' in configYAML else True
                errorfound = checkDeCartCompletion(wsilist, decartWatch, wsicompleted, isModel2025, dt_anchor)
                ## copy .med/.aix to local backup folder
                backupTHY = os.path.join(folderWSIbackup, 'aixthy')
                if os.path.exists(backupTHY) == False:
                    os.makedirs(backupTHY)
                dstTHY = os.path.join(dstMEDAIX, 'aixthy')
                if os.path.exists(dstTHY) == False:
                    os.makedirs(dstTHY)
                if errorfound:      ## not all wsi files were model inference completed
                    logger.debug(f'result of model inference: {wsicompleted}')
                    failed_wsi = os.path.join(backupTHY, 'failedWSI')
                    if os.path.exists(failed_wsi) == False:
                        os.makedirs(failed_wsi)
                    for i, file in enumerate(wsilist):
                        wfile = os.path.basename(file)
                        mfile = f'{os.path.splitext(wfile)[0]}.med'
                        afile = f'{os.path.splitext(wfile)[0]}.aix'
                        if wsicompleted[i]:
                            ## copy .med/.aix to local folder for backup
                            try:
                                shutil.copy(os.path.join(srcMEDAIX, mfile), os.path.join(backupTHY, mfile))
                                shutil.copy(os.path.join(srcMEDAIX, afile), os.path.join(backupTHY, afile))
                            except PermissionError:
                                logger.error(f'insufficient permission to copy the file')
                            except OSError as e:
                                logger.error(f'OS error occurred: {e}')
                            ## move .med/.aix to image storage
                            try:
                                shutil.move(os.path.join(srcMEDAIX, mfile), os.path.join(dstTHY, mfile))
                                shutil.move(os.path.join(srcMEDAIX, afile), os.path.join(dstTHY, afile))
                            except PermissionError:
                                logger.error(f'permission denied while accessing the moving files')
                            except shutil.Error as e:
                                logger.error(f'an error occurred: {e}')
                            except Exception as e:
                                logger.error(f'failed to move analyzed images: {e}')
                            ## local wsi backup folder
                            localwsibackup = os.path.join(folderWSIbackup, 'aixthy')
                        else:       ## decart failed to model inference this file
                            localwsibackup = os.path.join(folderWSIbackup, 'aixthy', 'failedWSI')
                            ## delete failed WSI from decart watch folder
                            failedwsi = os.path.join(decartWatch, wfile)
                            try:
                                os.unlink(failedwsi)
                                logger.trace(f'os.unlink({failedwsi})')
                            except FileNotFoundError:
                                logger.error(f'{failedwsi} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {failedwsi}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {failedwsi}: {e}')                           
                        ## move wsi files to local backup folder, for now
                        try:
                            shutil.move(file, os.path.join(localwsibackup, wfile))
                            logger.trace(f'move {file} to {os.path.join(localwsibackup, wfile)}')
                        except PermissionError:
                            logger.error(f'Permission denied when moving {file}')
                        except OSError as e:
                            logger.error(f'Error occurred while moving file: {e}')
                        ## delete if still exist
                        if os.path.exists(file):
                            try:
                                os.unlink(file)
                                logger.trace(f'os.unlink({file})')
                            except FileNotFoundError:
                                logger.error(f'{file} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {file}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {file}: {e}')                           
                        ## I don't know why??
                        if os.path.exists(file):
                            logger.error(f'[FATAL] why {file} still existed !!????')
                            delcmd = f'del {file}'
                            try:
                                os.system(delcmd)
                            except Exception as e:
                                logger.error(f"Unexpected error while deleting failed {file}: {e}")
                else:
                    ## copy .med/.aix to local backup folder
                    backupAnalyzedImageFiles(srcMEDAIX, folderBackup, flist, wsicompleted, 'AIxTHY', 'copy')
                    backupAnalyzedImageFiles(srcMEDAIX, dstMEDAIX, flist, wsicompleted, 'AIxTHY', 'move')
                    ## move wsi files to local backup folder, for now
                    for file in flist:
                        try:
                            #os.rename(file, os.path.join(backupTHY, os.path.basename(file)))
                            shutil.move(file, os.path.join(backupTHY, os.path.basename(file)))
                        except PermissionError:
                            logger.error(f'Permission denied when moving {file}')
                        except OSError as e:
                            logger.error(f'Error occurred while moving file: {e}')
                        ## delete if still exist
                        if os.path.exists(file):
                            try:
                                os.remove(file)
                            except FileNotFoundError:
                                logger.error(f'{file} does not exist')
                            except PermissionError:
                                logger.error(f'permission denied: unable to delete {file}')
                            except OSError as e:
                                logger.error(f'error occurred while deleting {file}: {e}')
                consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
                logger.info(f'processed {howmany} thyroid slides with {consumed_time[:-3]}')
            ## check decart DONE folder
            mlist = glob.glob(os.path.join(srcMEDAIX, 'done'))
            if len(mlist):
                logger.warning('some .med/.aix still exist in DeCart done folder')
                break
            ## goto thyroid loop if thyroid WSI found, or stay in urine loop
            flist = glob.glob(os.path.join(scannerURO, '*'))
            howmany = 0
            for file in flist:
                if os.path.isfile(file) and wsitype in MONITORED_WSI:
                    howmany += 1
            if howmany > 0:     ## urine WSI found
                break
            else:
                ### sleep another 3 minutes
                time.sleep(180)
        if byebye:
            break

