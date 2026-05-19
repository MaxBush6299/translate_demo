"""Shared helpers for the Document Translation demo.

All Azure access uses DefaultAzureCredential (Entra ID). No keys, no SAS.
- Translator data plane: caller has 'Cognitive Services User' on the account.
- Storage data plane (local upload/download): caller has a data role such as
  'Storage Blob Data Contributor' (granted by the Bicep deployment).
- Translator -> Storage during the batch job: Translator's system-assigned MI
  has 'Storage Blob Data Contributor' on the storage account.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from azure.ai.translation.document import DocumentTranslationClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DemoConfig:
    translator_endpoint: str
    storage_account_name: str
    container_name: str
    source_prefix: str
    glossary_blob_name: str
    target_prefix_no_glossary: str
    target_prefix_with_glossary: str
    source_language: str
    target_language: str
    local_source_pdf: Path
    local_glossary_tsv: Path
    local_output_dir: Path

    @property
    def blob_endpoint(self) -> str:
        return f"https://{self.storage_account_name}.blob.core.windows.net"

    @property
    def container_url(self) -> str:
        return f"{self.blob_endpoint}/{self.container_name}"

    @property
    def glossary_url(self) -> str:
        return f"{self.container_url}/{self.glossary_blob_name}"

    @property
    def source_blob_url(self) -> str:
        """Exact URL of the source PDF blob, used with StorageInputType.FILE."""
        return f"{self.container_url}/{self.source_prefix.rstrip('/')}/{self.local_source_pdf.name}"

    def target_blob_url(self, prefix: str) -> str:
        """Exact URL for the translated output blob.
        Same filename as the source, placed under the given virtual folder prefix.
        Using StorageInputType.FILE keeps source and output in the same container
        without the service conflating the two container-level paths."""
        return f"{self.container_url}/{prefix.rstrip('/')}/{self.local_source_pdf.name}"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


def load_config() -> DemoConfig:
    load_dotenv(REPO_ROOT / ".env")
    return DemoConfig(
        translator_endpoint=_require_env("TRANSLATOR_ENDPOINT"),
        storage_account_name=_require_env("STORAGE_ACCOUNT_NAME"),
        container_name=os.getenv("CONTAINER_NAME", "documents"),
        source_prefix=os.getenv("SOURCE_PREFIX", "source/"),
        glossary_blob_name=os.getenv(
            "GLOSSARY_BLOB_NAME", "glossaries/glossary_v1-en-es.tsv"
        ),
        target_prefix_no_glossary=os.getenv(
            "TARGET_PREFIX_NO_GLOSSARY", "target/no-glossary/"
        ),
        target_prefix_with_glossary=os.getenv(
            "TARGET_PREFIX_WITH_GLOSSARY", "target/with-glossary/"
        ),
        source_language=os.getenv("SOURCE_LANGUAGE", "en"),
        target_language=os.getenv("TARGET_LANGUAGE", "es"),
        local_source_pdf=REPO_ROOT
        / os.getenv(
            "LOCAL_SOURCE_PDF",
            "source_docs/osha_excerpt.pdf",
        ),
        local_glossary_tsv=REPO_ROOT
        / os.getenv("LOCAL_GLOSSARY_TSV", "glossary/glossary_v1-en-es.tsv"),
        local_output_dir=REPO_ROOT / os.getenv("LOCAL_OUTPUT_DIR", "output"),
    )


def credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def translation_client(cfg: DemoConfig) -> DocumentTranslationClient:
    return DocumentTranslationClient(cfg.translator_endpoint, credential())


def blob_service_client(cfg: DemoConfig) -> BlobServiceClient:
    return BlobServiceClient(account_url=cfg.blob_endpoint, credential=credential())


def upload_file(
    cfg: DemoConfig, local_path: Path, blob_name: str, *, overwrite: bool = True
) -> str:
    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    bsc = blob_service_client(cfg)
    container = bsc.get_container_client(cfg.container_name)
    with local_path.open("rb") as fh:
        container.upload_blob(name=blob_name, data=fh, overwrite=overwrite)
    blob_url = f"{cfg.container_url}/{blob_name}"
    print(f"Uploaded {local_path.name} -> {blob_url}")
    return blob_url


def download_prefix(cfg: DemoConfig, prefix: str, local_dir: Path) -> list[Path]:
    """Download every blob under `prefix` into `local_dir` (flat by filename)."""
    local_dir.mkdir(parents=True, exist_ok=True)
    bsc = blob_service_client(cfg)
    container = bsc.get_container_client(cfg.container_name)
    downloaded: list[Path] = []
    for blob in container.list_blobs(name_starts_with=prefix):
        local_name = Path(blob.name).name
        if not local_name:
            continue
        out_path = local_dir / local_name
        downloader = container.download_blob(blob.name)
        with out_path.open("wb") as fh:
            fh.write(downloader.readall())
        downloaded.append(out_path)
        print(f"Downloaded {blob.name} -> {out_path}")
    if not downloaded:
        print(f"WARNING: no blobs found under prefix '{prefix}'")
    return downloaded


def delete_prefix(cfg: DemoConfig, prefix: str) -> int:
    """Delete all blobs under `prefix`. Useful before re-running a translation."""
    bsc = blob_service_client(cfg)
    container = bsc.get_container_client(cfg.container_name)
    count = 0
    for blob in container.list_blobs(name_starts_with=prefix):
        container.delete_blob(blob.name)
        count += 1
    if count:
        print(f"Deleted {count} blob(s) under prefix '{prefix}'")
    return count


def print_translation_summary(poller) -> None:
    print(f"Job status: {poller.status()}")
    details = poller.details
    print(f"  Created on:       {details.created_on}")
    print(f"  Last updated on:  {details.last_updated_on}")
    print(f"  Total documents:  {details.documents_total_count}")
    print(f"  Succeeded:        {details.documents_succeeded_count}")
    print(f"  Failed:           {details.documents_failed_count}")


def print_document_results(results: Iterable) -> None:
    for doc in results:
        print(f"\nDocument ID: {doc.id}")
        print(f"  Status: {doc.status}")
        if doc.status == "Succeeded":
            print(f"  Source:      {doc.source_document_url}")
            print(f"  Translated:  {doc.translated_document_url}")
            print(f"  Language:    {doc.translated_to}")
        elif doc.error:
            print(f"  Error {doc.error.code}: {doc.error.message}")
