from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
# Assuming your scan function is in a utility file, e.g., utils.py
from .utils import scan_pitch_deck 

class SandboxScanView(APIView):
    permission_classes = [AllowAny] # No auth required

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded"}, status=400)
        
        # Call the logic directly
        try:
            result = scan_pitch_deck(file) 
            return Response({
                "status": "success",
                "extracted_data": result
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)