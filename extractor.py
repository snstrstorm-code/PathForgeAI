import re
import pdfplumber
import spacy
from spacy.matcher import PhraseMatcher

class ResumeSkillExtractor:
    def __init__(self, skill_database: list[str]):
        # Load lightweight spacy model for NLP parsing
        self.nlp = spacy.load("en_core_web_sm")
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        
        # Build phrase matcher patterns from skill taxonomy database
        patterns = [self.nlp.make_doc(skill) for skill in skill_database]
        self.matcher.add("SKILL_PATTERN", patterns)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text

    def extract_skills_with_context(self, text: str) -> dict:
        doc = self.nlp(text)
        matches = self.matcher(doc)
        
        extracted_data = {}
        
        for match_id, start, end in matches:
            span = doc[start:end]
            skill_name = span.text.title()
            
            # Sentence context surrounding the identified skill
            sentence = span.sent.text.strip()
            
            if skill_name not in extracted_data:
                extracted_data[skill_name] = {
                    "count": 1,
                    "contexts": [sentence]
                }
            else:
                extracted_data[skill_name]["count"] += 1
                if sentence not in extracted_data[skill_name]["contexts"]:
                    extracted_data[skill_name]["contexts"].append(sentence)
                    
        return extracted_data
