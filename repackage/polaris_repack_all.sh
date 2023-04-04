NUM_NODES=1
RANKS_PER_NODE=11
PROJ_NAME=laue-repack
QUEUE=preemptable
WALLTIME=05:00:00

PYTHONPATH=/home/aps34ide/laue_env/bin/python
CWD=/home/aps34ide/laue_src/logs_repack
SCRIPT_PATH=/home/aps34ide/laue_src/laue-gladier/repackage/repack_polaris.py


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
qsub -A 9169 \
-q ${QUEUE} \
-l select=${NUM_NODES}:system=polaris \
-l walltime=${WALLTIME} \
-l filesystems=home:eagle \
-l place=scatter \
-N ${PROJ_NAME} \
