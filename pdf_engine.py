import logging
import re
from collections import Counter

from config import ExtractionConfig
from constants import PYMUPDF_BOLD_BIT, PYMUPDF_ITALIC_BIT, GREEK_TO_LATIN

logger = logging.getLogger(__name__)


def _extract_spans(line):
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
                    break

    if not all_x:
        return

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
        cfg.col_boundary = float(best_gap_start + best_gap_size // 2)

    y_counts = Counter(all_y)
    sorted_y = sorted(y_counts.keys())
    if sorted_y:
        for i in range(len(sorted_y) - 1):
            gap = sorted_y[i + 1] - sorted_y[i]
            if gap >= 15 and sorted_y[i] < 100:
                cfg.header_y = float(sorted_y[i] + gap // 2)
                break

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
        r = _indent_range(right_bold)
        if r:
            cfg.right_col_indent = r


def _is_section_letter(page, page_width, cfg):
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
                if t in ('I', 'V', 'X', 'L', 'C', 'D', 'M'):
                    if not (s['flags'] & PYMUPDF_BOLD_BIT):
                        continue
                t = GREEK_TO_LATIN.get(t, t)
                if ord(t) > 0x024F:
                    continue
                if s['size'] < cfg.section_letter_min_size:
                    continue
                x_center = (line['bbox'][0] + line['bbox'][2]) / 2
                if abs(x_center - page_center) <= cfg.section_letter_center_tolerance:
                    return t
    return None


def _detect_suite_letter(page):
    text = page.get_text('text').strip()
    m = re.match(r'^([A-Z])\s*\(suite\)', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _verify_section_letter(doc, page_idx, candidate_letter, cfg):
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
                                "  OCR correction: marker '%s' (p.%d) -> '%s'",
                                candidate_letter, page_idx + 1, bio_letter,
                            )
                            return bio_letter
                        return candidate_letter
    return candidate_letter


def scan_section_letters(doc, cfg):
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
    if not section_letters:
        return None
    first = ord(section_letters[0][1])
    last = ord(section_letters[-1][1])
    return set(chr(c) for c in range(first, last + 1))


def _find_front_matter_end(doc, cfg):
    last_fm_page = -1
    limit = min(len(doc), cfg.start_page_scan_limit)
    for i in range(limit):
        text = doc[i].get_text('text').upper()
        if any(kw.upper() in text for kw in cfg.front_matter_keywords):
            last_fm_page = i
        elif last_fm_page >= 0:
            break
    return last_fm_page


def find_biography_start_page(doc, cfg, section_letters=None, fm_end=-1, suite_page=None):
    from classifiers import is_biography_start

    if suite_page is not None:
        logger.info("Suite marker found at page %d (PDF %d)", suite_page, suite_page + 1)
        return suite_page

    near_front = [s for s in (section_letters or []) if s[0] < max(fm_end + 20, 50)]
    if near_front:
        first_page, first_letter = near_front[0]
        for check_page in range(first_page, min(first_page + 2, len(doc))):
            page_lines = extract_page_data(doc[check_page], check_page, cfg)
            bio_count = sum(
                1 for j, ld in enumerate(page_lines)
                if is_biography_start(
                    ld, cfg,
                    page_lines[j + 1] if j + 1 < len(page_lines) else None,
                    page_lines[j - 1] if j > 0 else None,
                )
            )
            if bio_count >= 1:
                logger.info(
                    "Section marker '%s' found at page %d (PDF %d) with %d bio(s)",
                    first_letter, first_page, first_page + 1, bio_count,
                )
                return first_page

    search_start = max(0, fm_end + 1) if fm_end >= 0 else 0
    for i in range(search_start, len(doc)):
        page_lines = extract_page_data(doc[i], i, cfg)
        bio_count = sum(
            1 for j, ld in enumerate(page_lines)
            if is_biography_start(
                ld, cfg,
                page_lines[j + 1] if j + 1 < len(page_lines) else None,
                page_lines[j - 1] if j > 0 else None,
            )
        )
        if bio_count >= 1:
            logger.info(
                "Start detected (fallback): page %d (PDF %d) [%d bio(s)]",
                i, i + 1, bio_count,
            )
            return i

    return 0


def find_biography_end_page(doc, cfg, start_page):
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
            logger.info("End detected: page %d (PDF %d)", end - 1, end)
            break

    if not found_end:
        logger.info("No end section found, using last page: %d", total)

    return end


def _infer_first_letter(doc, start_page, cfg):
    from classifiers import is_biography_start
    for i in range(start_page, min(start_page + 5, len(doc))):
        page_lines = extract_page_data(doc[i], i, cfg)
        for j, ld in enumerate(page_lines):
            next_ld = page_lines[j + 1] if j + 1 < len(page_lines) else None
            prev_ld = page_lines[j - 1] if j > 0 else None
            if is_biography_start(ld, cfg, next_ld, prev_ld):
                name = ld['full_text'].strip().lstrip('*').strip()
                for ch in name:
                    if ch.isalpha():
                        return ch.upper()
    return None


def detect_boundaries(doc, cfg: ExtractionConfig):
    if not cfg.needs_auto_detect:
        return cfg.start_page, cfg.end_page, None

    logger.info("Auto-detecting boundaries...")

    fm_end = _find_front_matter_end(doc, cfg)

    suite_letter = None
    if fm_end >= 0:
        for i in range(fm_end, min(fm_end + 5, len(doc))):
            suite_letter = _detect_suite_letter(doc[i])
            if suite_letter:
                logger.info("Suite volume: starts with '%s' (p.%d)", suite_letter, i + 1)
                break

    all_section_letters = scan_section_letters(doc, cfg)

    suite_page = None
    if suite_letter:
        for i in range(max(0, fm_end), min(fm_end + 5, len(doc))):
            if _detect_suite_letter(doc[i]):
                suite_page = i
                break

    start = cfg.start_page
    end = cfg.end_page

    if start is None:
        start = find_biography_start_page(doc, cfg, all_section_letters, fm_end, suite_page)
    if end is None:
        end = find_biography_end_page(doc, cfg, start)

    section_letters = [(p, l) for p, l in all_section_letters if start <= p < end]

    if suite_letter:
        if not section_letters or section_letters[0][1] != suite_letter:
            section_letters = [(start, suite_letter)] + section_letters

    if section_letters:
        first_letter = section_letters[0][1]
        table_des_start = None
        for p, l in section_letters[1:]:
            if l < first_letter:
                table_des_start = p
                logger.info("TABLE DES detected at page %d (marker '%s' < '%s')",
                             p + 1, l, first_letter)
                break
        if table_des_start:
            end = min(end, table_des_start)
            section_letters = [(p, l) for p, l in section_letters if p < table_des_start]
            logger.info("End adjusted to page %d (before TABLE DES)", end)

    if section_letters:
        logger.info("Section markers (in range): %s",
                     ', '.join(f"'{l}' (p.{p+1})" for p, l in section_letters))

    volume_letters = get_volume_letter_range(section_letters)

    if not volume_letters:
        first_letter = _infer_first_letter(doc, start, cfg)
        if first_letter:
            last_letter = first_letter
            for i in range(end - 1, max(start, end - 10) - 1, -1):
                page_text = doc[i].get_text('text').strip()
                lines = page_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and line[0].isalpha() and line[0].isupper():
                        candidate = line[0].upper()
                        if candidate >= first_letter:
                            last_letter = max(last_letter, candidate)
                            break
                if last_letter > first_letter:
                    break
            volume_letters = set(chr(c) for c in range(ord(first_letter), ord(last_letter) + 1))
            logger.info("Inferred letter range: %s (from first bio)",
                         ', '.join(sorted(volume_letters)))

    if volume_letters:
        logger.info("Expected letters: %s", ', '.join(sorted(volume_letters)))

    return start, end, volume_letters
