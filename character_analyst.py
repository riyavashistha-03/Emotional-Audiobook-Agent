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
        
    def analyze_full_book_characters(self, full_text: str, max_chunks: int = 10) -> Dict:
        """
        Extract ALL characters from the entire book
        Processes book in chunks to handle long texts
        """
        print("📚 Analyzing book for character extraction...")
        
        # Split book into manageable chunks
        chunk_size = 10000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        chunks = chunks[:max_chunks]  # Limit chunks for API efficiency
        
        all_characters = {}
        
        for i, chunk in enumerate(chunks):
            print(f"  Processing chunk {i+1}/{len(chunks)}")
            
            prompt = f"""
            You are an expert literary analyst and audiobook casting director.
            
            Analyze this section of a book and extract ALL characters who speak or are major presences.
            
            BOOK TEXT (chunk {i+1}):
            {chunk[:8000]}...
            
            Return a JSON object with characters as keys. For EACH character, provide:
            {{
                "character_name": {{
                    "gender": "male/female/unknown",
                    "age_category": "child/teen/young_adult/middle_aged/elderly",
                    "personality_traits": ["trait1", "trait2", "trait3"],
                    "voice_qualities": ["deep", "high", "raspy", "smooth", "breathy", "authoritative"],
                    "speaking_pace": "fast/moderate/slow/varies",
                    "typical_emotions": ["happy", "sad", "angry", "scared", "neutral"],
                    "social_class": "upper/middle/lower/unknown",
                    "dialogue_samples": ["sample line 1", "sample line 2"],
                    "first_appearance": "description of where they appear",
                    "is_narrator": true/false
                }}
            }}
            
            Include ALL characters, even minor ones. Be comprehensive.
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                
                chunk_characters = json.loads(response.choices[0].message.content)
                
                # Merge with existing characters
                for char_name, char_data in chunk_characters.items():
                    if char_name in all_characters:
                        # Merge dialogue samples
                        if "dialogue_samples" in char_data:
                            existing = all_characters[char_name].get("dialogue_samples", [])
                            all_characters[char_name]["dialogue_samples"] = list(set(existing + char_data["dialogue_samples"]))
                    else:
                        all_characters[char_name] = char_data
                        
            except Exception as e:
                print(f"⚠️ Error processing chunk {i}: {e}")
                continue
        
        # Final cleanup and validation
        self.character_registry = self._validate_and_clean_registry(all_characters)
        print(f"✅ Found {len(self.character_registry)} unique characters")
        return self.character_registry
    
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
        Convert character analysis into detailed voice descriptions for MOSS
        """
        print("🎭 Generating voice design briefs...")
        
        voice_briefs = {}
        
        for char_name, char_data in self.character_registry.items():
            # Create rich voice description
            prompt = f"""
            Based on this character profile, write a SINGLE PARAGRAPH voice description for MOSS-VoiceGenerator.
            
            Character: {char_name}
            Gender: {char_data['gender']}
            Age: {char_data['age_category']}
            Personality: {', '.join(char_data['personality_traits'])}
            Voice qualities: {', '.join(char_data['voice_qualities'])}
            Speaking pace: {char_data['speaking_pace']}
            Social class: {char_data['social_class']}
            Sample dialogue: {char_data['dialogue_samples'][0] if char_data['dialogue_samples'] else 'Hello'}
            
            Write a COMPLETE voice description that includes:
            - Overall voice character (warm, cold, authoritative, etc.)
            - Pitch (low/medium/high and variations)
            - Resonance and texture
            - Speech patterns (articulation, rhythm)
            - Emotional range capabilities
            - Any accent or dialect
            - Age-appropriate qualities
            
            Format as a single, flowing paragraph. Be specific and vivid.
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                
                voice_briefs[char_name] = response.choices[0].message.content.strip()
                print(f"  ✓ Generated voice for: {char_name}")
                
            except Exception as e:
                print(f"⚠️ Error generating voice for {char_name}: {e}")
                voice_briefs[char_name] = f"A {char_data['gender']} voice, {char_data['age_category']}, with {', '.join(char_data['voice_qualities'])} qualities."
        
        self.voice_briefs = voice_briefs
        return voice_briefs
    
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
                model="llama-3.3-70b-versatile",
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
    
    def parse_dialogue_scene(self, chapter_text: str) -> Dict:
        """
        Parse chapter into scenes with dialogue turns
        """
        prompt = f"""
        Parse this chapter text into SCENES and DIALOGUE TURNS:
        
        {chapter_text[:8000]}...
        
        Return a JSON with:
        {{
            "scenes": [
                {{
                    "location": "description or unknown",
                    "characters_present": ["character1", "character2"],
                    "dialogue_turns": [
                        {{
                            "speaker": "character_name",
                            "text": "exact dialogue text",
                            "emotion": "emotion for this line",
                            "context_before": "brief context",
                            "context_after": "brief context"
                        }}
                    ],
                    "narration": "narration text for this scene"
                }}
            ]
        }}
        
        Be precise about speaker attribution. Use exact character names.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"⚠️ Error parsing scene: {e}")
            return {"scenes": []}
