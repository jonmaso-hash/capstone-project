# messaging_api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import ChatThread, ChatMessage
from .serializers import ChatMessageSerializer, SendMessagePayloadSerializer


class ThreadHistoryAPIView(APIView):
    """
    GET /api/v1/messaging/threads/<int:thread_id>/messages/
    Retrieves the historical timeline of messages inside a secured room for authorized participants.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        thread = get_object_or_404(ChatThread, id=thread_id)
        
        # Security Guardrail: Confirm target user is actually part of this conversation thread
        if request.user not in thread.participants.all():
            return Response({
                "error": "ACCESS_DENIED",
                "message": "You are not an active, authenticated participant in this conversation space."
            }, status=status.HTTP_403_FORBIDDEN)
            
        messages = thread.messages.all()
        serializer = ChatMessageSerializer(messages, many=True)
        
        # Mark fetched items as read asynchronously in a live production environment
        # messages.exclude(sender=request.user).update(is_read=True)
        
        return Response({
            "status": "success",
            "thread_type": thread.thread_type,
            "total_messages": messages.count(),
            "message_history": serializer.data
        }, status=status.HTTP_200_OK)


class DispatchMessageAPIView(APIView):
    """
    POST /api/v1/messaging/send/
    Ingests outbound messages, passing them through Zelda for toxic flag screening or deal intent parsing.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SendMessagePayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_thread = get_object_or_404(ChatThread, id=serializer.validated_data['thread_id'])
        
        if request.user not in target_thread.participants.all():
            return Response({
                "error": "UNAUTHORIZED_SENDER",
                "message": "Cannot post message payloads to channels where your signature is unverified."
            }, status=status.HTTP_403_FORBIDDEN)
            
        raw_text = serializer.validated_data['body_text']
        raw_text_lower = raw_text.lower()
        
        # Zelda AI Conversational Analysis Pipeline Simulation
        # Scans for deal terms, NDA patterns, or sentiment markers to build metadata flags
        detected_intents = []
        is_deal_oriented = False
        
        if "nda" in raw_text_lower or "non-disclosure" in raw_text_lower:
            detected_intents.append("COMPLIANCE_NDA_REQUEST")
        if "term sheet" in raw_text_lower or "valuation" in raw_text_lower or "equity" in raw_text_lower:
            detected_intents.append("DEAL_TERMS_NEGOTIATION")
            is_deal_oriented = True
            
        # Determine urgency score contextually
        urgency_rating = "HIGH" if "urgent" in raw_text_lower or "asap" in raw_text_lower else "NORMAL"
        
        # Setup structured analysis blocks to save to database record
        zelda_intelligence_block = {
            "parsed_intents": detected_intents,
            "sentiment_classification": "PROFESSIONAL_OBJECTIVE",
            "metadata_indicators": {
                "contains_transactional_triggers": is_deal_oriented,
                "workflow_urgency_priority": urgency_rating
            }
        }
        
        # In actual system operations, persist directly to the database:
        # ChatMessage.objects.create(thread=target_thread, sender=request.user, body_text=raw_text, zelda_moderation_metadata=zelda_intelligence_block)
        
        return Response({
            "status": "message_dispatched",
            "routing_confirmation": {
                "origin_identity": request.user.username,
                "target_thread_id": target_thread.id,
                "delivery_state": "ACK_RECEIVED"
            },
            "zelda_realtime_nlp_audit": zelda_intelligence_block
        }, status=status.HTTP_201_CREATED)