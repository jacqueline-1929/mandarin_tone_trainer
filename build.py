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
            {"han": "宋国有一个农夫，每天在田里耕地。",
             "pinyin": "Sòng guó yǒu yī gè nóngfū, měi tiān zài tián lǐ gēng dì.",
             "en": "In the state of Song there was a farmer who tilled his field every day."},
            {"han": "有一天，一只兔子飞快地跑过来，撞到了田边的树桩上，死了。",
             "pinyin": "Yǒu yī tiān, yī zhī tùzi fēikuài de pǎo guòlái, zhuàng dào le tián biān de shùzhuāng shàng, sǐ le.",
             "en": "One day a rabbit ran by very fast, crashed into a tree stump at the edge of the field, and died."},
            {"han": "农夫高兴地把兔子拿回家，做了一顿好饭。",
             "pinyin": "Nóngfū gāoxìng de bǎ tùzi ná huí jiā, zuò le yī dùn hǎo fàn.",
             "en": "The farmer happily took the rabbit home and made himself a nice meal."},
            {"han": "从此以后，他不再耕田，每天坐在树桩旁边，等着兔子再来。",
             "pinyin": "Cóngcǐ yǐhòu, tā bù zài gēng tián, měi tiān zuò zài shùzhuāng pángbiān, děng zhe tùzi zài lái.",
             "en": "From then on he stopped working his field; every day he sat by the stump waiting for another rabbit."},
            {"han": "可是，再也没有兔子撞到树桩上了。他的田地长满了野草，他成了大家的笑话。",
             "pinyin": "Kěshì, zài yě méi yǒu tùzi zhuàng dào shùzhuāng shàng le. Tā de tiándì zhǎng mǎn le yěcǎo, tā chéng le dàjiā de xiàohua.",
             "en": "But no more rabbits ever crashed into the stump. His fields grew over with weeds, and he became the village laughingstock."},
        ],
        "moral": {"han": "不要把偶然当作必然，不要靠运气过日子。",
                  "pinyin": "Bú yào bǎ ǒurán dàngzuò bìrán, bú yào kào yùnqì guò rìzi.",
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
            {"han": "楚国有个人请客，给客人一壶酒。",
             "pinyin": "Chǔ guó yǒu gè rén qǐngkè, gěi kèrén yī hú jiǔ.",
             "en": "In the state of Chu, a man hosted some guests and gave them a single jug of wine."},
            {"han": "人多酒少，他们想出一个办法：每个人在地上画一条蛇，谁先画完，谁就喝这壶酒。",
             "pinyin": "Rén duō jiǔ shǎo, tāmen xiǎng chū yī gè bànfǎ: měi gè rén zài dì shàng huà yī tiáo shé, shéi xiān huà wán, shéi jiù hē zhè hú jiǔ.",
             "en": "There were many people but little wine, so they made a deal: each person would draw a snake on the ground, and whoever finished first would get the jug."},
            {"han": "一个人很快就画完了。他看别人还没画完，得意地说：\"你们都太慢了！我还能给蛇画上脚。\"",
             "pinyin": "Yī gè rén hěn kuài jiù huà wán le. Tā kàn biérén hái méi huà wán, déyì de shuō: \"Nǐmen dōu tài màn le! Wǒ hái néng gěi shé huà shàng jiǎo.\"",
             "en": "One man finished very quickly. Seeing the others still drawing, he said proudly, \"You're all so slow! I have time to give my snake feet too.\""},
            {"han": "他正在画蛇脚的时候，另一个人画完了，把酒拿过去，说：\"蛇本来没有脚，你画的不是蛇了。\"",
             "pinyin": "Tā zhèngzài huà shé jiǎo de shíhou, lìng yī gè rén huà wán le, bǎ jiǔ ná guòqù, shuō: \"Shé běnlái méi yǒu jiǎo, nǐ huà de bú shì shé le.\"",
             "en": "While he was drawing the feet, another man finished, took the wine, and said, \"Snakes don't have feet — what you've drawn isn't a snake anymore.\""},
            {"han": "第一个人就这样失去了酒。",
             "pinyin": "Dì yī gè rén jiù zhèyàng shīqù le jiǔ.",
             "en": "And so the first man lost the wine."},
        ],
        "moral": {"han": "做事过头，反而把好事变成坏事。",
                  "pinyin": "Zuò shì guòtóu, fǎn'ér bǎ hǎo shì biàn chéng huài shì.",
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
            {"han": "从前有个人，养了一群羊。",
             "pinyin": "Cóngqián yǒu gè rén, yǎng le yī qún yáng.",
             "en": "Once there was a man who kept a flock of sheep."},
            {"han": "一天早上，他发现羊圈有一个洞，少了一只羊。",
             "pinyin": "Yī tiān zǎoshang, tā fāxiàn yáng juàn yǒu yī gè dòng, shǎo le yī zhī yáng.",
             "en": "One morning he noticed a hole in the pen and that one sheep was missing."},
            {"han": "邻居说：\"你快把洞补好吧。\"他却说：\"羊已经丢了，补也没用。\"",
             "pinyin": "Línjū shuō: \"Nǐ kuài bǎ dòng bǔ hǎo ba.\" Tā què shuō: \"Yáng yǐjīng diū le, bǔ yě méi yòng.\"",
             "en": "A neighbor said, \"Hurry up and fix the hole.\" But he replied, \"The sheep is already gone — fixing it is no use.\""},
            {"han": "第二天，又少了一只羊。",
             "pinyin": "Dì èr tiān, yòu shǎo le yī zhī yáng.",
             "en": "The next day, another sheep was missing."},
            {"han": "他后悔了，赶紧把洞补好。从那以后，他的羊再也没有丢过。",
             "pinyin": "Tā hòuhuǐ le, gǎnjǐn bǎ dòng bǔ hǎo. Cóng nà yǐhòu, tā de yáng zài yě méi yǒu diū guò.",
             "en": "He regretted it and quickly mended the hole. From then on, no more sheep were lost."},
        ],
        "moral": {"han": "知道错了就改，永远不晚。",
                  "pinyin": "Zhīdào cuò le jiù gǎi, yǒngyuǎn bù wǎn.",
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
            {"han": "边塞有一个老人，养了一匹好马。",
             "pinyin": "Biānsài yǒu yī gè lǎorén, yǎng le yī pǐ hǎo mǎ.",
             "en": "At the frontier lived an old man who kept a fine horse."},
            {"han": "有一天，马跑丢了。邻居们都来安慰他，他却说：\"这不一定是坏事。\"",
             "pinyin": "Yǒu yī tiān, mǎ pǎo diū le. Línjū men dōu lái ānwèi tā, tā què shuō: \"Zhè bù yīdìng shì huài shì.\"",
             "en": "One day the horse ran away. The neighbors came to console him, but he said, \"This isn't necessarily bad.\""},
            {"han": "过了几个月，那匹马回来了，还带回了一匹野马。邻居们都来祝贺，他却说：\"这不一定是好事。\"",
             "pinyin": "Guò le jǐ gè yuè, nà pǐ mǎ huí lái le, hái dài huí le yī pǐ yěmǎ. Línjū men dōu lái zhùhè, tā què shuō: \"Zhè bù yīdìng shì hǎo shì.\"",
             "en": "A few months later the horse came back, and brought a wild horse with it. The neighbors came to congratulate him, but he said, \"This isn't necessarily good.\""},
            {"han": "老人的儿子骑那匹野马，摔断了腿。邻居们又来安慰，他说：\"这不一定是坏事。\"",
             "pinyin": "Lǎorén de érzi qí nà pǐ yěmǎ, shuāi duàn le tuǐ. Línjū men yòu lái ānwèi, tā shuō: \"Zhè bù yīdìng shì huài shì.\"",
             "en": "The old man's son rode the wild horse and broke his leg. The neighbors came to console him again, and he said, \"This isn't necessarily bad.\""},
            {"han": "不久，国家打仗，年轻人都被征兵，大多数都死了。老人的儿子因为腿伤，没有去打仗，活了下来。",
             "pinyin": "Bùjiǔ, guójiā dǎzhàng, niánqīng rén dōu bèi zhēngbīng, dà duōshù dōu sǐ le. Lǎorén de érzi yīnwèi tuǐ shāng, méi yǒu qù dǎzhàng, huó le xiàlái.",
             "en": "Soon after, war broke out. Young men were drafted, and most of them died. Because of his broken leg, the old man's son didn't go, and he survived."},
        ],
        "moral": {"han": "好事坏事，常常会变。",
                  "pinyin": "Hǎo shì huài shì, chángcháng huì biàn.",
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
