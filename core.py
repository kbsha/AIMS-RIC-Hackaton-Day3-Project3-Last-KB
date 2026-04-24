"""
Core tutor components: curriculum, ASR, scoring, knowledge tracing, storage.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, Optional
import numpy as np


# ============================================================================
# PART 1: CURRICULUM LOADER
# ============================================================================

class CurriculumLoader:
    """Load and manage math curriculum items."""
    
    def __init__(self, curriculum_path: str = "tutor/data/curriculum.json"):
        """Load curriculum from JSON file."""
        try:
            with open(curriculum_path, 'r') as f:
                self.items = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Curriculum file not found: {curriculum_path}")
            self.items = []
        
        # Index by skill
        self.by_skill = {}
        for item in self.items:
            skill = item.get('skill', 'unknown')
            if skill not in self.by_skill:
                self.by_skill[skill] = []
            self.by_skill[skill].append(item)
        
        # Sort by difficulty
        for skill in self.by_skill:
            self.by_skill[skill].sort(key=lambda x: x.get('difficulty', 0))
    
    def get_item_by_id(self, item_id: str) -> Optional[Dict]:
        """Fetch a single item by ID."""
        for item in self.items:
            if item.get('id') == item_id:
                return item
        return None
    
    def get_initial_item(self) -> Optional[Dict]:
        """Return the easiest item (difficulty 1)."""
        for item in self.items:
            if item.get('difficulty') == 1:
                return item
        return self.items[0] if self.items else None
    
    def get_next_item(self, skill: str, current_difficulty: int) -> Optional[Dict]:
        """Get next item above current difficulty."""
        candidates = [
            item for item in self.by_skill.get(skill, [])
            if item.get('difficulty', 0) > current_difficulty
        ]
        return candidates[0] if candidates else None


# ============================================================================
# PART 2: ASR + LANGUAGE DETECTION
# ============================================================================

class ChildASRAdapter:
    """Transcribe and detect language."""
    
    def __init__(self):
        """Initialize ASR adapter."""
        try:
            import whisper
            self.model = whisper.load_model("tiny")
            self.asr_available = True
        except (ImportError, Exception) as e:
            print(f"⚠️ Whisper not available: {e}")
            self.model = None
            self.asr_available = False
        
        self.language_keywords = {
            'en': ['one', 'two', 'three', 'four', 'five', 'apple', 'goat', 'yes'],
            'fr': ['un', 'deux', 'trois', 'quatre', 'cinq', 'pomme', 'chèvre', 'oui'],
            'kin': ['rimwe', 'kabiri', 'gatatu', 'ine', 'itanu', 'pome', 'ihene', 'yego']
        }
    
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        """Transcribe audio using Whisper."""
        if not self.asr_available or self.model is None:
            return "[ASR disabled]"
        
        try:
            result = self.model.transcribe(audio_path, language=language)
            return result['text'].strip().lower()
        except Exception as e:
            print(f"⚠️ ASR error: {e}")
            return ""
    
    def detect_language(self, transcript: str) -> str:
        """Detect language from transcript."""
        if not transcript:
            return 'en'
        
        scores = {lang: 0 for lang in ['en', 'fr', 'kin']}
        transcript_lower = transcript.lower()
        
        for lang, keywords in self.language_keywords.items():
            scores[lang] = sum(1 for kw in keywords if kw in transcript_lower)
        
        detected = [lang for lang, score in scores.items() if score > 0]
        
        if len(detected) > 1:
            return 'mixed'
        elif detected:
            return detected[0]
        else:
            return 'en'


# ============================================================================
# PART 3: SCORING
# ============================================================================

class ResponseScorer:
    """Score child responses."""
    
    @staticmethod
    def score_response(expected_answer: int, transcript: str, item: Dict = None) -> bool:
        """Determine if response is correct."""
        
        number_words = {
            'en': {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'},
            'fr': {1: 'un', 2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq'},
            'kin': {1: 'rimwe', 2: 'kabiri', 3: 'gatatu', 4: 'ine', 5: 'itanu'}
        }
        
        transcript_lower = transcript.lower()
        
        for lang, words in number_words.items():
            if expected_answer in words:
                if words[expected_answer] in transcript_lower:
                    return True
        
        if str(expected_answer) in transcript_lower:
            return True
        
        return False


# ============================================================================
# PART 4: KNOWLEDGE TRACING
# ============================================================================

class BayesianKnowledgeTracing:
    """Bayesian Knowledge Tracing model."""
    
    def __init__(self, skill: str, p_init: float = 0.1, p_g: float = 0.25,
                 p_s: float = 0.05, p_t: float = 0.1):
        """Initialize BKT for a skill."""
        self.skill = skill
        self.p_init = p_init
        self.p_g = p_g
        self.p_s = p_s
        self.p_t = p_t
        self.p_learned = p_init
        self.history = []
    
    def update(self, correct: bool) -> float:
        """Update P(learned) based on response."""
        
        if correct:
            p_correct = (self.p_learned * (1 - self.p_s)) + \
                       ((1 - self.p_learned) * self.p_g)
        else:
            p_correct = (self.p_learned * self.p_s) + \
                       ((1 - self.p_learned) * (1 - self.p_g))
        
        if p_correct < 1e-10:
            return self.p_learned
        
        if correct:
            posterior = (self.p_learned * (1 - self.p_s)) / p_correct
        else:
            posterior = (self.p_learned * self.p_s) / p_correct
        
        self.p_learned = posterior + ((1 - posterior) * self.p_t)
        self.p_learned = np.clip(self.p_learned, 0, 1)
        
        self.history.append({
            'correct': correct,
            'p_learned': self.p_learned
        })
        
        return self.p_learned
    
    def predict_next_response(self) -> float:
        """Predict P(next response is correct)."""
        return (self.p_learned * (1 - self.p_s)) + \
               ((1 - self.p_learned) * self.p_g)
    
    def next_item_difficulty(self) -> int:
        """Recommend difficulty change: -1, 0, or +1."""
        if self.p_learned > 0.85:
            return +1
        elif self.p_learned < 0.3:
            return -1
        else:
            return 0


class LearnerState:
    """Track learner's knowledge across all skills."""
    
    def __init__(self, learner_id: str):
        """Initialize learner."""
        self.learner_id = learner_id
        self.skills = {
            'counting': BayesianKnowledgeTracing('counting'),
            'addition': BayesianKnowledgeTracing('addition'),
            'subtraction': BayesianKnowledgeTracing('subtraction'),
            'number_sense': BayesianKnowledgeTracing('number_sense'),
            'word_problem': BayesianKnowledgeTracing('word_problem'),
        }
        self.current_skill = 'counting'
        self.response_count = 0
    
    def record_response(self, skill: str, correct: bool):
        """Update BKT model."""
        if skill in self.skills:
            self.skills[skill].update(correct)
            self.response_count += 1
    
    def get_next_item_difficulty(self, skill: str) -> int:
        """Get recommended difficulty change."""
        if skill in self.skills:
            return self.skills[skill].next_item_difficulty()
        return 0


# ============================================================================
# PART 5: FEEDBACK GENERATION
# ============================================================================

class FeedbackGenerator:
    """Generate multilingual feedback."""
    
    @staticmethod
    def generate_feedback(correct: bool, language: str, expected_answer: int) -> str:
        """Generate feedback."""
        
        templates = {
            ('en', True): "Correct! Very good!",
            ('en', False): f"Not quite. The answer is {expected_answer}.",
            ('fr', True): "Correct! Très bien!",
            ('fr', False): f"Non. La réponse est {expected_answer}.",
            ('kin', True): "Wembe! Neza cyane!",
            ('kin', False): f"Ntabwo. Igisubizo ni {expected_answer}.",
        }
        
        key = (language if language in ['en', 'fr', 'kin'] else 'en', correct)
        return templates.get(key, templates[('en', correct)])


# ============================================================================
# PART 6: LOCAL STORAGE
# ============================================================================

class LocalProgressStore:
    """Store learner progress in SQLite."""
    
    def __init__(self, db_path: str = "tutor/data/progress.db"):
        """Initialize SQLite database."""
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS learners (
                learner_id TEXT PRIMARY KEY,
                name TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                response_id INTEGER PRIMARY KEY,
                learner_id TEXT,
                skill TEXT,
                item_id TEXT,
                correct BOOLEAN,
                transcript TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY(learner_id) REFERENCES learners(learner_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_learner(self, learner_id: str, name: str, language: str = 'en'):
        """Register a learner."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            'INSERT OR IGNORE INTO learners VALUES (?, ?, ?, ?)',
            (learner_id, name, language, datetime.now())
        )
        
        conn.commit()
        conn.close()
    
    def add_response(self, learner_id: str, skill: str, item_id: str,
                     correct: bool, transcript: str):
        """Log a response."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            'INSERT INTO responses VALUES (NULL, ?, ?, ?, ?, ?, ?)',
            (learner_id, skill, item_id, correct, transcript, datetime.now())
        )
        
        conn.commit()
        conn.close()
    
    def get_stats(self, learner_id: str) -> Dict:
        """Get learner stats."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT skill, COUNT(*) as attempts, SUM(correct) as correct_count
            FROM responses
            WHERE learner_id = ?
            GROUP BY skill
        ''', (learner_id,))
        
        rows = c.fetchall()
        conn.close()
        
        stats = {}
        for skill, attempts, correct_count in rows:
            accuracy = correct_count / attempts if attempts > 0 else 0
            stats[skill] = {
                'accuracy': accuracy,
                'attempts': attempts,
                'correct': correct_count
            }
        
        return stats
