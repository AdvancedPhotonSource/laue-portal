PYTHON_PATH=/data/laue34/env/laue_repack/bin/python
SCRIPT_PATH=/clhome/EPIX34ID/dev/src/laue-gladier/repackage/convert_laue_results.py
CWD=/data/laue34/logs


source ~/.bashrc

EXP_NAME=$1
FILE_PATH=$2
BASENAME=$(/usr/bin/basename ${FILE_PATH})

cd ${CWD}

/clhome/aps_tools/gridengine/bin/lx-amd64/qsub -b yes -cwd -N ${BASENAME} -q extra.q ${PYTHON_PATH} ${SCRIPT_PATH} ${EXP_NAME} ${FILE_PATH}