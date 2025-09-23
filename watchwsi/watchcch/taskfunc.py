import psutil
import subprocess
from loguru import logger
import time

## -------------------------------------------------------------- 
##  find running tasks (only for Windows)
## -------------------------------------------------------------- 
def getRunningTaskPID(taskname):
    tasks_psutil = []
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        try:
            tasks_psutil.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            logger.error(f"errors occurred while getting running tasks with psutil")
    taskPID = None
    for task in tasks_psutil:
        if taskname == task['name']:
            taskPID = task['pid']
            break
    return taskPID

def stopTask(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()  # 或使用 proc.kill() 強制終止
        proc.wait(timeout=3)
        logger.info(f"Process {pid} terminated.")
    except Exception as e:
        logger.errro(f"Failed to terminate process {pid}: {e}")

def restartTask(command):
    try:
        subprocess.Popen(command)
        #logger.info(f"{command} Task restarted.")
    except Exception as e:
        logger.error(f"Failed to restart task: {e}")

def stopDeCart(isService):
    decartPID = getRunningTaskPID('decart.exe')
    if isService:  ## decart is running as a service (2.7.x)
        ## NET STOP DeCart services if decart version is 2.7.x
        while True:
            try:
                stopcmd = ["NET", "STOP", "AIxMed DeCart"]
                stopdecart = subprocess.Popen(stopcmd, 
                                      stdout=subprocess.PIPE,   # capture standard output
                                      stderr=subprocess.PIPE,   # capture standard error
                                      text=True)
                '''
                #stdout, stderr = stopdecart.communicate()
                if stopdecart.returncode == 0:
                    logger.info('DeCart service temporarily stopped')
                else:
                    logger.warning(f'{stopdecart.returncode}: can not STOP DeCart service??')
                '''
            except Exception as e:
                logger.error(f'an error occurred: {str(e)}')
            # check process status
            decartSTOP = getRunningTaskPID('decart.exe')
            if decartSTOP:
                logger.error(f'DeCart is still running, pid: {decartSTOP}')
                time.sleep(15)
            else:
                logger.info('DeCart temporarily stopped')
                break
    else:   ## decart is running as a task (2.8.x)
        #decartPID = getRunningTaskPID('decart.exe')
        stopTask(decartPID)
        logger.info('DeCart service temporarily stopped')
        # check process status
        decartSTOP = getRunningTaskPID('decart.exe')
        if decartSTOP:
            logger.error(f'DeCart is still running, pid: {decartSTOP}')
        else:
            logger.info('DeCart temporarily stopped')

def restartDeCart(isService, decartexe):
    if isService:   ## decart is running as a service
        ## NET START DeCart services if decart version is 2.7.x
        while True:
            try:
                startcmd = ["NET", "START", "AIxMed DeCart"]
                startdecart = subprocess.Popen(startcmd, 
                                          stdout=subprocess.PIPE,   # capture standard output
                                          stderr=subprocess.PIPE,   # capture standard error
                                          text=True)
                '''
                #stdout, stderr = startdecart.communicate()
                if stopdecart.returncode == 0:
                    logger.info('DeCart service re-started')
                else:
                    logger.warning(f'{stopdecart.returncode}: can not re-start DeCart service')
                '''
            except Exception as e:
                logger.error(f'an error occurred: {str(e)}')
            ## check service
            decartPID = getRunningTaskPID('decart.exe')
            if decartPID:
                decart = psutil.Process(decartPID)
                logger.info(f'{decart.name()} (pid={decart.pid}) is {decart.status()} now')
                break
            else:
                ## not restart yet
                time.sleep(15)
    else:   ## decart is running as a task
        decartbin = [decartexe]
        logger.info('try restarting DeCart task')
        restartTask(decartbin)
        # check process status
        decartPID = getRunningTaskPID('decart.exe')
        if decartPID:
            decart_process = psutil.Process(decartPID)
            logger.info(f'DeCart is {decart_process.status()} now')
        else:
            logger.error('failed to re-start DeCart ')

## -------------------------------------------------------------- 
##  sample code from querying Copilot
## -------------------------------------------------------------- 
def get_running_tasks_summary():
    """综合显示运行中的任务"""
    print("=== psutil ===")
    tasks_psutil = []
    for proc in psutil.process_iter(['pid', 'name', 'username']):
        try:
            tasks_psutil.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    print(f"found {len(tasks_psutil)} running tasks processes")
    for task in tasks_psutil: #[:5]:  # 只显示前5个
        print(f"  PID: {task['pid']}, Task: {task['name']}")
    
    print("\n=== tasklist ===")
    try:
        result = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], 
                              capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        print(f"found {len(lines)} running tasks processes")
        #lines = result.stdout.strip().split('\n')[:5]  # 只显示前5个
        for line in lines:
            if line:
                parts = line.split('","')
                if len(parts) >= 2:
                    name = parts[0].replace('"', '')
                    pid = parts[1].replace('"', '')
                    print(f"  Task: {name} (PID: {pid})")
    except Exception as e:
        print(f"An error occurred while finding tasks with tasklist: {e}")

if __name__ == "__main__":
    get_running_tasks_summary()
