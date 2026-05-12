# Tonely

> Tone training for ears that grew up without tones.
> website live: [TONELY](https://jacqueline-1929.github.io/mandarin_tone_trainer/)

By **Jackie Carter** and **Sam Knox**.
Code released under the MIT License — see [LICENSE](LICENSE). Audio and embedded media remain under the licenses of their original sources (see Acknowledgments).

A single-page flashcard app for training Mandarin tone perception. Each card pairs a high-frequency monosyllabic word with a tone-minimal-pair contrast (same syllable, different tone) so you train the perceptual category — not just the word.

- **Study mode** — flip through 65 base/contrast pairs, see the character + pinyin + meaning, hear two native speakers pronounce each.
- **Test mode** — audio plays a randomly chosen word, you pick which of the two pair members you heard. 2-AFC tone discrimination, score tracked.
- **Vocab mode** — see an English meaning, pick the matching Chinese character + pinyin from 4 choices. One distractor is always the tone-pair partner (same syllable, wrong tone) so meaning *and* tone both have to be right.
- **Phrases mode** — 40 short conversational sentences from native-speaker recordings, mostly built from words in the deck. Hear bank words used in real speech, with sentence-level prosody and tone sandhi.
- **Chart mode** — Reference: the four tones plotted on a Chao 5-level pitch chart (high-level, rising, dipping, falling) plus the neutral tone. Click any tone to hear the canonical mā/má/mǎ/mà example.
- **Stories mode** — 4 classic Chinese chengyu (idiom origin tales): 守株待兔, 画蛇添足, 亡羊补牢, 塞翁失马. Each shows the story sentence-by-sentence (character / pinyin / English) alongside an embedded YouTube video so you can listen while reading.
- **Songs mode** — embedded Spotify playlist for listening practice and vocab exposure. Note: sung Mandarin flattens linguistic tones to fit the melody, so this is for vocabulary and fluency, not tone training.

## Usage

The app is one HTML file with no build step:

```sh
python3 -m http.server 8765
# open http://localhost:8765/index.html
```

(Audio playback is more reliable over `http://` than `file://` in some browsers, hence the local server.)

### Keyboard shortcuts

| Key | Study | Test | Vocab | Phrases | Chart | Stories | Songs |
|-----|-------|------|-------|---------|-------|---------|-------|
| ← / → | prev / next | — / next q | — / next q | prev / next | — | prev / next story | — |
| 1 / 2 | play speaker 1 / 2 | pick choice 1 / 2 | pick choice 1 / 2 | play (1) | — | — | — |
| 3 / 4 | — | — | pick choice 3 / 4 | — | — | — | — |
| space / r | — | replay (`r`) | — | play / replay | — | — | — |
| b / c | base / contrast | — | — | — | — | — | — |

In Chart mode, click any tone curve or info card to play its example. In Stories mode, the embedded YouTube player has its own controls.

## Adding or swapping content

The runtime data sources are two arrays in [build.py](build.py):

- `PAIRS` — the 65 tone-contrast word pairs (syllable, tone, speaker → Tone Perfect)
- `PHRASES` — the 40 sentences (Tatoeba audio ID, characters, pinyin, English)

To change either:

1. Edit `PAIRS` and/or `PHRASES` in [build.py](build.py).
2. Run `python3 build.py` — it resolves Tone Perfect item IDs, downloads any missing MP3s into `audio/` and `audio/phrases/`, and rewrites the `flashcardData` and `phraseData` blocks in [index.html](index.html) in place.

The script is idempotent: existing audio files are skipped on re-runs.

The human-readable word list lives in [50_words.md](50_words.md). To find new candidate phrases that use the existing word bank, see the curation notes in `build.py`'s `PHRASES` block — the candidates were drawn from Tatoeba's bulk Mandarin corpus filtered for sentences with audio that maximize bank-character coverage.

## Acknowledgments

**Word audio — Tone Perfect** (MSU Libraries):

> Catherine Ryu, Mandarin Tone Perception & Production Team, and Michigan State University Libraries. *Tone Perfect: Multimodal Database for Mandarin Chinese.* Accessed 7 May 2026. https://tone.lib.msu.edu/

A free, open-access corpus of 9,840 audio recordings covering all 410 standard Mandarin syllables × 4 tones × 6 native speakers (3 female, 3 male). This project uses two voices (Female Voice 1 and Male Voice 1). The maintainers ask that users [request access via their form](https://tone.lib.msu.edu/) and cite the corpus when redistributing. If you use this project, cite Tone Perfect — not this repo.

**Phrase audio — Tatoeba** (https://tatoeba.org/), licensed CC BY 2.0 FR:

> Tatoeba — a community-built corpus of example sentences with audio recorded by native speakers across many languages. Each phrase MP3 in `audio/phrases/` is named after its Tatoeba `audio_id`; the original sentence + recording author can be looked up via Tatoeba's API.

**Story videos — YouTube (LingoAce channel):**

> The Stories tab embeds animated chengyu narrations from [LingoAce](https://www.youtube.com/@LingoAce). Videos remain hosted on YouTube; this app only embeds them via `youtube-nocookie.com`. The English translations and pinyin shown alongside each story are written for this project (chengyu narratives themselves are public domain, ~2,000+ years old).

**Songs — Spotify:**

> The Songs tab embeds a Spotify playlist via Spotify's standard web embed. Playback requires Spotify and is subject to Spotify's terms.

## Project layout

```
tonely/
├── index.html         # the app (HTML + CSS + JS + flashcardData + phraseData inline)
├── 50_words.md        # human-readable word list with pairs
├── build.py           # word/phrase source-of-truth + audio fetcher + index.html patcher
├── audio/             # word MP3s (FV1 + MV1 per syllable-tone) + phrases/ + ma1-4 (chart)
└── README.md
```

## Why tone contrasts

For learners coming from a non-tonal L1 (English, French, etc.), the bottleneck isn't memorizing a word's tone — it's *hearing* the tone at all. Pairing each word with its tone-minimal partner (我 wǒ ↔ 卧 wò, 买 mǎi ↔ 卖 mài) forces the perceptual contrast that's invisible when words are studied in isolation. Two-alternative forced-choice testing on those pairs is one of the better-supported drills in L2 phonology research.
