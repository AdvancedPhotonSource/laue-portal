from collections.abc import Iterable

from dash import html


def detail_header(header_id):
    """Return the shared container used at the top of record-detail pages."""
    return html.Div(id=header_id, className="lp-detail-header")


def detail_header_content(title: str, links: Iterable[tuple[str, str]] = ()):
    """Build a detail title followed by consistently separated related links."""
    link_items = list(links)
    children = [html.Span(title, className="lp-detail-title")]

    if link_items:
        link_children = []
        for index, (label, href) in enumerate(link_items):
            if index:
                link_children.append(html.Span("|", className="lp-detail-separator"))
            link_children.append(html.A(label, href=href))
        children.append(html.Span(link_children, className="lp-detail-links"))

    return children
