import os
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import json
import time

class VoiceRepositoryChecker:
    def __init__(self):
        self.base_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/"
        self.api_url = "https://huggingface.co/api/models/hexgrad/Kokoro-82M/tree/main/voices"
        self.voices_folder = "model_assets/voices"
        os.makedirs(self.voices_folder, exist_ok=True)
        
    def fetch_available_voices_via_api(self):
        """Fetch available voices using Hugging Face API"""
        print("🔍 Fetching voice list from Hugging Face API...")
        
        try:
            response = requests.get(self.api_url, timeout=30)
            
            if response.status_code == 200:
                files_data = response.json()
                voice_files = []
                
                for file_info in files_data:
                    if file_info['type'] == 'file' and file_info['path'].endswith('.pt'):
                        filename = os.path.basename(file_info['path'])
                        size = file_info.get('size', 0)
                        voice_files.append({
                            'name': filename,
                            'size_bytes': size,
                            'size_mb': size / (1024 * 1024)
                        })
                
                print(f"✅ Found {len(voice_files)} voice files via API")
                return voice_files
            else:
                print(f"❌ API request failed: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error accessing API: {e}")
            return []
    
    def check_single_voice_exists(self, voice_name):
        """Check if a specific voice file exists in the repository"""
        url = f"{self.base_url}{voice_name}"
        
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                # Try to get file size
                size = response.headers.get('content-length')
                size_mb = int(size) / (1024 * 1024) if size else 0
                return {
                    'name': voice_name,
                    'exists': True,
                    'size_mb': size_mb
                }
        except requests.exceptions.RequestException:
            pass
        
        return {
            'name': voice_name,
            'exists': False,
            'size_mb': 0
        }
    
    def check_common_voices(self):
        """Check a list of commonly expected voice files"""
        print("\n🔍 Checking commonly used voice files...")
        
        common_voices = [
            # Female voices
            'af_bella.pt', 'af_sarah.pt', 'af_grace.pt', 'af_ashley.pt',
            'af_angelica.pt', 'af_jessica.pt', 'af_emma.pt', 'af_lily.pt',
            
            # Male voices
            'bm_daniel.pt', 'bm_john.pt', 'bm_arthur.pt', 'bm_kenny.pt',
            'bm_ryan.pt', 'bm_josh.pt', 'bm_michael.pt', 'bm_david.pt',
            
            # Child voices
            'cm_timmy.pt', 'cm_billy.pt', 'cm_tommy.pt',
            'cf_emily.pt', 'cf_suzie.pt', 'cf_olivia.pt',
            
            # Special voices
            'am_alex.pt',  # Androgynous/mixed
            'af_sophie.pt', 'bm_robert.pt',
            
            # Language-specific (if any)
            'af_es_maria.pt', 'bm_es_carlos.pt',  # Spanish
            'af_fr_sophie.pt', 'bm_fr_pierre.pt', # French
        ]
        
        available_voices = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all checking tasks
            future_to_voice = {
                executor.submit(self.check_single_voice_exists, voice): voice 
                for voice in common_voices
            }
            
            # Process results as they complete
            for future in tqdm(as_completed(future_to_voice), 
                              total=len(common_voices),
                              desc="Checking voices"):
                result = future.result()
                if result['exists']:
                    available_voices.append(result)
        
        return available_voices
    
    def scan_for_all_voices(self):
        """Try to discover all voice files by pattern matching"""
        print("\n🔍 Scanning for all possible voice files...")
        
        # Common patterns for voice file names
        voice_patterns = [
            r'^(af|bm|cm|cf|am)_[a-z]+\.pt$',  # Standard pattern: prefix_name.pt
            r'^[a-z]{2}_[a-z]+_[a-z]{2}\.pt$',  # Language codes: xx_name_xx.pt
            r'^[a-z]+_[a-z]+\.pt$',  # Simple pattern: type_name.pt
        ]
        
        # Try to fetch directory listing (if accessible)
        try:
            response = requests.get(self.base_url.replace('/resolve/', '/tree/'), timeout=10)
            if response.status_code == 200:
                # Try to parse HTML for links
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                voice_files = []
                for link in links:
                    href = link['href']
                    if href.endswith('.pt'):
                        filename = os.path.basename(href)
                        voice_files.append(filename)
                
                if voice_files:
                    print(f"✅ Found {len(voice_files)} voice files via directory listing")
                    return self.verify_voice_files(voice_files)
        except Exception as e:
            print(f"⚠️ Could not scan directory: {e}")
        
        # Fallback: try common naming patterns
        return self.discover_by_patterns()
    
    def discover_by_patterns(self):
        """Try to discover voices by common naming patterns"""
        print("🔍 Trying pattern-based discovery...")
        
        # Common prefixes and names
        prefixes = ['af', 'bm', 'cm', 'cf', 'am', 'bf', 'gm', 'gf']
        names = [
            'bella', 'sarah', 'grace', 'ashley', 'angelica', 'jessica', 'emma', 'lily',
            'daniel', 'john', 'arthur', 'kenny', 'ryan', 'josh', 'michael', 'david',
            'timmy', 'billy', 'tommy', 'emily', 'suzie', 'olivia', 'sophie', 'robert',
            'alex', 'maria', 'carlos', 'pierre', 'anna', 'william', 'henry', 'victor'
        ]
        
        possible_voices = []
        for prefix in prefixes:
            for name in names:
                possible_voices.append(f"{prefix}_{name}.pt")
        
        # Add some variations
        for name in names:
            possible_voices.append(f"voice_{name}.pt")
            possible_voices.append(f"{name}_voice.pt")
        
        print(f"Testing {len(possible_voices)} possible voice names...")
        
        available = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_voice = {
                executor.submit(self.check_single_voice_exists, voice): voice 
                for voice in possible_voices
            }
            
            for future in tqdm(as_completed(future_to_voice), 
                              total=len(possible_voices),
                              desc="Pattern discovery"):
                result = future.result()
                if result['exists']:
                    available.append(result)
        
        return available
    
    def verify_voice_files(self, voice_list):
        """Verify which voice files actually exist"""
        print(f"🔍 Verifying {len(voice_list)} potential voice files...")
        
        available = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_voice = {
                executor.submit(self.check_single_voice_exists, voice): voice 
                for voice in voice_list
            }
            
            for future in tqdm(as_completed(future_to_voice), 
                              total=len(voice_list),
                              desc="Verifying voices"):
                result = future.result()
                if result['exists']:
                    available.append(result)
        
        return available
    
    def categorize_voices(self, voices):
        """Categorize voices by type"""
        categories = {
            'female': [],
            'male': [],
            'child_male': [],
            'child_female': [],
            'androgynous': [],
            'other': []
        }
        
        for voice in voices:
            name = voice['name']
            
            if name.startswith('af_'):
                categories['female'].append(voice)
            elif name.startswith('bm_'):
                categories['male'].append(voice)
            elif name.startswith('cm_'):
                categories['child_male'].append(voice)
            elif name.startswith('cf_'):
                categories['child_female'].append(voice)
            elif name.startswith('am_'):
                categories['androgynous'].append(voice)
            else:
                categories['other'].append(voice)
        
        return categories
    
    def save_voice_list(self, voices, filename="available_voices.json"):
        """Save list of available voices to JSON file"""
        output_path = os.path.join(self.voices_folder, filename)
        
        # Add timestamp
        data = {
            'last_updated': time.strftime("%Y-%m-%d %H:%M:%S"),
            'total_voices': len(voices),
            'voices': voices
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved voice list to {output_path}")
        return output_path
    
    def generate_download_script(self, voices, output_file="download_all_voices.py"):
        """Generate a Python script to download all available voices"""
        script_content = '''import os
import requests
from tqdm import tqdm
import json

# Configuration
BASE_URL = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/"
VOICES_FOLDER = "model_assets/voices"
os.makedirs(VOICES_FOLDER, exist_ok=True)

# Voice list to download
VOICES_TO_DOWNLOAD = [
'''

        # Add all voices to the list
        for voice in voices:
            name = voice['name']
            script_content += f"    '{name}',  # {voice.get('size_mb', 0):.1f} MB\n"
        
        script_content += ''']

def download_voice(voice_name):
    """Download a single voice file"""
    url = BASE_URL + voice_name
    dest = os.path.join(VOICES_FOLDER, voice_name)
    
    # Skip if already exists and is valid
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return True, f"Skipped (already exists)"
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            
            with open(dest, 'wb') as f, tqdm(
                desc=voice_name,
                total=total_size,
                unit='B',
                unit_scale=True,
                leave=False
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            
            return True, f"Downloaded ({os.path.getsize(dest)/1024/1024:.1f} MB)"
        else:
            return False, f"HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print("🚀 Starting download of all available voices...")
    print("=" * 60)
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, voice in enumerate(VOICES_TO_DOWNLOAD, 1):
        print(f"{i}/{len(VOICES_TO_DOWNLOAD)}: {voice}")
        
        success, message = download_voice(voice)
        
        if success:
            if "Skipped" in message:
                skipped += 1
                print(f"   ⏭️  {message}")
            else:
                successful += 1
                print(f"   ✅ {message}")
        else:
            failed += 1
            print(f"   ❌ {message}")
    
    print("=" * 60)
    print(f"📊 Summary: {successful} downloaded, {skipped} skipped, {failed} failed")
    
    # Save a simple mapping file
    voice_map = {
        'female_default': 'af_bella.pt',
        'male_default': 'bm_daniel.pt',
        'child_male': 'cm_timmy.pt',
        'child_female': 'cf_emily.pt',
    }
    
    # Add all downloaded voices to mapping
    for voice in VOICES_TO_DOWNLOAD:
        key = voice.replace('.pt', '').replace('_', ' ')
        voice_map[key] = voice
    
    with open(os.path.join(VOICES_FOLDER, 'voice_mapping.json'), 'w') as f:
        json.dump(voice_map, f, indent=2)
    
    print(f"🗺️ Voice mapping saved to {os.path.join(VOICES_FOLDER, 'voice_mapping.json')}")

if __name__ == "__main__":
    main()
'''
        
        script_path = os.path.join(self.voices_folder, output_file)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"📝 Generated download script: {script_path}")
        return script_path
    
    def display_results(self, voices, categories=None):
        """Display available voices in a nice format"""
        print("\n" + "=" * 70)
        print("🎧 AVAILABLE VOICES IN KOKORO REPOSITORY")
        print("=" * 70)
        
        if not voices:
            print("❌ No voices found in the repository.")
            return
        
        print(f"\n📊 Total available voices: {len(voices)}")
        
        if categories:
            for category, items in categories.items():
                if items:
                    print(f"\n{'─' * 40}")
                    print(f"{category.upper()} VOICES ({len(items)})")
                    print(f"{'─' * 40}")
                    for voice in sorted(items, key=lambda x: x['name']):
                        size_str = f"{voice.get('size_mb', 0):.1f} MB" if voice.get('size_mb') else "size unknown"
                        print(f"  • {voice['name']:25} ({size_str})")
        else:
            # Simple list
            print("\n" + "─" * 60)
            for i, voice in enumerate(sorted(voices, key=lambda x: x['name']), 1):
                size_str = f"{voice.get('size_mb', 0):.1f} MB" if voice.get('size_mb') else "size unknown"
                print(f"{i:3d}. {voice['name']:25} ({size_str})")
        
        print("\n" + "=" * 70)
        
        # Show statistics
        total_size = sum(v.get('size_mb', 0) for v in voices)
        print(f"📦 Total size if downloaded: {total_size:.1f} MB")
        print(f"💾 Local storage required: ~{total_size:.1f} MB")
        
        # Essential voices check
        essential = ['af_bella.pt', 'bm_daniel.pt']
        missing_essential = [v for v in essential if v not in [voice['name'] for voice in voices]]
        
        if missing_essential:
            print(f"\n⚠️  Missing essential voices: {missing_essential}")
        else:
            print(f"\n✅ All essential voices are available!")

def main():
    print("🎧 Voice Repository Scanner for Kokoro-82M")
    print("=" * 60)
    
    checker = VoiceRepositoryChecker()
    
    # Try API method first
    api_voices = checker.fetch_available_voices_via_api()
    
    if api_voices:
        # Use API results
        voices = [{'name': v['name'], 'size_mb': v['size_mb']} for v in api_voices]
        print(f"\n✅ Successfully retrieved {len(voices)} voices from API")
    else:
        # Fallback to scanning methods
        print("\n⚠️ API method failed, trying discovery methods...")
        
        # Method 1: Check common voices
        common_voices = checker.check_common_voices()
        
        # Method 2: Try to discover more
        discovered_voices = checker.scan_for_all_voices()
        
        # Combine results, removing duplicates
        all_voices_dict = {}
        for voice in common_voices + discovered_voices:
            if voice['exists']:
                all_voices_dict[voice['name']] = voice
        
        voices = list(all_voices_dict.values())
        
        if not voices:
            print("❌ No voices found using any method.")
            print("The repository structure may have changed or is not accessible.")
            return
    
    # Categorize voices
    categories = checker.categorize_voices(voices)
    
    # Display results
    checker.display_results(voices, categories)
    
    # Save results
    json_file = checker.save_voice_list(voices)
    
    # Generate download script
    script_file = checker.generate_download_script(voices)
    
    # Local check
    print("\n🔍 Checking locally downloaded voices...")
    local_voices = []
    if os.path.exists(checker.voices_folder):
        for file in os.listdir(checker.voices_folder):
            if file.endswith('.pt'):
                filepath = os.path.join(checker.voices_folder, file)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                local_voices.append({
                    'name': file,
                    'size_mb': size_mb,
                    'local': True
                })
    
    if local_voices:
        print(f"📁 Found {len(local_voices)} voice files locally:")
        for voice in sorted(local_voices, key=lambda x: x['name']):
            print(f"  • {voice['name']:25} ({voice['size_mb']:.1f} MB)")
    else:
        print("📁 No voice files found locally.")
    
    # Next steps
    print("\n" + "=" * 60)
    print("🚀 NEXT STEPS:")
    print(f"1. View complete list: {json_file}")
    print(f"2. Download all voices: python {script_file}")
    print(f"3. Required packages: pip install requests tqdm beautifulsoup4")
    print("=" * 60)

if __name__ == "__main__":
    # Install required packages if missing
    try:
        import requests
        from tqdm import tqdm
    except ImportError:
        print("Installing required packages...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "tqdm"])
    
    # Optional: BeautifulSoup for HTML parsing
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Note: For advanced scanning, install: pip install beautifulsoup4")
    
    main()