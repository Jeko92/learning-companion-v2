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
        # Per section, (href, text pieces) for each element with an href in it.
        self.link_pieces = {section: [] for section in SECTIONS}
        # (depth in open_tags, text pieces) for elements with an href still open.
        self.open_links = []
        # Per section, (form attrs, [input attrs]) for each <form> inside it.
        self.section_forms = {section: [] for section in SECTIONS}
        # (depth in open_tags, input attrs list) for <form> elements still open.
        self.open_forms = []

    def text(self, section):
        return collapse(self.pieces[section])

    def href_text(self):
        return collapse(self.href_pieces)

    def links(self, section):
        """(href, text) for every element with an href inside the section."""
        return [(href, collapse(pieces)) for href, pieces in self.link_pieces[section]]

    def forms(self, section):
        """(form attrs, [input attrs]) for every <form> inside the section, with
        each <input> tied to the innermost form it sits in."""
        return [(attrs, list(inputs)) for attrs, inputs in self.section_forms[section]]

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        # <input> is void, so record it before the void-element return below.
        if tag == "input" and self.open_forms:
            self.open_forms[-1][1].append(attrs)
        if tag in VOID_ELEMENTS:
            return
        names = {name for name, _ in self.open_tags}
        if "href" in attrs:
            pieces = []
            for section in SECTIONS:
                if section in names:
                    self.link_pieces[section].append((attrs["href"], pieces))
            self.open_links.append((len(self.open_tags) + 1, pieces))
        if tag == "form":
            inputs = []
            for section in SECTIONS:
                if section in names:
                    self.section_forms[section].append((attrs, inputs))
            self.open_forms.append((len(self.open_tags) + 1, inputs))
        self.open_tags.append((tag, "href" in attrs))

    def handle_endtag(self, tag):
        names = [name for name, _ in self.open_tags]
        if tag in names:
            del self.open_tags[len(names) - 1 - names[::-1].index(tag) :]
            depth = len(self.open_tags)
            self.open_links = [(d, p) for d, p in self.open_links if d <= depth]
            self.open_forms = [(d, i) for d, i in self.open_forms if d <= depth]

    def handle_data(self, data):
        names = {name for name, _ in self.open_tags}
        for section in SECTIONS:
            if section in names:
                self.pieces[section].append(data)
        if any(has_href for _, has_href in self.open_tags):
            self.href_pieces.append(data)
        for _, pieces in self.open_links:
            pieces.append(data)
