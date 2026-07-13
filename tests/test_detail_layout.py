from dash import html

from laue_portal.components.detail_layout import detail_header, detail_header_content


def test_detail_header_uses_shared_container_class():
    header = detail_header("record-header")

    assert header.id == "record-header"
    assert header.className == "lp-detail-header"


def test_detail_header_content_builds_title_and_separated_links():
    content = detail_header_content(
        "Wire Reconstruction ID: 12",
        [("Job ID: 4", "/job?job_id=4"), ("Scan ID: 8", "/scan?scan_id=8")],
    )

    assert content[0].className == "lp-detail-title"
    assert content[0].children == "Wire Reconstruction ID: 12"
    assert content[1].className == "lp-detail-links"

    links = [child for child in content[1].children if isinstance(child, html.A)]
    separators = [child for child in content[1].children if isinstance(child, html.Span)]
    assert [(link.children, link.href) for link in links] == [
        ("Job ID: 4", "/job?job_id=4"),
        ("Scan ID: 8", "/scan?scan_id=8"),
    ]
    assert len(separators) == 1
    assert separators[0].className == "lp-detail-separator"


def test_detail_header_content_omits_empty_link_wrapper():
    content = detail_header_content("No record selected")

    assert len(content) == 1
    assert content[0].className == "lp-detail-title"
