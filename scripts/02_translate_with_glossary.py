"""Run 2 of the demo: translate the PDF en->es WITH the TSV glossary."""

from __future__ import annotations

from azure.ai.translation.document import (
    DocumentTranslationInput,
    StorageInputType,
    TranslationGlossary,
    TranslationTarget,
)

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

    delete_prefix(cfg, cfg.target_prefix_with_glossary)

    client = translation_client(cfg)

    inputs = [
        DocumentTranslationInput(
            source_url=cfg.source_blob_url,
            targets=[
                TranslationTarget(
                    target_url=cfg.target_blob_url(cfg.target_prefix_with_glossary),
                    language=cfg.target_language,
                    glossaries=[
                        TranslationGlossary(
                            glossary_url=cfg.glossary_url,
                            file_format="tsv",
                        )
                    ],
                )
            ],
            storage_type=StorageInputType.FILE,
        )
    ]

    print("Submitting batch job (with glossary):")
    print(f"  Source:   {cfg.source_blob_url}")
    print(f"  Target:   {cfg.target_blob_url(cfg.target_prefix_with_glossary)}")
    print(f"  Glossary: {cfg.glossary_url}")
    print(f"  {cfg.source_language} -> {cfg.target_language}")

    poller = client.begin_translation(inputs)
    result = poller.result()

    print_translation_summary(poller)
    print_document_results(result)

    local_dir = cfg.local_output_dir / "with-glossary"
    print(f"\nDownloading translated files to {local_dir} ...")
    download_prefix(cfg, cfg.target_prefix_with_glossary, local_dir)


if __name__ == "__main__":
    main()
