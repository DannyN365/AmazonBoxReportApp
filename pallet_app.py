from datetime import date
import html
from io import BytesIO
import json
from pathlib import Path
import re
from uuid import uuid4

from dotenv import load_dotenv
from lark_lookup import (
    load_repo_article_catalog,
    normalize_article_number,
)
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pallet Report",
    layout="wide",
)

load_dotenv()

LEGACY_STATE_FILE = Path(__file__).with_name(".pallet_report_state.json")
STATE_DIR = Path(__file__).with_name(".pallet_report_state")
DRAFT_QUERY_PARAM = "draft"
SESSION_DEFAULTS = {
    "input_operator_name": "",
    "input_order_id": "",
    "order_type": "pallet",
    "input_pallet_nr": "1",
    "input_length": 120,
    "input_width": 80,
    "input_height": "",
    "input_weight": "",
    "input_pallet_comment": "",
    "input_box_numbers": "",
    "input_pcs_per_box": "",
    "input_art_nr": "",
    "input_comment": "",
}
PERSISTED_SESSION_KEYS = [
    "pallets",
    "editing_index",
    "editing_box_index",
    "pending_clear_form",
    "pending_pallet_details",
    "pending_box_numbers",
    "entry_mode",
    "editing_pallet_index",
    "refresh_pallet_form_widgets",
    *SESSION_DEFAULTS.keys(),
]


def normalize_draft_key(raw_value):
    if not raw_value:
        return None

    normalized = re.sub(r"[^a-zA-Z0-9_-]", "", str(raw_value)).strip()
    if not normalized:
        return None

    return normalized[:80]


def is_box_order_mode():
    return st.session_state.get("order_type") == "box"


def handle_order_type_change(previous_order_type):
    current_order_type = st.session_state.order_type
    if current_order_type == previous_order_type:
        return

    st.session_state.entry_mode = "box"
    st.session_state.editing_pallet_index = None
    st.session_state.refresh_pallet_form_widgets = True

    if current_order_type == "box":
        st.session_state.input_pallet_nr = "1"
        st.session_state.active_pallet_nr = 1
        st.session_state.pending_pallet_details = {
            "input_pallet_nr": "1",
            "input_length": 120,
            "input_width": 80,
            "input_height": "",
            "input_weight": "",
            "input_pallet_comment": "",
        }
    else:
        if not str(st.session_state.input_pallet_nr).strip():
            st.session_state.input_pallet_nr = "1"

    persist_and_rerun()


def ensure_draft_key():
    draft_key = normalize_draft_key(st.query_params.get(DRAFT_QUERY_PARAM))
    if not draft_key:
        draft_key = uuid4().hex
        st.query_params[DRAFT_QUERY_PARAM] = draft_key

    st.session_state.draft_key = draft_key
    return draft_key


def get_state_file_path():
    draft_key = st.session_state.get("draft_key") or ensure_draft_key()
    return STATE_DIR / f"{draft_key}.json"


def load_persisted_state():
    state_file = get_state_file_path()
    source_file = state_file

    if not state_file.exists() and LEGACY_STATE_FILE.exists():
        source_file = LEGACY_STATE_FILE

    if not source_file.exists():
        return {}

    try:
        with source_file.open("r", encoding="utf-8") as persisted_file:
            state = json.load(persisted_file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(state, dict):
        return {}

    return state


def restore_persisted_session_state():
    persisted_state = load_persisted_state()
    if not persisted_state:
        return

    for key in PERSISTED_SESSION_KEYS:
        if key in persisted_state and key not in st.session_state:
            st.session_state[key] = persisted_state[key]


def persist_session_state():
    persisted_state = {}

    for key in PERSISTED_SESSION_KEYS:
        if key in st.session_state:
            persisted_state[key] = st.session_state[key]

    try:
        state_file = get_state_file_path()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with state_file.open("w", encoding="utf-8") as persisted_file:
            json.dump(persisted_state, persisted_file, ensure_ascii=True, indent=2)
    except OSError:
        pass


def persist_and_rerun():
    persist_session_state()
    st.rerun()


def inject_styles():
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1100px;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }

            h1, h2, h3 {
                letter-spacing: -0.02em;
            }

            .hero-panel {
                background: var(--secondary-background-color);
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 24px;
                padding: 1.5rem 1.6rem;
                margin-bottom: 1rem;
            }

            .hero-eyebrow {
                font-size: 0.78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.4rem;
                opacity: 0.7;
            }

            .hero-text {
                font-size: 1rem;
                margin: 0.35rem 0 0;
                opacity: 0.85;
            }

            .summary-card {
                background: var(--secondary-background-color);
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 20px;
                padding: 1rem 1.1rem;
                min-height: 118px;
            }

            .side-panel {
                background: var(--secondary-background-color);
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 22px;
                padding: 1rem;
                margin-bottom: 1rem;
            }

            .side-heading {
                font-size: 1.25rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .side-copy {
                opacity: 0.78;
                margin-bottom: 0.9rem;
            }

            .side-stat {
                border-top: 1px solid rgba(127, 127, 127, 0.16);
                padding-top: 0.7rem;
                margin-top: 0.7rem;
            }

            .side-stat strong {
                display: block;
                font-size: 1.05rem;
                margin-bottom: 0.12rem;
            }

            .pallet-chip {
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 16px;
                padding: 0.7rem 0.8rem;
                margin-bottom: 0.55rem;
                background: rgba(255, 255, 255, 0.02);
            }

            .pallet-chip-title {
                font-weight: 700;
                margin-bottom: 0.15rem;
            }

            .pallet-chip-copy {
                font-size: 0.92rem;
                opacity: 0.8;
            }

            .workflow-band {
                display: flex;
                gap: 0.65rem;
                flex-wrap: wrap;
                margin: 0.4rem 0 1rem;
            }

            .workflow-pill {
                background: linear-gradient(135deg, rgba(22, 163, 74, 0.16), rgba(59, 130, 246, 0.14));
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 999px;
                padding: 0.5rem 0.9rem;
                font-size: 0.9rem;
                font-weight: 600;
            }

            .preview-panel {
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.10), rgba(16, 185, 129, 0.10));
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 18px;
                padding: 0.95rem 1rem;
                margin-bottom: 0.9rem;
            }

            .preview-label {
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                opacity: 0.72;
                margin-bottom: 0.35rem;
            }

            .preview-value {
                font-size: 1.02rem;
                font-weight: 600;
                line-height: 1.4;
            }

            .size-warning {
                border: 1px solid rgba(248, 113, 113, 0.35);
                background: rgba(127, 29, 29, 0.16);
                color: #fecaca;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                margin: 0.8rem 0 0.2rem;
            }

            .size-warning strong {
                color: #fca5a5;
            }

            .size-ok {
                border: 1px solid rgba(74, 222, 128, 0.22);
                background: rgba(20, 83, 45, 0.14);
                color: #bbf7d0;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                margin: 0.8rem 0 0.2rem;
            }

            .summary-label {
                font-size: 0.84rem;
                margin-bottom: 0.5rem;
                opacity: 0.72;
            }

            .summary-value {
                font-size: 1.9rem;
                font-weight: 700;
                line-height: 1.1;
                margin-bottom: 0.25rem;
            }

            .summary-help {
                font-size: 0.9rem;
                opacity: 0.75;
            }

            .purge-flash {
                position: fixed;
                left: 50%;
                top: 1.1rem;
                transform: translateX(-50%);
                width: min(760px, calc(100vw - 2rem));
                z-index: 9999;
                pointer-events: none;
                animation: purge-fade 1.9s ease forwards;
            }

            .purge-flash-card {
                border-radius: 24px;
                overflow: hidden;
                border: 1px solid rgba(254, 202, 202, 0.42);
                box-shadow: 0 22px 56px rgba(127, 29, 29, 0.32);
                background:
                    radial-gradient(circle at top, rgba(255, 237, 213, 0.22), transparent 42%),
                    linear-gradient(135deg, rgba(127, 29, 29, 0.94), rgba(194, 65, 12, 0.95));
            }

            .purge-flash-top {
                padding: 1rem 1.2rem 0.55rem;
                color: #fff7ed;
            }

            .purge-flash-title {
                font-size: 1.15rem;
                font-weight: 800;
                letter-spacing: -0.02em;
            }

            .purge-flash-copy {
                margin-top: 0.2rem;
                opacity: 0.92;
            }

            .purge-flash-fireline {
                height: 34px;
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                padding: 0 0.8rem 0.35rem;
                font-size: 1.3rem;
                animation: purge-sweep 1s ease-out forwards;
                transform-origin: left center;
            }

            .purge-flash-ash {
                padding: 0.5rem 1.2rem 0.95rem;
                color: rgba(255, 247, 237, 0.9);
                font-size: 0.92rem;
            }

            @keyframes purge-sweep {
                0% {
                    transform: scaleX(0.35) translateX(-14%);
                    opacity: 0;
                }
                30% {
                    opacity: 1;
                }
                100% {
                    transform: scaleX(1) translateX(0);
                    opacity: 1;
                }
            }

            @keyframes purge-fade {
                0% {
                    opacity: 0;
                    transform: translateX(-50%) translateY(-10px) scale(0.97);
                }
                12% {
                    opacity: 1;
                    transform: translateX(-50%) translateY(0) scale(1);
                }
                78% {
                    opacity: 1;
                    transform: translateX(-50%) translateY(0) scale(1);
                }
                100% {
                    opacity: 0;
                    transform: translateX(-50%) translateY(-10px) scale(0.985);
                }
            }

            .section-note {
                margin-bottom: 0.6rem;
                opacity: 0.78;
            }

            .stAlert {
                border-radius: 16px;
            }

            div[data-testid="stExpander"] {
                border: 1px solid rgba(127, 127, 127, 0.18);
                border-radius: 18px;
                background: transparent;
            }

            div[data-testid="stExpander"] details summary p {
                font-weight: 600;
            }

            div[data-testid="stForm"] {
                background: transparent;
                border-radius: 24px;
                padding: 0.4rem 0.35rem 0;
            }

            div[data-testid="stNumberInput"] > div,
            div[data-testid="stTextInput"] > div,
            div[data-testid="stTextArea"] > div {
                background: var(--secondary-background-color);
                border-radius: 14px;
            }

            div[data-testid="stNumberInput"] input,
            div[data-testid="stTextInput"] input,
            div[data-testid="stTextArea"] textarea {
                color: var(--text-color) !important;
                -webkit-text-fill-color: var(--text-color) !important;
            }

            .small-label {
                font-size: 0.86rem;
                margin-bottom: 0.2rem;
                opacity: 0.72;
            }

            .lookup-note {
                font-size: 0.82rem;
                margin-top: 0.35rem;
                line-height: 1.35;
            }

            .lookup-note.info {
                color: #93c5fd;
            }

            .lookup-note.success {
                color: #86efac;
            }

            .lookup-note.warning {
                color: #fcd34d;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_box_numbers(box_text):
    normalized = box_text.strip()
    trailing_range_match = re.fullmatch(r"(\d+)\s*-\s*", normalized)
    if trailing_range_match:
        return trailing_range_match.group(1)
    return normalized


def format_form_value(value):
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)

def get_saved_article_name_for_current_row():
    index = st.session_state.get("editing_index")
    box_index = st.session_state.get("editing_box_index")
    if index is None or box_index is None:
        return ""

    try:
        return str(st.session_state.pallets[index]["items"][box_index].get("Article name", "")).strip()
    except (IndexError, KeyError, TypeError, AttributeError):
        return ""


def get_article_name_state(article_number, fallback_name=""):
    normalized_article_number = normalize_article_number(article_number)
    if not normalized_article_number:
        return "", "", "info"

    repo_catalog_payload = load_repo_article_catalog()
    if repo_catalog_payload:
        repo_catalog = repo_catalog_payload.get("catalog", {})
        if isinstance(repo_catalog, dict):
            article_name = str(repo_catalog.get(normalized_article_number, "")).strip()
            if article_name:
                generated_at = str(repo_catalog_payload.get("generated_at", "")).strip()
                message = "Article name loaded from repo JSON cache."
                if generated_at:
                    message = f"Article name loaded from repo JSON cache updated {generated_at}."
                return article_name, message, "success"
            return "", "No article name was found for this Art. nr in the repo JSON cache.", "warning"
    if fallback_name:
        return fallback_name, "Using the saved article name. No repo JSON cache is available for this Art. nr.", "info"
    return "", "Article name is only loaded from the repo JSON cache in the main app.", "info"


def article_lookup_note_markup(message, tone):
    if not message:
        return ""

    safe_message = html.escape(message)
    safe_tone = tone if tone in {"info", "success", "warning"} else "info"
    return f'<div class="lookup-note {safe_tone}">{safe_message}</div>'


def get_next_box_suggestion(box_text):
    normalized = parse_box_numbers(box_text)
    numbers = re.findall(r"\d+", normalized)
    if not numbers:
        return ""
    return f"{int(numbers[-1]) + 1}-"


def get_next_global_box_suggestion():
    max_box_number = 0

    for pallet in st.session_state.pallets:
        for box_line in pallet["items"]:
            numbers = re.findall(r"\d+", parse_box_numbers(box_line["Box numbers"]))
            if numbers:
                max_box_number = max(max_box_number, int(numbers[-1]))

    return f"{max_box_number + 1}-"


def is_standard_pallet_size(length, width):
    return length == 120 and width == 80


def pallet_size_notice_markup(length, width):
    if is_standard_pallet_size(length, width):
        return (
            '<div class="size-ok">'
            "<strong>Standard pallet size.</strong> Length 120 cm and width 80 cm."
            "</div>"
        )

    return (
        '<div class="size-warning">'
        "<strong>Non-standard pallet size.</strong> "
        f"Current size is {length} x {width} cm. This will still be saved."
        "</div>"
    )


def parse_int_field(label, value, minimum=0):
    raw_value = value.strip()
    if not raw_value:
        return None, f"Please enter {label.lower()}."

    try:
        parsed_value = int(raw_value)
    except ValueError:
        return None, f"{label} must be a whole number."

    if parsed_value < minimum:
        return None, f"{label} must be {minimum} or more."

    return parsed_value, None


def parse_float_field(label, value, minimum=0.0):
    raw_value = value.strip().replace(",", ".")
    if not raw_value:
        return None, f"Please enter {label.lower()}."

    try:
        parsed_value = float(raw_value)
    except ValueError:
        return None, f"{label} must be a number."

    if parsed_value < minimum:
        return None, f"{label} must be {minimum} or more."

    return parsed_value, None


def parse_optional_int_field(value, default_value):
    raw_value = value.strip()
    if not raw_value:
        return default_value, None

    try:
        return int(raw_value), None
    except ValueError:
        return None, "must be a whole number."


def parse_optional_float_field(value, default_value):
    raw_value = value.strip().replace(",", ".")
    if not raw_value:
        return default_value, None

    try:
        return float(raw_value), None
    except ValueError:
        return None, "must be a number."


def get_validated_pallet_header_data():
    pallet_nr, error = parse_optional_int_field(st.session_state.input_pallet_nr, default_value=1)
    if error:
        return None, f"Pallet nr {error}"
    if pallet_nr < 1:
        return None, "Pallet nr must be 1 or more."

    height, error = parse_optional_int_field(st.session_state.input_height, default_value=0)
    if error:
        return None, f"Height {error}"
    if height < 0:
        return None, "Height must be 0 or more."

    weight, error = parse_optional_float_field(st.session_state.input_weight, default_value=0.0)
    if error:
        return None, f"Weight kg {error}"
    if weight < 0:
        return None, "Weight kg must be 0 or more."

    return {
        "Pallet nr": pallet_nr,
        "Length cm": st.session_state.input_length,
        "Width cm": st.session_state.input_width,
        "Height cm": height,
        "Weight kg": weight,
        "Pallet comment": st.session_state.input_pallet_comment.strip(),
    }, None


def get_validated_box_line_data():
    pcs_per_box, error = parse_int_field("Pcs / box", st.session_state.input_pcs_per_box, minimum=1)
    if error:
        return None, error

    if not st.session_state.input_box_numbers.strip():
        return None, "Please enter box numbers."

    if not st.session_state.input_art_nr.strip():
        return None, "Please enter Art. nr."

    saved_article_name = get_saved_article_name_for_current_row()
    article_name, _, _ = get_article_name_state(
        st.session_state.input_art_nr,
        fallback_name=saved_article_name,
    )

    return {
        "Box numbers": parse_box_numbers(st.session_state.input_box_numbers),
        "Pcs / box": pcs_per_box,
        "Art. nr": normalize_article_number(st.session_state.input_art_nr),
        "Article name": article_name,
        "Comment": st.session_state.input_comment,
    }, None


def get_validated_form_data():
    pallet_header, error = get_validated_pallet_header_data()
    if error:
        return None, error

    box_line, error = get_validated_box_line_data()
    if error:
        return None, error

    return {**pallet_header, **box_line}, None


def split_pallet_data(pallet_data):
    pallet_header = {
        "Pallet nr": pallet_data["Pallet nr"],
        "Length cm": pallet_data["Length cm"],
        "Width cm": pallet_data["Width cm"],
        "Height cm": pallet_data["Height cm"],
        "Weight kg": pallet_data["Weight kg"],
        "Pallet comment": pallet_data["Pallet comment"],
    }
    box_line = {
        "Box numbers": pallet_data["Box numbers"],
        "Pcs / box": pallet_data["Pcs / box"],
        "Art. nr": pallet_data["Art. nr"],
        "Article name": pallet_data.get("Article name", ""),
        "Comment": pallet_data["Comment"],
    }
    return pallet_header, box_line


def find_pallet_index_by_number(pallet_nr):
    for index, pallet in enumerate(st.session_state.pallets):
        if pallet["Pallet nr"] == pallet_nr:
            return index
    return None


def get_next_pallet_number():
    if not st.session_state.pallets:
        return 1

    return max(pallet["Pallet nr"] for pallet in st.session_state.pallets) + 1


def get_current_pallet_number():
    active_pallet_nr = st.session_state.get("active_pallet_nr")
    if isinstance(active_pallet_nr, int) and active_pallet_nr >= 1:
        return active_pallet_nr

    pallet_nr, error = parse_optional_int_field(st.session_state.input_pallet_nr, default_value=1)
    if error or pallet_nr < 1:
        return 1
    return pallet_nr


def capture_pallet_detail_inputs():
    return {
        "input_pallet_nr": st.session_state.input_pallet_nr,
        "input_length": st.session_state.input_length,
        "input_width": st.session_state.input_width,
        "input_height": st.session_state.input_height,
        "input_weight": st.session_state.input_weight,
        "input_pallet_comment": st.session_state.input_pallet_comment,
    }


def ensure_visible_pallet_defaults(default_pallet_nr=None):
    if default_pallet_nr is None:
        default_pallet_nr = get_current_pallet_number()

    if not str(st.session_state.input_pallet_nr).strip():
        st.session_state.input_pallet_nr = str(default_pallet_nr)

    if st.session_state.input_length in (0, None):
        st.session_state.input_length = 120

    if st.session_state.input_width in (0, None):
        st.session_state.input_width = 80


def initialize_pallet_form_widgets(default_pallet_nr=None):
    ensure_visible_pallet_defaults(default_pallet_nr)
    widget_keys = [
        "pallet_form_pallet_nr",
        "pallet_form_weight",
        "pallet_form_length",
        "pallet_form_width",
        "pallet_form_height",
        "pallet_form_comment",
    ]
    needs_refresh = st.session_state.refresh_pallet_form_widgets or any(key not in st.session_state for key in widget_keys)
    if not needs_refresh:
        return

    st.session_state.pallet_form_pallet_nr = st.session_state.input_pallet_nr or str(default_pallet_nr or 1)
    st.session_state.pallet_form_weight = ""
    if str(st.session_state.input_weight).strip() not in ("", "0", "0.0"):
        st.session_state.pallet_form_weight = st.session_state.input_weight
    st.session_state.pallet_form_length = st.session_state.input_length or 120
    st.session_state.pallet_form_width = st.session_state.input_width or 80
    st.session_state.pallet_form_height = ""
    if str(st.session_state.input_height).strip() not in ("", "0"):
        st.session_state.pallet_form_height = st.session_state.input_height
    st.session_state.pallet_form_comment = st.session_state.input_pallet_comment
    st.session_state.refresh_pallet_form_widgets = False


def sync_inputs_from_pallet_form_widgets():
    st.session_state.input_pallet_nr = st.session_state.pallet_form_pallet_nr
    st.session_state.input_weight = st.session_state.pallet_form_weight
    st.session_state.input_length = st.session_state.pallet_form_length
    st.session_state.input_width = st.session_state.pallet_form_width
    st.session_state.input_height = st.session_state.pallet_form_height
    st.session_state.input_pallet_comment = st.session_state.pallet_form_comment


def get_active_pallet_index_for_details(default_pallet_nr):
    if st.session_state.editing_pallet_index is not None:
        return st.session_state.editing_pallet_index

    active_pallet_nr = st.session_state.get("active_pallet_nr")
    if isinstance(active_pallet_nr, int) and active_pallet_nr >= 1:
        active_index = find_pallet_index_by_number(active_pallet_nr)
        if active_index is not None:
            return active_index

    return find_pallet_index_by_number(default_pallet_nr)


def save_pallet(pallet_data, index=None, box_index=None):
    pallet_header, box_line = split_pallet_data(pallet_data)

    if index is None:
        existing_index = find_pallet_index_by_number(pallet_header["Pallet nr"])

        if existing_index is None:
            st.session_state.pallets.append(
                {
                    **pallet_header,
                    "items": [box_line],
                }
            )
        else:
            # Box entry should not overwrite already-saved pallet details with hidden defaults.
            st.session_state.pallets[existing_index]["items"].append(box_line)
    else:
        st.session_state.pallets[index].update(pallet_header)
        st.session_state.pallets[index]["items"][box_index] = box_line

    st.session_state.active_pallet_nr = pallet_header["Pallet nr"]

    st.session_state.pending_pallet_details = {
        "input_pallet_nr": format_form_value(pallet_header["Pallet nr"]),
        "input_length": pallet_header["Length cm"],
        "input_width": pallet_header["Width cm"],
        "input_height": format_form_value(pallet_header["Height cm"]),
        "input_weight": format_form_value(pallet_header["Weight kg"]),
        "input_pallet_comment": pallet_header["Pallet comment"],
    }
    if index is None:
        st.session_state.pending_box_numbers = get_next_box_suggestion(box_line["Box numbers"])
    else:
        st.session_state.pending_box_numbers = ""

    st.session_state.pending_clear_form = True


def save_pallet_details(pallet_header, start_next=False, index=None):
    if index is not None:
        st.session_state.pallets[index].update(pallet_header)
    else:
        existing_index = find_pallet_index_by_number(pallet_header["Pallet nr"])

        if existing_index is None:
            st.session_state.pallets.append(
                {
                    **pallet_header,
                    "items": [],
                }
            )
        else:
            st.session_state.pallets[existing_index].update(pallet_header)

    if start_next:
        next_pallet_nr = get_next_pallet_number()
        st.session_state.pending_pallet_details = {
            "input_pallet_nr": str(next_pallet_nr),
            "input_length": 120,
            "input_width": 80,
            "input_height": "",
            "input_weight": "",
            "input_pallet_comment": "",
        }
        st.session_state.pending_box_numbers = get_next_global_box_suggestion()
        st.session_state.entry_mode = "box"
        st.session_state.editing_pallet_index = None
        st.session_state.refresh_pallet_form_widgets = True
        st.session_state.active_pallet_nr = next_pallet_nr
    else:
        st.session_state.pending_pallet_details = {
            "input_pallet_nr": format_form_value(pallet_header["Pallet nr"]),
            "input_length": pallet_header["Length cm"],
            "input_width": pallet_header["Width cm"],
            "input_height": format_form_value(pallet_header["Height cm"]),
            "input_weight": format_form_value(pallet_header["Weight kg"]),
            "input_pallet_comment": pallet_header["Pallet comment"],
        }
        st.session_state.pending_box_numbers = ""
        st.session_state.entry_mode = "pallet"
        st.session_state.editing_pallet_index = None
        st.session_state.refresh_pallet_form_widgets = True
        st.session_state.active_pallet_nr = pallet_header["Pallet nr"]

    st.session_state.pending_clear_form = True


def start_next_pallet():
    next_pallet_nr = get_next_pallet_number()
    st.session_state.pending_pallet_details = {
        "input_pallet_nr": str(next_pallet_nr),
        "input_length": 120,
        "input_width": 80,
        "input_height": "",
        "input_weight": "",
        "input_pallet_comment": "",
    }
    st.session_state.pending_box_numbers = get_next_global_box_suggestion()
    st.session_state.entry_mode = "box"
    st.session_state.editing_pallet_index = None
    st.session_state.pending_clear_form = True
    st.session_state.active_pallet_nr = next_pallet_nr


def clear_form(keep_pallet_details=None, next_box_numbers=""):
    keep_pallet_details = keep_pallet_details or {}
    st.session_state.input_pallet_nr = keep_pallet_details.get("input_pallet_nr", "")
    st.session_state.input_length = keep_pallet_details.get("input_length", 120)
    st.session_state.input_width = keep_pallet_details.get("input_width", 80)
    st.session_state.input_height = keep_pallet_details.get("input_height", "")
    st.session_state.input_weight = keep_pallet_details.get("input_weight", "")
    st.session_state.input_pallet_comment = keep_pallet_details.get("input_pallet_comment", "")
    st.session_state.input_box_numbers = next_box_numbers
    st.session_state.input_pcs_per_box = ""
    st.session_state.input_art_nr = ""
    st.session_state.input_comment = ""
    st.session_state.editing_index = None
    st.session_state.editing_box_index = None
    st.session_state.editing_pallet_index = None

    pallet_nr, error = parse_optional_int_field(str(st.session_state.input_pallet_nr), default_value=1)
    if not error and pallet_nr >= 1:
        st.session_state.active_pallet_nr = pallet_nr


def reset_app_state():
    st.session_state.pallets = []
    st.session_state.editing_index = None
    st.session_state.editing_box_index = None
    st.session_state.pending_clear_form = False
    st.session_state.pending_pallet_details = {}
    st.session_state.pending_box_numbers = ""
    st.session_state.entry_mode = "box"
    st.session_state.editing_pallet_index = None
    st.session_state.refresh_pallet_form_widgets = True
    st.session_state.active_pallet_nr = 1

    for key, value in SESSION_DEFAULTS.items():
        st.session_state[key] = value

    st.session_state.pallet_form_pallet_nr = "1"
    st.session_state.pallet_form_weight = ""
    st.session_state.pallet_form_length = 120
    st.session_state.pallet_form_width = 80
    st.session_state.pallet_form_height = ""
    st.session_state.pallet_form_comment = ""
    st.session_state.show_purge_flash = True


def handle_reset_click():
    reset_app_state()
    persist_session_state()


def load_box_line_for_edit(index, box_index):
    pallet = st.session_state.pallets[index]
    box_line = pallet["items"][box_index]

    st.session_state.input_pallet_nr = format_form_value(pallet["Pallet nr"])
    st.session_state.input_length = pallet["Length cm"]
    st.session_state.input_width = pallet["Width cm"]
    st.session_state.input_height = format_form_value(pallet["Height cm"])
    st.session_state.input_weight = format_form_value(pallet["Weight kg"])
    st.session_state.input_pallet_comment = pallet.get("Pallet comment", "")
    st.session_state.input_box_numbers = box_line["Box numbers"]
    st.session_state.input_pcs_per_box = format_form_value(box_line["Pcs / box"])
    st.session_state.input_art_nr = box_line["Art. nr"]
    st.session_state.input_comment = box_line["Comment"]
    st.session_state.editing_index = index
    st.session_state.editing_box_index = box_index
    st.session_state.editing_pallet_index = None
    st.session_state.active_pallet_nr = pallet["Pallet nr"]


def load_pallet_details_for_edit(index):
    pallet = st.session_state.pallets[index]

    st.session_state.input_pallet_nr = format_form_value(pallet["Pallet nr"])
    st.session_state.input_length = pallet["Length cm"]
    st.session_state.input_width = pallet["Width cm"]
    st.session_state.input_height = format_form_value(pallet["Height cm"])
    st.session_state.input_weight = format_form_value(pallet["Weight kg"])
    st.session_state.input_pallet_comment = pallet.get("Pallet comment", "")
    st.session_state.editing_index = None
    st.session_state.editing_box_index = None
    st.session_state.editing_pallet_index = index
    st.session_state.entry_mode = "pallet"
    st.session_state.refresh_pallet_form_widgets = True
    st.session_state.active_pallet_nr = pallet["Pallet nr"]


def flatten_pallet_rows():
    rows = []

    for pallet in st.session_state.pallets:
        for box_line in pallet["items"]:
            rows.append(
                {
                    "Pallet nr": pallet["Pallet nr"],
                    "Length cm": pallet["Length cm"],
                    "Width cm": pallet["Width cm"],
                    "Height cm": pallet["Height cm"],
                    "Weight kg": pallet["Weight kg"],
                    "Pallet comment": pallet.get("Pallet comment", ""),
                    "Box numbers": box_line["Box numbers"],
                    "Pcs / box": box_line["Pcs / box"],
                    "Art. nr": box_line["Art. nr"],
                    "Article name": box_line.get("Article name", ""),
                    "Comment": box_line["Comment"],
                }
            )

    return rows


def flatten_pallet_rows_for_export():
    rows = []
    today_label = date.today().isoformat()
    blank_row = {
        "Pallet nr": None,
        "Length cm": None,
        "Width cm": None,
        "Height cm": None,
        "Weight kg": None,
        "Pallet comment": None,
        "Box numbers": None,
        "Pcs / box": None,
        "Art. nr": None,
        "Article name": None,
        "Date": None,
        "Comment": None,
        "Initials / name": None,
    }

    for pallet_index, pallet in enumerate(st.session_state.pallets):
        box_lines = pallet["items"] or [None]

        for box_index, box_line in enumerate(box_lines):
            is_first_line_of_pallet = box_index == 0
            is_first_export_row = len(rows) == 0
            rows.append(
                {
                    "Pallet nr": pallet["Pallet nr"] if is_first_line_of_pallet else None,
                    "Length cm": pallet["Length cm"] if is_first_line_of_pallet else None,
                    "Width cm": pallet["Width cm"] if is_first_line_of_pallet else None,
                    "Height cm": pallet["Height cm"] if is_first_line_of_pallet else None,
                    "Weight kg": pallet["Weight kg"] if is_first_line_of_pallet else None,
                    "Pallet comment": pallet.get("Pallet comment", "") if is_first_line_of_pallet else None,
                    "Box numbers": box_line["Box numbers"] if box_line else None,
                    "Pcs / box": box_line["Pcs / box"] if box_line else None,
                    "Art. nr": box_line["Art. nr"] if box_line else None,
                    "Article name": box_line.get("Article name", "") if box_line else None,
                    "Date": today_label if is_first_export_row else None,
                    "Comment": box_line["Comment"] if box_line else None,
                    "Initials / name": st.session_state.input_operator_name.strip() if is_first_export_row else None,
                }
            )

        if pallet_index < len(st.session_state.pallets) - 1:
            rows.append(blank_row.copy())

    return rows


def flatten_rows_for_pallet(pallet_nr):
    rows = []
    pallet_index = find_pallet_index_by_number(pallet_nr)

    if pallet_index is None:
        return rows

    pallet = st.session_state.pallets[pallet_index]
    for box_line in pallet["items"]:
        rows.append(
                {
                    "Pallet nr": pallet["Pallet nr"],
                    "Length cm": pallet["Length cm"],
                    "Width cm": pallet["Width cm"],
                    "Height cm": pallet["Height cm"],
                    "Weight kg": pallet["Weight kg"],
                    "Pallet comment": pallet.get("Pallet comment", ""),
                    "Box numbers": box_line["Box numbers"],
                    "Pcs / box": box_line["Pcs / box"],
                    "Art. nr": box_line["Art. nr"],
                    "Article name": box_line.get("Article name", ""),
                    "Comment": box_line["Comment"],
                }
            )

    return rows


def flatten_rows_for_box_export(pallet_nr):
    return flatten_rows_for_box_export_with_pending(pallet_nr)


def flatten_rows_for_box_export_with_pending(pallet_nr, pending_box_line=None):
    rows = []
    pallet_index = find_pallet_index_by_number(pallet_nr)
    today_label = date.today().isoformat()
    order_id = st.session_state.input_order_id.strip() or None
    operator_name = st.session_state.input_operator_name.strip() or None
    pallet = None
    if pallet_index is not None:
        pallet = st.session_state.pallets[pallet_index]

    box_lines = []
    if pallet is not None:
        box_lines.extend(pallet["items"])
    if pending_box_line is not None:
        box_lines.append(pending_box_line)

    if not box_lines:
        return rows

    weight_value = None
    if pallet is not None:
        weight_value = pallet.get("Weight kg")
        if weight_value in ("", None, 0, 0.0):
            weight_value = None

    for box_line in box_lines:
        rows.append(
            {
                "Box nr": box_line["Box numbers"],
                "Weight kg": weight_value,
                "Order ID": order_id,
                "Pcs / box": box_line["Pcs / box"],
                "Art. nr": box_line["Art. nr"],
                "Article name": box_line.get("Article name", ""),
                "Date": today_label,
                "Comment": box_line["Comment"] or None,
                "Initials / name": operator_name,
            }
        )

    return rows


def get_pending_box_line_state():
    has_unsaved_box_input = any(
        [
            st.session_state.input_box_numbers.strip(),
            st.session_state.input_pcs_per_box.strip(),
            st.session_state.input_art_nr.strip(),
            st.session_state.input_comment.strip(),
        ]
    )
    if not has_unsaved_box_input:
        return None, None, False

    pending_box_line, error = get_validated_box_line_data()
    if error:
        return None, error, True

    is_editing_existing_row = (
        st.session_state.editing_index is not None and st.session_state.editing_box_index is not None
    )
    if is_editing_existing_row:
        return None, None, False

    existing_rows = flatten_rows_for_pallet(get_current_pallet_number())
    for row in existing_rows:
        if (
            row["Box numbers"] == pending_box_line["Box numbers"]
            and row["Pcs / box"] == pending_box_line["Pcs / box"]
            and row["Art. nr"] == pending_box_line["Art. nr"]
            and row.get("Article name", "") == pending_box_line.get("Article name", "")
            and row["Comment"] == pending_box_line["Comment"]
        ):
            return None, None, False

    return pending_box_line, None, True


def normalize_pallets():
    normalized = []

    for pallet in st.session_state.pallets:
        if "items" in pallet:
            normalized_items = []
            for box_line in pallet["items"]:
                normalized_items.append(
                    {
                        "Box numbers": box_line["Box numbers"],
                        "Pcs / box": box_line["Pcs / box"],
                        "Art. nr": box_line["Art. nr"],
                        "Article name": box_line.get("Article name", ""),
                        "Comment": box_line["Comment"],
                    }
                )

            normalized.append(
                {
                    **pallet,
                    "Pallet comment": pallet.get("Pallet comment", ""),
                    "items": normalized_items,
                }
            )
            continue

        existing_index = None
        for index, existing_pallet in enumerate(normalized):
            if existing_pallet["Pallet nr"] == pallet["Pallet nr"]:
                existing_index = index
                break

        box_line = {
            "Box numbers": pallet["Box numbers"],
            "Pcs / box": pallet["Pcs / box"],
            "Art. nr": pallet["Art. nr"],
            "Article name": pallet.get("Article name", ""),
            "Comment": pallet["Comment"],
        }

        if existing_index is None:
            normalized.append(
                {
                    "Pallet nr": pallet["Pallet nr"],
                    "Length cm": pallet["Length cm"],
                    "Width cm": pallet["Width cm"],
                    "Height cm": pallet["Height cm"],
                    "Weight kg": pallet["Weight kg"],
                    "Pallet comment": pallet.get("Pallet comment", ""),
                    "items": [box_line],
                }
            )
        else:
            normalized[existing_index]["items"].append(box_line)

    st.session_state.pallets = normalized


def create_excel_file():
    df = pd.DataFrame(flatten_pallet_rows_for_export())

    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Pallets")
    except ModuleNotFoundError as exc:
        if exc.name == "openpyxl":
            raise RuntimeError("Excel export requires the openpyxl package to be installed.") from exc
        raise

    output.seek(0)
    return output


def create_box_excel_file(pallet_nr, pending_box_line=None):
    df = pd.DataFrame(
        flatten_rows_for_box_export_with_pending(pallet_nr, pending_box_line=pending_box_line),
        columns=[
            "Box nr",
            "Weight kg",
            "Order ID",
            "Pcs / box",
            "Art. nr",
            "Article name",
            "Date",
            "Comment",
            "Initials / name",
        ],
    )

    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Boxes")
    except ModuleNotFoundError as exc:
        if exc.name == "openpyxl":
            raise RuntimeError("Excel export requires the openpyxl package to be installed.") from exc
        raise

    output.seek(0)
    return output


def build_box_excel_filename(pallet_nr):
    today_label = date.today().isoformat()
    operator_name = st.session_state.input_operator_name.strip()
    safe_operator_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", operator_name).strip().rstrip(".")

    filename = f"Box_{pallet_nr}_{today_label}"
    if safe_operator_name:
        filename = f"{filename}_{safe_operator_name}"

    return f"{filename}.xlsx"


def build_excel_filename():
    operator_name = st.session_state.input_operator_name.strip()
    first_comment = st.session_state.pallets[0].get("Pallet comment", "").strip()
    safe_operator_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", operator_name).strip().rstrip(".")
    safe_comment = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", first_comment).strip().rstrip(".")

    if not safe_comment:
        safe_comment = "pallet_report"

    pallet_count = len(st.session_state.pallets)
    pallet_label = "pallet" if pallet_count == 1 else "pallets"
    today_label = date.today().isoformat()

    filename = f"{safe_comment} {pallet_count} {pallet_label} {today_label}"
    if safe_operator_name:
        filename = f"{filename} {safe_operator_name}"

    return f"{filename}.xlsx"


def total_weight():
    return sum(float(pallet["Weight kg"]) for pallet in st.session_state.pallets)


def total_box_lines():
    return sum(len(pallet["items"]) for pallet in st.session_state.pallets)


def total_box_lines_for_pallet(pallet_nr):
    pallet_index = find_pallet_index_by_number(pallet_nr)
    if pallet_index is None:
        return 0
    return len(st.session_state.pallets[pallet_index]["items"])


def total_pcs():
    return sum(box_line["Pcs / box"] for pallet in st.session_state.pallets for box_line in pallet["items"])


def build_summary_text():
    lines = [
        "Pallet report",
        f"Pallets: {len(st.session_state.pallets)}",
        f"Box rows: {total_box_lines()}",
        f"Total pieces: {total_pcs()}",
        f"Total weight: {total_weight():.1f} kg",
        "",
    ]

    for pallet in st.session_state.pallets:
        lines.append(
            f"Pallet {pallet['Pallet nr']} | "
            f"{pallet['Length cm']} x {pallet['Width cm']} x {pallet['Height cm']} cm | "
            f"{pallet['Weight kg']} kg"
        )
        if pallet.get("Pallet comment"):
            lines.append(f"- Pallet comment: {pallet['Pallet comment']}")
        for box_line in pallet["items"]:
            lines.append(
                f"- Box {box_line['Box numbers']} | "
                f"{box_line['Pcs / box']} pcs/box | "
                f"Art. nr {box_line['Art. nr']}"
                + (f" | {box_line.get('Article name', '')}" if box_line.get("Article name") else "")
                + (f" | {box_line['Comment']}" if box_line["Comment"] else "")
            )
        lines.append("")

    return "\n".join(lines).strip()


def current_pallet_preview():
    pallet_nr = st.session_state.input_pallet_nr.strip() or "Not set yet"
    weight = st.session_state.input_weight.strip() or "Not set yet"
    height = st.session_state.input_height.strip() or "Not set yet"

    return (
        f"Pallet nr: {pallet_nr}<br>"
        f"Size: {st.session_state.input_length} x {st.session_state.input_width} x {height} cm<br>"
        f"Weight: {weight} kg"
    )


def summary_card(label, value, help_text):
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
            <div class="summary-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_purge_flash():
    st.markdown(
        """
        <div class="purge-flash">
            <div class="purge-flash-card">
                <div class="purge-flash-top">
                    <div class="purge-flash-title">Purge complete</div>
                    <div class="purge-flash-copy">The pallet draft has been burned down to clean ashes.</div>
                </div>
                <div class="purge-flash-fireline">🔥 🔥 🔥 🔥 🔥 🔥 🔥 🔥 🔥</div>
                <div class="purge-flash-ash">Fresh start mode activated.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

ensure_draft_key()
restore_persisted_session_state()

if "pallets" not in st.session_state:
    st.session_state.pallets = []

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

if "editing_box_index" not in st.session_state:
    st.session_state.editing_box_index = None

if "pending_clear_form" not in st.session_state:
    st.session_state.pending_clear_form = False

if "pending_pallet_details" not in st.session_state:
    st.session_state.pending_pallet_details = {}

if "pending_box_numbers" not in st.session_state:
    st.session_state.pending_box_numbers = ""

if "entry_mode" not in st.session_state:
    st.session_state.entry_mode = "box"

if "editing_pallet_index" not in st.session_state:
    st.session_state.editing_pallet_index = None

if "refresh_pallet_form_widgets" not in st.session_state:
    st.session_state.refresh_pallet_form_widgets = True

if "active_pallet_nr" not in st.session_state:
    st.session_state.active_pallet_nr = 1


for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

for key in ["input_pallet_nr", "input_height", "input_weight", "input_pcs_per_box"]:
    if not isinstance(st.session_state[key], str):
        st.session_state[key] = format_form_value(st.session_state[key])

normalize_pallets()

if st.session_state.pending_clear_form:
    clear_form(st.session_state.pending_pallet_details, st.session_state.pending_box_numbers)
    st.session_state.pending_clear_form = False
    st.session_state.pending_pallet_details = {}
    st.session_state.pending_box_numbers = ""

if not st.session_state.input_pallet_nr.strip():
    st.session_state.input_pallet_nr = "1"

if st.session_state.editing_index is not None:
    st.session_state.entry_mode = "box"

if is_box_order_mode():
    st.session_state.entry_mode = "box"
    st.session_state.editing_pallet_index = None
    st.session_state.input_pallet_nr = "1"
    st.session_state.active_pallet_nr = 1


inject_styles()

if st.session_state.get("show_purge_flash"):
    render_purge_flash()
    st.session_state.show_purge_flash = False

st.markdown(
    """
    <div class="hero-panel">
        <div class="hero-eyebrow">Warehouse tool</div>
        <h1>Pallet Report</h1>
        <p class="hero-text">
            Add pallet details, review the list, and export everything to Excel when it is ready.
        </p>
        <p class="hero-text">Your current draft is saved automatically and restored after a refresh.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

previous_order_type = st.session_state.order_type
if is_box_order_mode():
    identity_col1, identity_col2, identity_col3 = st.columns([1.1, 1.1, 1], gap="large")
    with identity_col1:
        st.text_input(
            "Initials / name",
            placeholder="",
            key="input_operator_name",
        )
    with identity_col2:
        st.text_input(
            "Order ID",
            placeholder="",
            key="input_order_id",
        )
    with identity_col3:
        st.radio(
            "Order type",
            options=["pallet", "box"],
            format_func=lambda value: "Pallet order" if value == "pallet" else "Box order",
            horizontal=True,
            key="order_type",
        )
else:
    identity_col1, identity_col2 = st.columns([1.25, 1], gap="large")
    with identity_col1:
        st.text_input(
            "Initials / name",
            placeholder="",
            key="input_operator_name",
        )
    with identity_col2:
        st.radio(
            "Order type",
            options=["pallet", "box"],
            format_func=lambda value: "Pallet order" if value == "pallet" else "Box order",
            horizontal=True,
            key="order_type",
        )

handle_order_type_change(previous_order_type)

overview_col1, overview_col2, overview_col3 = st.columns(3)
with overview_col1:
    summary_card(
        "Pallets in list" if not is_box_order_mode() else "Orders in list",
        len(st.session_state.pallets),
        "Current number of saved pallets" if not is_box_order_mode() else "Current number of saved box orders",
    )
with overview_col2:
    summary_card(
        "Box rows in list",
        total_box_lines(),
        "Lines saved across all pallets" if not is_box_order_mode() else "Lines saved across all box orders",
    )
with overview_col3:
    summary_card(
        "Total weight" if not is_box_order_mode() else "Total pieces",
        f"{total_weight():.1f} kg" if not is_box_order_mode() else total_pcs(),
        "Combined weight of all pallets" if not is_box_order_mode() else "Combined pieces across all box rows",
    )

st.markdown(
    '<p class="section-note">'
    + (
        "Simple workflow: add the box rows, finish pallet details, then download the Excel file."
        if not is_box_order_mode()
        else "Simple workflow: add the box rows and export the box order Excel file when it is ready."
    )
    + "</p>",
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([0.8, 2.4], gap="large")

with left_col:
    st.button(
        "Reset all form data",
        type="primary",
        use_container_width=True,
        on_click=handle_reset_click,
    )

    st.markdown(
        """
        <div class="side-panel">
            <div class="side-heading">Shipment Summary</div>
            <div class="side-copy">"""
        + (
            "Keep an eye on what is already added and export from here when the pallet work is done."
            if not is_box_order_mode()
            else "Keep an eye on what is already added and export the box order when it is ready."
        )
        + """</div>
            <div class="side-stat">
                <strong>"""
        + ("Pallets" if not is_box_order_mode() else "Orders")
        + """</strong>
                <span>"""
        + str(len(st.session_state.pallets))
        + """ saved</span>
            </div>
            <div class="side-stat">
                <strong>Box Rows</strong>
                <span>"""
        + str(total_box_lines())
        + """ rows in total</span>
            </div>
            <div class="side-stat">
                <strong>Total Weight</strong>
                <span>"""
        + f"{total_weight():.1f} kg"
        + """</span>
            </div>
            <div class="side-stat">
                <strong>Total Pieces</strong>
                <span>"""
        + str(total_pcs())
        + """ pcs</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.pallets:
        summary_text = build_summary_text()
        if not is_box_order_mode():
            try:
                excel_file = create_excel_file()
            except RuntimeError as exc:
                st.warning(str(exc))
                excel_file = None

            if excel_file is not None:
                st.download_button(
                    label="Download Excel file",
                    data=excel_file,
                    file_name=build_excel_filename(),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

        st.download_button(
            label="Download summary text",
            data=summary_text,
            file_name="pallet_summary.txt",
            mime="text/plain",
            use_container_width=True,
        )

        with st.expander("Share-ready summary", expanded=False):
            st.text_area(
                "Summary text",
                value=summary_text,
                height=240,
                disabled=True,
                label_visibility="collapsed",
            )

        if not is_box_order_mode():
            st.markdown(
                """
                <div class="side-panel">
                    <div class="side-heading">Pallet Overview</div>
                    <div class="side-copy">Quick scan of what has been entered so far.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for pallet in st.session_state.pallets:
                st.markdown(
                    f"""
                    <div class="pallet-chip">
                        <div class="pallet-chip-title">Pallet {pallet['Pallet nr']}</div>
                        <div class="pallet-chip-copy">
                            {pallet['Length cm']} x {pallet['Width cm']} x {pallet['Height cm']} cm |
                            {pallet['Weight kg']} kg |
                            {len(pallet['items'])} box rows
                        </div>
                        <div class="pallet-chip-copy">
                            {pallet.get('Pallet comment', '-') or '-'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("The export buttons will appear here after the first pallet is added.")

with right_col:
    list_container = st.container(border=True)
    with list_container:
        st.subheader("Saved pallets" if not is_box_order_mode() else "Saved box rows")

        if st.session_state.pallets:
            st.caption(
                "Each pallet keeps its shared details once, with the box rows stored underneath."
                if not is_box_order_mode()
                else "Review the saved box rows here."
            )

            for i, pallet in enumerate(st.session_state.pallets):
                title = (
                    f"Pallet {pallet['Pallet nr']} | "
                    f"{pallet['Length cm']} x {pallet['Width cm']} x {pallet['Height cm']} cm | "
                    f"{len(pallet['items'])} box rows"
                ) if not is_box_order_mode() else f"Box order | {len(pallet['items'])} box rows"

                with st.expander(title, expanded=False):
                    if not is_box_order_mode():
                        info_col1, info_col2, info_col3 = st.columns(3)

                        with info_col1:
                            st.markdown("**Pallet size**")
                            st.write(f"{pallet['Length cm']} x {pallet['Width cm']} x {pallet['Height cm']} cm")

                        if not is_standard_pallet_size(pallet["Length cm"], pallet["Width cm"]):
                            st.markdown(
                                pallet_size_notice_markup(pallet["Length cm"], pallet["Width cm"]),
                                unsafe_allow_html=True,
                            )

                        with info_col2:
                            st.markdown("**Weight**")
                            st.write(f"{pallet['Weight kg']} kg")

                        with info_col3:
                            st.markdown("**Pallet nr**")
                            st.write(pallet["Pallet nr"])

                        st.markdown("**Pallet comment**")
                        st.write(pallet.get("Pallet comment", "") or "-")

                        action_head_col1, action_head_col2 = st.columns(2)
                        with action_head_col1:
                            if st.button("Edit pallet", key=f"edit_pallet_{i}", use_container_width=True):
                                load_pallet_details_for_edit(i)
                                persist_and_rerun()
                        with action_head_col2:
                            st.write("")

                st.markdown("**Box rows**")

                for box_i, box_line in enumerate(pallet["items"]):
                    row_col1, row_col2, row_col3, row_col4, row_col5 = st.columns([2.4, 1.5, 1.8, 2.4, 1.6])

                    with row_col1:
                        st.markdown("**Box numbers**")
                        st.write(box_line["Box numbers"])

                    with row_col2:
                        st.markdown("**Pcs / box**")
                        st.write(box_line["Pcs / box"])

                    with row_col3:
                        st.markdown("**Art. nr**")
                        st.write(box_line["Art. nr"])
                        if box_line.get("Article name"):
                            st.caption(box_line["Article name"])

                    with row_col4:
                        st.markdown("**Comment**")
                        st.write(box_line["Comment"] or "-")

                    with row_col5:
                        if st.button("Edit row", key=f"edit_{i}_{box_i}", use_container_width=True):
                            load_box_line_for_edit(i, box_i)
                            persist_and_rerun()

                        if st.button("Delete row", key=f"delete_{i}_{box_i}", use_container_width=True):
                            st.session_state.pallets[i]["items"].pop(box_i)
                            if not st.session_state.pallets[i]["items"]:
                                st.session_state.pallets.pop(i)
                            clear_form()
                            persist_and_rerun()

                    st.divider()

                if st.button(
                    "Remove whole pallet" if not is_box_order_mode() else "Clear saved box rows",
                    key=f"delete_pallet_{i}",
                    use_container_width=True,
                ):
                    st.session_state.pallets.pop(i)
                    clear_form()
                    persist_and_rerun()
        else:
            st.info("No pallets added yet. Start with the form below.")


    form_container = st.container(border=True)
    with form_container:
        current_pallet_nr = get_current_pallet_number()

        if st.session_state.entry_mode == "box":
            if st.session_state.editing_index is None:
                st.subheader(
                    f"Add box rows to pallet {current_pallet_nr}"
                    if not is_box_order_mode()
                    else "Add box rows"
                )
                st.caption(
                    "This step only shows box rows. When the pallet is finished, switch to pallet details."
                    if not is_box_order_mode()
                    else "This mode only uses box rows. Pallet details are hidden."
                )
            else:
                st.subheader(
                    f"Edit box row on pallet {current_pallet_nr}"
                    if not is_box_order_mode()
                    else "Edit box row"
                )
                st.caption(
                    "Update the selected row here. Pallet details stay in their own separate step."
                    if not is_box_order_mode()
                    else "Update the selected box row here."
                )

            workflow_markup = '<div class="workflow-band"><div class="workflow-pill">1. Add all box rows</div>'
            if not is_box_order_mode():
                workflow_markup += (
                    '<div class="workflow-pill">2. Switch to pallet details</div>'
                    '<div class="workflow-pill">3. Save and move to the next pallet</div>'
                )
            else:
                workflow_markup += (
                    '<div class="workflow-pill">2. Review the box order</div>'
                    '<div class="workflow-pill">3. Export the box Excel file</div>'
                )
            workflow_markup += "</div>"
            st.markdown(workflow_markup, unsafe_allow_html=True)

            preview_lines = []
            if not is_box_order_mode():
                preview_lines.append(f"Working on pallet {current_pallet_nr}")
            preview_lines.append(f"Box rows already added: {total_box_lines_for_pallet(current_pallet_nr)}")
            preview_lines.append(
                f"Next box suggestion: {st.session_state.input_box_numbers or 'Start with the first box row'}"
            )
            preview_value_markup = "<br>".join(preview_lines)
            st.markdown(
                (
                    '<div class="preview-panel">'
                    '<div class="preview-label">Current Box Step</div>'
                    f'<div class="preview-value">{preview_value_markup}</div>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

            st.markdown("#### Box details")
            detail_col1, detail_col2, detail_col3 = st.columns(3)

            with detail_col1:
                st.text_input(
                    "Box numbers",
                    placeholder="Example: 1-5 or 1,2,3,8-10",
                    key="input_box_numbers",
                )

            with detail_col2:
                st.text_input(
                    "Pcs / box",
                    placeholder="Example: 20",
                    key="input_pcs_per_box",
                )

            with detail_col3:
                st.text_input(
                    "Art. nr",
                    placeholder="Example: 12345",
                    key="input_art_nr",
                )

            current_article_name, article_lookup_message, article_lookup_tone = get_article_name_state(
                st.session_state.input_art_nr,
                fallback_name=get_saved_article_name_for_current_row(),
            )
            st.text_input(
                "Article name",
                value=current_article_name,
                placeholder="Filled automatically from Lark",
                disabled=True,
            )
            if article_lookup_message:
                st.markdown(
                    article_lookup_note_markup(article_lookup_message, article_lookup_tone),
                    unsafe_allow_html=True,
                )

            st.text_area(
                "Comment / note",
                placeholder="Optional information for the warehouse or booking",
                key="input_comment",
            )

            primary_label = "Add box row"
            if st.session_state.editing_index is not None:
                primary_label = "Save changes"

            if st.button(primary_label, type="primary", use_container_width=True, key="submit_box_row_button"):
                pallet_data, error = get_validated_form_data()
                if error:
                    st.warning(error)
                else:
                    save_pallet(
                        pallet_data,
                        st.session_state.editing_index,
                        st.session_state.editing_box_index,
                    )
                    persist_and_rerun()

            if st.button("Clear box fields", use_container_width=True, key="clear_box_fields_button"):
                st.session_state.pending_pallet_details = capture_pallet_detail_inputs()
                st.session_state.pending_box_numbers = ""
                st.session_state.pending_clear_form = True
                persist_and_rerun()

            pending_box_line, pending_box_error, has_pending_box_input = get_pending_box_line_state()
            current_box_rows = flatten_rows_for_box_export_with_pending(
                current_pallet_nr,
                pending_box_line=pending_box_line,
            )
            box_excel_file = None
            if current_box_rows:
                try:
                    box_excel_file = create_box_excel_file(current_pallet_nr, pending_box_line=pending_box_line)
                except RuntimeError as exc:
                    st.warning(str(exc))

            if is_box_order_mode():
                export_clicked = st.download_button(
                    label="Export box order Excel",
                    data=box_excel_file if box_excel_file is not None else b"",
                    file_name=build_box_excel_filename(current_pallet_nr),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    disabled=box_excel_file is None,
                )
                if export_clicked and pending_box_line is not None:
                    pallet_header, header_error = get_validated_pallet_header_data()
                    if header_error is None:
                        save_pallet(
                            {**pallet_header, **pending_box_line},
                            st.session_state.editing_index,
                            st.session_state.editing_box_index,
                        )
                        persist_session_state()
                st.caption("Use this when all box rows for the order are entered.")
            else:
                switch_col1, switch_col2 = st.columns([1, 1])
                with switch_col1:
                    if st.button("Ready to add pallet details", type="primary", use_container_width=True):
                        st.session_state.editing_pallet_index = find_pallet_index_by_number(current_pallet_nr)
                        st.session_state.entry_mode = "pallet"
                        st.session_state.refresh_pallet_form_widgets = True
                        ensure_visible_pallet_defaults(current_pallet_nr)
                        persist_and_rerun()
                with switch_col2:
                    st.caption("Use this when all box rows for the current pallet are entered.")

        else:
            initialize_pallet_form_widgets(current_pallet_nr)
            st.subheader(f"Add pallet details for pallet {current_pallet_nr}")
            st.caption("The box section is hidden in this step so you can finish the pallet cleanly.")

            st.markdown(
                f"""
                <div class="preview-panel">
                    <div class="preview-label">Current Pallet Step</div>
                    <div class="preview-value">
                        Pallet {current_pallet_nr}<br>
                        Box rows waiting on this pallet: {total_box_lines_for_pallet(current_pallet_nr)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("pallet_details_form"):
                top_col1, top_col2 = st.columns([1, 1])

                with top_col1:
                    st.text_input(
                        "Pallet nr",
                        placeholder="Example: 1",
                        key="pallet_form_pallet_nr",
                    )

                with top_col2:
                    st.text_input(
                        "Weight kg",
                        placeholder="Example: 263",
                        key="pallet_form_weight",
                    )

                st.markdown('<div class="small-label">Pallet size (cm)</div>', unsafe_allow_html=True)
                size_col1, size_col2 = st.columns(2)

                with size_col1:
                    st.number_input("Length", min_value=0, step=1, key="pallet_form_length")

                with size_col2:
                    st.number_input("Width", min_value=0, step=1, key="pallet_form_width")

                st.text_input("Height", placeholder="Amazon MAX 180 cm", key="pallet_form_height")

                st.text_area(
                    "Pallet comment",
                    placeholder="Optional note for this whole pallet",
                    key="pallet_form_comment",
                )

                st.markdown(
                    pallet_size_notice_markup(st.session_state.pallet_form_length, st.session_state.pallet_form_width),
                    unsafe_allow_html=True,
                )

                save_and_next = st.form_submit_button(
                    "Save and start next pallet",
                    type="primary",
                    use_container_width=True,
                )

                action_col1, action_col2 = st.columns(2)

                with action_col1:
                    save_only = st.form_submit_button(
                        "Save pallet details",
                        use_container_width=True,
                    )

                with action_col2:
                    back_to_boxes = st.form_submit_button(
                        "Back to box rows",
                        use_container_width=True,
                    )

                if save_only:
                    sync_inputs_from_pallet_form_widgets()
                    pallet_header, error = get_validated_pallet_header_data()
                    if error:
                        st.warning(error)
                    else:
                        save_pallet_details(
                            pallet_header,
                            index=get_active_pallet_index_for_details(current_pallet_nr),
                        )
                        persist_and_rerun()

                if save_and_next:
                    sync_inputs_from_pallet_form_widgets()
                    pallet_header, error = get_validated_pallet_header_data()
                    if error:
                        st.warning(error)
                    else:
                        save_pallet_details(
                            pallet_header,
                            start_next=True,
                            index=get_active_pallet_index_for_details(current_pallet_nr),
                        )
                        persist_and_rerun()

                if back_to_boxes:
                    sync_inputs_from_pallet_form_widgets()
                    st.session_state.editing_pallet_index = None
                    st.session_state.entry_mode = "box"
                    persist_and_rerun()


    if st.session_state.pallets:
        export_container = st.container(border=True)
        with export_container:
            review_pallet_nr = get_current_pallet_number()
            review_rows = flatten_rows_for_pallet(review_pallet_nr)

            st.subheader("Current Pallet Review" if not is_box_order_mode() else "Current Box Order Review")
            st.caption(
                f"Review for current pallet {review_pallet_nr}. When you move to the next pallet, this list starts empty."
                if not is_box_order_mode()
                else "Review for the current box order."
            )

            if review_rows:
                df = pd.DataFrame(review_rows)
                preview_df = df[["Box numbers", "Pcs / box", "Art. nr", "Comment"]]
                st.dataframe(
                    preview_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No box rows added for the current pallet yet.")

persist_session_state()
