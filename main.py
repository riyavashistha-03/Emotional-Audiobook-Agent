"""
Story Director - Core AI agent for book analysis and scene direction
"""
import fitz  # PyMuPDF
import os
import json
import re
from groq import Groq
from typing import Dict, List, Optional, Tuple

class StoryDirector:
    """
    AI Director that analyzes books and provides scene-by-scene direction
    """
    
    def __init__(self, groq_api_key: str):
        self.client = Groq(api_key=groq_api_key)
        self.full_text = ""
        self.metadata = {}
        self.chapters = []
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text with structure preservation"""
        print(f"📄 Extracting text from PDF: {pdf_path}")
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text() + "\n\n"
        
        self.full_text = full_text
        print(f"✅ Extracted {len(full_text)} characters")
        return full_text
    
    def extract_book_metadata(self) -> Dict:
        """Extract book title and author"""
        print("📚 Extracting book metadata...")
        
        prompt = f"""
        Extract the book title and author from this text.
        
        TEXT (first 2000 chars):
        {self.full_text[:2000]}
        
        Return JSON with:
        {{
            "title": "book title",
            "author": "author name",
            "language": "English/Spanish/etc."
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            self.metadata = json.loads(response.choices[0].message.content)
            print(f"✅ Title: {self.metadata.get('title', 'Unknown')}")
            print(f"✅ Author: {self.metadata.get('author', 'Unknown')}")
            return self.metadata
        except:
            self.metadata = {"title": "Unknown Title", "author": "Unknown Author", "language": "English"}
            return self.metadata
    
    def detect_chapters(self) -> List[Dict]:
        """Detect chapter boundaries using AI and regex"""
        print("📑 Detecting chapters...")
        
        # First try regex-based detection
        chapter_patterns = [
            r'CHAPTER\s+(\d+)[\.\s]',
            r'Chapter\s+(\d+)[\.\s]',
            r'^(\d+)\.\s+',  # Numbered at start of line
            r'\n(\d+)\.\s+',  # Numbered after newline
            r"(?i)CHAPTER\s+(?:[0-9]+|[A-Z]+)"
        ]
        
        lines = self.full_text.split('\n')
        chapters = []
        current_chapter = {"title": "Prologue/Start", "content": "", "number": 0}
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_chapter["content"] += "\n"
                continue
                
            # Check for chapter markers
            is_chapter = False
            chapter_num = None
            
            for pattern in chapter_patterns:
                match = re.match(pattern, line_stripped, re.IGNORECASE)
                if match:
                    is_chapter = True
                    try:
                        chapter_num = int(match.group(1))
                    except:
                        chapter_num = len(chapters) + 1
                    break
            
            # Skip table of contents, etc.
            skip_words = ['contents', 'index', 'preface', 'foreword', 'acknowledgements']
            if any(word in line_stripped.lower() for word in skip_words) and len(line_stripped) < 50:
                continue
            
            if is_chapter and len(current_chapter["content"]) > 200:
                # Save current chapter
                if current_chapter["content"].strip():
                    chapters.append(current_chapter.copy())
                
                # Start new chapter
                current_chapter = {
                    "title": line_stripped,
                    "content": "",
                    "number": chapter_num or (len(chapters) + 1)
                }
            else:
                current_chapter["content"] += line + '\n'
        
        # Add last chapter
        if current_chapter["content"].strip():
            chapters.append(current_chapter)
        
        # If regex found too few chapters, use AI
        if len(chapters) < 3 and len(self.full_text) > 10000:
            chapters = self._ai_chapter_detection()
        
        self.chapters = chapters
        print(f"✅ Found {len(chapters)} chapters")
        return chapters
    
    def _ai_chapter_detection(self) -> List[Dict]:
        """Use AI to detect chapters when regex fails"""
        prompt = f"""
        Identify the chapter boundaries in this book.
        
        TEXT (first 5000 chars):
        {self.full_text[:5000]}...
        
        Return a JSON list of chapters with:
        [
            {{
                "title": "chapter title",
                "number": chapter_number,
                "start_position": "approximate start text"
            }}
        ]
        
        Include ALL chapters. If no clear chapters, treat as single chapter.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            ai_chapters = json.loads(response.choices[0].message.content)
            
            # Convert to our format
            chapters = []
            if isinstance(ai_chapters, list):
                for i, ch in enumerate(ai_chapters):
                    chapters.append({
                        "title": ch.get("title", f"Chapter {i+1}"),
                        "content": f"[Chapter {i+1} content]",  # Placeholder
                        "number": ch.get("number", i+1)
                    })
            return chapters
        except:
            # Fallback: treat whole book as one chapter
            return [{
                "title": "Complete Book",
                "content": self.full_text,
                "number": 1
            }]
    
    def analyze_scene(self, text_snippet: str, context: str = "") -> Dict:
        """
        Analyze a scene for voice direction
        """
        prompt = f"""
        You are a professional audiobook director analyzing a scene.
        
        CONTEXT: {context}
        
        TEXT: '{text_snippet}'
        
        Return JSON with:
        {{
            "scene_type": "narration/dialogue/description/action",
            "characters_present": ["character1", "character2"],
            "primary_focus": "main character in this snippet",
            "emotion": "overall emotion",
            "pace": "slow/normal/fast",
            "intensity": 1-10,
            "has_dialogue": true/false,
            "dialogue_lines": [
                {{
                    "speaker": "character_name",
                    "text": "dialogue text",
                    "emotion": "character's emotion here"
                }}
            ]
        }}
        
        Be precise. If no dialogue, dialogue_lines should be empty list.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
        except:
            # Default fallback
            return {
                "scene_type": "narration",
                "characters_present": ["narrator"],
                "primary_focus": "narrator",
                "emotion": "neutral",
                "pace": "normal",
                "intensity": 5,
                "has_dialogue": False,
                "dialogue_lines": []
            }
