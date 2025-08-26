var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

// Custom renderer for expand/collapse functionality
dagcomponentfuncs.ExpandCollapseRenderer = function (params) {
    // Check if we have the required data
    if (!params || !params.data) {
        return null;
    }
    
    // Only show expand/collapse for job rows that have subjobs
    if (params.data.row_type === 'job' && params.data.total_subjobs > 0) {
        const jobId = params.data.job_id;
        const jobNode = params.node;
        
        // Store expanded state and auto-expansion tracking in global objects
        if (!window.expandedJobs) {
            window.expandedJobs = {};
        }
        if (!window.autoExpandedJobs) {
            window.autoExpandedJobs = {};
        }
        if (!window.manuallyCollapsedJobs) {
            window.manuallyCollapsedJobs = {};
        }
        
        // Handle auto-expansion on initial render
        if (params.data._should_auto_expand && 
            !window.expandedJobs.hasOwnProperty(jobId) && 
            !window.manuallyCollapsedJobs[jobId]) {
            // Auto-expand this job
            window.expandedJobs[jobId] = true;
            window.autoExpandedJobs[jobId] = true;
            
            // Trigger expansion after a short delay to ensure grid is ready
            setTimeout(() => {
                const subjobs = params.data._subjobs || [];
                if (subjobs.length > 0) {
                    // Find the index of this job row
                    let jobIndex = -1;
                    const allRows = [];
                    params.api.forEachNode((node, index) => {
                        allRows.push(node.data);
                        if (node.data.job_id === jobId) {
                            jobIndex = index;
                        }
                    });
                    
                    // Insert subjobs after the job row
                    if (jobIndex !== -1) {
                        const newRows = [
                            ...allRows.slice(0, jobIndex + 1),
                            ...subjobs,
                            ...allRows.slice(jobIndex + 1)
                        ];
                        params.api.setRowData(newRows);
                    }
                }
            }, 100);
        }
        
        // Handle auto-collapse when no longer running
        if (!params.data._should_auto_expand && 
            window.expandedJobs[jobId] && 
            window.autoExpandedJobs[jobId] &&
            !window.manuallyCollapsedJobs[jobId]) {
            // Auto-collapse this job
            window.expandedJobs[jobId] = false;
            delete window.autoExpandedJobs[jobId];
            
            // Trigger collapse
            setTimeout(() => {
                const filteredRows = [];
                params.api.forEachNode(node => {
                    if (node.data) {
                        // Keep all job rows and subjobs that don't belong to this job
                        if (node.data.row_type === 'job' || 
                            (node.data.row_type === 'subjob' && node.data.parent_job_id !== jobId)) {
                            filteredRows.push(node.data);
                        }
                    }
                });
                params.api.setRowData(filteredRows);
            }, 100);
        }
        
        const handleClick = (e) => {
            e.stopPropagation();
            
            // Toggle expanded state
            const isExpanded = window.expandedJobs[jobId] || false;
            window.expandedJobs[jobId] = !isExpanded;
            
            // Track manual interactions
            if (!isExpanded) {
                // User is manually expanding
                delete window.manuallyCollapsedJobs[jobId];
                if (window.autoExpandedJobs[jobId]) {
                    // User manually expanded an auto-expanded job, keep it as auto-expanded
                    window.autoExpandedJobs[jobId] = true;
                }
            } else {
                // User is manually collapsing
                if (window.autoExpandedJobs[jobId]) {
                    // User manually collapsed an auto-expanded job
                    window.manuallyCollapsedJobs[jobId] = true;
                    delete window.autoExpandedJobs[jobId];
                }
            }
            
            if (!isExpanded) {
                // Expanding - add subjobs
                const subjobs = params.data._subjobs || [];
                if (subjobs.length > 0) {
                    // Find the index of this job row
                    let jobIndex = -1;
                    const allRows = [];
                    params.api.forEachNode((node, index) => {
                        allRows.push(node.data);
                        if (node.data.job_id === jobId) {
                            jobIndex = index;
                        }
                    });
                    
                    // Insert subjobs after the job row
                    if (jobIndex !== -1) {
                        const newRows = [
                            ...allRows.slice(0, jobIndex + 1),
                            ...subjobs,
                            ...allRows.slice(jobIndex + 1)
                        ];
                        params.api.setRowData(newRows);
                    }
                }
            } else {
                // Collapsing - remove subjobs
                const filteredRows = [];
                params.api.forEachNode(node => {
                    if (node.data) {
                        // Keep all job rows and subjobs that don't belong to this job
                        if (node.data.row_type === 'job' || 
                            (node.data.row_type === 'subjob' && node.data.parent_job_id !== jobId)) {
                            filteredRows.push(node.data);
                        }
                    }
                });
                params.api.setRowData(filteredRows);
            }
            
            // Force re-render of this cell
            params.api.refreshCells({
                force: true,
                columns: ['expand']
            });
        };
        
        const isExpanded = window.expandedJobs[jobId] || false;
        
        return React.createElement(
            'button',
            {
                onClick: handleClick,
                style: {
                    border: 'none',
                    background: 'none',
                    cursor: 'pointer',
                    fontSize: '12px',
                    padding: '4px',
                    width: '100%',
                    outline: 'none'
                }
            },
            isExpanded ? '▼' : '▶'
        );
    }
    
    // Return null for subjob rows or jobs without subjobs
    return null;
};

// Date formatter for displaying datetime values in human-readable format
dagcomponentfuncs.DateFormatter = function (params) {
    if (!params.value) return '';
    
    // Parse the date string
    const date = new Date(params.value);
    
    // Check if date is valid
    if (isNaN(date.getTime())) return params.value;
    
    // Format the date as YYYY-MM-DD HH:MM:SS using toLocaleString
    const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    };
    
    // Use en-CA locale which gives YYYY-MM-DD format
    return date.toLocaleString('en-CA', options);
};

dagcomponentfuncs.ScanLinkRenderer = function (props) {
    // props.value will be the scanNumber for the current row
    const url = `/scan?scan_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the scan ID)
    );
};

dagcomponentfuncs.PeakIndexLinkRenderer = function (props) {
    // props.value will be the peakindex_id for the current row
    const url = `/peakindexing?peakindex_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the peakindex ID)
    );
};

dagcomponentfuncs.ReconLinkRenderer = function (props) {
    // props.value will be the recon_id for the current row
    const url = `/reconstruction?recon_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the recon ID)
    );
};

dagcomponentfuncs.WireReconLinkRenderer = function (props) {
    // props.value will be the wirerecon_id for the current row
    const url = `/wire_reconstruction?wirerecon_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the wirerecon ID)
    );
};

dagcomponentfuncs.JobIdLinkRenderer = function (props) {
    // When used as innerRenderer in group cell, props.value contains the grouped value
    // When used as regular cell renderer, props.value is the cell value
    
    // Check if this is a group row (has children)
    if (props.node && props.node.group) {
        // This is a group row (job row)
        // Extract job_id from the grouped value
        const jobId = props.value || props.node.key;
        const url = `/job?job_id=${jobId}`;
        return React.createElement(
            'a',
            { href: url },
            jobId // This will be the text of the link (the job ID)
        );
    }
    
    // For leaf rows (subjob rows) or when data is available
    if (props.data && props.data.row_type === 'subjob') {
        // For subjob rows, just return the plain value
        return props.value;
    }
    
    // Default case - render as link
    const url = `/job?job_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the job ID)
    );
};

dagcomponentfuncs.JobRefsRenderer = function (props) {
    const field_keys = props.value; // Array of field names from valueGetter
    const data = props.data; // Row data
    let job_refs = [];
    
    function make_table_link(text, url) {
        return React.createElement(
            'a',
            { href: url },
            text // This will be the text of the link (the table)
        );
    };

    // Iterate through the field names and get their values
    for (const field_key of field_keys) {
        const value = data[field_key];
        if (value !== null && value !== undefined) {
            let id_link;
            let table_link;
            
            if (field_key === 'calib_id') {
                id_link = value;
                table_link = 'Calib' //temp
            }
            else if (field_key === 'recon_id') {
                id_link = dagcomponentfuncs.ReconLinkRenderer({ value: value });
                table_link = make_table_link('Recon', `/reconstructions`)
            }
            else if (field_key === 'wirerecon_id') {
                id_link = dagcomponentfuncs.WireReconLinkRenderer({ value: value });
                table_link = make_table_link('WireRecon', `/wire-reconstructions`)
            }
            else if (field_key === 'peakindex_id') {
                id_link = dagcomponentfuncs.PeakIndexLinkRenderer({ value: value });
                table_link = make_table_link('Peak Indexing', `/peakindexings`)
            }
            
            job_refs.push(table_link, `: `, id_link);
        }
    }
    
    // Return a span element containing all the job references
    return React.createElement('span', null, job_refs);
};

dagcomponentfuncs.StatusRenderer = function (props) {
    // Status mapping
    const statusMapping = {
        0: { text: "Queued", color: "warning" },
        1: { text: "Running", color: "info" },
        2: { text: "Finished", color: "success" },
        3: { text: "Failed", color: "danger" },
        4: { text: "Cancelled", color: "secondary" }
    };
    
    const statusInfo = statusMapping[props.value] || { text: `Unknown (${props.value})`, color: "secondary" };
    
    // Create a Bootstrap badge
    return React.createElement(
        window.dash_bootstrap_components.Badge,
        {
            color: statusInfo.color,
            className: 'text-white'
        },
        statusInfo.text
    );
};

// SubJob Progress Renderer - shows completion status with text and progress bar
dagcomponentfuncs.SubJobProgressRenderer = function (props) {
    const data = props.data;
    const total = data.total_subjobs || 0;
    
    if (total === 0) {
        return React.createElement('span', { className: 'text-muted' }, 'No subjobs');
    }
    
    const completed = data.completed_subjobs || 0;
    const failed = data.failed_subjobs || 0;
    const running = data.running_subjobs || 0;
    const queued = data.queued_subjobs || 0;
    
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    
    // Create progress bar with different segments
    const progressSegments = [];
    
    if (completed > 0) {
        progressSegments.push(
            React.createElement('div', {
                key: 'completed',
                className: 'progress-bar bg-success',
                style: { width: `${(completed / total) * 100}%` },
                title: `${completed} completed`
            })
        );
    }
    
    if (failed > 0) {
        progressSegments.push(
            React.createElement('div', {
                key: 'failed',
                className: 'progress-bar bg-danger',
                style: { width: `${(failed / total) * 100}%` },
                title: `${failed} failed`
            })
        );
    }
    
    if (running > 0) {
        progressSegments.push(
            React.createElement('div', {
                key: 'running',
                className: 'progress-bar bg-info progress-bar-striped progress-bar-animated',
                style: { width: `${(running / total) * 100}%` },
                title: `${running} running`
            })
        );
    }
    
    if (queued > 0) {
        progressSegments.push(
            React.createElement('div', {
                key: 'queued',
                className: 'progress-bar bg-warning',
                style: { width: `${(queued / total) * 100}%` },
                title: `${queued} queued`
            })
        );
    }
    
    return React.createElement('div', { style: { width: '100%' } }, [
        React.createElement('div', { 
            key: 'text',
            className: 'text-center small mb-1' 
        }, `${completed}/${total} completed`),
        React.createElement('div', {
            key: 'progress',
            className: 'progress',
            style: { height: '20px' }
        }, progressSegments)
    ]);
};

// SubJob Detail Renderer - renders the detail grid for subjobs
dagcomponentfuncs.SubJobDetailRenderer = function (props) {
    const subjobs = props.data.subjobs || [];
    
    if (subjobs.length === 0) {
        return React.createElement('div', { 
            className: 'text-center text-muted p-3' 
        }, 'No subjobs for this job');
    }
    
    // Create a new grid for the subjobs
    const detailGridOptions = props.detailGridOptions || {};
    detailGridOptions.rowData = subjobs;
    
    // Create container for the detail grid
    const eDetailGrid = document.createElement('div');
    eDetailGrid.style.height = '100%';
    eDetailGrid.style.width = '100%';
    eDetailGrid.className = 'ag-theme-alpine';
    
    // Initialize the detail grid
    setTimeout(() => {
        new agGrid.Grid(eDetailGrid, detailGridOptions);
    }, 0);
    
    return eDetailGrid;
};

// dagcomponentfuncs.ActionButtonsRenderer = function (props) {
//     const { data } = props; // data contains the row data

//     // Ensure scanNumber is available from row data
//     const scanNumber = data.scanNumber;
//     if (scanNumber === undefined || scanNumber === null) {
//         console.error("scanNumber is missing in row data for ActionButtonsRenderer", data);
//         return null; // Or return an empty span or placeholder
//     }

//     const viewScanUrl = `/create-peakindexing?scan_id=${scanNumber}`;
//     const viewReconstructionUrl = `/view_reconstruction?scan_id=${scanNumber}`;

//     function handleScanClick() {
//         window.location.href = viewScanUrl;
//     }

//     function handleReconstructClick() {
//         window.location.href = viewReconstructionUrl;
//     }

//     return React.createElement('div', null, [
//         React.createElement(
//             window.dash_bootstrap_components.Button,
//             {
//                 key: 'indexBtn-' + scanNumber,
//                 onClick: handleScanClick,
//                 color: 'primary', 
//                 size: 'sm',
//                 style: { marginRight: '5px' }
//             },
//             'Index'
//         ),
//         React.createElement(
//             window.dash_bootstrap_components.Button,
//             {
//                 key: 'reconstructBtn-' + scanNumber,
//                 onClick: handleReconstructClick,
//                 color: 'primary', 
//                 size: 'sm'
//             },
//             'Reconstruct'
//         )
//     ]);
// };

dagcomponentfuncs.ActionButtonsRenderer = function (props) {
    const { data } = props; // data contains the row data

    // Ensure scanNumber is available from row data
    const scanNumber = data.scanNumber;
    if (scanNumber === undefined || scanNumber === null) {
        console.error("scanNumber is missing in row data for ActionButtonsRenderer", data);
        return null; // Or return an empty span or placeholder
    }

    // Find all fields in data that include "recon_id"
    const reconFields = Object.keys(data).filter(key => key.includes("recon_id"));
    const reconParams = reconFields
        .map(key => `${key}=${encodeURIComponent(data[key])}`)
        .join("&");

    // Construct URL with optional recon_id-related fields
    let createPeakIndexingUrl = `/create-peakindexing?scan_id=${scanNumber}`;
    if (reconParams) {
        createPeakIndexingUrl += `&${reconParams}`;
    }

    // Determine reconstruction URL based on aperture
    let createReconstructionUrl = `/create-reconstruction?scan_id=${scanNumber}`;
    if (data.aperture.includes('wire')) {
        createReconstructionUrl = `/create-wire-reconstruction?scan_id=${scanNumber}`;
    }
    if (reconParams) {
        createReconstructionUrl += `&${reconParams}`;
    }

    function handlePeakIndexingClick() {
        window.location.href = createPeakIndexingUrl;
    }

    function handleReconstructClick() {
        window.location.href = createReconstructionUrl;
    }

    return React.createElement('div', null, [
        React.createElement(
            window.dash_bootstrap_components.Button,
            {
                key: 'indexBtn-' + scanNumber,
                onClick: handlePeakIndexingClick,
                color: 'primary', 
                size: 'sm',
                style: { marginRight: '5px' }
            },
            'Index'
        ),
        React.createElement(
            window.dash_bootstrap_components.Button,
            {
                key: 'reconstructBtn-' + scanNumber,
                onClick: handleReconstructClick,
                color: 'primary', 
                size: 'sm'
            },
            'Reconstruct'
        )
    ]);
};
