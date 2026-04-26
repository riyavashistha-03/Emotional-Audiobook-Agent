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
        """Extract text and metadata using PyMuPDF"""
        print(f"📄 Extracting text from PDF: {pdf_path}")
        self.doc = fitz.open(pdf_path)
        full_text = ""
        self.page_offsets = [0] # character offset where each page starts
        
        # Also store TOC if available
        self.internal_toc = self.doc.get_toc()
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            text = page.get_text() + "\n\n"
            full_text += text
            self.page_offsets.append(len(full_text))
        
        self.full_text = full_text
        print(f"✅ Extracted {len(full_text)} characters from {len(self.doc)} pages")
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
        """Detect chapter boundaries using multiple strategies"""
        print("📑 Detecting chapters...")

        # 1. Try Internal PDF TOC first
        chapters = self._get_chapters_from_internal_toc()
        if chapters and len(chapters) > 3:
            print(f"✅ Found {len(chapters)} chapters from Internal TOC")
            self.chapters = self._populate_chapter_content(chapters)
            return self.chapters

        # 2. Try Manual TOC Analysis (Text parsing)
        chapters = self._extract_chapters_from_toc()
        if chapters and len(chapters) > 3:
            print(f"✅ Found {len(chapters)} chapters from manual TOC analysis")
            self.chapters = self._populate_chapter_content(chapters)
            return self.chapters

        # 3. Font-size based detection (Look for large headings)
        chapters = self._detect_chapters_by_font_size()
        if chapters and len(chapters) > 3:
            print(f"✅ Found {len(chapters)} chapters from font-size analysis")
            self.chapters = self._populate_chapter_content(chapters)
            return self.chapters

        # 4. Fallback: Sequential pattern matching
        chapters = self._detect_chapters_by_page_numbers()
        self.chapters = self._populate_chapter_content(chapters)
        print(f"✅ Found {len(self.chapters)} chapters via fallback")
        return self.chapters

    def _get_chapters_from_internal_toc(self) -> List[Dict]:
        """Convert PDF's internal TOC structure to our chapter format"""
        if not self.internal_toc:
            return []
            
        chapters = []
        for level, title, page in self.internal_toc:
            if level == 1 or "chapter" in title.lower():
                chapters.append({
                    "number": len(chapters) + 1,
                    "title": title,
                    "page_start": page,
                    "content": ""
                })
        return chapters

    def _detect_chapters_by_font_size(self) -> List[Dict]:
        """Scan for text with unusually large font size compared to body text"""
        print("🔍 Analyzing font sizes for chapter headers...")
        
        font_data = []
        for page_num in range(min(50, len(self.doc))): # Scan first 50 pages
            page = self.doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            font_data.append(s["size"])
        
        if not font_data: return []
        
        # Calculate median font size (body text)
        median_size = sorted(font_data)[len(font_data)//2]
        header_threshold = median_size * 1.5 # Headers are usually 50%+ larger
        
        chapters = []
        noise_keywords = ["copyright", "contents", "dedication", "preface", "about the author", "title page"]
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if "lines" in b:
                    full_block_text = " ".join([" ".join([s["text"] for s in l["spans"]]) for l in b["lines"]]).strip()
                    if not full_block_text: continue
                    
                    # Check if any span in the block is header-sized
                    is_header = any(any(s["size"] > header_threshold for s in l["spans"]) for l in b["lines"])
                    
                    if is_header and len(full_block_text) < 100:
                        # Filter noise
                        if any(kw in full_block_text.lower() for kw in noise_keywords):
                            continue
                            
                        # Avoid duplicates on same page
                        if chapters and chapters[-1]["page_start"] == page_num + 1:
                            continue
                            
                        chapters.append({
                            "number": len(chapters) + 1,
                            "title": full_block_text,
                            "page_start": page_num + 1,
                            "content": ""
                        })
        return chapters

    def _populate_chapter_content(self, chapters: List[Dict]) -> List[Dict]:
        """Extract actual text content for each chapter from full_text."""
        if not chapters or not self.full_text:
            return chapters

        # Sort by page_start if available, else by number
        chapters = sorted(chapters, key=lambda c: (c.get('page_start', 0), c.get('number', 0)))
        total_len = len(self.full_text)
        start_positions = []

        for ch in chapters:
            num = ch.get('number', 0)
            title = ch.get('title', '').strip()
            page_start = ch.get('page_start', 0)
            
            # Strategy 1: If we have a page number, use the character offset for that page
            if page_start > 0 and page_start <= len(self.page_offsets):
                start_positions.append(self.page_offsets[page_start - 1])
                continue

            # Strategy 2: Regex search (only if page number is missing)
            title_esc = re.escape(title)
            pos = -1
            patterns = [
                rf'(?mi)^\s*chapter\s+{num}\b',
                rf'(?mi)^\s*{title_esc}\b',
                rf'(?m)^\s*{num}\s*$',
            ]
            
            for pattern in patterns:
                m = re.search(pattern, self.full_text)
                if m:
                    pos = m.start()
                    break
            start_positions.append(pos)

        # Fill in any failed searches
        for i in range(len(start_positions)):
            if start_positions[i] < 0:
                prev = next((start_positions[j] for j in range(i - 1, -1, -1) if start_positions[j] >= 0), 0)
                nxt = next((start_positions[j] for j in range(i + 1, len(start_positions)) if start_positions[j] >= 0), total_len)
                start_positions[i] = (prev + nxt) // 2

        # Slice content
        for i, ch in enumerate(chapters):
            s = start_positions[i]
            e = start_positions[i + 1] if i + 1 < len(start_positions) else total_len
            
            # Trim the title from the start of the content to avoid repetition in audio
            content = self.full_text[s:e].strip()
            # Basic sanity check: if content starts with title, skip it
            # (We'll let the narrator handle titles if needed)
            chapters[i]['content'] = content

        return sorted(chapters, key=lambda c: c.get('number', 0))
    
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
        """Detect chapters by finding strictly sequential standalone numbers"""
        print("🔢 Detecting chapter numbers in text...")
        
        lines = self.full_text.split('\n')
        chapters = []
        expected_chapter_num = 1
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Standalone digits, strictly sequential
            if line_stripped.isdigit():
                chapter_num = int(line_stripped)

                if chapter_num == expected_chapter_num:
                    # Look ahead for a title
                    chapter_title = f"Chapter {chapter_num}"
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and 3 < len(next_line) < 60 and not next_line.isdigit():
                            # Filter out common noise
                            if not any(kw in next_line.lower() for kw in ["copyright", "dedicated", "contents"]):
                                chapter_title = next_line
                                break

                    chapters.append({
                        "number": chapter_num,
                        "title": chapter_title,
                        "content": "",
                        "page_start": 0 # Unknown
                    })
                    expected_chapter_num = chapter_num + 1
        
        return chapters if len(chapters) > 2 else []
    
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
