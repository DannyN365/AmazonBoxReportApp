import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from lark_lookup import (
    DEFAULT_LARK_API_BASE_URL,
    DEFAULT_LARK_ARTICLE_NAME_COLUMN_INDEX,
    DEFAULT_LARK_ARTICLE_NR_COLUMN_INDEX,
    DEFAULT_LARK_HEADER_ROWS,
    DEFAULT_LARK_LOOKUP_RANGE,
    DEFAULT_LARK_SOURCE_TYPE,
    fetch_lark_tenant_access_token,
    get_lark_lookup_config,
    load_lark_article_catalog,
    load_lark_bitable_article_catalog,
    load_lark_bitable_fields,
    load_lark_bitable_records,
    load_lark_sheet_values,
    normalize_article_number,
)

load_dotenv()

st.set_page_config(page_title="Lark Data Test", layout="wide")


def build_effective_config():
    env_config = get_lark_lookup_config()

    source_type_options = {
        "bitable": "Feishu Bitable",
        "sheet": "Feishu Sheet",
    }
    default_source_type = env_config["source_type"] or DEFAULT_LARK_SOURCE_TYPE

    with st.sidebar:
        st.header("Lark config")
        st.caption("Defaults come from .env or st.secrets. You can override them here for testing.")

        source_type = st.radio(
            "Source type",
            options=["bitable", "sheet"],
            index=0 if default_source_type == "bitable" else 1,
            format_func=lambda key: source_type_options[key],
        )
        api_base_url = st.text_input("API base URL", value=env_config["api_base_url"] or DEFAULT_LARK_API_BASE_URL)
        app_id = st.text_input("App ID", value=env_config["app_id"])
        app_secret = st.text_input("App Secret", value=env_config["app_secret"], type="password")

        if source_type == "bitable":
            base_app_token = st.text_input("Bitable app token", value=env_config["base_app_token"])
            base_table_id = st.text_input("Bitable table ID", value=env_config["base_table_id"])
            article_nr_field_id = st.text_input("Article nr field ID", value=env_config["article_nr_field_id"])
            article_name_field_id = st.text_input("Article name field ID", value=env_config["article_name_field_id"])
            spreadsheet_token = ""
            sheet_id = ""
            lookup_range = ""
            header_rows = int(env_config["header_rows"] or DEFAULT_LARK_HEADER_ROWS)
            article_nr_column_index = int(env_config["article_nr_column_index"] or DEFAULT_LARK_ARTICLE_NR_COLUMN_INDEX)
            article_name_column_index = int(
                env_config["article_name_column_index"] or DEFAULT_LARK_ARTICLE_NAME_COLUMN_INDEX
            )
        else:
            spreadsheet_token = st.text_input("Spreadsheet token", value=env_config["spreadsheet_token"])
            sheet_id = st.text_input("Sheet ID", value=env_config["sheet_id"])
            lookup_range = st.text_input("Lookup range", value=env_config["lookup_range"] or DEFAULT_LARK_LOOKUP_RANGE)
            header_rows = st.number_input(
                "Header rows",
                min_value=0,
                step=1,
                value=int(env_config["header_rows"] or DEFAULT_LARK_HEADER_ROWS),
            )
            article_nr_column_index = st.number_input(
                "Article nr column index",
                min_value=0,
                step=1,
                value=int(env_config["article_nr_column_index"] or DEFAULT_LARK_ARTICLE_NR_COLUMN_INDEX),
            )
            article_name_column_index = st.number_input(
                "Article name column index",
                min_value=0,
                step=1,
                value=int(env_config["article_name_column_index"] or DEFAULT_LARK_ARTICLE_NAME_COLUMN_INDEX),
            )
            base_app_token = ""
            base_table_id = ""
            article_nr_field_id = ""
            article_name_field_id = ""

    return {
        "source_type": source_type,
        "api_base_url": api_base_url.strip().rstrip("/"),
        "app_id": app_id.strip(),
        "app_secret": app_secret.strip(),
        "spreadsheet_token": spreadsheet_token.strip(),
        "sheet_id": sheet_id.strip(),
        "lookup_range": lookup_range.strip(),
        "header_rows": int(header_rows),
        "article_nr_column_index": int(article_nr_column_index),
        "article_name_column_index": int(article_name_column_index),
        "base_app_token": base_app_token.strip(),
        "base_table_id": base_table_id.strip(),
        "article_nr_field_id": article_nr_field_id.strip(),
        "article_name_field_id": article_name_field_id.strip(),
    }


def validate_config(config):
    missing = []
    common_keys = [
        ("App ID", "app_id"),
        ("App Secret", "app_secret"),
    ]
    for label, key in common_keys:
        if not config[key]:
            missing.append(label)

    if config["source_type"] == "bitable":
        source_keys = [
            ("Bitable app token", "base_app_token"),
            ("Bitable table ID", "base_table_id"),
            ("Article nr field ID", "article_nr_field_id"),
            ("Article name field ID", "article_name_field_id"),
        ]
    else:
        source_keys = [
            ("Spreadsheet token", "spreadsheet_token"),
            ("Sheet ID", "sheet_id"),
            ("Lookup range", "lookup_range"),
        ]

    for label, key in source_keys:
        if not config[key]:
            missing.append(label)

    if missing:
        st.error("Missing config: " + ", ".join(missing))
        return False

    return True


config = build_effective_config()

st.title("Lark Data Test")
st.caption("Use this app to verify Feishu auth, inspect the source data, and test article-number matching.")

status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    st.metric("Source", "Bitable" if config["source_type"] == "bitable" else "Sheet")
with status_col2:
    if config["source_type"] == "bitable":
        st.metric("Table ID", config["base_table_id"] or "-")
    else:
        st.metric("Range", config["lookup_range"] or "-")
with status_col3:
    if config["source_type"] == "bitable":
        st.metric(
            "Field IDs",
            f"{config['article_nr_field_id'] or '-'} -> {config['article_name_field_id'] or '-'}",
        )
    else:
        st.metric(
            "Columns",
            f"{config['article_nr_column_index']} -> {config['article_name_column_index']}",
        )

auth_container = st.container(border=True)
with auth_container:
    st.subheader("1. Test authentication")
    st.caption("This checks whether the app can get a tenant access token.")

    if st.button("Test Lark auth", type="primary", use_container_width=True):
        if validate_config(config):
            try:
                token = fetch_lark_tenant_access_token(
                    config["api_base_url"],
                    config["app_id"],
                    config["app_secret"],
                )
            except RuntimeError as exc:
                st.error(str(exc))
            else:
                st.success("Authentication worked.")
                st.code(token[:24] + "..." if token else "Token was empty", language="text")

preview_container = st.container(border=True)
with preview_container:
    st.subheader("2. Preview source data")
    preview_count = st.slider("Preview rows", min_value=5, max_value=50, value=15, step=5)

    if config["source_type"] == "bitable":
        st.caption("This loads Bitable fields and records so we can confirm the table and field IDs.")

        if st.button("Load Bitable preview", use_container_width=True):
            if validate_config(config):
                try:
                    fields = load_lark_bitable_fields(
                        config["api_base_url"],
                        config["app_id"],
                        config["app_secret"],
                        config["base_app_token"],
                        config["base_table_id"],
                    )
                    records = load_lark_bitable_records(
                        config["api_base_url"],
                        config["app_id"],
                        config["app_secret"],
                        config["base_app_token"],
                        config["base_table_id"],
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Loaded {len(fields)} fields and {len(records)} records from the configured table.")

                    if fields:
                        field_rows = [
                            {
                                "Field name": field.get("field_name", ""),
                                "Field ID": field.get("field_id", ""),
                                "Type": field.get("type", ""),
                            }
                            for field in fields
                        ]
                        st.caption("Field metadata")
                        st.dataframe(pd.DataFrame(field_rows), use_container_width=True, hide_index=True)

                    preview_rows = []
                    for record in records[:preview_count]:
                        fields_payload = record.get("fields") or {}
                        preview_rows.append(
                            {
                                "record_id": record.get("record_id", ""),
                                "fields": str(fields_payload),
                            }
                        )

                    if preview_rows:
                        st.caption("Raw record preview")
                        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                    else:
                        st.warning("The configured table returned no records.")
    else:
        st.caption("This helps confirm the sheet ID, range, header row count, and source columns.")

        if st.button("Load sheet preview", use_container_width=True):
            if validate_config(config):
                try:
                    values = load_lark_sheet_values(
                        config["api_base_url"],
                        config["app_id"],
                        config["app_secret"],
                        config["spreadsheet_token"],
                        config["sheet_id"],
                        config["lookup_range"],
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Loaded {len(values)} rows from the configured range.")
                    preview_rows = values[:preview_count]
                    if preview_rows:
                        frame = pd.DataFrame(preview_rows)
                        frame.columns = [f"Col {i}" for i in range(len(frame.columns))]
                        st.dataframe(frame, use_container_width=True, hide_index=True)
                    else:
                        st.warning("The configured range returned no rows.")

match_container = st.container(border=True)
with match_container:
    st.subheader("3. Test article-number matching")
    st.caption("Enter a known article number and verify that the expected article name is returned.")

    article_number_input = st.text_input("Article number to test", placeholder="Example: 12345")

    if st.button("Find article name", use_container_width=True):
        if validate_config(config):
            normalized_article_number = normalize_article_number(article_number_input)
            if not normalized_article_number:
                st.warning("Enter an article number first.")
            else:
                try:
                    if config["source_type"] == "bitable":
                        result = load_lark_bitable_article_catalog(
                            config["api_base_url"],
                            config["app_id"],
                            config["app_secret"],
                            config["base_app_token"],
                            config["base_table_id"],
                            config["article_nr_field_id"],
                            config["article_name_field_id"],
                        )
                        catalog = result["catalog"]
                    else:
                        catalog = load_lark_article_catalog(
                            config["api_base_url"],
                            config["app_id"],
                            config["app_secret"],
                            config["spreadsheet_token"],
                            config["sheet_id"],
                            config["lookup_range"],
                            config["header_rows"],
                            config["article_nr_column_index"],
                            config["article_name_column_index"],
                        )
                        result = None
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    article_name = catalog.get(normalized_article_number)
                    st.write(f"Normalized article number: `{normalized_article_number}`")
                    st.write(f"Catalog size: `{len(catalog)}` matched rows")

                    if result is not None:
                        st.write(f"Field name for article nr ID: `{result['article_nr_field_name'] or '-'}`")
                        st.write(f"Field name for article name ID: `{result['article_name_field_name'] or '-'}`")
                        st.write(f"Record count fetched: `{result['record_count']}`")

                    if article_name:
                        st.success(f"Match found: {article_name}")
                    else:
                        st.error("No match found with the current source settings.")

                        sample_matches = []
                        for key, value in catalog.items():
                            if normalized_article_number in key or key in normalized_article_number:
                                sample_matches.append({"Article nr": key, "Article name": value})
                            if len(sample_matches) == 10:
                                break

                        if sample_matches:
                            st.caption("Closest article-number candidates from the current catalog")
                            st.dataframe(pd.DataFrame(sample_matches), use_container_width=True, hide_index=True)

with st.expander("Expected .env values", expanded=False):
    st.code(
        "\n".join(
            [
                "LARK_APP_ID=cli_xxxxxxxxxxxxx",
                "LARK_APP_SECRET=xxxxxxxxxxxxxxxx",
                "LARK_SOURCE_TYPE=bitable",
                "LARK_BASE_APP_TOKEN=appcnxxxxxxxxxxxx",
                "LARK_BASE_TABLE_ID=tblxxxxxxxxxxxx",
                "LARK_BASE_ARTICLE_NR_FIELD_ID=fldxxxxxxxxxxxx",
                "LARK_BASE_ARTICLE_NAME_FIELD_ID=fldxxxxxxxxxxxx",
                "# Alternative sheet mode:",
                "# LARK_SOURCE_TYPE=sheet",
                "# LARK_PIM_SPREADSHEET_TOKEN=shtcnxxxxxxxxxxxx",
                "# LARK_PIM_SHEET_ID=xxxxxxxx",
                "# LARK_PIM_LOOKUP_RANGE=A:B",
                "# LARK_PIM_HEADER_ROWS=1",
                "# LARK_PIM_ARTICLE_NR_COLUMN_INDEX=0",
                "# LARK_PIM_ARTICLE_NAME_COLUMN_INDEX=1",
                "# Optional: LARK_API_BASE_URL=https://open.feishu.cn/open-apis",
            ]
        ),
        language="bash",
    )
