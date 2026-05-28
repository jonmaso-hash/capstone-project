"""
Core matching logic has been centralized into matchmaking/utils.py 
to resolve model attribute errors and deduplicate scoring functions.

This file remains as an explicit pass-through layer to maintain backwards 
compatibility and prevent import errors across background tasks or tests.
"""

from .utils import (
    calculate_match_score,
    calculate_rule_based_score,
    get_blended_match
)