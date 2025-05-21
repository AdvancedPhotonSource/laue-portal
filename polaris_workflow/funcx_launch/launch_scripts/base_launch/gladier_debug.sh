NUM_NODES=2
RANKS_PER_NODE=32
INPUT_DIR=$1
OUTPUT_DIR=$2
START_IM=0

BASENAME=$(/usr/bin/basename ${INPUT_DIR})
PROJ_NAME=laue_aps_${INPUT_DIR}

AFFINITY_PATH=../runscripts/set_gpu_affinity.sh
CONFIG_PATH=/eagle/APSDataAnalysis/mprince/lau/dev/laue-gladier/funcx_launch/launch_scripts/config_gladier_debug.yml
PYTHONPATH=/eagle/projects/APSDataAnalysis/mprince/lau_env_polaris/bin/python
CWD=/eagle/APSDataAnalysis/mprince/lau/dev/laue-parallel/logs_gladier


cd ${CWD}

echo "
cd \${PBS_O_WORKDIR}

# MPI and OpenMP settings
NNODES=\`wc -l < \$PBS_NODEFILE\`
NRANKS_PER_NODE=${RANKS_PER_NODE}
NDEPTH=2
NTHREADS=2

NTOTRANKS=\$(( NNODES * NRANKS_PER_NODE ))
echo \"NUM_OF_NODES= \${NNODES} TOTAL_NUM_RANKS= \${NTOTRANKS} RANKS_PER_NODE= \${NRANKS_PER_NODE} THREADS_PER_RANK= \${NTHREADS}\"

mpiexec -n \${NTOTRANKS} --ppn \${NRANKS_PER_NODE} --depth=\${NDEPTH} --cpu-bind depth --env NNODES=\${NNODES}  --env OMP_NUM_THREADS=\${NTHREADS} -env OMP_PLACES=threads \\
    ${AFFINITY_PATH} \\
    ${PYTHONPATH} \\
    ../laue_parallel.py \\
    ${CONFIG_PATH} \\
    --override_input ${INPUT_DIR} \\
    --override_output ${OUTPUT_DIR} \\
    --start_im ${START_IM} \\
    --prod_output

" | \
qsub -A APSDataAnalysis \
-q debug \
-l select=${NUM_NODES}:system=polaris \
-l walltime=0:40:00 \
-l filesystems=home:eagle \
-l place=scatter \
-N ${PROJ_NAME} \
-W block=true 