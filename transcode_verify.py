#!/usr/bin/env python3
"""仅用于验证6119设备按需转码，监听端口6081"""
from flask import Flask, request, jsonify
import subprocess
import signal
import logging

app = Flask(__name__)
logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")

# 仅6119设备
DEV_ID = "dev6119"
SRC_RTSP = "rtsp://admin:JRULMI@8.137.101.41:6119/h264/ch1/main/av_stream"
DST_RTSP = "rtsp://local:local123@127.0.0.1:6200/internal/trans_dev6119"

ref_count = 0
ffmpeg_proc = None

def kill_ffmpeg():
    global ffmpeg_proc
    if ffmpeg_proc:
        logging.info("kill ffmpeg process")
        try:
            ffmpeg_proc.terminate()
            ffmpeg_proc.wait(3)
        except Exception:
            ffmpeg_proc.kill()
        ffmpeg_proc = None

def sig_exit(signum, frame):
    logging.warning("dispatcher exit, cleanup ffmpeg")
    kill_ffmpeg()

signal.signal(signal.SIGINT, sig_exit)
signal.signal(signal.SIGTERM, sig_exit)

def launch_ffmpeg():
    global ffmpeg_proc
    cmd = [
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-stimeout", "3000000",
        "-i", SRC_RTSP,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "24",
        "-profile:v", "baseline",
        "-x264opts", "bframes=0:no-cabac=1:keyint=25",
        "-c:a", "opus", "-b:a", "64k",
        "-f", "rtsp", "-rtsp_transport", "tcp",
        DST_RTSP
    ]
    logging.info(f"start ffmpeg for {DEV_ID}")
    ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route("/hook/connect", methods=["POST"])
def hook_connect():
    global ref_count
    payload = request.get_json()
    path = payload.get("path","")
    if path != "/play/dev6119":
        return jsonify({"status":"ignore"}),200

    ref_count +=1
    logging.info(f"connect {DEV_ID}, ref={ref_count}")
    if ref_count == 1:
        launch_ffmpeg()
    return jsonify({"status":"ok"}),200

@app.route("/hook/disconnect", methods=["POST"])
def hook_disconnect():
    global ref_count
    payload = request.get_json()
    path = payload.get("path","")
    if path != "/play/dev6119":
        return jsonify({"status":"ignore"}),200

    ref_count -=1
    logging.info(f"disconnect {DEV_ID}, ref={ref_count}")
    if ref_count <= 0:
        kill_ffmpeg()
        ref_count = 0
    return jsonify({"status":"ok"}),200

if __name__ == "__main__":
    # 端口修改为6081，仅监听本地回环
    app.run(host="127.0.0.1", port=6081, debug=False)
