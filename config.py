"""ExtractionConfig dataclass."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractionConfig:
    """All tunable parameters for biography extraction.

    Every threshold, size, and document-specific value lives here.
    Defaults match the Biographie Nationale Volume 1 layout.
    """

    pdf_path: str = ""
    output_dir: str = "biographies_finales"

    start_page: int | None = None
    end_page: int | None = None

    end_section_keywords: list[str] = field(default_factory=lambda: [
        "ERRATA", "TABLE DES", "INDEX",
    ])

    min_bio_starts_for_page_detection: int = 3

    header_y: float = 60.0
    footer_y: float = 590.0
    col_boundary: float = 290.0
    y_merge_tolerance: float = 2.0
    left_col_indent: tuple[float, float] = (146.0, 165.0)
    right_col_indent: tuple[float, float] = (308.0, 330.0)

    min_bold_name_size: float = 7.0
    max_attribution_size: float = 7.5
    footnote_y: float = 350.0
    min_uppercase_ratio: float = 0.5
    min_uppercase_count: int = 2

    stub_merge_max_chars: int = 60
    min_entry_chars: int = 30
    short_entry_chars: int = 100
    alert_min_chars: int = 150
    xref_max_chars: int = 300
    xref_garbled_max_chars: int = 200
    latin_sample_chars: int = 300
    latin_uppercase_ratio: float = 0.8
    min_alpha_for_latin: int = 30

    min_name_length: int = 3
    max_name_alone_length: int = 50
    max_name_chars: int = 80
    max_filename_chars: int = 90
    fallback_name_chars: int = 60
    header_lines_count: int = 5

    max_merge_gap_lines: int = 2
    split_part1_min_chars: int = 10
    split_part2_min_chars: int = 50
    author_attrib_max_size: int = 100

    ocr_fixes: dict[str, str] = field(default_factory=lambda: {
        'ARIVOIIL': 'ARNOUL',
    })
    filename_ocr_fixes: dict[str, str] = field(default_factory=lambda: {
        'DETO -LÉDE': 'DE TOLÈDE',
        'DETO-LÉDE': 'DE TOLÈDE',
        'ARIVOIIL': 'ARNOUL',
    })

    extra_descriptors: list[str] = field(default_factory=list)
    extra_blacklisted_starts: list[str] = field(default_factory=list)
    extra_fragment_starters: list[str] = field(default_factory=list)
    extra_latin_fragments: list[str] = field(default_factory=list)
    extra_latin_indicators: list[str] = field(default_factory=list)

    @property
    def needs_auto_detect(self) -> bool:
        """True if start or end page must be auto-detected."""
        return self.start_page is None or self.end_page is None
