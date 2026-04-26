"""
model.py — legacy stub kept for import compatibility.
The actual TTS inference is now handled by kokoro.KPipeline inside voice_manager.py.
This file is no longer used for synthesis but kept to avoid import errors.
"""

import torch
import torch.nn as nn


class KokoroModel(nn.Module):
    """
    Stub model class — no longer used for inference.
    Synthesis is delegated to kokoro.KPipeline in voice_manager.py.
    """

    def __init__(self, hidden_size=384, num_layers=4):
        super().__init__()
        # Minimal placeholder so torch.load / load_state_dict don't crash
        self._placeholder = nn.Linear(1, 1)

    def forward(self, x):
        return x

    def inference(self, text: str, voice_embedding, emotion: str, speed: float):
        raise NotImplementedError(
            "KokoroModel.inference is deprecated. "
            "Use kokoro.KPipeline directly via KokoroVoiceManager."
        )
