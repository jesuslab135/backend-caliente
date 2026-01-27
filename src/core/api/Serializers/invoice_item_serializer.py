from rest_framework import serializers
from api.models import InvoiceItem

class InvoiceItemSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = '__all__'