# Autoclips

**Autoclips** is an automated web tool for generating organic video content from YouTube Shorts. It takes a list of YouTube Short URLs, downloads them, trims them to a 3-second "hook", and automatically stitches a user-provided Call-to-Action (CTA) video to the end of each clip. 

The resulting outputs are ready-to-post, high-quality, ~8-second vertical videos perfect for TikTok, Instagram Reels, and YouTube Shorts.

---

## 🚀 Features
- **Batch Processing**: Paste multiple YouTube Shorts URLs at once. They process in parallel!
- **Automated Trimming**: Extracts the crucial first 3 seconds of any Short to serve as a high-retention hook.
- **Custom CTA**: Upload your own video (any length or format) that gets automatically re-encoded and attached to every hook.
- **High-Quality Output**: Outputs conform to vertical video standards: 1080x1920 resolution, 60fps, with AAC stereo audio.
- **Glassmorphic UI**: Sleek, modern, dark-themed web interface for easy drag-and-drop usage.

---

## 🛠 Prerequisites
1. **Python**: Make sure Python is installed on your system ([python.org](https://www.python.org)).
2. **FFmpeg**: The tool relies heavily on `ffmpeg` for video manipulation. 
   - You can install it on Windows via terminal: `winget install ffmpeg`

---

## 🚦 How to Launch
1. Open the project folder.
2. Double-click the **`run.bat`** file.
   - *This script will automatically check for Python, install required dependencies (like Flask and yt-dlp), and start the local server.*
3. Your web browser should automatically open to `http://localhost:5000`.

---

## 📖 How to Use
1. **Step 1:** Upload your CTA (Call-to-Action) video. 
2. **Step 2:** Paste your YouTube Shorts URLs into the text box (one URL per line).
3. **Step 3:** Click **Generate Clips**.
4. The system will show a live progress bar for each URL as it downloads, trims, re-encodes, and stitches the final video.
5. Once complete, click the download buttons to save your ready-to-post content!

---

## 📂 Project Structure
```text
Autoclips/
├── app.py              # Main Flask backend application (handles downloads & ffmpeg)
├── requirements.txt    # Python dependencies
├── run.bat             # Auto-installer and server launcher for Windows
├── README.md           # This documentation file
├── templates/
│   └── index.html      # The main user interface
├── static/
│   ├── style.css       # UI styling (dark theme, animations)
│   └── script.js       # Client-side logic for uploads and progress polling
├── uploads/            # (Auto-created) Stores your uploaded CTA video
├── downloads/          # (Auto-created) Temporary storage for raw downloads/processing
└── output/             # (Auto-created) The final, stitched clips ready for download
```
