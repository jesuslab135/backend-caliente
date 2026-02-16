import csv
import io
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from api.Serializers.sport_event_serializer import SportEventSerializer
from api.models import SportEvent, League


class SportEventViewSet(viewsets.ModelViewSet):
    queryset = SportEvent.objects.all()
    serializer_class = SportEventSerializer
    lookup_field = 'uuid'

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_file(self, request):
        """
        POST /api/sportevents/import/
        Bulk-import sport events from an Excel (.xlsx/.xls) or CSV file.

        Expected columns: league_name (required), name (required), date_start (required),
                          date_end, priority, description
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'detail': 'No se proporcionó un archivo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = file.name.lower()
        try:
            if filename.endswith('.csv'):
                rows = self._parse_csv(file)
            elif filename.endswith(('.xlsx', '.xls')):
                rows = self._parse_excel(file)
            else:
                return Response(
                    {'detail': 'Formato no soportado. Use .xlsx, .xls o .csv'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {'detail': f'Error al leer el archivo: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-fetch all leagues keyed by lowercase name for fast lookup
        league_map = {}
        for league in League.objects.all():
            league_map[league.name.strip().lower()] = league

        imported = 0
        errors = []

        for i, row in enumerate(rows, start=2):  # start=2 because row 1 is header
            # --- league_name (required, FK lookup) ---
            league_name = str(row.get('league_name', '')).strip()
            if not league_name:
                errors.append(f'Fila {i}: El campo "league_name" es obligatorio.')
                continue

            league = league_map.get(league_name.lower())
            if not league:
                errors.append(f'Fila {i}: No se encontró la liga "{league_name}".')
                continue

            # --- name (required) ---
            name = str(row.get('name', '')).strip()
            if not name:
                errors.append(f'Fila {i}: El campo "name" es obligatorio.')
                continue

            # --- date_start (required) ---
            raw_date_start = str(row.get('date_start', '')).strip()
            date_start = self._parse_date(raw_date_start)
            if not date_start:
                errors.append(f'Fila {i}: El campo "date_start" es obligatorio y debe ser una fecha válida (YYYY-MM-DD HH:MM).')
                continue

            # --- date_end (optional) ---
            raw_date_end = str(row.get('date_end', '')).strip()
            date_end = self._parse_date(raw_date_end) if raw_date_end else None

            # --- priority (optional, default 5, clamped 1-10) ---
            raw_priority = row.get('priority', '5')
            try:
                priority = int(float(str(raw_priority).strip() or '5'))
                priority = max(1, min(10, priority))
            except (ValueError, TypeError):
                priority = 5

            # --- description (optional) ---
            description = str(row.get('description', '')).strip()

            try:
                SportEvent.objects.create(
                    league=league,
                    name=name,
                    date_start=date_start,
                    date_end=date_end,
                    priority=priority,
                    description=description,
                )
                imported += 1
            except Exception as e:
                errors.append(f'Fila {i}: {str(e)}')

        return Response(
            {'imported': imported, 'errors': errors},
            status=status.HTTP_201_CREATED if imported > 0 else status.HTTP_400_BAD_REQUEST,
        )

    def _parse_date(self, value):
        """Try multiple date formats and return a datetime or None."""
        if not value:
            return None

        # Try Django's parse_datetime first (handles ISO 8601)
        result = parse_datetime(value)
        if result:
            return result if timezone.is_aware(result) else timezone.make_aware(result)

        # Try common formats, make timezone-aware
        for fmt in (
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%d',
        ):
            try:
                dt = datetime.strptime(value, fmt)
                return timezone.make_aware(dt)
            except ValueError:
                continue

        return None

    def _parse_csv(self, file):
        """Parse a CSV file and return list of row dicts."""
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        return list(reader)

    def _parse_excel(self, file):
        """Parse an Excel file and return list of row dicts."""
        import openpyxl

        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if not header:
            return []

        # Normalize header names: strip, lowercase
        header = [str(h).strip().lower() if h else '' for h in header]

        result = []
        for row_values in rows_iter:
            if all(v is None for v in row_values):
                continue  # skip empty rows
            row_dict = {}
            for col_name, value in zip(header, row_values):
                # Convert datetime objects to string for uniform handling
                if isinstance(value, datetime):
                    row_dict[col_name] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    row_dict[col_name] = value if value is not None else ''
            result.append(row_dict)

        wb.close()
        return result
