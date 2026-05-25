# banking_api/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Transaction
from .serializers import TransactionSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    def create(self, request, *args, **kwargs):
        """
        Overrides create to ensure idempotency keys are handled 
        strictly before reaching the model layer.
        """
        serializer = self.get_serializer(data=request.data)
        
        # Proactive Enforcement: If validation fails (e.g., duplicate key),
        # the serializer returns a standard error format.
        if not serializer.is_valid():
            return Response(
                {"status": "error", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save and return the standardized Foundry Envelope
        transaction_obj = serializer.save()
        return Response(
            transaction_obj.to_foundry_envelope(), 
            status=status.HTTP_201_CREATED
        )
        
class AccountBalanceAPIView(APIView):
    """
    GET /api/v1/banking/balance/
    Retrieves the real-time calculated financial balances and ledger metadata.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Placeholder dictionary structure reflecting your core transaction attributes
        telemetry_payload = {
            "status": "success",
            "account_id": request.user.id,  # Tying to the active session user
            "balances": {
                "available_balance": 5250.75,
                "ledger_balance": 5250.75,
                "currency": "USD"
            },
            "compliance_tier": "cleared"
        }
        return Response(telemetry_payload, status=status.HTTP_200_OK)
    
class TransferFundsAPIView(APIView):
    """
    POST /api/v1/banking/transfer/
    Initiates transactional ledger transfers between account entities.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Pinnacle processing stub: mock ledger validation payload
        transfer_payload = {
            "status": "initiated",
            "transaction_reference": "TXN-MOCK-9918237",
            "details": {
                "sender_id": request.user.id,
                "recipient_account_id": request.data.get("recipient_account_id", "unknown"),
                "amount": request.data.get("amount", 0.00),
                "compliance_routing": "SCREENING_CLEARED"
            }
        }
        return Response(transfer_payload, status=status.HTTP_201_CREATED)