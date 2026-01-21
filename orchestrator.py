import os
import json
import fitz
from pydub import AudioSegment
import re
from main import StoryDirector
from speaker import AudiobookSpeaker

class ChapterBasedAudiobookAgent:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.output_folder = "chapters"
        os.makedirs(self.output_folder, exist_ok=True)
        
        self.director = StoryDirector()
        self.speaker = AudiobookSpeaker()
        
        # Load and process the entire book
        print("📖 Loading and analyzing book structure...")
        self.full_text = self.director.extract_text_from_pdf(pdf_path)
        self.book_metadata = self.director.extract_book_metadata(self.full_text)
        self.chapters = self.director.detect_chapters(self.full_text)
        
        print(f"📚 Book: {self.book_metadata['title']}")
        print(f"✍️ Author: {self.book_metadata['author']}")
        print(f"📑 Found {len(self.chapters)} chapters")
        
        # Display chapter list for user
        self.display_chapter_list()
    
    def display_chapter_list(self):
        """Display all detected chapters with numbers"""
        print("\n📋 Detected Chapters:")
        print("-" * 60)
        for i, chapter in enumerate(self.chapters):
            # Truncate long titles
            title = chapter['title'][:50] + "..." if len(chapter['title']) > 50 else chapter['title']
            print(f"{i+1:3d}. {title}")
        print("-" * 60)
    
    def create_book_introduction(self):
        """Create introductory audio with book title and author"""
        intro_text = f"{self.book_metadata['title']}. By {self.book_metadata['author']}."
        
        intro_notes = {
            "character": "authoritative_narrator",
            "emotion": "neutral",
            "pace": "slow",
            "voice_type": "authoritative"
        }
        
        intro_file = os.path.join(self.output_folder, "00_introduction.wav")
        print(f"\n🎤 Creating introduction: '{self.book_metadata['title']}'")
        self.speaker.generate_audio(intro_text, intro_notes, intro_file)
        
        return AudioSegment.from_wav(intro_file)
    
    def process_chapter(self, chapter_index, chapter_info, include_title=True):
        """Process a single chapter"""
        chapter_title = chapter_info['title']
        chapter_content = chapter_info['content']
        
        print(f"\n{'='*60}")
        print(f"📝 Processing Chapter {chapter_index + 1}: {chapter_title}")
        print(f"{'='*60}")
        
        chapter_audio = AudioSegment.empty()
        
        # Add chapter title if requested
        if include_title:
            chapter_title_audio = self.create_chapter_title_audio(chapter_title)
            chapter_audio += chapter_title_audio
            chapter_audio += AudioSegment.silent(duration=1500)  # 1.5 second pause
        
        # Split content into manageable segments (paragraphs)
        paragraphs = self.split_into_paragraphs(chapter_content)
        
        for i, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue
                
            print(f"\r📄 Processing paragraph {i+1}/{len(paragraphs)}", end="")
            
            # Analyze this paragraph
            previous_context = paragraphs[i-1] if i > 0 else ""
            scene_analysis = self.director.analyze_scene(paragraph, previous_context)
            
            # Prepare character info for speaker
            character_info = {
                "character": scene_analysis.get("primary_character", "narrator"),
                "emotion": scene_analysis.get("emotion", "neutral"),
                "gender": scene_analysis.get("character_gender", "neutral"),
                "age": scene_analysis.get("character_age", "adult"),
                "scene_type": scene_analysis.get("scene_type", "narration")
            }
            
            # Generate audio for this paragraph
            temp_file = os.path.join(self.output_folder, f"temp_para_{chapter_index}_{i}.wav")
            
            if self.speaker.generate_audio(paragraph, character_info, temp_file):
                # Add to chapter audio
                para_audio = AudioSegment.from_wav(temp_file)
                chapter_audio += para_audio
                
                # Add small pause between paragraphs
                if i < len(paragraphs) - 1:
                    pause = AudioSegment.silent(duration=500)  # 500ms pause
                    chapter_audio += pause
                
                # Clean up temp file
                os.remove(temp_file)
        
        print()  # New line after progress
        return chapter_audio
    
    def split_into_paragraphs(self, text, max_length=1000):
        """Split text into paragraphs, respecting natural breaks"""
        paragraphs = []
        current_para = ""
        
        lines = text.split('\n')
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines that aren't paragraph breaks
            if not line_stripped and not current_para:
                continue
            
            # If line is empty and we have content, it's a paragraph break
            if not line_stripped and current_para:
                paragraphs.append(current_para)
                current_para = ""
            elif len(current_para) + len(line_stripped) < max_length:
                current_para += line_stripped + " "
            else:
                # Current paragraph is getting too long, start new one
                if current_para:
                    paragraphs.append(current_para)
                current_para = line_stripped + " "
        
        # Add the last paragraph if exists
        if current_para:
            paragraphs.append(current_para)
        
        return paragraphs
    
    def create_chapter_title_audio(self, chapter_title):
        """Create special audio for chapter titles"""
        title_notes = {
            "character": "authoritative_narrator",
            "emotion": "neutral",
            "pace": "slow",
            "voice_type": "authoritative"
        }
        
        temp_file = os.path.join(self.output_folder, "temp_title.wav")
        title_text = f"Chapter. {chapter_title}"
        self.speaker.generate_audio(title_text, title_notes, temp_file)
        
        title_audio = AudioSegment.from_wav(temp_file)
        os.remove(temp_file)
        
        return title_audio
    
    def build_specific_chapters(self, chapter_numbers, output_name=None, include_intro=True):
        """
        Build audiobook for specific chapters only
        
        Args:
            chapter_numbers: List of chapter numbers (1-indexed) or range string
            output_name: Custom output filename (without extension)
            include_intro: Whether to include book introduction
        """
        # Parse chapter numbers
        chapters_to_process = self.parse_chapter_selection(chapter_numbers)
        
        if not chapters_to_process:
            print("❌ No valid chapters selected.")
            return
        
        print(f"\n🎯 Selected {len(chapters_to_process)} chapter(s): {chapters_to_process}")
        
        master_audio = AudioSegment.empty()
        
        # Add introduction if requested
        if include_intro:
            print("\n🎤 Adding book introduction...")
            intro_audio = self.create_book_introduction()
            master_audio += intro_audio
            master_audio += AudioSegment.silent(duration=2000)  # 2 second pause
        
        # Process selected chapters
        for idx, chapter_num in enumerate(chapters_to_process):
            chapter_idx = chapter_num - 1  # Convert to 0-indexed
            
            if 0 <= chapter_idx < len(self.chapters):
                chapter_info = self.chapters[chapter_idx]
                
                # Process chapter
                chapter_audio = self.process_chapter(
                    chapter_idx, 
                    chapter_info, 
                    include_title=True
                )
                
                master_audio += chapter_audio
                
                # Save individual chapter file
                chapter_filename = os.path.join(
                    self.output_folder, 
                    f"chapter_{chapter_num:02d}_selected.wav"
                )
                chapter_audio.export(chapter_filename, format="wav")
                print(f"💾 Saved individual chapter: {chapter_filename}")
                
                # Add chapter break (except after last chapter)
                if idx < len(chapters_to_process) - 1:
                    master_audio += AudioSegment.silent(duration=3000)  # 3 second pause
            else:
                print(f"⚠️ Chapter {chapter_num} not found. Skipping.")
        
        # Generate output filename
        if not output_name:
            chapter_str = "-".join(str(c) for c in chapters_to_process)
            output_name = f"{self.book_metadata['title'].replace(' ', '_')}_chapters_{chapter_str}"
        
        # Export final audiobook
        output_filename = f"{output_name}.mp3"
        print(f"\n🎬 Exporting selected chapters to: {output_filename}")
        master_audio.export(output_filename, format="mp3", bitrate="192k")
        
        print(f"\n✅ SUCCESS! Selected chapters created:")
        print(f"📁 Final file: {output_filename}")
        print(f"⏱️ Total duration: {len(master_audio) / 1000 / 60:.1f} minutes")
    
    def build_chapter_range(self, start_chapter, end_chapter, **kwargs):
        """
        Build audiobook for a range of chapters
        
        Args:
            start_chapter: First chapter to include (1-indexed)
            end_chapter: Last chapter to include (1-indexed)
        """
        chapter_range = list(range(start_chapter, end_chapter + 1))
        return self.build_specific_chapters(chapter_range, **kwargs)
    
    def parse_chapter_selection(self, selection):
        """
        Parse various chapter selection formats
        
        Supported formats:
        - Single number: 5
        - List: [1, 3, 5]
        - Range: "1-5" or "1:5"
        - Mixed: "1,3,5-8"
        """
        if isinstance(selection, (list, tuple)):
            # Already a list of numbers
            return [int(c) for c in selection if 1 <= int(c) <= len(self.chapters)]
        
        if isinstance(selection, int):
            # Single number
            return [selection] if 1 <= selection <= len(self.chapters) else []
        
        if isinstance(selection, str):
            # Parse string format
            chapters = set()
            
            # Handle different separators
            selection = selection.replace(':', '-')
            parts = selection.split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range like "1-5"
                    try:
                        start, end = map(int, part.split('-'))
                        for ch in range(start, end + 1):
                            if 1 <= ch <= len(self.chapters):
                                chapters.add(ch)
                    except:
                        continue
                else:
                    # Single chapter
                    try:
                        ch = int(part)
                        if 1 <= ch <= len(self.chapters):
                            chapters.add(ch)
                    except:
                        continue
            
            return sorted(list(chapters))
        
        return []
    
    def build_all_chapters(self):
        """Build complete audiobook with all chapters"""
        self.build_specific_chapters(
            list(range(1, len(self.chapters) + 1)),
            output_name=f"{self.book_metadata['title'].replace(' ', '_')}_complete",
            include_intro=True
        )
    
    def create_manifest(self, selected_chapters=None):
        """Create a JSON manifest with chapter information"""
        manifest = {
            "book": self.book_metadata,
            "chapters": [],
            "total_chapters": len(self.chapters),
            "output_folder": self.output_folder,
            "selected_chapters": selected_chapters
        }
        
        for i, chapter in enumerate(self.chapters):
            chapter_file = f"chapter_{i+1:02d}.wav"
            manifest["chapters"].append({
                "number": i + 1,
                "title": chapter['title'],
                "file": chapter_file,
                "word_count": len(chapter['content'].split()),
                "included_in_selection": (selected_chapters is None) or ((i+1) in selected_chapters)
            })
        
        manifest_file = os.path.join(self.output_folder, "manifest.json")
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"📋 Manifest created: {manifest_file}")

def get_user_selection():
    """Get chapter selection from user interactively"""
    print("\n" + "="*60)
    print("   CHAPTER SELECTION MENU   ")
    print("="*60)
    print("1. Process all chapters")
    print("2. Process specific chapters (e.g., 1,3,5 or 1-5)")
    print("3. Process a range of chapters (e.g., 3 to 7)")
    print("4. Process single chapter")
    print("0. Exit")
    print("-"*60)
    
    choice = input("Enter your choice (0-4): ").strip()
    
    return choice

if __name__ == "__main__":
    pdf_path = r"C:\Users\Rahul Dev\OneDrive\Desktop\Projects2026\emotioal-audiobook-agent\If He Had Been with Me.pdf"
    
    print("🚀 Initializing Enhanced Audiobook Agent...")
    agent = ChapterBasedAudiobookAgent(pdf_path)
    
    while True:
        choice = get_user_selection()
        
        if choice == "0":
            print("👋 Exiting...")
            break
            
        elif choice == "1":
            # Process all chapters
            print("\n📚 Processing ALL chapters...")
            agent.build_all_chapters()
            agent.create_manifest()
            break
            
        elif choice == "2":
            # Process specific chapters
            selection = input("\nEnter chapter numbers (e.g., '1,3,5' or '1-5,7-10'): ").strip()
            output_name = input("Output filename (without extension, press Enter for default): ").strip()
            include_intro = input("Include book introduction? (y/n, default=y): ").strip().lower() != 'n'
            
            agent.build_specific_chapters(
                selection,
                output_name=output_name if output_name else None,
                include_intro=include_intro
            )
            selected = agent.parse_chapter_selection(selection)
            agent.create_manifest(selected)
            break
            
        elif choice == "3":
            # Process range of chapters
            try:
                start = int(input("Start chapter: ").strip())
                end = int(input("End chapter: ").strip())
                output_name = input("Output filename (without extension, press Enter for default): ").strip()
                include_intro = input("Include book introduction? (y/n, default=y): ").strip().lower() != 'n'
                
                agent.build_chapter_range(
                    start, 
                    end,
                    output_name=output_name if output_name else None,
                    include_intro=include_intro
                )
                agent.create_manifest(list(range(start, end + 1)))
            except ValueError:
                print("❌ Invalid chapter numbers. Please enter integers.")
            break
            
        elif choice == "4":
            # Process single chapter
            try:
                chapter_num = int(input("Chapter number: ").strip())
                output_name = input("Output filename (without extension, press Enter for default): ").strip()
                include_intro = input("Include book introduction? (y/n, default=y): ").strip().lower() != 'n'
                
                agent.build_specific_chapters(
                    [chapter_num],
                    output_name=output_name if output_name else None,
                    include_intro=include_intro
                )
                agent.create_manifest([chapter_num])
            except ValueError:
                print("❌ Invalid chapter number.")
            break
            
        else:
            print("❌ Invalid choice. Please try again.")