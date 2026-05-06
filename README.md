# Universal File Converter

A self-hosted web application for converting files between multiple formats.

## Features

- 📄 **Documents**: DOCX, XLSX, PPTX → PDF, TXT, HTML, CSV
- 🖼️ **Images**: PNG ↔ JPG ↔ WEBP ↔ BMP ↔ GIF ↔ ICO
- 🎬 **Videos**: MP4, AVI, MKV, WEBM, MOV, FLV (+ extract audio)
- 🎵 **Audio**: MP3 ↔ WAV ↔ OGG ↔ FLAC ↔ M4A ↔ AAC
- 📦 **Batch Processing**: Upload and convert multiple files at once
- 🎨 **Clean UI**: Modern, responsive web interface
- 🚀 **Fast**: Processes files one by one with progress tracking

## Tech Stack

- **Backend**: FastAPI (Python)
- **Document Conversion**: LibreOffice (headless)
- **Image Processing**: Pillow
- **Media Conversion**: FFmpeg
- **Frontend**: Vanilla JavaScript (no frameworks)

## Installation

### Prerequisites

```bash
# Install system dependencies
apt update
apt install -y libreoffice ffmpeg python3-pip python3-venv
```

### Setup

```bash
# Clone repository
git clone <your-repo-url>
cd file-converter

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

## Usage

### Development

```bash
source venv/bin/activate
python app.py
```

Access at: http://localhost:8000

### Production (systemd)

Create `/etc/systemd/system/file-converter.service`:

```ini
[Unit]
Description=Universal File Converter
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/projects/file-converter
Environment="PATH=/root/projects/file-converter/venv/bin"
ExecStart=/root/projects/file-converter/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable file-converter
systemctl start file-converter
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name converter.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Increase timeout for large file conversions
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        
        # Increase max upload size
        client_max_body_size 500M;
    }
}
```

## API Endpoints

### `GET /`
Web UI

### `GET /api/formats`
Get supported format conversions

### `POST /api/convert`
Convert a file
- **Form Data**:
  - `file`: File to convert
  - `output_format`: Target format (e.g., "pdf", "mp3")
- **Returns**: Converted file

### `GET /health`
Health check with dependency status

## Supported Conversions

### Documents
- **DOCX/DOC** → PDF, TXT, HTML
- **XLSX/XLS** → PDF, CSV
- **PPTX/PPT** → PDF
- **ODT/ODS/ODP** → PDF, DOCX, XLSX, PPTX

### Images
- **PNG** ↔ JPG, JPEG, WEBP, BMP, GIF, ICO, PDF
- **JPG/JPEG** ↔ PNG, WEBP, BMP, GIF, ICO, PDF
- **WEBP** ↔ PNG, JPG, BMP, GIF, ICO
- **BMP/GIF/ICO** ↔ PNG, JPG, WEBP

### Videos
- **MP4** → AVI, MKV, WEBM, MOV, MP3, WAV, GIF
- **AVI/MKV/WEBM/MOV/FLV** → MP4, MP3, WAV

### Audio
- **MP3** ↔ WAV, OGG, FLAC, M4A, AAC
- All audio formats are interconvertible

## Configuration

### Timeouts
- Document conversion: 60 seconds
- Media conversion: 300 seconds (5 minutes)

### Temp Directory
Files are stored in `/tmp/file-converter` during conversion.

### Quality Settings
- **JPEG**: Quality 95
- **PNG**: Optimized compression
- **WEBP**: Quality 90
- **MP3**: VBR quality 2 (high quality)
- **MP4**: CRF 23 (balanced quality/size)

## Troubleshooting

### LibreOffice not found
```bash
apt install libreoffice
```

### FFmpeg not found
```bash
apt install ffmpeg
```

### Conversion timeout
Increase timeout values in `app.py`:
- `convert_document()`: Change `timeout=60`
- `convert_media()`: Change `timeout=300`

### Large file uploads
Increase `client_max_body_size` in Nginx config.

## License

MIT

## Author

Built for self-hosting file conversion needs.
