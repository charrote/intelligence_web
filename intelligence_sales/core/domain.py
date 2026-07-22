"""Shared domain configuration builder."""

def build_spec(
    slug,
    port,
    title_prefix,
    scout_label,
    agent_names,
    theme_color="#0ea5e9",
    inbox_rel="../inbox/",
    db_filename=None,
    statuses=None,
    extra_columns=None,
    list_columns=None,
    search=None,
    intelligence_ttl_days=None,
    default_entities=None,
    default_data_sources=None,
    target_types=None,
    target_type_initial_data=None,
):
    """Build a domain specification dict."""
    if db_filename is None:
        db_filename = slug
    return {
        "slug": slug,
        "port": port,
        "title_prefix": title_prefix,
        "scout_label": scout_label,
        "agent_names": agent_names,
        "theme_color": theme_color,
        "inbox_rel": inbox_rel,
        "db_filename": db_filename,
        "statuses": statuses or [("pending", "待处理"), ("active", "处理中"), ("done", "已完成")],
        "extra_columns": extra_columns or [],
        "list_columns": list_columns or ["id", "title", "status", "date"],
        "search": search,
        "intelligence_ttl_days": intelligence_ttl_days or {"default": 90},
        "default_entities": default_entities or [],
        "default_data_sources": default_data_sources or [],
        "target_types": target_types or [],
        "target_type_initial_data": target_type_initial_data or [],
    }