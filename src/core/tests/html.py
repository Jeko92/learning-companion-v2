"""HTML helpers shared by the apps' page tests.

Not a test module (no test_ prefix), so the runner doesn't collect it.
"""

from html.parser import HTMLParser

# HTML void elements never get an end tag, so they must not stay on the open stack.
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SECTIONS = ("title", "header", "nav", "main", "footer")


def collapse(pieces):
    """Joins text pieces with a space and collapses whitespace, so template
    formatting can't change a check and text from adjacent elements isn't
    glued together."""
    return " ".join(" ".join(pieces).split())


class PageParser(HTMLParser):
    """Collects the text inside each of SECTIONS, the text inside any element
    with an href, and every start tag with its attributes, so tests check
    structure, not just that a string appears somewhere on the page."""

    def __init__(self):
        super().__init__()
        self.open_tags = []
        self.pieces = {section: [] for section in SECTIONS}
        self.href_pieces = []
        # (tag, {attribute: value}) for every start tag, in document order.
        self.elements = []

    def text(self, section):
        return collapse(self.pieces[section])

    def href_text(self):
        return collapse(self.href_pieces)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        if tag not in VOID_ELEMENTS:
            has_href = any(name == "href" for name, _ in attrs)
            self.open_tags.append((tag, has_href))

    def handle_endtag(self, tag):
        names = [name for name, _ in self.open_tags]
        if tag in names:
            del self.open_tags[len(names) - 1 - names[::-1].index(tag) :]

    def handle_data(self, data):
        names = {name for name, _ in self.open_tags}
        for section in SECTIONS:
            if section in names:
                self.pieces[section].append(data)
        if any(has_href for _, has_href in self.open_tags):
            self.href_pieces.append(data)
