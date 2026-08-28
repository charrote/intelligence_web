"""Shared Flask app factory for intelligence domains."""

import os, sys, sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, Response
import jwt as pyjwt
from core.db import (
    init_db, migrate_db, get_db_path, create_intelligence,
    get_intelligences, get_intelligence_by_id, get_intelligence_by_project,
    get_intelligence_count_for_project, update_intelligence_status,
    delete_intelligence,
    get_history, get_categories,
    _seed_research_demos,
    add_comment, get_comments,
    add_summary, get_summary, get_dashboard_stats,
    get_commands, add_command_content,
    get_all_settings, get_setting, set_setting,
    authenticate_user, get_user_by_id, get_user_by_id_full,
    get_user_by_phone, get_user_by_username, create_user_with_phone,
    list_users, create_user, update_user, update_user_password, delete_user,
    list_roles, get_role, create_role, update_role, delete_role,
    get_role_permissions, set_role_permissions, list_permissions,
    get_user_role_ids, get_user_role_names, set_user_roles,
    get_user_effective_role, get_user_permission_codes,
    get_db,
    get_ai_analysis_configs, get_ai_analysis_config_by_id,
    save_ai_analysis_config, delete_ai_analysis_config, enable_ai_analysis_config,
    get_ai_analysis_runs, get_ai_analysis_run_by_id,
    save_ai_analysis_run, delete_ai_analysis_run,
    run_ai_analysis,
    generate_analysis_config,
)
from core import project as projlib
from core import datasource as dslib
from core import target_types as ttslib
from core.scheduler.scheduler import (
    trigger_extract_once, trigger_report_once, trigger_report_all,
    trigger_extract_async
)

DEFAULT_REPORT_PROMPT = """你是一个情报分析师。请基于以下已聚合的数据，撰写分析报告。

【报告名称】{{ report_name }}
【分析范围】{{ start_date }} 至 {{ end_date }}
【参与分析的数据】{{ fact_count }} 条结构化事实

=== 数据聚合结果 ===
{{ aggregated_data }}

=== 图表数据 ===
{{ chart_data }}

请按 JSON 格式返回：
{
  "analysis": "文字分析内容（不少于 200 字）...",
  "summary": "一段话总结..."
}"""


# Parse CORS origins from environment variable (comma-separated)
_CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:8765,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174').split(',') if o.strip()]


def _is_allowed_origin(origin):
    """Check if the request origin is in the allowed list."""
    if not origin:
        return False
    return origin in _CORS_ORIGINS


def create_app(project_root, spec):
    """Create and configure the Flask application for a domain."""
    app = Flask(__name__, static_folder=os.path.join(project_root, spec["slug"], "web", "static"))

    @app.before_request
    def handle_cors_preflight():
        """Handle CORS preflight OPTIONS requests and add CORS headers to all responses."""
        origin = request.headers.get('Origin', '')
        if _is_allowed_origin(origin):
            if request.method == 'OPTIONS':
                resp = Response('', status=200)
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                return resp
            else:
                # Add CORS headers to regular responses too
                request.environ['cors_origin'] = origin

    @app.after_request
    def add_cors_headers(response):
        """Add CORS headers to all responses if origin is allowed."""
        origin = request.environ.get('cors_origin', '')
        if _is_allowed_origin(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])

    # --- Init (create base tables if missing) ---
    init_db(project_root, spec)
    
    # --- Migrate (create new tables for projects/datasources/target_types) ---
    # Pass the domain key so the empty-DB built-in seed creates only THIS domain's
    # built-in rule/template (never a cross-domain record).
    migrate_db(db_path, domain_key=spec.get("domain_key"))

    # --- Seed demo data (research domain, empty db only) ---
    _seed_research_demos(db_path, spec)

    # --- Seed target types if empty ---
    db_target_types = ttslib.get_target_types(db_path)
    if not db_target_types:
        initial_data = spec.get("target_type_initial_data", [])
        if initial_data:
            ttslib.seed_target_types(db_path, initial_data)
        else:
            default_types = spec.get("target_types", [])
            if default_types:
                types_data = []
                for i, slug in enumerate(default_types):
                    types_data.append({
                        'slug': slug,
                        'label': slug.capitalize(),
                        'sort_order': i,
                    })
                ttslib.seed_target_types(db_path, types_data)

    # --- Domain Config ---
    @app.route('/api/domain_config')
    def domain_config():
        statuses = [{"key": k, "label": v} for k, v in spec["statuses"]]
        # Load target types from database
        db_target_types = ttslib.get_enabled_target_types(db_path)
        target_types = [tt['slug'] for tt in db_target_types] if db_target_types else spec.get("target_types", [])
        return jsonify({
            "slug": spec["slug"],
            "title_prefix": spec["title_prefix"],
            "theme_color": spec["theme_color"],
            "statuses": statuses,
            "agent_names": spec["agent_names"],
            "scout_label": spec["scout_label"],
            "search": spec.get("search"),
            "default_entities": spec.get("default_entities", []),
            "default_data_sources": spec.get("default_data_sources", []),
            "target_types": target_types,
            "target_type_details": [{"slug": tt['slug'], "label": tt['label'], "color": tt['color'], "icon": tt['icon']} for tt in db_target_types] if db_target_types else [],
            "extra_columns": spec["extra_columns"],
            "list_columns": spec["list_columns"],
            "intelligence_ttl_days": spec.get("intelligence_ttl_days", {}),
        })

    # --- Dashboard Stats ---
    @app.route('/api/dashboard/stats')
    def dashboard_stats():
        stats = get_dashboard_stats(db_path)
        return jsonify(stats)

    # --- Intelligence CRUD ---
    @app.route('/api/intelligence', methods=['GET'])
    def list_intelligence():
        limit = request.args.get('limit', 100, type=int)
        filters = {
            "search": request.args.get('search'),
            "status": request.args.get('status'),
            "category": request.args.get('category'),
            "company": request.args.get('company'),
            "project_id": request.args.get('project_id'),
            "limit": limit,
        }
        return jsonify(get_intelligences(db_path, filters))

    @app.route('/api/intelligence', methods=['POST'])
    def create_intel():
        data = request.json
        if not data.get('title') or not data.get('content'):
            return jsonify({'error': 'title and content are required'}), 400
        project_id = data.get('project_id')
        intel_id = create_intelligence(
            db_path,
            data['title'],
            data['content'],
            data.get('category', ''),
            data.get('contact_name', ''),
            {
                "company": data.get('company', ''),
                "contact_name": data.get('contact_name', ''),
                "deal_value": data.get('deal_value', 0),
                "industry": data.get('industry', ''),
            },
            project_id=project_id if project_id else None,
        )
        if intel_id is None:
            return jsonify({'error': 'duplicate title, skipping'}), 409
        return jsonify({'id': intel_id, 'status': 'pending'}), 201

    @app.route('/api/intelligence/<int:id>', methods=['GET'])
    def get_intel(id):
        intel = get_intelligence_by_id(db_path, id)
        if intel is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(intel)

    # --- Public share page (no auth) ---
    @app.route('/s/<token>')
    def share_page(token):
        from core.db import get_intelligence_by_share_token
        intel = get_intelligence_by_share_token(db_path, token)
        if intel is None:
            return '<h1 style="text-align:center;margin-top:60px;font-family:sans-serif;color:#9CA3AF">链接无效或已关闭</h1>', 404
        # Sanitize content: escape HTML then convert newlines to <p>
        import html as html_mod
        escaped = html_mod.escape(intel.get('content', ''))
        content_html = '<p>' + escaped.replace('\n', '</p><p>').strip() + '</p>'
        # Format date
        created = intel.get('created_at', '')[:10]
        # 注册开关（系统设置，实时生效）。默认关闭；显式开启才显示注册入口。
        from core.db import get_setting
        reg_flag = get_setting(db_path, 'register_enabled')
        register_enabled = reg_flag in ('1', 'true', 'True')
        from jinja2 import Environment
        tpl_path = os.path.join(os.path.dirname(__file__), 'share_template.html')
        with open(tpl_path, 'r', encoding='utf-8') as f:
            tpl = Environment(autoescape=True).from_string(f.read())
        html_out = tpl.render(
            title=intel.get('title', ''),
            category=intel.get('category', ''),
            company=intel.get('company', ''),
            created_at=created,
            content_html=content_html,
            source_url=intel.get('source_url', '') or '',
            register_enabled=register_enabled,
        )
        return Response(html_out, content_type='text/html; charset=utf-8')

    # --- Toggle sharing (requires intel.share permission) ---
    @app.route('/api/intelligence/<int:id>/share', methods=['POST'])
    def toggle_share(id):
        from core.db import set_intelligence_share
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        # 分享权限管控：角色勾选"开放情报分享"（intel.share）才允许。
        # admin 与持 intel.share 权限的角色放行；否则 403。
        if user.get('role') != 'admin' and 'intel.share' not in _user_perm_codes(user):
            return jsonify({'error': '没有权限执行此操作（需在角色中勾选"开放情报分享"）'}), 403
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get('enabled', True))
        result = set_intelligence_share(db_path, id, enabled)
        if result is None:
            return jsonify({'error': 'not found'}), 404
        token, on = result
        # Build share URL. WeChat's in-app browser only opens https links,
        # so default to https (respect X-Forwarded-Proto if a higher proxy
        # sets it; keep http only for local dev on localhost).
        scheme = request.headers.get('X-Forwarded-Proto', '')
        if not scheme:
            scheme = 'http' if 'localhost' in request.host or request.host.startswith('127.') else 'https'
        share_url = f"{scheme}://{request.host}/s/{token}" if on else ""
        return jsonify({'enabled': on, 'token': token, 'share_url': share_url})

    @app.route('/api/intelligence/<int:id>', methods=['DELETE'])
    def delete_intelligence_endpoint(id):
        """Delete an intelligence record. Admin only."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        if user.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        if delete_intelligence(db_path, id):
            return jsonify({'ok': True})
        return jsonify({'error': 'not found'}), 404

    @app.route('/api/intelligence/<int:id>/status', methods=['PUT'])
    def update_status(id):
        data = request.json
        status = data.get('status', '')
        opinion = data.get('opinion', '')
        update_intelligence_status(db_path, id, status, opinion)
        return jsonify({'ok': True, 'status': status})

    @app.route('/api/intelligence/<int:id>/comments', methods=['GET'])
    def get_intel_comments(id):
        limit = request.args.get('limit', 20, type=int)
        return jsonify(get_comments(db_path, id, limit))

    @app.route('/api/intelligence/<int:id>/comments', methods=['POST'])
    def add_intel_comment(id):
        data = request.json
        if not data.get('content'):
            return jsonify({'error': 'content required'}), 400
        agent_name = data.get('agent_name', 'unknown')
        agent_id = data.get('agent_id', '')
        cid = add_comment(db_path, id, agent_name, data['content'], agent_id)
        return jsonify({'id': cid}), 201

    @app.route('/api/intelligence/<int:id>/human-comment', methods=['POST'])
    def add_intel_human_comment(id):
        """Add a human (logged-in user) comment to an intelligence record.

        Any authenticated user may post. The commenter's identity is taken
        from the verified JWT (never from the request body).
        """
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': '未登录或登录已过期'}), 401

        intel = get_intelligence_by_id(db_path, id)
        if intel is None:
            return jsonify({'error': 'not found'}), 404

        data = request.get_json(silent=True) or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'error': '评论内容不能为空'}), 400
        if len(content) > 2000:
            return jsonify({'error': '评论内容不能超过 2000 字'}), 400

        # Resolve the real display name from the DB (falls back to username)
        db_user = get_user_by_id(db_path, user.get('user_id'))
        display_name = (db_user or {}).get('display_name') or user.get('username') or '用户'

        cid = add_comment(db_path, id, display_name, content, '', user_id=user.get('user_id'))
        return jsonify({
            'id': cid,
            'intelligence_id': id,
            'user_id': user.get('user_id'),
            'agent_name': display_name,
            'content': content,
            'created_at': datetime.now().isoformat(),
        }), 201

    @app.route('/api/intelligence/<int:id>/history', methods=['GET'])
    def get_intel_history(id):
        return jsonify(get_history(db_path, id))

    @app.route('/api/intelligence/<int:id>/summary', methods=['GET'])
    def get_intel_summary(id):
        summary = get_summary(db_path, id)
        if summary:
            return jsonify(summary)
        return jsonify({'content': ''})

    @app.route('/api/intelligence/<int:id>/summary', methods=['POST'])
    def add_intel_summary(id):
        data = request.json
        if not data.get('content'):
            return jsonify({'error': 'content required'}), 400
        sid = add_summary(db_path, id, data['content'])
        return jsonify({'id': sid}), 201

    # --- Categories ---
    @app.route('/api/categories')
    def categories():
        return jsonify(get_categories(db_path))

    # ========================================================================
    # Batch Import API
    # ========================================================================

    def _parse_file(file_storage):
        """Parse uploaded Excel/CSV file. Returns headers, preview, all_rows, mapping hints."""
        import csv
        import io as _io

        content = file_storage.read()
        filename = file_storage.filename.lower()

        if filename.endswith('.csv'):
            text = content.decode('utf-8', errors='replace')
            reader = csv.reader(_io.StringIO(text))
            all_rows = list(reader)
            if not all_rows:
                return [], [], [], {}
            headers = [h.strip() for h in all_rows[0]]
            data_rows = all_rows[1:]
        else:
            # Excel: try openpyxl first, fallback to basic parsing
            try:
                from openpyxl import load_workbook as _load_wb
                wb = _load_wb(_io.BytesIO(content))
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    return [], [], [], {}
                headers = [str(h).strip() if h else '' for h in rows[0]]
                data_rows = []
                for row in rows[1:]:
                    data_rows.append([str(v).strip() if v else '' for v in row])
            except ImportError:
                # Fallback: treat as CSV-like
                text = content.decode('utf-8', errors='replace')
                reader = csv.reader(_io.StringIO(text))
                all_rows = list(reader)
                if not all_rows:
                    return [], [], [], {}
                headers = [h.strip() for h in all_rows[0]]
                data_rows = all_rows[1:]

        # Auto-detect column mapping
        mapping = _auto_detect_mapping(headers)

        # Build preview (first 20 rows with mapped values)
        preview = []
        valid_count = 0
        error_count = 0
        for row_idx, row in enumerate(data_rows[:20], start=1):
            mapped = {}
            errors = []
            for field_key, col_idx in mapping.items():
                if col_idx is not None and col_idx < len(row):
                    mapped[field_key] = row[col_idx].strip()
                else:
                    mapped[field_key] = ''
            # Validate required fields
            if not mapped.get('title'):
                errors.append('缺少标题')
            if not mapped.get('content'):
                errors.append('缺少内容')
            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1
            else:
                error_count += 1
            preview.append({
                'row': row_idx,
                'mapped': mapped,
                'valid': is_valid,
                'errors': errors,
            })

        return headers, preview, data_rows, mapping

    def _auto_detect_mapping(headers):
        """Auto-detect which header column maps to which field."""
        mapping = {}
        keyword_map = {
            'title': ['标题', 'title', 'name', '主题', '名称', 'subject'],
            'content': ['内容', 'content', '正文', 'body', '描述', 'description', '详情'],
            'category': ['分类', 'category', '类型', 'type', '类别'],
            'status': ['状态', 'status', 'stage'],
            'source_url': ['来源链接', 'source_url', 'url', '链接', '链接地址', '原文链接'],
            'opinion': ['意见', 'opinion', '备注', 'note', 'comment', '备注说明'],
        }
        for field_key, keywords in keyword_map.items():
            for i, h in enumerate(headers):
                if h.lower() in [kw.lower() for kw in keywords]:
                    mapping[field_key] = i
                    break
        return mapping

    def _execute_import(db_path, rows_data, mapping, project_id=None, on_duplicate='skip'):
        """Insert intelligence records from mapped rows data."""
        inserted = 0
        skipped = 0
        errors = []

        all_rows = rows_data  # full data rows (not just preview)
        for entry in all_rows:
            if isinstance(entry, dict):
                # Already has mapped data
                row_data = entry
            else:
                # Raw row - need to map
                mapped = {}
                row_errors = []
                for field_key, col_idx in mapping.items():
                    if col_idx is not None and col_idx < len(entry):
                        mapped[field_key] = entry[col_idx].strip()
                    else:
                        mapped[field_key] = ''
                if not mapped.get('title'):
                    row_errors.append('缺少标题')
                if not mapped.get('content'):
                    row_errors.append('缺少内容')
                if row_errors:
                    errors.append({'row': entry.get('row', '?'), 'mapped': mapped, 'errors': row_errors})
                    continue
                row_data = mapped

            title = row_data.get('title', '').strip()
            content = row_data.get('content', '').strip()
            category = row_data.get('category', '')
            status = row_data.get('status', '')
            source_url = row_data.get('source_url', '')
            opinion = row_data.get('opinion', '')

            if not title or not content:
                errors.append({'row': row_data.get('row', '?'), 'mapped': row_data, 'errors': ['标题或内容为空']})
                continue

            # Auto-match project by source_url if no project_id specified
            eff_project_id = project_id
            if not eff_project_id and source_url:
                eff_project_id = _match_project_by_url(db_path, source_url)

            intel_id = create_intelligence(
                db_path,
                title, content, category, '',
                {
                    "company": row_data.get('company', ''),
                    "deal_value": 0,
                    "industry": row_data.get('industry', ''),
                    "source_url": source_url,
                },
                project_id=eff_project_id,
            )
            if intel_id is not None:
                inserted += 1
                # Add history entry for imported records
                try:
                    add_history(db_path, intel_id, 'batch_import',
                              f'批量导入来源: {source_url or "文件导入"}', '')
                except Exception:
                    pass
            else:
                if on_duplicate == 'skip':
                    skipped += 1
                else:
                    # Update existing record's project_id
                    try:
                        with get_db(db_path) as conn:
                            if eff_project_id:
                                conn.execute(
                                    'UPDATE intelligence SET project_id = ?, updated_at = ? WHERE LOWER(TRIM(title)) = ?',
                                    (eff_project_id, datetime.now().isoformat(), title.lower())
                                )
                                conn.commit()
                    except Exception:
                        pass
                    inserted += 1

        return inserted, skipped, errors

    def _match_project_by_url(db_path, url):
        """Match a URL to a project through its linked datasources."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else url

            with get_db(db_path) as conn:
                row = conn.execute('''
                    SELECT p.id FROM projects p
                    INNER JOIN project_datasources pd ON pd.project_id = p.id
                    INNER JOIN datasources d ON d.id = pd.datasource_id
                    WHERE d.url LIKE ? OR d.url = ?
                    LIMIT 1
                ''', (f'%{parsed.netloc}%', base_url)).fetchone()
                return row['id'] if row else None
        except Exception:
            return None

    @app.route('/api/intelligence/import', methods=['POST'])
    def batch_import():
        """Batch import intelligence from uploaded Excel/CSV files.

        Two modes:
        1. File upload: POST with file → returns headers, mapping, preview
        2. Confirm import: POST with confirm=true + data=JSON → inserts records
        """
        if request.method == 'POST':
            confirm = request.form.get('confirm', '').lower() == 'true'

            if confirm:
                # Mode 2: Execute import
                try:
                    data = json.loads(request.form.get('data', '{}'))
                except (json.JSONDecodeError, TypeError):
                    return jsonify({'error': 'invalid data format'}), 400

                mapping = data.get('mapping', {})
                project_id = data.get('project_id')

                # Use all_rows for full import, or fall back to preview rows
                rows_data = data.get('all_rows', data.get('rows', []))
                if not rows_data:
                    return jsonify({'error': 'no data to import'}), 400

                inserted, skipped, errors = _execute_import(db_path, rows_data, mapping, project_id)
                return jsonify({
                    'inserted_count': inserted,
                    'skipped_count': skipped,
                    'errors': errors,
                })
            else:
                # Mode 1: Parse file
                file = request.files.get('file')
                if not file or not file.filename:
                    return jsonify({'error': '请上传文件'}), 400

                headers, preview, all_data_rows, auto_mapping = _parse_file(file)
                if not headers:
                    return jsonify({'error': '无法解析文件，请检查格式'}), 400

                # Build preview mapping data (using auto_mapping)
                preview_rows = []
                valid_count = 0
                error_count = 0
                for entry in preview:
                    preview_rows.append({
                        'row': entry['row'],
                        'mapped': entry['mapped'],
                        'valid': entry['valid'],
                        'errors': entry['errors'],
                    })
                    if entry['valid']:
                        valid_count += 1
                    else:
                        error_count += 1

                return jsonify({
                    'headers': headers,
                    'mapping': auto_mapping,
                    'preview': preview_rows,
                    'all_rows': all_data_rows,
                    'total': len(all_data_rows),
                    'valid_count': valid_count,
                    'error_count': error_count,
                    'more_rows': len(all_data_rows) > 20,
                })

    # --- Commands ---
    @app.route('/api/commands', methods=['GET'])
    def commands():
        return jsonify(get_commands(db_path))

    @app.route('/api/commands', methods=['POST'])
    def add_command_endpoint():
        data = request.json
        if not data.get('content'):
            return jsonify({'error': 'content required'}), 400
        cid = add_command_content(db_path, data['content'])
        return jsonify({'id': cid}), 201

    @app.route('/api/commands/<int:id>', methods=['DELETE'])
    def delete_command_endpoint(id):
        _db = sqlite3.connect(db_path)
        _db.execute('DELETE FROM commands WHERE id = ?', (id,))
        _db.commit()
        _db.close()
        return jsonify({'ok': True})

    # ========================================================================
    # Auth / RBAC helpers
    # Defined early so @require_auth / @require_permission are available to the
    # Projects / Datasources / Target-Types endpoints below.
    # ========================================================================

    JWT_SECRET = os.environ.get('JWT_SECRET', 'default-dev-secret-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRY_HOURS = 24

    def _generate_token(user):
        """Generate a JWT token for the given user."""
        payload = {
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            # Domain access whitelist (slugs). Empty list = all enabled domains
            # (backward compatible with pre-gating users/tokens).
            'domains': user.get('domains') or [],
            # System-level RBAC (platform-wide). Computed at login on the primary
            # domain. Absent on pre-existing tokens -> endpoints fall back to DB.
            'role_ids': user.get('role_ids') or [],
            'permission_codes': user.get('permission_codes') or [],
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
            'iat': datetime.utcnow(),
        }
        return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def _verify_token(token):
        """Verify a JWT token and return the payload, or None if invalid."""
        try:
            return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            return None

    def require_auth(f):
        """Decorator to require JWT auth."""
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
            user = _verify_token(token) if token else None
            if not user:
                return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated

    def require_permission(code):
        """Decorator factory: require a specific permission code (RBAC).
        Usage: @require_permission('roles.manage')
        admin always passes; others must have the code in their role's permissions."""
        from functools import wraps
        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                auth_header = request.headers.get('Authorization', '')
                token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
                user = _verify_token(token) if token else None
                if not user:
                    return jsonify({'error': 'Unauthorized'}), 401
                role = user.get('role')
                if role == 'admin':
                    return f(*args, **kwargs)
                # System-level RBAC: prefer the permission codes embedded at login
                # (platform-wide, works across domains). Fall back to this domain's
                # DB only for pre-existing tokens that predate the claim.
                if 'permission_codes' in user:
                    codes = set(user.get('permission_codes') or [])
                else:
                    codes = get_user_permission_codes(db_path, user.get('user_id'), role)
                if code not in codes:
                    return jsonify({'error': '没有权限执行此操作'}), 403
                return f(*args, **kwargs)
            return decorated
        return decorator

    def _user_perm_codes(user):
        """Resolve a token user's effective permission-code set.

        Prefers the codes embedded in the JWT at login (system-level, works
        across domains); falls back to this domain's DB only for pre-existing
        tokens that predate the claim. admin is handled inside
        get_user_permission_codes (returns the full catalog).
        """
        role = user.get('role')
        if 'permission_codes' in user:
            return set(user.get('permission_codes') or [])
        return get_user_permission_codes(db_path, user.get('user_id'), role)

    def _require_user_or_perm(code):
        """Inline check: allow admin / self / holder of `code`. Returns
        (ok, response) so callers can short-circuit with the given response."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return False, (jsonify({'error': 'Unauthorized'}), 401)
        if user.get('role') == 'admin':
            return True, None
        if code in _user_perm_codes(user):
            return True, None
        return False, (jsonify({'error': '没有权限执行此操作'}), 403)

    def _admin_role_id():
        """Resolve the admin role's numeric id from the DB (1 if present)."""
        for r in list_roles(db_path):
            if r.get('name') == 'admin':
                return r.get('id')
        return 1

    def _is_admin_user(user):
        """True if the token user holds the admin role (effective role or
        any of its multi-role associations)."""
        if user.get('role') == 'admin':
            return True
        admin_id = _admin_role_id()
        rids = user.get('role_ids') or []
        return any(int(r) == admin_id for r in rids)

    def _is_admin_user_id(user_id):
        """True if the user with this DB id holds the admin role (effective
        role or any of its multi-role associations)."""
        u = get_user_by_id_full(db_path, user_id)
        if u is None:
            return False
        if u.get('role') == 'admin':
            return True
        admin_id = _admin_role_id()
        return any(int(r) == admin_id for r in (u.get('role_ids') or []))

    def _is_builtin_admin_id(user_id):
        """True for the built-in super-admin account (seeded as id=1,
        username='admin'). This account's role, domains and login name are
        locked: they cannot be modified through any API — the built-in admin
        must always keep its built-in administrator privileges."""
        if user_id == 1:
            return True
        u = get_user_by_id_full(db_path, user_id)
        return u is not None and u.get('username') == 'admin'

    def _normalize_domains(dom):
        """Normalize a domains field (list of slugs, or comma string, or None)
        to a clean list of slugs."""
        if not dom:
            return []
        if isinstance(dom, str):
            return [d.strip() for d in dom.split(',') if d.strip()]
        return [str(d).strip() for d in dom if str(d).strip()]

    def _in_user_domain(actor, target_user_id, target_domains):
        """Scope guard for user management: may `actor` see/act on the user with
        `target_user_id` given their domain whitelist?

        - admin → always
        - self → always
        - empty actor whitelist → all domains (legacy compat, matches domain gating)
        - otherwise → the target must share at least one domain with the actor
        """
        if actor.get('role') == 'admin':
            return True
        if actor.get('user_id') == target_user_id:
            return True
        actor_domains = _normalize_domains(actor.get('domains'))
        if not actor_domains:
            return True
        tdoms = _normalize_domains(target_domains)
        return any(d in actor_domains for d in tdoms)

    def _check_no_admin_grant(actor, role_ids):
        """Privilege-escalation guard: only an admin may grant the admin role.

        Returns a 403 response tuple if `actor` is not admin but `role_ids`
        includes the admin role; otherwise None (allowed).
        """
        if actor.get('role') == 'admin':
            return None
        admin_id = _admin_role_id()
        if any(int(r) == admin_id for r in role_ids):
            return (jsonify({'error': '只有管理员可以授予管理员角色'}), 403)
        return None

    def _require_any_perm(codes):
        """Inline check: allow admin or holder of ANY code in `codes`. Returns
        (ok, response)."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return False, (jsonify({'error': 'Unauthorized'}), 401)
        if user.get('role') == 'admin':
            return True, None
        owned = _user_perm_codes(user)
        if any(c in owned for c in codes):
            return True, None
        return False, (jsonify({'error': '没有权限执行此操作'}), 403)

    # --- Domain access gating (per-domain business APIs) ---
    # System-level endpoints (/api/auth, /api/system, /api/me, /api/health) are
    # shared across domains and are NOT gated. All other /api/* business routes
    # are gated by the user's domain whitelist (JWT 'domains' claim): admin or a
    # user with an empty whitelist (legacy token / not-yet-scoped user) passes;
    # otherwise the current domain's slug must be present in the whitelist.
    _DOMAIN_GATING_EXCLUDE = ('/api/auth/', '/api/system/', '/api/me/', '/api/health',
                              '/api/users', '/api/roles', '/api/permissions')

    @app.before_request
    def enforce_domain_access():
        path = request.path
        if not path.startswith('/api/'):
            return None
        if path.startswith(_DOMAIN_GATING_EXCLUDE):
            return None
        if request.method == 'OPTIONS':
            return None
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
        user = _verify_token(token) if token else None
        if not user:
            return None  # let the route's own auth check produce the 401
        if user.get('role') == 'admin':
            return None
        domains = user.get('domains') or []
        if not domains:
            return None  # legacy token / user without a whitelist: allow
        if spec['slug'] not in domains:
            return jsonify({'error': '没有访问「%s」的权限' % spec['title_prefix']}), 403
        return None

    # ========================================================================
    # Projects API
    # ========================================================================

    @app.route('/api/projects', methods=['GET'])
    def list_projects():
        items = projlib.get_projects(db_path, {
            "status": request.args.get('status'),
        })
        total = projlib.get_project_count(db_path)
        return jsonify({
            "total": total,
            "items": items,
        })

    @app.route('/api/projects', methods=['POST'])
    @require_permission('projects.manage')
    def create_project():
        data = request.json
        if not data.get('name') or not data.get('target_type'):
            return jsonify({'error': 'name and target_type are required'}), 400

        target_types = spec.get("target_types", [])
        if target_types and data['target_type'] not in target_types:
            return jsonify({
                'error': f'invalid target_type, must be one of: {target_types}'
            }), 400

        project_id = projlib.create_project(
            db_path,
            name=data['name'],
            target_type=data['target_type'],
            target_name=data.get('target_name', ''),
            scope=data.get('scope', ''),
            frequency=data.get('frequency', 'weekly'),
            instruction=data.get('instruction', ''),
            datasource_ids=data.get('datasource_ids', []),
        )
        project = projlib.get_project_by_id(db_path, project_id)
        return jsonify(project), 201

    @app.route('/api/projects/<int:id>', methods=['GET'])
    def get_project(id):
        project = projlib.get_project_by_id(db_path, id)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify({"project": project})

    @app.route('/api/projects/<int:id>', methods=['PUT'])
    @require_permission('projects.manage')
    def update_project_endpoint(id):
        project = projlib.update_project(db_path, id, request.json)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(project)

    @app.route('/api/projects/<int:id>/toggle', methods=['POST'])
    @require_permission('projects.manage')
    def toggle_project_status(id):
        data = request.json
        enabled = data.get('enabled', True)
        project = projlib.toggle_project_status(db_path, id, enabled)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(project)

    @app.route('/api/projects/<int:id>/datasources', methods=['GET'])
    def get_project_datasources(id):
        project = projlib.get_project_by_id(db_path, id)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify({"datasources": project.get('datasources', [])})

    @app.route('/api/projects/<int:id>/datasources', methods=['PUT'])
    @require_permission('projects.manage')
    def set_project_datasources(id):
        data = request.json
        datasource_ids = data.get('datasource_ids', [])
        project = projlib.set_project_datasources(db_path, id, datasource_ids)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(project)

    @app.route('/api/projects/<int:id>', methods=['DELETE'])
    @require_permission('projects.manage')
    def delete_project_endpoint(id):
        projlib.delete_project(db_path, id)
        return jsonify({'ok': True})

    @app.route('/api/projects/<int:id>/intel', methods=['GET'])
    def get_project_intelligence(id):
        """Get intelligence records linked to a project."""
        project = projlib.get_project_by_id(db_path, id)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        limit = request.args.get('limit', 50, type=int)
        intel_items = get_intelligence_by_project(db_path, id, limit=limit)
        total = get_intelligence_count_for_project(db_path, id)
        return jsonify({
            'project_id': id,
            'total': total,
            'items': intel_items,
        })

    # ========================================================================
    # Datasources API
    # ========================================================================

    @app.route('/api/datasources', methods=['GET'])
    def list_datasources():
        items = dslib.list_sources(db_path, {
            "type": request.args.get('type'),
            "status": request.args.get('status'),
            "search": request.args.get('search'),
        })
        return jsonify(items)

    @app.route('/api/datasources', methods=['POST'])
    @require_permission('datasources.manage')
    def create_datasource():
        data = request.json
        if not data.get('name') or not data.get('url'):
            return jsonify({'error': 'name and url are required'}), 400

        indicators = data.get('indicators', '')
        if isinstance(indicators, str) and indicators:
            indicators = [i.strip() for i in indicators.split(',') if i.strip()]

        source_id = dslib.create_source(
            db_path,
            name=data['name'],
            type_=data.get('type', 'website'),
            url=data['url'],
            schedule=data.get('schedule', 'daily'),
            status=data.get('status', 'active'),
            indicators=indicators,
            description=data.get('description', ''),
        )
        source = dslib.get_source_by_id(db_path, source_id)
        return jsonify(source), 201

    @app.route('/api/datasources/<int:id>', methods=['GET'])
    def get_datasource(id):
        source = dslib.get_source_by_id(db_path, id)
        if source is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(source)

    @app.route('/api/datasources/<int:id>', methods=['PUT'])
    @require_permission('datasources.manage')
    def update_datasource_endpoint(id):
        source = dslib.update_source(db_path, id, request.json)
        if source is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(source)

    @app.route('/api/datasources/<int:id>/status', methods=['PUT'])
    @require_permission('datasources.manage')
    def toggle_datasource_status(id):
        data = request.json
        enabled = data.get('status') == 'active'
        source = dslib.toggle_source_status(db_path, id, enabled)
        if source is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(source)

    @app.route('/api/datasources/<int:id>', methods=['DELETE'])
    @require_permission('datasources.manage')
    def delete_datasource_endpoint(id):
        dslib.delete_source(db_path, id)
        return jsonify({'ok': True})

    # ========================================================================
    # Target Types API
    # ========================================================================

    @app.route('/api/target_types', methods=['GET'])
    def list_target_types():
        items = ttslib.get_target_types(db_path, {
            "enabled": request.args.get('enabled'),
        })
        return jsonify(items)

    @app.route('/api/target_types', methods=['POST'])
    @require_permission('target_types.manage')
    def create_target_type():
        data = request.json
        if not data.get('slug') or not data.get('label'):
            return jsonify({'error': 'slug and label are required'}), 400

        type_id = ttslib.create_target_type(
            db_path,
            slug=data['slug'],
            label=data['label'],
            description=data.get('description', ''),
            color=data.get('color', '#3b4f8c'),
            icon=data.get('icon', ''),
            sort_order=data.get('sort_order', 0),
            enabled=data.get('enabled', True),
        )
        tt = ttslib.get_target_type_by_id(db_path, type_id)
        return jsonify(tt), 201

    @app.route('/api/target_types/<int:id>', methods=['GET'])
    def get_target_type(id):
        tt = ttslib.get_target_type_by_id(db_path, id)
        if tt is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(tt)

    @app.route('/api/target_types/<int:id>', methods=['PUT'])
    @require_permission('target_types.manage')
    def update_target_type_endpoint(id):
        tt = ttslib.update_target_type(db_path, id, request.json)
        if tt is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(tt)

    @app.route('/api/target_types/<int:id>/toggle', methods=['POST'])
    @require_permission('target_types.manage')
    def toggle_target_type_status(id):
        data = request.json
        enabled = data.get('enabled', True)
        tt = ttslib.toggle_target_type_enabled(db_path, id, enabled)
        if tt is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(tt)

    @app.route('/api/target_types/<int:id>', methods=['DELETE'])
    @require_permission('target_types.manage')
    def delete_target_type_endpoint(id):
        ttslib.delete_target_type(db_path, id)
        return jsonify({'ok': True})

    # ========================================================================
    # Roles API
    # ========================================================================

    @app.route('/api/roles', methods=['GET'])
    def list_roles_endpoint():
        """List all roles with user_count. Requires users.manage OR roles.manage
        (admin passes) — user management needs the role list for its dropdown.

        The admin role is hidden from every non-admin viewer (they can neither
        see it in role management nor pick it as a grant target)."""
        ok, resp = _require_any_perm(['users.manage', 'roles.manage'])
        if not ok:
            return resp
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        roles = list_roles(db_path)
        if not _is_admin_user(user or {}):
            admin_id = _admin_role_id()
            roles = [r for r in roles if r.get('id') != admin_id]
        # Attach the permission set for each role
        for r in roles:
            r['permissions'] = get_role_permissions(db_path, r['id'])
        return jsonify(roles)

    @app.route('/api/roles', methods=['POST'])
    def create_role_endpoint():
        """Create a role. Requires roles.manage (admin passes)."""
        ok, resp = _require_user_or_perm('roles.manage')
        if not ok:
            return resp
        data = request.json or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '角色名称不能为空'}), 400
        if any(r['name'] == name for r in list_roles(db_path)):
            return jsonify({'error': '角色名称已存在'}), 409
        role_id = create_role(db_path, name, label=data.get('label', ''), description=data.get('description', ''))
        if role_id is None:
            return jsonify({'error': '创建失败'}), 500
        # Optional initial permissions
        perms = data.get('permissions')
        if isinstance(perms, list):
            set_role_permissions(db_path, role_id, perms)
        r = get_role(db_path, role_id)
        r['user_count'] = 0
        r['permissions'] = get_role_permissions(db_path, role_id)
        return jsonify(r), 201

    @app.route('/api/roles/<int:id>', methods=['PUT'])
    def update_role_endpoint(id):
        """Update a role's label/description/permissions. Requires roles.manage
        (admin passes)."""
        ok, resp = _require_user_or_perm('roles.manage')
        if not ok:
            return resp
        role = get_role(db_path, id)
        if role is None:
            return jsonify({'error': '角色不存在'}), 404
        data = request.json or {}
        if 'label' in data or 'description' in data:
            update_role(db_path, id, label=data.get('label'), description=data.get('description'))
        if 'permissions' in data and isinstance(data.get('permissions'), list):
            set_role_permissions(db_path, id, data['permissions'])
        r = get_role(db_path, id)
        # user_count comes from list_roles (computes it via user_roles)
        for lr in list_roles(db_path):
            if lr['id'] == id:
                r['user_count'] = lr['user_count']
                break
        r['permissions'] = get_role_permissions(db_path, id)
        return jsonify(r)

    @app.route('/api/roles/<int:id>', methods=['DELETE'])
    def delete_role_endpoint(id):
        """Delete a role (non-system only). Requires roles.manage (admin passes)."""
        ok, resp = _require_user_or_perm('roles.manage')
        if not ok:
            return resp
        role = get_role(db_path, id)
        if role is None:
            return jsonify({'error': '角色不存在'}), 404
        if role.get('is_system'):
            return jsonify({'error': '内置角色不能删除'}), 403
        if not delete_role(db_path, id):
            return jsonify({'error': '删除失败'}), 500
        return jsonify({'ok': True})

    # Permission catalog endpoint (read-only)
    @app.route('/api/permissions', methods=['GET'])
    def list_permissions_endpoint():
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        if user.get('role') == 'admin':
            return jsonify(list_permissions(db_path))
        codes = _user_perm_codes(user)
        if 'users.manage' not in codes and 'roles.manage' not in codes:
            return jsonify({'error': '没有权限查看权限目录'}), 403
        return jsonify(list_permissions(db_path))

    # User-role association
    @app.route('/api/users/<int:user_id>/roles', methods=['GET'])
    def get_user_roles_endpoint(user_id):
        """A user's roles. Self, admin, or users.manage (admin passes). A non-admin
        users.manage holder is scoped to their own domains, and admin accounts are
        invisible to them (consistent with the user list)."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        is_self = user.get('user_id') == user_id
        is_admin = user.get('role') == 'admin'
        has_perm = 'users.manage' in _user_perm_codes(user)
        if not (is_self or is_admin or has_perm):
            return jsonify({'error': '没有权限查看此用户'}), 403
        if not is_admin:
            if _is_admin_user_id(user_id):
                return jsonify({'error': '没有权限查看此用户'}), 403
            target = get_user_by_id_full(db_path, user_id)
            if target is not None and not _in_user_domain(user, user_id, target.get('domains')):
                return jsonify({'error': '没有权限查看此用户'}), 403
        return jsonify({'role_ids': get_user_role_ids(db_path, user_id),
                        'role_names': get_user_role_names(db_path, user_id)})

    @app.route('/api/users/<int:user_id>/roles', methods=['PUT'])
    def set_user_roles_endpoint(user_id):
        """Assign one or more roles to a user. Requires users.manage (admin passes).
        Non-admins cannot grant the admin role and are scoped to their own domains."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        is_admin = user.get('role') == 'admin'
        if not is_admin and 'users.manage' not in _user_perm_codes(user):
            return jsonify({'error': '需要用户管理权限'}), 403
        # Non-admin: cannot touch admin accounts or users outside their domains.
        if not is_admin:
            if _is_admin_user_id(user_id):
                return jsonify({'error': '没有权限修改此用户'}), 403
            target = get_user_by_id_full(db_path, user_id)
            if target is not None and not _in_user_domain(user, user_id, target.get('domains')):
                return jsonify({'error': '没有权限修改此用户'}), 403
        data = request.json or {}
        role_ids = data.get('role_ids') or []
        if isinstance(role_ids, int):
            role_ids = [role_ids]
        if not isinstance(role_ids, list):
            return jsonify({'error': 'role_ids 必须是数组'}), 400
        # Built-in admin's role is locked: nobody (incl. admin) may modify it.
        if _is_builtin_admin_id(user_id):
            return jsonify({'error': '内置管理员的角色不可修改'}), 403
        # No privilege escalation: only admin may grant the admin role.
        err = _check_no_admin_grant(user, [int(r) for r in role_ids])
        if err:
            return err
        result = set_user_roles(db_path, user_id, role_ids)
        if result is None:
            return jsonify({'error': '更新失败'}), 500
        return jsonify({'role_ids': result,
                        'role_names': get_user_role_names(db_path, user_id)})

    # Current user's own permissions (used by frontend to gate menus)
    @app.route('/api/me/permissions', methods=['GET'])
    def me_permissions_endpoint():
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        # System-level: prefer token-embedded codes (platform-wide); fall back to
        # DB for pre-existing tokens.
        if 'permission_codes' in user:
            codes = set(user.get('permission_codes') or [])
        else:
            codes = get_user_permission_codes(db_path, user['user_id'], user.get('role'))
        # Map codes back to full permission objects for the frontend
        perms = list_permissions(db_path)
        code_to_perm = {p['code']: p for p in perms}
        return jsonify({
            'role': user.get('role'),
            'permissions': sorted(codes),
            'permission_objects': [code_to_perm[c] for c in sorted(codes) if c in code_to_perm],
        })


    # ========================================================================
    # System Settings
    # ========================================================================
    SENSITIVE_KEYS = {'model.api_key', 'mcp.agent_key', 'system.jwt_secret'}

    @app.route('/api/system/settings', methods=['GET'])
    def get_system_settings():
        all_settings = get_all_settings(db_path)
        result = {}
        for key, value in all_settings.items():
            if key in SENSITIVE_KEYS:
                if len(value) > 6:
                    result[key] = value[:3] + '***' + value[-3:]
                else:
                    result[key] = '***'
            else:
                result[key] = value
        return jsonify(result)

    @app.route('/api/system/settings', methods=['PUT'])
    def update_system_settings():
        data = request.json
        if not data:
            return jsonify({'error': '请提供设置数据'}), 400
        for key, value in data.items():
            set_setting(db_path, key, str(value) if value is not None else '')
        return jsonify({'success': True, 'count': len(data)})

    @app.route('/api/system/services/health')
    def services_health():
        import urllib.request as _urlopen
        import json as _json
        services = []
        # Use Docker service names instead of localhost since each container has its own network namespace
        service_specs = [
            ('research', 8766, '制造情报 API'),
            ('sales', 8767, '销售情报 API'),
            ('meilisearch', 7700, 'Meilisearch'),
        ]
        for hostname, port, name in service_specs:
            try:
                url = f'http://{hostname}:{port}/api/health' if port != 7700 else f'http://{hostname}:{port}/health'
                with _urlopen.urlopen(url, timeout=3) as resp:
                    data = _json.loads(resp.read().decode())
                    is_up = data.get('status') in ('ok', 'available')
                    services.append({'name': name, 'port': port, 'status': 'up' if is_up else 'down', 'details': data.get('status', '')})
            except Exception as e:
                services.append({'name': name, 'port': port, 'status': 'down', 'details': str(e)[:100]})
        return jsonify({'services': services})

    # ========================================================================
    # MCP Server Auto-detection
    # ========================================================================

    @app.route('/api/system/mcp/info')
    def get_mcp_info():
        """自动检测 MCP 服务器信息，用于 AI Agent 集成配置"""
        import secrets
        import os
        import logging
        
        try:
            # 使用统一配置模块获取 MCP 服务器信息
            from config import get_mcp_config
            
            mcp_config = get_mcp_config()
            host = os.environ.get("MCP_HOST", "localhost")
            
            # 检测 API Key，优先从共享卷读取，否则从数据库读取
            shared_key_file = os.path.join('/app', 'shared_data', 'agent_key.txt')
            mcp_agent_key = None
            
            # Try shared volume first
            try:
                if os.path.exists(shared_key_file):
                    with open(shared_key_file, 'r') as f:
                        mcp_agent_key = f.read().strip()
            except Exception:
                pass
            
            # Fallback to database
            if not mcp_agent_key:
                mcp_agent_key = get_setting(db_path, 'mcp.agent_key')
            
            # Generate new key if still empty
            if not mcp_agent_key:
                mcp_agent_key = secrets.token_urlsafe(32)
                set_setting(db_path, 'mcp.agent_key', mcp_agent_key)
                # Also save to shared volume
                try:
                    os.makedirs(os.path.dirname(shared_key_file), exist_ok=True)
                    with open(shared_key_file, 'w') as f:
                        f.write(mcp_agent_key)
                except Exception:
                    pass

            # MCP 已注册工具列表（与 mcp_server/server.py 保持一致）
            _MCP_TOOLS = [
                # 采集方向工具
                {'name': 'list_domains', 'desc': '动态发现所有可用情报域'},
                {'name': 'get_agent_workflow', 'desc': '获取指定域的 Agent 工作流配置'},
                {'name': 'list_active_projects', 'desc': '列出 active 采集项目'},
                {'name': 'get_project_detail', 'desc': '获取单个采集项目详情'},
                # 情报管理
                {'name': 'search_intelligence', 'desc': '按关键词搜索情报'},
                {'name': 'list_intelligence', 'desc': '列出情报'},
                {'name': 'get_intelligence', 'desc': '获取单条情报详情'},
                {'name': 'create_intelligence', 'desc': '创建新情报'},
                {'name': 'update_intelligence_status', 'desc': '更新情报状态'},
                {'name': 'add_comment', 'desc': '为情报添加评论'},
                # 数据源
                {'name': 'list_data_sources', 'desc': '列出数据源'},
                {'name': 'create_data_source', 'desc': '创建数据源'},
                {'name': 'get_crawl_logs', 'desc': '获取采集日志'},
                # 实体管理
                {'name': 'list_entities', 'desc': '列出实体'},
                {'name': 'get_entity_by_name', 'desc': '按名称查找实体'},
                {'name': 'link_intelligence_to_entity', 'desc': '将情报关联到实体'},
                {'name': 'get_intel_for_entity', 'desc': '获取实体相关情报'},
                # 通知
                {'name': 'list_subscriptions', 'desc': '列出用户订阅'},
                {'name': 'create_subscription', 'desc': '创建订阅'},
                {'name': 'get_notifications', 'desc': '获取通知'},
                # 系统
                {'name': 'system_status', 'desc': '获取系统状态'},
            ]

            # 返回 MCP 服务器信息
            return jsonify({
                'url': mcp_config['url'],
                'port': mcp_config['port'],
                'path': mcp_config['path'],
                'auto_detected': True,
                'agent_key': mcp_agent_key,
                'transport': mcp_config['transport'],
                'tools_count': len(_MCP_TOOLS),
                'tools': _MCP_TOOLS,
            })
        except Exception as e:
            logging.error(f"MCP info API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/system/mcp/key/reset', methods=['POST'])
    def reset_mcp_key():
        """重置 MCP Server API Key"""
        import secrets
        new_key = secrets.token_urlsafe(32)
        set_setting(db_path, 'mcp.agent_key', new_key)
        return jsonify({'success': True, 'agent_key': new_key})

    @app.route('/api/system/mcp/auth/toggle', methods=['POST'])
    def toggle_mcp_auth():
        """切换 MCP 服务器 API Key 验证开关"""
        import json
        from pathlib import Path
        
        # 读取当前开关状态
        config_path = Path(__file__).parent.parent / 'config' / 'ports.json'
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            return jsonify({'error': f'无法读取配置：{e}'}), 500
        
        # 切换开关
        current_state = config.get('mcp', {}).get('enable_auth', True)
        new_state = not current_state
        
        # 更新配置
        if 'mcp' not in config:
            config['mcp'] = {}
        config['mcp']['enable_auth'] = new_state
        
        # 保存配置
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return jsonify({'error': f'无法保存配置：{e}'}), 500
        
        return jsonify({
            'success': True,
            'enabled': new_state,
            'message': f"API Key 验证已 {'启用' if new_state else '禁用'}"
        })

    @app.route('/api/system/mcp/auth/status')
    def get_mcp_auth_status():
        """获取 MCP 服务器 API Key 验证开关状态"""
        import json
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / 'config' / 'ports.json'
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            enabled = config.get('mcp', {}).get('enable_auth', True)
        except Exception:
            enabled = True
        
        return jsonify({
            'enabled': enabled,
            'status': '启用' if enabled else '禁用'
        })

    # ========================================================================
    # Domain Controller (admin)
    # ========================================================================

    _DOMAINS_FILE = os.path.join(os.path.dirname(__file__), 'domains.json')

    def _load_domains():
        """Load domain registry from shared JSON file."""
        try:
            with open(_DOMAINS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'domains': []}

    def _save_domains(data):
        """Persist domain registry to shared JSON file."""
        with open(_DOMAINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @app.route('/api/system/domains')
    def list_domains():
        """List all registered domains (admin endpoint)."""
        data = _load_domains()
        return jsonify(data)

    @app.route('/api/system/domains/enabled')
    def enabled_domains():
        """Return enabled domains the current user may switch to.

        For the domain switcher: admin sees every enabled domain; a user with a
        non-empty domain whitelist sees only the enabled domains in their list;
        a legacy user (empty whitelist) sees all enabled domains (backward
        compatible — matches the per-domain API gating rule).
        """
        data = _load_domains()
        enabled = [d for d in data.get('domains', []) if d.get('enabled', True)]

        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
        user = _verify_token(token) if token else None
        if not user:
            return jsonify({'domains': []}), 401
        if user.get('role') == 'admin':
            return jsonify({'domains': enabled})
        domains = user.get('domains') or []
        if not domains:
            return jsonify({'domains': enabled})
        return jsonify({'domains': [d for d in enabled if d.get('slug') in domains]})

    @app.route('/api/system/domains/<int:port>/toggle', methods=['PUT'])
    def toggle_domain(port):
        """Enable or disable a domain by port (admin endpoint)."""
        body = request.json or {}
        new_enabled = body.get('enabled', True)
        data = _load_domains()
        for d in data.get('domains', []):
            if d['port'] == port:
                d['enabled'] = new_enabled
                _save_domains(data)
                return jsonify({'success': True, 'port': port, 'enabled': new_enabled})
        return jsonify({'error': '域不存在'}), 404

    # ========================================================================
    # Notifications (admin)
    # ========================================================================

    @app.route('/api/notifications')
    def list_notifications():
        """List user notifications."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user_id = user['user_id']
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 100))
        
        # Get notifications from settings table (notifications are stored as key-value)
        notifs = []
        try:
            with get_db(db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Notifications are stored with key prefix 'notif_'
                query = "SELECT key, value FROM settings WHERE key LIKE 'notif_%' ORDER BY rowid DESC LIMIT ?"
                if unread_only:
                    query = "SELECT key, value FROM settings WHERE key LIKE 'notif_%' AND value NOT LIKE '%read_at:%' ORDER BY rowid DESC LIMIT ?"
                rows = conn.execute(query, (limit,)).fetchall()
                for row in rows:
                    try:
                        import json as _json
                        notif = _json.loads(row['value'])
                        notif['_id'] = row['key']
                        notifs.append(notif)
                    except:
                        pass
        except Exception as e:
            print(f'Error loading notifications: {e}')
        
        unread = len([n for n in notifs if not n.get('read_at')])
        return jsonify({'items': notifs, 'unread': unread})

    @app.route('/api/notifications/unread-count')
    def unread_notification_count():
        """Get unread notification count."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user_id = user['user_id']
        unread = 0
        try:
            with get_db(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT COUNT(*) as cnt FROM settings WHERE key LIKE 'notif_%' AND value NOT LIKE '%read_at:%'").fetchone()
                unread = rows['cnt'] if rows else 0
        except:
            pass
        
        return jsonify({'unread': unread})

    @app.route('/api/notifications/read-all', methods=['POST'])
    def mark_all_notifications_read():
        """Mark all notifications as read."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            with get_db(db_path) as conn:
                conn.execute("UPDATE settings SET value = value || ',' || 'read_at:' || datetime('now') WHERE key LIKE 'notif_%'")
                conn.commit()
        except Exception as e:
            print(f'Error marking notifications read: {e}')
        
        return jsonify({'success': True})

    @app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
    def mark_notification_read(notification_id):
        """Mark a single notification as read."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            with get_db(db_path) as conn:
                conn.execute("UPDATE settings SET value = value || ',' || 'read_at:' || datetime('now') WHERE key = ?", (f'notif_{notification_id}',))
                conn.commit()
        except Exception as e:
            print(f'Error marking notification read: {e}')
        
        return jsonify({'success': True})

    # ========================================================================
    # Audit Logs (admin)
    # ========================================================================

    @app.route('/api/audit/logs')
    def list_audit_logs():
        """List audit logs with filtering and pagination."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        action = request.args.get('action', '')
        resource = request.args.get('resource', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        logs = []
        try:
            with get_db(db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM history WHERE 1=1"
                params = []
                
                if action:
                    query += " AND method = ?"
                    params.append(action)
                if resource:
                    query += " AND detail LIKE ?"
                    params.append(f'%{resource}%')
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)
                
                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                rows = conn.execute(query, params).fetchall()
                for row in rows:
                    log = dict(row)
                    log['id'] = log['id']
                    logs.append(log)
        except Exception as e:
            print(f'Error loading audit logs: {e}')
        
        # Count total
        total = 0
        try:
            with get_db(db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT COUNT(*) as cnt FROM history WHERE 1=1"
                params = []
                if action:
                    query += " AND method = ?"
                    params.append(action)
                if resource:
                    query += " AND detail LIKE ?"
                    params.append(f'%{resource}%')
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)
                total = conn.execute(query, params).fetchone()['cnt']
        except:
            pass
        
        return jsonify({'items': logs, 'total': total})

    @app.route('/api/audit/logs/<int:log_id>')
    def get_audit_log(log_id):
        """Get single audit log detail."""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        log = None
        try:
            with get_db(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM history WHERE id = ?", (log_id,)).fetchone()
                if row:
                    log = dict(row)
        except Exception as e:
            print(f'Error loading audit log: {e}')
        
        if not log:
            return jsonify({'error': 'Not found'}), 404
        
        return jsonify(log)

    # --- Health ---
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    # ========================================================================
    # User Management
    # ========================================================================

    @app.route('/api/users', methods=['GET'])
    def list_users_endpoint():
        """List users with optional search. Requires users.manage (admin passes).

        Admin users are hidden from every non-admin viewer. A non-admin
        users.manage holder is scoped to their own domains: they can only see
        users who share at least one domain with them (plus themselves).
        Empty whitelist = all domains (legacy compat, matches domain gating)."""
        ok, resp = _require_user_or_perm('users.manage')
        if not ok:
            return resp
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        search = request.args.get('search', '')
        limit = int(request.args.get('limit', 100))
        result = list_users(db_path, search=search if search else None, limit=limit)
        is_admin = _is_admin_user(user or {})
        for it in list(result['items']):
            # 1) Admin accounts are invisible to non-admins.
            if not is_admin and (it.get('role') == 'admin' or any(int(r) == _admin_role_id() for r in (it.get('role_ids') or []))):
                result['items'].remove(it)
                continue
            # 2) Non-admin viewers are scoped to their own domains.
            if not is_admin and not _in_user_domain(user, it['id'], it.get('domains')):
                result['items'].remove(it)
        return jsonify(result)

    @app.route('/api/users/<int:user_id>', methods=['GET'])
    def get_user_endpoint(user_id):
        """Get a single user by ID. Self or users.manage (admin passes).

        A non-admin viewer is scoped to their own domains (and to admin
        accounts being invisible), matching the list endpoint."""
        token_user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not token_user:
            return jsonify({'error': 'Unauthorized'}), 401
        is_self = token_user.get('user_id') == user_id
        is_admin = token_user.get('role') == 'admin'
        has_perm = 'users.manage' in _user_perm_codes(token_user)
        if not (is_self or is_admin or has_perm):
            return jsonify({'error': '没有权限查看此用户'}), 403
        u = get_user_by_id_full(db_path, user_id)
        if u is None:
            return jsonify({'error': 'not found'}), 404
        # Admin accounts are invisible to non-admins.
        if not is_admin and _is_admin_user_id(user_id):
            return jsonify({'error': '没有权限查看此用户'}), 403
        # Non-admin viewers are scoped to their own domains.
        if not is_admin and not _in_user_domain(token_user, user_id, u.get('domains')):
            return jsonify({'error': '没有权限查看此用户'}), 403
        return jsonify(u)

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    def update_user_endpoint(user_id):
        """Update a user. Self or users.manage (admin passes); self may change own
        password, users.manage may change any user (incl. roles)."""
        token_user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not token_user:
            return jsonify({'error': 'Unauthorized'}), 401
        # Self / admin / users.manage can edit. Others cannot.
        is_self = token_user.get('user_id') == user_id
        is_admin = token_user.get('role') == 'admin'
        has_perm = 'users.manage' in _user_perm_codes(token_user)
        if not (is_self or is_admin or has_perm):
            return jsonify({'error': '没有权限修改此用户'}), 403
        # A non-admin can never edit an admin account. (Otherwise the role
        # checkboxes — which hide the admin role from them — would silently
        # strip admin on save, i.e. a non-admin could demote an admin.)
        if not is_admin and _is_admin_user_id(user_id):
            return jsonify({'error': '没有权限修改此用户'}), 403
        # Non-admin viewers are scoped to their own domains: they can only
        # edit users who share a domain with them (or themselves).
        if not is_admin:
            target = get_user_by_id_full(db_path, user_id)
            if target is None:
                return jsonify({'error': '用户不存在'}), 404
            if not _in_user_domain(token_user, user_id, target.get('domains')):
                return jsonify({'error': '没有权限修改此用户'}), 403
        data = request.json
        if not data:
            return jsonify({'error': '请提供更新数据'}), 400
        # Built-in admin: role, domains and login name are locked — the
        # built-in administrator must keep its built-in privileges. Only
        # display_name, remark and password may be changed for this account.
        target_is_builtin_admin = _is_builtin_admin_id(user_id)
        if target_is_builtin_admin:
            if data.get('username') or data.get('role_ids') is not None \
                    or data.get('role_id') is not None or 'domains' in data:
                return jsonify({'error': '内置管理员的登录名、角色和所属域不可修改'}), 403
        # Build fields dict (exclude password — handled separately).
        # Changing username / domains is sensitive (identity / access scope) and
        # requires users.manage (or admin); a self user may only edit display_name
        # and remark here.
        can_manage_roles = is_admin or has_perm
        fields = {}
        if data.get('username'):
            if not can_manage_roles:
                return jsonify({'error': '修改用户名需要用户管理权限'}), 403
            fields['username'] = data['username']
        if data.get('display_name'):
            fields['display_name'] = data['display_name']
        if 'remark' in data:
            fields['remark'] = (data.get('remark') or '').strip()
        if data.get('domains'):
            if not can_manage_roles:
                return jsonify({'error': '修改所属域需要用户管理权限'}), 403
            domains = data['domains']
            if isinstance(domains, list):
                fields['domains'] = ','.join([str(d) for d in domains if d])
            elif isinstance(domains, str):
                fields['domains'] = domains
        if data.get('role_ids') is not None:
            if not can_manage_roles:
                return jsonify({'error': '修改角色需要用户管理权限'}), 403
            role_ids = data.get('role_ids')
            if isinstance(role_ids, int):
                role_ids = [role_ids]
            if not isinstance(role_ids, list):
                return jsonify({'error': 'role_ids 必须是数组'}), 400
            # No privilege escalation: only admin may grant the admin role.
            err = _check_no_admin_grant(token_user, [int(r) for r in role_ids])
            if err:
                return err
            # Persist legacy role (highest privilege) + user_roles together
            set_user_roles(db_path, user_id, role_ids)
        elif data.get('role_id') is not None:
            if not can_manage_roles:
                return jsonify({'error': '修改角色需要用户管理权限'}), 403
            err = _check_no_admin_grant(token_user, [int(data['role_id'])])
            if err:
                return err
            # Legacy single-role path: map numeric role_id to name and sync both
            id_to_role = {1: 'admin', 2: 'power_user', 3: 'user', 4: 'agent'}
            role_name = id_to_role.get(int(data['role_id']), 'user')
            role_id_map = {r['name']: r['id'] for r in list_roles(db_path)}
            if role_name in role_id_map:
                set_user_roles(db_path, user_id, [role_id_map[role_name]])
        updated = update_user(db_path, user_id, fields)
        if updated is None:
            # If only role changed (fields empty), update_user returns None; reload
            updated = get_user_by_id_full(db_path, user_id)
        if updated is None:
            return jsonify({'error': '更新失败'}), 500
        # Handle password update separately
        if data.get('password') and len(data['password']) >= 6:
            update_user_password(db_path, user_id, data['password'])
        updated['role_ids'] = get_user_role_ids(db_path, user_id)
        updated['role_names'] = get_user_role_names(db_path, user_id)
        return jsonify(updated)

    @app.route('/api/users/batch/domains', methods=['PUT'])
    def batch_set_user_domains_endpoint():
        """Batch-set the domain access whitelist for multiple users. Admin only.

        Sets users.domains only — never touches roles or passwords. An empty
        `domains` list clears the whitelist (user can then access all enabled
        domains). Returns per-user success/failure so a partial failure is visible.
        Requires users.manage (admin passes).
        """
        ok, resp = _require_user_or_perm('users.manage')
        if not ok:
            return resp
        data = request.json or {}
        user_ids = data.get('user_ids') or []
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        if not isinstance(user_ids, list) or not user_ids:
            return jsonify({'error': 'user_ids 必须是非空数组'}), 400
        raw_domains = data.get('domains', [])
        if isinstance(raw_domains, list):
            domains_str = ','.join([str(d) for d in raw_domains if d])
        elif isinstance(raw_domains, str):
            domains_str = raw_domains
        else:
            return jsonify({'error': 'domains 必须是数组或字符串'}), 400
        # Validate requested slugs against enabled domains (empty = clear, always allowed)
        if domains_str:
            valid_slugs = {d.get('slug') for d in _load_domains().get('domains', []) if d.get('enabled', True)}
            requested = [s for s in domains_str.split(',') if s]
            invalid = [s for s in requested if s not in valid_slugs]
            if invalid:
                return jsonify({'error': '无效的域标识: ' + ', '.join(invalid)}), 400
        # Domain scope: a non-admin may only batch-update users within their own
        # domains (judged by the user's current whitelist, before the change).
        actor = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        is_admin = bool(actor) and actor.get('role') == 'admin'
        updated_ids, failed = [], []
        for uid in user_ids:
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                failed.append({'id': uid, 'error': '无效的用户ID'})
                continue
            if not is_admin:
                target = get_user_by_id_full(db_path, uid)
                if target is None:
                    failed.append({'id': uid, 'error': '用户不存在'})
                    continue
                if not _in_user_domain(actor, uid, target.get('domains')):
                    failed.append({'id': uid, 'error': '没有权限操作此用户'})
                    continue
            # Built-in admin's domain whitelist is locked.
            if _is_builtin_admin_id(uid):
                failed.append({'id': uid, 'error': '内置管理员的所属域不可修改'})
                continue
            # domains='' clears the whitelist (update_user applies empty string, not None)
            res = update_user(db_path, uid, {'domains': domains_str})
            if res is None:
                failed.append({'id': uid, 'error': '更新失败或用户不存在'})
            else:
                updated_ids.append(res['id'])
        return jsonify({
            'updated': len(updated_ids),
            'updated_ids': updated_ids,
            'failed': failed,
            'domains': domains_str.split(',') if domains_str else []
        })

    @app.route('/api/users', methods=['POST'])
    def create_user_endpoint():
        """Create a new user. Requires users.manage (admin passes). Non-admins cannot
        grant the admin role."""
        token_user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not token_user:
            return jsonify({'error': 'Unauthorized'}), 401
        if token_user.get('role') != 'admin' and 'users.manage' not in _user_perm_codes(token_user):
            return jsonify({'error': '只有用户管理员可以创建用户'}), 403
        data = request.json
        if not data:
            return jsonify({'error': '请提供用户数据'}), 400
        username = data.get('username', '').strip()
        display_name = data.get('display_name', '').strip()
        password = data.get('password', '')
        role_id = int(data.get('role_id', 3))
        domains = data.get('domains', [])
        if not username or not display_name:
            return jsonify({'error': '用户名和显示名称不能为空'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': '密码至少6位'}), 400
        # Role handling: prefer multi-role role_ids, fall back to legacy single role_id
        role_ids = data.get('role_ids')
        if role_ids is None:
            role_ids = [role_id]
        elif isinstance(role_ids, int):
            role_ids = [role_ids]
        if not isinstance(role_ids, list) or not all(isinstance(r, (int, float)) for r in role_ids):
            return jsonify({'error': 'role_ids 必须是数字数组'}), 400
        if not role_ids:
            role_ids = [3]  # default to 'user'
        # No privilege escalation: only admin may grant the admin role.
        err = _check_no_admin_grant(token_user, [int(r) for r in role_ids])
        if err:
            return err
        if isinstance(domains, str):
            domains = [d.strip() for d in domains.split(',') if d.strip()]
        # Domain scope: a non-admin may only create users within their own
        # domains, so they can actually see and manage the user they create.
        # (An empty/all-domains whitelist puts the new user out of their scope.)
        if token_user.get('role') != 'admin':
            actor_domains = _normalize_domains(token_user.get('domains'))
            if actor_domains and not any(d in actor_domains for d in _normalize_domains(domains)):
                return jsonify({'error': '只能在自己所属的域内创建用户'}), 403
        # create_user sets a placeholder role; set_user_roles below re-syncs
        # users.role to the highest-privilege assigned role.
        uid = create_user(db_path, username, display_name, password, role='user', domains=domains, remark=data.get('remark', ''))
        if uid is None:
            return jsonify({'error': '创建失败（用户名可能已存在）'}), 409
        set_user_roles(db_path, uid, role_ids)
        u = get_user_by_id_full(db_path, uid)
        if u is None:
            return jsonify({'error': '创建后读取失败'}), 500
        u['role_ids'] = get_user_role_ids(db_path, uid)
        u['role_names'] = get_user_role_names(db_path, uid)
        return jsonify(u), 201

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    def delete_user_endpoint(user_id):
        """Delete (soft-disable) a user. Requires users.manage (admin passes).
        A non-admin cannot delete an admin account."""
        ok, resp = _require_user_or_perm('users.manage')
        if not ok:
            return resp
        if user_id == 1:
            return jsonify({'error': '不能删除超级管理员'}), 403
        actor = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not actor or actor.get('role') != 'admin':
            if _is_admin_user_id(user_id):
                return jsonify({'error': '不能删除管理员账号'}), 403
            # Non-admins are scoped to their own domains.
            target = get_user_by_id_full(db_path, user_id)
            if target is None:
                return jsonify({'error': '用户不存在'}), 404
            if not _in_user_domain(actor, user_id, target.get('domains')):
                return jsonify({'error': '没有权限删除此用户'}), 403
        if not delete_user(db_path, user_id):
            return jsonify({'error': '删除失败'}), 500
        return jsonify({'ok': True})

    # ========================================================================
    # Authentication
    # ========================================================================

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        """Authenticate user and return JWT token."""
        data = request.json
        if not data:
            return jsonify({'error': '请提供用户名和密码'}), 400
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        user = authenticate_user(db_path, username, password)
        if user is None:
            return jsonify({'error': '用户名或密码错误'}), 401
        # System-level RBAC: compute the user's roles + effective permission codes
        # HERE (research = system/primary domain that owns the identity store) and
        # embed them in the JWT. Both domains then resolve permissions from the
        # token, so a user's roles are platform-wide regardless of which domain
        # backend enforces them (sales container does not mount the research DB).
        user['role_ids'] = get_user_role_ids(db_path, user['id'])
        user['permission_codes'] = sorted(get_user_permission_codes(db_path, user['id'], user.get('role')))
        token = _generate_token(user)
        return jsonify({
            'token': token,
            'user': user,
        })

    # ── 自助注册（手机号 + 短信验证码 + 用户名 + 密码，role=user，免审核） ──
    # 内存限频表：phone -> {last_send_ts, day_date, day_count}
    _sms_rate = {}
    _SMS_COOLDOWN_SEC = 60        # 同号两次发码最小间隔
    _SMS_MAX_PER_DAY = 10         # 同号每日发码上限

    @app.route('/api/auth/sms/send', methods=['POST'])
    def auth_sms_send():
        """发送手机验证码（限频：同号 60s 冷却 + 每日 10 次）。"""
        data = request.json or {}
        phone = (data.get('phone') or '').strip()
        if not phone or not phone.isdigit() or not (11 <= len(phone) <= 15):
            return jsonify({'error': '请输入有效的手机号码'}), 400
        import time as _time
        now_ts = _time.time()
        today = datetime.now().strftime('%Y-%m-%d')
        rec = _sms_rate.get(phone, {'last_send_ts': 0, 'day_date': '', 'day_count': 0})
        if rec['day_date'] != today:
            rec['day_date'] = today
            rec['day_count'] = 0
        if rec['day_count'] >= _SMS_MAX_PER_DAY:
            return jsonify({'error': '今日发送次数已达上限，请明天再试'}), 429
        if now_ts - rec['last_send_ts'] < _SMS_COOLDOWN_SEC:
            wait = int(_SMS_COOLDOWN_SEC - (now_ts - rec['last_send_ts']))
            return jsonify({'error': f'发送过于频繁，请 {wait} 秒后再试'}), 429
        from core.sms import send_verify_code
        ok, msg = send_verify_code(phone, scene='register')
        if not ok:
            return jsonify({'error': msg}), 502
        rec['last_send_ts'] = now_ts
        rec['day_count'] += 1
        _sms_rate[phone] = rec
        return jsonify({'ok': True, 'message': msg, 'cooldown': _SMS_COOLDOWN_SEC})

    @app.route('/api/auth/register', methods=['POST'])
    def auth_register():
        """自助注册：用户名 + 手机号 + 短信验证码 + 密码。

        校验手机号验证码（PNVS / test_mode）→ 建 user（role=user，免审核）
        → 直接签发 JWT，前端注册成功即登录进门户。
        """
        # 注册开关（系统设置，实时生效）。默认关闭；显式开启才放行。
        from core.db import get_setting
        reg_flag = get_setting(db_path, 'register_enabled')
        if reg_flag not in ('1', 'true', 'True'):
            return jsonify({'error': '注册通道已关闭，暂不开放新用户注册'}), 403
        data = request.json or {}
        username = (data.get('username') or '').strip()
        phone = (data.get('phone') or '').strip()
        code = (data.get('code') or '').strip()
        password = data.get('password') or ''

        if not username:
            return jsonify({'error': '请输入用户名'}), 400
        if not (2 <= len(username) <= 32) or not username.replace('_', '').replace('-', '').isalnum():
            return jsonify({'error': '用户名需 2-32 位字母、数字、下划线或连字符'}), 400
        if not phone or not phone.isdigit() or not (11 <= len(phone) <= 15):
            return jsonify({'error': '请输入有效的手机号码'}), 400
        if not code or not code.isdigit():
            return jsonify({'error': '请输入短信验证码'}), 400
        if len(password) < 6:
            return jsonify({'error': '密码至少 6 位'}), 400

        # 用户名 / 手机号唯一性（友好提示）
        if get_user_by_username(db_path, username):
            return jsonify({'error': '用户名已被占用，请换一个'}), 409
        if get_user_by_phone(db_path, phone):
            return jsonify({'error': '该手机号已注册，请直接登录'}), 409

        # 短信验证码校验（PNVS 真实 / test_mode 本地）
        from core.sms import verify_code
        ok, msg = verify_code(phone, code)
        if not ok:
            return jsonify({'error': msg}), 400

        user_id, err = create_user_with_phone(db_path, username, password, phone,
                                               display_name=username)
        if user_id is None:
            return jsonify({'error': err or '注册失败'}), 409

        # 注册即登录：构造 user + 签发 JWT
        user = {
            'id': user_id,
            'username': username,
            'display_name': username,
            'role': 'user',
            'domains': [],
        }
        user['role_ids'] = get_user_role_ids(db_path, user_id)
        user['permission_codes'] = sorted(get_user_permission_codes(db_path, user_id, 'user'))
        token = _generate_token(user)
        return jsonify({
            'ok': True,
            'message': '注册成功',
            'token': token,
            'user': user,
        })

    @app.route('/api/auth/check')
    def auth_check():
        """Validate JWT token (used by nginx auth_request)."""
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response('Unauthorized', status=401)
        token = auth_header[7:]
        payload = _verify_token(token)
        if payload is None:
            return Response('Unauthorized', status=401)
        return Response('Authorized', status=200)

    # ========================================================================
    # AI Analyst
    # ========================================================================

    def _parse_reasoning(raw_reasoning):
        """从 reasoning 字段分离 thinking（推理过程）和 answer（最终回复）。

        支持两种格式：
        1. 有分隔标记：'...thinking...\\n\\nFinal Output Generation: ...\\nanswer...'
        2. 无分隔标记：整段都是 thinking（模型习惯性地输出思考过程）

        返回 (thinking, answer) 元组，未分离时 thinking=''。
        """
        import re as _re

        # 检测 thinking 标记
        thinking_pattern = (
            r'(?:^|\n)\s*(?:Here\'s a thinking process|## Reasoning|'
            r'让我分析一下|## 分析过程|## 思考过程)'
        )
        has_thinking = bool(_re.search(thinking_pattern, raw_reasoning))

        if not has_thinking:
            return '', raw_reasoning

        # 尝试找分隔标记（放宽匹配：允许前面的编号、markdown 格式等）
        separator_patterns = [
            r'(?:^|\\n).*?Final\\s+Output[\\s:]*',
            r'(?:^|\\n).*?最终答案[\\s:]*',
            r'(?:^|\\n).*?##\\s+Final\\s+Output',
            r'(?:^|\\n).*?##\\s+最终答案',
        ]
        split_idx = None
        for sp in separator_patterns:
            m = _re.search(sp, raw_reasoning, _re.IGNORECASE)
            if m:
                split_idx = m.start()
                break

        if split_idx is not None:
            thinking = raw_reasoning[:split_idx].strip()
            answer = raw_reasoning[split_idx:].strip()
            # 清理分隔标记前的多余内容
            answer = _re.sub(r'^[ \\t\\n\\r]+', '', answer)
            return thinking, answer
        else:
            # 有 thinking 标记但没有分隔 → 整段是思考过程，无正式回复
            return raw_reasoning.strip(), ''

    # Deprecated: AI Analyst real-time Q&A (replaced by scheduled reports)
    @app.route('/api/analyst/analyze', methods=['POST'])
    def analyst_analyze():
        """AI 分析师：基于情报数据回答用户问题。

        流程：搜索相关情报 → 构建上下文 → 调用 AI 模型 → 返回分析结果
        """
        import requests as _requests
        import collections as _collections
        import json as _json
        from core.search import create_search_engine, NoopEngine

        data = request.json or {}
        query = (data.get('query') or '').strip()
        domain = data.get('domain') or spec['slug']
        max_results = min(int(data.get('max_results') or 20), 50)

        if not query:
            return jsonify({'error': '查询内容不能为空'}), 400

        # --- Step 1: 搜索相关情报（限制数量以减少 token） ---
        search_config = spec.get('search') or {}
        search_engine = create_search_engine(db_path, search_config)
        search_result = search_engine.search(query, limit=max(3, max_results))
        search_items = search_result.get('items', [])

        # Meilisearch 未索引或不可用时，降级到 SQLite 模糊搜索
        if not search_items:
            sqlite_engine = NoopEngine(db_path, {})
            sqlite_result = sqlite_engine.search(query, limit=3)
            search_items = sqlite_result.get('items', [])

        # 统计摘要（给 AI 直接引用数据用）— 精简格式
        stats = {}
        if search_items:
            if any(item.get('category') for item in search_items):
                cat_counts = _collections.Counter(item.get('category', '未分类') for item in search_items)
                stats['category'] = dict(cat_counts)
            if any(item.get('company') for item in search_items):
                comp_counts = _collections.Counter(item.get('company', '').strip() for item in search_items if item.get('company', '').strip())
                if comp_counts:
                    stats['company'] = dict(comp_counts)
            if any(item.get('created_at') for item in search_items):
                month_counts = _collections.Counter((item.get('created_at', '') or '')[:7] for item in search_items if item.get('created_at', '') and len(item['created_at']) >= 7)
                if month_counts:
                    sorted_months = sorted(month_counts.keys())
                    stats['trend'] = {sorted_months[i]: month_counts[sorted_months[i]] for i in range(len(sorted_months))}

        stats_json = _json.dumps(stats, ensure_ascii=False) if stats else '{}'

        # 领域配置
        domain_info = {
            'title': spec.get('title_prefix', domain),
            'statuses': {k: v for k, v in spec.get('statuses', [])},
            'agent_names': spec.get('agent_names', []),
        }

        # 将搜索结果格式化为结构化上下文（精简版）
        context_parts = []
        for idx, item in enumerate(search_items[:3], start=1):
            parts = [f"【情报 #{item.get('id', idx)}】标题: {item.get('title', '')}"]
            if item.get('category'):
                parts.append(f"分类: {item['category']}")
            if item.get('company'):
                parts.append(f"公司: {item['company']}")
            if item.get('created_at'):
                parts.append(f"时间: {item['created_at'][:10]}")
            context_parts.append(' | '.join(parts))

        context_text = '\\n\\n---\\n\\n'.join(context_parts)

        # 如果没搜到结果，也告诉 AI
        if not context_parts:
            context_text = '(未搜索到相关情报记录)'

        # 统计摘要（给 AI 直接引用数据用）— 精简 JSON
        stats_text = '\\n\\n## 数据摘要\\n' + _json.dumps(stats, ensure_ascii=False) if stats else '\\n\\n## 数据摘要\\n无数据'

        system_prompt = """你是一位专业情报分析师。你的每次回复必须包含 **文字分析 + 数据图表** 两部分，缺一不可。

## 回复格式要求（严格遵守）

### 第一部分：文字分析（必须有）
- 用结构化段落回答用户问题，包含：
  1. **核心发现**：2-3 句话概括最重要的结论
  2. **详细分析**：用数字支撑观点，引用具体情报编号（如「情报 #1」）
  3. **趋势判断**：基于数据给出方向性判断
  4. **行动建议**：一行总结性建议
- 文字分析是回复的核心，图表是辅助。文字不能少于 100 字。
- 用中文回答。

### 第二部分：数据图表（必须有）
- 在文字分析结束后，必须用以下格式嵌入数据图表代码块（至少 1 个）：
  
  ```chart
  {
    "type": "pie",
    "title": "分类分布",
    "data": [{"name": "AI应用", "value": 8}, {"name": "MES系统", "value": 5}]
  }
  ```

- 可选图表类型：
  - `pie`：分类/占比分布
  - `bar`：横向/纵向对比
  - `line`：趋势变化（需包含 `labels` 和 `data` 字段）

- 图表数据必须从「数据摘要」中实际引用，不得编造数据。

## 重要原则
1. **文字优先**：没有文字分析的回复视为不合格
2. **图表必须**：每次回复至少生成 1 个图表代码块
3. **数据真实**：所有图表数据和文字分析必须基于提供的情报数据
4. **结构清晰**：使用 Markdown 格式，段落之间空一行
"""

        user_prompt = f"""## 用户问题
{query}

## 相关情报数据（{len(search_items)} 条）
{context_text}

{stats_text}"""

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]

        # --- Step 3: 调用 AI 模型 ---
        provider = get_setting(db_path, 'model.provider') or 'openai'
        api_base_url = (get_setting(db_path, 'model.api_base_url') or '').strip()
        api_key = get_setting(db_path, 'model.api_key') or ''
        model_name = get_setting(db_path, 'model.name') or ''

        if not api_key:
            return jsonify({'error': 'AI 模型未配置，请在系统设置中配置 API Key'}), 400
        if not model_name:
            return jsonify({'error': 'AI 模型未配置，请在系统设置中配置模型名称'}), 400

        timeout = 90  # 分析师分析超时（模型响应较慢）
        headers = {'Content-Type': 'application/json'}

        if provider == 'anthropic':
            if not api_base_url:
                api_base_url = 'https://api.anthropic.com'
            url = f'{api_base_url.rstrip("/")}/v1/messages'
            headers['x-api-key'] = api_key
            headers['anthropic-version'] = '2023-06-01'
            payload = {
                'model': model_name,
                'max_tokens': 4096,
                'messages': messages,
            }
        else:
            # OpenAI 兼容格式（openai, custom, zhipu, etc.）
            if not api_base_url:
                api_base_url = 'https://api.openai.com/v1'
            url = f'{api_base_url.rstrip("/")}/chat/completions'
            headers['Authorization'] = f'Bearer {api_key}'
            payload = {
                'model': model_name,
                'messages': messages,
                'max_tokens': 500,
            }

        try:
            resp = _requests.post(url, headers=headers, json=payload, timeout=timeout)

            if resp.status_code != 200:
                error_text = resp.text[:500]
                return jsonify({
                    'error': f'AI 模型调用失败 (HTTP {resp.status_code}): {error_text}',
                    'searched': len(search_items),
                }), 502

            body = resp.json()

            # 安全校验：body 必须是 dict
            if not isinstance(body, dict):
                return jsonify({
                    'error': 'AI 模型返回格式异常',
                    'detail': f'expected dict, got {type(body).__name__}',
                    'searched': len(search_items),
                }), 500

            # Extract response text with thinking separation
            analysis = ''
            thinking = ''

            if provider == 'anthropic':
                content_blocks = body.get('content', [])
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text = block.get('text', '')
                            if text:
                                analysis += text
            else:
                choices = body.get('choices', [])
                if choices and isinstance(choices[0], dict):
                    message = choices[0].get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content')
                        analysis = content if content else ''
                        # 回退：某些模型（如 Ornith）将文本放在 reasoning 字段
                        raw_reasoning = message.get('reasoning') or ''
                        if not analysis and raw_reasoning:
                            analysis = raw_reasoning

                        # 解析 reasoning：分离 thinking 和最终回复
                        # 情况A：content 有效 + reasoning 有 thinking → 从 reasoning 提取 thinking
                        # 情况B：content 为空 + reasoning 有全部内容 → 解析 reasoning 分离
                        if raw_reasoning:
                            t, a = _parse_reasoning(raw_reasoning)
                            if t:
                                thinking = t
                                if content:
                                    analysis = content  # 优先用 content 作为正式回复
                                elif a:
                                    analysis = a
                                elif not content:
                                    # 模型只有思考过程没有正式回复（未完成），
                                    # 直接返回空 analysis，前端会显示 thinking 提示用户
                                    analysis = ''

            # 如果是 error 响应（某些提供商在 200 中返回错误）
            if 'error' in body and body['error']:
                err_info = body['error']
                err_msg = err_info.get('message', '') if isinstance(err_info, dict) else str(err_info)
                return jsonify({
                    'error': f'AI 模型返回错误: {err_msg[:300]}',
                    'searched': len(search_items),
                }), 500

            if not analysis and not thinking:
                return jsonify({
                    'error': 'AI 模型未返回有效分析结果',
                    'detail': f'provider={provider}, model={model_name}, status_code=200, body_keys={list(body.keys()) if isinstance(body, dict) else type(body).__name__}',
                    'searched': len(search_items),
                }), 500

            # 构建图表配置
            charts = []
            if stats:
                if 'category' in stats and stats['category']:
                    charts.append({
                        'type': 'pie',
                        'title': '分类分布',
                        'data': [{'name': k, 'value': v} for k, v in sorted(stats['category'].items(), key=lambda x: -x[1])],
                    })
                if 'company' in stats and stats['company']:
                    charts.append({
                        'type': 'bar',
                        'title': '公司分布',
                        'data': [{'name': k, 'value': v} for k, v in sorted(stats['company'].items(), key=lambda x: -x[1])],
                    })
                if 'trend' in stats and stats['trend']:
                    trend_data = stats['trend']
                    labels = list(trend_data.keys())
                    values = list(trend_data.values())
                    charts.append({
                        'type': 'line',
                        'title': '月度情报趋势',
                        'labels': labels,
                        'data': values,
                    })

            return jsonify({
                'analysis': analysis,
                'thinking': thinking,
                'searched': len(search_items),
                'model': body.get('model', model_name),
                'usage': body.get('usage', {}),
                'charts': charts,
            })

        except _requests.exceptions.Timeout:
            return jsonify({
                'error': f'AI 模型请求超时（超过 {timeout} 秒），请稍后重试',
                'searched': len(search_items),
            }), 408
        except _requests.exceptions.ConnectionError as e:
            return jsonify({
                'error': f'无法连接 AI 模型服务: {str(e)[:200]}',
                'searched': len(search_items),
            }), 502
        except Exception as e:
            import logging
            logging.error(f"Analyst API error: {e}")
            return jsonify({
                'error': f'分析失败: {str(e)[:200]}',
                'searched': len(search_items),
            }), 500

    def _now_iso():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # ─── 平台级 LLM 配置（所有域共享） ─────────────────────────

    @app.route('/api/system/llm', methods=['GET'])
    @require_auth
    def get_llm_settings():
        """获取平台级 LLM 配置（api_key 脱敏）"""
        from config import get_llm_config
        cfg = get_llm_config()
        api_key = cfg.get('api_key', '')
        if len(api_key) > 6:
            cfg['api_key_masked'] = api_key[:3] + '***' + api_key[-3:]
        else:
            cfg['api_key_masked'] = '***' if api_key else ''
        cfg.pop('api_key', None)  # 不返回明文
        return jsonify(cfg)

    @app.route('/api/system/llm', methods=['PUT'])
    @require_auth
    def update_llm_settings():
        """更新平台级 LLM 配置"""
        from config import get_llm_config, save_llm_config
        data = request.json or {}
        # 读取当前配置，合并更新（api_key 为空/脱敏值时不更新）
        current = get_llm_config()
        new_key = data.get('api_key', '').strip()
        if new_key and '***' not in new_key:
            current['api_key'] = new_key
        elif new_key:
            # 脱敏值，不更新 key
            pass
        for k in ('provider', 'api_base_url', 'model_name', 'temperature', 'max_tokens'):
            if k in data and data[k] not in (None, ''):
                current[k] = data[k]
        save_llm_config(current)
        return jsonify({'ok': True})

    @app.route('/api/system/llm/test', methods=['POST'])
    @require_auth
    def test_llm_connection():
        """测试 LLM 连接"""
        from core.scheduler.llm_client import call_llm
        result = call_llm("你是测试助手。", "请回复：ok", temperature=0.1, max_tokens=50, timeout=15)
        if result.get('ok'):
            return jsonify({'ok': True, 'model': '已连通'})
        return jsonify({'ok': False, 'error': result.get('error', '未知错误')}), 500

    # ─── Tavily 搜索配置 ──────────────────────────────────────────

    @app.route('/api/system/tavily', methods=['GET'])
    @require_auth
    def get_tavily_settings():
        """获取 Tavily 搜索配置（api_key 脱敏）"""
        from config import get_tavily_config
        cfg = get_tavily_config()
        api_key = cfg.get('api_key', '')
        if len(api_key) > 6:
            cfg['api_key_masked'] = api_key[:5] + '***' + api_key[-3:]
        else:
            cfg['api_key_masked'] = '***' if api_key else ''
        cfg.pop('api_key', None)
        return jsonify(cfg)

    @app.route('/api/system/tavily', methods=['PUT'])
    @require_auth
    def update_tavily_settings():
        """更新 Tavily 搜索配置"""
        from config import get_tavily_config, save_tavily_config
        data = request.json or {}
        current = get_tavily_config()
        new_key = data.get('api_key', '').strip()
        if new_key and '***' not in new_key:
            current['api_key'] = new_key
        if 'base_url' in data and data['base_url'] not in (None, ''):
            current['base_url'] = data['base_url']
        save_tavily_config(current)
        return jsonify({'ok': True})

    # ─── 注册开放开关 ──────────────────────────────────────────
    # 存 DB settings（实时生效，改一次无需重建容器）。默认关闭（未设置 = 关）。
    def _register_enabled(db_path):
        from core.db import get_setting
        flag = get_setting(db_path, 'register_enabled')
        return flag in ('1', 'true', 'True')

    @app.route('/api/auth/register-status', methods=['GET'])
    def register_status():
        """公开：注册通道是否开放（登录页/注册页/分享页读取，无需登录）。"""
        return jsonify({'register_enabled': _register_enabled(db_path)})

    @app.route('/api/system/register', methods=['GET'])
    @require_auth
    def get_register_settings():
        """获取注册开放开关（admin）。"""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user or user.get('role') != 'admin':
            return jsonify({'error': '仅 admin 可配置'}), 403
        return jsonify({'register_enabled': _register_enabled(db_path)})

    @app.route('/api/system/register', methods=['PUT'])
    @require_auth
    def update_register_settings():
        """更新注册开放开关（admin）。enabled: true/false。"""
        user = _verify_token(request.headers.get('Authorization', '').replace('Bearer ', ''))
        if not user or user.get('role') != 'admin':
            return jsonify({'error': '仅 admin 可配置'}), 403
        from core.db import set_setting
        data = request.json or {}
        enabled = bool(data.get('register_enabled', True))
        set_setting(db_path, 'register_enabled', '1' if enabled else '0', category='auth')
        return jsonify({'ok': True, 'register_enabled': enabled})

    @app.route('/api/system/tavily/test', methods=['POST'])
    @require_auth
    def test_tavily_connection():
        """测试 Tavily API 连通性（发一次真实搜索）"""
        import requests
        from config import get_tavily_config
        cfg = get_tavily_config()
        api_key = cfg.get('api_key', '')
        if not api_key:
            return jsonify({'ok': False, 'error': 'Tavily API Key 未配置'}), 400
        try:
            resp = requests.post(
                cfg.get('base_url', 'https://api.tavily.com') + '/search',
                json={'api_key': api_key, 'query': 'test', 'max_results': 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return jsonify({'ok': True, 'results': len(data.get('results', []))})
        except Exception as e:
            return jsonify({'ok': False, 'error': f'{type(e).__name__}: {e}'}), 500


    # ─── 搜刮调度配置（系统自驱） ─────────────────────────────────

    @app.route('/api/system/search', methods=['GET'])
    @require_auth
    def get_search_settings():
        """获取搜刮调度配置。"""
        from config import get_search_config
        return jsonify(get_search_config())

    @app.route('/api/system/search', methods=['PUT'])
    @require_auth
    def update_search_settings():
        """更新搜刮调度配置。"""
        from config import get_search_config, save_search_config
        data = request.json or {}
        current = get_search_config()
        for k in ('enabled', 'max_per_domain',
                  'max_keywords_per_project', 'max_llm_calls_per_cycle',
                  'results_per_keyword', 'content_max_chars'):
            if k in data and data[k] is not None:
                current[k] = data[k]
        save_search_config(current)
        return jsonify({'ok': True})

    @app.route('/api/system/search/trigger', methods=['POST'])
    @require_auth
    def trigger_search_cycle():
        """手动触发一次搜刮（后台异步执行，立即返回）。

        完整一轮搜刮可能超过 gunicorn 工作进程超时（~120s），因此不再同步阻塞；
        结果记录在 search_run 履历（/api/system/search/runs），前端轮询刷新。
        """
        from core.scheduler.search_cycle import trigger_search_async
        return jsonify(trigger_search_async())

    # 域 slug → 展示名（调度履历表用）
    _SEARCH_DOMAIN_LABELS = {
        'intelligence_web': '制造情报域',
        'intelligence': '制造情报域',
        'intelligence_sales': '销售情报域',
    }

    @app.route('/api/system/search/runs', methods=['GET'])
    @require_auth
    def list_search_runs():
        """调度履历简报：合并两个域的搜刮运行记录（新 → 旧）。

        返回 {runs:[{id, domain, domain_label, trigger_type, started_at,
        completed_at, status, projects_processed, new_intel, llm_calls,
        duration_sec, intel:[{title,url,intel_id,project}], error_msg}],
        sources:{...}}
        跨域查询：research 容器额外向 sales 容器取数（本地容器网络）；
        失败时优雅降级（sources 里标注 unavailable）。
        """
        import requests as _requests
        from core.db import list_search_runs as _list_runs
        from core.db import finalize_stale_search_runs as _finalize_stale

        limit = min(int(request.args.get('limit', 30) or 30), 100)
        local_only = request.args.get('local') in ('1', 'true', 'yes')
        # research 域的 slug 是 intelligence_web（db 文件名为 intelligence），
        # sales 域 slug 是 intelligence_sales；跨域合并只在 research 容器做
        is_research = spec.get('slug') == 'intelligence_web'

        # 自愈：把进程被杀后卡在 running 的旧记录标记为 failed（阈值 10 分钟）
        try:
            _finalize_stale(db_path, max_age_sec=600)
        except Exception:
            pass

        def _label(slug):
            return _SEARCH_DOMAIN_LABELS.get(slug, slug or '-')

        runs = []
        for row in _list_runs(db_path, limit):
            row = dict(row)
            row['domain_label'] = _label(row.get('domain'))
            runs.append(row)
        sources = {'local': 'ok'}

        # 仅 research 容器需要跨域合并（sales 只跑自己的域）
        if is_research and not local_only:
            try:
                auth = request.headers.get('Authorization', '')
                resp = _requests.get(
                    'http://sales:8767/api/system/search/runs',
                    params={'limit': limit, 'local': '1'},
                    headers={'Authorization': auth},
                    timeout=6,
                )
                if resp.status_code == 200:
                    for row in (resp.json().get('runs') or []):
                        row = dict(row)
                        row['domain_label'] = _label(row.get('domain'))
                        runs.append(row)
                    sources['sales'] = 'ok'
                else:
                    sources['sales'] = f'unavailable (HTTP {resp.status_code})'
            except Exception as e:
                sources['sales'] = f'unavailable ({type(e).__name__})'

        runs.sort(key=lambda x: (x.get('started_at') or '', x.get('id') or 0), reverse=True)
        return jsonify({'runs': runs[:limit], 'sources': sources})

    # ─── 抽取规则管理 API ──────────────────────────────────────

    @app.route('/api/extract/rules', methods=['GET'])
    @require_auth
    def list_extract_rules():
        """List all extraction rules."""
        domain = request.args.get('domain')
        enabled = request.args.get('enabled')

        with get_db(db_path) as conn:
            sql = "SELECT er.*, COUNT(e.id) AS field_count " \
                  "FROM intel_extraction_rule er " \
                  "LEFT JOIN intel_extraction_field e ON er.id = e.rule_id " \
                  "WHERE 1=1"
            params = []
            if domain:
                sql += " AND er.domain = ?"
                params.append(domain)
            if enabled is not None:
                sql += " AND er.enabled = ?"
                params.append(1 if enabled == "1" else 0)
            sql += " GROUP BY er.id ORDER BY er.name"
            rows = conn.execute(sql, params).fetchall()
            return jsonify([dict(r) for r in rows])


    @app.route('/api/extract/rules', methods=['POST'])
    @require_auth
    def create_extract_rule():
        """Create a new extraction rule.

        Domain is SERVER-ENFORCED: the rule always belongs to THIS domain
        (spec['domain_key']). A client-supplied domain value is ignored, and a
        value pointing at another domain is rejected outright — cross-domain
        configuration is not allowed.
        """
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "规则名称为必填项"}), 400
        _dom = (data.get("domain") or "").strip()
        if _dom and _dom != spec.get("domain_key"):
            return jsonify({"error": "跨域配置被禁止：抽取规则只能属于本域（%s）" % spec.get("domain_key")}), 400
        now = _now_iso()
        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO intel_extraction_rule
                   (name, domain, description, scope, max_fields, enabled, built_in, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (data.get("name", ""), spec.get("domain_key"),
                 data.get("description", ""), data.get("scope", "full"),
                 data.get("max_fields", 15),
                 1 if data.get("enabled", True) else 0,
                 now, now)
            )
            rule_id = cursor.lastrowid
            conn.commit()

            # Create fields
            fields = data.get("fields", [])
            for i, f in enumerate(fields):
                conn.execute(
                    """INSERT INTO intel_extraction_field
                       (rule_id, field_key, field_label, field_type, is_required,
                        default_value, sort_order, help_text)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rule_id, f.get("field_key", ""), f.get("field_label", ""),
                     f.get("field_type", "text"),
                     1 if f.get("is_required") else 0, f.get("default_value", ""),
                     f.get("sort_order", i), f.get("help_text", ""))
                )
            conn.commit()
            return jsonify({"id": rule_id, "ok": True}), 201


    @app.route('/api/extract/rules/<int:rule_id>', methods=['GET'])
    @require_auth
    def get_extract_rule(rule_id):
        """Get rule details with field list."""
        with get_db(db_path) as conn:
            rule = conn.execute(
                "SELECT * FROM intel_extraction_rule WHERE id = ?", (rule_id,)
            ).fetchone()
            if not rule:
                return jsonify({"error": "Not found"}), 404
            rule_dict = dict(rule)
            fields = conn.execute(
                "SELECT * FROM intel_extraction_field WHERE rule_id = ? ORDER BY sort_order",
                (rule_id,)
            ).fetchall()
            rule_dict["fields"] = [dict(r) for r in fields]
            return jsonify(rule_dict)


    @app.route('/api/extract/rules/<int:rule_id>', methods=['PUT'])
    @require_auth
    def update_extract_rule(rule_id):
        """Update extraction rule (replace fields).

        Domain is SERVER-ENFORCED: the rule always stays in THIS domain
        (spec['domain_key']). A client-supplied domain value pointing at another
        domain is rejected outright — cross-domain reassignment is not allowed.
        """
        data = request.get_json()
        _dom = (data.get("domain") or "").strip()
        if _dom and _dom != spec.get("domain_key"):
            return jsonify({"error": "跨域配置被禁止：抽取规则只能属于本域（%s）" % spec.get("domain_key")}), 400
        with get_db(db_path) as conn:
            conn.execute(
                """UPDATE intel_extraction_rule SET
                   name=?, domain=?, description=?, scope=?, max_fields=?,
                   enabled=?, updated_at=?
                   WHERE id=?""",
                (data.get("name"), spec.get("domain_key"),
                 data.get("description", ""), data.get("scope", "full"),
                 data.get("max_fields", 15),
                 1 if data.get("enabled", True) else 0,
                 _now_iso(), rule_id)
            )
            conn.execute("DELETE FROM intel_extraction_field WHERE rule_id = ?", (rule_id,))
            fields = data.get("fields", [])
            for i, f in enumerate(fields):
                conn.execute(
                    """INSERT INTO intel_extraction_field
                       (rule_id, field_key, field_label, field_type, is_required,
                        default_value, sort_order, help_text)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rule_id, f["field_key"], f["field_label"], f.get("field_type", "text"),
                     1 if f.get("is_required") else 0, f.get("default_value", ""),
                     f.get("sort_order", i), f.get("help_text", ""))
                )
            conn.commit()
            return jsonify({"ok": True})


    @app.route('/api/extract/rules/<int:rule_id>', methods=['DELETE'])
    @require_auth
    def delete_extract_rule(rule_id):
        """Delete extraction rule (built-in cannot be deleted)."""
        with get_db(db_path) as conn:
            rule = conn.execute("SELECT built_in FROM intel_extraction_rule WHERE id = ?", (rule_id,)).fetchone()
            if not rule:
                return jsonify({"error": "Not found"}), 404
            if rule["built_in"] == 1:
                return jsonify({"error": "内置规则不可删除，仅可禁用", "ok": False}), 403
            conn.execute("DELETE FROM intel_extraction_rule WHERE id = ?", (rule_id,))
            conn.commit()
            return jsonify({"ok": True})


    @app.route('/api/extract/rules/<int:rule_id>/trigger', methods=['POST'])
    @require_auth
    def trigger_extract(rule_id):
        """Manually trigger extraction for all pending intelligence."""
        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE intelligence SET extracted = 0 "
                "WHERE id IN (SELECT DISTINCT intel_id FROM intel_fact WHERE rule_id = ?)",
                (rule_id,)
            )
            conn.commit()
        result = trigger_extract_once()
        return jsonify(result)

    @app.route('/api/extract/trigger', methods=['POST'])
    @require_auth
    def trigger_extract_all():
        """Manually trigger a full extraction cycle (async).

        Returns immediately; extraction runs in a background thread.
        Poll /api/extract/stats (pending_extract) to track progress.
        """
        return jsonify(trigger_extract_async())


    # ─── 报告模板管理 API ──────────────────────────────────────

    @app.route('/api/reports/templates', methods=['GET'])
    @require_auth
    def list_report_templates():
        """List all report templates."""
        domain = request.args.get('domain')
        enabled = request.args.get('enabled')
        status = request.args.get('status')

        with get_db(db_path) as conn:
            sql = "SELECT * FROM intel_aggregate WHERE 1=1"
            params = []
            if domain:
                sql += " AND domain = ?"
                params.append(domain)
            if enabled is not None:
                sql += " AND enabled = ?"
                params.append(1 if enabled == "1" else 0)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY name"
            rows = conn.execute(sql, params).fetchall()
            return jsonify([dict(r) for r in rows])


    @app.route('/api/reports/templates', methods=['POST'])
    @require_auth
    def create_report_template():
        """Create a report template.

        Domain is SERVER-ENFORCED: the template always belongs to THIS domain
        (spec['domain_key']). A client-supplied domain value pointing at another
        domain is rejected outright — cross-domain configuration is not allowed.
        """
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "报告名称为必填项"}), 400
        _dom = (data.get("domain") or "").strip()
        if _dom and _dom != spec.get("domain_key"):
            return jsonify({"error": "跨域配置被禁止：报告模板只能属于本域（%s）" % spec.get("domain_key")}), 400
        now = _now_iso()
        with get_db(db_path) as conn:
            rule = conn.execute(
                "SELECT id FROM intel_extraction_rule WHERE id = ? AND enabled = 1",
                (data.get("rule_id"),)
            ).fetchone()
            if not rule:
                return jsonify({"error": "指定的抽取规则不存在或已禁用"}), 400
            cursor = conn.execute(
                """INSERT INTO intel_aggregate
                   (domain, name, description, rule_id, group_by, metrics, filters,
                    chart_config, prompt_template, schedule_minutes, lookback_days,
                    enabled, next_run, status, built_in, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, ?)""",
                (spec.get("domain_key"), data.get("name"),
                 data.get("description", ""), data.get("rule_id"),
                 data.get("group_by", "entity_name"),
                 json.dumps(data.get("metrics", [])),
                 json.dumps(data.get("filters", [])),
                 json.dumps(data.get("chart_config", [])),
                 data.get("prompt_template", DEFAULT_REPORT_PROMPT),
                 data.get("schedule_minutes", 1440),
                 data.get("lookback_days", 30),
                 1 if data.get("enabled", True) else 0,
                 data.get("next_run", now),
                 now, now)
            )
            conn.commit()
            return jsonify({"id": cursor.lastrowid, "ok": True}), 201


    @app.route('/api/reports/templates/<int:template_id>', methods=['GET'])
    @require_auth
    def get_report_template(template_id):
        """Get template details."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM intel_aggregate WHERE id = ?", (template_id,)
            ).fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            d = dict(row)
            for key in ("metrics", "filters", "chart_config"):
                if d.get(key):
                    d[key] = json.loads(d[key])
            return jsonify(d)


    @app.route('/api/reports/templates/<int:template_id>', methods=['PUT'])
    @require_auth
    def update_report_template(template_id):
        """Update report template.

        Domain is SERVER-ENFORCED: the template always stays in THIS domain
        (spec['domain_key']). A client-supplied domain value pointing at another
        domain is rejected outright — cross-domain reassignment is not allowed.
        """
        data = request.get_json()
        _dom = (data.get("domain") or "").strip()
        if _dom and _dom != spec.get("domain_key"):
            return jsonify({"error": "跨域配置被禁止：报告模板只能属于本域（%s）" % spec.get("domain_key")}), 400
        with get_db(db_path) as conn:
            _rule_id = data.get("rule_id")
            if _rule_id is None:
                # rule_id 是 NOT NULL；前端未提供时保留原值，避免写 NULL
                row = conn.execute(
                    "SELECT rule_id FROM intel_aggregate WHERE id = ?", (template_id,)
                ).fetchone()
                if not row:
                    return jsonify({"error": "Not found"}), 404
                _rule_id = row[0]
            else:
                rule = conn.execute(
                    "SELECT id FROM intel_extraction_rule WHERE id = ? AND enabled = 1",
                    (_rule_id,)
                ).fetchone()
                if not rule:
                    return jsonify({"error": "指定的抽取规则不存在或已禁用"}), 400
            conn.execute(
                """UPDATE intel_aggregate SET
                   domain=?, name=?, description=?, rule_id=?, group_by=?,
                   metrics=?, filters=?, chart_config=?, prompt_template=?,
                   schedule_minutes=?, lookback_days=?, enabled=?, updated_at=?
                   WHERE id=?""",
                (spec.get("domain_key"), data.get("name"), data.get("description", ""),
                 _rule_id, data.get("group_by", "entity_name"),
                 json.dumps(data.get("metrics", [])),
                 json.dumps(data.get("filters", [])),
                 json.dumps(data.get("chart_config", [])),
                 data.get("prompt_template", ""),
                 data.get("schedule_minutes", 1440),
                 data.get("lookback_days", 30),
                 1 if data.get("enabled", True) else 0,
                 _now_iso(), template_id)
            )
            conn.commit()
            return jsonify({"ok": True})


    @app.route('/api/reports/templates/<int:template_id>', methods=['DELETE'])
    @require_auth
    def delete_report_template(template_id):
        """Delete report template (built-in cannot be deleted)."""
        with get_db(db_path) as conn:
            row = conn.execute("SELECT built_in FROM intel_aggregate WHERE id = ?", (template_id,)).fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            if row["built_in"] == 1:
                return jsonify({"error": "内置模板不可删除，仅可禁用", "ok": False}), 403
            conn.execute("DELETE FROM intel_aggregate WHERE id = ?", (template_id,))
            conn.commit()
            return jsonify({"ok": True})


    # ─── 抽取结果查询 API ──────────────────────────────────────

    @app.route('/api/extract/facts', methods=['GET'])
    @require_auth
    def list_facts():
        """Query structured facts with pagination and filters."""
        rule_id = request.args.get('rule_id')
        intel_id = request.args.get('intel_id')
        field_key = request.args.get('field_key')
        entity = request.args.get('entity')
        start_at = request.args.get('start_at')
        end_at = request.args.get('end_at')
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))

        with get_db(db_path) as conn:
            sql = "SELECT * FROM intel_fact WHERE 1=1"
            params = []
            if rule_id:
                sql += " AND rule_id = ?"
                params.append(rule_id)
            if intel_id:
                sql += " AND intel_id = ?"
                params.append(intel_id)
            if field_key:
                sql += " AND field_key = ?"
                params.append(field_key)
            if entity:
                sql += " AND (entity_name LIKE ? OR value_text LIKE ?)"
                params.append(f"%{entity}%", f"%{entity}%")
            if start_at:
                sql += " AND created_at >= ?"
                params.append(start_at)
            if end_at:
                sql += " AND created_at <= ?"
                params.append(end_at)
            sql += " ORDER BY created_at DESC"
            total = conn.execute(sql.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
            rows = conn.execute(sql, params).fetchall()
            return jsonify({
                "total": total,
                "limit": limit,
                "offset": offset,
                "rows": [dict(r) for r in rows]
            })


    @app.route('/api/extract/facts/<int:intel_id>', methods=['GET'])
    @require_auth
    def get_intel_facts(intel_id):
        """Get extraction results for a single intelligence record."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT f.*, r.name AS rule_name
                   FROM intel_fact f
                   LEFT JOIN intel_extraction_rule r ON f.rule_id = r.id
                   WHERE f.intel_id = ?
                   ORDER BY f.rule_id, f.field_key""",
                (intel_id,)
            ).fetchall()
            grouped = {}
            for row in rows:
                rule_name = row["rule_name"] or f"rule_{row['rule_id']}"
                if rule_name not in grouped:
                    grouped[rule_name] = []
                grouped[rule_name].append(dict(row))
            return jsonify({"intel_id": intel_id, "rules": grouped})


    @app.route('/api/extract/stats', methods=['GET'])
    @require_auth
    def extract_stats():
        """Get extraction statistics."""
        with get_db(db_path) as conn:
            total_intel = conn.execute("SELECT COUNT(*) FROM intelligence").fetchone()[0]
            extracted = conn.execute("SELECT COUNT(*) FROM intelligence WHERE extracted = 1").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM intelligence WHERE extracted = 2").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM intelligence WHERE extracted = 0").fetchone()[0]
            total_facts = conn.execute("SELECT COUNT(*) FROM intel_fact").fetchone()[0]
            rules = conn.execute(
                "SELECT id, name, domain, enabled, "
                "(SELECT COUNT(*) FROM intel_fact WHERE rule_id=er.id) AS fact_count "
                "FROM intel_extraction_rule er ORDER BY name"
            ).fetchall()
            return jsonify({
                "total_intelligence": total_intel,
                "extracted": extracted,
                "extract_failed": failed,
                "pending_extract": pending,
                "total_facts": total_facts,
                "coverage_pct": round(extracted / total_intel * 100, 1) if total_intel > 0 else 0,
                "rules": [dict(r) for r in rules]
            })


    # ─── 调度器管理 API ────────────────────────────────────────

    @app.route('/api/reports/scheduler', methods=['GET'])
    @require_auth
    def scheduler_status():
        """Get scheduler status and template summary."""
        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM report_scheduler WHERE id = 1").fetchone()
            templates = conn.execute(
                """SELECT id, name, domain, status, enabled,
                          last_success_time, fail_count, next_run
                   FROM intel_aggregate
                   ORDER BY domain, name"""
            ).fetchall()
            if row:
                d = dict(row)
                d["templates"] = [dict(t) for t in templates]
                return jsonify(d)
            return jsonify({"error": "scheduler not initialized"}), 500


    @app.route('/api/reports/scheduler/toggle', methods=['POST'])
    @require_auth
    def toggle_scheduler():
        """Enable/disable scheduler components."""
        data = request.get_json()
        action = data.get("action", "toggle")
        component = data.get("component", "all")

        with get_db(db_path) as conn:
            now = _now_iso()
            if component == "all":
                if action == "enable":
                    conn.execute("UPDATE report_scheduler SET scheduler_enabled = 1, extract_enabled = 1, report_enabled = 1, updated_at = ? WHERE id = 1", (now,))
                elif action == "disable":
                    conn.execute("UPDATE report_scheduler SET scheduler_enabled = 0, extract_enabled = 0, report_enabled = 0, updated_at = ? WHERE id = 1", (now,))
                else:
                    row = conn.execute("SELECT scheduler_enabled FROM report_scheduler WHERE id = 1").fetchone()
                    new_val = 0 if row["scheduler_enabled"] == 1 else 1
                    conn.execute(f"UPDATE report_scheduler SET scheduler_enabled = {new_val}, extract_enabled = {new_val}, report_enabled = {new_val}, updated_at = ? WHERE id = 1", (now,))
            elif component == "extract":
                if action == "enable":
                    conn.execute("UPDATE report_scheduler SET extract_enabled = 1, updated_at = ? WHERE id = 1", (now,))
                elif action == "disable":
                    conn.execute("UPDATE report_scheduler SET extract_enabled = 0, updated_at = ? WHERE id = 1", (now,))
                else:
                    row = conn.execute("SELECT extract_enabled FROM report_scheduler WHERE id = 1").fetchone()
                    new_val = 0 if row["extract_enabled"] == 1 else 1
                    conn.execute(f"UPDATE report_scheduler SET extract_enabled = {new_val}, updated_at = ? WHERE id = 1", (now,))
            elif component == "report":
                if action == "enable":
                    conn.execute("UPDATE report_scheduler SET report_enabled = 1, updated_at = ? WHERE id = 1", (now,))
                elif action == "disable":
                    conn.execute("UPDATE report_scheduler SET report_enabled = 0, updated_at = ? WHERE id = 1", (now,))
                else:
                    row = conn.execute("SELECT report_enabled FROM report_scheduler WHERE id = 1").fetchone()
                    new_val = 0 if row["report_enabled"] == 1 else 1
                    conn.execute(f"UPDATE report_scheduler SET report_enabled = {new_val}, updated_at = ? WHERE id = 1", (now,))
            conn.commit()
            return jsonify({"ok": True})


    @app.route('/api/reports/scheduler/run-all', methods=['POST'])
    @require_auth
    def scheduler_run_all():
        """Trigger all due reports now."""
        result = trigger_report_all()
        return jsonify(result)


    @app.route('/api/reports/scheduler/reset-fused/<int:template_id>', methods=['POST'])
    @require_auth
    def reset_fused(template_id):
        """Reset a template from fused state."""
        with get_db(db_path) as conn:
            conn.execute(
                """UPDATE intel_aggregate SET
                   status = 'active',
                   fail_count = 0,
                   last_fail_time = NULL,
                   next_run = ?
                   WHERE id = ? AND status = 'fused'""",
                (_now_iso(), template_id)
            )
            conn.commit()
            return jsonify({"ok": True})


    # ─── 报告执行 API ──────────────────────────────────────

    @app.route('/api/reports/run/<int:template_id>', methods=['POST'])
    @require_auth
    @require_permission('reports.manage')
    def run_report(template_id):
        """Manually trigger a single report execution (management action)."""
        result = trigger_report_once(template_id)
        return jsonify(result)


    @app.route('/api/reports/runs', methods=['GET'])
    @require_auth
    @require_permission('reports.view')
    def list_report_runs(template_id=None):
        """Get execution history (optionally filtered by template_id)."""
        template_id = request.args.get('template_id', type=int)
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))
        with get_db(db_path) as conn:
            if template_id is not None:
                where = "WHERE r.template_id = ?"
                wp = [template_id]
            else:
                where = ""
                wp = []
            total = conn.execute(
                f"SELECT COUNT(*) FROM report_run r {where}", wp
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT r.id, r.template_id, a.name AS template_name, r.domain,
                          r.scheduled_time, r.completed_at,
                          r.status, r.duration_sec, r.retry_count, r.fact_count, r.error_msg
                   FROM report_run r
                   LEFT JOIN intel_aggregate a ON r.template_id = a.id
                   {where}
                   ORDER BY r.scheduled_time DESC
                   LIMIT ? OFFSET ?""",
                wp + [limit, offset]
            ).fetchall()
            return jsonify({
                "total": total,
                "limit": limit,
                "offset": offset,
                "runs": [dict(r) for r in rows]
            })


    @app.route('/api/reports/runs/<int:run_id>', methods=['GET'])
    @require_auth
    @require_permission('reports.view')
    def get_report_run(run_id):
        """Get single report run details."""
        with get_db(db_path) as conn:
            run = conn.execute(
                """SELECT r.*, a.name AS template_name, a.domain AS template_domain
                   FROM report_run r
                   LEFT JOIN intel_aggregate a ON r.template_id = a.id
                   WHERE r.id = ?""",
                (run_id,)
            ).fetchone()
            if not run:
                return jsonify({"error": "Not found"}), 404
            d = dict(run)
            for key in ("aggregated_data", "output_charts"):
                if d.get(key):
                    d[key] = json.loads(d[key])
            return jsonify(d)


    @app.route('/api/reports/overview', methods=['GET'])
    @require_auth
    def report_overview():
        """Get latest execution summary for all templates."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT a.id AS template_id, a.name, a.domain,
                          r.status AS last_status,
                          r.completed_at AS last_time,
                          r.duration_sec AS last_duration,
                          r.fact_count AS last_fact_count,
                          a.status AS template_status
                   FROM intel_aggregate a
                   LEFT JOIN report_run r ON a.id = r.template_id
                   AND r.id = (
                       SELECT MAX(id) FROM report_run WHERE template_id = a.id
                   )
                   WHERE a.enabled = 1
                   ORDER BY a.domain, a.name"""
            ).fetchall()
            return jsonify([dict(r) for r in rows])


    # ──────────────────────────────────────────────
    # AI Analysis Config Routes
    # ──────────────────────────────────────────────

    @app.route('/api/ai/analysis/configs', methods=['GET'])
    @require_auth
    def api_ai_analysis_configs():
        """Get analysis config list."""
        domain = request.args.get('domain')
        enabled = request.args.get('enabled')
        if enabled is not None:
            enabled = int(enabled)
        configs = get_ai_analysis_configs(db_path, domain=domain, enabled=enabled)
        return jsonify(configs)

    @app.route('/api/ai/analysis/configs/<int:config_id>', methods=['GET'])
    @require_auth
    def api_ai_analysis_config_detail(config_id):
        """Get single analysis config."""
        config = get_ai_analysis_config_by_id(db_path, config_id)
        if not config:
            return jsonify({"error": "Config not found"}), 404
        return jsonify(config)

    @app.route('/api/ai/analysis/configs', methods=['POST'])
    @require_auth
    def api_ai_analysis_config_create():
        """Create analysis config."""
        data = request.json
        if not all(k in data for k in ['domain', 'name', 'intent']):
            return jsonify({"error": "Missing required fields: domain, name, intent"}), 400
        config_id = save_ai_analysis_config(db_path, data)
        return jsonify({"success": True, "id": config_id})

    @app.route('/api/ai/analysis/configs/<int:config_id>', methods=['PUT'])
    @require_auth
    def api_ai_analysis_config_update(config_id):
        """Update analysis config."""
        data = request.json
        data['id'] = config_id
        existing = get_ai_analysis_config_by_id(db_path, config_id)
        if not existing:
            return jsonify({"error": "Config not found"}), 404
        config_id = save_ai_analysis_config(db_path, data)
        return jsonify({"success": True, "id": config_id})

    @app.route('/api/ai/analysis/configs/<int:config_id>/toggle', methods=['POST'])
    @require_auth
    def api_ai_analysis_config_toggle(config_id):
        """Toggle config enabled/disabled."""
        data = request.json
        enabled = data.get('enabled', 1)
        enable_ai_analysis_config(db_path, config_id, enabled)
        return jsonify({"success": True, "enabled": enabled})

    @app.route('/api/ai/analysis/configs/<int:config_id>', methods=['DELETE'])
    @require_auth
    def api_ai_analysis_config_delete(config_id):
        """Delete analysis config."""
        delete_ai_analysis_config(db_path, config_id)
        return jsonify({"success": True})

    # ──────────────────────────────────────────────
    # AI Analysis Run Routes
    # ──────────────────────────────────────────────

    @app.route('/api/ai/analysis/runs', methods=['GET'])
    @require_auth
    def api_ai_analysis_runs():
        """Get analysis run list."""
        config_id = request.args.get('config_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        runs = get_ai_analysis_runs(db_path, config_id=config_id, limit=limit, offset=offset)
        return jsonify(runs)

    @app.route('/api/ai/analysis/runs/<int:run_id>', methods=['GET'])
    @require_auth
    def api_ai_analysis_run_detail(run_id):
        """Get single analysis run details."""
        run = get_ai_analysis_run_by_id(db_path, run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404
        # Parse JSON fields
        for key in ("result_charts", "result_data"):
            if run.get(key):
                run[key] = json.loads(run[key])
        return jsonify(run)

    @app.route('/api/ai/analysis/runs/<int:run_id>', methods=['DELETE'])
    @require_auth
    def api_ai_analysis_run_delete(run_id):
        """Delete analysis run."""
        delete_ai_analysis_run(db_path, run_id)
        return jsonify({"success": True})

    @app.route('/api/ai/analysis/runs/<int:run_id>/re-run', methods=['POST'])
    @require_auth
    def api_ai_analysis_run_re_run(run_id):
        """Re-run an analysis."""
        run = get_ai_analysis_run_by_id(db_path, run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404
        # Create a new run with same parameters
        new_run_id = save_ai_analysis_run(db_path, {
            "config_id": run.get("config_id"),
            "domain": run["domain"],
            "title": run["title"],
            "status": "running",
            "start_time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            "lookback_days": run.get("lookback_days", 30),
        })
        return jsonify({"success": True, "run_id": new_run_id})

    # ──────────────────────────────────────────────
    # AI Analysis - Natural Language Input (one-shot)
    # ──────────────────────────────────────────────

    @app.route('/api/ai/analysis/run', methods=['POST'])
    @require_auth
    def api_ai_analysis_run():
        """Natural language analysis - one-shot execution."""
        data = request.json
        if not data or 'intent' not in data:
            return jsonify({"error": "Missing 'intent' field"}), 400
        intent = data['intent']
        lookback_days = data.get('lookback_days', 30)
        spec_slug = spec.get("slug", "research")
        
        # Execute analysis
        result = run_ai_analysis(db_path, {"slug": spec_slug}, intent, lookback_days)
        return jsonify(result)

    @app.route('/api/ai/generate-config', methods=['POST'])
    @require_auth
    def api_ai_generate_config():
        """Generate structured config (extraction rule + report template) from natural language."""
        data = request.get_json(silent=True) or {}
        intent = (data.get('intent') or '').strip()
        if not intent:
            return jsonify({"ok": False, "error": "请描述你想要的报告内容"}), 400
        lookback_days = int(data.get('lookback_days') or 30)
        spec_slug = spec.get("slug", "research")

        try:
            result = generate_analysis_config(db_path, {"slug": spec_slug}, intent, lookback_days)
            if result.get("ok"):
                return jsonify(result)
            return jsonify(result), 500
        except Exception as e:
            return jsonify({"ok": False, "error": f"生成配置异常: {str(e)}"}), 500

    return app
