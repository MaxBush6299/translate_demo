"""Upload the demo PDF and glossary TSV to blob storage."""

from __future__ import annotations

from common import load_config, upload_file


def main() -> None:
    cfg = load_config()

    source_blob = f"{cfg.source_prefix.rstrip('/')}/{cfg.local_source_pdf.name}"
    upload_file(cfg, cfg.local_source_pdf, source_blob)

    upload_file(cfg, cfg.local_glossary_tsv, cfg.glossary_blob_name)

    print("\nInputs uploaded. Next: python scripts/01_translate_no_glossary.py")


if __name__ == "__main__":
    main()
