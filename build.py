#!/usr/bin/env python3
"""
Build script for Mandarin tone-contrast flashcards.

Resolves each (syllable, tone, speaker) -> Tone Perfect item ID, downloads the
MP3 to audio/, and rewrites the flashcardData block in index.html.

Idempotent: skips downloads for files that already exist.

Usage: python3 build.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO_DIR = ROOT / "audio"
INDEX_HTML = ROOT / "index.html"
TONE_PERFECT_BASE = "https://tone.lib.msu.edu"
SPEAKERS = ("FV1", "MV1")
HEADERS = {"User-Agent": "Mozilla/5.0 (mandapanda flashcard builder)"}

# (id, base_char, base_pinyin, base_syl, base_tone, base_meaning,
#      contrast_char, contrast_pinyin, contrast_syl, contrast_tone, contrast_meaning)
PAIRS = [
    (1,  "我", "wǒ",   "wo", 3, "I, me",            "卧", "wò",   "wo", 4, "to lie down"),
    (2,  "你", "nǐ",   "ni", 3, "you",              "泥", "ní",   "ni", 2, "mud"),
    (3,  "他", "tā",   "ta", 1, "he / she",         "踏", "tà",   "ta", 4, "to step on"),
    (4,  "是", "shì",  "shi",4, "to be, yes",       "十", "shí",  "shi",2, "ten"),
    (5,  "不", "bù",   "bu", 4, "no, not",          "补", "bǔ",   "bu", 3, "to mend"),
    (6,  "大", "dà",   "da", 4, "big",              "打", "dǎ",   "da", 3, "to hit"),
    (7,  "好", "hǎo",  "hao",3, "good",             "号", "hào",  "hao",4, "number, date"),
    (8,  "很", "hěn",  "hen",3, "very",             "恨", "hèn",  "hen",4, "to hate"),
    (9,  "小", "xiǎo", "xiao",3,"small",            "笑", "xiào", "xiao",4,"to laugh, smile"),
    (10, "人", "rén",  "ren",2, "person",           "忍", "rěn",  "ren",3, "to endure"),
    (11, "有", "yǒu",  "you",3, "to have",          "油", "yóu",  "you",2, "oil"),
    (12, "来", "lái",  "lai",2, "to come",          "赖", "lài",  "lai",4, "to rely on"),
    (13, "去", "qù",   "qu", 4, "to go",            "取", "qǔ",   "qu", 3, "to take, get"),
    (14, "看", "kàn",  "kan",4, "to look",          "砍", "kǎn",  "kan",3, "to chop"),
    (15, "说", "shuō", "shuo",1,"to speak",         "烁", "shuò", "shuo",4,"bright, shining"),
    (16, "吃", "chī",  "chi",1, "to eat",           "尺", "chǐ",  "chi",3, "a ruler"),
    (17, "喝", "hē",   "he", 1, "to drink",         "和", "hé",   "he", 2, "and, with"),
    (18, "在", "zài",  "zai",4, "at, in, on",       "灾", "zāi",  "zai",1, "disaster"),
    (19, "这", "zhè",  "zhe",4, "this",             "者", "zhě",  "zhe",3, "one who (suffix)"),
    (20, "那", "nà",   "na", 4, "that",             "拿", "ná",   "na", 2, "to hold, take"),
    (21, "钱", "qián", "qian",2,"money",            "千", "qiān", "qian",1,"thousand"),
    (22, "学", "xué",  "xue",2, "to study",         "雪", "xuě",  "xue",3, "snow"),
    (23, "名", "míng", "ming",2,"name",             "命", "mìng", "ming",4,"life, fate"),
    (24, "叫", "jiào", "jiao",4,"to be called",     "教", "jiāo", "jiao",1,"to teach"),
    (25, "想", "xiǎng","xiang",3,"to want, think",  "像", "xiàng","xiang",4,"image, resemblance"),
    (26, "买", "mǎi",  "mai",3, "to buy",           "卖", "mài",  "mai",4, "to sell"),
    (27, "中", "zhōng","zhong",1,"middle",          "重", "zhòng","zhong",4,"heavy"),
    (28, "高", "gāo",  "gao",1, "tall, high",       "告", "gào",  "gao",4, "to tell"),
    (29, "水", "shuǐ", "shui",3,"water",            "睡", "shuì", "shui",4,"to sleep"),
    (30, "点", "diǎn", "dian",3,"point, dot",       "电", "diàn", "dian",4,"electricity"),
    (31, "开", "kāi",  "kai",1, "to open",          "凯", "kǎi",  "kai",3, "triumphant"),
    (32, "新", "xīn",  "xin",1, "new",              "信", "xìn",  "xin",4, "letter, trust"),
    (33, "今", "jīn",  "jin",1, "today",            "进", "jìn",  "jin",4, "to enter"),
    (34, "年", "nián", "nian",2,"year",             "念", "niàn", "nian",4,"to read aloud"),
    (35, "会", "huì",  "hui",4, "can, will",        "回", "huí",  "hui",2, "to return"),
    (36, "要", "yào",  "yao",4, "to want, need",    "腰", "yāo",  "yao",1, "waist"),
    (37, "对", "duì",  "dui",4, "correct",          "堆", "duī",  "dui",1, "a pile"),
    (38, "谢", "xiè",  "xie",4, "to thank",         "些", "xiē",  "xie",1, "some, a few"),
    (39, "走", "zǒu",  "zou",3, "to walk",          "奏", "zòu",  "zou",4, "to play (music)"),
    (40, "常", "cháng","chang",2,"often",           "唱", "chàng","chang",4,"to sing"),
    (41, "还", "hái",  "hai",2, "still, yet",       "害", "hài",  "hai",4, "harm, damage"),
    (42, "等", "děng", "deng",3,"to wait",          "灯", "dēng", "deng",1,"lamp"),
    (43, "听", "tīng", "ting",1,"to listen",        "停", "tíng", "ting",2,"to stop"),
    (44, "真", "zhēn", "zhen",1,"real, true",       "阵", "zhèn", "zhen",4,"a burst, period"),
    (45, "都", "dōu",  "dou",1, "all",              "豆", "dòu",  "dou",4, "bean"),
    (46, "从", "cóng", "cong",2,"from",             "聪", "cōng", "cong",1,"intelligent"),
    (47, "几", "jǐ",   "ji", 3, "how many",         "鸡", "jī",   "ji", 1, "chicken"),
    (48, "用", "yòng", "yong",4,"to use",           "永", "yǒng", "yong",3,"forever"),
    (49, "问", "wèn",  "wen",4, "to ask",           "文", "wén",  "wen",2, "language, culture"),
    (50, "喜", "xǐ",   "xi", 3, "to like",          "西", "xī",   "xi", 1, "west"),
    (51, "一", "yī",   "yi", 1, "one",              "已", "yǐ",   "yi", 3, "already"),
    (52, "上", "shàng","shang",4,"up, on, above",   "商", "shāng","shang",1,"commerce"),
    (53, "下", "xià",  "xia",4, "down, below",      "虾", "xiā",  "xia",1, "shrimp"),
    (54, "个", "gè",   "ge", 4, "(measure word)",   "哥", "gē",   "ge", 1, "older brother"),
    (55, "国", "guó",  "guo",2, "country",          "果", "guǒ",  "guo",3, "fruit"),
    (56, "也", "yě",   "ye", 3, "also",             "夜", "yè",   "ye", 4, "night"),
    (57, "后", "hòu",  "hou",4, "after, behind",    "猴", "hóu",  "hou",2, "monkey"),
    (58, "把", "bǎ",   "ba", 3, "to hold, handle",  "八", "bā",   "ba", 1, "eight"),
    (59, "做", "zuò",  "zuo",4, "to do, make",      "昨", "zuó",  "zuo",2, "yesterday"),
    (60, "时", "shí",  "shi",2, "time",             "史", "shǐ",  "shi",3, "history"),
    (61, "多", "duō",  "duo",1, "many, much",       "朵", "duǒ",  "duo",3, "(measure for flowers)"),
    (62, "少", "shǎo", "shao",3,"few, little",      "烧", "shāo", "shao",1,"to burn"),
    (63, "出", "chū",  "chu",1, "to go out",        "处", "chù",  "chu",4, "place"),
    (64, "天", "tiān", "tian",1,"day, sky",         "田", "tián", "tian",2,"field"),
    (65, "早", "zǎo",  "zao",3, "early",            "造", "zào",  "zao",4, "to make, create"),
]

ID_LINE_RE = re.compile(
    r"href='/tone/(\d+)'[^>]*>[^<]*</a><br/>\s*by\s+(Female|Male)\s+Voice\s+(\d)"
)


def http_get(url: str, retries: int = 3) -> bytes:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed after {retries} attempts: {url} ({last_err})")


def speaker_code(gender: str, voice_num: str) -> str:
    return f"{'F' if gender == 'Female' else 'M'}V{voice_num}"


def resolve_ids(syllable: str, tone: int) -> dict[str, int]:
    """Return {speaker_code: tone_id} for the 6 speakers of a given syllable+tone."""
    qs = urllib.parse.urlencode(
        [("fq", f"custom.sound:{syllable}"), ("fq", f"custom.tone:{tone}")]
    )
    html = http_get(f"{TONE_PERFECT_BASE}/search?{qs}").decode("utf-8", errors="ignore")
    out: dict[str, int] = {}
    for tone_id, gender, voice_num in ID_LINE_RE.findall(html):
        out[speaker_code(gender, voice_num)] = int(tone_id)
    return out


def download_mp3(tone_id: int, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        return  # already downloaded
    data = http_get(f"{TONE_PERFECT_BASE}/tone/{tone_id}/PROXY_MP3/download")
    if len(data) < 1000:
        raise RuntimeError(f"suspiciously small mp3 ({len(data)}B) for id {tone_id}")
    dest.write_bytes(data)


def fetch_one(syllable: str, tone: int) -> dict[str, str]:
    """Resolve and download FV1+MV1 for a (syl, tone). Returns {speaker: filename}."""
    AUDIO_DIR.mkdir(exist_ok=True)
    needed = {sp: AUDIO_DIR / f"{syllable}{tone}_{sp}.mp3" for sp in SPEAKERS}
    if all(p.exists() and p.stat().st_size > 1000 for p in needed.values()):
        return {sp: f"audio/{p.name}" for sp, p in needed.items()}

    ids = resolve_ids(syllable, tone)
    missing = [sp for sp in SPEAKERS if sp not in ids]
    if missing:
        raise RuntimeError(f"speakers {missing} not found for {syllable}{tone}; got {list(ids)}")

    for sp in SPEAKERS:
        download_mp3(ids[sp], needed[sp])
    return {sp: f"audio/{needed[sp].name}" for sp in SPEAKERS}


def build_flashcard_data() -> list[dict]:
    # Collect unique (syl, tone) combos
    combos: set[tuple[str, int]] = set()
    for row in PAIRS:
        combos.add((row[3], row[4]))    # base
        combos.add((row[8], row[9]))    # contrast

    print(f"Resolving {len(combos)} unique syllable-tone combos "
          f"({len(combos) * len(SPEAKERS)} mp3 files)...", file=sys.stderr)

    paths: dict[tuple[str, int], dict[str, str]] = {}
    errors: list[tuple[tuple[str, int], str]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_one, s, t): (s, t) for (s, t) in combos}
        for i, fut in enumerate(as_completed(futures), 1):
            combo = futures[fut]
            try:
                paths[combo] = fut.result()
                print(f"  [{i}/{len(combos)}] {combo[0]}{combo[1]} ✓", file=sys.stderr)
            except Exception as e:
                errors.append((combo, str(e)))
                print(f"  [{i}/{len(combos)}] {combo[0]}{combo[1]} ✗ {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} failures:", file=sys.stderr)
        for combo, msg in errors:
            print(f"  {combo[0]}{combo[1]}: {msg}", file=sys.stderr)
        sys.exit(1)

    cards = []
    for (cid, b_ch, b_py, b_syl, b_tn, b_mn,
         c_ch, c_py, c_syl, c_tn, c_mn) in PAIRS:
        b = paths[(b_syl, b_tn)]
        c = paths[(c_syl, c_tn)]
        cards.append({
            "id": cid,
            "charBase": b_ch, "pinyinBase": b_py, "meaningBase": b_mn, "toneBase": b_tn,
            "audioBase1": b["FV1"], "audioBase2": b["MV1"],
            "charContrast": c_ch, "pinyinContrast": c_py, "meaningContrast": c_mn, "toneContrast": c_tn,
            "audioContrast1": c["FV1"], "audioContrast2": c["MV1"],
        })
    return cards


DATA_BLOCK_RE = re.compile(
    r"const flashcardData = \[.*?\];\s*\n",
    re.DOTALL,
)


def patch_index_html(cards: list[dict]) -> None:
    js_array = "const flashcardData = " + json.dumps(cards, ensure_ascii=False, indent=4) + ";\n"
    html = INDEX_HTML.read_text(encoding="utf-8")
    new_html, n = DATA_BLOCK_RE.subn(js_array, html, count=1)
    if n != 1:
        raise RuntimeError("could not find flashcardData block in index.html")
    INDEX_HTML.write_text(new_html, encoding="utf-8")
    print(f"Wrote {len(cards)} cards into {INDEX_HTML.name}", file=sys.stderr)


if __name__ == "__main__":
    cards = build_flashcard_data()
    patch_index_html(cards)
    print(f"\nDone. {len(cards)} pairs, {len(list(AUDIO_DIR.glob('*.mp3')))} mp3 files in audio/.",
          file=sys.stderr)
