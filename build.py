#!/usr/bin/env python3
"""
Build script for Mandarin tone-contrast flashcards.

For each (syllable, tone, speaker) in PAIRS: resolves to a Tone Perfect item ID
and downloads the MP3 to audio/.

For each phrase in PHRASES: downloads the Tatoeba audio to audio/phrases/.

Then rewrites the flashcardData and phraseData blocks in index.html.

Idempotent: skips downloads for files that already exist.

Usage: python3 build.py
"""
import json
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
PHRASE_AUDIO_DIR = AUDIO_DIR / "phrases"
INDEX_HTML = ROOT / "index.html"
TONE_PERFECT_BASE = "https://tone.lib.msu.edu"
TATOEBA_AUDIO_BASE = "https://tatoeba.org/en/audio/download"
SPEAKERS = ("FV1", "MV1")
HEADERS = {"User-Agent": "Mozilla/5.0 (tonely flashcard builder)"}

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


# =============================================================================
# Phrases — sourced from Tatoeba (CC BY 2.0 FR). Each entry has:
#   tatoeba_audio_id : ID for the audio download URL
#   text             : Mandarin sentence (Simplified)
#   pinyin           : citation-form pinyin (no sandhi marking)
#   meaning          : English gloss
# =============================================================================
PHRASES = [
    (25746,   "你在听我说吗？",                  "Nǐ zài tīng wǒ shuō ma?",                       "Are you listening to me?"),
    (26040,   "今天天气很好。",                  "Jīntiān tiānqì hěn hǎo.",                       "The weather is nice today."),
    (1280206, "我今天想早睡。",                  "Wǒ jīntiān xiǎng zǎo shuì.",                    "I want to sleep early today."),
    (1279628, "我每天都吃水果。",                "Wǒ měitiān dōu chī shuǐguǒ.",                   "I eat fruit every day."),
    (1277915, "要不要一起去？",                  "Yào bú yào yīqǐ qù?",                           "Want to go together?"),
    (25745,   "我想看看。",                      "Wǒ xiǎng kàn kan.",                             "I want to take a look."),
    (25537,   "我什么都不想喝。",                "Wǒ shénme dōu bù xiǎng hē.",                    "I don't want to drink anything."),
    (25858,   "我不想等那么久。",                "Wǒ bù xiǎng děng nàme jiǔ.",                    "I don't want to wait that long."),
    (25900,   "我能问一些问题吗？",              "Wǒ néng wèn yīxiē wèntí ma?",                   "Can I ask some questions?"),
    (26450,   "我已经吃饱了，谢谢。",            "Wǒ yǐjīng chī bǎo le, xièxie.",                 "I'm already full, thank you."),
    (26986,   "我今天感觉好多了。",              "Wǒ jīntiān gǎnjué hǎoduō le.",                  "I feel much better today."),
    (26557,   "他和我一样高。",                  "Tā hé wǒ yīyàng gāo.",                          "He's as tall as me."),
    (26798,   "我买不起那个。",                  "Wǒ mǎi bù qǐ nàge.",                            "I can't afford that."),
    (27398,   "我去不了，也不想去。",            "Wǒ qù bù liǎo, yě bù xiǎng qù.",                "I can't go, and I don't want to."),
    (25499,   "你想走的时候就走吧。",            "Nǐ xiǎng zǒu de shíhou jiù zǒu ba.",            "Leave whenever you want."),
    (26702,   "我想看这部电影。",                "Wǒ xiǎng kàn zhè bù diànyǐng.",                 "I want to watch this movie."),
    (26300,   "我们早点走不是更好吗？",          "Wǒmen zǎo diǎn zǒu bú shì gèng hǎo ma?",        "Wouldn't it be better to leave earlier?"),
    (25775,   "你更喜欢哪个，这个还是那个？",    "Nǐ gèng xǐhuan nǎge, zhège háishì nàge?",       "Which do you prefer, this one or that one?"),
    (1280930, "他不是我的男朋友，他是我的哥哥。", "Tā bú shì wǒ de nán péngyou, tā shì wǒ de gēge.","He's not my boyfriend, he's my older brother."),
    (27402,   "一个是新的，另一个是旧的。",      "Yīge shì xīn de, lìng yīge shì jiù de.",        "One is new, the other is old."),
    (25445,   "等她回来的时候问问她。",          "Děng tā huílái de shíhou wèn wen tā.",          "Ask her when she comes back."),
    (26095,   "他半夜打了个电话给我。",          "Tā bànyè dǎ le ge diànhuà gěi wǒ.",             "He called me in the middle of the night."),
    (26612,   "你回来之前我已经走了。",          "Nǐ huílái zhīqián wǒ yǐjīng zǒu le.",           "I'd already left before you came back."),
    (25816,   "他很快就会回来的。",              "Tā hěn kuài jiù huì huílái de.",                "He'll be back soon."),
    (1281126, "我们明天早上九点见好吗？",        "Wǒmen míngtiān zǎoshang jiǔ diǎn jiàn hǎo ma?", "Shall we meet at 9 tomorrow morning?"),
    (992955,  "我今天不想起床。",                "Wǒ jīntiān bù xiǎng qǐchuáng.",                 "I don't want to get up today."),
    (1281062, "我只想和你在一起。",              "Wǒ zhǐ xiǎng hé nǐ zài yīqǐ.",                  "I just want to be with you."),
    (1281091, "你昨天上午在打网球吗？",          "Nǐ zuótiān shàngwǔ zài dǎ wǎngqiú ma?",         "Were you playing tennis yesterday morning?"),
    (27535,   "我在想你今天会不会来。",          "Wǒ zài xiǎng nǐ jīntiān huì bú huì lái.",       "I was wondering if you'd come today."),
    (1278056, "今天要不要去我家看看？",          "Jīntiān yào bú yào qù wǒ jiā kàn kan?",         "Want to come see my house today?"),
    (26785,   "我等我的一个朋友等了一小时。",    "Wǒ děng wǒ de yī ge péngyou děng le yī xiǎoshí.","I waited for a friend for an hour."),
    (25519,   "你走了，我们都会想你的。",        "Nǐ zǒu le, wǒmen dōu huì xiǎng nǐ de.",         "When you leave, we'll all miss you."),
    (26068,   "如果我是你，我也会这么做。",      "Rúguǒ wǒ shì nǐ, wǒ yě huì zhème zuò.",         "If I were you, I'd do the same."),
    (25931,   "我们在下个加油站停一下。",        "Wǒmen zài xià ge jiāyóuzhàn tíng yīxià.",       "Let's stop at the next gas station."),
    (25416,   "雨不停，我们不会出去。",          "Yǔ bù tíng, wǒmen bú huì chū qù.",              "The rain won't stop, so we won't go out."),
    (26911,   "这看上去像个蛋。",                "Zhè kàn shàngqù xiàng ge dàn.",                 "This looks like an egg."),
    (25839,   "你现在好点了吗？",                "Nǐ xiànzài hǎo diǎn le ma?",                    "Are you feeling better now?"),
    (26936,   "不要把门开着。",                  "Bú yào bǎ mén kāi zhe.",                        "Don't leave the door open."),
    (26082,   "你是我的一切。",                  "Nǐ shì wǒ de yīqiè.",                           "You are my everything."),
    (26348,   "这是你的信。",                    "Zhè shì nǐ de xìn.",                            "This is your letter."),
]


def download_phrase(audio_id: int, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        return
    data = http_get(f"{TATOEBA_AUDIO_BASE}/{audio_id}")
    if len(data) < 1000:
        raise RuntimeError(f"suspiciously small mp3 ({len(data)}B) for audio_id {audio_id}")
    dest.write_bytes(data)


# Spotify playlist ID for the Songs tab. Just the ID, not the full URL.
# To swap: paste a new playlist URL, take the bit between /playlist/ and the ?
SPOTIFY_PLAYLIST_ID = "6TZP72K8V8hrcSMWbz7LGw"


# =============================================================================
# Stories — chengyu (Chinese idiom origin tales). Each is broken into sentences
# so the UI can show character/pinyin/English aligned per sentence. The audio
# is a YouTube embed (privacy-enhanced via youtube-nocookie.com).
# =============================================================================
STORIES = [
    {
        "id": 1,
        "title_han":    "守株待兔",
        "title_pinyin": "Shǒu zhū dài tù",
        "title_en":     "Waiting by the Stump",
        "youtube_id":   "FVUgXgIEnSo",
        "youtube_label":"LingoAce · animated story",
        "body": [
            {"han": "很久很久以前，有一个农夫在田里种地。",
             "pinyin": "Hěn jiǔ hěn jiǔ yǐ qián yǒu yí gè nóng fū zài tián lǐ zhòng dì",
             "en": "Long, long ago, a farmer was working in his field."},
            {"han": "天特别热，他不停地擦着头上的汗珠。",
             "pinyin": "Tiān tè bié rè tā bù tíng dì cā zhe tóu shàng de hàn zhū",
             "en": "The day was very hot — he kept wiping the sweat from his brow."},
            {"han": "\"种田真是太辛苦了！要是不种田就有东西吃，那该有多好啊。\"",
             "pinyin": "Zhòng tián zhēn shì tài xīn kǔ le yào shì bù zhòng tián jiù yǒu dōng xī chī nà gāi yǒu duō hǎo a",
             "en": "\"Farming is so exhausting. If only I could have food without farming — how nice that would be.\""},
            {"han": "突然，他往旁边一看，原来是一只兔子撞到了田边的大树上，一动不动。",
             "pinyin": "Tū rán tā wǎng páng biān yī kàn yuán lái shì yī zhī tù zi zhuàng dào le tián biān de dà shù shàng yī dòng bù dòng",
             "en": "Suddenly he looked over — a rabbit had run into the big tree beside the field, lying perfectly still."},
            {"han": "\"啊，兔子撞死了！太好了，今天有兔子肉吃了！\"",
             "pinyin": "A tù zi zhuàng sǐ le tài hǎo le jīn tiān yǒu tù zi ròu chī le",
             "en": "\"The rabbit's killed itself! Great — rabbit meat for dinner tonight!\""},
            {"han": "农夫拿着兔子回了家，一家人开开心心地吃了一顿兔子肉。",
             "pinyin": "Nóng fū ná zhe tù zi huí le jiā yī jiā rén kāi kāi xīn xīn dì chī le yī dùn tù zi ròu",
             "en": "He took the rabbit home, and the family happily ate it together."},
            {"han": "农夫想：今天有一只兔子撞死了，说不定明天也有兔子撞死。那我就不用种田了，只要在那棵大树下等兔子就可以了。",
             "pinyin": "Nóng fū xiǎng jīn tiān yǒu yī zhī tù zi zhuàng sǐ le shuō bù dìng míng tiān yě yǒu tù zi zhuàng sǐ nà wǒ jiù bù yòng zhòng tián le zhǐ yào zài nà kē dà shù xià děng tù zi jiù kě yǐ le",
             "en": "He thought: \"A rabbit died today — maybe another will die tomorrow. Then I won't need to farm — I'll just wait under that tree for rabbits.\""},
            {"han": "第二天，农夫一大早就来到田里，坐在树下开始等兔子。",
             "pinyin": "Dì èr tiān nóng fū yī dà zǎo jiù lái dào tián lǐ zuò zài shù xià kāi shǐ děng tù zi",
             "en": "The next day, he came to the field at dawn and sat under the tree, waiting."},
            {"han": "他等啊等啊，一直等到太阳落山，也没有等到一只兔子。",
             "pinyin": "Tā děng a děng a yì zhí děng dào tài yáng luò shān yě méi yǒu děng dào yī zhī tù zi",
             "en": "He waited and waited, until the sun set — but no rabbit came."},
            {"han": "就这样等了一个星期，还是没有等到。",
             "pinyin": "Jiù zhè yàng děng le yí gè xīng qī hái shì méi yǒu děng dào",
             "en": "He waited like this for a whole week. Still nothing."},
            {"han": "旁边的邻居看他的田里长满了杂草，就问他：\"你怎么不锄草啊？再这样下去，你今年就收不到粮食了。\"",
             "pinyin": "Páng biān de lín jū kàn tā de tián lǐ zhǎng mǎn le zá cǎo jiù wèn tā nǐ zěn me bù chú cǎo a zài zhè yàng xià qù nǐ jīn nián jiù shōu bú dào liáng shí le",
             "en": "His neighbor saw the field overgrown with weeds and asked: \"Why aren't you weeding? At this rate, you'll have no harvest this year.\""},
            {"han": "\"没事，我不用锄草，也不用收粮食。会有兔子来撞死，我可以吃兔子肉。\"",
             "pinyin": "Méi shì wǒ bù yòng chú cǎo yě bù yòng shōu liáng shí huì yǒu tù zi lái zhuàng sǐ wǒ kě yǐ chī tù zi ròu",
             "en": "\"Don't worry — I don't need to weed or harvest. Rabbits will come and kill themselves, and I'll have rabbit meat.\""},
            {"han": "邻居听了哈哈大笑，摇摇头就走了。",
             "pinyin": "Lín jū tīng le hā hā dà xiào yáo yáo tóu jiù zǒu le",
             "en": "The neighbor burst out laughing, shook his head, and walked away."},
        ],
        "moral": {"han": "不要把偶然当作必然，不要靠运气过日子。",
                  "pinyin": "Bú yào bǎ ǒu rán dàng zuò bì rán bú yào kào yùn qì guò rì zi",
                  "en": "Don't mistake a fluke for a sure thing — don't live by luck."},
    },
    {
        "id": 2,
        "title_han":    "画蛇添足",
        "title_pinyin": "Huà shé tiān zú",
        "title_en":     "Drawing Legs on a Snake",
        "youtube_id":   "Ll-n4rHfOyo",
        "youtube_label":"LingoAce · animated story",
        "body": [
            {"han": "很久以前，有一户人家请了三个人帮忙做事。",
             "pinyin": "Hěn jiǔ yǐ qián yǒu yī hù rén jiā qǐng le sān gè rén bāng máng zuò shì",
             "en": "Long ago, a household hired three men to help with some work."},
            {"han": "主人看到帮忙的人特别累，就拿出一壶好酒给他们喝。",
             "pinyin": "Zhǔ rén kàn dào bāng máng de rén tè bié lèi jiù ná chū yī hú hǎo jiǔ gěi tā men hē",
             "en": "Seeing how tired the workers were, the host brought out a jug of good wine for them."},
            {"han": "他们看着小小的一壶酒皱起了眉头：\"这壶酒根本不够分给我们三个人啊。\"",
             "pinyin": "Tā men kàn zhe xiǎo xiǎo de yī hú jiǔ zhòu qǐ le méi tóu zhè hú jiǔ gēn běn bù gòu fēn gěi wǒ men sān gè rén a",
             "en": "They frowned at the small jug: \"This isn't nearly enough for the three of us.\""},
            {"han": "\"三个人一起喝都不痛快，还不如就给一个人。那这壶酒给谁呢？\"",
             "pinyin": "Sān gè rén yì qǐ hē dōu bù tòng kuài hái bù rú jiù gěi yí gè rén nà zhè hú jiǔ gěi shuí ne",
             "en": "\"Splitting it three ways isn't satisfying — better one person take it all. But who gets the wine?\""},
            {"han": "\"我们比赛画蛇，谁先把蛇画好，这壶酒就给谁喝，怎么样？\"",
             "pinyin": "Wǒ men bǐ sài huà shé shuí xiān bǎ shé huà hǎo zhè hú jiǔ jiù gěi shuí hē zěn me yàng",
             "en": "\"Let's race to draw a snake — whoever finishes first drinks the wine. How about that?\""},
            {"han": "三个人来到院子里开始画蛇。",
             "pinyin": "Sān gè rén lái dào yuàn zi lǐ kāi shǐ huà shé",
             "en": "The three went out to the yard and started drawing snakes."},
            {"han": "有一个人很快就画好了，他得意地拿起酒：\"他们画得好慢，我还有时间让自己的蛇更漂亮。那我就来给蛇画脚吧。\"",
             "pinyin": "Yǒu yí gè rén hěn kuài jiù huà hǎo le tā dé yì dì ná qǐ jiǔ tā men huà dé hǎo màn wǒ hái yǒu shí jiān ràng zì jǐ de shé gèng piào liàng nà wǒ jiù lái gěi shé huà jiǎo ba",
             "en": "One man finished quickly. Smugly picking up the wine, he said: \"They're so slow — I have time to make my snake even better. I'll add some feet.\""},
            {"han": "那个人拿着酒壶，就开始在自己画好的蛇上添了几只脚。",
             "pinyin": "Nà ge rén ná zhe jiǔ hú jiù kāi shǐ zài zì jǐ huà hǎo de shé shàng tiān le jǐ zhī jiǎo",
             "en": "Holding the wine jug, he started adding feet to his finished snake."},
            {"han": "他画到第四只脚的时候，另一个人也画好了：\"把酒给我，我是第一个画好的。\"",
             "pinyin": "Tā huà dào dì sì zhǐ jiǎo de shí hòu lìng yí gè rén yě huà hǎo le bǎ jiǔ gěi wǒ wǒ shì dì yí gè huà hǎo de",
             "en": "Just as he was drawing the fourth foot, another finished. \"Give me the wine — I was the first to finish.\""},
            {"han": "\"你胡说！明明我是第一个画好的，你看我还有时间给它画脚呢。\"",
             "pinyin": "Nǐ hú shuō míng míng wǒ shì dì yí gè huà hǎo de nǐ kàn wǒ hái yǒu shí jiān gěi tā huà jiǎo ne",
             "en": "\"Nonsense! I clearly finished first — see, I had time to add feet.\""},
            {"han": "\"蛇有脚吗？你这画的根本不是蛇。我们是比赛画蛇，你输了。\"",
             "pinyin": "Shé yǒu jiǎo ma nǐ zhè huà de gēn běn bú shì shé wǒ men shì bǐ sài huà shé nǐ shū le",
             "en": "\"Does a snake have feet? What you've drawn isn't a snake at all. We were racing to draw a snake — you lose.\""},
            {"han": "第二个人拿起酒，开心地喝了起来。",
             "pinyin": "Dì èr gè rén ná qǐ jiǔ kāi xīn dì hē le qǐ lái",
             "en": "The second man picked up the wine and drank happily."},
            {"han": "第一个人就只能叹着气，望着自己画的四脚蛇。",
             "pinyin": "Dì yí gè rén jiù zhǐ néng tàn zhe qì wàng zhe zì jǐ huà de sì jiǎo shé",
             "en": "The first could only sigh, staring at his four-legged \"snake.\""},
        ],
        "moral": {"han": "做事过头，反而把好事变成坏事。",
                  "pinyin": "Zuò shì guò tóu fǎn ér bǎ hǎo shì biàn chéng huài shì",
                  "en": "Overdoing something turns a win into a loss — gilding the lily."},
    },
    {
        "id": 3,
        "title_han":    "亡羊补牢",
        "title_pinyin": "Wáng yáng bǔ láo",
        "title_en":     "Mending the Pen After the Sheep Are Gone",
        "youtube_id":   "jAx04A2X1ag",
        "youtube_label":"LingoAce · animated story",
        "body": [
            {"han": "很久很久以前，有个人养了一群羊。",
             "pinyin": "Hěn jiǔ hěn jiǔ yǐ qián yǒu gè rén yǎng le yī qún yáng",
             "en": "Long, long ago, there was a man who kept a flock of sheep."},
            {"han": "有一天早晨，养羊人来到院子里看羊：\"一，二，三，四，五……诶，我怎么少了一只羊啊？\"",
             "pinyin": "Yǒu yī tiān zǎo chén yǎng yáng rén lái dào yuàn zi lǐ kàn yáng yī èr sān sì wǔ éi wǒ zěn me shǎo le yī zhī yáng a",
             "en": "One morning, the sheep keeper came to the yard to count: \"One, two, three, four, five… wait, I'm missing one!\""},
            {"han": "羊圈破了一个洞。一定是狼夜里钻进来，把羊叼走了。",
             "pinyin": "Yáng juàn pò le yí gè dòng yí dìng shì láng yè lǐ zuān jìn lái bǎ yáng diāo zǒu le",
             "en": "There was a hole in the pen. \"A wolf must have slipped in last night and carried one off.\""},
            {"han": "\"哎呀，我怎么这么倒霉啊！\"",
             "pinyin": "Āi yā wǒ zěn me zhè me dǎo méi a",
             "en": "\"Oh no, why am I so unlucky!\""},
            {"han": "邻居说：\"快把羊圈修一修，把洞补上吧。\"",
             "pinyin": "Lín jū shuō kuài bǎ yáng juàn xiū yī xiū bǎ dòng bǔ shàng ba",
             "en": "His neighbor said: \"Hurry — fix the pen and patch the hole.\""},
            {"han": "\"羊已经丢了，还修羊圈做什么。\"",
             "pinyin": "Yáng yǐ jīng diū le hái xiū yáng juàn zuò shén me",
             "en": "\"The sheep is already gone — what's the point of fixing the pen?\""},
            {"han": "第二天早上，这个人又发现少了一只羊：\"一，二，三，四……啊，我又丢了一只羊！\"",
             "pinyin": "Dì èr tiān zǎo shàng zhè ge rén yòu fā xiàn shǎo le yī zhī yáng yī èr sān sì a wǒ yòu diū le yī zhī yáng",
             "en": "The next morning, he found another sheep missing: \"One, two, three, four… ah, I've lost another!\""},
            {"han": "邻居说：\"现在修羊圈还来得及，这样狼就不会来了。\"",
             "pinyin": "Lín jū shuō xiàn zài xiū yáng juàn hái lái de jí zhè yàng láng jiù bú huì lái le",
             "en": "His neighbor said: \"It's still not too late to fix the pen — then the wolf can't come back.\""},
            {"han": "\"我现在就修。哎呀，真后悔没有听你的话。\"",
             "pinyin": "Wǒ xiàn zài jiù xiū āi yā zhēn hòu huǐ méi yǒu tīng nǐ de huà",
             "en": "\"I'll fix it right now. Oh, I really regret not listening to you.\""},
            {"han": "养羊人赶紧把羊圈补好了。从那以后，再也没丢过羊了。",
             "pinyin": "Yǎng yáng rén gǎn jǐn bǎ yáng juàn bǔ hǎo le cóng nà yǐ hòu zài yě méi diū guò yáng le",
             "en": "The sheep keeper quickly mended the pen. From then on, no more sheep were lost."},
        ],
        "moral": {"han": "知道错了就改，永远不晚。",
                  "pinyin": "Zhī dào cuò le jiù gǎi yǒng yuǎn bù wǎn",
                  "en": "When you realize a mistake, fix it. It's never too late."},
    },
    {
        "id": 4,
        "title_han":    "塞翁失马",
        "title_pinyin": "Sài wēng shī mǎ",
        "title_en":     "The Old Man and the Lost Horse",
        "youtube_id":   "3kWLqOmIFFM",
        "youtube_label":"LingoAce · animated story",
        "body": [
            {"han": "在边塞地区，有一位被人们称为塞翁的老人。",
             "pinyin": "Zài biān sài dì qū yǒu yī wèi bèi rén men chēng wéi sāi wēng de lǎo rén",
             "en": "In the frontier region lived an old man whom everyone called Saiweng (\"the Old Man at the Border\")."},
            {"han": "他的生活充满了智慧和哲理。",
             "pinyin": "Tā de shēng huó chōng mǎn le zhì huì hé zhé lǐ",
             "en": "His life was full of wisdom and quiet philosophy."},
            {"han": "一天，塞翁家的马不知何故，越过边界，跑到了胡人的地方。",
             "pinyin": "Yī tiān sāi wēng jiā de mǎ bù zhī hé gù yuè guò biān jiè pǎo dào le hú rén de dì fāng",
             "en": "One day, for no apparent reason, his horse crossed the border and ran off into the territory of the Hu people."},
            {"han": "邻居们听说后，都来安慰塞翁，但他却不以为然，反而说：\"这怎么就不能是一件好事呢？\"",
             "pinyin": "Lín jū men tīng shuō hòu dōu lái ān wèi sāi wēng dàn tā què bù yǐ wéi rán fǎn ér shuō zhè zěn me jiù bù néng shì yī jiàn hǎo shì ne",
             "en": "When his neighbors came to console him, he was unbothered — and even said: \"How do we know this isn't a good thing?\""},
            {"han": "几个月后，那匹马不仅自己回来了，还带回了一匹胡人的骏马。",
             "pinyin": "Jǐ gè yuè hòu nà pǐ mǎ bù jǐn zì jǐ huí lái le hái dài huí le yì pǐ hú rén de jùn mǎ",
             "en": "A few months later, the horse came back on its own — and brought a fine Hu horse with it."},
            {"han": "邻居们纷纷来祝贺塞翁，但塞翁却说：\"这为什么就不能是一件坏事呢？\"",
             "pinyin": "Lín jū men fēn fēn lái zhù hè sāi wēng dàn sāi wēng què shuō zhè wèi shén me jiù bù néng shì yī jiàn huài shì ne",
             "en": "Neighbors came to congratulate him. But Saiweng said: \"How do we know this isn't a bad thing?\""},
            {"han": "因为他知道，好事和坏事有时候是难以预料的。",
             "pinyin": "Yīn wèi tā zhī dào hǎo shì hé huài shì yǒu shí hòu shì nán yǐ yù liào de",
             "en": "He knew that good fortune and bad are often hard to predict."},
            {"han": "不久，塞翁的儿子因为喜欢骑马，结果从马上摔下来，跌断了大腿。",
             "pinyin": "Bù jiǔ sāi wēng de ér zi yīn wèi xǐ huān qí mǎ jié guǒ cóng mǎ shàng shuāi xià lái diē duàn le dà tuǐ",
             "en": "Soon, his son, who loved riding, was thrown from the new horse and broke his leg."},
            {"han": "邻居们又来安慰塞翁，但塞翁依然保持平和的心态：\"这怎么就不能是一件好事呢？\"",
             "pinyin": "Lín jū men yòu lái ān wèi sāi wēng dàn sāi wēng yī rán bǎo chí píng hé de xīn tài zhè zěn me jiù bù néng shì yī jiàn hǎo shì ne",
             "en": "Again the neighbors came to console him, but Saiweng remained calm: \"How do we know this isn't a good thing?\""},
            {"han": "过了一年，胡人大举入侵边境，许多壮年男子都拿起武器去参加战斗，许多人都在战斗中牺牲了。",
             "pinyin": "Guò le yī nián hú rén dà jǔ rù qīn biān jìng xǔ duō zhuàng nián nán zi dōu ná qǐ wǔ qì qù cān jiā zhàn dòu xǔ duō rén dōu zài zhàn dòu zhōng xī shēng le",
             "en": "A year later, the Hu people launched a major invasion. Many young men took up arms — and many died in battle."},
            {"han": "而塞翁的儿子因为腿伤，没有被征召入伍，最终父子俩都得以保全生命。",
             "pinyin": "Ér sāi wēng de ér zi yīn wèi tuǐ shāng méi yǒu bèi zhēng zhào rù wǔ zuì zhōng fù zǐ liǎ dōu dé yǐ bǎo quán shēng mìng",
             "en": "But Saiweng's son, because of his injured leg, was not drafted — and so father and son were both spared."},
            {"han": "这个故事告诉我们，祸福相依，好事和坏事往往在一定条件下可以互相转化。",
             "pinyin": "Zhè ge gù shì gào sù wǒ men huò fú xiāng yī hǎo shì hé huài shì wǎng wǎng zài yí dìng tiáo jiàn xià kě yǐ hù xiāng zhuǎn huà",
             "en": "This story tells us: misfortune and fortune lean on each other — good and bad can often turn into one another, given the right conditions."},
        ],
        "moral": {"han": "好事坏事，常常会变。",
                  "pinyin": "Hǎo shì huài shì cháng cháng huì biàn",
                  "en": "Good fortune and bad often turn into each other."},
    },
]
# Canonical mā/má/mǎ/mà examples used by the Chart tab. Single speaker (FV1).
CHART_TONES = (
    (1, "妈", "mā", "mother"),
    (2, "麻", "má", "hemp"),
    (3, "马", "mǎ", "horse"),
    (4, "骂", "mà", "to scold"),
)


def build_chart_audio() -> list[dict]:
    """Fetch ma1..ma4 FV1 audio and return chart-tone metadata."""
    AUDIO_DIR.mkdir(exist_ok=True)
    out: list[dict] = []
    for tone, char, pinyin, meaning in CHART_TONES:
        dest = AUDIO_DIR / f"ma{tone}_FV1.mp3"
        if not (dest.exists() and dest.stat().st_size > 1000):
            ids = resolve_ids("ma", tone)
            if "FV1" not in ids:
                raise RuntimeError(f"FV1 not found for ma{tone}")
            download_mp3(ids["FV1"], dest)
            print(f"  chart ma{tone} ✓", file=sys.stderr)
        out.append({
            "tone": tone,
            "char": char,
            "pinyin": pinyin,
            "meaning": meaning,
            "audio": f"audio/{dest.name}",
        })
    return out


def build_phrase_data() -> list[dict]:
    PHRASE_AUDIO_DIR.mkdir(exist_ok=True, parents=True)
    print(f"\nFetching {len(PHRASES)} phrase audio files from Tatoeba...", file=sys.stderr)

    out: list[dict] = []
    errors: list[tuple[int, str]] = []

    def fetch(idx_audio_id: tuple[int, int]) -> tuple[int, int]:
        idx, audio_id = idx_audio_id
        dest = PHRASE_AUDIO_DIR / f"{audio_id}.mp3"
        download_phrase(audio_id, dest)
        return idx, audio_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, (i, p[0])): (i, p[0]) for i, p in enumerate(PHRASES)}
        for fut in as_completed(futures):
            i, aid = futures[fut]
            try:
                fut.result()
                print(f"  phrase {i+1}/{len(PHRASES)} (aid={aid}) ✓", file=sys.stderr)
            except Exception as e:
                errors.append((aid, str(e)))
                print(f"  phrase {i+1}/{len(PHRASES)} (aid={aid}) ✗ {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} phrase audio failures:", file=sys.stderr)
        for aid, msg in errors:
            print(f"  aid={aid}: {msg}", file=sys.stderr)
        sys.exit(1)

    for i, (audio_id, text, pinyin, meaning) in enumerate(PHRASES, start=1):
        out.append({
            "id": i,
            "text": text,
            "pinyin": pinyin,
            "meaning": meaning,
            "audio": f"audio/phrases/{audio_id}.mp3",
            "tatoeba_audio_id": audio_id,
        })
    return out


CARD_DATA_RE    = re.compile(r"const flashcardData = \[.*?\];\s*\n",         re.DOTALL)
PHRASE_DATA_RE  = re.compile(r"const phraseData = \[.*?\];\s*\n",            re.DOTALL)
CHART_DATA_RE   = re.compile(r"const chartTones = \[.*?\];\s*\n",            re.DOTALL)
STORY_DATA_RE   = re.compile(r"const storyData = \[.*?\];\s*\n",             re.DOTALL)
SPOTIFY_RE      = re.compile(r'const spotifyPlaylistId = "[^"]*";\s*\n',     re.DOTALL)


def _replace_or_insert(html: str, regex: re.Pattern, new_block: str, insert_after: re.Pattern) -> str:
    if regex.search(html):
        return regex.sub(new_block, html, count=1)
    return insert_after.sub(lambda m: m.group(0) + "\n        " + new_block, html, count=1)


def patch_index_html(cards, phrases, chart_tones, stories, spotify_id) -> None:
    blocks = {
        "cards":   ("const flashcardData = ", json.dumps(cards,       ensure_ascii=False, indent=4)),
        "phrases": ("const phraseData = ",    json.dumps(phrases,     ensure_ascii=False, indent=4)),
        "chart":   ("const chartTones = ",    json.dumps(chart_tones, ensure_ascii=False, indent=4)),
        "stories": ("const storyData = ",     json.dumps(stories,     ensure_ascii=False, indent=4)),
    }
    cards_js   = blocks["cards"][0]   + blocks["cards"][1]   + ";\n"
    phrases_js = blocks["phrases"][0] + blocks["phrases"][1] + ";\n"
    chart_js   = blocks["chart"][0]   + blocks["chart"][1]   + ";\n"
    stories_js = blocks["stories"][0] + blocks["stories"][1] + ";\n"
    spotify_js = f'const spotifyPlaylistId = "{spotify_id}";\n'

    html = INDEX_HTML.read_text(encoding="utf-8")

    html, n_cards = CARD_DATA_RE.subn(cards_js, html, count=1)
    if n_cards != 1:
        raise RuntimeError("could not find flashcardData block in index.html")

    html = _replace_or_insert(html, PHRASE_DATA_RE, phrases_js, CARD_DATA_RE)
    html = _replace_or_insert(html, CHART_DATA_RE,  chart_js,   PHRASE_DATA_RE)
    html = _replace_or_insert(html, STORY_DATA_RE,  stories_js, CHART_DATA_RE)
    html = _replace_or_insert(html, SPOTIFY_RE,     spotify_js, STORY_DATA_RE)

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {len(cards)} cards, {len(phrases)} phrases, {len(chart_tones)} chart tones, "
          f"{len(stories)} stories, spotify={spotify_id} into {INDEX_HTML.name}", file=sys.stderr)


if __name__ == "__main__":
    cards = build_flashcard_data()
    chart_tones = build_chart_audio()
    phrases = build_phrase_data()
    patch_index_html(cards, phrases, chart_tones, STORIES, SPOTIFY_PLAYLIST_ID)
    n_words = len(list(AUDIO_DIR.glob('*.mp3')))
    n_phrases = len(list(PHRASE_AUDIO_DIR.glob('*.mp3'))) if PHRASE_AUDIO_DIR.exists() else 0
    print(f"\nDone. {len(cards)} pairs ({n_words} word mp3s), "
          f"{len(phrases)} phrases ({n_phrases} phrase mp3s), "
          f"{len(STORIES)} stories.",
          file=sys.stderr)
