from datetime import datetime, timezone

from dotenv import load_dotenv

from lark_lookup import (
    build_lark_bitable_article_catalog_result,
    get_lark_lookup_config,
    save_repo_article_catalog,
)

load_dotenv()


def main():
    config = get_lark_lookup_config()
    if config["source_type"] != "bitable":
        raise RuntimeError("LARK_SOURCE_TYPE must be set to bitable for refresh_article_catalog_json.py.")
    if not config["bitable_enabled"]:
        raise RuntimeError("Missing Feishu Bitable credentials or IDs for article catalog refresh.")

    result = build_lark_bitable_article_catalog_result(
        config["api_base_url"],
        config["app_id"],
        config["app_secret"],
        config["base_app_token"],
        config["base_table_id"],
        config["article_nr_field_id"],
        config["article_name_field_id"],
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "bitable",
        "article_nr_field_name": result["article_nr_field_name"],
        "article_name_field_name": result["article_name_field_name"],
        "record_count": result["record_count"],
        "catalog_count": len(result["catalog"]),
        "catalog": dict(sorted(result["catalog"].items())),
    }
    save_repo_article_catalog(payload)

    print(
        f"Saved data/article_catalog.json with {payload['catalog_count']} catalog rows "
        f"from {payload['record_count']} Feishu records."
    )


if __name__ == "__main__":
    main()
