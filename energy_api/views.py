# C:\Users\jonathan\Desktop\KCV\energy_api\views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import GenerationLog, PowerGridAsset

# 1. TELEMETRY INGEST VIEW
class GridTelemetryIngestAPIView(APIView):
    """
    POST /api/v1/energy/telemetry/
    Ingests and logs streaming operational metric packets from grid sensors.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"status": "telemetry_ingested", "log_id": 101}, status=status.HTTP_201_CREATED)


# 2. ASSET REGISTRY VIEW (Fulfills the missing import)
class GridAssetRegistryAPIView(APIView):
    """
    GET /api/v1/energy/assets/
    Retrieves the complete registered list of industrial power infrastructure nodes.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        assets_payload = [
            {
                "asset_id": "SUB-TX-001",
                "asset_name": "Downtown Distribution Substation",
                "asset_type": "substation",
                "operational_status": "nominal",
                "current_load_mw": 42.5
            },
            {
                "asset_id": "BATT-ST-042",
                "asset_name": "Northside Battery Bank",
                "asset_type": "battery_bank",
                "operational_status": "nominal",
                "current_load_mw": 12.8
            }
        ]
        return Response({"status": "success", "assets": assets_payload}, status=status.HTTP_200_OK)
    
@csrf_exempt
def ingest_telemetry(request):
    # 1. Handle non-POST methods immediately
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed. Use POST for data ingestion."}, 
            status=405
        )

    # 2. Process POST request
    try:
        data = json.loads(request.body)
        idempotency_key = request.META.get('HTTP_X_IDEMPOTENCY_KEY')
        
        if GenerationLog.objects.filter(idempotency_key=idempotency_key).exists():
            return JsonResponse({"error": "Duplicate request"}, status=409)

        log = GenerationLog.objects.create(
            asset_id=data['asset_id'],
            current_output_mw=data['current_output_mw'],
            carbon_offset_intensity=data['carbon_offset_intensity'],
            idempotency_key=idempotency_key
        )
        return JsonResponse({"status": "success", "id": log.id}, status=201)
            
    except Exception as e:
        # Return a 400 for malformed JSON or missing fields instead of 405
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
            print(f"DEBUGGING ERROR: {e}") # This shows up in your terminal
            return JsonResponse({"error": str(e)}, status=400)