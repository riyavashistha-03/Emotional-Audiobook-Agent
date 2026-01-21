import os
import soundfile as sf
from kokoro import KPipeline
import numpy as np
import re

class AudiobookSpeaker:
    def __init__(self, lang_code='a'):
        self.pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
        self.voice_dir = os.path.join("model_assets", "voices")
        
        self.voice_library = {
            # Narrator voices
            "neutral_narrator": "af_bella.pt",
            "authoritative_narrator": "bm_daniel.pt",
            "storyteller": "af_sarah.pt",
            
            # Female voices with emotional variations
            "young_woman_neutral": "af_bella.pt",
            "young_woman_excited": "af_sarah.pt",  # Higher pitch, faster
            "young_woman_scared": "af_bella.pt",   # Trembling, higher pitch
            "young_woman_angry": "af_sarah.pt",    # Lower, sharper
            
            # Male voices with emotional variations
            "man_neutral": "bm_daniel.pt",
            "man_excited": "bm_john.pt",          # Brighter, faster
            "man_scared": "bm_daniel.pt",         # Quivering, breathy
            "man_angry": "bm_john.pt",            # Deeper, louder
            
            # Child voices
            "child_boy": "cm_timmy.pt",
            "child_girl": "cf_emily.pt",
            
            # Elderly voices
            "old_man": "bm_arthur.pt",
            "old_woman": "af_grace.pt",
        }

        self.emotion_modulation = {
            "excited": {"speed": 1.2, "pitch_shift": 1.1, "volume": 1.1},
            "scared": {"speed": 1.3, "pitch_shift": 1.15, "volume": 0.9, "tremble": 0.1},
            "angry": {"speed": 1.1, "pitch_shift": 0.9, "volume": 1.2},
            "sad": {"speed": 0.8, "pitch_shift": 0.95, "volume": 0.9},
            "happy": {"speed": 1.15, "pitch_shift": 1.05, "volume": 1.05},
            "neutral": {"speed": 1.0, "pitch_shift": 1.0, "volume": 1.0},
            "mysterious": {"speed": 0.9, "pitch_shift": 0.95, "volume": 0.95},
        }
        
        
    def detect_character_and_emotion(self, text_segment, context=""):
        """
        Analyze text to determine who's speaking and their emotional state
        This should work with the StoryDirector's analysis
        """
        # Patterns to detect dialogue
        dialogue_patterns = [
            r'^\"(.*?)\"',  # Quoted dialogue
            r'said (\w+)',  # "said John"
            r'asked (\w+)', # "asked Mary"
            r'(\w+) whispered',  # "John whispered"
            r'(\w+) shouted',   # "Mary shouted"
            r'(\w+) cried',     # "she cried"
        ]
        
        # Default to narrator
        character = "narrator"
        base_emotion = "neutral"
        
        # Check for dialogue indicators
        for pattern in dialogue_patterns:
            match = re.search(pattern, text_segment, re.IGNORECASE)
            if match:
                # Extract character name from dialogue tags
                if match.groups():
                    char_name = match.group(1).lower()
                    # Map common names to character types
                    if char_name in ['she', 'her', 'mary', 'sarah', 'emily', 'anna']:
                        character = "young_woman"
                    elif char_name in ['he', 'him', 'john', 'david', 'michael', 'jack']:
                        character = "man"
                    elif char_name in ['boy', 'child', 'timmy', 'billy']:
                        character = "child_boy"
                    elif char_name in ['girl', 'child', 'emily', 'suzie']:
                        character = "child_girl"
                    elif char_name in ['old', 'elder', 'grandpa', 'grandfather']:
                        character = "old_man"
                    elif char_name in ['grandma', 'grandmother', 'old woman']:
                        character = "old_woman"
        
        # Detect emotional keywords
        emotion_keywords = {
            'excited': ['excited', 'thrilled', 'eager', 'enthusiastic'],
            'scared': ['scared', 'afraid', 'terrified', 'frightened'],
            'angry': ['angry', 'furious', 'enraged', 'mad'],
            'sad': ['sad', 'upset', 'depressed', 'unhappy'],
            'happy': ['happy', 'joyful', 'delighted', 'cheerful'],
            'mysterious': ['mysterious', 'secret', 'whispered', 'hidden'],
        }
        
        text_lower = text_segment.lower()
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                base_emotion = emotion
                break
        
        return character, base_emotion

    def get_voice_for_character(self, character, emotion):
        """
        Select appropriate voice file based on character and emotion
        """
        voice_key = f"{character}_{emotion}"
        
        # Try exact match first
        if voice_key in self.voice_library:
            return self.voice_library[voice_key]
        
        # Fallback to character with neutral emotion
        neutral_key = f"{character}_neutral"
        if neutral_key in self.voice_library:
            return self.voice_library[neutral_key]
        
        # Ultimate fallback to neutral narrator
        return self.voice_library["neutral_narrator"]

    def apply_emotion_modulation(self, audio_data, emotion):
        """Apply basic audio modulation based on emotion"""
        if emotion not in self.emotion_modulation:
            return audio_data
        
        modulation = self.emotion_modulation[emotion]  
    
    def generate_audio(self, text, character_info, output_filename):
        """
        Generate audio with character-specific voices
        character_info should contain: {"character": "...", "emotion": "...", "gender": "...", "age": "..."}
        """
        # Extract character and emotion info
        character = character_info.get("character", "narrator")
        emotion = character_info.get("emotion", "neutral")
        
        # Get appropriate voice file
        voice_file = self.get_voice_for_character(character, emotion)
        voice_path = os.path.join(self.voice_dir, voice_file)
        
        # Get speed modulation
        modulation = self.emotion_modulation.get(emotion, self.emotion_modulation["neutral"])
        speed = modulation["speed"]
        
        print(f"🎙️ Character: {character} | Emotion: {emotion} | Voice: {voice_file}")
        
        if not os.path.exists(voice_path):
            print(f"⚠️ Voice file {voice_file} not found. Using default.")
            voice_path = os.path.join(self.voice_dir, "af_bella.pt")
            
        # Generate audio
        generator = self.pipeline(
            text, 
            voice=voice_path, 
            speed=speed, 
            split_pattern=r'\n+'
        )
        
        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_chunks.append(audio)
        
        if audio_chunks:
            combined_audio = np.concatenate(audio_chunks)
            
            # Apply emotion-based audio modulation
            modulated_audio = self.apply_emotion_modulation(combined_audio, emotion)  # FIXED: Changed emotion_modulation to apply_emotion_modulation
            
            # Save audio
            sf.write(output_filename, modulated_audio, 24000)
            print(f"✅ Audio saved: {output_filename}")
            return True
        else:
            print("❌ Error: No audio was generated.")
            return False


# Add this simple version for testing
if __name__ == "__main__":
    # 1. Initialize our production speaker
    my_speaker = AudiobookSpeaker()

    # 2. Test character detection
    test_text = "John said, 'I'm excited to see you!' Mary whispered, 'I'm scared.'"
    print("Testing character detection...")
    character, emotion = my_speaker.detect_character_and_emotion(test_text)
    print(f"Detected: Character={character}, Emotion={emotion}")
    
    # 3. Test audio generation with simple notes
    test_notes = {
        "character": "narrator",
        "emotion": "tense"
    }

    test_text = "This is a test of the enhanced audiobook speaker."
    
    print("\n🚀 Testing audio generation...")
    success = my_speaker.generate_audio(test_text, test_notes, "test_output.wav")
    
    if success:
        print("✅ Test successful! Check test_output.wav")
    else:
        print("❌ Test failed.")