"""Shared Flask app factory for intelligence domains."""

import os, sys, sqlite3
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.db import (
    init_db, get_db_path, create_intelligence,
    get_intelligences, get_intelligence_by_id, update_intelligence_status,
    get_history, get_categories,
    add_comment, get_comments,
    add_summary, get_summary, get_dashboard_stats,
    get_all_settings, set_setting,
)


def create_app(project_root, spec):
    """Create and configure the Flask application for a domain."""
    # Static files served by nginx, not by Flask
    app = Flask(__name__)
    CORS(app, origins=os.environ.get("CORS_ORIGINS", "").split(","))

    db_path = get_db_path(project_root, spec["slug"])

    # --- Domain Config ---
    @app.route('/api/domain_config')
    def domain_config():
        statuses = [{"key": k, "label": v} for k, v in spec["statuses"]]
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
            "limit": limit,
        }
        return jsonify(get_intelligences(db_path, filters))

    @app.route('/api/intelligence', methods=['POST'])
    def create_intel():
        data = request.json
        if not data.get('title') or not data.get('content'):
            return jsonify({'error': 'title and content are required'}), 400
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
            }
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

    # --- System Settings ---
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
        ports = [
            (8766, '制造情报 API'),
            (8767, '销售情报 API'),
            (8768, '爬虫服务'),
            (7700, 'Meilisearch'),
        ]
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

    return app