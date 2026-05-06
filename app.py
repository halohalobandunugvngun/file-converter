from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
import uuid
from PIL import Image
import logging
import json
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Universal File Converter & Video Downloader")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temp directory for conversions
TEMP_DIR = Path("/tmp/file-converter")
TEMP_DIR.mkdir(exist_ok=True)

# Supported conversions
DOCUMENT_FORMATS = {
    'docx': ['pdf', 'txt', 'html'],
    'doc': ['pdf', 'txt', 'html'],
    'xlsx': ['pdf', 'csv'],
    'xls': ['pdf', 'csv'],
    'pptx': ['pdf'],
    'ppt': ['pdf'],
    'odt': ['pdf', 'docx'],
    'ods': ['pdf', 'xlsx'],
    'odp': ['pdf', 'pptx'],
}

IMAGE_FORMATS = {
    'png': ['jpg', 'jpeg', 'webp', 'bmp', 'gif', 'ico', 'pdf'],
    'jpg': ['png', 'webp', 'bmp', 'gif', 'ico', 'pdf'],
    'jpeg': ['png', 'webp', 'bmp', 'gif', 'ico', 'pdf'],
    'webp': ['png', 'jpg', 'jpeg', 'bmp', 'gif', 'ico'],
    'bmp': ['png', 'jpg', 'jpeg', 'webp', 'gif', 'ico'],
    'gif': ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'ico'],
    'ico': ['png', 'jpg', 'jpeg', 'webp', 'bmp'],
}

VIDEO_FORMATS = {
    'mp4': ['mp3', 'wav', 'avi', 'mkv', 'webm', 'mov', 'flv', 'gif'],
    'avi': ['mp4', 'mp3', 'wav', 'mkv', 'webm', 'mov'],
    'mkv': ['mp4', 'mp3', 'wav', 'avi', 'webm', 'mov'],
    'webm': ['mp4', 'mp3', 'wav', 'avi', 'mkv', 'mov'],
    'mov': ['mp4', 'mp3', 'wav', 'avi', 'mkv', 'webm'],
    'flv': ['mp4', 'mp3', 'wav', 'avi', 'mkv', 'webm'],
}

AUDIO_FORMATS = {
    'mp3': ['wav', 'ogg', 'flac', 'm4a', 'aac'],
    'wav': ['mp3', 'ogg', 'flac', 'm4a', 'aac'],
    'ogg': ['mp3', 'wav', 'flac', 'm4a', 'aac'],
    'flac': ['mp3', 'wav', 'ogg', 'm4a', 'aac'],
    'm4a': ['mp3', 'wav', 'ogg', 'flac', 'aac'],
    'aac': ['mp3', 'wav', 'ogg', 'flac', 'm4a'],
}

ALL_FORMATS = {**DOCUMENT_FORMATS, **IMAGE_FORMATS, **VIDEO_FORMATS, **AUDIO_FORMATS}


def convert_document(input_path: Path, output_format: str) -> Path:
    """Convert document using LibreOffice"""
    output_dir = input_path.parent
    output_path = output_dir / f"{input_path.stem}.{output_format}"
    
    try:
        cmd = [
            'libreoffice',
            '--headless',
            '--convert-to', output_format,
            '--outdir', str(output_dir),
            str(input_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            raise Exception(f"LibreOffice conversion failed: {result.stderr}")
        
        if not output_path.exists():
            raise Exception("Output file was not created")
            
        return output_path
    except subprocess.TimeoutExpired:
        raise Exception("Conversion timeout (60s)")
    except Exception as e:
        raise Exception(f"Document conversion failed: {str(e)}")


def convert_image(input_path: Path, output_format: str) -> Path:
    """Convert image using Pillow"""
    output_path = input_path.parent / f"{input_path.stem}.{output_format}"
    
    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB for formats that don't support transparency
            if output_format.lower() in ['jpg', 'jpeg'] and img.mode in ['RGBA', 'LA', 'P']:
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ['RGBA', 'LA'] else None)
                img = rgb_img
            
            # Save with appropriate settings
            save_kwargs = {}
            if output_format.lower() in ['jpg', 'jpeg']:
                save_kwargs['quality'] = 95
            elif output_format.lower() == 'png':
                save_kwargs['optimize'] = True
            elif output_format.lower() == 'webp':
                save_kwargs['quality'] = 90
                
            img.save(output_path, format=output_format.upper(), **save_kwargs)
            
        return output_path
    except Exception as e:
        raise Exception(f"Image conversion failed: {str(e)}")


def convert_media(input_path: Path, output_format: str) -> Path:
    """Convert video/audio using FFmpeg"""
    output_path = input_path.parent / f"{input_path.stem}.{output_format}"
    
    try:
        # Basic FFmpeg command
        cmd = ['ffmpeg', '-i', str(input_path), '-y']
        
        # Format-specific settings
        if output_format in ['mp3']:
            cmd.extend(['-codec:a', 'libmp3lame', '-qscale:a', '2'])
        elif output_format in ['wav']:
            cmd.extend(['-codec:a', 'pcm_s16le'])
        elif output_format in ['mp4']:
            cmd.extend(['-codec:v', 'libx264', '-crf', '23', '-codec:a', 'aac'])
        elif output_format in ['webm']:
            cmd.extend(['-codec:v', 'libvpx-vp9', '-codec:a', 'libopus'])
        elif output_format == 'gif':
            cmd.extend(['-vf', 'fps=10,scale=480:-1:flags=lanczos', '-loop', '0'])
            
        cmd.append(str(output_path))
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg conversion failed: {result.stderr}")
            
        if not output_path.exists():
            raise Exception("Output file was not created")
            
        return output_path
    except subprocess.TimeoutExpired:
        raise Exception("Conversion timeout (5 minutes)")
    except Exception as e:
        raise Exception(f"Media conversion failed: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal File Converter</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .card {
            background: white;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 12px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 30px;
        }
        
        .upload-area:hover {
            border-color: #764ba2;
            background: #f8f9ff;
        }
        
        .upload-area.dragover {
            border-color: #764ba2;
            background: #f0f2ff;
        }
        
        .upload-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .upload-text {
            font-size: 1.2em;
            color: #333;
            margin-bottom: 10px;
        }
        
        .upload-hint {
            color: #666;
            font-size: 0.9em;
        }
        
        #fileInput {
            display: none;
        }
        
        .format-selector {
            margin-bottom: 20px;
        }
        
        .format-selector label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .format-selector select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: border-color 0.3s;
        }
        
        .format-selector select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .convert-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .convert-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .convert-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .files-list {
            margin-top: 30px;
        }
        
        .file-item {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .file-info {
            flex: 1;
        }
        
        .file-name {
            font-weight: 600;
            color: #333;
            margin-bottom: 4px;
        }
        
        .file-status {
            font-size: 0.9em;
            color: #666;
        }
        
        .file-status.converting {
            color: #667eea;
        }
        
        .file-status.success {
            color: #28a745;
        }
        
        .file-status.error {
            color: #dc3545;
        }
        
        .download-btn {
            padding: 8px 20px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
        }
        
        .download-btn:hover {
            background: #218838;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            margin-top: 8px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }
        
        .supported-formats {
            margin-top: 40px;
            padding-top: 30px;
            border-top: 2px solid #e0e0e0;
        }
        
        .supported-formats h3 {
            margin-bottom: 20px;
            color: #333;
        }
        
        .format-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .format-category {
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
        }
        
        .format-category h4 {
            color: #667eea;
            margin-bottom: 8px;
        }
        
        .format-category ul {
            list-style: none;
            font-size: 0.9em;
            color: #666;
        }
        
        .format-category li {
            padding: 4px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔄 Universal File Converter</h1>
            <p>Convert documents, images, videos, and audio files | <a href="/downloader" style="color: white; text-decoration: underline;">📥 Video Downloader</a></p>
        </div>
        
        <div class="card">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📁</div>
                <div class="upload-text">Click to upload or drag & drop files</div>
                <div class="upload-hint">Support multiple files at once</div>
            </div>
            <input type="file" id="fileInput" multiple>
            
            <div class="format-selector">
                <label for="outputFormat">Convert to:</label>
                <select id="outputFormat">
                    <option value="">Select output format...</option>
                </select>
            </div>
            
            <button class="convert-btn" id="convertBtn" disabled>Convert Files</button>
            
            <div class="files-list" id="filesList"></div>
            
            <div class="supported-formats">
                <h3>Supported Formats</h3>
                <div class="format-grid">
                    <div class="format-category">
                        <h4>📄 Documents</h4>
                        <ul>
                            <li>DOCX, DOC → PDF, TXT, HTML</li>
                            <li>XLSX, XLS → PDF, CSV</li>
                            <li>PPTX, PPT → PDF</li>
                            <li>ODT, ODS, ODP</li>
                        </ul>
                    </div>
                    <div class="format-category">
                        <h4>🖼️ Images</h4>
                        <ul>
                            <li>PNG ↔ JPG ↔ WEBP</li>
                            <li>BMP, GIF, ICO</li>
                            <li>Image → PDF</li>
                        </ul>
                    </div>
                    <div class="format-category">
                        <h4>🎬 Videos</h4>
                        <ul>
                            <li>MP4, AVI, MKV, WEBM</li>
                            <li>MOV, FLV</li>
                            <li>Video → MP3, GIF</li>
                        </ul>
                    </div>
                    <div class="format-category">
                        <h4>🎵 Audio</h4>
                        <ul>
                            <li>MP3 ↔ WAV ↔ OGG</li>
                            <li>FLAC, M4A, AAC</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const outputFormat = document.getElementById('outputFormat');
        const convertBtn = document.getElementById('convertBtn');
        const filesList = document.getElementById('filesList');
        
        let selectedFiles = [];
        let conversions = [];
        
        // Upload area click
        uploadArea.addEventListener('click', () => fileInput.click());
        
        // File input change
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        
        function handleFiles(files) {
            selectedFiles = Array.from(files);
            updateFormatOptions();
            displayFiles();
            convertBtn.disabled = selectedFiles.length === 0;
        }
        
        function updateFormatOptions() {
            if (selectedFiles.length === 0) {
                outputFormat.innerHTML = '<option value="">Select output format...</option>';
                return;
            }
            
            // Get common formats for all selected files
            const extensions = selectedFiles.map(f => {
                const ext = f.name.split('.').pop().toLowerCase();
                return ext;
            });
            
            // Fetch supported formats from API
            fetch('/api/formats')
                .then(r => r.json())
                .then(formats => {
                    const commonFormats = new Set();
                    
                    extensions.forEach(ext => {
                        if (formats[ext]) {
                            formats[ext].forEach(f => commonFormats.add(f));
                        }
                    });
                    
                    outputFormat.innerHTML = '<option value="">Select output format...</option>';
                    Array.from(commonFormats).sort().forEach(format => {
                        const option = document.createElement('option');
                        option.value = format;
                        option.textContent = format.toUpperCase();
                        outputFormat.appendChild(option);
                    });
                });
        }
        
        function displayFiles() {
            filesList.innerHTML = '';
            selectedFiles.forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <div class="file-info">
                        <div class="file-name">${file.name}</div>
                        <div class="file-status" id="status-${index}">Ready</div>
                        <div class="progress-bar" id="progress-${index}" style="display: none;">
                            <div class="progress-fill"></div>
                        </div>
                    </div>
                    <button class="download-btn" id="download-${index}" style="display: none;">Download</button>
                `;
                filesList.appendChild(fileItem);
            });
        }
        
        convertBtn.addEventListener('click', async () => {
            const format = outputFormat.value;
            if (!format) {
                alert('Please select an output format');
                return;
            }
            
            convertBtn.disabled = true;
            conversions = [];
            
            for (let i = 0; i < selectedFiles.length; i++) {
                await convertFile(selectedFiles[i], format, i);
            }
            
            convertBtn.disabled = false;
        });
        
        async function convertFile(file, format, index) {
            const statusEl = document.getElementById(`status-${index}`);
            const progressEl = document.getElementById(`progress-${index}`);
            const downloadBtn = document.getElementById(`download-${index}`);
            
            statusEl.textContent = 'Converting...';
            statusEl.className = 'file-status converting';
            progressEl.style.display = 'block';
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('output_format', format);
            
            try {
                const response = await fetch('/api/convert', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Conversion failed');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const filename = file.name.replace(/\.[^/.]+$/, '') + '.' + format;
                
                conversions.push({ url, filename });
                
                statusEl.textContent = 'Completed ✓';
                statusEl.className = 'file-status success';
                progressEl.querySelector('.progress-fill').style.width = '100%';
                
                downloadBtn.style.display = 'block';
                downloadBtn.onclick = () => {
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    a.click();
                };
                
            } catch (error) {
                statusEl.textContent = `Error: ${error.message}`;
                statusEl.className = 'file-status error';
                progressEl.style.display = 'none';
            }
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/formats")
async def get_formats():
    """Get supported formats"""
    return ALL_FORMATS


@app.post("/api/convert")
async def convert_file(
    file: UploadFile = File(...),
    output_format: str = Form(...)
):
    """Convert a single file"""
    # Get file extension
    input_ext = file.filename.split('.')[-1].lower()
    output_format = output_format.lower()
    
    # Validate conversion
    if input_ext not in ALL_FORMATS:
        raise HTTPException(400, f"Unsupported input format: {input_ext}")
    
    if output_format not in ALL_FORMATS.get(input_ext, []):
        raise HTTPException(400, f"Cannot convert {input_ext} to {output_format}")
    
    # Create unique temp directory for this conversion
    conversion_id = str(uuid.uuid4())
    temp_dir = TEMP_DIR / conversion_id
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Save uploaded file
        input_path = temp_dir / file.filename
        with open(input_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"Converting {file.filename} ({input_ext} → {output_format})")
        
        # Determine conversion type and convert
        if input_ext in DOCUMENT_FORMATS:
            output_path = convert_document(input_path, output_format)
        elif input_ext in IMAGE_FORMATS:
            output_path = convert_image(input_path, output_format)
        elif input_ext in VIDEO_FORMATS or input_ext in AUDIO_FORMATS:
            output_path = convert_media(input_path, output_format)
        else:
            raise HTTPException(400, "Unsupported format")
        
        # Return converted file
        return FileResponse(
            path=output_path,
            filename=f"{Path(file.filename).stem}.{output_format}",
            media_type='application/octet-stream',
            background=None  # Don't delete yet
        )
        
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        raise HTTPException(500, str(e))
    finally:
        # Cleanup after a delay (give time for download)
        # In production, use a background task or cleanup job
        pass


@app.get("/health")
async def health():
    """Health check endpoint"""
    checks = {
        "libreoffice": shutil.which("libreoffice") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "yt-dlp": shutil.which("yt-dlp") is not None,
    }
    
    return {
        "status": "healthy" if all(checks.values()) else "degraded",
        "dependencies": checks
    }


@app.post("/api/download/info")
async def get_video_info(url: str = Form(...)):
    """Get video information without downloading"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract available formats
            formats = []
            if 'formats' in info:
                seen = set()
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':  # Has both video and audio
                        height = f.get('height', 0)
                        ext = f.get('ext', 'mp4')
                        filesize = f.get('filesize') or f.get('filesize_approx', 0)
                        
                        if height and height not in seen:
                            seen.add(height)
                            formats.append({
                                'quality': f"{height}p",
                                'ext': ext,
                                'filesize': filesize,
                                'format_id': f.get('format_id')
                            })
            
            # Sort by quality
            formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
            
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'formats': formats[:10],  # Top 10 qualities
                'has_audio': any(f.get('acodec') != 'none' for f in info.get('formats', [])),
            }
            
    except Exception as e:
        logger.error(f"Video info error: {str(e)}")
        raise HTTPException(400, f"Failed to get video info: {str(e)}")


@app.post("/api/download")
async def download_video(
    url: str = Form(...),
    quality: str = Form("best"),
    format_type: str = Form("video")  # video or audio
):
    """Download video from URL"""
    download_id = str(uuid.uuid4())
    download_dir = TEMP_DIR / download_id
    download_dir.mkdir(exist_ok=True)
    
    try:
        logger.info(f"Downloading {format_type} from {url} (quality: {quality})")
        
        if format_type == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
        else:
            # Video download
            if quality == "best":
                format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                # Extract height from quality (e.g., "720p" -> 720)
                height = quality.replace('p', '')
                format_str = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
            
            ydl_opts = {
                'format': format_str,
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find the downloaded file
            downloaded_files = list(download_dir.glob('*'))
            if not downloaded_files:
                raise Exception("No file was downloaded")
            
            output_file = downloaded_files[0]
            filename = output_file.name
            
            logger.info(f"Downloaded: {filename}")
            
            return FileResponse(
                path=output_file,
                filename=filename,
                media_type='application/octet-stream',
                background=None
            )
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(500, f"Download failed: {str(e)}")
    finally:
        # Cleanup will happen later
        pass


@app.get("/downloader", response_class=HTMLResponse)
async def downloader_page():
    """Video downloader UI"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Video Downloader</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        h1 { color: #667eea; margin-bottom: 30px; }
        .input-group { margin: 20px 0; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        input, select { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1em; }
        input:focus, select:focus { outline: none; border-color: #667eea; }
        button { width: 100%; padding: 16px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 1.1em; font-weight: 600; cursor: pointer; margin: 10px 0; }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .video-info { display: none; margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .video-info img { max-width: 100%; border-radius: 8px; margin-bottom: 15px; }
        .status { padding: 15px; margin: 15px 0; border-radius: 8px; display: none; }
        .status.success { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .status.info { background: #d1ecf1; color: #0c5460; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #667eea; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .sites { margin-top: 30px; padding-top: 20px; border-top: 2px solid #e0e0e0; }
        .sites h3 { margin-bottom: 15px; color: #333; }
        .site-tags { display: flex; flex-wrap: wrap; gap: 10px; }
        .site-tags span { padding: 6px 12px; background: #e9ecef; border-radius: 6px; font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to Home</a>
        <h1>📥 Video Downloader</h1>
        
        <div class="input-group">
            <label>Video URL:</label>
            <input type="text" id="videoUrl" placeholder="Paste YouTube, Twitter, Instagram, TikTok, or any video URL...">
        </div>
        
        <button id="fetchBtn">Get Video Info</button>
        
        <div id="status" class="status"></div>
        
        <div id="videoInfo" class="video-info">
            <img id="thumbnail" src="" alt="Thumbnail">
            <h3 id="title"></h3>
            <p id="uploader"></p>
            <p id="duration"></p>
            
            <div class="input-group">
                <label>Download as:</label>
                <select id="downloadType">
                    <option value="video">Video</option>
                    <option value="audio">Audio Only (MP3)</option>
                </select>
            </div>
            
            <div class="input-group" id="qualityGroup">
                <label>Quality:</label>
                <select id="quality">
                    <option value="best">Best Quality</option>
                </select>
            </div>
            
            <button id="downloadBtn">Download</button>
        </div>
        
        <div class="sites">
            <h3>Supported Sites (1000+)</h3>
            <div class="site-tags">
                <span>YouTube</span>
                <span>Twitter/X</span>
                <span>Instagram</span>
                <span>TikTok</span>
                <span>Facebook</span>
                <span>Reddit</span>
                <span>Vimeo</span>
                <span>Dailymotion</span>
                <span>Twitch</span>
                <span>SoundCloud</span>
                <span>Bilibili</span>
                <span>And 990+ more...</span>
            </div>
        </div>
    </div>
    
    <script>
        const fetchBtn = document.getElementById('fetchBtn');
        const downloadBtn = document.getElementById('downloadBtn');
        const videoUrl = document.getElementById('videoUrl');
        const videoInfo = document.getElementById('videoInfo');
        const status = document.getElementById('status');
        const downloadType = document.getElementById('downloadType');
        const qualityGroup = document.getElementById('qualityGroup');
        
        function showStatus(message, type) {
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
        }
        
        fetchBtn.addEventListener('click', async () => {
            const url = videoUrl.value.trim();
            if (!url) {
                showStatus('Please enter a video URL', 'error');
                return;
            }
            
            fetchBtn.disabled = true;
            fetchBtn.textContent = 'Fetching info...';
            videoInfo.style.display = 'none';
            
            try {
                const formData = new FormData();
                formData.append('url', url);
                
                const response = await fetch('/api/download/info', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to fetch video info');
                }
                
                const data = await response.json();
                
                document.getElementById('thumbnail').src = data.thumbnail;
                document.getElementById('title').textContent = data.title;
                document.getElementById('uploader').textContent = 'By: ' + data.uploader;
                document.getElementById('duration').textContent = 'Duration: ' + Math.floor(data.duration / 60) + ':' + (data.duration % 60).toString().padStart(2, '0');
                
                // Populate quality options
                const qualitySelect = document.getElementById('quality');
                qualitySelect.innerHTML = '<option value="best">Best Quality</option>';
                data.formats.forEach(f => {
                    const option = document.createElement('option');
                    option.value = f.quality;
                    option.textContent = f.quality + ' (' + f.ext + ')';
                    qualitySelect.appendChild(option);
                });
                
                videoInfo.style.display = 'block';
                showStatus('Video info loaded successfully!', 'success');
                
            } catch (error) {
                showStatus(error.message, 'error');
            } finally {
                fetchBtn.disabled = false;
                fetchBtn.textContent = 'Get Video Info';
            }
        });
        
        downloadType.addEventListener('change', () => {
            qualityGroup.style.display = downloadType.value === 'audio' ? 'none' : 'block';
        });
        
        downloadBtn.addEventListener('click', async () => {
            const url = videoUrl.value.trim();
            const type = downloadType.value;
            const quality = document.getElementById('quality').value;
            
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Downloading...';
            showStatus('Downloading... This may take a while for large videos.', 'info');
            
            try {
                const formData = new FormData();
                formData.append('url', url);
                formData.append('format_type', type);
                formData.append('quality', quality);
                
                const response = await fetch('/api/download', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Download failed');
                }
                
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'video';
                a.click();
                window.URL.revokeObjectURL(downloadUrl);
                
                showStatus('Download complete!', 'success');
                
            } catch (error) {
                showStatus(error.message, 'error');
            } finally {
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Download';
            }
        });
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
