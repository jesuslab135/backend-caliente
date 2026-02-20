import csv
import io

from .base import BaseFileParser


class CsvFileParser(BaseFileParser):
    """Concrete strategy for parsing CSV files."""

    def parse(self, file) -> list[dict]:
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        return [
            {k.strip().lower(): v for k, v in row.items()}
            for row in reader
        ]
