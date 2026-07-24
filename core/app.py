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
    get_history, get_categories,
    add_comment, get_comments,
    add_summary, get_summary, get_dashboard_stats,
    get_commands, add_command_content,
    get_all_settings, set_setting,
    authenticate_user, get_user_by_id, get_db,
)
from core import project as projlib
from core import datasource as dslib
from core import target_types as ttslib


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
    migrate_db(db_path)

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
    def update_project_endpoint(id):
        project = projlib.update_project(db_path, id, request.json)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(project)

    @app.route('/api/projects/<int:id>/toggle', methods=['POST'])
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
    def set_project_datasources(id):
        data = request.json
        datasource_ids = data.get('datasource_ids', [])
        project = projlib.set_project_datasources(db_path, id, datasource_ids)
        if project is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(project)

    @app.route('/api/projects/<int:id>', methods=['DELETE'])
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
    def update_datasource_endpoint(id):
        source = dslib.update_source(db_path, id, request.json)
        if source is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(source)

    @app.route('/api/datasources/<int:id>/status', methods=['PUT'])
    def toggle_datasource_status(id):
        data = request.json
        enabled = data.get('status') == 'active'
        source = dslib.toggle_source_status(db_path, id, enabled)
        if source is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(source)

    @app.route('/api/datasources/<int:id>', methods=['DELETE'])
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
    def update_target_type_endpoint(id):
        tt = ttslib.update_target_type(db_path, id, request.json)
        if tt is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(tt)

    @app.route('/api/target_types/<int:id>/toggle', methods=['POST'])
    def toggle_target_type_status(id):
        data = request.json
        enabled = data.get('enabled', True)
        tt = ttslib.toggle_target_type_enabled(db_path, id, enabled)
        if tt is None:
            return jsonify({'error': 'not found'}), 404
        return jsonify(tt)

    @app.route('/api/target_types/<int:id>', methods=['DELETE'])
    def delete_target_type_endpoint(id):
        ttslib.delete_target_type(db_path, id)
        return jsonify({'ok': True})

    # ========================================================================
    # Roles API
    # ========================================================================

    @app.route('/api/roles', methods=['GET'])
    def list_roles():
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(db_path)
        _conn.row_factory = _sqlite3.Row
        rows = _conn.execute('''
            SELECT role, COUNT(*) as user_count FROM users
            GROUP BY role ORDER BY role
        ''').fetchall()
        _conn.close()
        roles = [{'id': i+1, 'name': r['role'], 'user_count': r['user_count']} for i, r in enumerate(rows)]
        return jsonify(roles)

    @app.route('/api/roles', methods=['POST'])
    def create_role():
        data = request.json
        if not data or not data.get('name'):
            return jsonify({'error': '角色名称不能为空'}), 400
        role_name = data['name'].strip()
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(db_path)
        existing = _conn.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role_name,)).fetchone()[0]
        _conn.close()
        return jsonify({'id': 1, 'name': role_name, 'user_count': existing})

    @app.route('/api/roles/<int:id>', methods=['PUT'])
    def update_role_endpoint(id):
        data = request.json
        if not data or not data.get('name'):
            return jsonify({'error': '角色名称不能为空'}), 400
        return jsonify({'id': id, 'name': data['name'].strip()})

    @app.route('/api/roles/<int:id>', methods=['DELETE'])
    def delete_role_endpoint(id):
        return jsonify({'ok': True})

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
        ports = [(8766, '制造情报 API'), (8767, '销售情报 API'), (8768, '爬虫服务'), (7700, 'Meilisearch')]
        for port, name in ports:
            try:
                url = f'http://localhost:{port}/api/health' if port != 7700 else f'http://localhost:{port}/health'
                with _urlopen.urlopen(url, timeout=3) as resp:
                    data = _json.loads(resp.read().decode())
                    is_up = data.get('status') in ('ok', 'available')
                    services.append({'name': name, 'port': port, 'status': 'up' if is_up else 'down', 'details': data.get('status', '')})
            except Exception as e:
                services.append({'name': name, 'port': port, 'status': 'down', 'details': str(e)[:100]})
        return jsonify({'services': services})

    # --- Health ---
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    # ========================================================================
    # Authentication
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
        token = _generate_token(user)
        return jsonify({
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

    return app