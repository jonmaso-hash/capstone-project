from django.urls import path
from .views import PropertyMatchRadarAPIView, OMOpticalUnderwriterAPIView

# 'app_name' provides a namespace so you can reverse URLs as 'real_estate_api:property_match'
app_name = 'real_estate_api'

urlpatterns = [
    path('match/', PropertyMatchRadarAPIView.as_view(), name='property_match'),
    path('documents/underwrite/', OMOpticalUnderwriterAPIView.as_view(), name='om_underwrite'),
]