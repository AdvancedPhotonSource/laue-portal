EXPERIMENT_NAME=laue_test
DATA_DIR=/clhome/EPIX34ID/dev/src/experiment_staging

source /home/dm/etc/dm.setup.sh

dm-add-experiment --experiment=${EXPERIMENT_NAME} --type=XMD
dm-update-experiment --users d322808,d313944 --id

dm-start-experiment --experiment=${EXPERIMENT_NAME}
dm-start-daq --experiment=${EXPERIMENT_NAME} --data-directory=${DATA_DIR} \
--workflow-name=Process_Laue_Point --workflow-owner=epix34id 

read -p "Press enter to end experiment"

dm-stop-daq --experiment=${EXPERIMENT_NAME} --data-directory=${DATA_DIR}
dm-stop-experiment --experiment=${EXPERIMENT_NAME}

read -p "Press enter to delete experiment"

dm-delete-experiment --experiment=${EXPERIMENT_NAME}
