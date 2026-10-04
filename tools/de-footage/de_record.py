"""Record the DE window (60 fps, NVENC) and the system sound (WASAPI loopback) for the live study.

usage: C:/tmp/de-footage/tools/venv/Scripts/python tools/de-footage/de_record.py "<window title>" <out_dir>
Stop: create <out_dir>/STOP (the script then finishes ffmpeg with 'q' and closes the WAV).
Outputs: video.mkv, audio.wav, sync.json (start stamps of both streams, perf_counter + wall clock).
Align later by a calibration click: the UI click sound vs the frame where the cursor clicks.
"""
import json
import os
import subprocess
import sys
import threading
import time
import warnings
import wave

import numpy as np
import soundcard as sc

warnings.filterwarnings("ignore")
title, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
stop_flag = os.path.join(out, "STOP")
if os.path.exists(stop_flag):
    os.remove(stop_flag)
sync = {}
stop = threading.Event()


def audio():
    spk = sc.default_speaker()
    mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
    with wave.open(os.path.join(out, "audio.wav"), "wb") as w, mic.recorder(samplerate=48000, channels=2) as r:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        sync["audio_start_perf"] = time.perf_counter()
        sync["audio_start_wall"] = time.time()
        while not stop.is_set():
            d = r.record(numframes=4800)  # 100 ms blocks
            w.writeframes((np.clip(d, -1, 1) * 32767).astype("<i2").tobytes())


t = threading.Thread(target=audio, daemon=True)
t.start()
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", "60",
       "-draw_mouse", "1", "-i", f"title={title}", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19",
       os.path.join(out, "video.mkv")]
sync["video_spawn_perf"] = time.perf_counter()
sync["video_spawn_wall"] = time.time()
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
print("recording; touch", stop_flag, "to stop", flush=True)
while p.poll() is None and not os.path.exists(stop_flag):
    time.sleep(0.5)
if p.poll() is None:
    p.stdin.write(b"q")
    p.stdin.flush()
    p.wait(timeout=30)
stop.set()
t.join(timeout=5)
sync["video_exit_code"] = p.returncode
json.dump(sync, open(os.path.join(out, "sync.json"), "w"), indent=1)
print("stopped", sync, flush=True)
