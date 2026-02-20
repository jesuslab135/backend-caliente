from django.core.exceptions import ValidationError
from django.db import IntegrityError

from api.models import League
from .base import BaseFileParser


class LeagueImportService:
    """Orchestrates league import from CSV/Excel files."""

    def __init__(self, file, filename: str):
        self._parser = BaseFileParser.get_parser(filename)
        self._file = file
        self._imported = 0
        self._errors: list[str] = []

    def execute(self) -> dict:
        rows = self._parser.parse(self._file)

        for i, row in enumerate(rows, start=2):
            try:
                data = self._validate_row(row, i)
                League.objects.create(**data)
                self._imported += 1
            except ValidationError as e:
                self._errors.append(f'Fila {i}: {e.message}')
            except IntegrityError:
                name = row.get('name', '').strip()
                self._errors.append(f'Fila {i}: La liga "{name}" ya existe.')
            except Exception as e:
                self._errors.append(f'Fila {i}: {str(e)}')

        return {'imported': self._imported, 'errors': self._errors}

    def _validate_row(self, row: dict, row_num: int) -> dict:
        name = str(row.get('name', '')).strip()
        if not name:
            raise ValidationError('El campo "name" es obligatorio.')

        sport = str(row.get('sport', '')).strip()
        country = str(row.get('country', '')).strip()

        try:
            base_priority = int(float(str(row.get('base_priority', '5')).strip() or '5'))
            base_priority = max(1, min(10, base_priority))
        except (ValueError, TypeError):
            base_priority = 5

        raw_active = str(row.get('is_active', 'true')).strip().lower()
        is_active = raw_active not in ('false', '0', 'no', 'inactiva', '')

        return {
            'name': name,
            'sport': sport,
            'country': country,
            'base_priority': base_priority,
            'is_active': is_active,
        }
