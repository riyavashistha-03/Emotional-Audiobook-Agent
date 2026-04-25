# 🎙️ Emotional AI Audiobook Agent

A sophisticated Python-based agent that transforms PDF books into emotionally intelligent audiobooks. This project uses a Director-Speaker architecture where an LLM analyzes emotional context before Kokoro TTS synthesizes natural, expressive speech entirely on your local machine.

## 🚀 Key Features

✅ **No API Dependencies** - Kokoro TTS runs entirely locally (no internet required for synthesis)
✅ **Emotional Analysis** - Groq's Llama 3 analyzes emotional context in real-time  
✅ **Character Voice Mapping** - Automatically assigns diverse voices to different characters  
✅ **Local Processing** - Your data never leaves your machine  
✅ **Fast Rendering** - 82M parameter Kokoro model is lightweight and efficient  
✅ **Web Interface** - Beautiful Streamlit UI for easy audiobook creation  

---

## 🛠️ Technical Architecture

### Components

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **Story Director** | Analyzes PDF & extracts emotional cues | Groq API + Llama 3 |
| **Character Analyst** | Identifies characters & voice traits | Groq API + Prompting |
| **Voice Manager** | Maps characters to voices | Kokoro TTS (Local) |
| **Orchestrator** | Coordinates entire pipeline | PyDAub + Audio Processing |
| **Interface** | Web UI for users | Streamlit |

### The Pipeline

```
PDF Input
    ↓
[Extract Text] (PyMuPDF)
    ↓
[LLM Analysis] (Groq/Llama 3)
    ├─ Extract metadata (title, author)
    ├─ Detect chapters
    └─ Identify characters & emotions
    ↓
[Voice Mapping] (Kokoro)
    ├─ Map characters to voices
    └─ Create voice registry
    ↓
[Audio Synthesis] (Kokoro TTS - Local)
    ├─ Generate dialogue per scene
    ├─ Add emotion modulation
    └─ Combine into chapters
    ↓
Audio Exports (MP3)
```

---

## 📋 Prerequisites

### System Requirements
- **Python**: 3.11+
- **RAM**: 8GB minimum (16GB recommended for faster processing)
- **Storage**: ~2GB for model files
- **GPU** (Optional): CUDA-capable GPU for faster synthesis (~3x speedup)

### Required System Services
- **eSpeak NG** (Windows only) - Phoneme engine for Kokoro
- **FFmpeg** - Audio format conversion

### API Keys
- **Groq API Key** - Get free at https://console.groq.com/
  - Free tier includes millions of tokens for testing
  - Used for emotional analysis only (brief API calls)

---

## 🔧 Installation

### 1️⃣ Clone Repository
```bash
git clone <repo-url>
cd emotioal-audiobook-agent
```

### 2️⃣ Install Dependencies
```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/Scripts/activate  # Windows
# or
source .venv/bin/activate      # macOS/Linux

# Install Python packages
pip install -r requirements.txt
```

### 3️⃣ Install System Dependencies

**Windows (using WinGet or Chocolatey):**
```bash
# Option 1: WinGet (Windows Package Manager)
winget install eSpeak.eSpeak-NG
winget install ffmpeg

# Option 2: Chocolatey
choco install espeak-ng ffmpeg
```

**macOS:**
```bash
brew install espeak-ng ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install espeak-ng ffmpeg
```

### 4️⃣ Configure Environment
Create `.env` file in project root:
```env
GROQ_API_KEY=your_api_key_here
```

Get your Groq API key: https://console.groq.com/

### 5️⃣ Verify Kokoro Models
Models are pre-downloaded in `model_assets/`:
- `kokoro-v1_0.pth` - Main Kokoro model (82M parameters)
- `voices/` - 40+ pre-trained voice files

If models are missing:
```bash
cd model_assets
python download_models.py
```

---

## 🚀 Quick Start

### Option A: Web Interface (Recommended)
```bash
streamlit run interface.py
```
Then:
1. Upload your PDF
2. Click "Initialize Studio"
3. Select chapters
4. Click "Generate Audio"

### Option B: Command Line
```python
from orchestrator import AudiobookOrchestrator

# Initialize
orchestrator = AudiobookOrchestrator(
    pdf_path="path/to/book.pdf",
    groq_api_key="your_api_key",
    model_dir="model_assets"
)

# Load & analyze
orchestrator.load_book()
orchestrator.analyze_characters()

# Generate audio
orchestrator.generate_chapters([1, 2, 3])  # Chapter numbers
```

---

## 📚 Available Voices

Kokoro provides 40+ diverse voices organized by gender and tone:

### Female Voices
- `af_*` - American Female (alloy, bella, breeze, etc.)
- `bf_*` - British Female (alice, emma, isabella, etc.)
- `ef_*` - European Female
- `hf_*` - High-pitched Female
- `if_*` - International Female
- `jf_*` - Japanese Female
- `pf_*` - Pixie Female
- `zf_*` - Mandarin Chinese Female

### Male Voices
- `am_*` - American Male (adam, daniel, eric, liam, michael, etc.)
- `bm_*` - British Male (daniel, fable, george, lewis)
- `em_*` - European Male
- `hm_*` - High-pitched Male
- `im_*` - International Male
- `jm_*` - Japanese Male
- `pm_*` - Pixie Male
- `zm_*` - Mandarin Chinese Male

List available voices in Python:
```python
from voice_manager import KokoroVoiceManager

manager = KokoroVoiceManager()
print(manager.list_voices())
print(manager.list_voices(filter_gender="female"))
```

---

## ⚙️ Configuration

### Kokoro TTS Parameters
In `voice_manager.py`, adjust synthesis quality:

```python
# Speed modulation (0.5 = slower, 1.0 = normal, 2.0 = faster)
manager.synthesize_text(
    text="Hello world",
    voice="af_bella",
    emotion="happy",
    speed=1.0
)

# Emotion options: neutral, happy, sad, angry, excited, calm
```

### Voice Caching
Synthesized audio is cached in `voice_cache/`:
- Avoids re-synthesis if text hasn't changed
- Each voice gets 1 cache file per unique text

---

## 🎯 Performance Tips

1. **GPU Acceleration** (Optional)
   - Install CUDA-capable PyTorch for ~3x speedup
   - Already configured if NVIDIA GPU available

2. **Batch Processing**
   - Generate multiple chapters in sequence
   - System automatically caches repeated voice synthesis

3. **Text Optimization**
   - Shorter scenes = faster processing
   - System auto-splits long chapters

4. **Memory Management**
   - Typical usage: ~2-3GB RAM for synthesis
   - Voice cache can grow (manageable, delete `voice_cache/` to reset)

---

## 📁 Project Structure

```
emotioal-audiobook-agent/
├── main.py                    # Story Director (LLM analysis)
├── character_analyst.py       # Character voice designer
├── voice_manager.py          # Kokoro TTS wrapper
├── orchestrator.py           # Pipeline coordinator
├── interface.py              # Streamlit web UI
├── requirements.txt          # Python dependencies
│
├── model_assets/
│   ├── kokoro-v1_0.pth      # Main Kokoro model
│   ├── voices/               # 40+ voice embeddings
│   └── voice_map.json        # Voice metadata
│
├── voice_cache/              # Cached audio files
├── audiobook_output/         # Generated MP3s
├── chapters/                 # Extracted chapters
└── README.md                 # This file
```

---

## 🔑 API Usage & Costs

### Groq (Emotional Analysis)
- **Free Tier**: Unlimited access with rate limits
- **Cost**: Free! (as of 2026)
- **Usage**: Only brief LLM calls for analysis
- **Typical**: ~$0 per book

No costs for Kokoro synthesis - it's entirely local!

---

## 🐛 Troubleshooting

### "Kokoro model not found"
```bash
cd model_assets
python download_models.py
```

### "eSpeak-ng not found" (Windows)
```bash
winget install eSpeak.eSpeak-NG
# Restart terminal & Python
```

### "GROQ_API_KEY not set"
```bash
# Add to .env file
echo "GROQ_API_KEY=your_key" > .env
```

### Slow synthesis
- Check GPU availability: `python -c "import torch; print(torch.cuda.is_available())"`
- Reduce chapter size or use faster voices
- Allocate more system memory

### Audio quality issues
- Kokoro works best with clear, well-formatted text
- Ensure PDF extracts cleanly (avoid scanned images)
- Try different voices for character variety

---

## 🚀 Future Enhancements

- [ ] Real-time emotion modulation curves
- [ ] Automatic chapter splitting by emotional arc
- [ ] Voice synthesis fine-tuning
- [ ] Multi-language support
- [ ] Audio post-processing (normalization, effects)
- [ ] Batch PDF processing
- [ ] Advanced voice cloning

---

## 📄 License

This project is open-source. Check LICENSE file for details.

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Better character-voice matching
- Enhanced emotion detection
- Voice quality improvements
- UI/UX enhancements

---

## 📞 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review code comments in each module
3. Check Groq API documentation: https://console.groq.com/docs
4. Kokoro model: https://github.com/kokoro-ai/kokoro

---

**Made with ❤️ for audiobook enthusiasts**

