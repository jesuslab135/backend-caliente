from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

from api.models import League, SportEvent
from .base import BaseFileParser


class SportEventImportService:
    """
    Orchestrates sport event import from CSV/Excel files.

    Responsibilities:
    - Selects file parser via Strategy Pattern (BaseFileParser.get_parser)
    - Validates each row and normalizes data
    - Auto-creates leagues that don't exist yet
    - Creates SportEvent records
    - Accumulates errors per row for user feedback
    """

    COLUMN_ALIASES = {
        'league': 'league', 'league_name': 'league', 'liga': 'league',
        'sport': 'sport', 'deporte': 'sport',
        'country': 'country', 'pais': 'country', 'país': 'country',
        'date': 'date', 'fecha': 'date', 'date_start': 'date',
        'date_end': 'date_end', 'fecha_fin': 'date_end',
        'time': 'time', 'hora': 'time',
        'home team': 'home_team', 'home_team': 'home_team', 'home': 'home_team', 'equipo local': 'home_team',
        'away team': 'away_team', 'away_team': 'away_team', 'away': 'away_team', 'equipo visitante': 'away_team',
        'priority': 'priority', 'prioridad': 'priority',
        'name': 'name', 'nombre': 'name',
        'description': 'description', 'descripcion': 'description', 'descripción': 'description',
    }

    DATE_FORMATS = [
        '%d.%m.%Y',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
    ]

    def __init__(self, file, filename: str):
        self._parser = BaseFileParser.get_parser(filename)
        self._file = file
        self._imported = 0
        self._errors: list[str] = []
        self._league_cache: dict[str, League] = {}

    def execute(self) -> dict:
        """Main entry point. Parse file, validate rows, persist events."""
        rows = self._parser.parse(self._file)
        self._build_league_cache()

        for i, raw_row in enumerate(rows, start=2):
            row = self._normalize_columns(raw_row)
            try:
                event_data = self._validate_row(row, i)
                self._create_event(event_data)
                self._imported += 1
            except ValidationError as e:
                self._errors.append(f'Fila {i}: {e.message}')

        return {'imported': self._imported, 'errors': self._errors}

    def _build_league_cache(self):
        """Pre-fetch all leagues keyed by lowercase name for O(1) lookup."""
        for league in League.objects.all():
            self._league_cache[league.name.strip().lower()] = league

    def _normalize_columns(self, row: dict) -> dict:
        """Map aliased column names to canonical names."""
        normalized = {}
        for key, value in row.items():
            canonical = self.COLUMN_ALIASES.get(key.strip().lower(), key.strip().lower())
            normalized[canonical] = str(value).strip() if value else ''
        return normalized

    def _validate_row(self, row: dict, row_num: int) -> dict:
        """Validate a single row and return normalized data for creation."""
        league_name = row.get('league', '')
        if not league_name:
            raise ValidationError('El campo "league" es obligatorio.')

        sport = row.get('sport', '')
        country = row.get('country', '')
        league = self._get_or_create_league(league_name, sport, country)

        home_team = row.get('home_team', '')
        away_team = row.get('away_team', '')

        name = row.get('name', '')
        if not name:
            if home_team and away_team:
                name = f"{home_team} vs {away_team}"
            else:
                raise ValidationError('Se requiere "name" o ambos "home_team" y "away_team".')

        date_str = row.get('date', '')
        time_str = row.get('time', '')
        if not date_str:
            raise ValidationError('El campo "date" es obligatorio.')

        date_start = self._parse_datetime(date_str, time_str)
        if not date_start:
            raise ValidationError(f'Formato de fecha no reconocido: "{date_str} {time_str}".')

        priority = self._parse_priority(row.get('priority', '5'))

        date_end_str = row.get('date_end', '')
        date_end = self._parse_datetime(date_end_str, '') if date_end_str else None

        description = row.get('description', '')

        data = {
            'league': league,
            'name': name,
            'date_start': date_start,
            'home_team': home_team,
            'away_team': away_team,
            'priority': priority,
        }
        if date_end:
            data['date_end'] = date_end
        if description:
            data['description'] = description

        return data

    def _get_or_create_league(self, name: str, sport: str, country: str) -> League:
        """Return cached league or auto-create a new one."""
        key = name.strip().lower()
        if key not in self._league_cache:
            league = League.objects.create(
                name=name.strip(),
                sport=sport,
                country=country,
                base_priority=5,
            )
            self._league_cache[key] = league
        return self._league_cache[key]

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime | None:
        """Combine date and time strings into a timezone-aware datetime."""
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                if time_str and '%H' not in fmt:
                    try:
                        t = datetime.strptime(time_str, '%H:%M')
                        dt = dt.replace(hour=t.hour, minute=t.minute)
                    except ValueError:
                        pass
                return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except ValueError:
                continue
        return None

    def _parse_priority(self, value: str) -> int:
        """Parse priority string, default 5, clamped 1-10."""
        try:
            p = int(float(value or '5'))
            return max(1, min(10, p))
        except (ValueError, TypeError):
            return 5

    def _create_event(self, data: dict):
        """Persist a single SportEvent."""
        SportEvent.objects.create(**data)
