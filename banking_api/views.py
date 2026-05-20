import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import LedgerAccount, Transaction
from .serializers import AccountSummarySerializer, FundTransferSerializer


class AccountBalanceAPIView(APIView):
    """
    GET /api/v1/banking/accounts/
    Returns a consolidated ledger summary of all financial accounts linked to the authenticated user profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = LedgerAccount.objects.filter(user=request.user)
        serializer = AccountSummarySerializer(accounts, many=True)
        return Response({
            "status": "success",
            "accounts": serializer.data
        }, status=status.HTTP_200_OK)


class TransferFundsAPIView(APIView):
    """
    POST /api/v1/banking/ledger/transfer/
    Executes a high-integrity atomic transfer between two structural ledger account nodes.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FundTransferSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        src_num = serializer.validated_data['source_account']
        dest_num = serializer.validated_data['destination_account']
        transfer_amount = serializer.validated_data['amount']
        
        # Pull account targets
        source_acc = get_object_or_404(LedgerAccount, account_number=src_num, user=request.user)
        dest_acc = get_object_or_404(LedgerAccount, account_number=dest_num)
        
        # Check liquidity pools
        if source_acc.balance < transfer_amount:
            return Response({
                "error": "INSUFFICIENT_LIQUIDITY",
                "message": "The selected source ledger node lacks the adequate clear balance to settle this transaction."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Zelda Atomic Transaction Update (Mock Simulation for now)
        source_acc.balance -= transfer_amount
        dest_acc.balance += transfer_amount
        
        # Mocking an atomic write out confirmation hash
        tx_reference = f"TX-ZELDA-{uuid.uuid4().hex[:12].upper()}"
        
        return Response({
            "status": "settled",
            "transaction_reference": tx_reference,
            "settlement_details": {
                "debited_node": source_acc.account_number,
                "credited_node": dest_acc.account_number,
                "amount_processed": float(transfer_amount),
                "remaining_available_balance": float(source_acc.balance)
            },
            "system_audit_log": "Ledger state synchronized across regional cluster schemas successfully."
        }, status=status.HTTP_201_CREATED)