var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

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
        props.value // This will be the text of the link (the peakindex_id)
    );
};

dagcomponentfuncs.ReconLinkRenderer = function (props) {
    // props.value will be the peakindex_id for the current row
    const url = `/reconstruction?reconid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the peakindex_id)
    );
};

dagcomponentfuncs.WireReconLinkRenderer = function (props) {
    // props.value will be the peakindex_id for the current row
    const url = `/wire_reconstruction?wirereconid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the peakindex_id)
    );
};

dagcomponentfuncs.DatasetIdScanLinkRenderer = function (props) {
    // props.value will be the dataset_id for the current row
    const url = `/scan?id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the dataset_id)
    );
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