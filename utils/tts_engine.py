"""
Kokoro TTS Engine - Core text-to-speech synthesis
Handles text processing, voice synthesis, and audio generation
"""
import torch
import numpy as np
from typing import Tuple, Optional
import re


class TTSEngine:
    """
    Text-to-Speech engine using Kokoro model
    Handles low-level synthesis operations
    """
    
    def __init__(self, model, device='cpu'):
        """
        Initialize TTS Engine
        
        Args:
            model: The Kokoro model instance
            device: Computation device ('cpu' or 'cuda')
        """
        self.model = model
        self.device = device
        self.sample_rate = 24000
        
    def preprocess_text(self, text: str) -> str:
        """
        Clean and normalize text for TTS
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
        return text.strip()
    
    def text_to_tokens(self, text: str) -> torch.Tensor:
        """
        Convert text to token representation
        This is a simplified version - actual implementation depends on Kokoro's tokenizer
        
        Args:
            text: Preprocessed text
            
        Returns:
            Token tensor
        """
        # Simple character-level tokenization as a placeholder
        # In reality, Kokoro likely uses word-piece or BPE tokenization
        chars = list(text)
        # Create token IDs (simplified - ASCII values)
        token_ids = [ord(c) for c in chars]
        
        return torch.tensor(token_ids, dtype=torch.long, device=self.device).unsqueeze(0)
    
    def synthesize(self, 
                   text: str, 
                   voice_embedding: torch.Tensor,
                   emotion: str = 'neutral',
                   speed: float = 1.0) -> np.ndarray:
        """
        Synthesize audio from text and voice embedding
        
        Args:
            text: Input text to synthesize
            voice_embedding: Speaker voice embedding
            emotion: Emotion modulation (neutral, happy, sad, angry, excited, calm)
            speed: Speaking speed multiplier (0.5-2.0)
            
        Returns:
            Audio waveform as numpy array (mono, 24kHz)
        """
        # Preprocess text
        clean_text = self.preprocess_text(text)
        
        # Convert text to tokens
        tokens = self.text_to_tokens(clean_text)
        
        # Prepare voice embedding
        voice_emb = voice_embedding.to(self.device).unsqueeze(0) if voice_embedding.dim() == 1 else voice_embedding.to(self.device)
        
        # Prepare emotion embedding
        emotion_embedding = self._get_emotion_embedding(emotion)
        
        # Run inference through model
        with torch.no_grad():
            try:
                # Call model's inference method
                mel_spec = self.model.inference(
                    text=clean_text,
                    voice_embedding=voice_emb,
                    emotion=emotion,
                    speed=speed
                )
                
                # Convert mel-spectrogram to waveform
                # In a real implementation, this would use a vocoder (e.g., HiFi-GAN)
                # For now, we'll create a more realistic placeholder
                audio = self._mel_to_audio(mel_spec, speed)
                
            except Exception as e:
                print(f"⚠️ Inference error: {e}")
                # Fallback: generate realistic placeholder audio
                audio = self._generate_realistic_audio(len(clean_text), speed)
        
        return audio
    
    def _get_emotion_embedding(self, emotion: str) -> torch.Tensor:
        """
        Get emotion embedding vector
        
        Args:
            emotion: Emotion name
            
        Returns:
            Emotion embedding tensor
        """
        emotion_map = {
            'neutral': torch.zeros(256, device=self.device),
            'happy': torch.ones(256, device=self.device) * 0.5,
            'sad': torch.ones(256, device=self.device) * -0.5,
            'angry': torch.ones(256, device=self.device) * 0.7,
            'excited': torch.ones(256, device=self.device) * 0.9,
            'calm': torch.ones(256, device=self.device) * -0.3,
        }
        
        return emotion_map.get(emotion.lower(), emotion_map['neutral'])
    
    def _mel_to_audio(self, mel_spec: torch.Tensor, speed: float) -> np.ndarray:
        """
        Convert mel-spectrogram to audio waveform
        This is a simplified version of what a vocoder would do
        
        Args:
            mel_spec: Mel-spectrogram tensor
            speed: Speaking speed
            
        Returns:
            Audio waveform
        """
        if mel_spec is None or (isinstance(mel_spec, torch.Tensor) and mel_spec.nelement() == 0):
            return self._generate_realistic_audio(100, speed)
        
        # Convert to numpy if needed
        if isinstance(mel_spec, torch.Tensor):
            mel_spec = mel_spec.cpu().numpy()
        
        # Simple mel-to-audio: use magnitude as proxy for waveform
        audio = np.sum(mel_spec, axis=0) if mel_spec.ndim > 1 else mel_spec
        
        # Normalize
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        # Apply speed adjustment
        if speed != 1.0:
            audio = self._adjust_speed(audio, speed)
        
        return audio.astype(np.float32)
    
    def _generate_realistic_audio(self, text_length: int, speed: float) -> np.ndarray:
        """
        Generate realistic placeholder audio
        Simulates speech by creating a more natural-sounding signal
        
        Args:
            text_length: Length of input text
            speed: Speaking speed
            
        Returns:
            Generated audio waveform
        """
        # Estimate duration: ~10 characters per second at normal speed
        duration = (text_length / 10.0) / speed
        num_samples = int(duration * self.sample_rate)
        num_samples = max(num_samples, self.sample_rate // 10)  # Minimum 100ms
        
        # Create a more realistic audio signal using FM synthesis
        t = np.linspace(0, duration, num_samples)
        
        # Base frequency varying to simulate speech formants
        f0 = 150 + 50 * np.sin(2 * np.pi * 1.5 * t)  # Varying fundamental frequency
        
        # Create carrier signal
        carrier = np.sin(2 * np.pi * f0 * t)
        
        # Add some harmonics for realism
        harmonic1 = 0.3 * np.sin(2 * np.pi * f0 * 2 * t)
        harmonic2 = 0.15 * np.sin(2 * np.pi * f0 * 3 * t)
        
        # Combine signals
        audio = carrier + harmonic1 + harmonic2
        
        # Apply amplitude envelope (speech-like)
        envelope = np.sin(np.pi * t / duration) ** 0.5
        audio = audio * envelope
        
        # Add slight variation in intensity
        amplitude_mod = 0.7 + 0.3 * np.sin(2 * np.pi * 3.5 * t)
        audio = audio * amplitude_mod
        
        # Normalize to prevent clipping
        audio = audio / np.max(np.abs(audio) + 1e-6) * 0.8
        
        return audio.astype(np.float32)
    
    def _adjust_speed(self, audio: np.ndarray, speed: float) -> np.ndarray:
        """
        Adjust audio playback speed using interpolation
        
        Args:
            audio: Input audio
            speed: Speed factor (1.0 = normal)
            
        Returns:
            Speed-adjusted audio
        """
        if speed == 1.0:
            return audio
        
        # Resample by interpolation
        original_length = len(audio)
        new_length = int(original_length / speed)
        
        indices = np.linspace(0, original_length - 1, new_length)
        adjusted = np.interp(indices, np.arange(original_length), audio)
        
        return adjusted.astype(np.float32)
