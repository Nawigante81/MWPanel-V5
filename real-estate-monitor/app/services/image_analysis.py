"""
Image analysis service for property photos.
Uses computer vision to extract information from images.
"""
import hashlib
from typing import List, Optional, Tuple
from io import BytesIO
import asyncio

import httpx
from PIL import Image, ImageStat

from app.logging_config import get_logger

logger = get_logger("image_analysis")


class ImageAnalyzer:
    """
    Analyzes property images using computer vision.
    
    Features:
    - Perceptual hash for duplicate detection
    - Brightness/contrast analysis
    - Room count estimation
    - Furniture detection
    """
    
    def __init__(self):
        self.min_image_size = (100, 100)
    
    async def analyze_image(self, image_url: str) -> dict:
        """
        Analyze a single image.
        
        Returns:
            dict with analysis results
        """
        try:
            # Download image
            image_data = await self._download_image(image_url)
            if not image_data:
                return {"error": "Failed to download image"}
            
            img = Image.open(BytesIO(image_data))
            
            # Run analysis
            results = {
                "perceptual_hash": self._calculate_phash(img),
                "brightness": self._analyze_brightness(img),
                "contrast": self._analyze_contrast(img),
                "dimensions": img.size,
                "format": img.format,
            }
            
            # Estimate room type from image content
            results["estimated_room"] = self._estimate_room_type(img)
            
            return results
            
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"error": str(e)}
    
    async def analyze_images(self, image_urls: List[str]) -> List[dict]:
        """Analyze multiple images concurrently."""
        tasks = [self.analyze_image(url) for url in image_urls]
        return await asyncio.gather(*tasks)
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            return None
    
    def _calculate_phash(self, img: Image.Image, hash_size: int = 8) -> str:
        """
        Calculate perceptual hash (pHash) for image.
        Used for duplicate detection across sources.
        """
        # Resize and convert to grayscale
        img = img.convert('L').resize(
            (hash_size + 1, hash_size),
            Image.Resampling.LANCZOS
        )
        
        pixels = list(img.getdata())
        
        # Calculate difference hash
        diff = []
        for row in range(hash_size):
            for col in range(hash_size):
                left_pixel = pixels[row * (hash_size + 1) + col]
                right_pixel = pixels[row * (hash_size + 1) + col + 1]
                diff.append(left_pixel > right_pixel)
        
        # Convert to hex
        decimal_value = sum(bit << i for i, bit in enumerate(diff))
        return format(decimal_value, f'0{hash_size * hash_size // 4}x')
    
    def _analyze_brightness(self, img: Image.Image) -> float:
        """Analyze image brightness (0-100)."""
        stat = ImageStat.Stat(img.convert('L'))
        brightness = stat.mean[0]
        return round((brightness / 255) * 100, 2)
    
    def _analyze_contrast(self, img: Image.Image) -> float:
        """Analyze image contrast (0-100)."""
        stat = ImageStat.Stat(img.convert('L'))
        contrast = stat.stddev[0]
        return round((contrast / 128) * 100, 2)
    
    def _estimate_room_type(self, img: Image.Image) -> Optional[str]:
        """
        Estimate room type from image.
        Simple heuristic based on image characteristics.
        """
        # This is a simplified version
        # In production, you'd use a trained ML model
        
        stat = ImageStat.Stat(img)
        
        # Calculate color distribution
        if img.mode == 'RGB':
            r, g, b = stat.mean[:3]
            
            # Kitchens tend to have more white/light colors
            if r > 200 and g > 200 and b > 200:
                return "kitchen"
            
            # Living rooms tend to be warmer
            if r > g and r > b:
                return "living_room"
            
            # Bedrooms tend to be darker
            if stat.mean[0] < 150:
                return "bedroom"
        
        return "unknown"
    
    def find_similar_images(
        self,
        phash1: str,
        phashes: List[str],
        threshold: int = 5
    ) -> List[str]:
        """
        Find similar images based on perceptual hash.
        
        Args:
            phash1: Reference hash
            phashes: List of hashes to compare
            threshold: Maximum hamming distance for similarity
        
        Returns:
            List of similar hashes
        """
        similar = []
        
        for phash2 in phashes:
            distance = self._hamming_distance(phash1, phash2)
            if distance <= threshold:
                similar.append(phash2)
        
        return similar
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """Calculate hamming distance between two hashes."""
        if len(hash1) != len(hash2):
            return float('inf')
        
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)
        
        xor = int1 ^ int2
        return bin(xor).count('1')
    
    def estimate_room_count(self, images_analysis: List[dict]) -> int:
        """
        Estimate total room count from multiple images.
        """
        unique_rooms = set()
        
        for analysis in images_analysis:
            room = analysis.get("estimated_room")
            if room and room != "unknown":
                unique_rooms.add(room)
        
        return len(unique_rooms)
    
    def calculate_condition_score(self, images_analysis: List[dict]) -> float:
        """
        Calculate overall condition score (0-10) based on images.
        """
        if not images_analysis:
            return 5.0
        
        scores = []
        
        for analysis in images_analysis:
            score = 5.0  # Base score
            
            # Brightness factor
            brightness = analysis.get("brightness", 50)
            if brightness > 70:
                score += 1
            elif brightness < 30:
                score -= 1
            
            # Contrast factor
            contrast = analysis.get("contrast", 50)
            if contrast > 60:
                score += 0.5
            
            scores.append(score)
        
        avg_score = sum(scores) / len(scores)
        return round(max(0, min(10, avg_score)), 2)


class DuplicateImageDetector:
    """
    Detects duplicate images across different offers.
    Uses perceptual hashing.
    """
    
    def __init__(self):
        self.analyzer = ImageAnalyzer()
    
    async def check_duplicate(
        self,
        image_url: str,
        existing_hashes: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if image is a duplicate.
        
        Returns:
            (is_duplicate, matched_hash)
        """
        analysis = await self.analyzer.analyze_image(image_url)
        
        if "error" in analysis:
            return False, None
        
        phash = analysis.get("perceptual_hash")
        if not phash:
            return False, None
        
        similar = self.analyzer.find_similar_images(phash, existing_hashes)
        
        if similar:
            return True, similar[0]
        
        return False, None
    
    async def find_duplicate_offers(
        self,
        offer_images: dict  # {offer_id: [image_urls]}
    ) -> List[Tuple[str, str]]:
        """
        Find offers with duplicate images.
        
        Returns:
            List of (offer_id1, offer_id2) tuples
        """
        duplicates = []
        all_hashes = {}  # {offer_id: [hashes]}
        
        # Analyze all images
        for offer_id, image_urls in offer_images.items():
            hashes = []
            for url in image_urls:
                analysis = await self.analyzer.analyze_image(url)
                if "perceptual_hash" in analysis:
                    hashes.append(analysis["perceptual_hash"])
            all_hashes[offer_id] = hashes
        
        # Compare offers
        offer_ids = list(all_hashes.keys())
        for i, offer1 in enumerate(offer_ids):
            for offer2 in offer_ids[i+1:]:
                # Check if any images match
                for hash1 in all_hashes[offer1]:
                    similar = self.analyzer.find_similar_images(
                        hash1, all_hashes[offer2]
                    )
                    if similar:
                        duplicates.append((offer1, offer2))
                        break
        
        return duplicates


# Global instance
_image_analyzer: Optional[ImageAnalyzer] = None
_duplicate_detector: Optional[DuplicateImageDetector] = None


def get_image_analyzer() -> ImageAnalyzer:
    """Get or create image analyzer."""
    global _image_analyzer
    
    if _image_analyzer is None:
        _image_analyzer = ImageAnalyzer()
    
    return _image_analyzer


def get_duplicate_detector() -> DuplicateImageDetector:
    """Get or create duplicate detector."""
    global _duplicate_detector
    
    if _duplicate_detector is None:
        _duplicate_detector = DuplicateImageDetector()
    
    return _duplicate_detector
