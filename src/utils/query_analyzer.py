import re
import structlog
from typing import Optional, List, Dict, Any

logger = structlog.get_logger(__name__)


class QueryAnalyzer:
    @staticmethod
    def is_educational_query(query: str) -> bool:
        educational_keywords = [
            "mcq", "questions", "quiz", "test", "exam", "assessment",
            "generate", "create questions", "multiple choice", "true false",
            "practice questions", "mock test", "sample questions",
            "exercise", "problem", "worksheet"
        ]
        query_lower = query.lower().strip()
        return any(keyword in query_lower for keyword in educational_keywords)

    @staticmethod
    def detect_complexity_level(query: str) -> str:
        query_lower = query.lower().strip()

        jee_keywords = ["jee", "jee advanced", "iit", "competitive", "entrance"]
        if any(keyword in query_lower for keyword in jee_keywords):
            return "jee_advanced"

        advanced_keywords = ["advanced", "difficult", "complex", "challenging", "hard"]
        if any(keyword in query_lower for keyword in advanced_keywords):
            return "advanced"

        basic_keywords = ["basic", "easy", "simple", "beginner", "fundamental", "elementary"]
        if any(keyword in query_lower for keyword in basic_keywords):
            return "basic"

        return "intermediate"

    @staticmethod
    def extract_question_count(query: str) -> Optional[int]:
        patterns = [
            r'(\d+)\s*(?:questions?|mcqs?|problems?|exercises?)',
            r'(?:generate|create|make)\s*(\d+)',
            r'(\d+)\s*(?:multiple\s*choice|true\s*false)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                try:
                    count = int(match.group(1))
                    if 1 <= count <= 50:
                        return count
                except ValueError:
                    continue
        return None

    @staticmethod
    def detect_question_types(query: str) -> List[str]:
        query_lower = query.lower().strip()
        detected_types = []

        mcq_patterns = ["mcq", "multiple choice", "multiple-choice", "choices", "options"]
        if any(pattern in query_lower for pattern in mcq_patterns):
            detected_types.append("multiple_choice")

        tf_patterns = ["true false", "true/false", "t/f", "true or false"]
        if any(pattern in query_lower for pattern in tf_patterns):
            detected_types.append("true_false")

        sa_patterns = ["short answer", "brief answer", "explain", "describe", "write about"]
        if any(pattern in query_lower for pattern in sa_patterns):
            detected_types.append("short_answer")

        if not detected_types:
            detected_types.append("multiple_choice")

        return detected_types

    @staticmethod
    def detect_subject_area(query: str, context: str = "") -> str:
        combined_text = f"{query} {context}".lower()

        subject_areas = {
            "mechanics": [
                "force", "motion", "velocity", "acceleration", "newton",
                "momentum", "collision", "friction", "gravity", "projectile"
            ],
            "thermodynamics": [
                "heat", "temperature", "entropy", "thermal", "gas law",
                "carnot", "efficiency", "work", "energy transfer"
            ],
            "electromagnetism": [
                "electric", "magnetic", "current", "voltage", "resistance",
                "capacitor", "inductor", "electromagnetic", "circuit"
            ],
            "optics": [
                "light", "reflection", "refraction", "lens", "mirror",
                "wavelength", "interference", "diffraction", "prism"
            ],
            "modern_physics": [
                "quantum", "relativity", "atom", "nuclear", "photon",
                "electron", "proton", "radioactive", "particle"
            ],
            "waves": [
                "wave", "frequency", "amplitude", "sound", "vibration",
                "oscillation", "resonance", "standing wave"
            ]
        }

        for area, keywords in subject_areas.items():
            if any(keyword in combined_text for keyword in keywords):
                return area

        return "general_physics"

    @staticmethod
    def detect_query_intent(query: str) -> Optional[str]:
        query_lower = query.lower().strip()

        concept_patterns = [
            r'^what (is|are|does|do)', r'^explain', r'^define', r'^describe',
            r'definition of', r'meaning of', r'concept of', r'understanding', r'tell me about'
        ]

        for pattern in concept_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "concept"

        example_patterns = ['example', 'show me', 'demonstrate', 'illustration', 'sample', 'case study']
        for pattern in example_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "example"

        question_patterns = [
            r'^how (do|to|can)', r'^solve', r'^calculate', r'^find',
            r'^determine', r'practice', r'exercise', r'problem'
        ]

        for pattern in question_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "question"

        return None

    @staticmethod
    def analyze_query_comprehensive(query: str, context: str = "") -> Dict[str, Any]:
        analysis = {
            "original_query": query,
            "is_educational": QueryAnalyzer.is_educational_query(query),
            "complexity_level": QueryAnalyzer.detect_complexity_level(query),
            "question_count": QueryAnalyzer.extract_question_count(query),
            "question_types": QueryAnalyzer.detect_question_types(query),
            "subject_area": QueryAnalyzer.detect_subject_area(query, context),
            "query_intent": QueryAnalyzer.detect_query_intent(query),
            "is_jee_focused": "jee" in query.lower() or "iit" in query.lower(),
            "requires_structured_response": True
        }

        if not analysis["is_educational"]:
            analysis["requires_structured_response"] = False

        if analysis["is_educational"] and analysis["question_count"] is None:
            analysis["question_count"] = 5

        return analysis

    @staticmethod
    def classify_question_type_from_options(options: List[str]) -> str:
        if not options or len(options) == 0:
            return "short_answer"
        elif len(options) == 2:
            option_texts = [opt.lower().strip() for opt in options]
            tf_variations = [
                ["true", "false"], ["yes", "no"],
                ["correct", "incorrect"], ["right", "wrong"]
            ]

            for tf_pair in tf_variations:
                if set(option_texts) == set(tf_pair):
                    return "true_false"

            return "multiple_choice"
        else:
            return "multiple_choice"

    @staticmethod
    def extract_physics_topics(text: str) -> List[str]:
        physics_topics = {
            "Newton's Laws": ["newton", "newton's law", "force", "f=ma"],
            "Kinematics": ["velocity", "acceleration", "displacement", "motion"],
            "Work and Energy": ["work", "energy", "kinetic", "potential"],
            "Momentum": ["momentum", "collision", "conservation"],
            "Rotational Motion": ["angular", "torque", "rotational", "moment of inertia"],
            "Heat Transfer": ["heat", "conduction", "convection", "radiation"],
            "Gas Laws": ["ideal gas", "boyle", "charles", "gay-lussac"],
            "Thermodynamic Processes": ["isothermal", "adiabatic", "isobaric"],
            "Electric Fields": ["electric field", "coulomb", "gauss"],
            "Magnetic Fields": ["magnetic field", "ampere", "faraday"],
            "Circuits": ["circuit", "ohm", "resistance", "capacitance"],
            "Wave Motion": ["wave", "frequency", "wavelength", "amplitude"],
            "Optics": ["reflection", "refraction", "lens", "mirror"],
            "Quantum Physics": ["quantum", "photon", "planck", "de broglie"],
            "Relativity": ["relativity", "einstein", "spacetime"]
        }

        text_lower = text.lower()
        found_topics = []

        for topic, keywords in physics_topics.items():
            if any(keyword in text_lower for keyword in keywords):
                found_topics.append(topic)

        return found_topics