import csv
from pathlib import Path

from .vocab_entry import VocabEntry
from .logging import get_logger


logger = get_logger("anker.tsv")


def read_from_string(text: str) -> list[VocabEntry]:
    logger.debug("Parsing TSV text into vocabulary entries")
    rows = list(csv.reader(text.splitlines(), delimiter="\t"))
    logger.debug("Parsed %d TSV rows", len(rows))
    entries: list[VocabEntry] = []
    for idx, row in enumerate(rows):
        if len(row) != 4:
            logger.warning(
                "Skipping malformed TSV row %d: expected 4 columns, got %d",
                idx + 1,
                len(row),
            )
            continue
        front, back, front_lang, back_lang = row
        entries.append(
            VocabEntry(
                front=front,
                back=back,
                front_language=front_lang,
                back_language=back_lang,
            )
        )
    logger.info("Converted %d TSV rows into %d vocabulary entries", len(rows), len(entries))
    return entries


def read_from_file(path: Path) -> list[VocabEntry]:
    logger.info("Reading TSV vocabulary from %s", path)
    text = path.read_text(encoding="utf-8")
    return read_from_string(text)


def write_to_file(vocab: list[VocabEntry], path: Path) -> None:
    logger.info("Writing %d vocabulary entries to TSV at %s", len(vocab), path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        for e in vocab:
            writer.writerow([
                e.front,
                e.back,
                e.front_language,
                e.back_language,
            ])
    logger.info("Finished writing TSV file to %s", path.resolve())

