from rest_framework import serializers

class ContractAnalysisSerializer(serializers.Serializer):
    contract_file = serializers.FileField(required=True)
    governing_law_target = serializers.CharField(default="California", max_length=100)
    flag_indemnity_caps = serializers.BooleanField(default=True)

class ConflictCheckSerializer(serializers.Serializer):
    adversary_party_name = serializers.CharField(required=True, max_length=255)
    matter_description = serializers.CharField(required=True, max_length=2000)
    risk_tolerance = serializers.ChoiceField(choices=['conservative', 'standard'], default='standard')