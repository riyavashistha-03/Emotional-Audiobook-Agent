"""
MOSS Voice Manager - Handles voice generation and caching for MOSS-TTS
"""
import os
import json
import hashlib
import requests
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
import soundfile as sf
import torch
import time
from datetime import datetime

class MOSSVoiceManager:
    """
    Manages voice generation using MOSS-VoiceGenerator and MOSS-TTSD
    Assumes MOSS services are running locally or on a accessible server
    """
    
    def __init__(self, moss_api_url: str = "http://localhost:7860"):
        """
        Initialize MOSS Voice Manager
        
        Args:
            moss_api_url: URL where MOSS services are running
                         (default assumes local deployment)
        """
        self.api_url = moss_api_url
        self.voice_cache_dir = Path("voice_cache")
        self.voice_cache_dir.mkdir(exist_ok=True)
        
        # Voice registry stores mapping of character -> voice_id
        self.voice_registry_file = self.voice_cache_dir / "voice_registry.json"
        self.voice_registry = self._load_registry()
        
        # Check if MOSS services are available
        self._check_moss_availability()
        
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
    
    def _check_moss_availability(self):
        """Check if MOSS services are running"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ MOSS-TTS services available")
            else:
                print("⚠️ MOSS-TTS services not responding, will use mock mode")
        except:
            print("⚠️ MOSS-TTS services not available, will use mock mode")
            print("   To use real voices, deploy MOSS-TTSD locally")
            print("   See: https://github.com/OpenMOSS/MOSS-TTSD")
    
    def create_voice_from_description(self, character_name: str, voice_description: str) -> Optional[str]:
        """
        Generate a voice from text description using MOSS-VoiceGenerator
        
        Args:
            character_name: Name of the character
            voice_description: Detailed voice description from CharacterVoiceDesigner
            
        Returns:
            voice_id if successful, None otherwise
        """
        print(f"🎤 Creating voice for: {character_name}")
        
        # Create unique hash of description to avoid recreating
        desc_hash = hashlib.md5(voice_description.encode()).hexdigest()[:10]
        cache_key = f"{character_name.lower().replace(' ', '_')}_{desc_hash}"
        
        # Check if already cached
        if cache_key in self.voice_registry:
            print(f"  ✓ Using cached voice: {cache_key}")
            return self.voice_registry[cache_key]["voice_id"]
        
        # Prepare request for MOSS-VoiceGenerator
        payload = {
            "description": voice_description,
            "character_name": character_name,
            "language": "en",
            "quality": "high"  # or "fast"
        }
        
        try:
            # Call MOSS-VoiceGenerator
            response = requests.post(
                f"{self.api_url}/generate_voice",
                json=payload,
                timeout=120  # Voice generation can take time
            )
            
            if response.status_code == 200:
                result = response.json()
                voice_id = result.get("voice_id")
                
                if voice_id:
                    # Store in registry
                    self.voice_registry[cache_key] = {
                        "voice_id": voice_id,
                        "character_name": character_name,
                        "description": voice_description,
                        "created_at": datetime.now().isoformat()
                    }
                    self._save_registry()
                    print(f"  ✅ Voice created: {voice_id}")
                    return voice_id
                else:
                    print(f"  ❌ No voice_id in response")
                    return None
            else:
                print(f"  ❌ MOSS error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error creating voice: {e}")
            return None
    
    def generate_dialogue_scene(self, 
                                scene_data: Dict,
                                voice_map: Dict[str, str],
                                output_path: str) -> bool:
        """
        Generate audio for a complete dialogue scene using MOSS-TTSD
        
        Args:
            scene_data: Scene data from CharacterVoiceDesigner.parse_dialogue_scene()
            voice_map: Mapping of character names to voice_ids
            output_path: Where to save the audio file
            
        Returns:
            True if successful
        """
        print(f"  🎬 Generating scene with {len(scene_data.get('dialogue_turns', []))} lines")
        
        # Prepare MOSS-TTSD request
        speakers = []
        dialogue_turns = []
        
        for turn in scene_data.get("dialogue_turns", []):
            speaker = turn.get("speaker", "narrator")
            text = turn.get("text", "")
            emotion = turn.get("emotion", "neutral")
            
            voice_id = voice_map.get(speaker)
            if not voice_id:
                print(f"  ⚠️ No voice for {speaker}, using default")
                voice_id = "default_narrator"
            
            # Get emotion modulation if available
            modulation = {}
            if "emotion_params" in turn:
                modulation = turn["emotion_params"]
            
            dialogue_turns.append({
                "speaker": speaker,
                "voice_id": voice_id,
                "text": text,
                "emotion": emotion,
                "modulation": modulation
            })
        
        # Add narration if present
        if scene_data.get("narration"):
            narrator_id = voice_map.get("narrator", "default_narrator")
            dialogue_turns.insert(0, {
                "speaker": "narrator",
                "voice_id": narrator_id,
                "text": scene_data["narration"],
                "emotion": "neutral",
                "modulation": {}
            })
        
        payload = {
            "dialogue": dialogue_turns,
            "sample_rate": 24000,
            "format": "wav",
            "scene_type": "audiobook"
        }
        
        try:
            # Call MOSS-TTSD
            response = requests.post(
                f"{self.api_url}/generate_dialogue",
                json=payload,
                timeout=300  # Dialogue generation can be slow
            )
            
            if response.status_code == 200:
                # Save audio file
                audio_data = response.content
                
                # Response could be WAV bytes or JSON with audio path
                if response.headers.get("content-type") == "audio/wav":
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                else:
                    # Handle JSON response with audio path
                    result = response.json()
                    audio_path = result.get("audio_path")
                    if audio_path and os.path.exists(audio_path):
                        import shutil
                        shutil.copy(audio_path, output_path)
                    else:
                        print(f"  ❌ No audio in response")
                        return False
                
                print(f"  ✅ Scene audio saved: {output_path}")
                return True
            else:
                print(f"  ❌ MOSS error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error generating dialogue: {e}")
            return False
    
    def generate_emotion_variant(self, 
                                 voice_id: str,
                                 text: str,
                                 emotion: str,
                                 modulation: Dict,
                                 output_path: str) -> bool:
        """
        Generate audio with specific emotion modulation
        """
        payload = {
            "voice_id": voice_id,
            "text": text,
            "emotion": emotion,
            "modulation": modulation,
            "sample_rate": 24000
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/synthesize",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            else:
                return False
        except:
            return False
    
    def get_mock_voice_id(self, character_name: str) -> str:
        """Generate a mock voice ID for testing without MOSS"""
        mock_id = f"mock_{character_name.lower().replace(' ', '_')}"
        return mock_id
