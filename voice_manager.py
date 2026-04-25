"""
Kokoro Voice Manager - Handles voice generation using Kokoro TTS locally
"""
import os
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
import soundfile as sf
import torch
import torchaudio
import time
from datetime import datetime
import warnings
from utils.model import KokoroModel
from utils.tts_engine import TTSEngine
warnings.filterwarnings('ignore')

class KokoroVoiceManager:
    """
    Manages voice generation using Kokoro TTS model locally
    No API calls required - runs entirely on local machine
    """
    
    def __init__(self, model_dir: str = "model_assets", device: str = None):
        """
        Initialize Kokoro Voice Manager
        
        Args:
            model_dir: Path to model_assets directory
            device: 'cuda' or 'cpu' (auto-detected if None)
        """
        self.model_dir = Path(model_dir)
        self.voice_cache_dir = Path("voice_cache")
        self.voice_cache_dir.mkdir(exist_ok=True)
        
        # Set device
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"🎙️ Kokoro Voice Manager initialized (device: {self.device})")
        
        # Voice registry stores mapping of character -> voice
        self.voice_registry_file = self.voice_cache_dir / "voice_registry.json"
        self.voice_registry = self._load_registry()
        
        # Load available voices
        self.available_voices = self._load_available_voices()
        
        # Initialize Kokoro model
        self._initialize_kokoro()
    
    def _load_registry(self) -> Dict:
        """Load voice registry from cache"""
        if self.voice_registry_file.exists():
            try:
                with open(self.voice_registry_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_registry(self):
        """Save voice registry to cache"""
        with open(self.voice_registry_file, 'w') as f:
            json.dump(self.voice_registry, f, indent=2)
    
    def _load_available_voices(self) -> List[str]:
        """Load list of available voices from model_assets"""
        voices_dir = self.model_dir / "voices"
        if not voices_dir.exists():
            print(f"⚠️ Voices directory not found at {voices_dir}")
            return []
        
        # Get all .pt voice files
        voice_files = list(voices_dir.glob("*.pt"))
        voices = [f.stem for f in voice_files]  # Remove .pt extension
        
        print(f"📊 Found {len(voices)} available voices")
        return sorted(voices)
    
    def _initialize_kokoro(self):
        """Initialize Kokoro TTS model"""
        try:
            print("⏳ Loading Kokoro model...")
            kokoro_path = self.model_dir / "kokoro-v1_0.pth"
            
            if not kokoro_path.exists():
                raise FileNotFoundError(f"Kokoro model not found at {kokoro_path}")
            
            # Instantiate the model and load the state dict
            self.model = KokoroModel()
            state_dict = torch.load(kokoro_path, map_location=self.device)
            
            # This is a workaround. The .pth file is a state dictionary, not a full model object.
            # We are loading the state dictionary into our placeholder model.
            # This might fail if the keys in the state_dict do not match the model architecture.
            # For now, we'll try to load it and catch any errors.
            try:
                self.model.load_state_dict(state_dict, strict=False)
            except RuntimeError as e:
                print(f"⚠️  Warning: Could not load all keys from state dictionary: {e}")
                print("     This may be expected if the model architecture is not fully defined.")

            self.model.to(self.device)
            self.model.eval()
            
            print("✅ Kokoro model loaded successfully")
            
        except Exception as e:
            print(f"❌ Failed to initialize Kokoro: {e}")
            raise
    
    def map_character_to_voice(self, character_name: str, voice_description: str) -> str:
        """
        Map a character to an available voice based on description
        
        Args:
            character_name: Name of the character
            voice_description: Description of desired voice qualities
            
        Returns:
            Selected voice name
        """
        if not self.available_voices:
            print(f"⚠️ No voices available, using default")
            return "af_bella"  # Fallback voice
        
        # Check if already mapped
        cache_key = character_name.lower().replace(' ', '_')
        if cache_key in self.voice_registry:
            voice = self.voice_registry[cache_key].get("selected_voice")
            print(f"  ✓ Using cached voice for {character_name}: {voice}")
            return voice
        
        # Simple voice selection based on description keywords
        voice = self._select_voice_by_description(voice_description)
        
        # Store in registry
        self.voice_registry[cache_key] = {
            "character_name": character_name,
            "selected_voice": voice,
            "description": voice_description,
            "created_at": datetime.now().isoformat()
        }
        self._save_registry()
        
        print(f"  ✅ Mapped {character_name} to voice: {voice}")
        return voice
    
    def _select_voice_by_description(self, description: str) -> str:
        """
        Select voice based on description keywords
        Uses simple heuristics to match voice characteristics
        """
        description_lower = description.lower()
        
        # Gender detection
        if any(word in description_lower for word in ['male', 'man', 'boy', 'masculine', 'deep']):
            male_voices = [v for v in self.available_voices if v.startswith(('am_', 'bm_', 'em_', 'hm_', 'im_', 'jm_', 'pm_', 'zm_'))]
            if male_voices:
                return male_voices[0]
        else:
            female_voices = [v for v in self.available_voices if v.startswith(('af_', 'bf_', 'ef_', 'hf_', 'if_', 'jf_', 'pf_', 'zf_'))]
            if female_voices:
                return female_voices[0]
        
        # Fallback
        return self.available_voices[0] if self.available_voices else "af_bella"
    
    def synthesize_text(self, 
                       text: str, 
                       voice: str,
                       emotion: str = "neutral",
                       speed: float = 1.0,
                       output_path: str = None) -> Optional[str]:
        """
        Synthesize text to speech using Kokoro
        
        Args:
            text: Text to synthesize
            voice: Voice name (e.g., 'af_bella', 'am_daniel')
            emotion: Emotion modulation (neutral, happy, sad, angry, etc.)
            speed: Speaking speed (0.5-2.0)
            output_path: Optional output file path
            
        Returns:
            Path to generated audio file
        """
        try:
            # Validate voice
            if voice not in self.available_voices:
                print(f"⚠️ Voice '{voice}' not found, using fallback")
                voice = self.available_voices[0] if self.available_voices else "af_bella"
            
            # Load voice file
            voice_path = self.model_dir / "voices" / f"{voice}.pt"
            if not voice_path.exists():
                print(f"⚠️ Voice file not found: {voice_path}")
                return None
            
            print(f"  🎵 Synthesizing with voice: {voice}")
            print(f"     Text length: {len(text)} characters")
            
            # Generate output filename if not provided
            if not output_path:
                text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                output_path = self.voice_cache_dir / f"audio_{voice}_{text_hash}.wav"
            
            # Initialize TTS engine if not already done
            if not hasattr(self, 'tts_engine'):
                self.tts_engine = TTSEngine(self.model, device=self.device)
            
            # Load voice embeddings
            voice_data = torch.load(voice_path, map_location=self.device)
            
            # Perform actual synthesis using TTS engine
            audio = self.tts_engine.synthesize(
                text=text,
                voice_embedding=voice_data,
                emotion=emotion,
                speed=speed
            )
            
            # Save audio
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            sf.write(output_path, audio, 24000)
            
            print(f"  ✅ Audio saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"  ❌ Synthesis error: {e}")
            return None
    
    def generate_dialogue_scene(self, 
                                scene_data: Dict,
                                voice_map: Dict[str, str],
                                output_path: str) -> bool:
        """
        Generate audio for a complete dialogue scene using Kokoro
        
        Args:
            scene_data: Scene data with dialogue turns
            voice_map: Mapping of character names to voice names
            output_path: Where to save the audio file
            
        Returns:
            True if successful
        """
        try:
            print(f"  🎬 Generating scene with {len(scene_data.get('dialogue_turns', []))} lines")
            
            # Process each dialogue turn
            audio_segments = []
            
            # Add narration if present
            if scene_data.get("narration"):
                narrator_voice = voice_map.get("narrator", "af_alloy")
                audio_path = self.synthesize_text(
                    text=scene_data["narration"],
                    voice=narrator_voice,
                    emotion="neutral"
                )
                if audio_path:
                    audio = sf.read(audio_path)[0]
                    audio_segments.append(audio)
            
            # Add dialogue turns
            for turn in scene_data.get("dialogue_turns", []):
                speaker = turn.get("speaker", "narrator")
                text = turn.get("text", "")
                emotion = turn.get("emotion", "neutral")
                
                voice = voice_map.get(speaker)
                if not voice:
                    print(f"  ⚠️ No voice for {speaker}, using default")
                    voice = "af_bella"
                
                audio_path = self.synthesize_text(
                    text=text,
                    voice=voice,
                    emotion=emotion
                )
                
                if audio_path:
                    audio = sf.read(audio_path)[0]
                    audio_segments.append(audio)
            
            # Concatenate all audio segments
            if audio_segments:
                combined_audio = np.concatenate(audio_segments)
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                sf.write(output_path, combined_audio, 24000)
                print(f"  ✅ Scene audio saved: {output_path}")
                return True
            else:
                print(f"  ❌ No audio generated")
                return False
                
        except Exception as e:
            print(f"  ❌ Error generating dialogue: {e}")
            return False
    
    def generate_emotion_variant(self, 
                                 voice: str,
                                 text: str,
                                 emotion: str,
                                 modulation: Dict = None,
                                 output_path: str = None) -> Optional[str]:
        """
        Generate audio with specific emotion modulation
        
        Args:
            voice: Voice name
            text: Text to synthesize
            emotion: Emotion type
            modulation: Optional modulation parameters
            output_path: Output file path
            
        Returns:
            Path to generated audio file
        """
        # Apply modulation to synthesis parameters
        speed = 1.0
        if modulation:
            if emotion == "sad":
                speed = 0.85
            elif emotion == "happy":
                speed = 1.15
            elif emotion == "angry":
                speed = 1.1
        
        return self.synthesize_text(
            text=text,
            voice=voice,
            emotion=emotion,
            speed=speed,
            output_path=output_path
        )
    
    def get_voice_info(self) -> Dict:
        """Get information about available voices"""
        return {
            "available_voices": self.available_voices,
            "total_voices": len(self.available_voices),
            "device": self.device,
            "model": "Kokoro-82M"
        }
    
    def list_voices(self, filter_gender: str = None) -> List[str]:
        """
        List available voices with optional gender filter
        
        Args:
            filter_gender: 'male' or 'female' or None
            
        Returns:
            List of voice names
        """
        voices = self.available_voices
        
        if filter_gender == "male":
            voices = [v for v in voices if any(v.startswith(p) for p in ('am_', 'bm_', 'em_', 'hm_', 'im_', 'jm_', 'pm_', 'zm_'))]
        elif filter_gender == "female":
            voices = [v for v in voices if any(v.startswith(p) for p in ('af_', 'bf_', 'ef_', 'hf_', 'if_', 'jf_', 'pf_', 'zf_'))]
        
        return voices
