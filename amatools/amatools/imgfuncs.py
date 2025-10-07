import os
import glob
import numpy as np
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None
import cv2
from .queryMED import cropTileFromMLayerOfMED
from .amautility import getCellTileCoordinates

##---------------------------------------------------------
## return gray image from BGR image
def cvt2GrayImage(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

##---------------------------------------------------------
## calculate tile sharpness value with 'brenner' or 'laplacian' methods
##---------------------------------------------------------
def calcTileSharpnessValue(grayimg, method='brenner'):
    if method == 'brenner':
        sharpness = 0
        shapes = np.shape(grayimg)
        for x in range(0, shapes[0]-2):
            for y in range(0, shapes[1]):
                sharpness += (int(grayimg[x+2], y)-int(grayimg[x, y]))**2
    elif method == 'laplacian':
        laplacian = cv2.Laplacian(grayimg, cv2.CV_64F)
        sharpness = np.mean(np.abs(laplacian))
    return sharpness

##---------------------------------------------------------
## update gamma value of image
def updateGamma2Image(pngfile, gamma=1.0):
    pngimg = cv2.imread(pngfile)
    ## build a lookup table mapping the pixel values [0, 255] to adjust gamma values
    newGamma = 1.0 / gamma
    lookup_table = np.array([((i/255.0)**newGamma)*255 for i in np.arange(0,256)]).astype('uint8')
    ## apply gamma correction using the lookup table
    return cv2.LUT(pngimg, lookup_table)

##---------------------------------------------------------
## save cropped tile image to png file
def saveCropTile2PNG(cropimg, pngfile, z=None):
    thisimg = Image.fromarray(cropimg)
    if z:
        imgw, imgh = thisimg.size
        draw = ImageDraw.Draw(thisimg)
        draw.text((8, imgh-16), f'z{z:02}', (0, 0, 0))
    thisimg.save(pngfile)

##---------------------------------------------------------
## save cell tile image (default: 200x200)
##---------------------------------------------------------
def saveCellTile2PNG(medfile, tilefname, layerZ, celldata):
    cx, cy, cw, ch = getCellTileCoordinates(celldata['segments_cell'])
    ## change tile size to 200x200
    tx, ty = cx + cw//2 - 100, cy + ch//2 - 100
    if tx <= 0:
        tx = 0
    if ty <= 0:
        ty = 0
    tileimg = cropTileFromMLayerOfMED(medfile, layerZ, tx, ty, 200, 200)
    saveCropTile2PNG(tileimg, tilefname)

##---------------------------------------------------------
## save multiple cropped tile image into animation png file
def saveMutiPNG2GIF(pngfolder, gifname):
    pnglist = sorted(glob.glob(os.path.join(pngfolder, '*.png')))
    if len(pnglist) == 0:
        print('No png files found.')
        return
    # Create the frames
    frames = []
    for i in pnglist:
        new_frame = Image.open(i)
        frames.append(new_frame)
    # Save into a GIF file that loops forever
    frames[0].save(gifname, format='GIF',
               append_images=frames[1:],
               save_all=True,
               duration=500, loop=0)

