import time
import sys
import logging
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
import subprocess

def monitor_directory(path):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', 
                        filename='transfer.log')
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            sar_output = subprocess.check_output(['sar', '1', '1'])
            logging.info('System activity: %s', sar_output)

            netstat_output = subprocess.check_output(['netstat', '-s'])
            logging.info('Network activity: %s', sar_output)
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    monitor_directory(sys.argv[1])