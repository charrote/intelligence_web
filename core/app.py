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
    add_comment, get_comments,
    add_summary, get_summary, get_dashboard_stats,
    get_commands, add_command_content,
    get_all_settings, get_setting, set_setting,
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
        """Return only enabled domains (for frontend domain switcher)."""
        data = _load_domains()
        enabled = [d for d in data.get('domains', []) if d.get('enabled', True)]
        return jsonify({'domains': enabled})

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

    return app