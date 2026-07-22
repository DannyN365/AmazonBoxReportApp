import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("LARK_API_BASE_URL", "https://open.feishu.cn/open-apis").strip().rstrip("/")

# Read from .env (recommended)
APP_ID = os.getenv("LARK_APP_ID", "").strip()
APP_SECRET = os.getenv("LARK_APP_SECRET", "").strip()

# This is your Bitable APP token (app_token)
APP_TOKEN = os.getenv("LARK_BASE_APP_TOKEN", "").strip()

# Export these table ids from env if they exist
TABLE_ENV_KEYS = [
    "LARK_TABLE_ID_4",
    "LARK_TABLE_ID_5",
    "LARK_TABLE_ID_6",
    "LARK_TABLE_ID_7",
    "LARK_TABLE_ID_8",
    "LARK_TABLE_ID_9",
    "LARK_TABLE_ID_10",
    # optional legacy ones (may be in other apps)
    "LARK_STOCK_TABLE_ID",
    "LARK_BASE_TABLE_ID",
    "LARK_TABLE_ID_2",
    "LARK_TABLE_ID_3",
    "LARK_TABLE_ID_11",
]

OUT_PATH = "lark_fields.json"


def safe_print(message: str):
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="backslashreplace").decode("ascii"))


def get_tenant_access_token():
    url = f"{API_BASE_URL}/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"Lark auth error: {j}")
    return j["tenant_access_token"]


def fetch_bitable_fields(token, table_id: str):
    url = f"{API_BASE_URL}/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        return j  # return error payload to handle
    return j


def print_table_fields(table_id: str, items: list):
    print(f"\n--- Field Details for Table: {table_id} ---")
    print(f"{'Field Name':<40} | {'Field ID':<20} | {'Type'}")
    print("-" * 75)
    for field in items:
        name = field.get("field_name", "")
        fid = field.get("field_id", "")
        ftype = field.get("type", "")
        print(f"{name:<40} | {fid:<20} | {ftype}")


def main():
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("Missing LARK_APP_ID / LARK_APP_SECRET in .env")
    if not APP_TOKEN:
        raise RuntimeError("Missing LARK_BASE_APP_TOKEN in .env")

    print(f"Using APP_TOKEN={APP_TOKEN}")

    # gather table ids
    tables = []
    print("Exporting tables:")
    for k in TABLE_ENV_KEYS:
        v = (os.getenv(k, "") or "").strip()
        if v:
            tables.append((k, v))
            print(f"  {k} = {v}")

    token = get_tenant_access_token()

    # { "<app_token>": { "tables": { "<table_id>": { "fields": { "<fid>": {"name":..., "type":...} }}}}}
    out = {APP_TOKEN: {"tables": {}}}

    for env_key, table_id in tables:
        j = fetch_bitable_fields(token, table_id)

        # Handle TableIdNotFound etc. without crashing
        if isinstance(j, dict) and j.get("code") != 0:
            code = j.get("code")
            msg = j.get("msg")
            if code == 1254041 and msg == "TableIdNotFound":
                print(f"\n[SKIP] {env_key}={table_id} not found in this APP_TOKEN (TableIdNotFound)")
                continue
            raise RuntimeError(f"Lark fields API error for {env_key}={table_id}: {j}")

        items = (j.get("data") or {}).get("items") or []
        print_table_fields(table_id, items)

        fields_map = {}
        for it in items:
            fid = it.get("field_id")
            name = it.get("field_name")
            ftype = it.get("type")
            if fid and name is not None:
                fields_map[fid] = {"name": name, "type": ftype}

        out[APP_TOKEN]["tables"][table_id] = {"fields": fields_map}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    safe_print(f"\nSaved field map to: {OUT_PATH}")


if __name__ == "__main__":
    main()
