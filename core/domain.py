"""Shared domain configuration builder."""


def _derive_target_types(default_entities):
    """Derive unique target types from default_entities list.

    Returns a list of unique type strings, preserving first-seen order.
    """
    seen = set()
    types = []
    for entity in default_entities or []:
        t = entity.get("type", "")
        if t and t not in seen:
            seen.add(t)
            types.append(t)
    return types


def build_spec(
    slug,
    port,
    title_prefix,
    scout_label,
    agent_names,
    theme_color="#0ea5e9",
    inbox_rel="../inbox/",
    db_filename=None,
    domain_key=None,
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
    """Build a domain specification dict.

    Args:
        target_types: explicit list of valid target_type values for projects.
                      If not provided, derived automatically from
                      default_entities[].type (preserving first-seen order).
        target_type_initial_data: initial seed data for target_types table.
    """
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
        "domain_key": domain_key or slug,
        "statuses": statuses or [("pending", "待处理"), ("active", "处理中"), ("done", "已完成")],
        "extra_columns": extra_columns or [],
        "list_columns": list_columns or ["id", "title", "status", "date"],
        "search": search,
        "intelligence_ttl_days": intelligence_ttl_days or {"default": 90},
        "default_entities": default_entities or [],
        "default_data_sources": default_data_sources or [],
        "target_types": target_types or _derive_target_types(default_entities),
        "target_type_initial_data": target_type_initial_data or [],
    }