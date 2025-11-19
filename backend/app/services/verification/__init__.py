"""
Verification Service Package

Services for verifying Facebook posts against retrieved news articles
using NLI (Natural Language Inference) techniques.
"""

from app.services.verification.claim_evidence_mapper import ClaimEvidenceMapper
from app.services.verification.explanation_generator import ExplanationGenerator
from app.services.verification.stance_classifier import StanceClassifier
from app.services.verification.verdict_aggregator import VerdictAggregator
from app.services.verification.verification_service import VerificationService

__all__ = [
    "ClaimEvidenceMapper",
    "StanceClassifier",
    "VerdictAggregator",
    "ExplanationGenerator",
    "VerificationService",
]
