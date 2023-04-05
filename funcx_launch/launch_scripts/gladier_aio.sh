NUM_NODES=1
RANKS_PER_NODE=32
INPUT_DIR=$1
OUTPUT_DIR=$2
START_IM=0

BASENAME=$(/usr/bin/basename ${INPUT_DIR})
POINT_NAME=$(/usr/bin/basename ${INPUT_DIR} .h5)
PROJ_NAME=laue_test_${POINT_NAME}

AFFINITY_PATH=../runscripts/set_soft_affinity.sh
CONFIG_PATH=/home/aps34ide/laue_src/laue-gladier/funcx_launch/launch_scripts/config_gladier.yml
CONDA_PATH=/home/aps34ide/laue_env
CWD=/home/aps34ide/laue_src/laue-parallel/logs_gladier

REPACK_SCRIPT=/home/aps34ide/laue_src/laue-gladier/repackage/repack_polaris.py
REPACK_INPUT="$(/usr/bin/dirname "${OUTPUT_DIR}")"
REPACK_DIR=/eagle/APSDataProcessing/aps34ide/repacks/aio_out

cd ${CWD}

echo "
cd \${PBS_O_WORKDIR}

module load conda
conda activate ${CONDA_PATH}

# MPI and OpenMP settings
NNODES=\`wc -l < \$PBS_NODEFILE\`
NRANKS_PER_NODE=${RANKS_PER_NODE}
NDEPTH=2
NTHREADS=2

NTOTRANKS=\$(( NNODES * NRANKS_PER_NODE ))
echo \"NUM_OF_NODES= \${NNODES} TOTAL_NUM_RANKS= \${NTOTRANKS} RANKS_PER_NODE= \${NRANKS_PER_NODE} THREADS_PER_RANK= \${NTHREADS}\"

mpiexec -n \${NTOTRANKS} --ppn \${NRANKS_PER_NODE} --depth=\${NDEPTH} --cpu-bind depth --env NNODES=\${NNODES}  --env OMP_NUM_THREADS=\${NTHREADS} -env OMP_PLACES=threads \\
    ${AFFINITY_PATH} \\
    python \\
    ../laue_parallel.py \\
    ${CONFIG_PATH} \\
    --override_input ${INPUT_DIR} \\
    --override_output ${OUTPUT_DIR} \\
    --start_im ${START_IM} \\
    --no_load_balance \\
    --prod_output


mpiexec -n 1 --ppn 1 --depth=\${NDEPTH} --cpu-bind depth --env NNODES=\${NNODES}  --env OMP_NUM_THREADS=\${NTHREADS} -env OMP_PLACES=threads \\
    python ${REPACK_SCRIPT} ${REPACK_INPUT} ${REPACK_DIR} --p ${POINT_NAME}

" | \
qsub -A 9169 \
-q debug \
-l select=${NUM_NODES}:system=polaris \
-l walltime=01:00:00 \
-l filesystems=home:eagle \
-l place=scatter \
-N ${PROJ_NAME} \
-W block=true 
