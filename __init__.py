"""
AIMS KTT Hackathon 2026 · S2.T3.1 · AI Math Tutor for Early Learners
Main tutor package
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core import (
    CurriculumLoader,
    ChildASRAdapter,
    ResponseScorer,
    BayesianKnowledgeTracing,
    LearnerState,
    FeedbackGenerator,
    LocalProgressStore,
)

__all__ = [
    "CurriculumLoader",
    "ChildASRAdapter",
    "ResponseScorer",
    "BayesianKnowledgeTracing",
    "LearnerState",
    "FeedbackGenerator",
    "LocalProgressStore",
]
