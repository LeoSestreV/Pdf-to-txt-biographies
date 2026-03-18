"""PyMuPDF-based PDF text extraction with font metadata."""

import logging
import re
from collections import Counter

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


def auto_detect_layout(doc, cfg: ExtractionConfig, sample_range=None):
    """Analyze PDF pages to auto-detect column boundary and indent ranges.

    Samples content pages to find:
    - col_boundary: gap between left and right column X positions
    - header_y: Y below which lines are running headers
    - left_col_indent / right_col_indent: X ranges for biography start indentation
    """
    total = len(doc)
    if sample_range is None:
        start = max(0, total // 5)
        end = min(total, total * 4 // 5)
        step = max(1, (end - start) // 40)
        sample_range = range(start, end, step)

    all_x = []
    all_y = []
    bold_x = []

    for pi in sample_range:
        page = doc[pi]
        for b in page.get_text('dict')['blocks']:
            if 'lines' not in b:
                continue
            for line in b['lines']:
                y = line['bbox'][1]
                x = line['bbox'][0]
                for s in line['spans']:
                    if not s['text'].strip():
                        continue
                    all_x.append(int(x))
                    all_y.append(int(y))
                    if (s['flags'] & PYMUPDF_BOLD_BIT) and s['size'] >= 7.0:
                        clean = re.sub(r'[\s\-\'\.,;:\(\)\*]', '', s['text'])
                        if clean and len(clean) >= 3:
                            upper = sum(1 for c in clean if c.isupper())
                            if upper / len(clean) > 0.5:
                                bold_x.append(int(x))
                    break  # only first span per line

    if not all_x:
        return

    # Find column boundary: largest gap in X distribution between 200-350
    x_counts = Counter(all_x)
    buckets = {}
    for x, cnt in x_counts.items():
        bucket = (x // 5) * 5
        buckets[bucket] = buckets.get(bucket, 0) + cnt

    sorted_buckets = sorted(buckets.keys())
    best_gap_start = 0
    best_gap_size = 0
    for i in range(len(sorted_buckets) - 1):
        gap = sorted_buckets[i + 1] - sorted_buckets[i]
        mid = (sorted_buckets[i] + sorted_buckets[i + 1]) / 2
        if 180 < mid < 380 and gap > best_gap_size:
            best_gap_size = gap
            best_gap_start = sorted_buckets[i]

    if best_gap_size >= 15:
        col_boundary = best_gap_start + best_gap_size // 2
        cfg.col_boundary = float(col_boundary)
        logger.info("  col_boundary auto-détecté: %.0f", cfg.col_boundary)

    # Auto-detect header_y: find the Y below which very few lines appear
    y_counts = Counter(all_y)
    sorted_y = sorted(y_counts.keys())
    if sorted_y:
        for i in range(len(sorted_y) - 1):
            gap = sorted_y[i + 1] - sorted_y[i]
            if gap >= 15 and sorted_y[i] < 100:
                cfg.header_y = float(sorted_y[i] + gap // 2)
                logger.info("  header_y auto-détecté: %.0f", cfg.header_y)
                break

    # Auto-detect indent ranges from bold biography name positions
    def _indent_range(positions):
        if len(positions) < 3:
            return None
        positions = sorted(positions)
        q1 = positions[len(positions) // 4]
        q3 = positions[3 * len(positions) // 4]
        iqr = q3 - q1
        lo = q1 - 1.5 * max(iqr, 10)
        hi = q3 + 1.5 * max(iqr, 10)
        filtered = [x for x in positions if lo <= x <= hi]
        if not filtered:
            return None
        return (float(min(filtered) - 2), float(max(filtered) + 5))

    if bold_x:
        left_bold = [x for x in bold_x if x < cfg.col_boundary]
        right_bold = [x for x in bold_x if x >= cfg.col_boundary]

        r = _indent_range(left_bold)
        if r:
            cfg.left_col_indent = r
            logger.info("  left_col_indent auto-détecté: (%.0f, %.0f)", *cfg.left_col_indent)

        r = _indent_range(right_bold)
        if r:
            cfg.right_col_indent = r
            logger.info("  right_col_indent auto-détecté: (%.0f, %.0f)", *cfg.right_col_indent)


def _is_section_letter(page, page_width, cfg):
    """Check if a page contains a section letter marker (e.g. 'A', 'B').

    Section letters are isolated uppercase letters, large (>= 12pt),
    roughly centered on the page, that mark the beginning of an
    alphabetic section in the biography volume.

    Returns the letter if found, None otherwise.
    """
    page_center = page_width / 2
    for b in page.get_text('dict')['blocks']:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            line_text = ''.join(s['text'] for s in line['spans']).strip()
            if len(line_text) > 3:
                continue
            for s in line['spans']:
                t = s['text'].strip()
                if not t or len(t) != 1 or not t.isalpha():
                    continue
                # Must be a Latin letter A-Z (including accented equivalents)
                # Exclude Greek letters and isolated Roman numeral 'I'
                if t in ('I', 'V', 'X', 'L', 'C', 'D', 'M'):
                    # Only accept I/V/X/etc. if bold -- a real section marker
                    # is typically bold while roman numerals in front matter are not
                    if not (s['flags'] & PYMUPDF_BOLD_BIT):
                        continue
                # Normalize Greek lookalikes from OCR (Β->B, Α->A, etc.)
                _GREEK_TO_LATIN = {
                    'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H',
                    'Ι': 'I', 'Κ': 'K', 'Μ': 'M', 'Ν': 'N', 'Ο': 'O',
                    'Ρ': 'P', 'Τ': 'T', 'Υ': 'Y', 'Χ': 'X',
                }
                t = _GREEK_TO_LATIN.get(t, t)
                if ord(t) > 0x024F:
                    continue
                if s['size'] < cfg.section_letter_min_size:
                    continue
                x_center = (line['bbox'][0] + line['bbox'][2]) / 2
                if abs(x_center - page_center) <= cfg.section_letter_center_tolerance:
                    return t
    return None


def _verify_section_letter(doc, page_idx, candidate_letter, cfg):
    """Verify a section letter by checking biography names on nearby pages.

    OCR can confuse letters (C→G, O→Q, etc.). Cross-check the candidate
    against the first letters of bold biography names on the same/next page.
    Returns the corrected letter.
    """
    from classifiers import is_biography_start
    for check_page in range(page_idx, min(page_idx + 2, len(doc))):
        page_lines = extract_page_data(doc[check_page], check_page, cfg)
        for j, ld in enumerate(page_lines):
            next_ld = page_lines[j + 1] if j + 1 < len(page_lines) else None
            prev_ld = page_lines[j - 1] if j > 0 else None
            if is_biography_start(ld, cfg, next_ld, prev_ld):
                name_text = ld['full_text'].strip().lstrip('*').strip()
                for ch in name_text:
                    if ch.isalpha():
                        bio_letter = ch.upper()
                        if bio_letter != candidate_letter:
                            logger.info(
                                "  Correction OCR: marqueur '%s' (p.%d) → '%s' "
                                "(d'après biographies)",
                                candidate_letter, page_idx + 1, bio_letter,
                            )
                            return bio_letter
                        return candidate_letter
    return candidate_letter


def scan_section_letters(doc, cfg):
    """Scan all pages to find section letter markers and return them in order.

    Returns a list of (page_index, letter) tuples, e.g. [(41, 'A'), (250, 'B')].
    Section letters are verified against actual biography names to correct OCR errors.
    """
    page_width = doc[0].rect.width
    letters = []
    for i in range(len(doc)):
        letter = _is_section_letter(doc[i], page_width, cfg)
        if letter:
            verified = _verify_section_letter(doc, i, letter, cfg)
            if not letters or verified != letters[-1][1]:
                letters.append((i, verified))
    return letters


def get_volume_letter_range(section_letters):
    """Determine the expected letter range from section letter markers.

    Returns a set of uppercase letters that biographies in this volume
    should start with (including letters between the first and last marker).
    """
    if not section_letters:
        return None
    first = ord(section_letters[0][1])
    last = ord(section_letters[-1][1])
    return set(chr(c) for c in range(first, last + 1))


def find_biography_start_page(doc, cfg, section_letters=None):
    """Find the first page where biographies begin using section letter markers.

    Scans from page 0, looking for a page with:
    1. An isolated, large, centered uppercase letter (section marker)
    2. Followed by biography content on the same page or the next

    Falls back to the old method (counting bio starts) if no marker is found.
    """
    from classifiers import is_biography_start

    if section_letters:
        first_page = section_letters[0][0]
        first_letter = section_letters[0][1]
        # Verify: this page or the next must contain biography starts
        for check_page in range(first_page, min(first_page + 2, len(doc))):
            page_lines = extract_page_data(doc[check_page], check_page, cfg)
            bio_count = 0
            for j, ld in enumerate(page_lines):
                next_ld = page_lines[j + 1] if j + 1 < len(page_lines) else None
                prev_ld = page_lines[j - 1] if j > 0 else None
                if is_biography_start(ld, cfg, next_ld, prev_ld):
                    bio_count += 1
            if bio_count >= 1:
                logger.info(
                    "Marqueur de section '%s' trouvé page %d (PDF %d) "
                    "avec %d biographie(s)",
                    first_letter, first_page, first_page + 1, bio_count,
                )
                return first_page

    # Fallback: find first page with enough bio starts
    logger.info("Aucun marqueur de section trouvé, fallback sur comptage...")
    for i in range(len(doc)):
        page_lines = extract_page_data(doc[i], i, cfg)
        bio_count = 0
        for j, ld in enumerate(page_lines):
            next_ld = page_lines[j + 1] if j + 1 < len(page_lines) else None
            prev_ld = page_lines[j - 1] if j > 0 else None
            if is_biography_start(ld, cfg, next_ld, prev_ld):
                bio_count += 1
        if bio_count >= cfg.min_bio_starts_for_page_detection:
            logger.info(
                "Début détecté (fallback): page %d (PDF %d) [%d biographies]",
                i, i + 1, bio_count,
            )
            return i

    return 0


def find_biography_end_page(doc, cfg, start_page):
    """Find the last page of biographies.

    Scans backward from the end, looking for end-section keywords
    (ERRATA, TABLE DES MATIÈRES, TABLE ALPHABÉTIQUE, INDEX) only
    in the last N pages to avoid false matches in body text.
    """
    total = len(doc)
    keywords_upper = [kw.upper() for kw in cfg.end_section_keywords]
    search_start = max(start_page, total - cfg.end_section_search_pages)
    found_end = False
    end = total

    for i in range(total - 1, search_start, -1):
        text = doc[i].get_text("text").upper()
        if any(kw in text for kw in keywords_upper):
            end = i
            found_end = True
        elif found_end:
            logger.info("Fin détectée : page %d (PDF %d)", end - 1, end)
            break

    if not found_end:
        logger.info("Aucune section de fin détectée, dernière page: %d", total)

    return end


def detect_boundaries(doc, cfg: ExtractionConfig):
    """Resolve the first and last biography pages.

    Uses section letter markers (large centered uppercase letters like 'A', 'B')
    to find where biographies begin, with a fallback to counting biography starts.
    End detection scans backward for ERRATA/TABLE DES/INDEX keywords.

    Returns (start_page, end_page, volume_letters) where volume_letters is a set
    of uppercase letters expected in this volume (e.g. {'A', 'B'}), or None.
    """
    if not cfg.needs_auto_detect:
        return cfg.start_page, cfg.end_page, None

    logger.info("Détection automatique des limites...")

    section_letters = scan_section_letters(doc, cfg)
    if section_letters:
        logger.info("Marqueurs de section trouvés: %s",
                     ', '.join(f"'{l}' (p.{p+1})" for p, l in section_letters))
    volume_letters = get_volume_letter_range(section_letters)

    start = cfg.start_page
    end = cfg.end_page

    if start is None:
        start = find_biography_start_page(doc, cfg, section_letters)

    if end is None:
        end = find_biography_end_page(doc, cfg, start)

    return start, end, volume_letters
