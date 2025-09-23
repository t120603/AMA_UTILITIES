import argparse
import psutil
from .modelWSI import cmdModelInference
from .amaconfig import initLogger
from .parseAIX import retrieveAnalysisMetadata

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
    parser.add_argument("-m", "--modelname", help='model product name')
    parser.add_argument("-o", "--option", default="inference", required=True)
    parser.add_argument("-p", "--decartpath", help='decart folder')
    parser.add_argument("-v", "--decartversion", help='decart version')
    args = parser.parse_args()
    # initiate Logger
    initLogger()
    action = args.option.lower()
    if action == 'inference':
        cmdModelInference(args.wsipath, model_name=args.modelname, decart_version=args.decartversion, config_file=args.configjson)
    elif action == 'analysis':
        retrieveAnalysisMetadata(args.wsipath)
    else:
        logger.error(f'[cli.py] unknown action {action}')
        usage_example = '''Usage:
          [option='inference'] for running model inference
            ama-go -o inference -f d:\workfolder\inference\test -m AIxURO -v 2.7.4
          [option='analysis'] for analyzing metadata from .aix folder
            ama-go -oanalysis -f d:\workfolder\inference\test
        '''
        print('-'*80)
        print(usage_example)
        print('-'*80)
