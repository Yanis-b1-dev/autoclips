import os
import sys
import uuid
import threading
import subprocess
import shutil
import zipfile
import io
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"

for d in [UPLOAD_DIR, DOWNLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

# In-memory job tracker: { job_id: { urls: [], results: [], status: "running"|"done" } }
jobs = {}
jobs_lock = threading.Lock()

CTA_PATH = UPLOAD_DIR / "cta.mp4"

# ---------------------------------------------------------------------------
# Resolve ffmpeg at startup — searches WinGet, common paths, then falls back
# ---------------------------------------------------------------------------
def _find_ffmpeg() -> str:
    # 1. Already on PATH (normal case after shell restart)
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. WinGet install location (Gyan.FFmpeg package)
    local_app = Path(os.environ.get("LOCALAPPDATA", ""))
    winget_pkgs = local_app / "Microsoft" / "WinGet" / "Packages"
    for exe in winget_pkgs.glob("Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe"):
        return str(exe)

    # 3. Common static install paths
    for p in [
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/tools/ffmpeg/bin/ffmpeg.exe"),
    ]:
        if p.exists():
            return str(p)

    return "ffmpeg"  # last resort — will surface a clear error if truly missing

FFMPEG_BIN = _find_ffmpeg()

# Inject ffmpeg bin dir into PATH for all child processes (yt-dlp, etc.)
_ffmpeg_dir = str(Path(FFMPEG_BIN).parent)
if _ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Helper: run ffmpeg command and return (success, stderr)
# ---------------------------------------------------------------------------
def run_ffmpeg(*args):
    cmd = [FFMPEG_BIN, "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Helper: download + process a single URL
# ---------------------------------------------------------------------------
def process_url(url, job_id, idx):
    job = jobs[job_id]
    entry = job["results"][idx]
    entry["status"] = "downloading"

    work_dir = DOWNLOAD_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download with yt-dlp (best mp4, max 60s to be safe)
    raw_path = work_dir / f"{idx}_raw.mp4"
    yt_cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--ffmpeg-location", FFMPEG_BIN,
        "-f", "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "--merge-output-format", "mp4",
        "-o", str(raw_path),
        url
    ]
    result = subprocess.run(yt_cmd, capture_output=True, text=True)
    if result.returncode != 0 or not raw_path.exists():
        entry["status"] = "error"
        entry["error"] = f"Download failed: {result.stderr[-300:]}"
        return

    entry["status"] = "trimming"

    # 2. Trim hook to exactly 3 seconds (re-encode for clean cut)
    hook_path = work_dir / f"{idx}_hook.mp4"
    ok, err = run_ffmpeg(
        "-ss", "0",
        "-i", str(raw_path),
        "-t", "3",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "60",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        str(hook_path)
    )
    if not ok or not hook_path.exists():
        entry["status"] = "error"
        entry["error"] = f"Trim failed: {err[-300:]}"
        return

    entry["status"] = "encoding_cta"

    # 3. Re-encode CTA to match hook specs (1080x1920, 30fps, aac)
    cta_reenc_path = work_dir / f"{idx}_cta_reenc.mp4"
    ok, err = run_ffmpeg(
        "-i", str(CTA_PATH),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "60",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        str(cta_reenc_path)
    )
    if not ok or not cta_reenc_path.exists():
        entry["status"] = "error"
        entry["error"] = f"CTA re-encode failed: {err[-300:]}"
        return

    entry["status"] = "concatenating"

    # 4. Write concat list and stitch hook + CTA
    concat_list = work_dir / f"{idx}_concat.txt"
    concat_list.write_text(
        f"file '{hook_path.resolve()}'\nfile '{cta_reenc_path.resolve()}'\n"
    )

    output_name = f"clip_{job_id[:8]}_{idx + 1}.mp4"
    out_path = OUTPUT_DIR / output_name
    ok, err = run_ffmpeg(
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_path)
    )
    if not ok or not out_path.exists():
        entry["status"] = "error"
        entry["error"] = f"Concat failed: {err[-300:]}"
        return

    entry["status"] = "done"
    entry["filename"] = output_name

    # Cleanup work dir for this url
    shutil.rmtree(work_dir / f"{idx}_raw.mp4", ignore_errors=True)


# ---------------------------------------------------------------------------
# Background worker: processes all URLs in a job
# ---------------------------------------------------------------------------
def run_job(job_id):
    job = jobs[job_id]
    threads = []
    for idx, url in enumerate(job["urls"]):
        t = threading.Thread(target=process_url, args=(url, job_id, idx))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    job["status"] = "done"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload-cta", methods=["POST"])
def upload_cta():
    if "cta" not in request.files:
        return jsonify({"error": "No file sent"}), 400
    file = request.files["cta"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    file.save(str(CTA_PATH))
    return jsonify({"ok": True, "message": "CTA video uploaded successfully"})


@app.route("/process", methods=["POST"])
def process():
    if not CTA_PATH.exists():
        return jsonify({"error": "Upload your CTA video first"}), 400

    data = request.get_json()
    urls = [u.strip() for u in data.get("urls", []) if u.strip()]
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    job_id = str(uuid.uuid4())
    job = {
        "status": "running",
        "urls": urls,
        "results": [
            {"url": url, "status": "queued", "filename": None, "error": None}
            for url in urls
        ]
    }
    with jobs_lock:
        jobs[job_id] = job

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "results": job["results"]
    })


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)


@app.route("/files")
def list_files():
    files = [f.name for f in OUTPUT_DIR.iterdir() if f.suffix == ".mp4"]
    return jsonify({"files": sorted(files)})


@app.route("/download-all")
def download_all():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        job_id = request.args.get("job_id")
        for f in OUTPUT_DIR.iterdir():
            if f.suffix == ".mp4":
                if job_id:
                    if f.name.startswith(f"clip_{job_id[:8]}"):
                        zf.write(f, arcname=f.name)
                else:
                    zf.write(f, arcname=f.name)
    memory_file.seek(0)
    return send_file(memory_file, download_name="all_clips.zip", as_attachment=True)


@app.route("/clear-output", methods=["POST"])
def clear_output():
    for f in OUTPUT_DIR.iterdir():
        if f.suffix == ".mp4":
            f.unlink()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
