"""PyMuPDF-based PDF text extraction with font metadata."""

import logging

from config import ExtractionConfig
from constants import PYMUPDF_BOLD_BIT, PYMUPDF_ITALIC_BIT

logger = logging.getLogger(__name__)


def _extract_spans(line):
    """Extract non-empty spans with font metadata from a PDF line object."""
    return [
        {
            'text': s['text'],
            'bold': bool(s['flags'] & PYMUPDF_BOLD_BIT),
            'italic': bool(s['flags'] & PYMUPDF_ITALIC_BIT),
            'size': s['size'],
            'font': s['font'],
        }
        for s in line['spans']
        if s['text'].strip()
    ]


def _merge_span_groups(groups):
    """Merge grouped span lists into final line data objects."""
    groups.sort(key=lambda g: (0 if g[3] else 1, g[0], g[1]))

    lines_data = []
    for min_y, min_x, spans_list, _is_left in groups:
        spans_list.sort(key=lambda t: t[0])
        merged_spans = []
        for k, (_, sp) in enumerate(spans_list):
            if k > 0 and merged_spans:
                last_text = merged_spans[-1]['text']
                first_text = sp[0]['text'] if sp else ''
                if last_text and not last_text.endswith(' ') and \
                   first_text and not first_text.startswith(' '):
                    merged_spans.append({
                        'text': ' ', 'bold': False, 'italic': False,
                        'size': 0, 'font': '',
                    })
            merged_spans.extend(sp)

        full_text = ''.join(s['text'] for s in merged_spans).strip()
        lines_data.append({
            'y': min_y,
            'x': min_x,
            'spans': merged_spans,
            'full_text': full_text,
            'has_bold_start': merged_spans[0]['bold'] if merged_spans else False,
            'page': 0,
        })
    return lines_data


def extract_page_data(page, page_idx, cfg: ExtractionConfig):
    """Extract text spans with metadata from a page.

    Merges line objects that share the same y-position (within tolerance)
    into a single logical line, sorted by x-position.
    """
    raw_lines = []
    for b in page.get_text('dict')['blocks']:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            y_top = line['bbox'][1]
            if y_top < cfg.header_y:
                continue
            spans = _extract_spans(line)
            if spans:
                raw_lines.append((y_top, line['bbox'][0], spans))

    raw_lines.sort(key=lambda t: (t[0], t[1]))

    groups = []
    for y, x, spans in raw_lines:
        is_left = x < cfg.col_boundary
        merged = False
        for g in groups:
            if abs(y - g[0]) <= cfg.y_merge_tolerance and is_left == g[3]:
                g[2].append((x, spans))
                g[0] = min(g[0], y)
                g[1] = min(g[1], x)
                merged = True
                break
        if not merged:
            groups.append([y, x, [(x, spans)], is_left])

    lines_data = _merge_span_groups(groups)
    for ld in lines_data:
        ld['page'] = page_idx
    return lines_data


def detect_boundaries(doc, cfg: ExtractionConfig):
    """Resolve the first and last biography pages.

    If both start_page and end_page are set in config, use them directly.
    Otherwise, auto-detect the missing boundary:
    - Forward scan: finds the first page with enough biography starts
      (at least min_bio_starts_for_page_detection) to distinguish real
      biography pages from title pages with incidental name patterns.
    - Backward scan: looks for end-section keywords (ERRATA, INDEX, etc.).

    Returns (start_page, end_page) as 0-indexed, end exclusive.
    """
    from classifiers import is_biography_start

    if not cfg.needs_auto_detect:
        return cfg.start_page, cfg.end_page

    total = len(doc)
    start = cfg.start_page
    end = cfg.end_page

    logger.info("Détection automatique des limites...")

    if start is None:
        start = 0
        for i in range(total):
            page_lines = extract_page_data(doc[i], i, cfg)
            bio_count = 0
            for j, ld in enumerate(page_lines):
                next_ld = page_lines[j + 1] if j + 1 < len(page_lines) else None
                prev_ld = page_lines[j - 1] if j > 0 else None
                if is_biography_start(ld, cfg, next_ld, prev_ld):
                    bio_count += 1
            if bio_count >= cfg.min_bio_starts_for_page_detection:
                start = i
                logger.info("Début détecté : page %d (PDF %d) [%d biographies]", i, i + 1, bio_count)
                break

    if end is None:
        end = total
        keywords_upper = [kw.upper() for kw in cfg.end_section_keywords]
        found_end = False
        for i in range(total - 1, start, -1):
            text = doc[i].get_text("text").upper()
            if any(kw in text for kw in keywords_upper):
                end = i
                found_end = True
            elif found_end:
                logger.info("Fin détectée : page %d (PDF %d)", end - 1, end)
                break

        if not found_end:
            logger.info("Aucune section de fin détectée, dernière page: %d", total)

    return start, end
