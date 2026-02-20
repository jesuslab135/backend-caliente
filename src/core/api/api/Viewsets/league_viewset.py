from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from api.Serializers.league_serializer import LeagueSerializer
from api.models import League
from api.services.importers import LeagueImportService


class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    lookup_field = 'uuid'

    @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_file(self, request):
        """
        POST /api/leagues/import/
        Bulk-import leagues from an Excel (.xlsx/.xls) or CSV file.
        Delegates to LeagueImportService (Strategy Pattern).
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'detail': 'No se proporcionó un archivo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = LeagueImportService(file, file.name)
            result = service.execute()
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        status_code = status.HTTP_201_CREATED if result['imported'] > 0 else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)
