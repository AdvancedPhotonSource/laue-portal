DATA_DIR=/data34a/Run2023-1/TestPolarisFlyScan

source /home/dm/etc/dm.setup.sh

dm-start-daq --experiment=laue_test --data-directory=${DATA_DIR} --workflow-name=Process_Laue_Point --workflow-owner=epix34id --duration 1d

dm-start-daq --experiment=laue_test --data-directory=/clhome/EPIX34ID/dev/src/experiment_staging --workflow-name=Process_Laue_Point --workflow-owner=epix34id --duration 1d

dm-get-processing-job --id 6846d89a-cdd1-4019-8a0a-5dd7c672b744 --display-keys ALL --display-format pprint