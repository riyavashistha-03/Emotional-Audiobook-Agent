"""
Kokoro TTS Engine - Real synthesis using the kokoro pip package (KPipeline)
Supports all available voice .pt files and produces real speech audio.
"""
import numpy as np
from typing import Optional
import re
import os


class TTSEngine:
    """
    Text-to-Speech engine using the official Kokoro KPipeline.
    Loads voice embeddings from local .pt files and synthesizes real speech.
    """

    def __init__(self, model=None, device='cpu'):
        """
        Initialize TTS Engine.

        Args:
            model: Unused (kept for API compatibility). KPipeline is used instead.
            device: Computation device ('cpu' or 'cuda'). Passed to KPipeline.
        """
        self.device = device
        self.sample_rate = 24000
        self._pipeline = None  # Lazy-loaded

    def _get_pipeline(self):
        """Lazily initialize the KPipeline on first use."""
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
                # lang_code='a' = American English
                self._pipeline = KPipeline(lang_code='a')
                print("✅ Kokoro KPipeline initialized successfully")
            except ImportError:
                raise ImportError(
                    "❌ The 'kokoro' package is not installed. "
                    "Run: pip install kokoro"
                )
        return self._pipeline

    def preprocess_text(self, text: str) -> str:
        """Clean and normalize text for TTS."""
        text = ' '.join(text.split())
        # Keep common punctuation for natural prosody
        text = re.sub(r'[^\w\s.,!?\'"\\-]', '', text)
        return text.strip()

    def synthesize(self,
                   text: str,
                   voice_embedding=None,   # kept for API compat (ignored)
                   emotion: str = 'neutral',
                   speed: float = 1.0,
                   voice_name: str = 'af_bella') -> np.ndarray:
        """
        Synthesize audio from text using the real Kokoro KPipeline.

        Args:
            text:            Input text.
            voice_embedding: Ignored (KPipeline loads voices by name internally).
            emotion:         Emotion string — mapped to speed adjustments.
            speed:           Speaking speed multiplier (0.5–2.0).
            voice_name:      Voice name such as 'af_bella', 'am_adam', etc.

        Returns:
            Audio waveform as numpy float32 array (mono, 24 kHz).
        """
        clean_text = self.preprocess_text(text)
        if not clean_text:
            return np.zeros(self.sample_rate // 10, dtype=np.float32)

        # Emotion → slight speed adjustment
        speed = self._apply_emotion_speed(emotion, speed)

        try:
            pipeline = self._get_pipeline()
            audio_chunks = []

            generator = pipeline(
                clean_text,
                voice=voice_name,
                speed=speed,
                # split_pattern splits on sentences so long texts stay natural
            )
            for _, _, audio in generator:
                if audio is not None and len(audio) > 0:
                    audio_chunks.append(audio.astype(np.float32))

            if audio_chunks:
                return np.concatenate(audio_chunks)
            else:
                print(f"⚠️ KPipeline returned empty audio for voice '{voice_name}'")
                return self._silence(len(clean_text))

        except Exception as e:
            print(f"❌ Kokoro synthesis error: {e}")
            return self._silence(len(clean_text))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_emotion_speed(self, emotion: str, base_speed: float) -> float:
        """Map emotion to a speed multiplier on top of base_speed."""
        modifiers = {
            'sad':     0.88,
            'happy':   1.12,
            'angry':   1.10,
            'excited': 1.18,
            'calm':    0.92,
            'neutral': 1.00,
        }
        modifier = modifiers.get(emotion.lower(), 1.00)
        return round(base_speed * modifier, 2)

    def _silence(self, text_length: int) -> np.ndarray:
        """Return silence proportional to estimated speech duration."""
        duration = max(text_length / 10.0, 0.1)
        return np.zeros(int(duration * self.sample_rate), dtype=np.float32)
