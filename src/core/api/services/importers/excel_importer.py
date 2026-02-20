from datetime import datetime

from .base import BaseFileParser


class ExcelFileParser(BaseFileParser):
    """Concrete strategy for parsing Excel (.xlsx/.xls) files."""

    def parse(self, file) -> list[dict]:
        import openpyxl

        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        raw_header = next(rows_iter, None)
        if not raw_header:
            wb.close()
            return []

        header = [str(h).strip().lower() if h else '' for h in raw_header]

        result = []
        for row_values in rows_iter:
            if all(v is None for v in row_values):
                continue
            row_dict = {}
            for col_name, value in zip(header, row_values):
                if isinstance(value, datetime):
                    row_dict[col_name] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    row_dict[col_name] = value if value is not None else ''
            result.append(row_dict)

        wb.close()
        return result
