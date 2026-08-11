"""
Early-Stage Design Options Comparator
======================================
A transparent AI reasoning tool for building-performance engineers.
The engineer provides context and options; the AI shows its reasoning
axis-by-axis — never a single verdict. The human retains final authority.
"""

import os
import json
import re
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
load_dotenv()

st.set_page_config(
    page_title="Early-Stage Design Comparator",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GROQ_MODEL = "llama-3.3-70b-versatile"
ORIENTATIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
SHADING_TYPES = [
    "None",
    "Horizontal overhang",
    "Vertical fins",
    "Louvers",
    "Deep recess",
]
AXES = ["Energy Load", "Thermal Comfort", "Daylight / Glare"]
AXIS_ICONS = {"Energy Load": "⚡", "Thermal Comfort": "🌡️", "Daylight / Glare": "☀️"}
SCORE_COLORS = {
    "Favorable": "#2e7d32",
    "Mixed": "#e65100",
    "Unfavorable": "#c62828",
}
SCORE_BG = {
    "Favorable": "#e8f5e9",
    "Mixed": "#fff3e0",
    "Unfavorable": "#ffebee",
}


# ─────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────
def _init_state():
    defaults = {
        "num_options": 2,
        "ai_results": None,
        "final_choice": None,
        "final_why": "",
        "ai_shifted": False,
        "comparison_run": False,
        "opt_names": [
            "Option A — Full-height glazing, east façade",
            "Option B — Punched windows, west façade",
            "Option C — Curtain wall, south façade",
        ],
        "opt_orientations": ["E", "W", "S"],
        "opt_glazing": [70, 30, 50],
        "opt_shading": ["None", "Horizontal overhang", "Louvers"],
        "opt_gut": ["", "", ""],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ─────────────────────────────────────────────
# Groq helpers
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are an early-stage building-performance advisor helping architects and engineers reason through design options before detailed simulation begins.

Your role is to provide DIRECTIONAL, QUALITATIVE reasoning only — not engineering calculations, energy models, or precise numbers. Always make your assumptions explicit.

CRITICAL RULES:
1. Do NOT output an overall winner, ranking, or recommendation. You only provide per-axis, per-option directional reads.
2. Every score MUST be accompanied by a one-sentence justification. Never show a bare score.
3. For each option, score exactly three axes: Energy Load, Thermal Comfort, Daylight / Glare.
4. Each axis score must be exactly one of: Favorable | Mixed | Unfavorable.
5. List 3–5 key assumptions per option (things your assessment depends on that were not stated).
6. List 1–2 factors that, if different, would meaningfully change the assessment.
7. Respond ONLY with a valid JSON object — no preamble, no markdown fences, no trailing text.

JSON schema (return exactly this structure, with one entry per option):
{
  "options": [
    {
      "name": "<option name>",
      "axes": {
        "Energy Load":      {"score": "<Favorable|Mixed|Unfavorable>", "reasoning": "<one sentence>"},
        "Thermal Comfort":  {"score": "<Favorable|Mixed|Unfavorable>", "reasoning": "<one sentence>"},
        "Daylight / Glare": {"score": "<Favorable|Mixed|Unfavorable>", "reasoning": "<one sentence>"}
      },
      "assumptions": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
      "flip_factors": ["<factor 1>", "<factor 2>"]
    }
  ]
}"""


def build_user_prompt(site_context, program_brief, options):
    lines = [
        f"SITE CONTEXT:\n{site_context.strip()}",
        f"\nPROGRAM BRIEF:\n{program_brief.strip()}",
        "\nDESIGN OPTIONS:",
    ]
    for i, opt in enumerate(options):
        lines.append(
            f"\n  Option {i+1}: {opt['name']}\n"
            f"    Orientation: {opt['orientation']}\n"
            f"    Glazing Ratio: {opt['glazing']}%\n"
            f"    Shading Type: {opt['shading']}\n"
            f"    Engineer's initial read: {opt['gut'] or '(not provided)'}"
        )
    lines.append(
        "\nProvide your directional assessment following the JSON schema exactly. "
        "Do not pick a winner. Do not rank. Do not recommend."
    )
    return "\n".join(lines)


def _repair_json(text: str) -> str:
    """
    Attempt lightweight repair of common model JSON errors:
    1. Replace stray ] that close an object context (] instead of })
    2. Close any unclosed braces/brackets at the end of a truncated response.
    """
    # Fix `}]` -> `}}` when inside an axes-style object
    # Pattern: the model writes  "reasoning": "..."}]  instead of  "reasoning": "..."}}  
    text = re.sub(r'("reasoning"\s*:\s*"[^"]*")\s*\]', r'\1}', text)
    text = re.sub(r'("score"\s*:\s*"[^"]*")\s*\]', r'\1}', text)

    # Close any unclosed structures at the end (handles truncation)
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

    # Append missing closers
    closing = {'[': ']', '{': '}'}
    for opener in reversed(stack):
        text = text.rstrip() + closing[opener]

    return text


def _extract_json(text: str) -> dict:
    """Try to parse JSON from raw model output, with repair and regex fallback."""
    text = text.strip()

    # Strip markdown fences first
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    candidate = fenced.group(1).strip() if fenced else text

    # Try direct parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Try after repair
    try:
        return json.loads(_repair_json(candidate))
    except json.JSONDecodeError:
        pass

    # Grab first { ... } block and repair
    brace = re.search(r"(\{[\s\S]+)", candidate)
    if brace:
        try:
            return json.loads(_repair_json(brace.group(1)))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse model response as JSON. Raw output (first 600 chars):\n{text[:600]}") 


def call_groq(site_context, program_brief, options):
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        raise ValueError(
            "GROQ_API_KEY is not set. Create a .env file with your key "
            "(see .env.example)."
        )
    client = Groq(api_key=api_key)
    user_prompt = build_user_prompt(site_context, program_brief, options)

    def _call_once(temperature: float) -> dict:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=temperature,
            max_tokens=4096,  # 2048 was too low — multi-option reasoning easily exceeds it
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            # NOTE: response_format json_object is intentionally omitted.
            # Groq's strict server-side JSON validation rejects even slightly
            # malformed model output (e.g. ] instead of } closing an object),
            # returning a 400 before we can attempt recovery. We parse
            # ourselves below, which is more resilient.
        )
        return _extract_json(response.choices[0].message.content)

    # Attempt 1
    try:
        return _call_once(temperature=0.35)
    except (ValueError, json.JSONDecodeError):
        pass

    # Attempt 2 — slightly higher temperature sometimes fixes the structure
    return _call_once(temperature=0.5)


# ─────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────
def score_badge(score: str) -> str:
    color = SCORE_COLORS.get(score, "#555")
    bg = SCORE_BG.get(score, "#f5f5f5")
    return (
        f'<span style="background:{bg};color:{color};font-weight:700;'
        f'padding:3px 10px;border-radius:12px;font-size:0.85rem;'
        f'border:1.5px solid {color};">{score}</span>'
    )


def render_axis_row(axis: str, data: dict):
    icon = AXIS_ICONS.get(axis, "•")
    score = data.get("score", "—")
    reasoning = data.get("reasoning", "")
    st.markdown(
        f"""<div style="margin-bottom:10px;padding:10px 14px;
        border-left:4px solid {SCORE_COLORS.get(score,'#ccc')};
        background:{SCORE_BG.get(score,'#fafafa')};border-radius:0 8px 8px 0;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
          <span style="font-size:1.1rem;">{icon}</span>
          <strong style="font-size:0.95rem;">{axis}</strong>
          {score_badge(score)}
        </div>
        <div style="font-size:0.88rem;color:#444;margin-left:28px;">{reasoning}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_option_card(opt_result: dict, gut_instinct: str):
    name = opt_result.get("name", "Unnamed option")
    axes = opt_result.get("axes", {})
    assumptions = opt_result.get("assumptions", [])
    flips = opt_result.get("flip_factors", [])

    st.markdown(f"#### {name}")

    # Engineer's gut instinct — shown FIRST
    with st.container(border=True):
        st.markdown("**🧠 Engineer's initial read** *(before AI output)*")
        st.markdown(
            f'<div style="background:#f0f4ff;padding:10px 14px;border-radius:8px;'
            f'font-style:italic;color:#333;font-size:0.92rem;">'
            f'{gut_instinct if gut_instinct.strip() else "<em>(not recorded)</em>"}'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("**AI Directional Read** *(per-axis reasoning always shown)*")
    for axis in AXES:
        data = axes.get(axis, {})
        render_axis_row(axis, data)

    # Assumptions + flip factors — always visible, de-emphasized
    with st.expander("📋 Assumptions & what would change this read", expanded=True):
        st.markdown(
            '<p style="font-size:0.82rem;color:#888;margin-bottom:4px;">'
            "These assumptions underpin the AI's read. If they differ from "
            "your project reality, adjust your interpretation accordingly.</p>",
            unsafe_allow_html=True,
        )
        if assumptions:
            st.markdown("**Key assumptions the AI is making:**")
            for a in assumptions:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:#555;'
                    f'padding:2px 0 2px 12px;">• {a}</div>',
                    unsafe_allow_html=True,
                )
        if flips:
            st.markdown("**What would change this assessment:**")
            for f in flips:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:#555;'
                    f'padding:2px 0 2px 12px;">↩ {f}</div>',
                    unsafe_allow_html=True,
                )


# ─────────────────────────────────────────────
# Main layout
# ─────────────────────────────────────────────
def main():
    # ── Header ──────────────────────────────
    st.markdown(
        """
        <div style="padding:18px 0 8px 0;">
          <h1 style="margin:0;font-size:1.75rem;font-weight:700;">
            🏛️ Early-Stage Design Options Comparator
          </h1>
          <p style="color:#555;font-size:0.97rem;margin-top:6px;max-width:820px;">
            This tool supports early-stage building-performance decisions by making
            AI reasoning visible and structured — axis by axis, assumption by assumption.
            The AI does <strong>not</strong> pick a winner; it surfaces trade-offs.
            The engineer retains full decision authority.
          </p>
          <hr style="margin-top:12px;border:none;border-top:1.5px solid #e0e0e0;">
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Input section ────────────────────────
    st.markdown("## 1 · Project Context")
    col_site, col_brief = st.columns(2)
    with col_site:
        site_context = st.text_area(
            "Site context",
            placeholder=(
                "e.g. Bengaluru, hot-humid climate, north-facing site, "
                "high ambient noise from adjacent road, low-rise neighbours to north."
            ),
            height=120,
            key="site_context",
            help="Describe climate, orientation of site, surroundings, constraints.",
        )
    with col_brief:
        program_brief = st.text_area(
            "Program brief",
            placeholder=(
                "e.g. 80-person open office, 2 meeting rooms, "
                "target LEED Gold, 9 am–6 pm primary occupancy."
            ),
            height=120,
            key="program_brief",
            help="Describe the building programme, occupancy, and performance targets.",
        )

    # ── Option count ─────────────────────────
    st.markdown("## 2 · Design Options")
    n_col, _ = st.columns([2, 5])
    with n_col:
        st.session_state.num_options = st.radio(
            "Number of options to compare",
            [2, 3],
            index=st.session_state.num_options - 2,
            horizontal=True,
            key="num_options_radio",
        )

    n = st.session_state.num_options
    option_cols = st.columns(n)

    opt_data = []
    for i, col in enumerate(option_cols):
        with col:
            st.markdown(f"#### Option {chr(65+i)}")
            name = st.text_input(
                "Option name / description",
                value=st.session_state.opt_names[i],
                key=f"opt_name_{i}",
                placeholder=f"Option {chr(65+i)} — brief label",
            )
            orientation = st.selectbox(
                "Primary façade orientation",
                ORIENTATIONS,
                index=ORIENTATIONS.index(st.session_state.opt_orientations[i]),
                key=f"opt_orient_{i}",
            )
            glazing = st.slider(
                "Glazing ratio (%)",
                10,
                90,
                value=st.session_state.opt_glazing[i],
                step=5,
                key=f"opt_glazing_{i}",
            )
            shading = st.selectbox(
                "Shading type",
                SHADING_TYPES,
                index=SHADING_TYPES.index(st.session_state.opt_shading[i]),
                key=f"opt_shading_{i}",
            )
            gut = st.text_area(
                "Your gut instinct & reasoning for this option",
                value=st.session_state.opt_gut[i],
                key=f"opt_gut_{i}",
                height=100,
                placeholder=(
                    "What does your experience tell you about this option? "
                    "What trade-offs do you already expect?"
                ),
                help="Captured BEFORE the AI output — your independent view.",
            )
            opt_data.append(
                {
                    "name": name,
                    "orientation": orientation,
                    "glazing": glazing,
                    "shading": shading,
                    "gut": gut,
                }
            )

    # ── Run button ───────────────────────────
    st.markdown("")
    run_col, _ = st.columns([2, 5])
    with run_col:
        run_btn = st.button(
            "▶  Run Comparison",
            type="primary",
            use_container_width=True,
            disabled=not (site_context.strip() and program_brief.strip()),
        )

    if not (site_context.strip() and program_brief.strip()):
        st.caption("Fill in site context and program brief to enable comparison.")

    # ── Call AI ──────────────────────────────
    if run_btn:
        with st.spinner("Sending to Groq · reasoning in progress…"):
            try:
                result = call_groq(site_context, program_brief, opt_data[:n])
                st.session_state.ai_results = result
                st.session_state.comparison_run = True
                st.session_state.final_choice = None
            except ValueError as e:
                st.error(f"Configuration error: {e}")
            except json.JSONDecodeError:
                st.error(
                    "The AI returned a response that could not be parsed as JSON. "
                    "Try running again."
                )
            except Exception as e:
                st.error(f"API error: {e}")

    # ── Results ──────────────────────────────
    if st.session_state.comparison_run and st.session_state.ai_results:
        results = st.session_state.ai_results.get("options", [])
        n_results = min(len(results), n)

        st.markdown("---")
        st.markdown("## 3 · AI Directional Read")
        st.caption(
            "No overall winner is shown — trade-offs are yours to weigh. "
            "Reasoning is always shown alongside each score."
        )

        result_cols = st.columns(n_results)
        gut_values = [opt_data[i]["gut"] for i in range(n_results)]

        for i, col in enumerate(result_cols):
            with col:
                render_option_card(results[i], gut_values[i])

        # ── Engineer's Final Call ─────────────
        st.markdown("---")
        st.markdown(
            """
            <div style="background:#f8f9ff;border:2px solid #3f51b5;border-radius:10px;
            padding:20px 24px 6px 24px;margin-bottom:16px;">
            <h2 style="margin:0 0 4px 0;color:#3f51b5;font-size:1.3rem;">
              ✍️ Engineer's Final Call
            </h2>
            <p style="font-size:0.88rem;color:#555;margin:0 0 16px 0;">
              This section captures your decision — independent of, and informed by,
              the AI reasoning above. It is the most important record in this session.
            </p>
            """,
            unsafe_allow_html=True,
        )

        option_labels = [
            r.get("name", f"Option {i+1}") for i, r in enumerate(results[:n_results])
        ]
        option_labels_ext = option_labels + ["None of these — need another option"]

        default_idx = 0
        if st.session_state.final_choice in option_labels_ext:
            default_idx = option_labels_ext.index(st.session_state.final_choice)

        chosen = st.radio(
            "Which option are you proceeding with?",
            option_labels_ext,
            key="final_choice_radio",
            index=default_idx,
        )
        st.session_state.final_choice = chosen

        final_why = st.text_area(
            "Why? (especially note if this differs from the AI's read)",
            value=st.session_state.final_why,
            key="final_why_input",
            height=90,
            placeholder=(
                "Explain your reasoning. If your choice diverges from the AI read, "
                "note which factors the AI missed or over/under-weighted."
            ),
        )
        st.session_state.final_why = final_why

        ai_shifted = st.checkbox(
            "✅  The AI's reasoning changed or refined my thinking",
            value=st.session_state.ai_shifted,
            key="ai_shifted_check",
            help=(
                "Core data point: did transparent AI reasoning actually influence "
                "the engineer's view?"
            ),
        )
        st.session_state.ai_shifted = ai_shifted

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Session Summary ───────────────────
        st.markdown("---")
        st.markdown("## 4 · Session Summary")
        st.caption(
            "A snapshot of this comparison session — suitable for sharing with "
            "reviewers or attaching to a design-stage record."
        )

        def condensed_read(opt_result):
            axes = opt_result.get("axes", {})
            short_names = {
                "Energy Load": "Energy",
                "Thermal Comfort": "Comfort",
                "Daylight / Glare": "Daylight",
            }
            parts = []
            for ax in AXES:
                sc = axes.get(ax, {}).get("score", "—")
                parts.append(f"{short_names[ax]}: {sc}")
            return " · ".join(parts)

        table_rows = []
        for i, r in enumerate(results[:n_results]):
            gut_text = opt_data[i]["gut"]
            table_rows.append(
                {
                    "Option": r.get("name", f"Option {i+1}"),
                    "Engineer's initial read": (
                        (gut_text[:80] + "…")
                        if gut_text and len(gut_text) > 80
                        else gut_text or "(not recorded)"
                    ),
                    "AI directional read": condensed_read(r),
                    "Engineer's final call": (
                        "✓ Selected"
                        if r.get("name") == st.session_state.final_choice
                        else "—"
                    ),
                    "AI shifted thinking": (
                        "Yes ✓" if st.session_state.ai_shifted else "No"
                    ),
                }
            )

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        if st.session_state.final_why:
            st.markdown(
                f"**Decision rationale recorded:** {st.session_state.final_why}"
            )

        st.markdown(
            '<p style="font-size:0.78rem;color:#aaa;margin-top:16px;">'
            "⚠️ This tool provides qualitative directional guidance only. "
            "It is not a substitute for energy simulation, thermal analysis, "
            "or licensed engineering judgment. Outputs should be validated "
            "against project-specific conditions before any design commitment."
            "</p>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
