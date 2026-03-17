#!/usr/bin/env python3
"""
Extract biographies from scanned PDF volumes of biographical dictionaries.

Uses PyMuPDF font metadata (bold detection) combined with text pattern matching
and indentation analysis to reliably segment biography entries.
Automatically detects biography start/end pages unless overridden in config.

Usage:
    python extract_biographies.py BiographieNationale_Volume1.pdf
    python extract_biographies.py volume1_config.json
"""

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
from config import ExtractionConfig, build_config
from constants import UC, build_word_sets
from pdf_engine import detect_boundaries, extract_page_data

logger = logging.getLogger(__name__)


def collect_bio_starts(doc, cfg: ExtractionConfig, start_page: int, end_page: int):
    """Scan biography pages [start_page, end_page) and collect starts."""
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
        if gidx == 0 or not re.search(rf'[{UC}]{{2,}}-$',
                                       all_lines[gidx - 1][2]['full_text'].rstrip())
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

        merged.append((gidx, pidx, ld))

    return all_lines, merged


def extract_bio_text(all_lines, start_gidx, end_gidx):
    """Extract the raw text lines between two global line indices."""
    return [
        ld['full_text']
        for gidx, _, ld in all_lines
        if start_gidx <= gidx < end_gidx
    ]


def run(cfg: ExtractionConfig):
    """Run the full extraction pipeline with the given configuration."""
    pdf_path = Path(cfg.pdf_path)
    output_dir = Path(cfg.output_dir)
    log_file = Path(cfg.log_file)

    logger.info("Opening %s...", pdf_path)
    doc = fitz.open(str(pdf_path))
    logger.info("Total pages: %d", len(doc))

    start_page, end_page = detect_boundaries(doc, cfg)
    logger.info("Pages traitées : %d à %d", start_page + 1, end_page)

    words = build_word_sets(cfg)

    logger.info("Extracting text with font metadata...")
    all_lines, bio_starts = collect_bio_starts(doc, cfg, start_page, end_page)
    logger.info("Total text lines extracted: %d", len(all_lines))
    logger.info("Biography starts detected: %d", len(bio_starts))

    logger.info("Segmenting biographies...")
    biographies = []
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_lines = extract_bio_text(all_lines, gidx, end_gidx)
        biographies.append((clean_biography_text(raw_lines, cfg), raw_lines))

    logger.info("Biographies segmented: %d", len(biographies))

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
    logger.info("After merging stubs: %d", len(biographies))

    biographies = [
        entry
        for bio_text, raw_lines in biographies
        for entry in split_merged_entries(bio_text, raw_lines, cfg)
    ]

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    log_entries = []
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

        filename = extract_filename(bio_text, raw_lines, cfg, words)

        if filename in filename_counts:
            filename_counts[filename] += 1
            stem, ext = Path(filename).stem, Path(filename).suffix
            filename = f"{stem} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        (output_dir / filename).write_text(bio_text, encoding='utf-8')

        word_count = len(bio_text.split())
        char_count = len(bio_text)
        status = "OK" if char_count >= cfg.alert_min_chars else "ALERTE: très court"
        log_entries.append(f"{filename} | {word_count} mots | {char_count} car. | {status}")
        written += 1

    title = cfg.report_title or f"RAPPORT D'EXTRACTION - {pdf_path.name}"
    alerts = [e for e in log_entries if "ALERTE" in e]
    report_lines = [
        "=" * 80,
        title,
        "=" * 80,
        "",
        f"Biographies extraites : {written}",
        f"Renvois (Voir...) ignorés : {skipped_xrefs}",
        f"Faux positifs ignorés : {skipped_false}",
        f"Total entrées détectées : {len(biographies)}",
        "",
    ]
    if alerts:
        report_lines.append(f"--- ALERTES ({len(alerts)} entrées courtes < {cfg.alert_min_chars} car.) ---")
        report_lines.extend(f"  {a}" for a in alerts)
        report_lines.append("")
    report_lines.append("--- DÉTAIL COMPLET ---")
    report_lines.extend(f"  {entry}" for entry in log_entries)

    log_file.write_text('\n'.join(report_lines) + '\n', encoding='utf-8')

    logger.info("Terminé!")
    logger.info("  %d biographies écrites dans %s/", written, output_dir)
    logger.info("  %d renvois ignorés", skipped_xrefs)
    logger.info("  %d faux positifs ignorés", skipped_false)
    logger.info("  Rapport: %s", log_file)


def main():
    parser = argparse.ArgumentParser(
        description="Extract biographies from scanned PDF biographical dictionaries.",
        epilog="Examples:\n"
               "  %(prog)s BiographieNationale_Volume1.pdf\n"
               "  %(prog)s volume1_config.json\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        help="PDF file or JSON config (auto-detected by extension)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    run(build_config(args.source))


if __name__ == "__main__":
    main()
