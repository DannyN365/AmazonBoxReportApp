import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote

import requests
import streamlit as st

DEFAULT_LARK_API_BASE_URL = "https://open.feishu.cn/open-apis"
DEFAULT_LARK_LOOKUP_RANGE = "A:B"
DEFAULT_LARK_HEADER_ROWS = 1
DEFAULT_LARK_ARTICLE_NR_COLUMN_INDEX = 0
DEFAULT_LARK_ARTICLE_NAME_COLUMN_INDEX = 1
DEFAULT_LARK_SOURCE_TYPE = "bitable"
LOCAL_CATALOG_CACHE_PATH = Path(__file__).with_name(".lark_article_catalog_cache.json")
LOCAL_CATALOG_CACHE_TTL_SECONDS = 3600
REPO_ARTICLE_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "article_catalog.json"


def get_secret_value(name, default=""):
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default

    return value if value not in (None, "") else default


def get_int_setting(name, default_value):
    raw_value = str(get_secret_value(name, "")).strip()
    if not raw_value:
        return default_value

    try:
        return int(raw_value)
    except ValueError:
        return default_value


def normalize_article_number(value):
    normalized = str(value).strip()
    if not normalized:
        return ""

    if re.fullmatch(r"\d+\.0+", normalized):
        return normalized.split(".", 1)[0]

    return normalized


def build_local_catalog_cache_key(source_type, parts):
    normalized_parts = [source_type]
    normalized_parts.extend(str(part).strip() for part in parts)
    return "|".join(normalized_parts)


def load_local_catalog_cache(cache_key):
    if not LOCAL_CATALOG_CACHE_PATH.exists():
        return None

    try:
        with LOCAL_CATALOG_CACHE_PATH.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    entry = payload.get(cache_key)
    if not isinstance(entry, dict):
        return None

    cached_at = entry.get("cached_at", 0)
    if not isinstance(cached_at, (int, float)):
        return None

    if time.time() - float(cached_at) > LOCAL_CATALOG_CACHE_TTL_SECONDS:
        return None

    return entry.get("data")


def save_local_catalog_cache(cache_key, data):
    payload = {}
    if LOCAL_CATALOG_CACHE_PATH.exists():
        try:
            with LOCAL_CATALOG_CACHE_PATH.open("r", encoding="utf-8") as cache_file:
                existing_payload = json.load(cache_file)
            if isinstance(existing_payload, dict):
                payload = existing_payload
        except (OSError, json.JSONDecodeError):
            payload = {}

    payload[cache_key] = {
        "cached_at": time.time(),
        "data": data,
    }

    try:
        with LOCAL_CATALOG_CACHE_PATH.open("w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file, ensure_ascii=True, indent=2)
    except OSError:
        pass


def load_repo_article_catalog(path=None):
    catalog_path = Path(path) if path else REPO_ARTICLE_CATALOG_PATH
    if not catalog_path.exists():
        return None

    try:
        with catalog_path.open("r", encoding="utf-8") as catalog_file:
            payload = json.load(catalog_file)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    catalog = payload.get("catalog")
    if not isinstance(catalog, dict):
        return None

    return payload


def save_repo_article_catalog(payload, path=None):
    catalog_path = Path(path) if path else REPO_ARTICLE_CATALOG_PATH
    catalog_path.parent.mkdir(parents=True, exist_ok=True)

    with catalog_path.open("w", encoding="utf-8") as catalog_file:
        json.dump(payload, catalog_file, ensure_ascii=True, indent=2, sort_keys=True)


def flatten_bitable_value(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float)):
        return str(value).strip()

    if isinstance(value, list):
        flattened_parts = []
        for item in value:
            flattened_item = flatten_bitable_value(item)
            if flattened_item:
                flattened_parts.append(flattened_item)
        return ", ".join(flattened_parts).strip()

    if isinstance(value, dict):
        for key in ["text", "name", "value", "label"]:
            if key in value:
                flattened_value = flatten_bitable_value(value.get(key))
                if flattened_value:
                    return flattened_value

        if "id" in value:
            return str(value.get("id", "")).strip()

    return str(value).strip()


def get_lark_lookup_config():
    config = {
        "api_base_url": str(
            get_secret_value("LARK_API_BASE_URL", DEFAULT_LARK_API_BASE_URL)
        ).strip().rstrip("/"),
        "source_type": str(get_secret_value("LARK_SOURCE_TYPE", DEFAULT_LARK_SOURCE_TYPE)).strip().lower(),
        "app_id": str(get_secret_value("LARK_APP_ID", "")).strip(),
        "app_secret": str(get_secret_value("LARK_APP_SECRET", "")).strip(),
        "spreadsheet_token": str(get_secret_value("LARK_PIM_SPREADSHEET_TOKEN", "")).strip(),
        "sheet_id": str(get_secret_value("LARK_PIM_SHEET_ID", "")).strip(),
        "lookup_range": str(get_secret_value("LARK_PIM_LOOKUP_RANGE", DEFAULT_LARK_LOOKUP_RANGE)).strip(),
        "base_app_token": str(get_secret_value("LARK_BASE_APP_TOKEN", "")).strip(),
        "base_table_id": str(get_secret_value("LARK_BASE_TABLE_ID", "")).strip(),
        "article_nr_field_id": str(get_secret_value("LARK_BASE_ARTICLE_NR_FIELD_ID", "")).strip(),
        "article_name_field_id": str(get_secret_value("LARK_BASE_ARTICLE_NAME_FIELD_ID", "")).strip(),
        "header_rows": get_int_setting("LARK_PIM_HEADER_ROWS", DEFAULT_LARK_HEADER_ROWS),
        "article_nr_column_index": get_int_setting(
            "LARK_PIM_ARTICLE_NR_COLUMN_INDEX", DEFAULT_LARK_ARTICLE_NR_COLUMN_INDEX
        ),
        "article_name_column_index": get_int_setting(
            "LARK_PIM_ARTICLE_NAME_COLUMN_INDEX", DEFAULT_LARK_ARTICLE_NAME_COLUMN_INDEX
        ),
    }
    config["sheet_enabled"] = all(
        [
            config["app_id"],
            config["app_secret"],
            config["spreadsheet_token"],
            config["sheet_id"],
        ]
    )
    config["bitable_enabled"] = all(
        [
            config["app_id"],
            config["app_secret"],
            config["base_app_token"],
            config["base_table_id"],
            config["article_nr_field_id"],
            config["article_name_field_id"],
        ]
    )
    if config["source_type"] not in {"sheet", "bitable"}:
        config["source_type"] = DEFAULT_LARK_SOURCE_TYPE
    config["enabled"] = config["bitable_enabled"] if config["source_type"] == "bitable" else config["sheet_enabled"]
    return config


def fetch_lark_tenant_access_token(api_base_url, app_id, app_secret):
    try:
        response = requests.post(
            f"{api_base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Unable to reach the Lark authentication API.") from exc

    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("msg") or "Lark rejected the supplied credentials.")

    return payload.get("tenant_access_token", "")


def fetch_lark_sheet_values(api_base_url, access_token, spreadsheet_token, cell_range):
    encoded_range = quote(cell_range, safe="")

    try:
        response = requests.get(
            f"{api_base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values/{encoded_range}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Unable to read the configured Lark PIM sheet.") from exc

    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("msg") or "Lark could not return the requested sheet values.")

    return payload.get("data", {}).get("valueRange", {}).get("values", [])


def fetch_lark_bitable_fields(api_base_url, access_token, app_token, table_id):
    try:
        response = requests.get(
            f"{api_base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Unable to read the configured Feishu Bitable fields.") from exc

    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("msg") or "Feishu could not return the requested field metadata.")

    return (payload.get("data") or {}).get("items") or []


def fetch_lark_bitable_records(api_base_url, access_token, app_token, table_id, page_size=500):
    headers = {"Authorization": f"Bearer {access_token}"}
    records = []
    page_token = ""

    while True:
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token

        try:
            response = requests.get(
                f"{api_base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Unable to read the configured Feishu Bitable records.") from exc

        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("msg") or "Feishu could not return the requested Bitable records.")

        data = payload.get("data") or {}
        records.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            break

    return records


@st.cache_data(ttl=600, show_spinner=False)
def load_lark_sheet_values(
    api_base_url,
    app_id,
    app_secret,
    spreadsheet_token,
    sheet_id,
    lookup_range,
):
    access_token = fetch_lark_tenant_access_token(api_base_url, app_id, app_secret)
    return fetch_lark_sheet_values(
        api_base_url,
        access_token,
        spreadsheet_token,
        f"{sheet_id}!{lookup_range}",
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_lark_bitable_fields(
    api_base_url,
    app_id,
    app_secret,
    app_token,
    table_id,
):
    access_token = fetch_lark_tenant_access_token(api_base_url, app_id, app_secret)
    return fetch_lark_bitable_fields(
        api_base_url,
        access_token,
        app_token,
        table_id,
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_lark_bitable_records(
    api_base_url,
    app_id,
    app_secret,
    app_token,
    table_id,
):
    access_token = fetch_lark_tenant_access_token(api_base_url, app_id, app_secret)
    return fetch_lark_bitable_records(
        api_base_url,
        access_token,
        app_token,
        table_id,
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_lark_article_catalog(
    api_base_url,
    app_id,
    app_secret,
    spreadsheet_token,
    sheet_id,
    lookup_range,
    header_rows,
    article_nr_column_index,
    article_name_column_index,
):
    cache_key = build_local_catalog_cache_key(
        "sheet",
        [
            api_base_url,
            spreadsheet_token,
            sheet_id,
            lookup_range,
            header_rows,
            article_nr_column_index,
            article_name_column_index,
        ],
    )
    cached_catalog = load_local_catalog_cache(cache_key)
    if isinstance(cached_catalog, dict):
        return cached_catalog

    values = load_lark_sheet_values(
        api_base_url,
        app_id,
        app_secret,
        spreadsheet_token,
        sheet_id,
        lookup_range,
    )

    catalog = {}
    data_rows = values[max(header_rows, 0) :]
    for row in data_rows:
        if article_nr_column_index >= len(row):
            continue

        article_number = normalize_article_number(row[article_nr_column_index])
        if not article_number:
            continue

        article_name = ""
        if article_name_column_index < len(row):
            article_name = str(row[article_name_column_index]).strip()

        if article_name and article_number not in catalog:
            catalog[article_number] = article_name

    save_local_catalog_cache(cache_key, catalog)
    return catalog


@st.cache_data(ttl=600, show_spinner=False)
def load_lark_bitable_article_catalog(
    api_base_url,
    app_id,
    app_secret,
    app_token,
    table_id,
    article_nr_field_id,
    article_name_field_id,
):
    cache_key = build_local_catalog_cache_key(
        "bitable",
        [
            api_base_url,
            app_token,
            table_id,
            article_nr_field_id,
            article_name_field_id,
        ],
    )
    cached_result = load_local_catalog_cache(cache_key)
    if isinstance(cached_result, dict):
        return cached_result

    result = build_lark_bitable_article_catalog_result(
        api_base_url,
        app_id,
        app_secret,
        app_token,
        table_id,
        article_nr_field_id,
        article_name_field_id,
    )
    save_local_catalog_cache(cache_key, result)
    return result


def build_lark_bitable_article_catalog_result(
    api_base_url,
    app_id,
    app_secret,
    app_token,
    table_id,
    article_nr_field_id,
    article_name_field_id,
):
    fields = load_lark_bitable_fields(
        api_base_url,
        app_id,
        app_secret,
        app_token,
        table_id,
    )
    records = load_lark_bitable_records(
        api_base_url,
        app_id,
        app_secret,
        app_token,
        table_id,
    )

    field_name_by_id = {}
    for field in fields:
        field_id = str(field.get("field_id", "")).strip()
        field_name = str(field.get("field_name", "")).strip()
        if field_id and field_name:
            field_name_by_id[field_id] = field_name

    article_nr_field_name = field_name_by_id.get(article_nr_field_id, "")
    article_name_field_name = field_name_by_id.get(article_name_field_id, "")

    catalog = {}
    flattened_records = []

    for record in records:
        fields_payload = record.get("fields") or {}
        raw_article_number = flatten_bitable_value(
            fields_payload.get(article_nr_field_id)
            or fields_payload.get(article_nr_field_name)
            or ""
        )
        raw_article_name = flatten_bitable_value(
            fields_payload.get(article_name_field_id)
            or fields_payload.get(article_name_field_name)
            or ""
        )

        article_number = normalize_article_number(raw_article_number)
        article_name = str(raw_article_name).strip()
        if article_number and article_name and article_number not in catalog:
            catalog[article_number] = article_name

        flattened_records.append(
            {
                "record_id": record.get("record_id", ""),
                "article_nr": article_number,
                "article_name": article_name,
            }
        )

    result = {
        "catalog": catalog,
        "records": flattened_records,
        "field_name_by_id": field_name_by_id,
        "article_nr_field_name": article_nr_field_name,
        "article_name_field_name": article_name_field_name,
        "record_count": len(records),
    }
    return result
