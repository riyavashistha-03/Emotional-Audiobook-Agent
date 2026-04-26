"""
Enhanced Character Analyst - Extracts characters and generates voice descriptions
"""
import json
import re
from groq import Groq
from typing import Dict, List, Any
import hashlib
from datetime import datetime

class CharacterVoiceDesigner:
    """AI Agent that analyzes full book and designs character voices"""
    
    def __init__(self, groq_api_key: str):
        self.client = Groq(api_key=groq_api_key)
        self.character_registry = {}
        self.voice_briefs = {}
        
    def analyze_characters_in_text(self, text: str) -> Dict:
        """
        Extract and resolve characters from a specific text (e.g., selected chapters).
        Includes alias resolution (Phineas/Finn).
        """
        print(f"🎭 Analyzing text for character extraction and alias resolution...")
        
        prompt = f"""
        You are a literary analyst. Extract the ACTUAL characters from the text provided below.
        
        CRITICAL INSTRUCTIONS:
        1. DO NOT use examples or placeholders (like Sherlock Holmes, Watson, etc.) unless they are actually in the text.
        2. If the text is empty or you cannot find characters, return an empty JSON object: {{}}
        3. Identify characters referred to by different names (aliases, nicknames, e.g., Phineas and Finn) and group them under their Official Name.
        4. Focus on characters that actually speak or have significant presence in this specific snippet.
        
        TEXT CONTENT:
        ---
        {text[:15000]}
        ---
        
        Return a JSON object where each key is the 'Official Name' of a character.
        Value is their profile:
        {{
            "Official Name": {{
                "aliases": ["nickname1", "title"],
                "gender": "male/female/unknown",
                "age_category": "child/teen/adult/elderly",
                "personality": "brief description",
                "voice_profile": "deep/high/raspy/etc",
                "is_narrator": false
            }}
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            data = json.loads(response.choices[0].message.content)
            self.character_registry = data
            return data
        except Exception as e:
            print(f"⚠️ Error analyzing characters: {e}")
            return {}

    def analyze_full_book_characters(self, full_text: str, max_chunks: int = 10) -> Dict:
        # Keeping for compatibility but favoring analyze_characters_in_text for selected chapters
        return self.analyze_characters_in_text(full_text[:50000])
    
    def _validate_and_clean_registry(self, registry: Dict) -> Dict:
        """Clean and validate character data"""
        cleaned = {}
        
        for name, data in registry.items():
            # Skip entries that aren't real characters
            if len(name) < 2 or name.lower() in ["unknown", "narrator", "character"]:
                continue
                
            # Ensure required fields
            cleaned[name] = {
                "gender": data.get("gender", "unknown"),
                "age_category": data.get("age_category", "adult"),
                "personality_traits": data.get("personality_traits", ["neutral"]),
                "voice_qualities": data.get("voice_qualities", ["neutral"]),
                "speaking_pace": data.get("speaking_pace", "moderate"),
                "typical_emotions": data.get("typical_emotions", ["neutral"]),
                "social_class": data.get("social_class", "middle"),
                "dialogue_samples": data.get("dialogue_samples", [])[:3],  # Keep top 3
                "first_appearance": data.get("first_appearance", "unknown"),
                "is_narrator": data.get("is_narrator", False)
            }
            
        return cleaned
    
    def generate_voice_design_briefs(self) -> Dict[str, str]:
        """
        Convert character analysis into detailed voice descriptions.
        Batched to save time.
        """
        if not self.character_registry:
            return {}
            
        print(f"🎭 Batch generating voice briefs for {len(self.character_registry)} characters...")
        
        prompt = f"""
        Create a detailed one-paragraph voice description for each character below.
        Describe pitch, texture, resonance, and speech patterns suitable for TTS selection.
        
        CHARACTERS:
        {json.dumps(self.character_registry, indent=2)}
        
        Return a JSON object where each key is the EXACT 'Official Name' and each value is a SINGLE STRING containing the voice description. 
        DO NOT use placeholders. 
        Example format (DO NOT USE THESE NAMES): {{"CharacterName": "A deep, resonant voice..."}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            raw_briefs = json.loads(response.choices[0].message.content)
            
            # Ensure all values are strings
            final_briefs = {}
            for name, brief in raw_briefs.items():
                if isinstance(brief, dict):
                    # Extract string from common nested keys if LLM makes a mistake
                    brief = brief.get("description") or brief.get("voice_description") or str(brief)
                final_briefs[name] = str(brief)
                
            self.voice_briefs = final_briefs
            return self.voice_briefs
        except Exception as e:
            print(f"⚠️ Error batch generating briefs: {e}")
            # Fallback to simple descriptions
            return {name: "A standard neutral voice." for name in self.character_registry}
    
    def get_emotion_modulation(self, character: str, emotion: str, context: str) -> Dict:
        """
        Generate emotion-specific modulation parameters
        """
        char_data = self.character_registry.get(character, {})
        
        prompt = f"""
        Character: {character}
        Baseline voice: {self.voice_briefs.get(character, 'Neutral voice')}
        
        Current scene context: {context}
        Emotion needed: {emotion}
        
        How should this character's voice MODULATE for this specific emotion?
        
        Return a JSON with:
        {{
            "pitch_shift": (number from -3 to +3 semitones),
            "speed_multiplier": (number from 0.7 to 1.5),
            "volume_multiplier": (number from 0.7 to 1.5),
            "breathiness": (number from 0 to 10),
            "tension": (number from 0 to 10),
            "effects": ["tremble", "whisper", "shout", "cry", "laugh", "none"]
        }}
        
        Only include effects that make sense for {emotion}.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
        except:
            # Default modulation
            return {
                "pitch_shift": 0,
                "speed_multiplier": 1.0,
                "volume_multiplier": 1.0,
                "breathiness": 5,
                "tension": 5,
                "effects": ["none"]
            }
    
    def parse_dialogue_scene(self, text: str) -> Dict:
        """
        Parse text into scenes with per-line emotion tagging and alias resolution.
        """
        char_list = list(self.character_registry.keys())
        
        prompt = f"""
        Break this text into sequential scenes. 
        For each scene, extract 'dialogue_turns' (speaker, text, emotion) and 'narration'.
        
        IMPORTANT: 
        1. 'speaker' MUST be one of: {char_list} or 'narrator'.
        2. Resolve nicknames to official names.
        3. 'emotion' should be specific (whispering, screaming, crying, happy, angry, neutral).
        
        TEXT:
        {text[:10000]}
        
        Return JSON format.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"⚠️ Scene parsing error: {e}")
            return {"scenes": [{"narration": text, "dialogue_turns": []}]}
