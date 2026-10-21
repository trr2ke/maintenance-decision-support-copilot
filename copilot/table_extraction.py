"""Copy explicit Markdown threshold/status rows without model summarization."""
import re


def _cells(line):
    line = line.strip()
    if "|" not in line:
        return []
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line)]


def extract_table_triples(content):
    """Return verbatim, grounded relationships from two-column status tables.

    A fragment without its header is deliberately not interpreted. Callers must
    preserve complete tables when chunking. Cells outside the graph's length
    limits are not truncated; the original source remains the authority.
    """
    lines = content.splitlines(keepends=True)
    triples = []
    for index in range(len(lines) - 2):
        headers = _cells(lines[index])
        divider = _cells(lines[index + 1])
        if len(headers) != 2 or len(divider) != 2:
            continue
        if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in divider):
            continue
        labels = [cell.strip("*_` ").casefold() for cell in headers]
        if labels.count("status") != 1:
            continue
        status_column = labels.index("status")
        metric_column = 1 - status_column
        metric = headers[metric_column]
        if not metric or len(metric) > 180:
            continue
        for row_index in range(index + 2, len(lines)):
            cells = _cells(lines[row_index])
            if len(cells) != 2:
                break
            condition, status = cells[metric_column], cells[status_column]
            if (not re.search(r"\d", condition) or not status
                    or len(condition) > 180 or len(status) > 180):
                continue
            row = lines[row_index].strip()
            if len(row) <= 500:
                triples.append({"subject": condition, "predicate": "INDICATES",
                                "object": status, "evidence": row})
            # Retain a contiguous quotation: never splice a header onto a row.
            context = "".join(lines[index:row_index + 1]).strip()
            if len(context) <= 500:
                triples.append({"subject": metric, "predicate": "HAS_THRESHOLD",
                                "object": condition, "evidence": context})
    return triples
