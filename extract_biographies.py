#!/usr/bin/env python3
import argparse
import logging
import re
import shutil
from pathlib import Path

import fitz

from classifiers import (
    is_biography_start, is_cross_reference, is_false_positive,
    is_name_continuation, split_merged_entries,
)
from cleaner import clean_biography_text, extract_filename
from config import ExtractionConfig
from constants import UC, build_word_sets
from pdf_engine import auto_detect_layout, detect_boundaries, extract_page_data

logger = logging.getLogger(__name__)

INPUT_DIR = "BioPdf"
OUTPUT_DIR = "biographies_finales"


def collect_bio_starts(doc, cfg: ExtractionConfig, start_page: int, end_page: int):
    all_lines = []
    for pidx in range(start_page, end_page):
        for ld in extract_page_data(doc[pidx], pidx, cfg):
            all_lines.append((len(all_lines), pidx, ld))

    bio_starts = []
    for i, (gidx, pidx, ld) in enumerate(all_lines):
        next_ld = all_lines[i + 1][2] if i + 1 < len(all_lines) else None
        prev_ld = all_lines[i - 1][2] if i > 0 else None
        if is_biography_start(ld, cfg, next_ld, prev_ld):
            bio_starts.append((gidx, pidx, ld))

    bio_starts = [
        (gidx, pidx, ld) for gidx, pidx, ld in bio_starts
        if gidx == 0 or (
            not re.search(rf'[{UC}]{{2,}}-$',
                          all_lines[gidx - 1][2]['full_text'].rstrip()) and
            not re.search(r'\bVoir\s*$', all_lines[gidx - 1][2]['full_text'].rstrip())
        )
    ]

    merged = []
    skip_next = False
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        if skip_next:
            skip_next = False
            continue

        if i + 1 < len(bio_starts):
            next_gidx = bio_starts[i + 1][0]
            next_ld = bio_starts[i + 1][2]
            gap = next_gidx - gidx

            if gap <= cfg.max_merge_gap_lines:
                between_text = ' '.join(
                    all_lines[j][2]['full_text']
                    for j in range(gidx, next_gidx) if j < len(all_lines)
                )
                if 'Voir' not in between_text:
                    prev_text = all_lines[next_gidx - 1][2]['full_text'] if next_gidx - 1 >= 0 else ''
                    if is_name_continuation(prev_text, next_ld['full_text']):
                        skip_next = True
                    elif any(f' {link} ' in between_text.lower()
                             for link in ('surnommé', 'dit', 'dite',
                                          'nommé', 'appelé')):
                        skip_next = True

        merged.append((gidx, pidx, ld))

    return all_lines, merged


def extract_bio_text(all_lines, start_gidx, end_gidx):
    return [
        ld['full_text']
        for gidx, _, ld in all_lines
        if start_gidx <= gidx < end_gidx
    ]


def _get_bio_first_letter(bio_text):
    text = bio_text.strip().lstrip('*').strip()
    for ch in text:
        if ch.isalpha():
            return ch.upper()
    return None


def run(pdf_path: str, output_dir: Path):
    path = Path(pdf_path)
    if not path.exists():
        raise SystemExit(f"Error: file {pdf_path} does not exist.")

    cfg = ExtractionConfig(pdf_path=pdf_path)
    words = build_word_sets(cfg)

    logger.info("Opening %s...", path)
    doc = fitz.open(str(path))
    logger.info("Total pages: %d", len(doc))

    auto_detect_layout(doc, cfg)

    start_page, end_page, volume_letters = detect_boundaries(doc, cfg)
    logger.info("Processing pages: %d to %d", start_page + 1, end_page)

    all_lines, bio_starts = collect_bio_starts(doc, cfg, start_page, end_page)
    logger.info("Text lines: %d | Bio starts: %d", len(all_lines), len(bio_starts))

    biographies = []
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_lines = extract_bio_text(all_lines, gidx, end_gidx)
        biographies.append((clean_biography_text(raw_lines, cfg), raw_lines))

    merged_bios = []
    i = 0
    while i < len(biographies):
        bio_text, raw_lines = biographies[i]
        if len(bio_text.strip()) < cfg.stub_merge_max_chars and i + 1 < len(biographies):
            next_text, next_raw = biographies[i + 1]
            merged_bios.append((
                f"{bio_text.strip()} {next_text.strip()}",
                raw_lines + next_raw,
            ))
            i += 2
        else:
            merged_bios.append((bio_text, raw_lines))
            i += 1
    biographies = merged_bios

    biographies = [
        entry
        for bio_text, raw_lines in biographies
        for entry in split_merged_entries(bio_text, raw_lines, cfg)
    ]

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    written = 0
    skipped_xrefs = 0
    skipped_false = 0
    filename_counts = {}

    for bio_text, raw_lines in biographies:
        if is_cross_reference(bio_text, cfg):
            skipped_xrefs += 1
            continue
        if is_false_positive(bio_text, cfg, words):
            skipped_false += 1
            continue
        if volume_letters:
            first_letter = _get_bio_first_letter(bio_text)
            if first_letter and first_letter not in volume_letters:
                skipped_false += 1
                continue

        filename = extract_filename(bio_text, raw_lines, cfg, words)

        if filename in filename_counts:
            filename_counts[filename] += 1
            stem, ext = Path(filename).stem, Path(filename).suffix
            filename = f"{stem} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        (output_dir / filename).write_text(bio_text, encoding='utf-8')
        written += 1

    logger.info("Done! %d biographies written to %s/", written, output_dir)
    logger.info("  %d cross-references skipped | %d false positives skipped",
                skipped_xrefs, skipped_false)
    return written


def main():
    parser = argparse.ArgumentParser(
        description="Extract biographies from scanned PDF biographical dictionaries.",
    )
    parser.add_argument("-i", "--input", default=INPUT_DIR,
                        help=f"Input directory containing PDFs (default: {INPUT_DIR})")
    parser.add_argument("-o", "--output", default=OUTPUT_DIR,
                        help=f"Output directory (default: {OUTPUT_DIR})")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        raise SystemExit(f"Error: directory {input_dir} does not exist.")

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Error: no PDFs found in {input_dir}/")

    logger.info("Found %d PDF(s) in %s/", len(pdfs), input_dir)
    base_dir = Path(args.output)
    total_written = 0

    for pdf_path in pdfs:
        output_dir = base_dir / pdf_path.stem
        logger.info("=" * 60)
        logger.info("Processing: %s -> %s/", pdf_path, output_dir)
        logger.info("=" * 60)
        total_written += run(str(pdf_path), output_dir)

    logger.info("=" * 60)
    logger.info("Total: %d biographies written to %s/", total_written, base_dir)


if __name__ == "__main__":
    main()
