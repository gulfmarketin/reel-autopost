import sys, json, base64, subprocess
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'scripts'))
from autopost import make_sfx
from playwright.sync_api import sync_playwright
mode, out = sys.argv[1], sys.argv[2]
cfgs = json.load(open(sys.argv[3]))
only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
FPS = 30
with sync_playwright() as p:
    b = p.chromium.launch()
    for cfg in cfgs:
        if only and cfg['row'] not in only: continue
        pg = b.new_page(viewport={'width': 1080, 'height': 1920})
        pg.goto('file://' + __import__('os').path.abspath(__import__('os').path.join(__import__('os').path.dirname(__file__), 'template.html'))); pg.wait_for_timeout(300)
        info = pg.evaluate('c => setup(c)', cfg)
        grab = lambda t: base64.b64decode(pg.evaluate(f"(render({t}), document.getElementById('c').toDataURL('image/jpeg',0.93))").split(',')[1])
        if mode == 'preview':
            t = 0; frames = []
            for sc in cfg['scenes']: frames.append(t + sc['d'] * 0.75); t += sc['d']
            frames[-1] = info['total'] - 0.5
            for i, ft in enumerate(frames): open(f"{out}/r{cfg['row']}_{i}.jpg", 'wb').write(grab(ft))
        else:
            silent = f"{out}/r{cfg['row']}.silent.mp4"
            ff = subprocess.Popen(['ffmpeg','-v','error','-y','-f','image2pipe','-vcodec','mjpeg','-r',str(FPS),'-i','-','-c:v','libx264','-pix_fmt','yuv420p','-crf','19',silent], stdin=subprocess.PIPE)
            for f in range(int(info['total'] * FPS)): ff.stdin.write(grab(f / FPS))
            ff.stdin.close(); ff.wait()
            wav = f"{out}/r{cfg['row']}.wav"; make_sfx(info['events'], info['total'], wav, seed=int(cfg['row']))
            subprocess.run(['ffmpeg','-v','error','-y','-i',silent,'-i',wav,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart', f"{out}/reel-row{cfg['row']}-40s.mp4"], check=True)
            subprocess.run(['rm', silent, wav]); print('done row', cfg['row'], info['total'])
        pg.close()
    b.close()
