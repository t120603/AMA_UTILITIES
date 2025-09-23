import argparse
import os, shutil
from .watchwsi import startMonitorFolders

def watchwsi():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--config", default=None)
    parser.add_argument("-l", "--logfname", default=None)
    args = parser.parse_args()

    # copy config file to %LOCALAPPDATA%
    folder = os.path.join(os.getenv('LOCALAPPDATA'), 'ama_qcapi')
    if os.path.exists(folder) == False:
        os.makedirs(folder)
    if args.config:
        config = os.path.join(folder, 'config-watchwsi.json')
        shutil.copy(args.config, config)
        print(f'[INFO] copied {args.config} to {config}')
    fname = 'watchwsi-debug.log' if not args.logfname else args.logfname
    logfile = os.path.join(folder, fname)
    print(f'[INFO] logfile is {logfile}')
    startMonitorFolders(args.config, logfile)
