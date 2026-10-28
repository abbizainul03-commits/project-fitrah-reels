#!/usr/bin/env python3
"""Quran recitation video maker (Arabic + Malayalam, 1920x1080).

  python3 quran.py new   <name> --surah 55 --from 1 --to 40
  python3 quran.py time  <name>              # auto-detect verse timings from the audio
  python3 quran.py render <name> [--preview 30]

Each video lives in videos/<name>/ : put your recitation audio there (any audio file),
optionally a background (background.mp4 / .jpg, or several clips in backgrounds/),
and optionally logo.png for the corner watermark.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
VIDEOS = os.path.join(ROOT, 'videos')
API = 'https://raw.githubusercontent.com/fawazahmed0/quran-api/1'
W, H = 1920, 1080
AUDIO_EXT = ('.mp3', '.m4a', '.wav', '.aac', '.ogg', '.opus', '.flac')
VIDEO_EXT = ('.mp4', '.mov', '.webm', '.mkv')
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp')

DEFAULTS = {
    'translation': 'mal-abdulhameedmada',
    'channel': 'Your Channel',
    'intro_kicker': 'സൂറത്ത്',
    'intro_hold': 2.5,        # seconds of title card before the recitation starts
    'intro_segments': 1,      # audio segments before verse 1 (1 = Bismillah, 2 = Ta'awwudh + Bismillah, 0 = none)
    'lead': 0.25,             # show each verse this many seconds before the reciter starts it
    'fade': 0.4,
    'tail': 2.0,              # seconds held after the audio ends
    'background': '',         # '' = auto (your files, else night-sky) | night-sky | gold-smoke | sea-parting | a file name
    'dim': None,              # darken the background (0 = none, 1 = black); default depends on the background
    'blur': 0,                # blur the background (0 = off, try 6)
    'fps': 30,
    'silence_db': -35,
    'min_silence': 0.45,
}


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def pdir(name):
    d = os.path.join(VIDEOS, name)
    if not os.path.isdir(d):
        sys.exit(f'No project at {d}. Create it with: python3 quran.py new {name} --surah N --from A --to B')
    return d


def load_project(name):
    d = pdir(name)
    with open(os.path.join(d, 'project.json'), encoding='utf-8') as f:
        p = {**DEFAULTS, **json.load(f)}
    with open(os.path.join(d, 'verses.json'), encoding='utf-8') as f:
        verses = json.load(f)
    return d, p, verses


def find_audio(d, p):
    if p.get('audio'):
        return os.path.join(d, p['audio'])
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(AUDIO_EXT))
    if not files:
        sys.exit(f'No audio file found in {d}. Copy your recitation (mp3/m4a/wav) into that folder.')
    return os.path.join(d, files[0])


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def fmt(t):
    return f'{int(t // 60)}:{t % 60:05.2f}'


# ---------------------------------------------------------------- new
def cmd_new(a):
    d = os.path.join(VIDEOS, a.name)
    os.makedirs(d, exist_ok=True)
    info = fetch_json(f'{API}/info.json')['chapters'][a.surah - 1]
    last = len(info['verses'])
    a.to = min(a.to or last, last)
    ar = fetch_json(f'{API}/editions/ara-quranuthmanihaf/{a.surah}.json')['chapter']
    tr = fetch_json(f'{API}/editions/{a.translation}/{a.surah}.json')['chapter']
    eds = fetch_json(f'{API}/editions.json')
    author = eds.get(a.translation.replace('-', '_'), {}).get('author', a.translation)
    verses = [{'verse': v, 'arabic': ar[v - 1]['text'], 'translation': tr[v - 1]['text'].strip()}
              for v in range(a.frm, a.to + 1)]
    with open(os.path.join(d, 'verses.json'), 'w', encoding='utf-8') as f:
        json.dump(verses, f, ensure_ascii=False, indent=1)

    proj_path = os.path.join(d, 'project.json')
    proj = {}
    if os.path.exists(proj_path):
        with open(proj_path, encoding='utf-8') as f:
            proj = json.load(f)
    proj.update({
        'surah': a.surah, 'from': a.frm, 'to': a.to, 'translation': a.translation,
        'translation_author': author,
        'surah_name_en': info['name'], 'surah_name_ar': info['arabicname'],
    })
    proj.setdefault('surah_name_ml', info['name'])
    proj.setdefault('channel', a.channel or DEFAULTS['channel'])
    proj.setdefault('intro_segments', 0 if a.surah == 9 or a.frm > 1 else 1)
    with open(proj_path, 'w', encoding='utf-8') as f:
        json.dump(proj, f, ensure_ascii=False, indent=2)
    print(f'Created {d}\n  {len(verses)} verses ({info["name"]} {a.frm}-{a.to}), translation: {author}')
    print(f'Next: put your recitation audio in {d}, set "surah_name_ml" / "channel" in project.json,'
          f' then run: python3 quran.py time {a.name}')


# ---------------------------------------------------------------- time
def speech_segments(audio, db, min_sil):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', audio, '-af',
                          f'silencedetect=noise={db}dB:d={min_sil}', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    total = duration(audio)
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', err)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', err)]
    segs, cur = [], 0.0
    for i, s in enumerate(starts):
        if s > cur:
            segs.append([cur, s])
        cur = ends[i] if i < len(ends) else total
    if cur < total:
        segs.append([cur, total])
    return [s for s in segs if s[1] - s[0] >= 0.25], total


def fit_segments(segs, k):
    """Merge across the shortest pauses (pauses inside a verse) or split the longest
    segments until there are exactly k segments."""
    segs = [list(s) for s in segs]
    while len(segs) > k:
        gaps = [segs[i + 1][0] - segs[i][1] for i in range(len(segs) - 1)]
        i = gaps.index(min(gaps))
        segs[i:i + 2] = [[segs[i][0], segs[i + 1][1]]]
    while len(segs) < k:
        i = max(range(len(segs)), key=lambda j: segs[j][1] - segs[j][0])
        s, e = segs[i]
        m = (s + e) / 2
        segs[i:i + 1] = [[s, m], [m, e]]
    return segs


def cmd_time(a):
    d, p, verses = load_project(a.name)
    audio = find_audio(d, p)
    db = a.silence_db if a.silence_db is not None else p['silence_db']
    ms = a.min_silence if a.min_silence is not None else p['min_silence']
    segs, total = speech_segments(audio, db, ms)
    k = p['intro_segments'] + len(verses)
    print(f'Audio: {os.path.basename(audio)} ({fmt(total)}), found {len(segs)} recitation segments, need {k}')
    if len(segs) < k:
        print('  WARNING: fewer pauses than verses - some verses were split evenly. Check the times below,'
              ' or try --min-silence 0.3 / --silence-db -30.')
    fitted = fit_segments(segs, k)
    ay = fitted[p['intro_segments']:]
    timings = {'audio': os.path.basename(audio), 'audio_duration': round(total, 2),
               'ayahs': [{'verse': v['verse'], 'start': round(s[0], 2), 'end': round(s[1], 2)}
                         for v, s in zip(verses, ay)]}
    with open(os.path.join(d, 'timings.json'), 'w', encoding='utf-8') as f:
        json.dump(timings, f, indent=1)
    for t in timings['ayahs']:
        print(f'  verse {t["verse"]:>3}  {fmt(t["start"])} - {fmt(t["end"])}')
    print(f'Saved timings.json. Fix any start time there if needed, then: python3 quran.py render {a.name}')


# ---------------------------------------------------------------- render
# Generated (no footage needed) backgrounds: name -> (loop seconds, default dim)
STYLES = {'night-sky': (12, 0.45), 'gold-smoke': (16, 0.0), 'sea-parting': (16, 0.05)}


def default_background(fps, style='night-sky'):
    cache = os.path.join(ROOT, '.cache')
    out = os.path.join(cache, f'{style}_{fps}.mp4')
    if os.path.exists(out):
        return out
    frames = os.path.join(cache, 'bgframes')
    shutil.rmtree(frames, ignore_errors=True)
    loop = STYLES[style][0]
    print(f'Rendering "{style}" background loop (one time, cached in .cache/)...')
    js = os.path.join(ROOT, 'render_cards.js')
    if style == 'night-sky':
        run(['node', js, 'bgframes', frames, str(loop), str(fps)])
    else:
        run(['node', js, 'bgstyle', style, frames, str(loop), str(fps)])
    run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(frames, 'f_%05d.png'),
         '-vf', f'scale={W}:{H}:flags=lanczos', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', out])
    shutil.rmtree(frames, ignore_errors=True)
    return out


def background_input(d, p, build, fps):
    """Returns (ffmpeg input args, is_still_image) for the background."""
    norm = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1'
    if p.get('background') in STYLES:
        return ['-stream_loop', '-1', '-i', default_background(fps, p['background'])], False
    if p.get('background'):
        cands = [os.path.join(d, p['background'])]
    else:
        clips = sorted(glob.glob(os.path.join(d, 'backgrounds', '*')))
        cands = [c for c in clips if c.lower().endswith(VIDEO_EXT + IMAGE_EXT)]
        if not cands:
            cands = [os.path.join(d, f) for f in sorted(os.listdir(d))
                     if f.lower().startswith('background') and f.lower().endswith(VIDEO_EXT + IMAGE_EXT)][:1]
    if not cands:
        return ['-stream_loop', '-1', '-i', default_background(fps)], False
    if len(cands) == 1 and cands[0].lower().endswith(IMAGE_EXT):
        return ['-i', cands[0]], True
    if len(cands) == 1:
        return ['-stream_loop', '-1', '-i', cands[0]], False
    # several clips: normalise each, join them into one loop
    parts = []
    for i, c in enumerate(cands):
        out = os.path.join(build, f'bgpart_{i:02d}.mp4')
        src = ['-loop', '1', '-t', '8', '-i', c] if c.lower().endswith(IMAGE_EXT) else ['-i', c]
        run(['ffmpeg', '-y', '-loglevel', 'error', *src, '-an', '-vf', norm, '-c:v', 'libx264', '-crf', '18',
             '-pix_fmt', 'yuv420p', out])
        parts.append(out)
    lst = os.path.join(build, 'bglist.txt')
    with open(lst, 'w') as f:
        f.writelines(f"file '{os.path.abspath(x)}'\n" for x in parts)
    joined = os.path.join(build, 'bg_joined.mp4')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', joined])
    return ['-stream_loop', '-1', '-i', joined], False


def srt_time(t):
    ms = int(round(max(t, 0) * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def cmd_srt(a):
    """Subtitle files for editing the video yourself (CapCut, VN, Premiere...)."""
    d, p, verses = load_project(a.name)
    tpath = os.path.join(d, 'timings.json')
    if not os.path.exists(tpath):
        cmd_time(a)
    with open(tpath, encoding='utf-8') as f:
        ayahs = json.load(f)['ayahs']
    vmap = {v['verse']: v for v in verses}
    lead = p['lead']
    # each verse stays on screen until the next one starts (or 1.5 s after the last one ends)
    rows = []
    for i, t in enumerate(ayahs):
        start = max(0.0, t['start'] - lead)
        end = ayahs[i + 1]['start'] - lead - 0.05 if i + 1 < len(ayahs) else t['end'] + 1.5
        rows.append((start, end, vmap[t['verse']]))
    outs = {
        'malayalam': lambda v: v['translation'],
        'arabic': lambda v: f"{v['arabic']} ({v['verse']})",
        'arabic+malayalam': lambda v: f"{v['arabic']} ({v['verse']})\n{v['translation']}",
    }
    for kind, text in outs.items():
        path = os.path.join(d, f'{a.name}_{kind}.srt')
        with open(path, 'w', encoding='utf-8-sig') as f:   # BOM helps some editors detect UTF-8
            for n, (s_, e_, v) in enumerate(rows, 1):
                f.write(f'{n}\n{srt_time(s_)} --> {srt_time(e_)}\n{text(v)}\n\n')
        print(f'Saved {path}')
    with open(os.path.join(d, f'{a.name}_verses.txt'), 'w', encoding='utf-8') as f:
        for s_, e_, v in rows:
            f.write(f"[{fmt(s_)}] {v['verse']}\n{v['arabic']}\n{v['translation']}\n\n")


def cmd_render(a):
    d, p, verses = load_project(a.name)
    if a.background:
        p['background'] = a.background
    if p['dim'] is None:
        p['dim'] = STYLES.get(p['background'], (0, 0.45))[1]
    tpath = os.path.join(d, 'timings.json')
    if not os.path.exists(tpath):
        cmd_time(a)
    with open(tpath, encoding='utf-8') as f:
        timings = json.load(f)
    audio = find_audio(d, p)
    fps, fade, lead, hold = p['fps'], p['fade'], p['lead'], p['intro_hold']
    build = os.path.join(d, 'build')
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(build)

    # 1. cards
    vmap = {v['verse']: v for v in verses}
    name_ml = p.get('surah_name_ml') or p['surah_name_en']
    rng = f'{p["from"]} – {p["to"]}'
    logo = next((os.path.join(d, f) for f in ('logo.png', 'logo.jpg') if os.path.exists(os.path.join(d, f))), None)
    jobs = [
        {'out': os.path.join(build, 'overlay.png'), 'card': {
            'type': 'overlay', 'channel': p['channel'], 'vignette': True, 'dim': p['dim'],
            'logo': ('file://' + logo) if logo else None,
            'source': f'Quran {p["surah"]}:{rng.replace(" ", "")}  ·  Translation: {p.get("translation_author", "")}'}},
        {'out': os.path.join(build, 'intro.png'), 'card': {
            'type': 'intro', 'kicker': p['intro_kicker'], 'title': name_ml, 'arname': p['surah_name_ar'],
            'range': f'ആയത്ത് {rng}', 'bismillah': p['surah'] != 9}},
    ]
    for t in timings['ayahs']:
        v = vmap[t['verse']]
        jobs.append({'out': os.path.join(build, f'ayah_{t["verse"]:03d}.png'), 'card': {
            'type': 'ayah', 'verse': v['verse'], 'arabic': v['arabic'], 'translation': v['translation'],
            'ref': f'{name_ml}  ·  {p["surah"]}:{v["verse"]}'}})
    with open(os.path.join(build, 'jobs.json'), 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False)
    print(f'Rendering {len(jobs)} cards...')
    run(['node', os.path.join(ROOT, 'render_cards.js'), 'stills', os.path.join(build, 'jobs.json')])

    # 2. timeline: (card or None, start, end), frame-aligned
    snap = lambda t: round(t * fps) / fps
    total = snap(hold + timings['audio_duration'] + p['tail'])
    if a.preview:
        total = min(total, snap(a.preview))
    starts = [max(0.0, snap(hold + t['start'] - lead)) for t in timings['ayahs']]
    timeline = []
    if starts and starts[0] > 0.8:
        timeline.append((os.path.join(build, 'intro.png'), 0.0, starts[0]))
    elif starts and starts[0] > 0:
        timeline.append((None, 0.0, starts[0]))
    for i, t in enumerate(timings['ayahs']):
        end = starts[i + 1] if i + 1 < len(starts) else total
        timeline.append((os.path.join(build, f'ayah_{t["verse"]:03d}.png'), starts[i], end))
    timeline = [(c, s, min(e, total)) for c, s, e in timeline if s < total and e > s]

    # 3. transparent text track (qtrle keeps static frames tiny)
    print(f'Building text track ({len(timeline)} segments)...')
    lst = os.path.join(build, 'text.txt')
    with open(lst, 'w') as f:
        for i, (card, s, e) in enumerate(timeline):
            dur = e - s
            seg = os.path.join(build, f'seg_{i:04d}.mov')
            src = ['-loop', '1', '-framerate', str(fps), '-i', card] if card else \
                  ['-f', 'lavfi', '-i', f'color=c=black@0.0:s={W}x{H}:r={fps}']
            fd = min(fade, dur / 3)
            vf = f'format=argb,fade=t=in:st=0:d={fd}:alpha=1,fade=t=out:st={dur - fd:.3f}:d={fd}:alpha=1' if card \
                else 'format=argb'
            run(['ffmpeg', '-y', '-loglevel', 'error', *src, '-t', f'{dur:.3f}', '-vf', vf,
                 '-c:v', 'qtrle', '-pix_fmt', 'argb', seg])
            f.write(f"file '{os.path.abspath(seg)}'\n")
    text_track = os.path.join(build, 'text.mov')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', text_track])

    # 4. composite
    bg_in, still = background_input(d, p, build, fps)
    hold_still = f',loop=-1:1:0,setpts=N/{fps}/TB' if still else ''   # decode a still image once, not every frame
    blur = f',gblur=sigma={p["blur"]}' if p['blur'] else ''
    fc = (f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1{blur}{hold_still},fps={fps}[bg];'
          f'[2:v]format=yuva420p,loop=-1:1:0,setpts=N/{fps}/TB[ov];'      # dim + vignette + watermark, decoded once
          f'[bg][ov]overlay[v1];'
          f'[v1][1:v]overlay=eof_action=pass,format=yuv420p[v];'
          f'[3:a]adelay={int(hold * 1000)}:all=1,apad[a]')
    out = os.path.join(d, f'{a.name}{"_preview" if a.preview else ""}.mp4')
    print('Compositing final video...')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-stats', *bg_in, '-i', text_track,
         '-i', os.path.join(build, 'overlay.png'), '-i', audio,
         '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-t', f'{total:.3f}', '-r', str(fps),
         '-c:v', 'libx264', '-preset', a.x264_preset, '-crf', '18', '-c:a', 'aac', '-b:a', '192k',
         '-movflags', '+faststart', out])
    if not a.keep_build:
        for f in glob.glob(os.path.join(build, 'seg_*.mov')) + glob.glob(os.path.join(build, 'bgpart_*.mp4')):
            os.remove(f)
    print(f'Done: {out} ({fmt(total)})')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    n = sub.add_parser('new', help='create a video project and download the verses')
    n.add_argument('name')
    n.add_argument('--surah', type=int, required=True)
    n.add_argument('--from', dest='frm', type=int, default=1)
    n.add_argument('--to', type=int, default=0, help='last verse (default: end of surah)')
    n.add_argument('--translation', default=DEFAULTS['translation'],
                   help='mal-abdulhameedmada | mal-muhammadkarakun | mal-cheriyamundamab | eng-...')
    n.add_argument('--channel')
    for name, helptext in (('time', 'detect verse timings from the audio'), ('render', 'render the MP4'),
                           ('srt', 'export subtitle files (.srt) to edit the video yourself')):
        s = sub.add_parser(name, help=helptext)
        s.add_argument('name')
        s.add_argument('--silence-db', type=float)
        s.add_argument('--min-silence', type=float)
        if name == 'render':
            s.add_argument('--preview', type=float, help='only render the first N seconds')
            s.add_argument('--x264-preset', default='veryfast', help='ultrafast for quick tests, slow for max quality')
            s.add_argument('--keep-build', action='store_true')
            s.add_argument('--background', help='night-sky | gold-smoke | sea-parting | a file in the project folder')
    a = ap.parse_args()
    {'new': cmd_new, 'time': cmd_time, 'render': cmd_render, 'srt': cmd_srt}[a.cmd](a)


if __name__ == '__main__':
    main()
