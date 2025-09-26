import argparse
import psutil
import re
from loguru import logger
from .modelWSI import cmdModelInference
from .amaconfig import initLogger, pcENV
from .amautility import updateDeCartConfig
from .parseAIX import retrieveAnalysisMetadata
from .queryMED import extractSingleLayersFromMultiLayersMED

def stopThisTask(taskname):
    ## getRunningTaskPID
    tasks_psutil = []
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        try:
            tasks_psutil.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            print("[cli.py][ERROR] errors occurred while getting running tasks with psutil")
    taskPID = None
    for task in tasks_psutil:
        if taskname == task['name']:
            taskPID = task['pid']
            break
    if not taskPID:
        ## stopTask
        try:
            proc = psutil.Process(taskPID)
            proc.terminate()  # 或使用 proc.kill() 強制終止
            proc.wait(timeout=3)
            print(f"[cli.py][INFO] Process {taskname} (pid={taskPID}) terminated.")
        except Exception as e:
            print(f"[cli.py][ERROR] Failed to terminate process {taskPID}: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destpath", help="destination path")
    parser.add_argument("-f", "--wsipath", help="wsi file or wsi folder or med/aix folder", required=True)
    parser.add_argument("-j", "--configjson", help="configuration settings")
    parser.add_argument("-l", "--layers", help='[i, j]: from layer-i to layer-j')
    parser.add_argument("-m", "--modelname", help='model product name')
    parser.add_argument("-o", "--option", default="inference", required=True)
    parser.add_argument("-p", "--decartpath", help='decart folder')
    parser.add_argument("-v", "--decartversion", help='decart version')
    args = parser.parse_args()
    # initiate Logger
    initLogger()
    # initiate parameters for this HW environment
    AMA_ARGS = pcENV()
    AMA_ARGS.loadConfigJson(args.configjson) if args.configjson else AMA_ARGS.defaultConfig()
    # actions
    action = args.option.lower()
    if action == 'inference':
        cmdModelInference(args.wsipath, model_name=args.modelname, decart_version=args.decartversion, config_file=args.configjson)
    elif action == 'analysis':
        retrieveAnalysisMetadata(args.wsipath)
    elif action == 'extract':
        layer_range = args.layers
        zrange = []     ## default: best-z only
        if layer_range:
            if bool(re.match(r'^[\d-]+$', layer_range)) == False:
                logger.error(f'do not know which layers need to be extracting: {layer_range}')
            else:
                zrange = args.layers.split('-')
                if len(zrange) <= 2:
                    zrange.append(int(layer_range[0]))
                    zrange.append(int(layer_range[1]))
        ##
        if args.modelname:
            thismodel = args.modelname
            updateDeCartConfig(thismodel, AMA_ARGS.envConfig['decartyaml'])
        else:
            thismodel = None
        extractSingleLayersFromMultiLayersMED(args.wsipath, args.destpath, whichlayers=zrange, modelname=thismodel)
    else:
        logger.error(f'[cli.py] unknown action {action}')
        usage_example = '''Usage:
          [option='inference'] for running model inference
            ama-go -o inference -f d:\workfolder\inference\test -m AIxURO -v 2.7.4
          [option='analysis'] for analyzing metadata from .aix folder
            ama-go -o analysis -f d:\workfolder\inference\test
          [option='extract'] for extract single layer images from .med file
            ama-go -o extarct -f multiple_layers.med -d dest_folder_path -l 0-4
        '''
        print('-'*80)
        print(usage_example)
        print('-'*80)
