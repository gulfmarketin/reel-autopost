"""Pick the next unposted row from the Google Sheet, render it as a reel, publish to Instagram.

Env:
  SHEET_CSV_URL    CSV export link of the sheet (or pass --csv path for a local file)
  IG_USER_ID       Instagram professional account ID
  IG_ACCESS_TOKEN  Page access token with instagram_content_publish
  HANDLE           optional text shown at the bottom of the video (e.g. @yourpage)
  DRY_RUN=1        render only, don't publish
"""
import argparse, base64, csv, hashlib, io, json, os, subprocess, sys, time, wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "posted.json"
OUT = ROOT / "out"
GRAPH = "https://graph.facebook.com/v21.0"
FPS, SR = 30, 44100


# ---------------- sheet ----------------
def load_rows(csv_path=None):
    if csv_path:
        text = Path(csv_path).read_text(encoding="utf-8")
    else:
        r = requests.get(os.environ["SHEET_CSV_URL"], timeout=60)
        r.raise_for_status()
        text = r.content.decode("utf-8")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row.get("Text") or "").strip()
        if not raw:
            continue
        status = (row.get("Status") or "").strip().upper()
        if status not in ("", "READY"):
            continue  # set Status to SKIP / POSTED in the sheet to exclude a row
        hook, _, payoff = raw.partition("Payoff:")
        rows.append({
            "no": row.get("No.", ""),
            "hook": hook.strip(),
            "payoff": payoff.strip(),
            "caption": (row.get("Caption") or "").strip(),
            "key": hashlib.sha1(raw.encode()).hexdigest()[:16],
        })
    return rows


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"posted": {}}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False))


# ---------------- video ----------------
def render_video(row, index, out_path):
    from playwright.sync_api import sync_playwright
    data = {"hook": row["hook"], "payoff": row["payoff"], "index": index, "handle": os.environ.get("HANDLE", "")}
    silent = out_path.with_suffix(".silent.mp4")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto((ROOT / "template" / "reel.html").as_uri())
        pg.evaluate("document.fonts.ready")
        info = pg.evaluate("d => setup(d)", data)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-r", str(FPS),
                               "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
                               str(silent)], stdin=subprocess.PIPE)
        for f in range(int(info["total"] * FPS)):
            d = pg.evaluate(f"(render({f / FPS}), document.getElementById('c').toDataURL('image/jpeg',0.93))")
            ff.stdin.write(base64.b64decode(d.split(",")[1]))
        ff.stdin.close(); ff.wait()
        b.close()
    wav = out_path.with_suffix(".wav")
    make_sfx(info["events"], info["total"], wav, seed=index)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(out_path)], check=True)
    silent.unlink(); wav.unlink()
    return info["total"]


# ---------------- sound effects (no music) ----------------
def make_sfx(events, total, path, seed=0):
    rng = np.random.default_rng(seed)
    n = int(SR * (total + 0.5)); L = np.zeros(n); R = np.zeros(n)

    def bp(x, lo, hi):
        return sosfilt(butter(2, [lo, hi], "bandpass", fs=SR, output="sos"), x)

    def whoosh(up):
        d = 0.8; m = int(d * SR); tt = np.arange(m) / SR; x = rng.standard_normal(m); out = np.zeros(m)
        for c in range(40):
            p = c / 40; fc = 300 + (p if up else 1 - p) * 3000
            out += bp(x, fc * 0.6, fc * 1.4) * np.exp(-((tt - p * d) / (d / 40 * 1.5)) ** 2)
        return out * np.sin(np.pi * np.minimum(1, tt / d)) ** 2 / np.abs(out).max()

    def tick(f):
        tt = np.arange(int(0.04 * SR)) / SR
        return np.sin(2 * np.pi * f * tt) * np.exp(-tt * 120) + 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt * 300)

    def pop(f):
        tt = np.arange(int(0.18 * SR)) / SR
        return np.sin(2 * np.pi * (f * np.exp(-tt * 6)) * tt) * np.exp(-tt * 22)

    for i, (t, kind) in enumerate(events):
        if kind == "whoosh":
            sig, g, at = whoosh(i % 2 == 0), 0.35, max(0, t - 0.3)
        elif kind == "tick":
            sig, g, at = tick(2000 + (i % 4) * 220), 0.4, t
        else:
            sig, g, at = pop(700), 0.55, t
        s = int(at * SR); e = min(n, s + len(sig)); pan = 0.35 + 0.3 * (i % 2)
        L[s:e] += sig[:e - s] * g * (1 - pan); R[s:e] += sig[:e - s] * g * pan
    mix = np.stack([L, R], 1); mix = mix / (np.abs(mix).max() or 1) * 0.85
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())


# ---------------- instagram ----------------
def publish(video, caption):
    uid, tok = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    r = requests.post(f"{GRAPH}/{uid}/media", data={"media_type": "REELS", "upload_type": "resumable",
                                                    "caption": caption, "share_to_feed": "true", "access_token": tok}, timeout=60)
    r.raise_for_status(); cid = r.json()["id"]
    size = video.stat().st_size
    with open(video, "rb") as fh:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/v21.0/{cid}", data=fh, timeout=300,
                          headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)})
    r.raise_for_status()
    for _ in range(20):  # up to ~10 minutes
        time.sleep(30)
        st = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=60).json()
        code = st.get("status_code")
        print("container status:", code)
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {st}")
    else:
        raise RuntimeError("Instagram processing timed out")
    r = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--row", help="render a specific sheet No. (testing)")
    ap.add_argument("--count", type=int, default=1)
    a = ap.parse_args()
    dry = os.environ.get("DRY_RUN", "") in ("1", "true", "True") or not os.environ.get("IG_ACCESS_TOKEN")
    rows = load_rows(a.csv); st = load_state()
    seen, queue = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            continue  # duplicate text in the sheet
        seen.add(r["key"])
        if a.row and r["no"] != a.row:
            continue
        if not a.row and r["key"] in st["posted"]:
            continue
        queue.append((len(seen) - 1, r))
    print(f"{len(seen)} unique posts in sheet, {len(st['posted'])} already posted, {len(queue)} waiting")
    if not queue:
        print("Nothing left to post. Add new rows to the sheet."); return
    OUT.mkdir(exist_ok=True)
    for idx, row in queue[:a.count]:
        out = OUT / f"reel-{row['no']}.mp4"
        dur = render_video(row, idx, out)
        print(f"rendered row {row['no']} ({dur:.1f}s) -> {out}")
        if dry:
            print("DRY RUN: not publishing"); continue
        media_id = publish(out, row["caption"])
        st["posted"][row["key"]] = {"no": row["no"], "media_id": media_id,
                                    "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        save_state(st)
        print(f"published row {row['no']} as media {media_id}")


if __name__ == "__main__":
    sys.exit(main())
