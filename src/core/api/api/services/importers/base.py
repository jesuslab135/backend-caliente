from abc import ABC, abstractmethod


class BaseFileParser(ABC):
    """Abstract strategy for parsing uploaded files into row dicts."""

    @abstractmethod
    def parse(self, file) -> list[dict]:
        """Parse an uploaded file and return a list of normalized row dicts."""
        ...

    @classmethod
    def get_parser(cls, filename: str) -> 'BaseFileParser':
        """Factory method: select the correct parser strategy by file extension."""
        from .csv_importer import CsvFileParser
        from .excel_importer import ExcelFileParser

        lower = filename.lower()
        if lower.endswith('.csv'):
            return CsvFileParser()
        if lower.endswith(('.xlsx', '.xls')):
            return ExcelFileParser()
        raise ValueError(f'Formato de archivo no soportado: {filename}')
