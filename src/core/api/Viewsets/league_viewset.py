import csv
import io

from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from api.Serializers.league_serializer import LeagueSerializer
from api.models import League


class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    lookup_field = 'uuid'

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_file(self, request):
        """
        POST /api/leagues/import/
        Bulk-import leagues from an Excel (.xlsx/.xls) or CSV file.

        Expected columns: name (required), sport, country, base_priority, is_active
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

        imported = 0
        errors = []

        for i, row in enumerate(rows, start=2):  # start=2 because row 1 is header
            name = str(row.get('name', '')).strip()
            if not name:
                errors.append(f'Fila {i}: El campo "name" es obligatorio.')
                continue

            sport = str(row.get('sport', '')).strip()
            country = str(row.get('country', '')).strip()

            # Parse base_priority
            raw_priority = row.get('base_priority', '5')
            try:
                base_priority = int(float(str(raw_priority).strip() or '5'))
                base_priority = max(1, min(10, base_priority))
            except (ValueError, TypeError):
                base_priority = 5

            # Parse is_active
            raw_active = str(row.get('is_active', 'true')).strip().lower()
            is_active = raw_active not in ('false', '0', 'no', 'inactiva', '')

            try:
                League.objects.create(
                    name=name,
                    sport=sport,
                    country=country,
                    base_priority=base_priority,
                    is_active=is_active,
                )
                imported += 1
            except IntegrityError:
                errors.append(f'Fila {i}: La liga "{name}" ya existe.')
            except Exception as e:
                errors.append(f'Fila {i}: {str(e)}')

        return Response(
            {'imported': imported, 'errors': errors},
            status=status.HTTP_201_CREATED if imported > 0 else status.HTTP_400_BAD_REQUEST,
        )

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
                row_dict[col_name] = value if value is not None else ''
            result.append(row_dict)

        wb.close()
        return result
