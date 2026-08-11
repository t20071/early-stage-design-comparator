# Early-Stage Design Options Comparator

A lightweight AI-assisted tool for **building-performance engineers** to reason
through early-stage design options — before detailed simulation begins.

Built as a working prototype of an *interaction pattern*, not a simulation
engine. It is intended to demonstrate how AI reasoning can be surfaced
transparently enough for a skeptical expert to trust, challenge, and override it.

---

## Why it's built this way

Two principles drive every design decision:

1. **Reasoning must always be visible.** No score, verdict, or directional read
   appears without the sentence that justifies it. This is not cosmetic — it is
   the mechanism that lets an engineer catch a wrong assumption before it
   influences a decision.

2. **The human retains final authority — structurally, not just in principle.**
   The tool deliberately does *not* output an overall winner or ranking. It
   surfaces per-axis trade-offs (Energy Load, Thermal Comfort, Daylight/Glare).
   The engineer weighs them. The "Engineer's Final Call" section records that
   decision explicitly, including whether the AI's reasoning changed their
   thinking — which is the key success metric of this experiment.

---

## Screenshots

### Input + Design Options
![Input form](image.png)
![Program brief and options](image-1.png)

### AI Directional Read (per option, per axis)
![AI output - option A](image-2.png)
![AI output - option B](image-3.png)
![AI output - axes detail](image-4.png)
![Assumptions expander](image-5.png)

### Engineer's Final Call + Session Summary
![Final call and summary](image-6.png)


---

## Stack

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| LLM | [Groq](https://groq.com/) — `llama-3.3-70b-versatile` |
| Output format | JSON mode (structured, parseable) |
| Temperature | 0.35 (low, for consistent directional reads) |
| State | `st.session_state` only — no database |

---

## Getting started

### 1. Prerequisites

- [Conda](https://docs.conda.io/en/latest/) installed
- A [Groq API key](https://console.groq.com/) (free tier works)

### 2. Clone the repo

```bash
git clone <your-repo-url>
cd 01_moser_ai_practice
```

### 3. Create the conda environment

```bash
conda create -n moser_ai python=3.11 -y
conda activate moser_ai
pip install -r requirements.txt
```

### 4. Set your API key

```bash
cp .env.example .env
# Open .env and replace your_key_here with your actual Groq API key
```

### 5. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501` in your browser.

---

## How to use

1. **Fill in site context and program brief** (top section)
2. **Define 2–3 design options** — orientation, glazing ratio, shading type,
   and your own gut instinct for each option *(recorded before you see AI output)*
3. **Click "Run Comparison"** — Groq returns directional reads for each option
   across three axes, with reasoning always adjacent
4. **Review the AI read** — check the assumptions it's making; adjust your
   interpretation if any don't match your project reality
5. **Record your final call** — choose your option, note your reasoning, and
   mark whether the AI's transparency changed your thinking

---

## What this tool does NOT do

- ❌ Real energy simulation or load calculations
- ❌ HVAC or structural analysis
- ❌ Pick a winner or rank options
- ❌ Store data between sessions
- ❌ Require login or a database

These are intentional omissions, not missing features.

---

## File structure

```
.
├── app.py              # Main Streamlit application (single file)
├── requirements.txt    # Python dependencies
├── .env.example        # API key template (copy to .env, never commit .env)
├── screenshots/        # UI screenshots for README
└── README.md
```

---

## License

MIT — use freely, adapt freely, attribute appreciated.
# early-stage-design-comparator
