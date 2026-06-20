# core/trickplay.py
import os
import subprocess
import logging
from pathlib import Path
from PIL import Image
import math

logger = logging.getLogger(__name__)

class TrickplayGenerator:
    """Generate trickplay sprites for smooth seeking (like Jellyfin)"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.trickplay_dir = Path("data/trickplay")
        self.trickplay_dir.mkdir(parents=True, exist_ok=True)
        
    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def generate_trickplay(self, video_path: str, media_id: int, media_type: str) -> dict:
        """Generate trickplay sprites for a video file"""
        if not self.check_ffmpeg():
            logger.warning("ffmpeg not available, cannot generate trickplay")
            return None
        
        trickplay_folder = self.trickplay_dir / str(media_id)
        trickplay_folder.mkdir(parents=True, exist_ok=True)
        
        # Get video duration
        duration = self._get_video_duration(video_path)
        if not duration:
            return None
        
        # Number of screenshots (10-second intervals, max 100 images)
        interval = 10
        num_screenshots = min(math.ceil(duration / interval), 100)
        
        # Generate screenshots
        screenshot_paths = []
        for i in range(num_screenshots):
            timestamp = i * interval
            output_path = trickplay_folder / f"screenshot_{i:04d}.jpg"
            
            if not output_path.exists():
                success = self._extract_frame(video_path, timestamp, str(output_path))
                if success:
                    screenshot_paths.append(str(output_path))
            else:
                screenshot_paths.append(str(output_path))
        
        if not screenshot_paths:
            return None
        
        # Create sprite sheet
        sprite_sheet, sprite_info = self._create_sprite_sheet(screenshot_paths, trickplay_folder)
        
        return {
            'media_id': media_id,
            'media_type': media_type,
            'interval': interval,
            'sprite_sheet': sprite_sheet,
            'sprite_info': sprite_info,
            'num_screenshots': len(screenshot_paths)
        }
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
        return None
    
    def _extract_frame(self, video_path: str, timestamp: float, output_path: str) -> bool:
        """Extract a single frame from video at given timestamp"""
        try:
            cmd = [
                'ffmpeg', '-ss', str(timestamp), '-i', video_path,
                '-frames:v', '1', '-vf', 'scale=320:-1', '-q:v', '2',
                '-y', output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to extract frame: {e}")
            return False
    
    def _create_sprite_sheet(self, image_paths: list, output_folder: Path) -> tuple:
        """Create a sprite sheet from multiple images"""
        try:
            from PIL import Image
            
            images = []
            for path in image_paths:
                if os.path.exists(path):
                    img = Image.open(path)
                    images.append(img)
            
            if not images:
                return None, None
            
            # Calculate grid size
            cols = min(10, len(images))
            rows = math.ceil(len(images) / cols)
            
            # Get image dimensions
            img_width, img_height = images[0].size
            
            # Create sprite sheet
            sprite_width = cols * img_width
            sprite_height = rows * img_height
            sprite_sheet = Image.new('RGB', (sprite_width, sprite_height))
            
            # Paste images
            for idx, img in enumerate(images):
                x = (idx % cols) * img_width
                y = (idx // cols) * img_height
                sprite_sheet.paste(img, (x, y))
            
            # Save sprite sheet
            sprite_path = output_folder / 'sprite.jpg'
            sprite_sheet.save(sprite_path, 'JPEG', quality=85)
            
            sprite_info = {
                'cols': cols,
                'rows': rows,
                'image_width': img_width,
                'image_height': img_height,
                'sprite_width': sprite_width,
                'sprite_height': sprite_height,
                'count': len(images)
            }
            
            return str(sprite_path), sprite_info
            
        except Exception as e:
            logger.error(f"Failed to create sprite sheet: {e}")
            return None, None
    
    def get_trickplay_html(self, media_id: int, duration: float) -> str:
        """Get HTML for trickplay seek bar"""
        trickplay_folder = self.trickplay_dir / str(media_id)
        sprite_path = trickplay_folder / 'sprite.jpg'
        
        if not sprite_path.exists():
            return ''
        
        # Read sprite info
        info_path = trickplay_folder / 'sprite_info.json'
        if info_path.exists():
            import json
            with open(info_path, 'r') as f:
                sprite_info = json.load(f)
        else:
            return ''
        
        interval = 10  # seconds between screenshots
        
        return f'''
        <div class="trickplay-container" style="position: relative; margin-top: 10px;">
            <div id="trickplayPreview" style="position: absolute; bottom: 50px; left: 0; display: none; pointer-events: none;">
                <img id="trickplayImage" src="/api/trickplay/sprite/{media_id}" style="border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.5);">
                <div id="trickplayTime" style="position: absolute; bottom: 5px; right: 5px; background: rgba(0,0,0,0.7); padding: 2px 6px; border-radius: 4px; font-size: 12px;"></div>
            </div>
            <input type="range" id="trickplaySeekBar" min="0" max="{duration}" step="0.1" style="width: 100%;" oninput="updateTrickplayPreview(this.value)">
        </div>
        
        <script>
        const spriteCols = {sprite_info['cols']};
        const spriteRows = {sprite_info['rows']};
        const imageWidth = {sprite_info['image_width']};
        const imageHeight = {sprite_info['image_height']};
        const spriteWidth = {sprite_info['sprite_width']};
        const spriteHeight = {sprite_info['sprite_height']};
        const screenshotsCount = {sprite_info['count']};
        const interval = {interval};
        const duration = {duration};
        
        let currentPreviewIndex = -1;
        
        function updateTrickplayPreview(seconds) {{
            const previewDiv = document.getElementById('trickplayPreview');
            const previewImage = document.getElementById('trickplayImage');
            const previewTime = document.getElementById('trickplayTime');
            
            // Calculate which screenshot to show
            const index = Math.floor(seconds / interval);
            if (index >= screenshotsCount) return;
            
            if (currentPreviewIndex !== index) {{
                currentPreviewIndex = index;
                
                // Calculate position in sprite sheet
                const col = index % spriteCols;
                const row = Math.floor(index / spriteCols);
                const x = -col * imageWidth;
                const y = -row * imageHeight;
                
                previewImage.style.objectPosition = `${{x}}px ${{y}}px`;
                previewImage.style.width = `${spriteWidth}px`;
                previewImage.style.height = `${spriteHeight}px`;
            }}
            
            // Format time
            const minutes = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            previewTime.textContent = `${minutes}:${secs.toString().padStart(2, '0')}`;
            
            // Position preview based on seek bar position
            const seekBar = document.getElementById('trickplaySeekBar');
            const percent = seconds / duration;
            const previewX = percent * seekBar.offsetWidth - imageWidth / 2;
            previewDiv.style.left = `${{Math.max(0, Math.min(previewX, seekBar.offsetWidth - imageWidth))}}px`;
            previewDiv.style.display = 'block';
        }}
        
        // Hide preview when not hovering
        document.getElementById('trickplaySeekBar').addEventListener('mouseleave', () => {{
            document.getElementById('trickplayPreview').style.display = 'none';
        }});
        </script>
        '''