## amatools.amaconfig
##   (1) initiate loguru.Logger
##   (2) configuration for working machine
## 
import os, sys
import json
from loguru import logger
import wmi, GPUtil, platform

## ---------- ---------- ---------- ----------
## 📋 initiate Loguru.Logger
## ---------- ---------- ---------- ----------
def initLogger(level=None, logpath=None):
    # 📝 設定日誌
    log_level = 'TRACE' if (not level) or (level.lower() not in ['info', 'debug', 'warning', 'error']) else level
    # log folder exists?
    if logpath == None:
        logpath = os.path.join(os.getenv('LOCALAPPDATA'), 'amatools')
    if os.path.isdir(logpath) == False:
        os.makedirs(logpath)

    logfile = os.path.join(logpath, 'amatools.log')
    if os.path.isfile(logfile):
        logger.warning(f'{logfile} already existed!')

    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <blue>Line {line: >4} ({file}):</blue> | <b>{message}</b>"
    logger.add(sys.stdout, level=log_level, format=log_format, colorize=True, backtrace=True, diagnose=True)
    logger.add(logfile, rotation='4 MB', level=log_level, format=log_format, colorize=False, backtrace=True, diagnose=True)

## ---------- ---------- ---------- ----------
## ⚙️ HW components: OS, CPU, GPU, RAM
## ---------- ---------- ---------- ----------
def getMSinfo():
    thispc = wmi.WMI()
    ## OS
    winos = thispc.Win32_OperatingSystem()
    hw_os = winos[0].Caption if len(winos) > 0 else ''
    ## CPU
    cpu = thispc.Win32_Processor()
    hw_cpu = cpu[0].Name.strip() if len(cpu) > 0 else ''
    ## RAM
    ram = thispc.Win32_PhysicalMemory()
    ram_mb = 0
    for i in range(len(ram)):
        ram_mb += int(ram[i].Capacity)/1048576
    hw_ram = f'{round(ram_mb/1024)}GB'
    ## GPU 
    gpu = GPUtil.getGPUs()
    hw_gpu = gpu[0].name if len(gpu) > 0 else ''

    thisos = platform.platform()
    
    return thisos, hw_os, hw_cpu, hw_gpu, hw_ram

## ---------- ---------- ---------- ----------
## configuration for working machine
## ---------- ---------- ---------- ----------
class pcENV:
    def __init__(self, jsonfile=None):
        self.envConfig = {}
        if jsonfile:
            self.loadConfigJson(jsonfile)

    def loadConfigJson(self, jsonfile):
        if os.path.isfile(jsonfile):
            with open(jsonfile, 'r', encoding='utf-8') as f:
                dictconfig = json.load(f)
            param = dictconfig.get('localdrive', {})
            self.envConfig['amahome'] = param.get('home', 'd:\\amahome')
            self.envConfig['wsipath'] = param.get('modelwatch', 'd:\\amahome\\wsipath')
            self.envConfig['med_aix'] = param.get('imgbackup', 'd:\\amahome\\medaix')
            param = dictconfig.get('decart', {})
            self.envConfig['decartpath'] = param.get('binpath', 'c:\\bin\\DeCart\\decart2.7.4')
            self.envConfig['decart_exe'] = os.path.join(self.envConfig['decartpath'], 'decart.exe')
            self.envConfig['decart_ver'] = param.get('version', '2.7.4')
            self.envConfig['decartyaml'] = param.get('config', 'c:\\ProgramData\\DeCart\\config.yaml')
            param = dictconfig.get('metadata', {})
            self.envConfig['dbmeta_uro'] = param.get('db_uro', 'metadataURO.db')
            self.envConfig['dbmeta_thy'] = param.get('db_thy', 'metadataTHY.db')
            self.envConfig['hw_os'], _, self.envConfig['hw_cpu'], self.envConfig['hw_gpu'], self.envConfig['hw_ram'] = getMSinfo()
        else:
            logger.error(f'[pcENV] {jsonfile} not found!')

    def defaultConfig(self):
        self.envConfig['amahome'] = 'd:\\amahome'
        self.envConfig['wsipath'] = 'd:\\amahome\\wsipath'
        self.envConfig['med_aix'] = 'd:\\amahome\\medaix'
        self.envConfig['decart_ver'] = '2.7.4'
        self.envConfig['decartpath'] = f"c:\\bin\\DeCart\\decart{self.envConfig['decart_ver']}"
        self.envConfig['decart_exe'] = os.path.join(self.envConfig['decartpath'], 'decart.exe')
        self.envConfig['decartyaml'] = 'c:\\ProgramData\\DeCart\\config.yaml'
        self.envConfig['dbmeta_uro'] = 'metadataURO.db'
        self.envConfig['dbmeta_thy'] = 'metadataTHY.db'
        #self.envConfig['hw_os']  = 'Windows11 Pro 24H2' 
        #self.envConfig['hw_cpu'] = 'Ryzen 7 7700X'
        #self.envConfig['hw_gpu'] = 'RTX 4060 Ti'
        #self.envConfig['hw_ram'] = '128GB'
        self.envConfig['hw_os'], _, self.envConfig['hw_cpu'], self.envConfig['hw_gpu'], self.envConfig['hw_ram'] = getMSinfo()

## ---------- ---------- ---------- ----------
## configuration for this machine, should be customized for each machine
## ---------- ---------- ---------- ----------
def getConfig(decart_sw_version, dictConfig=None):
    if dictConfig == None:
        dictConfig = {}
        dictConfig['workzone'] = r'd:\workfolder'
        dictConfig['runmodel'] = os.path.join(dictConfig['workzone'], 'aixinference')
        dictConfig['tempzone'] = os.path.join(dictConfig['workzone'], 'tmpzone')
        dictConfig['backpath'] = os.path.join(dictConfig['workzone'], 'medaix')
        dictConfig['binpath']  = r'c:\bin'
        dictConfig['decart_ver'] = decart_sw_version
        dictConfig['decartpath'] = os.path.join(dictConfig['binpath'], f"decart{dictConfig['decart_ver']}")
        dictConfig['exe_decart'] = os.path.join(dictConfig['binpath'], f"decart{dictConfig['decart_ver']}", 'decart.exe')
        dictConfig['exe_rasar']  = os.path.join(dictConfig['binpath'], f"decart{dictConfig['decart_ver']}", 'convert', 'rasar.exe')
        dictConfig['exe_vips']   = os.path.join(dictConfig['binpath'], f"decart{dictConfig['decart_ver']}", 'convert', 'vips.exe')
        dictConfig['dbmeta_uro'] = os.path.join(dictConfig['runmodel'], 'metadataURO.db')
        dictConfig['dbmeta_thy'] = os.path.join(dictConfig['runmodel'], 'metadataTHY.db')
        hw_os, _, hw_cpu, hw_gpu, hw_ram = getMSinfo()
        dictConfig['hw_os']  = hw_os
        dictConfig['hw_cpu'] = hw_cpu
        dictConfig['hw_gpu'] = hw_gpu
        dictConfig['hw_ram'] = hw_ram
    # return configuration
    params = {}
    params['workzone'] = dictConfig.get('workzone', os.getenv('HOME'))
    params['runmodel'] = dictConfig.get('runmodel', os.path.join(dictConfig['workzone'], 'aixinference'))
    params['tempzone'] = dictConfig.get('tempzone', os.path.join(dictConfig['workzone'], 'tmpzone'))
    params['backpath'] = dictConfig.get('backpath', os.path.join(dictConfig['workzone'], 'medaix'))
    params['binpath'] = dictConfig.get('binpath', r'c:')
    params['decart_ver'] = decart_sw_version
    params['exe_decart'] = dictConfig.get('exe_decart', os.path.join(params['binpath'], decart_sw_version, 'decart.exe'))
    params['exe_rasar'] = dictConfig.get('exe_rasar', os.path.join(params['binpath'], decart_sw_version, 'rasar.exe'))
    params['exe_vips'] = dictConfig.get('exe_vips', os.path.join(params['binpath'], decart_sw_version, 'convert', 'vips.exe'))
    params['db_meta_uro'] = dictConfig.get('db_mata_uro', os.path.join(params['runmodel'], 'metadataURO.db'))
    params['db_meta_thy'] = dictConfig.get('db_mata_thy', os.path.join(params['runmodel'], 'metadataTHY.db'))
    params['hw_os'] = dictConfig.get('hw_os')
    params['hw_cpu'] = dictConfig.get('hw_cpu')
    params['hw_gpu'] = dictConfig.get('hw_gpu')
    params['hw_ram'] = dictConfig.get('hw_ram')
    return params

