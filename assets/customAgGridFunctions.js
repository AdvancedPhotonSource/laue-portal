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
    const url = `/scan?scan_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value // This will be the text of the link (the scan ID)
    );
};

dagcomponentfuncs.ScanSourceLinkRenderer = function (props) {
    const scanNumber = props.data.scan_number;
    if (scanNumber == null) {
        return React.createElement('span', { className: 'text-muted' }, 'Unlinked');
    }
    return React.createElement(
        'a',
        { href: `/scan?scan_id=${scanNumber}` },
        `SN${scanNumber}`
    );
};

dagcomponentfuncs.IndexingLinkRenderer = function (props) {
    const url = `/peakindexing?indexing_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        'I' + props.value
    );
};

dagcomponentfuncs.ReconstructionLinkRenderer = function (props) {
    if (props.value == null) {
        return React.createElement('span', { className: 'text-muted' }, 'Direct');
    }
    const method = props.data && (props.data.method || props.data.reconstruction_method);
    const page = method === 'wire' ? '/wire_reconstruction' : '/reconstruction';
    const url = `${page}?reconstruction_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        'R' + props.value
    );
};

dagcomponentfuncs.SourceLinksRenderer = function (props) {
    const data = props.data;
    const elements = [];

    if (data.scan_number != null) {
        if (elements.length > 0) elements.push(' \u00A0');
        elements.push(
            React.createElement('a', {
                key: 'sn',
                href: '/scan?scan_id=' + data.scan_number
            }, 'SN' + data.scan_number)
        );
    }

    if (data.reconstruction_id != null) {
        if (elements.length > 0) elements.push(' \u00A0');
        const page = data.reconstruction_method === 'wire' ? '/wire_reconstruction' : '/reconstruction';
        elements.push(
            React.createElement('a', {
                key: 'reconstruction',
                href: page + '?reconstruction_id=' + data.reconstruction_id
            }, 'R' + data.reconstruction_id)
        );
    }

    if (elements.length === 0) {
        return React.createElement('span', { className: 'text-muted' }, 'Unlinked');
    }

    return React.createElement('span', null, elements);
};

dagcomponentfuncs.JobIdLinkRenderer = function (props) {
    const url = `/job?job_id=${props.value}`;
    return React.createElement(
        'a',
        { href: url },
        props.value
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
            else if (field_key === 'reconstruction_id') {
                id_link = dagcomponentfuncs.ReconstructionLinkRenderer({ value: value, data: data });
                table_link = make_table_link('Reconstruction', `/reconstructions`)
            }
            else if (field_key === 'indexing_id') {
                id_link = dagcomponentfuncs.IndexingLinkRenderer({ value: value });
                table_link = make_table_link('Indexing', `/peakindexings`)
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
    const progressText = props.value === 1 && props.data && props.data.status_progress ? ` ${props.data.status_progress}` : '';
    const isCancelled = props.value === 4;
    
    // Create a Bootstrap badge
    return React.createElement(
        window.dash_bootstrap_components.Badge,
        {
            color: statusInfo.color,
            className: isCancelled ? '' : 'text-white',
            style: isCancelled ? {
                backgroundColor: 'var(--bs-gray-200)',
                border: '1px solid var(--bs-gray-400)',
                color: 'var(--bs-gray-700)'
            } : undefined
        },
        statusInfo.text + progressText
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

// Scan import status renderer for bulk upload page
dagcomponentfuncs.ScanImportStatusRenderer = function (props) {
    const statusMapping = {
        'new':      { text: 'New',      color: 'success' },
        'exists':   { text: 'Exists',   color: 'warning' },
        'imported': { text: 'Imported', color: 'info' },
        'failed':   { text: 'Failed',   color: 'danger' },
        'skipped':  { text: 'Skipped',  color: 'secondary' },
        'duplicate': { text: 'Duplicate', color: 'secondary' },
        'invalid':   { text: 'Invalid',   color: 'danger' },
    };

    const key = (props.value || '').toLowerCase();
    const info = statusMapping[key] || { text: props.value || '', color: 'secondary' };

    return React.createElement(
        window.dash_bootstrap_components.Badge,
        { color: info.color, className: 'text-white' },
        info.text
    );
};
