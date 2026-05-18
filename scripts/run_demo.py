"""End-to-end runner: upload inputs, run both translations, download outputs, compare."""

from __future__ import annotations

import importlib


def _run(module_name: str) -> None:
    print(f"\n{'=' * 70}\n=== {module_name}\n{'=' * 70}")
    mod = importlib.import_module(module_name)
    mod.main()


def main() -> None:
    _run("00_upload_inputs")
    _run("01_translate_no_glossary")
    _run("02_translate_with_glossary")
    _run("03_compare")
    print("\nDemo complete. See ./output/no-glossary/, ./output/with-glossary/, and ./output/comparison.html")


if __name__ == "__main__":
    main()
