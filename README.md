# 🎙️ Emotional AI Audiobook Agent (In-Progress)
A sophisticated Python-based agent that converts PDF books into emotionally resonant audiobooks. This project uses a Director-Speaker architecture, where an LLM analyzes the emotional context of text before a high-quality local TTS engine synthesizes the speech.

## 🚀 What's Done So Far
### 1. The "Director" Agent (main.py)
LLM Integration: Connected to Groq Cloud API using Llama 3 models for ultra-fast text analysis.

Emotional Intelligence: Developed a system that extracts text from PDFs and generates JSON-formatted "directions" (emotion, reading speed, and pitch) based on the narrative tone.

### 2. The "Speaker" Engine (speaker.py)
Local Inference: Integrated the Kokoro-82M model, a lightweight yet powerful TTS engine that runs entirely on your local machine.

Phoneme Processing: Configured espeak-ng to handle English phonemes for natural-sounding speech.

Dynamic Voice Switching: Implemented a system to switch between different voices (e.g., af_bella and am_daniel) based on the Director's emotional cues.

### 3 . The Orchestrator (orchestrator.py)
Pipeline Automation: Built the master logic to loop through PDF pages, coordinate between the Director and Speaker, and manage temporary audio files.

Audio Synthesis: Successfully generated individual page audio and verified the synthesis pipeline.


## 🛠️ Technical Setup
Prerequisites
Python 3.11+

eSpeak NG: Mandatory system-level phoneme engine for Windows.

FFmpeg: Required for audio file manipulation and merging.

### Core Dependencies
|    |     |
|----|-----|
|PyMuPDF  |      -> PDF text extraction|
|----|-----|
|groq     |      -> AI Director (Llama 3)|
|----|-----|
|kokoro   |      -> AI Speaker (Local TTS)|
|----|-----|
|soundfile|      -> Audio output management|
|----|-----|
|pydub    |      -> Audio stitching|

