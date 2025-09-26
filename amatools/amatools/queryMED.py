## ----- utility to retrieve metadata.json from .med
import os, io
import shutil
import json
import time
from datetime import timedelta
import numpy as np
import math
from loguru import logger
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from .asarlib import AsarFile
from .amautility import replaceSpace2underscore

## ---------- ---------- ---------- ----------
## retrieve metadata.json from .med file
## ---------- ---------- ---------- ----------
def getMetadataFromMED(medfile):
    with AsarFile(medfile) as thismed:
        mdata = thismed.read_file('metadata.json')
    metajson = json.loads(mdata)
    return metajson

## ---------- ---------- ---------- ----------
## crop tile image from .med file
## ---------- ---------- ---------- ----------
def cropTileFromMLayerOfMED(medfname, whichz, x_topleft, y_topleft, fov_size_x, fov_size_y):
    ## read .med file using asarlib
    asar = AsarFile(medfname)
    ztree = asar.listdir(f'Z{whichz}_files')
    ##
    pyramid_bottom_layer = sorted([int(x) for x in ztree if x.isnumeric()])[-1]
    dzi_path = f'Z{whichz}_files/{pyramid_bottom_layer}'
    # use an auxiliary image to cover the ROI, then crop the part we need
    tile_x, tile_y = int(x_topleft // 254), int(y_topleft // 254)
    img_aux_x_tile_num, img_aux_y_tile_num = math.ceil(fov_size_x / 254) + 1, math.ceil(fov_size_y / 254) + 1

    img_aux = np.full((img_aux_y_tile_num * 254, img_aux_x_tile_num * 254, 3), 243, dtype=np.uint8) # 243 = background value (roughly)
    webplist = asar.listdir(dzi_path)
    for x in range(img_aux_x_tile_num):
        for y in range(img_aux_y_tile_num):
            webpname = f'{tile_x + x}_{tile_y + y}.webp'
            img_dzi_path = f"{dzi_path}/{webpname}"
            if webpname in webplist:
                readwebp = asar.read_file(img_dzi_path, decode=False)
                pil_img = Image.open(io.BytesIO(readwebp))
                img_dzi = np.array(pil_img)[1 if tile_y + y > 0 else 0:-1, 1 if tile_x + x > 0 else 0:-1, :]
            else:
                continue
            img_aux[y*254 : min((y+1)*254, y*254+img_dzi.shape[0]), x*254 : min((x+1)*254, x*254+img_dzi.shape[1]), :] = img_dzi
    img = img_aux[y_topleft - tile_y*254:y_topleft - tile_y*254 + fov_size_y, x_topleft - tile_x*254:x_topleft - tile_x*254 + fov_size_x, :]
    ##
    asar.close()
    return img

## ---------- ---------- ---------- ----------
## update metadata.json from multiple layers to single layer
## ---------- ---------- ---------- ----------
def updateMEDmetadata2singleLayer(medfile, dzipath):
    medjson = getMetadataFromMED(medfile)
    sizeZ = medjson.get('SizeZ', 1)
    if sizeZ == 1:
        logger.warning(f'{os.path.basename(medfile)} is already a single layer image')
        return sizeZ, 0
    bestZ = medjson.get('BestFocusLayer', -1)
    if bestZ == -1:
        logger.error(f'missing BestFocusLayer in metadata.json of {os.path.basename(medfile)}')
        return sizeZ, 0
    medjson.pop('BestFocusLayer')
    levelcount = medjson.get('LevelCount', 0)
    if levelcount > 0:
        medjson['LevelCount'] = 0
    medjson['IndexZ'] = [0]
    medjson['SizeZ']  = 1
    ## update metadata.json
    metafile = os.path.join(dzipath, 'metadata.json')
    with open(metafile, 'w', encoding='utf-8') as newmeta:
        json.dump(medjson, newmeta)
    logger.info(f'metadata.json for single layer was updated for {medfile}')
    return sizeZ, bestZ

## ---------- ---------- ---------- ----------
## extract specified layer from multiple layers of .med file (using asarlib)
## ---------- ---------- ---------- ----------
def extractOneLayerFromMED(medfname, binpath, whichlayer):
    ## parameters settings
    dzi_tmp = os.path.join(os.genenv('temp'), 'dzi')
    rasar = os.path.join(binpath, 'convert', 'rasar.exe')
    if os.path.exists(rasar) == False:
        logger.error(f"can't find {rasar}, please check again")
        return
    ## replace ' ' with '_' in the .med filename
    thismed = replaceSpace2underscore(medfname)
    if not os.path.exists(dzi_tmp):
        os.makedirs(dzi_tmp)
    ## extraact necessary files/folders from .med, using asarlib
    try:
        with AsarFile(thismed) as unpackmed:
            mdata = unpackmed.read_file('metadata.json')
            metajson = json.loads(mdata)
            zstack = metajson.get('SizeZ')
            if whichlayer >= zstack:
                logger.error(f'{os.path.basename(medfname)} contains {zstack}-layer, unable to extract {whichlayer} layer')
                return
            bestz = metajson.get('BestFocusLayer', 0)
            if bestz == 0:
                logger.warning(f'{thismed} is a singe layer image.')
                return
            metajson.pop('BestFocusLayer')  ## remove BestFocusLayer
            if metajson.get('LevelCount') != None:
                metajson['LevelCount'] = 0
            #zstack = metajson.get('SizeZ')
            if zstack != None:
                metajson['SizeZ'] = 0
            if metajson.get('IndexZ') != None:
                metajson['IndexZ'] = [0]
            ## rewrite metadata.json for bestz layer
            with open(os.path.join(dzi_tmp, 'metadata.json'), 'w', encoding='utf-8') as fmeta:
                json.dump(metajson, fmeta)
            ## extract webp data of bestz layer
            dirwalk = unpackmed.listdir()
            unpackmed.extract(f'Z{whichlayer}_files', dzi_tmp)
            unpackmed.extract_file(f'Z{whichlayer}.dzi', dzi_tmp)
            os.rename(os.path.join(dzi_tmp, f'Z{whichlayer}_files'), os.path.join(dzi_tmp, 'Z0_files'))
            os.rename(os.path.join(dzi_tmp, f'Z{whichlayer}.dzi'), os.path.join(dzi_tmp, 'Z0.dzi'))
            if f'Z{whichlayer}.dz' in dirwalk:
                unpackmed.extract_file(f'Z{whichlayer}.dz', dzi_tmp)
                os.rename(os.path.join(dzi_tmp, f'Z{whichlayer}.dz'), os.path.join(dzi_tmp, 'Z0.dz'))
            stidx = zstack*3 if f'Z{whichlayer}.dz' in dirwalk else zstack*2
            for i in range(stidx, len(dirwalk)):
                if dirwalk[i] == 'metadata.json':
                    continue
                unpackmed.extract_file(dirwalk[i], dzi_tmp)
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling asarlib.AsarFle(): {e}")
        return
    ## pack dzi to a single.med file
    medprefixname = os.path.splitext(thismed)[0]
    layermed = medprefixname + f'z{whichlayer:02}.med'
    logger.trace(f'Packing {dzi_tmp} to {layermed}...')
    packMED = f'{rasar} pack {dzi_tmp} {layermed}'
    os.system(packMED)
    logger.info(f'{layermed} completed! removing temporary dzi folder...')
    shutil.rmtree(dzi_tmp)
    return

## ---------- ---------- ---------- ----------
##  extract DZI data of specified layer from .med file
## ---------- ---------- ---------- ----------
def extractDZIdataFromMED(medfile, layer, dzipath):
    with AsarFile(medfile) as thismed:
        ## extract associated file
        asslist = thismed.listdir()
        dz_existed = False
        for _, associate in enumerate(asslist):
            if 'Z' not in associate and associate != 'metadata.json':
                thismed.extract_file(associate, dzipath)
            if f'Z{layer}.dz' == associate:
                dz_existed = True
        thismed.extract(f'Z{layer}_files', dzipath)
        if dz_existed:
            thismed.extract_file(f'Z{layer}.dz', dzipath)
        thismed.extract_file(f'Z{layer}.dzi', dzipath)
        os.rename(os.path.join(dzipath, f'Z{layer}_files'), os.path.join(dzipath, 'Z0_files'))
        os.rename(os.path.join(dzipath, f'Z{layer}.dzi'), os.path.join(dzipath, 'Z0.dzi'))
        if dz_existed:
            os.rename(os.path.join(dzipath, f'Z{layer}.dz'), os.path.join(dzipath, 'Z0.dz'))

## ---------- ---------- ---------- ----------
##  extract every single layers from mutiple layers of .med file
## ---------- ---------- ---------- ----------
def extractSingleLayersFromMultiLayersMED(medfname, dstpath, binpath, whichlayers=None, modelname=None):
    binasar = os.path.join(binpath, 'convert', 'rasar.exe')
    multimed = replaceSpace2underscore(medfname)
    dzipath = os.path.join(dstpath, 'dzi')
    if os.path.isdir(dzipath) == False:
        os.makedirs(dzipath)
    logger.info(f'extract single layers from {os.path.basename(medfname)} to {dstpath}')
    t0 = time.perf_counter()
    TotalLayers, BestzLayer = updateMEDmetadata2singleLayer(multimed, dzipath)
    medprefix = os.path.splitext(os.path.split(multimed)[1])[0]
    ## identify which layers should be extracting
    is_singleLayer = True
    if whichlayers == []:
        slayer = BestzLayer
    else:
        slayer = whichlayers[0]
        if len(whichlayers) == 2:
            elayer = whichlayers[1]
            is_singleLayer = False
    if is_singleLayer:
        if slayer > TotalLayers:
            slayer = BestzLayer
        extractDZIdataFromMED(multimed, slayer, dzipath)
        thismed = os.path.join(dstpath, f'{medprefix}_z{slayer:02}.med')
        cmd_packmed = f'{binasar} pack {dzipath} {thismed}'
        os.system(cmd_packmed)
        logger.info(f'{os.path.basename(thismed)} is generated!')
        # remove Z0_files, Z0.dzi, Z0.dz
        if os.path.isdir(f'{dzipath}\\Z0_files'):
            shutil.rmtree(f'{dzipath}\\Z0_files')
        if os.path.isfile(f'{dzipath}\\Z0.dzi'):
            os.remove(f'{dzipath}\\Z0.dzi')
        if os.path.isfile(f'{dzipath}\\Z0.dz'):
            os.remove(f'{dzipath}\\Z0.dz')
    else:
        if slayer > elayer:
            slayer, elayer = elayer, slayer
        if elayer >= TotalLayers:
            elayer = TotalLayers-1
        for lidx in range(slayer, elayer+1):
            extractDZIdataFromMED(multimed, lidx, dzipath)
            bz = f'_{lidx:02}_bestz_' if lidx == BestzLayer else '_'
            thismed = os.path.join(dstpath, f'{medprefix}{bz}z{lidx:02}.med')
            cmd_packmed = f'{binasar} pack {dzipath} {thismed}'
            os.system(cmd_packmed)
            logger.info(f'[{os.path.basename(thismed)} is generated!')
            # remove Z0_files, Z0.dzi, Z0.dz
            if os.path.isdir(f'{dzipath}\\Z0_files'):
                shutil.rmtree(f'{dzipath}\\Z0_files')
            if os.path.isfile(f'{dzipath}\\Z0.dzi'):
                os.remove(f'{dzipath}\\Z0.dzi')
            if os.path.isfile(f'{dzipath}\\Z0.dz'):
                os.remove(f'{dzipath}\\Z0.dz')
    ## remove dzi folder
    shutil.rmtree(dzipath)
    consumed_time = f'{timedelta(seconds=time.perf_counter()-t0)}'
    alllayers = f'z{slayer}' if is_singleLayer else f'z{slayer}-z{elayer}'
    logger.info(f'took {consumed_time[:-3]} to extract {alllayers} single layers from {os.path.basename(medfname)}')
    if modelname in ['AIxURO', 'AIxTHY']:
        t0 = time.perf_counter()
        updateDeCartConfig(modelname)
        decart_version = args['decart_ver']
        doModelInference(dstpath, modelname, decart_version, bmetadata=False)
        tsstop = datetime.now().timestamp()
        aux.printmsg(f'[INFO] took {aux.timestampDelta2String(tsstop-tsfrom)} to analyze all {TotalLayers} single layers from {os.path.basename(medfname)}')
