import os
import yaml
from datetime import datetime, timedelta
from loguru import logger

##---------------------------------------------------------
## change model product in config.yaml
##---------------------------------------------------------
def updateDeCartConfig(thismodel, decartYaml):
    updated = False
    #decartYaml = r'c:\ProgramData\DeCart\config.yaml'
    if os.path.isfile(decartYaml) == False:
        logger.error(f'config.yaml file {decartYaml} does not exist!')
        return updated
    with open(decartYaml, 'r') as curyaml:
        conf = yaml.load(curyaml, Loader=yaml.FullLoader)
    if conf['preset'].lower() != thismodel.lower():
        conf['preset'] = thismodel.lower()
        try:
            with open(decartYaml, 'w') as newyaml:
                yaml.dump(conf, newyaml)
            updated = True
        except PermissionError:
            logger.error(f"do not have permission to write to {decartYaml}.")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
    return updated

## parse image conversion timestamp and inference timestamp from subprocess.run()
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

## replace ' ' with '_' in the filename
def replaceSpace2underscore(fname):
    thisfile = fname
    if ' ' in fname:
        mpath, mfile = os.path.split(fname)
        tmpfile = mfile.replace(' ', '_')
        thisfile = os.path.join(mpath, tmpfile)
        os.rename(fname, thisfile)
    return thisfile

##---------------------------------------------------------
## print out data on the stdout
##---------------------------------------------------------
def dumpMetadata2stdout(infdata):
    if len(infdata) == 0:
        logger.warning('no metadatafor analyzing!')
        return
    whichmodel, modelversion = infdata[0]['modelname'], infdata[0]['modelversion']
    logger.trace('-'*240)
    toprow = f"{'wsi filename':<32}"
    if whichmodel == 'AIxURO':
        toprow += f"{'suspicious':<12}{'atypical':<12}{'benign':<12}{'degenerated':<12}"
    else:   ## AIxTHY
        if modelversion[:6] in ['2025.2']:
            toprow += f"{'follicular':<12}{'oncocytic':<12}{'epithelioid':<12}{'lymphocytes':<12}{'histiocytes':<12}{'colloid':<12}"
        else:
            toprow += f"{'follicular':<12}{'hurthle':<12}{'lymphocytes':<12}{'histiocytes':<12}{'colloid':<12}"
    toprow += f"{'width':^8}{'height':^8}{'model name&ver':^20}{'similarity':^12}{'convert time':^14}{'inference time':^14}{'analysis time':^14}"
    logger.trace(toprow)
    logger.trace('-'*240)
    for d in infdata:
        #d = infdata[ii]
        thisrow = f"{d['wsifname'][:30]:<32}"
        if whichmodel == 'AIxURO':
            thisrow += f"{d['cellCount'][2]:<12,}{d['cellCount'][3]:<12,}{d['cellCount'][4]:<12,}{d['cellCount'][7]:<12,}"
        else:   ## AIxTHY
            if modelversion[:6] in ['2025.2']:
                thisrow += f"{d['cellCount'][1]:<12,}{d['cellCount'][2]:<12,}{d['cellCount'][3]:<12,}{d['cellCount'][4]:<12,}{d['cellCount'][5]:<12,}{d['cellCount'][6]:<12,}"
            else:
                thisrow += f"{d['cellCount'][1]:<12,}{d['cellCount'][2]:<12,}{d['cellCount'][4]:<12,}{d['cellCount'][3]:<12,}{d['cellCount'][5]:<12,}"
        thismodel = d['modelname']+' '+d['modelversion']
        tsconvert = (datetime(1970,1,1)+timedelta(seconds=d['convert_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
        tsinference = (datetime(1970,1,1)+timedelta(seconds=d['inference_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
        tsanalysis = (datetime(1970,1,1)+timedelta(seconds=d['analysis_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
        thisrow += f"{d['width']:>8,}{d['height']:>8,}{thismodel:^20}{d['similarity']:^10.4f}{tsconvert:>14}{tsinference:>14}{tsanalysis:>14}"
        logger.trace(thisrow)
    logger.trace('-'*240)
