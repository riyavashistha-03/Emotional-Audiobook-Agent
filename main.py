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
        """Detect chapter boundaries using Table of Contents first, then regex/AI"""
        print("📑 Detecting chapters...")
        
        # First, try to extract chapters from Table of Contents
        chapters = self._extract_chapters_from_toc()
        
        if chapters and len(chapters) > 5:
            print(f"✅ Found {len(chapters)} chapters from Table of Contents")
            self.chapters = chapters
            return chapters
        
        print("⚠️ Table of Contents extraction didn't find enough chapters, trying pattern matching...")
        
        # Fallback: use regex-based detection for simple number markers
        chapters = self._detect_chapters_by_page_numbers()
        
        if chapters and len(chapters) > 5:
            print(f"✅ Found {len(chapters)} chapters from page numbers")
            self.chapters = chapters
            return chapters
        
        # Final fallback: use AI detection
        print("⚠️ Pattern matching found too few chapters, using AI detection...")
        chapters = self._ai_chapter_detection()
        
        self.chapters = chapters
        print(f"✅ Found {len(chapters)} chapters")
        return chapters
    
    def _extract_chapters_from_toc(self) -> List[Dict]:
        """Extract chapters from Table of Contents"""
        print("🔍 Scanning for Table of Contents...")
        
        # Look for "Table of Contents" or similar
        lines = self.full_text.split('\n')
        toc_start = -1
        toc_end = -1
        
        # Find TOC section
        for i, line in enumerate(lines):
            lower_line = line.lower().strip()
            if 'table of contents' in lower_line or 'contents' in lower_line:
                toc_start = i
                print(f"📚 Found Table of Contents at line {i}")
                break
        
        if toc_start == -1:
            return []
        
        # Find end of TOC (usually when we hit actual chapter content)
        for i in range(toc_start + 1, min(toc_start + 500, len(lines))):
            line = lines[i].strip()
            # TOC ends when we encounter substantial body text or chapter numbering with page numbers
            if line and len(line) > 80 and not any(c.isdigit() for c in line):
                toc_end = i
                break
            # Or if we hit a clear chapter start marker
            if re.match(r'^(CHAPTER\s+\d+|Chapter\s+\d+|^\d+$)', line, re.IGNORECASE):
                if i > toc_start + 5:  # Make sure we're past the TOC header
                    toc_end = i
                    break
        
        if toc_end == -1:
            toc_end = min(toc_start + 300, len(lines))
        
        # Extract TOC text
        toc_text = '\n'.join(lines[toc_start:toc_end])
        print(f"📄 TOC section: {len(toc_text)} characters")
        
        # Parse TOC entries - look for patterns like:
        # 1. Chapter Title         5
        # Chapter 1: Title         10
        # 1 - Title               12
        chapters = []
        toc_patterns = [
            (r'^(\d+)\s*[\.\-\s]+(.+?)(?:\s+(\d+))?$', 'number_title'),  # 1. Title [page]
            (r'(?i)^chapter\s+(\d+)[\.\:\-\s]+(.+?)(?:\s+(\d+))?$', 'chapter_title'),  # Chapter 1: Title [page]
        ]
        
        for line in toc_text.split('\n'):
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            chapter_num = None
            chapter_title = None
            
            for pattern, pattern_type in toc_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    chapter_num = groups[0]
                    chapter_title = groups[1] if len(groups) > 1 else f"Chapter {chapter_num}"
                    
                    try:
                        chapter_num = int(chapter_num)
                    except:
                        chapter_num = len(chapters) + 1
                    
                    # Clean up title
                    if chapter_title:
                        chapter_title = chapter_title.strip()
                    
                    chapters.append({
                        "number": chapter_num,
                        "title": chapter_title or f"Chapter {chapter_num}",
                        "content": "",
                    })
                    break
        
        return chapters if len(chapters) > 0 else []
    
    def _detect_chapters_by_page_numbers(self) -> List[Dict]:
        """Detect chapters by finding simple number markers at start of lines"""
        print("🔢 Detecting chapter numbers in text...")
        
        lines = self.full_text.split('\n')
        chapters = []
        
        # Look for standalone numbers (1, 2, 3, etc)
        expected_chapter_num = 1
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check if line is just a number
            if line_stripped.isdigit():
                chapter_num = int(line_stripped)
                
                # Accept if it matches expected sequence or if it's a reasonable chapter number
                if chapter_num == expected_chapter_num or chapter_num < 200:
                    # Get next non-empty line as potential title
                    chapter_title = f"Chapter {chapter_num}"
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and len(next_line) < 100:
                            chapter_title = next_line
                            break
                    
                    chapters.append({
                        "number": chapter_num,
                        "title": chapter_title,
                        "content": "",
                    })
                    
                    expected_chapter_num = chapter_num + 1
        
        return chapters if len(chapters) > 5 else []
    
    def _ai_chapter_detection(self) -> List[Dict]:
        """Use AI to detect chapters when regex fails"""
        print("🤖 Using AI to detect all chapters...")
        
        prompt = f"""
        Analyze this book text and identify ALL chapter boundaries and titles.
        
        IMPORTANT: Find EVERY SINGLE chapter, no matter the format.
        
        TEXT (first 8000 characters):
        {self.full_text[:8000]}...
        
        Return a JSON array with all chapters in this format:
        [
            {{"number": 1, "title": "Chapter One"}},
            {{"number": 2, "title": "Chapter Two"}},
            ...
        ]
        
        Look for:
        - Lines starting with "Chapter"
        - Lines with just numbers (1, 2, 3...)
        - Roman numerals (I, II, III...)
        - Part/Book designations
        
        Include EVERY chapter. Return as a JSON array ONLY.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            
            # Try to parse JSON
            try:
                ai_chapters = json.loads(response_text)
            except:
                # If not valid JSON, try to extract chapter list
                ai_chapters = []
                lines = response_text.split('\n')
                for line in lines:
                    if 'number' in line.lower() or 'chapter' in line.lower():
                        try:
                            # Try to parse as JSON object
                            if '{' in line and '}' in line:
                                chapter_obj = json.loads(line)
                                ai_chapters.append(chapter_obj)
                        except:
                            pass
            
            # Convert to our format
            chapters = []
            if isinstance(ai_chapters, list) and len(ai_chapters) > 0:
                for ch in ai_chapters:
                    if isinstance(ch, dict):
                        chapters.append({
                            "title": ch.get("title", f"Chapter {ch.get('number', len(chapters)+1)}"),
                            "content": "",  # Will be populated from full text
                            "number": ch.get("number", len(chapters)+1)
                        })
                    else:
                        chapters.append({
                            "title": str(ch),
                            "content": "",
                            "number": len(chapters) + 1
                        })
            
            if chapters:
                print(f"✅ AI detected {len(chapters)} chapters")
                return chapters
            else:
                raise Exception("No chapters parsed")
                
        except Exception as e:
            print(f"⚠️ AI detection failed: {e}")
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
