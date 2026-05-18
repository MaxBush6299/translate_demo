"""Run 1 of the demo: translate the PDF en->es with NO glossary."""

from __future__ import annotations

from azure.ai.translation.document import DocumentTranslationInput, StorageInputType, TranslationTarget

from common import (
    delete_prefix,
    download_prefix,
    load_config,
    print_document_results,
    print_translation_summary,
    translation_client,
)


def main() -> None:
    cfg = load_config()

    # Clear any previous Run 1 output to avoid "file already exists" failures.
    delete_prefix(cfg, cfg.target_prefix_no_glossary)

    client = translation_client(cfg)

    # Use StorageInputType.FILE so source and target can live in the same
    # container under different virtual folder prefixes. The managed identity
    # docs require bare container URLs for the Folder mode; FILE mode lets us
    # pass exact blob URLs and avoids same-container collisions.
    inputs = [
        DocumentTranslationInput(
            source_url=cfg.source_blob_url,
            targets=[
                TranslationTarget(
                    target_url=cfg.target_blob_url(cfg.target_prefix_no_glossary),
                    language=cfg.target_language,
                )
            ],
            storage_type=StorageInputType.FILE,
        )
    ]

    print("Submitting batch job (no glossary):")
    print(f"  Source: {cfg.source_blob_url}")
    print(f"  Target: {cfg.target_blob_url(cfg.target_prefix_no_glossary)}")
    print(f"  {cfg.source_language} -> {cfg.target_language}")

    poller = client.begin_translation(inputs)
    result = poller.result()

    print_translation_summary(poller)
    print_document_results(result)

    local_dir = cfg.local_output_dir / "no-glossary"
    print(f"\nDownloading translated files to {local_dir} ...")
    download_prefix(cfg, cfg.target_prefix_no_glossary, local_dir)


if __name__ == "__main__":
    main()
