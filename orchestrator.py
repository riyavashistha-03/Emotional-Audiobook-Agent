"""
Main Orchestrator - Coordinates the entire audiobook generation process
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable
from pydub import AudioSegment
import time

from main import StoryDirector
from character_analyst import CharacterVoiceDesigner
from voice_manager import MOSSVoiceManager

class AudiobookOrchestrator:
    """
    Master orchestrator that coordinates all components
    """
    
    def __init__(self, 
                 pdf_path: str,
                 groq_api_key: str,
                 moss_api_url: str = "http://localhost:7860",
                 output_dir: str = "audiobook_output"):
        
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        print("🎧 Initializing Audiobook Orchestrator...")
        self.director = StoryDirector(groq_api_key)
        self.character_designer = CharacterVoiceDesigner(groq_api_key)
        self.voice_manager = MOSSVoiceManager(moss_api_url)
        
        # State
        self.full_text = ""
        self.metadata = {}
        self.chapters = []
        self.character_registry = {}
        self.voice_map = {}  # character -> voice_id
        
        # Progress tracking
        self.progress_callback = None
        self.status_callback = None
    
    def set_progress_callbacks(self, 
                               progress_callback: Optional[Callable] = None,
                               status_callback: Optional[Callable] = None):
        """Set callbacks for UI progress updates"""
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def _update_progress(self, progress: float, status: str):
        """Update progress via callbacks"""
        if self.progress_callback:
            self.progress_callback(progress)
        if self.status_callback:
            self.status_callback(status)
        print(f"📊 {status}")
    
    def load_book(self) -> bool:
        """Load and analyze the book"""
        try:
            self._update_progress(0.1, "Extracting text from PDF...")
            self.full_text = self.director.extract_text_from_pdf(self.pdf_path)
            
            self._update_progress(0.2, "Extracting book metadata...")
            self.metadata = self.director.extract_book_metadata()
            
            self._update_progress(0.3, "Detecting chapters...")
            self.chapters = self.director.detect_chapters()
            
            return True
        except Exception as e:
            print(f"❌ Error loading book: {e}")
            return False
    
    def analyze_characters(self) -> bool:
        """Analyze all characters in the book"""
        try:
            self._update_progress(0.4, "Analyzing characters (this may take a moment)...")
            self.character_registry = self.character_designer.analyze_full_book_characters(
                self.full_text
            )
            
            self._update_progress(0.5, "Generating voice design briefs...")
            voice_briefs = self.character_designer.generate_voice_design_briefs()
            
            self._update_progress(0.6, "Creating voices with MOSS...")
            
            # Create voices for each character
            total_chars = len(self.character_registry)
            for i, (char_name, _) in enumerate(self.character_registry.items()):
                if char_name in voice_briefs:
                    voice_id = self.voice_manager.create_voice_from_description(
                        char_name,
                        voice_briefs[char_name]
                    )
                    if voice_id:
                        self.voice_map[char_name] = voice_id
                
                # Update progress
                progress = 0.6 + (0.2 * (i + 1) / total_chars)
                self._update_progress(progress, f"Created voice for: {char_name}")
            
            # Always add a narrator voice
            if "narrator" not in self.voice_map:
                narrator_brief = "A calm, neutral, professional narrator voice, clear articulation, moderate pace, suitable for storytelling."
                narrator_id = self.voice_manager.create_voice_from_description(
                    "narrator",
                    narrator_brief
                )
                if narrator_id:
                    self.voice_map["narrator"] = narrator_id
            
            self._update_progress(0.8, f"✅ Created {len(self.voice_map)} voices")
            return True
            
        except Exception as e:
            print(f"❌ Error analyzing characters: {e}")
            return False
    
    def generate_chapter(self, 
                        chapter_index: int,
                        use_mock: bool = False) -> Optional[str]:
        """
        Generate a single chapter
        
        Args:
            chapter_index: 0-based chapter index
            use_mock: If True, use mock voice IDs (for testing without MOSS)
            
        Returns:
            Path to generated audio file or None
        """
        if chapter_index >= len(self.chapters):
            print(f"❌ Chapter {chapter_index} not found")
            return None
        
        chapter = self.chapters[chapter_index]
        chapter_num = chapter.get('number', chapter_index + 1)
        chapter_title = chapter.get('title', f'Chapter {chapter_num}')
        
        self._update_progress(
            0.0,
            f"📝 Processing Chapter {chapter_num}: {chapter_title[:50]}..."
        )
        
        # Parse chapter into scenes
        scene_data = self.character_designer.parse_dialogue_scene(chapter['content'])
        
        if not scene_data or 'scenes' not in scene_data:
            print(f"⚠️ No scenes detected, treating as single scene")
            scene_data = {
                'scenes': [{
                    'location': 'unknown',
                    'characters_present': ['narrator'],
                    'dialogue_turns': [],
                    'narration': chapter['content'][:5000]  # Limit length
                }]
            }
        
        # Prepare voice map for this chapter
        chapter_voice_map = {}
        if use_mock:
            # Use mock IDs for testing
            for char_name in self.character_registry:
                chapter_voice_map[char_name] = self.voice_manager.get_mock_voice_id(char_name)
            chapter_voice_map['narrator'] = 'mock_narrator'
        else:
            chapter_voice_map = self.voice_map.copy()
        
        # Generate each scene
        chapter_audio = AudioSegment.empty()
        scene_files = []
        
        for i, scene in enumerate(scene_data.get('scenes', [])):
            self._update_progress(
                (i + 1) / len(scene_data['scenes']),
                f"  Generating scene {i+1}/{len(scene_data['scenes'])}"
            )
            
            scene_file = self.output_dir / f"chapter_{chapter_num:02d}_scene_{i+1:02d}.wav"
            
            # Add emotion modulation for each dialogue turn
            for turn in scene.get('dialogue_turns', []):
                speaker = turn.get('speaker')
                emotion = turn.get('emotion', 'neutral')
                
                if speaker in self.character_registry:
                    # Get emotion modulation parameters
                    context = f"{turn.get('context_before', '')} {turn.get('text', '')}"
                    modulation = self.character_designer.get_emotion_modulation(
                        speaker,
                        emotion,
                        context
                    )
                    turn['emotion_params'] = modulation
            
            if use_mock:
                # For testing, create silent audio
                duration_ms = len(scene.get('narration', '')) * 50  # Rough estimate
                silent_audio = AudioSegment.silent(duration=min(duration_ms, 30000))
                silent_audio.export(scene_file, format="wav")
                chapter_audio += silent_audio
                scene_files.append(scene_file)
            else:
                # Generate real audio with MOSS
                success = self.voice_manager.generate_dialogue_scene(
                    scene,
                    chapter_voice_map,
                    str(scene_file)
                )
                
                if success and scene_file.exists():
                    scene_audio = AudioSegment.from_wav(str(scene_file))
                    chapter_audio += scene_audio
                    scene_files.append(str(scene_file))
            
            # Add pause between scenes
            if i < len(scene_data['scenes']) - 1:
                chapter_audio += AudioSegment.silent(duration=1000)
        
        # Export chapter audio
        chapter_output = self.output_dir / f"chapter_{chapter_num:02d}.mp3"
        chapter_audio.export(str(chapter_output), format="mp3", bitrate="192k")
        
        # Clean up scene files (optional)
        for scene_file in scene_files:
            try:
                os.remove(scene_file)
            except:
                pass
        
        self._update_progress(1.0, f"✅ Chapter {chapter_num} complete")
        return str(chapter_output)
    
    def generate_chapters(self, 
                         chapter_selection: List[int],
                         use_mock: bool = False) -> List[str]:
        """
        Generate multiple chapters
        
        Args:
            chapter_selection: List of chapter numbers (1-indexed)
            use_mock: If True, use mock voices for testing
            
        Returns:
            List of generated audio file paths
        """
        generated_files = []
        
        for i, chapter_num in enumerate(chapter_selection):
            # Convert to 0-indexed
            chapter_idx = chapter_num - 1
            
            if 0 <= chapter_idx < len(self.chapters):
                # Update overall progress
                overall_progress = i / len(chapter_selection)
                self._update_progress(
                    overall_progress,
                    f"Processing chapter {chapter_num}/{chapter_selection[-1]}"
                )
                
                # Generate chapter
                chapter_file = self.generate_chapter(chapter_idx, use_mock)
                if chapter_file:
                    generated_files.append(chapter_file)
        
        # If multiple chapters, combine them
        if len(generated_files) > 1:
            self._combine_chapters(generated_files, chapter_selection)
        
        return generated_files
    
    def _combine_chapters(self, chapter_files: List[str], chapter_numbers: List[int]):
        """Combine multiple chapters into one audiobook"""
        combined = AudioSegment.empty()
        
        # Add introduction
        intro_text = f"{self.metadata.get('title', 'Audiobook')}. By {self.metadata.get('author', 'Unknown')}."
        
        # Generate intro with narrator voice
        intro_file = self.output_dir / "00_introduction.wav"
        if self.voice_manager.generate_dialogue_scene(
            {'dialogue_turns': [], 'narration': intro_text},
            {'narrator': self.voice_map.get('narrator', 'default')},
            str(intro_file)
        ):
            combined += AudioSegment.from_wav(str(intro_file))
            combined += AudioSegment.silent(duration=2000)
        
        # Add chapters
        for i, chapter_file in enumerate(chapter_files):
            chapter_audio = AudioSegment.from_mp3(chapter_file)
            combined += chapter_audio
            
            if i < len(chapter_files) - 1:
                combined += AudioSegment.silent(duration=3000)
        
        # Export combined
        if len(chapter_numbers) == len(self.chapters):
            output_name = f"{self.metadata.get('title', 'book').replace(' ', '_')}_complete.mp3"
        else:
            range_str = f"chapters_{chapter_numbers[0]}_{chapter_numbers[-1]}"
            output_name = f"{self.metadata.get('title', 'book').replace(' ', '_')}_{range_str}.mp3"
        
        combined_output = self.output_dir / output_name
        combined.export(str(combined_output), format="mp3", bitrate="192k")
        print(f"✅ Combined audiobook saved: {combined_output}")
        
        return str(combined_output)
    
    def generate_all_chapters(self, use_mock: bool = False) -> List[str]:
        """Generate all chapters in the book"""
        chapter_numbers = list(range(1, len(self.chapters) + 1))
        return self.generate_chapters(chapter_numbers, use_mock)
    
    def save_manifest(self):
        """Save generation manifest"""
        manifest = {
            "book": self.metadata,
            "total_chapters": len(self.chapters),
            "characters": list(self.character_registry.keys()),
            "voices_created": list(self.voice_map.keys()),
            "chapters": []
        }
        
        for i, chapter in enumerate(self.chapters):
            manifest["chapters"].append({
                "number": chapter.get('number', i+1),
                "title": chapter.get('title', f'Chapter {i+1}'),
                "word_count": len(chapter.get('content', '').split()),
                "characters_in_chapter": []  # Could be populated by scene analysis
            })
        
        manifest_file = self.output_dir / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"📋 Manifest saved: {manifest_file}")