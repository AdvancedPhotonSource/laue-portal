var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

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
    const url = `/scan?id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the scan ID)
    );
};

dagcomponentfuncs.PeakIndexLinkRenderer = function (props) {
    // props.value will be the peakindex_id for the current row
    const url = `/indexedpeak?indexid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the peakindex ID)
    );
};

dagcomponentfuncs.ReconLinkRenderer = function (props) {
    // props.value will be the recon_id for the current row
    const url = `/reconstruction?reconid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the recon ID)
    );
};

dagcomponentfuncs.WireReconLinkRenderer = function (props) {
    // props.value will be the wirerecon_id for the current row
    const url = `/wire_reconstruction?wirereconid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the wirerecon ID)
    );
};

dagcomponentfuncs.JobIdLinkRenderer = function (props) {
    // props.value will be the job_id for the current row
    const url = `/job?id=${props.value}`;
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
                table_link = make_table_link('PeakIndex', `/indexedpeaks`)
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

//     const viewScanUrl = `/create-indexedpeaks?scan_id=${scanNumber}`; 
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
    let createIndexedPeaksUrl = `/create-indexedpeaks?scan_id=${scanNumber}`;
    if (reconParams) {
        createIndexedPeaksUrl += `&${reconParams}`;
    }

    // Determine reconstruction URL based on aperture
    let createReconstructionUrl = `/create-reconstruction?scan_id=${scanNumber}`;
    if (data.aperture.includes('wire')) {
        createReconstructionUrl = `/create-wire-reconstruction?scan_id=${scanNumber}`;
    }

    function handleIndexedPeaksClick() {
        window.location.href = createIndexedPeaksUrl;
    }

    function handleReconstructClick() {
        window.location.href = createReconstructionUrl;
    }

    return React.createElement('div', null, [
        React.createElement(
            window.dash_bootstrap_components.Button,
            {
                key: 'indexBtn-' + scanNumber,
                onClick: handleIndexedPeaksClick,
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
