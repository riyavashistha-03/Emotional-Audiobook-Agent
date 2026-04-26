"""
Kokoro Voice Manager — Real TTS using the official kokoro pip package (KPipeline).
All synthesis is done locally; no external API calls.
Voice .pt files are loaded from model_assets/voices/ by the Kokoro pipeline.
"""

import os
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
import soundfile as sf
import time
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


class KokoroVoiceManager:
    """
    Manages voice generation using the official Kokoro TTS KPipeline.
    Uses local .pt voice files from model_assets/voices/.
    """

    def __init__(self, model_dir: str = "model_assets", device: str = None):
        """
        Initialize Kokoro Voice Manager.

        Args:
            model_dir: Path to model_assets directory (contains voices/).
            device:    'cuda' or 'cpu' (auto-detected if None). Currently KPipeline
                       handles device selection internally, so this is informational.
        """
        self.model_dir = Path(model_dir)
        self.voice_cache_dir = Path("voice_cache")
        self.voice_cache_dir.mkdir(exist_ok=True)

        import torch
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"🎙️ Kokoro Voice Manager initializing (device: {self.device})")

        # Voice registry: character → voice name
        self.voice_registry_file = self.voice_cache_dir / "voice_registry.json"
        self.voice_registry = self._load_registry()

        # Discover available voices from local .pt files
        self.available_voices = self._load_available_voices()

        # Initialize the real KPipeline
        self._pipeline = None
        self._init_pipeline()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_registry(self) -> Dict:
        """Load voice registry from cache."""
        if self.voice_registry_file.exists():
            try:
                with open(self.voice_registry_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_registry(self):
        """Persist voice registry."""
        with open(self.voice_registry_file, 'w') as f:
            json.dump(self.voice_registry, f, indent=2)

    def _load_available_voices(self) -> List[str]:
        """List voice names from model_assets/voices/*.pt files."""
        voices_dir = self.model_dir / "voices"
        if not voices_dir.exists():
            print(f"⚠️  Voices directory not found at {voices_dir}")
            return []

        voice_files = list(voices_dir.glob("*.pt"))
        # Exclude non-voice .pt files (e.g. utility scripts accidentally named .pt)
        voices = sorted(f.stem for f in voice_files
                        if len(f.stem) > 2 and '_' in f.stem)

        print(f"📊 Found {len(voices)} available voices")
        return voices

    def _init_pipeline(self):
        """Load the real Kokoro KPipeline."""
        try:
            from kokoro import KPipeline
            print("⏳ Loading Kokoro KPipeline…")
            # lang_code='a' = American English (covers all af_*/am_* voices)
            self._pipeline = KPipeline(lang_code='a')
            print("✅ Kokoro KPipeline ready")
        except ImportError:
            print("❌ kokoro package not found. Run:  pip install kokoro")
            raise
        except Exception as e:
            print(f"❌ Failed to load KPipeline: {e}")
            raise

    # ------------------------------------------------------------------
    # Voice mapping
    # ------------------------------------------------------------------

    def map_character_to_voice(self, character_name: str,
                               voice_description: str) -> str:
        """
        Map a character to an available voice based on description keywords.

        Args:
            character_name:    Character name.
            voice_description: Description of desired voice qualities.

        Returns:
            Selected voice name (e.g. 'af_bella').
        """
        if not self.available_voices:
            print(f"⚠️  No voices available, using default 'af_bella'")
            return "af_bella"

        cache_key = character_name.lower().replace(' ', '_')

        # Return cached mapping if present
        if cache_key in self.voice_registry:
            voice = self.voice_registry[cache_key].get("selected_voice")
            if voice and voice in self.available_voices:
                print(f"  ✓ Using cached voice for {character_name}: {voice}")
                return voice

        # Select by description
        voice = self._select_voice_by_description(voice_description)

        self.voice_registry[cache_key] = {
            "character_name": character_name,
            "selected_voice": voice,
            "description": voice_description,
            "created_at": datetime.now().isoformat(),
        }
        self._save_registry()

        print(f"  ✅ Mapped {character_name} → {voice}")
        return voice

    def _select_voice_by_description(self, description: str) -> str:
        """Heuristic voice selection based on gender / age keywords."""
        desc = description.lower()

        is_male = any(w in desc for w in
                      ['male', 'man', 'boy', 'masculine', 'deep', 'baritone', 'bass'])

        if is_male:
            # Prefer American male, then British male
            for prefix in ('am_', 'bm_', 'em_', 'hm_', 'im_', 'jm_', 'pm_', 'zm_'):
                candidates = [v for v in self.available_voices
                              if v.startswith(prefix)]
                if candidates:
                    return candidates[0]
        else:
            # Prefer American female, then British female
            for prefix in ('af_', 'bf_', 'ef_', 'hf_', 'if_', 'jf_', 'pf_', 'zf_'):
                candidates = [v for v in self.available_voices
                              if v.startswith(prefix)]
                if candidates:
                    return candidates[0]

        return self.available_voices[0] if self.available_voices else "af_bella"

    # ------------------------------------------------------------------
    # Core synthesis
    # ------------------------------------------------------------------

    def synthesize_text(self,
                        text: str,
                        voice: str,
                        emotion: str = "neutral",
                        speed: float = 1.0,
                        output_path: str = None) -> Optional[str]:
        """
        Synthesize text to speech using the real Kokoro KPipeline.

        Args:
            text:        Text to synthesize.
            voice:       Voice name (e.g. 'af_bella', 'am_adam').
            emotion:     Emotion label for speed/pitch adjustments.
            speed:       Base speaking speed (0.5–2.0).
            output_path: Where to save the .wav file.

        Returns:
            Path to the saved .wav file, or None on failure.
        """
        if not text or not text.strip():
            return None

        # Validate voice
        if voice not in self.available_voices:
            print(f"  ⚠️  Voice '{voice}' not in local list; trying anyway…")

        # Emotion → speed adjustment
        speed = self._emotion_speed(emotion, speed)

        # Auto output path
        if not output_path:
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = str(
                self.voice_cache_dir / f"audio_{voice}_{text_hash}.wav"
            )

        print(f"  🎵 Synthesizing | voice={voice} | len={len(text)} chars | "
              f"emotion={emotion} | speed={speed:.2f}")

        try:
            audio_chunks = []
            generator = self._pipeline(text, voice=voice, speed=speed)
            for _, _, audio in generator:
                if audio is not None:
                    # Kokoro might return a torch.Tensor or a numpy array
                    if hasattr(audio, 'numpy'):
                        audio_np = audio.detach().cpu().numpy()
                    else:
                        audio_np = audio
                    
                    if len(audio_np) > 0:
                        audio_chunks.append(audio_np.astype(np.float32))

            if not audio_chunks:
                print(f"  ❌ KPipeline produced no audio")
                return None

            audio_array = np.concatenate(audio_chunks)
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            sf.write(output_path, audio_array, 24000)
            print(f"  ✅ Saved: {output_path}")
            return output_path

        except Exception as e:
            print(f"  ❌ Synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Scene / dialogue helpers
    # ------------------------------------------------------------------

    def generate_dialogue_scene(self,
                                scene_data: Dict,
                                voice_map: Dict[str, str],
                                output_path: str) -> bool:
        """
        Generate audio for a complete dialogue scene.

        Args:
            scene_data:  Dict with 'narration' and 'dialogue_turns'.
            voice_map:   Mapping of character names → voice names.
            output_path: Where to save the combined .wav.

        Returns:
            True if audio was successfully written.
        """
        print(f"  🎬 Scene: {len(scene_data.get('dialogue_turns', []))} lines")

        audio_segments: List[np.ndarray] = []

        # Narration first
        narration = scene_data.get("narration", "").strip()
        if narration:
            narrator_voice = voice_map.get("narrator", "af_bella")
            if narrator_voice not in self.available_voices:
                narrator_voice = "af_bella"
            path = self.synthesize_text(narration, narrator_voice, "neutral")
            if path:
                audio, _ = sf.read(path)
                audio_segments.append(
                    audio[:, 0] if audio.ndim > 1 else audio
                )

        # Dialogue turns
        for turn in scene_data.get("dialogue_turns", []):
            speaker = turn.get("speaker", "narrator")
            text    = turn.get("text", "").strip()
            emotion = turn.get("emotion", "neutral")

            if not text:
                continue

            voice = voice_map.get(speaker)
            if not voice:
                # Try case-insensitive lookup
                for k, v in voice_map.items():
                    if k.lower() == speaker.lower():
                        voice = v
                        break
            if not voice:
                print(f"  ⚠️  No voice mapped for '{speaker}', using narrator voice")
                voice = voice_map.get("narrator", "af_bella")

            path = self.synthesize_text(text, voice, emotion)
            if path:
                audio, _ = sf.read(path)
                audio_segments.append(
                    audio[:, 0] if audio.ndim > 1 else audio
                )
                # Small inter-turn pause (0.3 s)
                audio_segments.append(
                    np.zeros(int(0.3 * 24000), dtype=np.float32)
                )

        if not audio_segments:
            print(f"  ❌ No audio generated for scene")
            return False

        combined = np.concatenate(audio_segments).astype(np.float32)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        sf.write(output_path, combined, 24000)
        print(f"  ✅ Scene saved: {output_path}")
        return True

    def generate_emotion_variant(self,
                                 voice: str,
                                 text: str,
                                 emotion: str,
                                 modulation: Dict = None,
                                 output_path: str = None) -> Optional[str]:
        """Generate audio with emotion modulation."""
        speed = 1.0
        if modulation:
            speed = modulation.get("speed_multiplier", 1.0)
        return self.synthesize_text(text, voice, emotion, speed, output_path)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _emotion_speed(self, emotion: str, base: float) -> float:
        mods = {
            'sad': 0.88, 
            'happy': 1.12, 
            'angry': 1.15,
            'excited': 1.25, 
            'calm': 0.90, 
            'neutral': 1.00,
            'whispering': 0.70,
            'screaming': 1.40,
            'crying': 0.80,
            'shouting': 1.30,
            'urgent': 1.20,
            'soft': 0.85
        }
        return round(base * mods.get(emotion.lower(), 1.00), 2)

    def get_voice_info(self) -> Dict:
        return {
            "available_voices": self.available_voices,
            "total_voices": len(self.available_voices),
            "device": self.device,
            "model": "Kokoro-82M (KPipeline)",
        }

    def list_voices(self, filter_gender: str = None) -> List[str]:
        male_prefixes   = ('am_', 'bm_', 'em_', 'hm_', 'im_', 'jm_', 'pm_', 'zm_')
        female_prefixes = ('af_', 'bf_', 'ef_', 'hf_', 'if_', 'jf_', 'pf_', 'zf_')

        if filter_gender == "male":
            return [v for v in self.available_voices
                    if any(v.startswith(p) for p in male_prefixes)]
        if filter_gender == "female":
            return [v for v in self.available_voices
                    if any(v.startswith(p) for p in female_prefixes)]
        return list(self.available_voices)
