import fitz  # PyMuPDF
from groq import Groq
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class StoryDirector : 
    """The AI Agent that character, emotions and scene changes from the text"""

    def analyze_scene(self, text_snippet, previous_context=""):
        prompt = f"""
        You are a professional audiobook director analyzing a scene. 
        
        CONTEXT: {previous_context}
        
        TEXT: '{text_snippet}'
        
        Analyze and return ONLY a JSON object with these keys:
        - "scene_type": (narration, dialogue, description, action)
        - "primary_character": (narrator, male_character, female_character, child, etc.)
        - "character_gender": (male, female, neutral)
        - "character_age": (child, young_adult, adult, elderly)
        - "emotion": (neutral, joyful, terrified, angry, excited, sad, mysterious)
        - "pitch": (low, medium, high)
        - "pace": (slow, normal, fast)
        - "voice_type": (deep_male, soft_female, child_like, authoritative, storyteller)
        - "is_dialogue": (true/false)
        - "speaking_character_name": (if dialogue, who's speaking)
        """
        response = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature = 0.7
        )
        result = json.loads(response.choices[0].message.content)
        return result

    def detect_chapters(self, full_text):
        """Detect chapter boundaries in text"""
        chapter_patterns = [
            r'CHAPTER\s+\d+[\.\s]',
            r'Chapter\s+\d+[\.\s]',
            r'\n\d+\.\s+',  # Numbered chapters: "1. "
            r'\n[A-Z][A-Z\s]+\n',  # All caps titles
        ]
        chapters = []
        current_chapter = {"title": "Prologue", "content": "", "start": 0}
        
        lines = full_text.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check for chapter headings
            is_chapter = False
            for pattern in chapter_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_chapter = True
                    break
                
             # Check for common non-chapter sections to skip
            skip_sections = ['TABLE OF CONTENTS', 'INDEX', 'PREFACE', 'FOREWORD', 'ACKNOWLEDGEMENTS']
            if any(section in line_stripped.upper() for section in skip_sections):
                continue
            
            if is_chapter and len(current_chapter["content"]) > 100:  # Ensure chapter has content
                # Save current chapter
                chapters.append(current_chapter.copy())
                
                # Start new chapter
                current_chapter = {
                    "title": line_stripped,
                    "content": "",
                    "start": i
                }
            else:
                current_chapter["content"] += line + '\n'
                
        # Add the last chapter
        if current_chapter["content"]:
            chapters.append(current_chapter)
        
        return chapters
    
    def extract_book_metadata(self, full_text):
        """Extract book title and author from text"""
        # Look for title patterns (usually at the beginning)
        lines = full_text.split('\n')[:50]  # Check first 50 lines
        
        title = "Unknown Title"
        author = "Unknown Author"
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Common title indicators
            if len(line_stripped) > 5 and len(line_stripped) < 100 and line_stripped.isupper():
                if title == "Unknown Title":
                    title = line_stripped
            
            # Author indicators
            if 'by' in line_lower or 'author:' in line_lower:
                author_match = re.search(r'by\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', line, re.IGNORECASE)
                if author_match:
                    author = author_match.group(1)
        
        return {"title": title, "author": author}
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text with structure preservation"""
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text() + "\n\n"
        
        return full_text