import csv
import time
from datetime import datetime, timedelta
import wmi, GPUtil
from loguru import logger

## ---------- ---------- ---------- ----------
## HW components 
## ---------- ---------- ---------- ----------
'''
ENV_OS = 'Windows11 Pro 24H2'
ENVCPU = 'AMD Ryzen 7955WX'
ENVGPU = 'RTX A6000 Ada'
ENVRAM = '192GB'
'''
def getMSinfo():
    thispc = wmi.WMI()
    ## OS
    winos = thispc.Win32_OperatingSystem()
    hw_os = winos[0].Caption if len(winos) > 0 else ''
    ## CPU
    cpu = thispc.Win32_Processor()
    hw_cpu = cpu[0].Name if len(cpu) > 0 else ''
    ## RAM
    ram = thispc.Win32_PhysicalMemory()
    ram_mb = 0
    for i in range(len(ram)):
        ram_mb += int(ram[i].Capacity)/1048576
    hw_ram = f'{round(ram_mb/1024)}GB'
    ## GPU 
    gpu = GPUtil.getGPUs()
    hw_gpu = gpu[0].name if len(gpu) > 0 else ''
    
    return hw_os, hw_cpu, hw_gpu, hw_ram

## ---------- ---------- ---------- ----------
## utilities for analyzing .aix metadata 
## ---------- ---------- ---------- ----------
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

## count the number of thyroid traits
def countNumberOfTHYtraits(tclist, maxTraits, threshold=0.4):
    traitCount = [0 for i in range(maxTraits)]
    howmany = len(tclist)
    if howmany == 0:
        logger.error('empty cell list in countNumberOfTHYtraits()')
        return traitCount
    for i in range(howmany):
        celltraits = tclist[i]['traits']
        for j in range(len(tclist[i]['traits'])):
            if celltraits[j] >= threshold:
                traitCount[j] += 1
    return traitCount

## ---------- ---------- ---------- ----------
## save model inference metadata to CSV
## ---------- ---------- ---------- ----------
def saveInferenceResult2CSV(infdata, infpath):
    if os.path.exists(infpath) == False:
        os.mkdir(infpath)
    infdata.sort(key=lambda x: x['wsifname'], reverse=False)
    tsnow = datetime.now().strftime('%Y%m%d_%H%M%S')
    whichmodel, modelversion = infdata[0]['modelname'], infdata[0]['modelversion']
    outcsv = os.path.join(infpath, f'{whichmodel}_{modelversion}_inference_{tsnow}.csv')
    logger.trace(f'Saving inference result to {os.path.basename(outcsv)}...')
    ##
    colMODEL = ['modelname', 'modelversion', 'similarity']
    colWSI = ['layer#', 'bestz', 'mpp', 'icc', 'width', 'height', 'medfsize(MB)', 'wsifsize(MB)']
    colENV = ['analysis_date', 'convert_time', 'inference_time', 'analysis_time', 'envOS', 'envCPU', 'envGPU', 'envRAM', 'scanner']
    with open(outcsv, 'w', newline='') as csvobj:
        if whichmodel == 'AIxURO':
            colCELLs = ['wsifname', 'suspicious', 'atypical', 'benign', 'degenerated', 'top24AVGncratio', 'top24AVGnucarea', 'scellAVGncratio', 'scellAVGnucarea', 'acellAVGncratio', 'acellAVGnucarea']
        else:   ## AIxTHY
            if modelversion[:6] in ['2025.2']:
                colCELLs = ['wsifname', 'follicular', 'oncocytic', 'epithelioid', 'lymphocytes', 'histiocytes', 'colloid']
            else:
                colCELLs = ['wsifname', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes', 'colloid']
        fieldcols = colCELLs + colMODEL + colWSI + colENV
        csvwriter = csv.DictWriter(csvobj, fieldnames=fieldcols)
        csvwriter.writeheader()
        for ii in range(len(infdata)):
            thisrow = {}
            ## colCELLs
            thisrow['wsifname'] = infdata[ii]['wsifname']
            if whichmodel == 'AIxURO':
                thisrow['suspicious']      = infdata[ii]['cellCount'][2]
                thisrow['atypical']        = infdata[ii]['cellCount'][3]
                thisrow['benign']          = infdata[ii]['cellCount'][4]
                thisrow['degenerated']     = infdata[ii]['cellCount'][7]
                thisrow['top24AVGncratio'] = infdata[ii]['avgtop24ncratio']
                thisrow['top24AVGnucarea'] = infdata[ii]['avgtop24nucarea']
                thisrow['scellAVGncratio'] = infdata[ii]['savgncratio']
                thisrow['scellAVGnucarea'] = infdata[ii]['savgnucarea']
                thisrow['acellAVGncratio'] = infdata[ii]['aavgncratio']
                thisrow['acellAVGnucarea'] = infdata[ii]['aavgnucarea']
            else:   ## AIxTHY
                if modelversion[:6] in ['2025.2']:
                    thisrow['follicular']  = infdata[ii]['cellCount'][1]
                    thisrow['oncocytic']   = infdata[ii]['cellCount'][2]
                    thisrow['epithelioid'] = infdata[ii]['cellCount'][3]
                    thisrow['lymphocytes'] = infdata[ii]['cellCount'][4]
                    thisrow['histiocytes'] = infdata[ii]['cellCount'][5]
                    thisrow['colloid']     = infdata[ii]['cellCount'][6]
                else:
                    thisrow['colloid']     = infdata[ii]['cellCount'][5]
                    thisrow['hurthle']     = infdata[ii]['cellCount'][2]
                    thisrow['histiocytes'] = infdata[ii]['cellCount'][3]
                    thisrow['lymphocytes'] = infdata[ii]['cellCount'][4]
                    thisrow['follicular']  = infdata[ii]['cellCount'][1]
            ## colMODEL = ['modelname', 'modelversion', 'similarity']
            thisrow['modelname'] = infdata[ii]['modelname']
            thisrow['modelversion'] = infdata[ii]['modelversion']
            thisrow['similarity'] = infdata[ii]['similarity']
            ## colWSI = ['layer#', 'bestz', 'mpp', 'icc', 'width', 'height', 'medfsize', 'wsifsize']
            thisrow['layer#'] = infdata[ii]['sizez']
            thisrow['bestz'] = infdata[ii]['bestfocuslayer']
            thisrow['mpp'] = infdata[ii]['mpp']
            thisrow['icc'] = infdata[ii]['icc']
            thisrow['width'] = infdata[ii]['width']
            thisrow['height'] = infdata[ii]['height']
            thisrow['medfsize(MB)'] = infdata[ii]['medfsize']
            thisrow['wsifsize(MB)'] = infdata[ii]['wsifsize']
            ## colENV = ['analysis_date', 'analysis_time', 'envOS', 'envCPU', 'envGPU', 'envRAM', 'scanner']
            thisrow['analysis_date'] = datetime.fromtimestamp(infdata[ii]['execution_date']).strftime('%Y-%m-%d %H:%M:%S')
            tsstr = (datetime(1970,1,1)+timedelta(seconds=infdata[ii]['convert_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['convert_time'] = tsstr
            tsstr = (datetime(1970,1,1)+timedelta(seconds=infdata[ii]['inference_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['inference_time'] = tsstr
            tsstr = (datetime(1970,1,1)+timedelta(seconds=infdata[ii]['analysis_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['analysis_time'] = tsstr
            thisrow['envOS'], thisrow['envCPU'], thisrow['envGPU'], thisrow['envRAM'] = getMSinfo()
            thisrow['scanner'] = infdata[ii]['scanner']
            csvwriter.writerow(thisrow)
    logger.trace(f'Inference result saved to {os.path.basename(outcsv)} completed.')

## ---------- ---------- ---------- ----------
## save model inference metadata to Sqlite3 database
## ---------- ---------- ---------- ----------
def saveAnalyzedMetadata2DB4QC(aixmeta, path_medaix, qcxDBpath, dbname):
    if len(aixmeta) == 0:
        logger.error('no analyzed metadata!')
        return
    modelProduct = aixmeta[0]['modelname']
    modelVersion = aixmeta[0]['modelversion']
    '''
    #qcxDBpath = os.environ.get['QCxDBpath']
    if modelProduct.lower() == 'aixuro':
        thisdb = os.path.join(qcxDBpath, uroDBname)
        backdb = os.path.join(os.getenv('localappdata'), 'ama_qc', uroDBname)
    elif modelProduct.lower() == 'aixthy':
        thisdb = os.path.join(qcxDBpath, thyDBname)
        backdb = os.path.join(os.getenv('localappdata'), 'ama_qc', thyDBname)
    else:
        logger.error(f'no database for model {modelProduct}')
        return
   '''
    thisdb = os.path.join(qcxDBpath, dbname)
    backdb = os.path.join(os.getenv('localappdata'), 'ama_qc', dbname)
    ## insert analyzed metadata into database for QC
    for ii in range(len(aixmeta)):
        thisdata = {}
        thisdata['label'] = os.path.splitext(aixmeta[ii]['wsifname'])[0]
        thisdata['zlayer'] = aixmeta[ii]['sizez']
        thisdata['zfocus'] = aixmeta[ii]['bestfocuslayer']
        thisdata['similarity'] = aixmeta[ii]['similarity']
        thisdata['modeln'] = modelProduct
        thisdata['modelv'] = modelVersion
        thisdata['medfile'] = f"{thisdata['label']}.med"
        thisdata['medpath'] = path_medaix
        if modelProduct.lower() == 'aixuro':
            thisdata['suspicious']  = aixmeta[ii]['cellCount'][2]
            thisdata['atypical']    = aixmeta[ii]['cellCount'][3]
            thisdata['degenerated'] = aixmeta[ii]['cellCount'][7]
            thisdata['benign']      = aixmeta[ii]['cellCount'][4]
            thisdata['t_avg_ncratio'] = aixmeta[ii]['avgtop24ncratio']
            thisdata['t_avg_nucarea'] = aixmeta[ii]['avgtop24nucarea']
            thisdata['s_avg_ncratio'] = aixmeta[ii]['savgncratio']
            thisdata['s_avg_nucarea'] = aixmeta[ii]['savgnucarea']
            thisdata['a_avg_ncratio'] = aixmeta[ii]['aavgncratio']
            thisdata['a_avg_nucarea'] = aixmeta[ii]['aavgnucarea']
        else:
            thisdata['category'] = aixmeta[ii]['cellCount']
            thisdata['traits']   = aixmeta[ii]['traits']

        insertInferenceMetadata2DB(thisdata, thisdb)
    ## backup updated database 
    shutil.copy(thisdb, backdb)

## --------  --------  --------
