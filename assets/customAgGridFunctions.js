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
