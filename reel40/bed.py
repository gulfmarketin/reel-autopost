import sys, subprocess, numpy as np, wave
src, out, total = sys.argv[1], sys.argv[2], float(sys.argv[3])
SR = 44100
raw = subprocess.run(['ffmpeg','-v','error','-i',src,'-f','s16le','-ac','2','-ar',str(SR),'-'], capture_output=True, check=True).stdout
x = np.frombuffer(raw, '<i2').reshape(-1, 2).astype(np.float32) / 32768
xf = int(0.5 * SR)                      # 0.5 s equal-power crossfade between loops
fade_in = np.sin(np.linspace(0, np.pi/2, xf))[:, None]; fade_out = np.cos(np.linspace(0, np.pi/2, xf))[:, None]
n = int(total * SR); bed = np.zeros((n + len(x), 2), np.float32); pos = 0
while pos < n:
    seg = x.copy()
    if pos > 0: seg[:xf] *= fade_in
    seg[-xf:] *= fade_out
    bed[pos:pos + len(seg)] += seg; pos += len(seg) - xf
bed = bed[:n]
t = np.arange(n) / SR
bed *= np.minimum(1, np.minimum(t / 1.0, (total - t) / 2.0))[:, None]   # 1 s fade in, 2 s fade out
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(bed, -1, 1) * 32767).astype('<i2').tobytes())
