"""
Main Orchestrator - Coordinates the entire audiobook generation process
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable
from pydub import AudioSegment
import time
import numpy as np
import soundfile as sf

from main import StoryDirector
from character_analyst import CharacterVoiceDesigner
from voice_manager import KokoroVoiceManager
from analysis_cache import AnalysisCache

class AudiobookOrchestrator:
    """
    Master orchestrator that coordinates all components
    """
    
    def __init__(self, 
                 pdf_path: str,
                 groq_api_key: str,
                 model_dir: str = "model_assets",
                 output_dir: str = "audiobook_output"):
        
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        print("🎧 Initializing Audiobook Orchestrator...")
        self.director = StoryDirector(groq_api_key)
        self.character_designer = CharacterVoiceDesigner(groq_api_key)
        self.voice_manager = KokoroVoiceManager(model_dir=model_dir)
        
        # Initialize analysis cache
        self.analysis_cache = AnalysisCache(cache_dir="analysis_cache")
        
        # State
        self.full_text = ""
        self.metadata = {}
        self.chapters = []
        self.character_registry = {}
        self.voice_map = {}  # character -> voice (name, not id)
        self.analysis_from_cache = False  # Track if analysis was from cache
        
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
            # Check if analysis is cached
            cached_analysis = self.analysis_cache.load_analysis(self.pdf_path)
            
            if cached_analysis:
                # Load from cache
                self._update_progress(0.1, "📖 Loading cached book analysis...")
                self.metadata = cached_analysis.get("metadata", {})
                self.chapters = cached_analysis.get("chapters", [])
                self.character_registry = cached_analysis.get("character_registry", {})
                self.voice_map = cached_analysis.get("voice_map", {})
                self.analysis_from_cache = True
                
                self._update_progress(0.3, f"✅ Loaded {len(self.chapters)} chapters from cache")
                return True
            
            # New analysis if not cached
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
            # Skip analysis if it was already loaded from cache
            if self.analysis_from_cache:
                self._update_progress(0.8, "✅ Using cached character analysis")
                return True
            
            self._update_progress(0.4, "Analyzing characters (this may take a moment)...")
            self.character_registry = self.character_designer.analyze_full_book_characters(
                self.full_text
            )
            
            self._update_progress(0.5, "Generating voice design briefs...")
            voice_briefs = self.character_designer.generate_voice_design_briefs()
            
            self._update_progress(0.6, "Mapping characters to Kokoro voices...")
            
            # Map characters to available Kokoro voices
            total_chars = len(self.character_registry)
            for i, (char_name, _) in enumerate(self.character_registry.items()):
                if char_name in voice_briefs:
                    voice = self.voice_manager.map_character_to_voice(
                        char_name,
                        voice_briefs[char_name]
                    )
                    if voice:
                        self.voice_map[char_name] = voice
                
                # Update progress
                progress = 0.6 + (0.2 * (i + 1) / total_chars)
                self._update_progress(progress, f"Mapped voice for: {char_name}")
            
            # Always add a narrator voice
            if "narrator" not in self.voice_map:
                narrator_brief = "A calm, neutral, professional narrator voice, clear articulation, moderate pace, suitable for storytelling."
                narrator_voice = self.voice_manager.map_character_to_voice(
                    "narrator",
                    narrator_brief
                )
                if narrator_voice:
                    self.voice_map["narrator"] = narrator_voice
            
            # Save analysis to cache for future use
            self.analysis_cache.save_analysis(
                self.pdf_path,
                self.metadata,
                self.chapters,
                self.character_registry,
                self.voice_map
            )
            
            self._update_progress(0.8, f"✅ Mapped {len(self.voice_map)} character voices")
            return True
            
        except Exception as e:
            print(f"❌ Error analyzing characters: {e}")
            return False
    
    def generate_chapter(self, 
                        chapter_index: int) -> Optional[str]:
        """
        Generate a single chapter
        
        Args:
            chapter_index: 0-based chapter index
            
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
        
        # Use voice map for this chapter
        chapter_voice_map = self.voice_map.copy()
        
        # Generate each scene
        # Start with empty list - will combine via numpy
        scene_audio_list = []
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
            
            # Generate audio with Kokoro
            success = self.voice_manager.generate_dialogue_scene(
                scene,
                chapter_voice_map,
                str(scene_file)
            )
            
            if success and scene_file.exists():
                try:
                    import soundfile as sf
                    import numpy as np
                    
                    # Load audio as numpy array (more reliable than AudioSegment)
                    audio_data, sr = sf.read(str(scene_file))
                    
                    # Ensure it's 1D (mono)
                    if audio_data.ndim > 1:
                        audio_data = audio_data[:, 0]
                    
                    scene_audio_list.append(audio_data)
                    scene_files.append(str(scene_file))
                    print(f"  ✅ Scene {i+1} loaded: {len(audio_data)} samples")
                    
                    # Add pause between scenes
                    if i < len(scene_data['scenes']) - 1:
                        pause_duration = int(1.0 * 24000)  # 1 second at 24kHz
                        pause = np.zeros(pause_duration)
                        scene_audio_list.append(pause)
                except Exception as e:
                    print(f"  ⚠️ Error loading scene audio: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            else:
                print(f"  ⚠️ Scene generation failed")
        
        # Combine all audio using numpy
        import numpy as np
        import soundfile as sf
        
        if scene_audio_list:
            try:
                chapter_audio_combined = np.concatenate(scene_audio_list)
                
                # Export as WAV first (lossless)
                chapter_wav = self.output_dir / f"chapter_{chapter_num:02d}.wav"
                sf.write(str(chapter_wav), chapter_audio_combined, 24000)
                print(f"  ✅ Chapter WAV saved: {chapter_wav}")
                
                # Convert WAV to MP3 using pydub
                chapter_output = self.output_dir / f"chapter_{chapter_num:02d}.mp3"
                try:
                    wav_audio = AudioSegment.from_wav(str(chapter_wav))
                    wav_audio.export(str(chapter_output), format="mp3", bitrate="192k")
                    print(f"  ✅ Chapter MP3 exported: {chapter_output}")
                except Exception as e:
                    print(f"  ⚠️ MP3 export failed: {e}, using WAV instead")
                    chapter_output = chapter_wav
            except Exception as e:
                print(f"  ❌ Failed to combine audio: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"  ❌ No audio generated for chapter")
            return None
        
        # Clean up scene files (optional)
        for scene_file in scene_files:
            try:
                os.remove(scene_file)
            except:
                pass
        
        self._update_progress(1.0, f"✅ Chapter {chapter_num} complete")
        return str(chapter_output)
    
    def generate_chapters(self, chapter_selection: List[int]) -> List[str]:
        """
        Generate multiple chapters
        
        Args:
            chapter_selection: List of chapter numbers (1-indexed)
            
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
                chapter_file = self.generate_chapter(chapter_idx)
                if chapter_file:
                    generated_files.append(chapter_file)
        
        # If multiple chapters, combine them
        if len(generated_files) > 1:
            self._combine_chapters(generated_files, chapter_selection)
        
        return generated_files
    
    def _combine_chapters(self, chapter_files: List[str], chapter_numbers: List[int]):
        """Combine multiple chapters into one audiobook"""
        import soundfile as sf
        import numpy as np
        
        combined_audio_list = []
        
        # Add introduction
        intro_text = f"{self.metadata.get('title', 'Audiobook')}. By {self.metadata.get('author', 'Unknown')}."
        
        # Generate intro with narrator voice
        intro_file = self.output_dir / "00_introduction.wav"
        if self.voice_manager.generate_dialogue_scene(
            {'dialogue_turns': [], 'narration': intro_text},
            {'narrator': self.voice_map.get('narrator', 'default')},
            str(intro_file)
        ):
            try:
                intro_audio, sr = sf.read(str(intro_file))
                if intro_audio.ndim > 1:
                    intro_audio = intro_audio[:, 0]
                combined_audio_list.append(intro_audio)
                combined_audio_list.append(np.zeros(int(2.0 * 24000)))  # 2 second pause
            except Exception as e:
                print(f"  ⚠️ Error loading intro: {e}")
        
        # Add chapters
        for i, chapter_file in enumerate(chapter_files):
            try:
                # Try loading as WAV first (more reliable)
                if chapter_file.endswith('.wav'):
                    chapter_audio, sr = sf.read(str(chapter_file))
                else:
                    # For MP3, use AudioSegment
                    chapter_audio_seg = AudioSegment.from_mp3(chapter_file)
                    # Convert to numpy
                    samples = np.array(chapter_audio_seg.get_array_of_samples())
                    if chapter_audio_seg.channels == 2:
                        samples = samples.reshape((-1, 2))
                        chapter_audio = samples[:, 0].astype(np.float32) / 32768.0
                    else:
                        chapter_audio = samples.astype(np.float32) / 32768.0
                
                # Ensure mono
                if chapter_audio.ndim > 1:
                    chapter_audio = chapter_audio[:, 0]
                
                combined_audio_list.append(chapter_audio)
                
                if i < len(chapter_files) - 1:
                    combined_audio_list.append(np.zeros(int(3.0 * 24000)))  # 3 second pause
                    
            except Exception as e:
                print(f"  ⚠️ Error loading chapter {i}: {e}")
                continue
        
        # Combine all audio
        if combined_audio_list:
            try:
                combined = np.concatenate(combined_audio_list)
                
                # Export
                if len(chapter_numbers) == len(self.chapters):
                    output_name = f"{self.metadata.get('title', 'book').replace(' ', '_')}_complete.wav"
                else:
                    range_str = f"chapters_{chapter_numbers[0]}_{chapter_numbers[-1]}"
                    output_name = f"{self.metadata.get('title', 'book').replace(' ', '_')}_{range_str}.wav"
                
                output_path = self.output_dir / output_name
                sf.write(str(output_path), combined, 24000)
                print(f"  ✅ Combined audiobook saved: {output_path}")
                
            except Exception as e:
                print(f"  ❌ Failed to combine chapters: {e}")
                import traceback
                traceback.print_exc()
    
    def generate_all_chapters(self) -> List[str]:
        """Generate all chapters in the book"""
        chapter_numbers = list(range(1, len(self.chapters) + 1))
        return self.generate_chapters(chapter_numbers)
    
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
    
    def clear_analysis_cache(self) -> bool:
        """
        Clear cached analysis for this book
        Use this if you want to re-analyze the book
        
        Returns:
            True if successful
        """
        return self.analysis_cache.clear_cache(self.pdf_path)
    
    def get_cache_status(self) -> Dict:
        """
        Get cache status for the current book
        
        Returns:
            Dict with cache information
        """
        has_cache = self.analysis_cache.has_analysis(self.pdf_path)
        return {
            "cached": has_cache,
            "analysis_from_cache": self.analysis_from_cache,
            "cache_key": self.analysis_cache.get_cache_key(self.pdf_path) if has_cache else None,
            "chapters": len(self.chapters),
            "characters": len(self.character_registry)
        }
    
    @staticmethod
    def get_all_cached_books() -> Dict:
        """
        Get statistics about all cached books
        
        Returns:
            Dict with cache statistics
        """
        cache = AnalysisCache()
        return cache.get_cache_stats()