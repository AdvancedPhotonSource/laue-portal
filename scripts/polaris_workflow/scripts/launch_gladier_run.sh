EXPERIMENT_NAME=$1
FILE_NAME=$2

source /clhome/DMADMIN/DM/dm-support-4.1.7/CONDA/bin/activate /clhome/EPIX34ID/dev/env/laue-gladier

cd /clhome/EPIX34ID/dev/src/laue-gladier
python /clhome/EPIX34ID/dev/src/laue-gladier/laue_client/process_point.py ${EXPERIMENT_NAME} ${FILE_NAME}