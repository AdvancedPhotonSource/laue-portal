PYTHON_PATH=/data/laue34/env/laue_repack/bin/python
SCRIPT_PATH=/clhome/EPIX34ID/dev/src/laue-gladier/repackage/convert_laue_results.py
CWD=/data/laue34/logs

EXP_NAME=$1
FILE_PATH=$2

cd ${CWD}

qsub -b yes -cwd -q extra.q ${PYTHON_PATH} ${SCRIPT_PATH} ${EXP_NAME} ${FILE_PATH}