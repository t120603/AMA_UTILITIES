import argparse
import os, shutil
from .qcxmain import startQCAPI
#from .qcxfuncs import startMonitorFolders

import psutil

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
    print(f"[cli.py][TRACE] Process {taskname} (pid={taskPID})")
    if taskPID:
        ## stopTask
        try:
            proc = psutil.Process(taskPID)
            proc.terminate()  # 或使用 proc.kill() 強制終止
            proc.wait(timeout=3)
            print(f"[cli.py][INFO] Process {taskname} (pid={taskPID}) terminated.")
        except Exception as e:
            print(f"[cli.py][ERROR] Failed to terminate process {taskPID}: {e}")
    return taskPID

def main():
    ## stop 'qcapi-cch' and 'watch-wsi' tasks if still running
    ## stopThisTask('qcapi-cch.exe') <-- idiot!!
    taskpid = stopThisTask('watch-wsi.exe')
    if taskpid:
        print(f"[cli.py][WARNING] watch-wsi.exe (pid={taskpid}) is still running")
        #return False
    ##
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--config", default=None)
    parser.add_argument("-l", "--logfname", default=None)
    args = parser.parse_args()

    #init configuration if run with config.json
    # copy config file to %LOCALAPPDATA%
    folder = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi')
    if os.path.exists(folder) == False:
        os.makedirs(folder)
    if args.config:
        config = os.path.join(folder, 'config-qcapi-cch.json')
        shutil.copy(args.config, config)
        print(f'[INFO] copied {args.config} to {config}')
    fname = 'qcapi-debug.log' if not args.logfname else args.logfname
    logfile = os.path.join(folder, fname)
    print(f'[INFO] logfile is {logfile}')
    startQCAPI(args.config, logfile)
