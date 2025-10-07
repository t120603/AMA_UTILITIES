## ----- utilit to read .aix
import os, glob
import gzip
import json
import numpy as np
import shapely.geometry
from loguru import logger
from tqdm import tqdm
from .queryMED import getMetadataFromMED
from .amacsvdb import saveTCellsMetadata2CSV, saveTraitsSummary2CSV
from .amacsvdb import saveAnalysisMetadata2CSV

##---------------------------------------------------------
## secret data, and criteria of 'score'
##---------------------------------------------------------
## secret data: number of traits
NUM_TRAIT_URO = 14
NUM_TRAIT_THY = 20
NUM_TOP = 24
ONLY_SUSPICIOUS = True
## criteria of 'score'
CRITERA_SCORE = 0.4
CRITERA_TRAIT = 0.4

## -------------------------------------------------------------- 
## calculate cell area
## -------------------------------------------------------------- 
def calculateCellArea(segments, mpp=None):
    if mpp == None:
        mpp = 0.25      ## not actual mpp, only for reference
    convex = []
    for i, xy in enumerate(segments):
        x, y = xy
        convex.append((x*mpp, y*mpp))
    thiscell = shapely.geometry.Polygon(convex)
    return thiscell.area

## -------------------------------------------------------------- 
## retrieve 'model' and 'graph' from aix metadata
## -------------------------------------------------------------- 
def getMetadataFromAIX(aixfile, save2json=False):
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

## -------------------------------------------------------------- 
# parse details of aix metadata
## -------------------------------------------------------------- 
def getCellsInfoFromAIX(aixfile, mpp=None):
    aixinfo, aixcell = getMetadataFromAIX(aixfile)
    whichmodel = aixinfo.get('Model', 'unknown')
    if whichmodel == 'AIxURO':
        ## return getAixuroCellInfo(aixfile)
        typeName = ['background', 'nuclei', 'suspicious', 'atypical', 'benign',
                       'other', 'tissue', 'degenerated']
        cellCount = [0 for i in range(len(typeName))]
        nulltags = [0.0 for _ in range(NUM_TRAIT_URO)]
        ## get all the cell information
        allCells = []
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
                thiscell['category'] = category
                thiscell['ncratio']  = cdata.get('ncRatio', 0.0)
                if category != 1:  ## cell
                    thiscell['segments_cell'] = cbody[kk][1]['segments']
                    thiscell['segments_nuclei'] = cbody[kk+1][1]['segments']
                else:   ## nuclei
                    thiscell['segments_cell'] = []
                    thiscell['segments_nuclei'] = cbody[kk][1]['segments']
                if mpp is not None:
                    thiscell['cellarea'] = calculateCellArea(thiscell['segments_cell'], mpp)
                    thiscell['nucleicalc'] = calculateCellArea(thiscell['segments_nuclei'], mpp)
                else:
                    thiscell['cellarea'] = 0.0
                thiscell['nucleiarea'] = thiscell['cellarea']*thiscell['ncratio']

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
        nulltags = [0.0 for _ in range(NUM_TRAIT_THY)]
        ## get all the cell information
        allCells = []
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
                if mpp is not None:
                    thiscell['cellarea'] = calculateCellArea(thiscell['segments'], mpp)

                thiscell['probability'] = cdata.get('prob', 0.0)
                thiscell['score'] = cdata.get('score', 0.0)
                thiscell['traits'] = cdata.get('tags', nulltags)
                allCells.append(thiscell)
        cellsList = sorted(allCells, key=lambda x: (-x['category'], x['score']), reverse=True)
        return aixinfo, objCount, cellsList
    else:
        logger.error(f'{os.path.basename(aixfile)} is not analyzed by AIxURO or AIxTHY model.')
        return aixinfo, [], []

## -------------------------------------------------------------- 
##  utilities for parsing .aix metadata 
## -------------------------------------------------------------- 
## average of NC ratio and Nuclei area of suspicious/atypical cells
def getUROaverageOfSAcells(tclist):
    averageURO = {
        'suspicious': {'cell_area': 0.0, 'nuclei_area': 0.0, 'nc_ratio': 0.0},
        'atypical': {'cell_area': 0.0, 'nuclei_area': 0.0, 'nc_ratio': 0.0},
    }
    sumSncratio, sumAncratio = 0.0, 0.0
    sumScelarea, sumAcelarea = 0, 0
    sumSnucarea, sumAnucarea = 0, 0
    countS, countA = 0, 0
    for i in range(len(tclist)):
        if tclist[i]['category'] == 2:
            celltype = 'suspicious'
        elif tclist[i]['category'] == 3:
            celltype = 'atypical'
        else:
            continue
        cellArea = tclist[i]['cellarea']
        nucleiArea = tclist[i]['nucleiarea']
        if celltype == 'suspicious':
            sumSncratio += tclist[i]['ncratio']
            sumScelarea += cellArea
            sumSnucarea += nucleiArea
            countS += 1
        else:
            sumAncratio += tclist[i]['ncratio']
            sumAcelarea += cellArea
            sumAnucarea += nucleiArea
            countA += 1
    if countS > 0:
        averageURO['suspicious']['nc_ratio'] = sumSncratio / countS
        averageURO['suspicious']['cell_area'] = sumScelarea / countS
        averageURO['suspicious']['nuclei_area'] = sumSnucarea / countS
    if countA > 0:
        averageURO['atypical']['nc_ratio'] = sumAncratio / countA
        averageURO['atypical']['cell_area'] = sumAcelarea / countA
        averageURO['atypical']['nuclei_area'] = sumAnucarea / countA

    return averageURO

## ---------- ---------- ---------- ----------
## average/error of NC ratio and Nuclei area of suspicious/atypical cells
## simulate the nuclei area based on cell area and NC ratio
## ---------- ---------- ---------- ----------
def calculateUROaverageOfSAcells(tclist):
    averageURO = {
        'suspicious': {'cell_area': 0.0, 'cell_error': 0.0, 'nuclei_area': 0.0, 'nuclei_error': 0.0, 'nc_ratio': 0.0, 'ratio_error': 0.0},
        'atypical': {'cell_area': 0.0, 'cell_error': 0.0, 'nuclei_area': 0.0, 'nuclei_error': 0.0, 'nc_ratio': 0.0, 'ratio_error': 0.0},
    }
    filteredcells = filter(lambda x: (x['category'] == 2), tclist)
    suspicious_cells = list(filteredcells)
    filteredcells = filter(lambda x: (x['category'] == 3), tclist)
    atypical_cells = list(filteredcells)
    cellarea_suspicious, nucleiarea_suspicious, ncratio_suspicious = [], [], []
    cellarea_atypical, nucleiarea_atypical, ncratio_atypical = [], [], []
    if len(suspicious_cells) > 0:
        for i in range(len(suspicious_cells)):
            cellarea_suspicious.append(round(suspicious_cells[i]['cellarea'], 2))
            nucleiarea_suspicious.append(round(suspicious_cells[i]['nucleiarea'], 0))
            #nucleiarea_suspicious.append(round(suspicious_cells[i]['nucleicalc'], 0))
            ncratio_suspicious.append(round(suspicious_cells[i]['ncratio'], 2))
        averageURO['suspicious']['cell_area'] = np.mean(cellarea_suspicious)
        averageURO['suspicious']['cell_error'] = np.std(cellarea_suspicious)
        averageURO['suspicious']['nuclei_area'] = np.mean(nucleiarea_suspicious)
        averageURO['suspicious']['nuclei_error'] = np.std(nucleiarea_suspicious)
        averageURO['suspicious']['nc_ratio'] = np.mean(ncratio_suspicious)
        averageURO['suspicious']['ratio_error'] = np.std(ncratio_suspicious)
    if len(atypical_cells) > 0:
        for i in range(len(atypical_cells)):
            cellarea_atypical.append(round(atypical_cells[i]['cellarea'], 2))
            nucleiarea_atypical.append(round(atypical_cells[i]['nucleiarea'], 0))
            #nucleiarea_atypical.append(round(atypical_cells[i]['nucleicalc'], 0))
            ncratio_atypical.append(round(atypical_cells[i]['ncratio'], 2))
        averageURO['atypical']['cell_area'] = np.mean(cellarea_atypical)
        averageURO['atypical']['cell_error'] = np.std(cellarea_atypical)
        averageURO['atypical']['nuclei_area'] = np.mean(nucleiarea_atypical)
        averageURO['atypical']['nuclei_error'] = np.std(nucleiarea_atypical)
        averageURO['atypical']['nc_ratio'] = np.mean(ncratio_atypical)
        averageURO['atypical']['ratio_error'] = np.std(ncratio_atypical)
    ##
    #logger.debug(f'Atypical Cell Area: {cellarea_atypical}')
    #logger.debug(f'Atypical N/C Ratio: {ncratio_atypical}')
    #logger.debug(f'Atypical Nuclei Area: {nucleiarea_atypical}')
    return averageURO

## count/analyze the cell information in AIxURO model
def getUROaverageOfTopCells(tclist, topNum, suspiciousOnly):
    averageTOP = {
        'cell_area': 0.0, 'nuclei_area': 0.0, 'nc_ratio': 0.0,
    }
    acells = [] ## list of atypical cells
    scells = [] ## list of suspicious cells
    topCells = [] ## list of TOP number of cells to return
    for i in range(len(tclist)):
        if tclist[i]['category'] == 2 or tclist[i]['category'] == 3:
            thiscell = (tclist[i]['cellname'],
                        tclist[i]['score'],
                        tclist[i]['probability'],
                        tclist[i]['ncratio'],
                        tclist[i]['cellarea'],
                        tclist[i]['nucleiarea'],
                        #tclist[i]['cellarea']*tclist[i]['ncratio'])
                        tclist[i]['traits'])
            if tclist[i]['category'] == 2:
                scells.append(thiscell)
            else:
                acells.append(thiscell)
    ## sort cell list
    scells.sort(key=lambda x: x[1], reverse=True)
    acells.sort(key=lambda x: x[1], reverse=True)
    ## TOP number of cells
    cellCount = 0
    sumNCratio, sumCelarea, sumNucarea = 0.0, 0.0, 0.0
    ## 
    for i in range(len(scells)):
        sumNCratio += scells[i][3]
        sumCelarea += scells[i][4]
        sumNucarea += scells[i][5]
        cellCount += 1
        topCells.append(scells[i])
        if cellCount >= topNum:
            break
    if cellCount < topNum and suspiciousOnly == False:
        for i in range(len(acells)):
            sumNCratio += acells[i][3]
            sumCelarea += acells[i][4]
            sumNucarea += acells[i][5]
            cellCount += 1
            topCells.append(acells[i])
            if cellCount >= topNum:
                break
    if cellCount > 0:
        averageTOP['nc_ratio'] = sumNCratio / cellCount
        averageTOP['cell_area'] = sumCelarea / cellCount
        averageTOP['nuclei_area'] = sumNucarea / cellCount

    return topCells, averageTOP

## count traits
def countNumberOfUROtraits(tclist, threshold):
    ''' 
    count the number of each trait in the cell list
    [0, 1, 2]   'hyperchromasia', 'clumpedchromtin', 'irregularmembrane', of suspicious cells
    [3]         'hyperchromasia' & 'clumpedchromtin' of suspicious cells
    [4]         'hyperchromasia' & 'irregularmembrane' of suspicious cells
    [5]         'clumpedchromtin' & 'irregularmembrane' of suspicious cells
    [6]         'hyperchromasia' & 'clumpedchromtin' & 'irregularmembrane' of suspicious celles
    [7 ~ 13]    same as above, but only for atypical cells
    [14 ~ 21]   same as above, but only for TOP number of cells
    '''
    traitCount = [0 for i in range(21)]
    howmany = len(tclist)
    if howmany == 0:
        logger.error('empty cell list in countNumberOfUROtraits()')
        return traitCount
    slist = []
    for i in range(len(tclist)):
        category = tclist[i]['category']
        if category != 2 and category != 3:
            continue
        ioffset = 7 if category == 3 else 0
        celltraits = tclist[i]['traits']
        trait1 = True if celltraits[0] >= threshold else False
        trait2 = True if celltraits[1] >= threshold else False
        trait3 = True if celltraits[2] >= threshold else False
        if trait1:
            traitCount[0+ioffset] += 1
            if trait2:
                if trait3:
                    traitCount[6+ioffset] += 1
                else:
                    traitCount[3+ioffset] += 1
            else:
                if trait3:
                    traitCount[4+ioffset] += 1
        if trait2:
            traitCount[1+ioffset] += 1
            if trait3 and trait1 == False:
                traitCount[5+ioffset] += 1
        if trait3:
            traitCount[2+ioffset] += 1
        if category == 2:   ## suspicious cell
            celltraits = (tclist[i]['score'], tclist[i]['traits'][0], 
                          tclist[i]['traits'][1], tclist[i]['traits'][2])
            slist.append(celltraits)
    ## TOP24, only suspicious cells
    slist.sort(key=lambda x: x[0], reverse=True)
    top24 = 24 if len(slist) > 24 else len(slist)
    for i in range(top24):
        if slist[i][1] >= threshold:
            traitCount[14] += 1
    return traitCount

def countNumberOfTHYtraits(tclist, maxTraits, threshold):
    '''
    model 2024.2-0625
    cccccc
    model 2025.2-0526, 2025.2-0626
    Architecture Traits:
        'Papillary configuration', 'Nuclear crowding and overlapping', 'Microfollices', 'Falt/Uniform'
    Morphlogic features:
        'Nuclear enlargement', 'Multinucleated gaint cell', 'Degenrated', 'Normal'
    Papillary thyroid carcinoma traits:
        'Pseudoinclusions', 'Grooving', Marginal micronucleoli'
    Epithelioid carcinoma (metastasis) traits:
        'Clumping chromatin', 'Prominent nucleoli', 
    Medullary thyroid carcinoma traits:
        'Plasmacytoid', 'Salt and Papper chromatin', 'Binucleation', 'spindlle'
    Artifact effects:
        'LightnessEffect', 'DryingArtifact', 'Unfocused'
    '''
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

## -------------------------------------------------------------- 
##  get CELL AREA data of suspicious/atypical cells for chart
## -------------------------------------------------------------- 
def get_URO_CellAreaData(sclist, aclist):
    scCellArea = []
    acCellArea = []
    for i in range(len(sclist)):
        scCellArea.append(round(sclist[i]['cellarea'], 0))
    for i in range(len(aclist)):
        acCellArea.append(round(aclist[i]['cellarea'], 0))
    sc_elements, sc_counts = np.unique(scCellArea, return_counts=True)
    ac_elements, ac_counts = np.unique(acCellArea, return_counts=True)
    return sc_elements, sc_counts, ac_elements, ac_counts

## -------------------------------------------------------------- 
##  get NUCLEUS AREA data of suspicious/atypical cells for chart
## -------------------------------------------------------------- 
def get_URO_NucleusAreaData(sclist, aclist):
    scNucleusArea = []
    acNucleusArea = []
    for i in range(len(sclist)):
        #scNucleusArea.append(round(sclist[i]['nucleicalc'], 0))
        scNucleusArea.append(round(sclist[i]['nucleiarea'], 0))
    for i in range(len(aclist)):
        #acNucleusArea.append(round(aclist[i]['nucleicalc'], 0))
        acNucleusArea.append(round(aclist[i]['nucleiarea'], 0))
    sc_elements, sc_counts = np.unique(scNucleusArea, return_counts=True)
    ac_elements, ac_counts = np.unique(acNucleusArea, return_counts=True)
    return sc_elements, sc_counts, ac_elements, ac_counts

## -------------------------------------------------------------- 
##  get N/C RATIO data of suspicious/atypical cells for chart
## -------------------------------------------------------------- 
def get_URO_NCRatioData(sclist, aclist):
    scNCRatio = []
    acNCRatio = []
    for i in range(len(sclist)):
        scNCRatio.append(round(sclist[i]['ncratio'], 2))
    for i in range(len(aclist)):
        acNCRatio.append(round(aclist[i]['ncratio'], 2))
    sc_elements, sc_counts = np.unique(scNCRatio, return_counts=True)
    ac_elements, ac_counts = np.unique(acNCRatio, return_counts=True)
    return sc_elements, sc_counts, ac_elements, ac_counts

## -------------------------------------------------------------- 
##  query category name by category id for AIxURO and AIxTHY models
## -------------------------------------------------------------- 
## special case for decart 2.0.x ad 2.1.x (AIxURO only)
def specialCase(category):
    categoryname = ['benign', 'atypical', 'suspicious', 'nuclei']
    typename = 'unknown' if category > 3 else categoryname[category]
    return typename

def getCategoryName(whichmodel, whichversion, category, noModelArch=None):
    uroTypeName = ['background', 'nuclei', 'suspicious', 'atypical', 'benign',
                   'other', 'tissue', 'degenerated']
    thy2024Name = ['background', 'follicular', 'hurthle', 'histiocytes', 'lymphocytes',
                   'colloid', 'multinucleatedGaint', 'psammomaBodies']
    thy2025Name = ['background', 'follicular', 'oncocytic', 'epithelioid',
                   'lymphocytes', 'histiocytes', 'colloid']
    if whichmodel == 'AIxURO':
        typename = uroTypeName[category] if not noModelArch else specialCase(category)
    elif whichmodel == 'AIxTHY':
        if whichversion[:6] in ['2025.2']:
            typename = thy2025Name[category]
        else:   ## modelversion: 2024.2-0625
            typename = thy2024Name[category]
    else:
        typename = 'unknown'
        logger.error(f'incorrect model:{whichmodel} in getCategoryName()')
    return typename

## -------------------------------------------------------------- 
##  cli.py option='analysis'
##  utilities for analyzing group of .aix files 
## -------------------------------------------------------------- 
def retrieveAnalysisMetadata(workpath, thismpp=None):
    if not thismpp:
        medlist = glob.glob(os.path.join(workpath, '*.med'))
        if len(medlist) > 0:
            medjson = getMetadataFromMED(medlist[0])
            thismpp = medjson.get('MPP', 0.0)
    ## what if mpp = 0.0?
    if thismpp == 0.0:
        in_mpp = input('Please enter the MPP data for analyzing .aix files: ')
        try:
            thismpp = float(in_mpp)
        except:
            thismpp = 0.0
            logger.error('input data is not a valid float data, can not continue analyzing!')
            logger.warning('Please get the MPP data, and run this appication again!')
            return None
    cellmeta, tagsmeta = [], []
    if thismpp != 0.0:
        aixlist = glob.glob(os.path.join(workpath, '*.aix'))
        for aixfile in tqdm(aixlist, desc=f'collecting analysis metadata from {workpath}'):
            ## collect analysis metadata
            thismeta = {}
            aixinfo, cellcount, cellslist = getCellsInfoFromAIX(aixfile, mpp=thismpp)
            modelname, modelversion = aixinfo['Model'], aixinfo['ModelVersion']
            thismeta['modelname'], thismeta['modelversion'] = modelname, modelversion
            thismeta['cellcount'] = cellcount
            thismeta['similaritydegree'] = aixinfo.get('SimilarityDegree', '')
            if modelname == 'AIxURO':
                averageAREA = getUROaverageOfSAcells(cellslist)
                thismeta['avgsncratio'] = averageAREA['suspicious']['nc_ratio']
                thismeta['avgscelarea'] = averageAREA['suspicious']['cell_area']
                thismeta['avgsnucarea'] = averageAREA['suspicious']['nuclei_area']
                thismeta['avgancratio'] = averageAREA['atypical']['nc_ratio']
                thismeta['avgacelarea'] = averageAREA['atypical']['cell_area']
                thismeta['avganucarea'] = averageAREA['atypical']['nuclei_area']
                _, averageTOP = getUROaverageOfTopCells(cellslist, NUM_TOP, ONLY_SUSPICIOUS)
                thismeta['topncratio'] = averageTOP['nc_ratio']
                thismeta['topcelarea'] = averageTOP['cell_area']
                thismeta['topnucarea'] = averageTOP['nuclei_area']
            cellmeta.append(thismeta)
            #### save metadata to CSV
            saveTCellsMetadata2CSV(aixfile, cellslist, modelname, modelversion)
            ## collect traits information
            if modelname == 'AIxURO':
                thistrait = countNumberOfUROtraits(cellslist, CRITERA_TRAIT)
            else:
                thistrait = countNumberOfTHYtraits(cellslist, NUM_TRAIT_THY, CRITERA_TRAIT)
            tagsmeta.append(thistrait)
    if cellmeta and tagsmeta:
        modelname = cellmeta[0]['modelname']
        modelversion = cellmeta[0]['modelversion']
        ## summary of analysis metadata
        saveAnalysisMetadata2CSV(modelname, modelversion, aixlist, cellmeta)
                                                                         
        ## summary of traits
        saveTraitsSummary2CSV(modelname, modelversion, aixlist, tagsmeta)
        logger.info('[analysis] .aix files analysis completed!!')
    else:
        logger.warning('No .aix files found in the directory, or MPP data is not available, can not continue analyzing!')

