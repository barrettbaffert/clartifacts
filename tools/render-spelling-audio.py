#!/usr/bin/env python3
"""Pre-render spelling.html narration as AAC clips with Kokoro (free, local TTS).

Recorded clips play through an <audio> element, which iOS does not mute with the
Ring/Silent switch (web speech is muted), and sound the same on every device.

Renders every list whose LISTS entry has `audio: true`, skipping clips that
already exist, plus the shared phrases in audio/common/. Lists without the flag
keep using the device voice.

  audio/<list id>/<slug>.m4a     the word
  audio/<list id>/<slug>.s.m4a   its sentence
  slug = word lowercased with everything but a-z0-9 removed (would've -> wouldve);
  spelling.html's clipSlug() must match.

Run with the Kokoro venv (Python 3.12; see ~/theLab/kokoro-venv):
  ~/theLab/kokoro-venv/bin/python tools/render-spelling-audio.py
  ~/theLab/kokoro-venv/bin/python tools/render-spelling-audio.py --voice bf_emma --force
"""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np, soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "spelling.html")
AUDIO = os.path.join(ROOT, "audio")
SR = 24000
WORD_SPEED, SENTENCE_SPEED = 0.9, 1.0
COMMON = {  # must match the clip names used in spelling.html
    "start": ("Let's practice spelling!", 1.0),
    "test": ("Testing, one two three. If you hear this, we're good.", 1.0),
}

def slug(word):
    return re.sub(r"[^a-z0-9]", "", word.lower())

def load_lists():
    """Evaluate the LISTS literal with node rather than regexing word pairs."""
    src = open(HTML, encoding="utf-8").read()
    m = re.search(r"const LISTS = \[.*?\n\];", src, re.S)
    if not m:
        sys.exit("could not find `const LISTS = [...]` in spelling.html")
    js = m.group(0) + "\nprocess.stdout.write(JSON.stringify(LISTS));"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)

class Voice:
    def __init__(self, name):
        from kokoro import KPipeline
        self.name = name
        # First letter of a Kokoro voice is its accent: a = American, b = British.
        self.pipe = KPipeline(lang_code=name[0], repo_id="hexgrad/Kokoro-82M")

    def render(self, text, speed, path):
        chunks = [np.asarray(a) for _, _, a in self.pipe(text, voice=self.name, speed=speed)]
        clip = np.concatenate(chunks).astype(np.float32)
        clip = clip / (np.abs(clip).max() or 1.0) * 0.89  # Kokoro levels vary clip to clip
        pad = np.zeros(int(SR * 0.05), dtype=np.float32)
        clip = np.concatenate([pad, clip, pad])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav = tmp.name
        try:
            sf.write(wav, clip, SR)
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "32000", wav, path], check=True)
        finally:
            os.unlink(wav)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default="af_heart", help="Kokoro voice (default af_heart)")
    ap.add_argument("--force", action="store_true", help="re-render clips that already exist")
    ap.add_argument("--list", help="only this list id")
    args = ap.parse_args()

    lists = [l for l in load_lists() if l.get("audio") and (not args.list or l["id"] == args.list)]
    jobs = []  # (text, speed, path)
    for name, (text, speed) in COMMON.items():
        jobs.append((text, speed, os.path.join(AUDIO, "common", name + ".m4a")))
    for l in lists:
        slugs = [slug(w) for w, _ in l["words"]]
        dupes = {s for s in slugs if slugs.count(s) > 1}
        if dupes or "" in slugs:
            sys.exit(f"{l['id']}: clip slugs collide or are empty: {sorted(dupes) or ['<empty>']}")
        for (word, sentence), s in zip(l["words"], slugs):
            d = os.path.join(AUDIO, l["id"])
            jobs.append((word + ".", WORD_SPEED, os.path.join(d, s + ".m4a")))
            jobs.append((sentence, SENTENCE_SPEED, os.path.join(d, s + ".s.m4a")))

    todo = [j for j in jobs if args.force or not os.path.exists(j[2])]
    print(f"{len(lists)} flagged list(s), {len(jobs)} clips, {len(todo)} to render with {args.voice}")
    if not todo:
        return
    voice = Voice(args.voice)
    for i, (text, speed, path) in enumerate(todo, 1):
        voice.render(text, speed, path)
        print(f"  [{i}/{len(todo)}] {os.path.relpath(path, ROOT)}")
    with open(os.path.join(AUDIO, "VOICE"), "w") as f:
        f.write(args.voice + "\n")

if __name__ == "__main__":
    main()
