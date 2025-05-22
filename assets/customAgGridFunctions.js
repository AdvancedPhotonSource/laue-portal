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

dagcomponentfuncs.DatasetIdScanLinkRenderer = function (props) {
    // props.value will be the dataset_id for the current row
    const url = `/scan?scanid=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the dataset_id)
    );
};

dagcomponentfuncs.ActionButtonsRenderer = function (props) {
    const { data } = props; // data contains the row data

    // Ensure scanNumber is available from row data
    const scanNumber = data.scanNumber;
    if (scanNumber === undefined || scanNumber === null) {
        console.error("scanNumber is missing in row data for ActionButtonsRenderer", data);
        return null; // Or return an empty span or placeholder
    }

    const viewScanUrl = `/view_scan?id=${scanNumber}`; 
    const viewReconstructionUrl = `/view_reconstruction?scan_id=${scanNumber}`;

    function handleScanClick() {
        window.location.href = viewScanUrl;
    }

    function handleReconstructClick() {
        window.location.href = viewReconstructionUrl;
    }

    return React.createElement('div', null, [
        React.createElement(
            window.dash_bootstrap_components.Button,
            {
                key: 'scanBtn-' + scanNumber,
                onClick: handleScanClick,
                color: 'primary', 
                size: 'sm',
                style: { marginRight: '5px' }
            },
            'Scan'
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
