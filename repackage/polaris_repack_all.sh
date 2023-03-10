NUM_NODES=1
RANKS_PER_NODE=10
PROJ_NAME=laue-repack
QUEUE=debug

PYTHONPATH=/eagle/projects/APSDataAnalysis/mprince/lau_env_polaris/bin/python
CWD=/eagle/APSDataAnalysis/mprince/lau/dev/laue-gladier
SCRIPT_PATH=/eagle/APSDataAnalysis/mprince/lau/dev/laue-gladier/repackage/repack_polaris.py


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
    ${PYTHONPATH} ${SCRIPT_PATH} $@ 

" | \
qsub -A APSDataAnalysis \
-q ${QUEUE} \
-l select=${NUM_NODES}:system=polaris \
-l walltime=0:30:00 \
-l filesystems=home:eagle \
-l place=scatter \
-N ${PROJ_NAME} \