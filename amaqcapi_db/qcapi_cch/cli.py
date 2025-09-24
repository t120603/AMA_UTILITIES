import argparse
import os, shutil
from .qcxmain import startQCAPI
#from .qcxfuncs import startMonitorFolders

def main():
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
