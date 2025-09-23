## ----- utility to retrieve metadata.json from .med
import io
import json
import webp
import numpy as np
import math
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from .asarlib import AsarFile
from .amautility import replaceSpace2underscore

def getMetadataFromMED(medfile):
    with AsarFile(medfile) as thismed:
        mdata = thismed.read_file('metadata.json')
    metajson = json.loads(mdata)
    return metajson

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

## extract specified layer from multiple layers of .med file (using asarlib)
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

