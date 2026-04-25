"""
Analysis Cache Manager - Persists book analysis results to avoid re-analysis
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple


class AnalysisCache:
    """
    Manages persistent storage of book analysis results
    """
    
    def __init__(self, cache_dir: str = "analysis_cache"):
        """
        Initialize cache manager
        
        Args:
            cache_dir: Directory to store analysis caches
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _compute_file_hash(self, pdf_path: str) -> str:
        """
        Compute hash of PDF file to identify it uniquely
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            SHA256 hash of file
        """
        sha256_hash = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # Use first 16 chars
    
    def get_cache_key(self, pdf_path: str) -> str:
        """
        Get unique cache key for a PDF
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Cache key (filename without extension + hash)
        """
        file_hash = self._compute_file_hash(pdf_path)
        file_name = Path(pdf_path).stem
        return f"{file_name}_{file_hash}"
    
    def _get_manifest_path(self, cache_key: str) -> Path:
        """Get path to manifest file for a cached book"""
        return self.cache_dir / f"{cache_key}_manifest.json"
    
    def has_analysis(self, pdf_path: str) -> bool:
        """
        Check if a book has been analyzed before
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if analysis exists in cache
        """
        cache_key = self.get_cache_key(pdf_path)
        manifest_path = self._get_manifest_path(cache_key)
        return manifest_path.exists()
    
    def save_analysis(self, 
                     pdf_path: str,
                     metadata: Dict,
                     chapters: list,
                     character_registry: Dict,
                     voice_map: Dict) -> bool:
        """
        Save analysis results to cache
        
        Args:
            pdf_path: Path to PDF file
            metadata: Book metadata
            chapters: List of chapters
            character_registry: Character analysis results
            voice_map: Character to voice mapping
            
        Returns:
            True if successful
        """
        try:
            cache_key = self.get_cache_key(pdf_path)
            manifest_path = self._get_manifest_path(cache_key)
            
            analysis_data = {
                "pdf_path": str(pdf_path),
                "cache_key": cache_key,
                "metadata": metadata,
                "chapters": chapters,
                "character_registry": character_registry,
                "voice_map": voice_map,
                "num_chapters": len(chapters),
                "num_characters": len(character_registry)
            }
            
            with open(manifest_path, 'w') as f:
                json.dump(analysis_data, f, indent=2)
            
            print(f"✅ Analysis cached for: {Path(pdf_path).name}")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to cache analysis: {e}")
            return False
    
    def load_analysis(self, pdf_path: str) -> Optional[Dict]:
        """
        Load analysis results from cache
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Analysis data dict or None if not found
        """
        try:
            if not self.has_analysis(pdf_path):
                return None
            
            cache_key = self.get_cache_key(pdf_path)
            manifest_path = self._get_manifest_path(cache_key)
            
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            
            print(f"📖 Loaded cached analysis for: {Path(pdf_path).name}")
            print(f"   - {data['num_chapters']} chapters")
            print(f"   - {data['num_characters']} characters")
            
            return data
            
        except Exception as e:
            print(f"⚠️ Failed to load cached analysis: {e}")
            return None
    
    def clear_cache(self, pdf_path: str = None) -> bool:
        """
        Clear cache for a specific book or entire cache
        
        Args:
            pdf_path: Optional path to specific PDF
            
        Returns:
            True if successful
        """
        try:
            if pdf_path:
                # Clear specific book cache
                cache_key = self.get_cache_key(pdf_path)
                manifest_path = self._get_manifest_path(cache_key)
                if manifest_path.exists():
                    manifest_path.unlink()
                    print(f"🗑️ Cleared cache for: {Path(pdf_path).name}")
            else:
                # Clear entire cache
                import shutil
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
                print(f"🗑️ Cleared entire analysis cache")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to clear cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict:
        """
        Get statistics about cached analyses
        
        Returns:
            Dict with cache statistics
        """
        cache_files = list(self.cache_dir.glob("*_manifest.json"))
        
        stats = {
            "total_cached_books": len(cache_files),
            "cache_dir": str(self.cache_dir),
            "cached_books": []
        }
        
        for manifest_path in cache_files:
            try:
                with open(manifest_path, 'r') as f:
                    data = json.load(f)
                stats["cached_books"].append({
                    "name": Path(data['pdf_path']).name,
                    "chapters": data['num_chapters'],
                    "characters": data['num_characters']
                })
            except:
                pass
        
        return stats
