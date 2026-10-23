"""Render a Script into a 1080x1920 Short (mp4) and a thumbnail (jpg).

Captions are drawn with Pillow; ffmpeg stitches them. Narration audio comes
from an optional `tts_command` in the config (any CLI TTS, e.g. edge-tts):
the placeholders {text} and {out} are filled in. Without it the Short is
rendered with background music only (or silent).
"""
import shlex
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
CHARS_PER_SECOND = 7.0  # Korean narration pace; adjust per voice
MIN_BEAT_SECONDS = 2.0


def _font(cfg, size):
    path = cfg.get("font_path")
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _card(text, cfg, out, accent=(255, 214, 0)):
    img = Image.new("RGB", (W, H), tuple(cfg.get("background_rgb", (16, 16, 20))))
    d = ImageDraw.Draw(img)
    font = _font(cfg, 88)
    lines = textwrap.wrap(text, width=cfg.get("wrap_chars", 12)) or [""]
    line_h = 110
    y = (H - line_h * len(lines)) // 2
    for line in lines:
        w = d.textlength(line, font=font)
        d.text(((W - w) / 2, y), line, font=font, fill=accent, stroke_width=4, stroke_fill=(0, 0, 0))
        y += line_h
    handle = cfg.get("handle")
    if handle:
        small = _font(cfg, 44)
        d.text((60, H - 160), handle, font=small, fill=(200, 200, 200))
    img.save(out)


def beat_seconds(narration):
    return max(MIN_BEAT_SECONDS, len(narration) / CHARS_PER_SECOND)


def timeline(script):
    """(caption, narration, seconds) for every segment of the Short."""
    segs = [(script.thumbnail_text, script.hook)]
    segs += [(b.on_screen, b.narration) for b in script.beats]
    segs += [(script.perspective, script.perspective), (script.cta, script.cta)]
    return [(cap, nar, beat_seconds(nar)) for cap, nar in segs]


def _tts(cfg, text, out):
    cmd = cfg.get("tts_command")
    if not cmd:
        return None
    subprocess.run(cmd.format(text=shlex.quote(text), out=shlex.quote(str(out))), shell=True, check=True)
    return out


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       check=True, capture_output=True, text=True)
    return float(r.stdout.strip())


def _voice_track(cfg, segs, out_dir):
    """Synthesize each segment separately so every caption lasts exactly as long as its line."""
    if not cfg.get("tts_command"):
        return None, segs
    timed, parts = [], []
    for i, (cap, nar, _) in enumerate(segs):
        clip = _tts(cfg, nar, out_dir / f"voice_{i:02d}.mp3")
        sec = _duration(clip) + 0.25  # short breath between lines
        padded = out_dir / f"voice_{i:02d}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-af", "apad", "-t", f"{sec:.3f}",
                        "-ar", "44100", "-ac", "1", str(padded)], check=True)
        timed.append((cap, nar, sec))
        parts.append(f"file '{padded.resolve()}'")
    (out_dir / "voice.txt").write_text("\n".join(parts) + "\n")
    voice = out_dir / "voice.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(out_dir / "voice.txt"),
                    "-c:a", "aac", str(voice)], check=True)
    return voice, timed


def render(script, cfg, out_dir):
    out_dir = Path(out_dir)
    frames = out_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    voice, segs = _voice_track(cfg, timeline(script), out_dir)
    concat = []
    for i, (cap, _, sec) in enumerate(segs):
        f = frames / f"{i:02d}.png"
        _card(cap, cfg, f)
        concat += [f"file '{f.resolve()}'", f"duration {sec:.2f}"]
    concat.append(f"file '{(frames / f'{len(segs) - 1:02d}.png').resolve()}'")  # concat demuxer needs the last frame twice
    (out_dir / "concat.txt").write_text("\n".join(concat) + "\n")
    total = sum(s for _, _, s in segs)

    bgm = cfg.get("bgm_path")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(out_dir / "concat.txt")]
    audio_inputs = [p for p in (voice, bgm) if p]
    for p in audio_inputs:
        cmd += ["-i", str(p)]
    if len(audio_inputs) == 2:
        cmd += ["-filter_complex", "[2:a]volume=0.15[b];[1:a][b]amix=inputs=2:duration=first[a]", "-map", "0:v", "-map", "[a]"]
    elif audio_inputs:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-t", f"{total:.2f}", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast"]
    if audio_inputs:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    video = out_dir / "video.mp4"
    subprocess.run(cmd + [str(video)], check=True)

    thumb = out_dir / "thumbnail.jpg"
    _card(script.thumbnail_text, cfg, out_dir / "thumb.png")
    Image.open(out_dir / "thumb.png").convert("RGB").resize((720, 1280)).save(thumb, quality=90)
    return video, thumb, total
