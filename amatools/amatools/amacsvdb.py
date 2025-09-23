## amatools.amacsvdb:
##   (1) update analyzed results into CSV
##   (2) update analyzed results to sqlite3 database
##
import os, glob
import shutil
import csv
import pandas as pd
from collections import Counter
from datetime import datetime, timedelta
from loguru import logger
from tqdm import tqdm
from .amaconfig import getMSinfo

##---------------------------------------------------------
## special case for category name
##---------------------------------------------------------
def getCategoryNamebyID(whichmodel, whichversion, category, noModelArch=None):
    uroTypeName = ['background', 'nuclei', 'suspicious', 'atypical', 'benign',
                   'other', 'tissue', 'degenerated']
    thy2024Name = ['background', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes',
                   'colloid', 'multinucleatedGaint', 'psammomaBodies']
    thy2025Name = ['background', 'follicular', 'oncocytic', 'epithelioid',
                   'lymphocytes', 'histiocytes', 'colloid']
    if whichmodel == 'AIxURO':
        if noModelArch:
            ## special case for decart 2.0.x ad 2.1.x (AIxURO only)
            categoryname = ['benign', 'atypical', 'suspicious', 'nuclei']
            typename = 'unknown' if category > 3 else categoryname[category]
        else:
            typename = uroTypeName[category] 
    elif whichmodel == 'AIxTHY':
        if whichversion[:6] in ['2025.2']:
            typename = thy2025Name[category]
        else:   ## modelversion: 2024.2-0625
            typename = thy2024Name[category]
    else:
        typename = 'unknown'
        logger.error(f'incorrect model:{whichmodel} in getCategoryNamebyID()')
    return typename

##---------------------------------------------------------
## save inference result to CSV file
##---------------------------------------------------------
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
    with open(outcsv, 'w', newline='', encoding='utf-8') as csvobj:
        if whichmodel == 'AIxURO':
            colCELLs = ['wsifname', 'suspicious', 'atypical', 'benign', 'degenerated', \
                        'top24AVGncratio', 'top24AVGcellarea', 'top24AVGnuclarea', \
                        'ScellAVGncratio', 'ScellAVGcellarea', 'ScellAVGnuclarea', \
                        'AcellAVGncratio', 'AcellAVGcellarea', 'AcellAVGnuclarea']
        else:   ## AIxTHY
            if modelversion[:6] in ['2025.2']:
                colCELLs = ['wsifname', 'follicular', 'oncocytic', 'epithelioid', 'lymphocytes', 'histiocytes', 'colloid']
            else:
                colCELLs = ['wsifname', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes', 'colloid']
        fieldcols = colCELLs + colMODEL + colWSI + colENV
        csvwriter = csv.DictWriter(csvobj, fieldnames=fieldcols)
        csvwriter.writeheader()
        #for ii in range(len(infdata)):
        thisOS, thatOS, thisCPU, thisGPU, thisRAM = getMSinfo()
        for mdata in infdata:
            thisrow = {}
            ## colCELLs
            thisrow['wsifname'] = mdata['wsifname']
            if whichmodel == 'AIxURO':
                thisrow['suspicious']       = mdata['cellCount'][2]
                thisrow['atypical']         = mdata['cellCount'][3]
                thisrow['benign']           = mdata['cellCount'][4]
                thisrow['degenerated']      = mdata['cellCount'][7]
                thisrow['top24AVGncratio']  = mdata['topncratio']
                thisrow['top24AVGcellarea'] = mdata['topcelarea']
                thisrow['top24AVGnuclarea'] = mdata['topnucarea']
                thisrow['ScellAVGncratio']  = mdata['avgsncratio']
                thisrow['ScellAVGcellarea'] = mdata['avgscelarea']
                thisrow['ScellAVGnuclarea'] = mdata['avgsnucarea']
                thisrow['AcellAVGncratio']  = mdata['avgancratio']
                thisrow['AcellAVGcellarea'] = mdata['avgacelarea']
                thisrow['AcellAVGnuclarea'] = mdata['avganucarea']
            else:   ## AIxTHY
                if modelversion[:6] in ['2025.2']:
                    thisrow['follicular']  = mdata['cellCount'][1]
                    thisrow['oncocytic']   = mdata['cellCount'][2]
                    thisrow['epithelioid'] = mdata['cellCount'][3]
                    thisrow['lymphocytes'] = mdata['cellCount'][4]
                    thisrow['histiocytes'] = mdata['cellCount'][5]
                    thisrow['colloid']     = mdata['cellCount'][6]
                else:
                    thisrow['colloid']     = mdata['cellCount'][5]
                    thisrow['hurthle']     = mdata['cellCount'][2]
                    thisrow['histiocytes'] = mdata['cellCount'][3]
                    thisrow['lymphocytes'] = mdata['cellCount'][4]
                    thisrow['follicular']  = mdata['cellCount'][1]
            ## colMODEL = ['modelname', 'modelversion', 'similarity']
            thisrow['modelname'] = mdata['modelname']
            thisrow['modelversion'] = mdata['modelversion']
            thisrow['similarity'] = mdata['similarity']
            ## colWSI = ['layer#', 'bestz', 'mpp', 'icc', 'width', 'height', 'medfsize', 'wsifsize']
            thisrow['layer#'] = mdata['sizez']
            thisrow['bestz'] = mdata['bestfocuslayer']
            thisrow['mpp'] = mdata['mpp']
            thisrow['icc'] = mdata['icc']
            thisrow['width'] = mdata['width']
            thisrow['height'] = mdata['height']
            thisrow['medfsize(MB)'] = mdata['medfsize']
            thisrow['wsifsize(MB)'] = mdata['wsifsize']
            ## colENV = ['analysis_date', 'analysis_time', 'envOS', 'envCPU', 'envGPU', 'envRAM', 'scanner']
            thisrow['analysis_date'] = datetime.fromtimestamp(mdata['execution_date']).strftime('%Y-%m-%d %H:%M:%S')
            tsstr = (datetime(1970,1,1)+timedelta(seconds=mdata['convert_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['convert_time'] = tsstr
            tsstr = (datetime(1970,1,1)+timedelta(seconds=mdata['inference_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['inference_time'] = tsstr
            tsstr = (datetime(1970,1,1)+timedelta(seconds=mdata['analysis_timestamp'])).strftime('%H:%M:%S.%f')[:-3]
            thisrow['analysis_time'] = tsstr
            thisrow['envOS'], thisrow['envCPU'], thisrow['envGPU'], thisrow['envRAM'] = thisOS, thisCPU, thisGPU, thisRAM
            thisrow['scanner'] = mdata['scanner']
            csvwriter.writerow(thisrow)
    logger.trace(f'Inference result saved to {os.path.basename(outcsv)} completed.')

##---------------------------------------------------------
## save target cells metadata of a slide to CSV file
##---------------------------------------------------------
def saveTCellsMetadata2CSV(aixfname, allcells, aixmodel, modelver):
    if len(allcells) == 0:
        logger.error(f'empty analysis metadata in {aixfname}')
        return
    # sort by category
    allcells.sort(key=lambda x: x['category'])
    #
    path_aix, file_aix = os.path.split(aixfname)
    shortname = os.path.splitext(file_aix)[0]
    pathmeta = f'{path_aix}\\metadata'
    if os.path.isdir(pathmeta) == False:
        os.mkdir(pathmeta)
    csvfname = f'{pathmeta}\\metadata_{shortname}_{aixmodel}_{modelver}.csv'
 
    with open(csvfname, 'w', newline='') as outcsv:
        if aixmodel == 'AIxURO':
            headcols = ['cellname', 'category', 'probability', 'score', 'ncratio', 'cellarea', 'nucleusarea']
            tagscols = ['hyperchromasia', 'clumpedchromtin', 'irregularmembrane', 'pyknotic', 'lightnesseffect',
                        'dryingartifact', 'degenerated', 'smudged', 'unfocused', 'barenucleus', 'binuclei', 'normal', 
                        'fibrovascularcore', 'nuclearplemorphism' ]
        elif aixmodel == 'AIxTHY':
            headcols = ['cellname', 'category', 'probability', 'score', 'cellarea'] 
            if modelver[:6] in ['2025.2']:
                architectureTraits = ['Papillary', 'NuclearCrowding', 'Microfollicles', 'FlatUniform']
                morphologicFeatures = ['NuclearEnlargement', 'MultinucleatedGiantCell', 'Degenerated', 'Normal']
                papillarythyroid = ['Pseudoinclusions', 'Grooving', 'MarginalMicronucleoli']
                eptheloid = ['ClumpingChromatin', 'ProminentNucleoli']
                medullarythyroid = ['Plasmacytoid', 'SaltAndPepper', 'Binucleation', 'Spindle']
                artifactEffects = ['LightnessEffect', 'DryingArtifact', 'Unfocused']
                tagscols = architectureTraits+morphologicFeatures+papillarythyroid+eptheloid+medullarythyroid+artifactEffects
            else:
                tagscols = ['microfollicles', 'papillae', 'palenuclei', 'grooving', 'pseudoinclusions', 'marginallyplaced', 'plasmacytoid', 'saltandpepper' ]
        fields = headcols+tagscols 
        ww = csv.DictWriter(outcsv, fieldnames=fields)
        ww.writeheader()
        for thiscell in allcells:
            thisrow = {}
            thisrow['cellname']        = thiscell['cellname']
            thisrow['category']        = getCategoryNamebyID(aixmodel, modelver, thiscell['category'])
            thisrow['probability']     = thiscell['probability']
            thisrow['score']           = thiscell['score']
            if aixmodel == 'AIxURO':
                thisrow['ncratio']     = thiscell['ncratio']
                thisrow['cellarea']    = thiscell['cellarea']
                thisrow['nucleusarea'] = thiscell['nucleiarea']
            elif aixmodel == 'AIxTHY':
                thisrow['cellarea']    = thiscell['cellarea']
            for j in range(len(thiscell['traits'])):
                thisrow[tagscols[j]] = thiscell['traits'][j] 
            ww.writerow(thisrow)
    logger.trace(f'metadata of target cells saved to {os.path.basename(csvfname)} completed.')

## ---------- ---------- ---------- ----------
##  save summary of analysis metadata to CSV
## ---------- ---------- ---------- ----------
def saveAnalysisMetadata2CSV(whichModel, modelver, listaix, listavg):
    if len(listaix) == 0 or len(listavg) == 0:
        return
    path_aix, _ = os.path.split(listaix[0])
    csvfname = f'{path_aix}\\summary_of_analysis_metadata.csv'
    with open(csvfname, 'w', newline='') as outcsv:
        if whichModel == 'AIxURO':
            fields = ['aixfname', 'suspicious', 'atypical', 'benign', 'degenerated', 'modelversion', 'similaritydegree', 
                      'suspicious_avg_ncratio', 'suspicious_avg_cellarea', 'suspicious_avg_nucarea', 'atypical_avg_ncratio', 'atypical_avg_cellarea', 'atypical_avg_nucarea',
                      'top24_ncratio', 'top24_cellarea', 'top24_nucarea']
        elif whichModel == 'AIxTHY':
            if modelver[:6] in ['2025.2']:
                fields = ['aixfname', 'modelversion', 'similaritydegree', 'follicular', 'oncocytic', 'epithelioid', 
                          'lymphocytes', 'histiocytes', 'colloid']
            else:
                fields = ['aixfname', 'modelversion', 'similaritydegree', 'follicular', 'hurthle', 'histiocytes',
                          'lymphocytes', 'colloid', 'multinucleated', 'psammoma']
        ww = csv.DictWriter(outcsv, fieldnames=fields)
        ww.writeheader()
        for ii in tqdm(range(len(listavg)), desc='save analysis metadata'):
            thisrow = {}
            _, thisaixname = os.path.split(listaix[ii])
            thisrow['aixfname']          = thisaixname
            thisrow['modelversion']  = f"{whichModel} {listavg[ii]['modelversion']}"
            thisrow['similaritydegree'] = listavg[ii]['similaritydegree']
            if whichModel == 'AIxURO':
                thisrow['suspicious']    = listavg[ii]['cellcount'][2]
                thisrow['atypical']      = listavg[ii]['cellcount'][3]
                thisrow['benign']        = listavg[ii]['cellcount'][4]
                thisrow['degenerated']   = listavg[ii]['cellcount'][7]
                thisrow['suspicious_avg_ncratio']  = listavg[ii]['avgsncratio']
                thisrow['suspicious_avg_cellarea'] = listavg[ii]['avgscelarea']
                thisrow['suspicious_avg_nucarea']  = listavg[ii]['avgsnucarea']
                thisrow['atypical_avg_ncratio']    = listavg[ii]['avgancratio']
                thisrow['atypical_avg_cellarea']   = listavg[ii]['avgacelarea']
                thisrow['atypical_avg_nucarea']    = listavg[ii]['avganucarea']
                thisrow['top24_ncratio']           = listavg[ii]['topncratio']
                thisrow['top24_cellarea']          = listavg[ii]['topcelarea']
                thisrow['top24_nucarea']           = listavg[ii]['topnucarea']
            elif whichModel == 'AIxTHY':
                thisrow['follicular']    = listavg[ii]['cellcount'][1]
                if modelver[:6] in ['2025.2']:
                    thisrow['oncocytic']      = listavg[ii]['cellcount'][2]
                    thisrow['epithelioid']    = listavg[ii]['cellcount'][3]
                    thisrow['lymphocytes']    = listavg[ii]['cellcount'][4]
                    thisrow['histiocytes']    = listavg[ii]['cellcount'][5]
                    thisrow['colloid']        = listavg[ii]['cellcount'][6]
                else:
                    thisrow['hurthle']        = listavg[ii]['cellcount'][2]
                    thisrow['histiocytes']    = listavg[ii]['cellcount'][3]
                    thisrow['lymphocytes']    = listavg[ii]['cellcount'][4]
                    thisrow['colloid']        = listavg[ii]['cellcount'][5]
                    thisrow['multinucleated'] = listavg[ii]['cellcount'][6]
                    thisrow['psammoma']       = listavg[ii]['cellcount'][7]
            ww.writerow(thisrow)
    logger.trace(f'summary of analysis metadata saved to {os.path.basename(csvfname)} completed.')

## ---------- ---------- ---------- ----------
##  save traits summary to CSV
## ---------- ---------- ---------- ----------
def saveTraitsSummary2CSV(whichmodel, modelver, aixlist, taglist):
    if len(aixlist) == 0 or len(taglist) == 0:
        logger.error(f'nothing in {os.path.dirname(aixlist[0])} to save to CSV')
        return
    if whichmodel.lower() not in ['aixuro', 'aixthy']:
        logger.error(f'[saveTraitsSummary2CSV] unknown Model: {whichmodel}')
        return
    path_aix, _ = os.path.split(aixlist[0])
    csvfname = f'{path_aix}\\summary_of_traits.csv'
    with open(csvfname, 'w', newline='') as tagcsv:
        if whichmodel == 'AIxURO':
            fields = ['aixfname', 'S_T1', 'S_T2', 'S_T3', 'S_T1T2', 'S_T1T3', 'S_T2T3', 'S_T1T2T3', 
                      'A_T1', 'A_T2', 'A_T3', 'A_T1T2', 'A_T1T3', 'A_T2T3', 'A_T1T2T3', 
                      'TOP_T1', 'TOP_T2', 'TOP_T3', 'TOP_T1T2', 'TOP_T1T3', 'TOP_T2T3', 'TOP_T1T2T3']
        else:   # AIxTHY
            if modelver[:6] in ['2025.2']:
                fields = ['aixfname', 'Papillary', 'NuclearCrowding', 'Microfollicles', 'FlatUniform', 
                            'NuclearEnlargement', 'MultinucleatedGiantCell', 'Degenerated', 'Normal',
                            'Pseudoinclusions', 'Grooving', 'MarginalMicronucleoli',
                            'ClumpingChromatin', 'ProminentNucleoli', 
                            'Plasmacytoid', 'SaltAndPepper', 'Binucleation', 'Spindle', 
                            'LightnessEffect', 'DryingArtifact', 'Unfocused']
            else:
                fields = ['aixfname', 'microfollicles', 'papillae', 'palenuclei', 'grooving', 'pseudoinclusions', 
                          'marginallyplaced', 'plasmacytoid', 'saltandpepper']
        ww = csv.DictWriter(tagcsv, fieldnames=fields)
        ww.writeheader()
        #for i in range(len(aixlist)):
        for i in tqdm(range(len(aixlist)), desc='saving traits summary'):
            thistag = taglist[i]
            thisrow = {}
            _, thisaixname = os.path.split(aixlist[i])
            thisrow['aixfname'] = thisaixname
            if whichmodel == 'AIxURO':
                thisrow['S_T1']     = thistag[0]
                thisrow['S_T2']     = thistag[1]
                thisrow['S_T3']     = thistag[2]
                thisrow['S_T1T2']   = thistag[3]
                thisrow['S_T1T3']   = thistag[4]
                thisrow['S_T2T3']   = thistag[5]
                thisrow['S_T1T2T3'] = thistag[6]
                thisrow['A_T1']     = thistag[7]
                thisrow['A_T2']     = thistag[8]
                thisrow['A_T3']     = thistag[9]
                thisrow['A_T1T2']   = thistag[10]
                thisrow['A_T1T3']   = thistag[11]
                thisrow['A_T2T3']   = thistag[12]
                thisrow['A_T1T2T3'] = thistag[13]
                thisrow['TOP_T1']   = thistag[14]
                thisrow['TOP_T2']   = thistag[15]
                thisrow['TOP_T3']   = thistag[16]
                thisrow['TOP_T1T2'] = thistag[17]
                thisrow['TOP_T1T3'] = thistag[18]
                thisrow['TOP_T2T3'] = thistag[19]
                thisrow['TOP_T1T2T3'] = thistag[20]
            else:   # AIxTHY
                if modelver[:6] in ['2025.2']:
                    thisrow['Papillary']               = thistag[0]
                    thisrow['NuclearCrowding']         = thistag[1]
                    thisrow['Microfollicles']          = thistag[2]
                    thisrow['FlatUniform']             = thistag[3]
                    thisrow['NuclearEnlargement']      = thistag[4]
                    thisrow['MultinucleatedGiantCell'] = thistag[5]
                    thisrow['Degenerated']             = thistag[6]
                    thisrow['Normal']                  = thistag[7]
                    thisrow['Pseudoinclusions']        = thistag[8]
                    thisrow['Grooving']                = thistag[9]
                    thisrow['MarginalMicronucleoli']   = thistag[10]
                    thisrow['ClumpingChromatin']       = thistag[11]
                    thisrow['ProminentNucleoli']       = thistag[12]
                    thisrow['Plasmacytoid']            = thistag[13]
                    thisrow['SaltAndPepper']           = thistag[14]
                    thisrow['Binucleation']            = thistag[15]
                    thisrow['Spindle']                 = thistag[16]
                    thisrow['LightnessEffect']         = thistag[17]
                    thisrow['DryingArtifact']          = thistag[18]
                    thisrow['Unfocused']               = thistag[19]
                else:
                    thisrow['microfollicles']   = thistag[0]
                    thisrow['papillae']         = thistag[1]
                    thisrow['palenuclei']       = thistag[2]
                    thisrow['grooving']         = thistag[3]
                    thisrow['pseudoinclusions'] = thistag[4] 
                    thisrow['marginallyplaced'] = thistag[5]
                    thisrow['plasmacytoid']     = thistag[6]
                    thisrow['saltandpepper']    = thistag[7]
            ww.writerow(thisrow)
    logger.trace(f'traits summary saved to {os.path.basename(csvfname)} completed.')

## ---------- ---------- ---------- ----------
## 🩻 save model inference metadata to Sqlite3 database
## ---------- ---------- ---------- ----------
def insertAnalyzedMetadata2DB(medata, dbname):
    if os.path.isfile(dbname) == False:
        logger.warning(f'database {dbname} does not exist')
        createNewQCxDB(medata['modeln'].lower(), dbname)
    labelname = medata['label']
    modelname, model_ver = medata['modeln'], medata['modelv']
    medfile, medpath = medata['medfile'], medata['medpath']
    ## check if this slide already existed
    if modelname.lower() == 'aixuro':
        slidetype = 'urine'
    elif modelname.lower() == 'aixthy':
        slidetype = 'thyroid'
    mdata = queryAnalyzedMetadataFromDB(dbname, labelname, slidetype)
    if len(mdata):
        for k in range(len(mdata)):
            if mdata[k]['model'] == f'{modelname} {model_ver}':
                logger.error(f'slide {labelname} already existed in database {dbname}')
                return
        logger.warning(f"slide {labelname} already existed in database {dbname}, but analyzed by {modelname} {model_ver} this time")
    ##
    if medata['modeln'].lower() == 'aixuro':
        sql_head = "INSERT INTO QCxURO \
            (slidelabel, zlayer, zfocus, similarity, suspicious, atypical, degenerated, benign, \
            s_avg_ncratio, s_avg_nuclarea, a_avg_ncratio, a_avg_nuclarea, \
            t_avg_ncratio, t_avg_nuclarea, modelProduct, modelVersion, \
            medfname, medfpath) VALUES "
        sql_tail = f"('{labelname}', {medata['zlayer']}, {medata['zfocus']}, {medata['similarity']}, \
            {medata['suspicious']}, {medata['atypical']}, {medata['degenerated']}, {medata['benign']}, \
            {medata['s_avg_ncratio']}, {medata['s_avg_nucarea']}, \
            {medata['a_avg_ncratio']}, {medata['a_avg_nucarea']}, \
            {medata['t_avg_ncratio']}, {medata['t_avg_nucarea']}, \
            '{modelname}', '{model_ver}', '{medfile}', '{medpath}')"
    elif medata['modeln'].lower() == 'aixthy':
        sql_head = "INSERT INTO QCxTHY \
            (slidelabel, zlayer, zfocus, similarity, \
            category1, category2, category3, category4, category5, category6, \
            trait1, trait2, trait3, trait4, trait5, trait6, trait7, trait8, trait9, trait10, \
            trait11, trait12, trait13, trait14, trait15, trait16, trait17, trait18, trait19, trait20, \
            modelProduct, modelVersion, medfname, medfpath) VALUES "
        sql_tail = f"('{labelname}', {medata['zlayer']}, {medata['zfocus']}, {medata['similarity']}, \
            {medata['category'][1]}, {medata['category'][2]}, {medata['category'][3]}, \
            {medata['category'][4]}, {medata['category'][5]}, {medata['category'][6]}, \
            {medata['traits'][0]}, {medata['traits'][1]}, {medata['traits'][2]}, {medata['traits'][3]}, \
            {medata['traits'][4]}, {medata['traits'][5]}, {medata['traits'][6]}, {medata['traits'][7]}, \
            {medata['traits'][8]}, {medata['traits'][9]}, {medata['traits'][10]}, {medata['traits'][11]}, \
            {medata['traits'][12]}, {medata['traits'][13]}, {medata['traits'][14]}, {medata['traits'][15]}, \
            {medata['traits'][16]}, {medata['traits'][17]}, {medata['traits'][18]}, {medata['traits'][19]}, \
            '{modelname}', '{model_ver}', '{medfile}', '{medpath}')"

    sql_str = sql_head + sql_tail
    try:
        with sqlite3.connect(dbname) as dbconn:
            cur = dbconn.cursor()
            cur.execute(sql_str)
            dbconn.commit()
        logger.info(f'{os.path.basename(dbname)} updated!')
    except sqlite3.OperationalError as e:
        logger.error(f'save inference metadata to database {dbname} failed, {e}')
    except sqlite3.Error as e:
        logger.error(f'general SQlite error: {e}')
    finally:
        if dbconn:
            dbconn.close()

## ---------- ---------- ---------- ----------
## 🗄️ update analyzed metadata to Sqlite3 database
## ---------- ---------- ---------- ----------
def updateAnalyzedMetadata2DB(aixmeta, thismodel, qcxDBpath, dbname):
    if len(aixmeta) == 0:
        logger.error('no analyzed metadata!')
        return
    modelProduct = aixmeta[0]['modelname']
    modelVersion = aixmeta[0]['modelversion']

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
