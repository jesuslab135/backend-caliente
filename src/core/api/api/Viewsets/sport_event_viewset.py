from collections import defaultdict

from django.utils.dateparse import parse_date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from api.Serializers.sport_event_serializer import SportEventSerializer
from api.models import SportEvent, League
from api.services.importers import SportEventImportService


class SportEventViewSet(viewsets.ModelViewSet):
    queryset = SportEvent.objects.select_related('league').all()
    serializer_class = SportEventSerializer
    lookup_field = 'uuid'

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_file(self, request):
        """
        POST /api/sportevents/import/
        Bulk-import sport events from an Excel (.xlsx/.xls) or CSV file.
        Delegates to SportEventImportService (Strategy Pattern).
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'detail': 'No se proporcionó un archivo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = SportEventImportService(file, file.name)
            result = service.execute()
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        status_code = status.HTTP_201_CREATED if result['imported'] > 0 else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)

    @action(detail=False, methods=['get'], url_path='calendar/month')
    def calendar_month(self, request):
        """
        GET /api/sportevents/calendar/month/?year=2026&month=2&sport=Soccer&league=NBA
        Returns per-day sport counts for the calendar month view.
        """
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not year or not month:
            return Response(
                {'detail': 'Parámetros "year" y "month" son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year, month = int(year), int(month)
        except (ValueError, TypeError):
            return Response(
                {'detail': '"year" y "month" deben ser números enteros.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = SportEvent.objects.filter(
            date_start__year=year,
            date_start__month=month,
        ).select_related('league')

        sport = request.query_params.get('sport')
        league = request.query_params.get('league')
        if sport:
            qs = qs.filter(league__sport__iexact=sport)
        if league:
            qs = qs.filter(league__name__iexact=league)

        result = defaultdict(lambda: defaultdict(int))
        for event in qs.only('date_start', 'league__sport'):
            date_key = event.date_start.strftime('%Y-%m-%d')
            sport_name = event.league.sport
            result[date_key][sport_name] += 1

        data = {}
        for date_key, sports in result.items():
            data[date_key] = [
                {'sport': sport_name, 'count': count}
                for sport_name, count in sorted(sports.items())
            ]

        return Response(data)

    @action(detail=False, methods=['get'], url_path='calendar/day')
    def calendar_day(self, request):
        """
        GET /api/sportevents/calendar/day/?date=2026-02-04&sport=Soccer&league=NBA
        Returns events grouped by hour for the day timeline view.
        """
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {'detail': 'Parámetro "date" es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date = parse_date(date_str)
        if not date:
            return Response(
                {'detail': 'Formato de fecha inválido. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = SportEvent.objects.filter(
            date_start__date=date,
        ).select_related('league').order_by('date_start')

        sport = request.query_params.get('sport')
        league = request.query_params.get('league')
        if sport:
            qs = qs.filter(league__sport__iexact=sport)
        if league:
            qs = qs.filter(league__name__iexact=league)

        result = defaultdict(list)
        for event in qs:
            hour_key = event.date_start.strftime('%H')
            result[hour_key].append({
                'uuid': str(event.uuid),
                'name': event.name,
                'display_name': event.display_name,
                'league': event.league.name,
                'sport': event.league.sport,
                'home_team': event.home_team,
                'away_team': event.away_team,
                'time': event.date_start.strftime('%H:%M'),
                'priority': event.priority,
            })

        return Response(dict(result))

    @action(detail=False, methods=['post'], url_path='scrape')
    def scrape_flashscore(self, request):
        """
        POST /api/sportevents/scrape/
        Trigger the Flashscore scraper to auto-import upcoming events.
        Optional body: {"urls": ["https://www.flashscore.com/football/spain/laliga/fixtures/"]}
        Deduplicates: only imports events not already in the database.
        """
        from api.management.commands.scrape_flashscore import run_scraper

        urls = request.data.get('urls', None)
        result = run_scraper(urls=urls)

        if result['imported'] > 0:
            status_code = status.HTTP_201_CREATED
        elif result.get('skipped', 0) > 0:
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return Response(result, status=status_code)

    @action(detail=False, methods=['get'], url_path='sports')
    def available_sports(self, request):
        """
        GET /api/sportevents/sports/
        Returns distinct sport names from active leagues that have events.
        """
        sports = (
            League.objects
            .filter(is_active=True, events__isnull=False)
            .exclude(sport='')
            .values_list('sport', flat=True)
            .distinct()
            .order_by('sport')
        )
        return Response(list(sports))
