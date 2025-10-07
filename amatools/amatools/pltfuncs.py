import os, glob
os.environ['OPENCV_IO_MAX_IMAGE_PIXELS'] = str(pow(2, 50))
import cv2
import io
import gzip
import webp
import numpy as np
import math
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
from scipy.interpolate import make_interp_spline, interp1d, PchipInterpolator
from .parseAIX import get_URO_NucleusAreaData, get_URO_NCRatioData, get_URO_CellAreaData

##---------------------------------------------------------
## draw smooth line chart using PCHIP
##---------------------------------------------------------
def drawSmoothLineChart(xy):
    # 1. 原始數據（非均勻或稀疏點）
    xnc = np.array(xy['xticks'])
    ysc = np.array(xy['scells'])
    yac = np.array(xy['acells'])
    # 檢查原始極值
    ys_min, ys_max = ysc.min(), ysc.max()
    ya_min, ya_max = yac.min(), yac.max()
    # 2. 生成密集的 x_new 用於平滑繪圖
    x_new = np.linspace(xnc.min(), xnc.max(), 500)
    # 3. 使用 PCHIP 進行插值（保形，不超限）
    pchip = PchipInterpolator(xnc, ysc)
    ysc_new = pchip(x_new)
    pchip = PchipInterpolator(xnc, yac)
    yac_new = pchip(x_new)
    # 驗證插值結果是否超出原始極值
    assert ysc_new.min() >= ys_min - 1e-10, "插值結果低於原始最小值！"
    assert ysc_new.max() <= ys_max + 1e-10, "插值結果高於原始最大值！"
    assert yac_new.min() >= ya_min - 1e-10, "插值結果低於原始最小值！"
    assert yac_new.max() <= ya_max + 1e-10, "插值結果高於原始最大值！"
    # 4. 繪圖
    fig, ax = plt.subplots(figsize=(6,9))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.set(xticks=xnc, xticklabels=xy['xlabel'])
    ax.plot(x_new, yac_new, c='#F7E142', label='atypical cell')
    ax.scatter(xnc, yac, marker='o', facecolors='none', color='#F7E142', label='atypical cell')
    ax.plot(x_new, ysc_new, c='red', label='suspicious cell')
    ax.scatter(xnc, ysc, marker='o', facecolors='none', color='red', label='suspicious cell')

    plt.ylabel('Number of Cells')
    ax.text(0, 1.1, xy['title'], color='blue', fontweight='bold', transform=ax.transAxes)
    tailunit = ' μm²' if xy['title'] == 'NUCLEUS AREA' else ''
    offset_delta = 0.12 if xy['title'] == 'NUCLEUS AREA' else 0
    stext = '□ Suspicious cell '
    if xy['s_avg'] > 0:
        stext += f"[{xy['s_avg']:.2f}±{xy['s_err']:.2f}{tailunit}]"
        offseta = 0.46 + offset_delta
    else:
        offseta = 0.3
    ax.text(0, 1.05, stext, color='red', transform=ax.transAxes)
    atext = '□ Atypical cell '
    if xy['a_avg'] > 0:
        atext += f"[{xy['a_avg']:.2f}±{xy['a_err']:.2f}{tailunit}]"
    ax.text(offseta, 1.05, atext, color='#F7E142', transform=ax.transAxes)
    ax.grid(visible=True, axis='y', color='lightgray')
    #ax.legend()
    plt.savefig(xy['pngname'])
    plt.close(fig)

def drawURO_AVG_NCRatio(pltpath, scells, acells, uroaverage):
    xl = ['0.4', '0.45', '0.5', '0.55', '0.6', '0.65', '0.7', '0.75', '0.8', '0.85', '0.9', '0.95', '1.0']
    xi = [i for i in range(len(xl))]
    ys = [0 for _ in range(len(xl))]
    ya = [0 for _ in range(len(xl))]
    # get N/C Ratio data
    sc_elements, sc_counts, ac_elements, ac_counts = get_URO_NCRatioData(scells, acells)
    for ii in range(len(sc_elements)):
        iidx = int(((sc_elements[ii]-0.4)*100+0.1)/5)
        ys[iidx] += sc_counts[ii]
    for ii in range(len(ac_elements)):
        iidx = int(((ac_elements[ii]-0.4)*100+0.1)/5)
        ya[iidx] += ac_counts[ii]

    drawdata = {}
    drawdata['xticks'] = xi
    drawdata['xlabel'] = xl
    drawdata['scells'] = ys
    drawdata['acells'] = ya
    drawdata['title'] = 'N/C RATIO'
    drawdata['s_avg'] = uroaverage['suspicious']['nc_ratio']
    drawdata['s_err'] = uroaverage['suspicious']['ratio_error']
    drawdata['a_avg'] = uroaverage['atypical']['nc_ratio']
    drawdata['a_err'] = uroaverage['atypical']['ratio_error']
    drawdata['pngname'] = os.path.join(pltpath, 'URO_NCRatio_Chart.png')
    drawSmoothLineChart(drawdata)

def drawURO_AVG_NucleusArea(pltpath, scells, acells, uroaverage):
    xl = ['0', '20', '40', '60', '80', '100', '120', '140', '160', '180', '200', '>200']
    xi = [i for i in range(len(xl))]
    ys = [0 for _ in range(len(xl))]
    ya = [0 for _ in range(len(xl))]
    # get N/C Ratio data
    sc_elements, sc_counts, ac_elements, ac_counts = get_URO_NucleusAreaData(scells, acells)
    for ii in range(len(sc_elements)):
        if int(sc_elements[ii]) >= 210:
            ys[11] += sc_counts[ii]
        else:
            iidx = int((sc_elements[ii]+10)/20)
            ys[iidx] += sc_counts[ii]
    for ii in range(len(ac_elements)):
        if int(ac_elements[ii]) >= 210:
            ya[11] += ac_counts[ii]
        else:
            iidx = int((ac_elements[ii]+10)/20)
            ya[iidx] += ac_counts[ii]

    drawdata = {}
    drawdata['xticks'] = xi
    drawdata['xlabel'] = xl
    drawdata['scells'] = ys
    drawdata['acells'] = ya
    drawdata['title'] = 'NUCLEUS AREA'
    drawdata['s_avg'] = uroaverage['suspicious']['nuclei_area']
    drawdata['s_err'] = uroaverage['suspicious']['nuclei_error']
    drawdata['a_avg'] = uroaverage['atypical']['nuclei_area']
    drawdata['a_err'] = uroaverage['atypical']['nuclei_error']
    drawdata['pngname'] = os.path.join(pltpath, 'URO_NucleusArea_Chart.png')
    drawSmoothLineChart(drawdata)

