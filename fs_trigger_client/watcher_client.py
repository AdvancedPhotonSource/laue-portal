#!/usr/bin/env python

import os
import argparse

from tools.folder_watch import FileTrigger
from full_client import run_flow
# Arg Parsing
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('localdir', type=str, default='.')
    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()
    local_dir = os.path.expanduser(args.localdir)

    ##Creates and starts the watcher
    exp = FileTrigger(local_dir, ClientLogic=run_flow)
    exp.run()





