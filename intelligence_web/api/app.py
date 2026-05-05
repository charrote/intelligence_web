from flask import Flask, request, jsonify
from flask_cors import CORS
from models import init_db, create_intelligence, get_intelligences, get_intelligence_by_id, update_intelligence_status, add_history, get_history, get_categories, get_commands, add_command, delete_command, generate_command_file, reorder_command, reorder_commands_batch, add_comment, get_comments, add_summary, get_summary, get_approved_intelligences, get_agent_names, get_db
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/intelligence', methods=['POST'])
def create_intel():
    data = request.json
    if not data.get('title') or not data.get('content'):
        return jsonify({'error': 'title and content are required'}), 400
    
    intel_id = create_intelligence(
        data['title'],
        data['content'],
        data.get('category', '')
    )
    if intel_id is None:
        return jsonify({'error': 'duplicate title, skipping'}), 409
    return jsonify({'id': intel_id, 'status': 'pending'}), 201

@app.route('/api/intelligence', methods=['GET'])
def list_intel():
    filters = {}
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('category'):
        filters['category'] = request.args.get('category')
    if request.args.get('date_from'):
        filters['date_from'] = request.args.get('date_from')
    if request.args.get('date_to'):
        filters['date_to'] = request.args.get('date_to')
    
    intelligences = get_intelligences(filters)
    # 为每条情报添加评论数
    for intel in intelligences:
        intel['comment_count'] = len(get_comments(intel['id'], limit=999))
    return jsonify(intelligences)

@app.route('/api/intelligence/<int:id>', methods=['GET'])
def get_intel(id):
    intel = get_intelligence_by_id(id)
    if not intel:
        return jsonify({'error': 'not found'}), 404
    return jsonify(intel)

@app.route('/api/intelligence/<int:id>/status', methods=['PUT'])
def update_status(id):
    data = request.json
    status = data.get('status')
    if status not in ['approved', 'rejected', 'active', 'completed', 'discarded']:
        return jsonify({'error': 'invalid status'}), 400
    
    opinion = data.get('opinion', '')
    if update_intelligence_status(id, status, opinion):
        return jsonify({'success': True})
    return jsonify({'error': 'not found'}), 404

@app.route('/api/intelligence/<int:id>/history', methods=['GET'])
def list_history(id):
    history = get_history(id)
    return jsonify(history)

@app.route('/api/intelligence/<int:id>/history', methods=['POST'])
def create_history(id):
    data = request.json
    action = data.get('action')
    if not action:
        return jsonify({'error': 'action is required'}), 400
    
    history_id = add_history(
        id,
        action,
        data.get('detail', ''),
        data.get('file_location', '')
    )
    return jsonify({'id': history_id}), 201

@app.route('/api/categories', methods=['GET'])
def list_categories():
    return jsonify(get_categories())

@app.route('/api/commands', methods=['GET'])
def list_commands():
    return jsonify(get_commands())

@app.route('/api/commands', methods=['POST'])
def create_command():
    data = request.json
    content = data.get('content')
    if not content:
        return jsonify({'error': 'content is required'}), 400
    cmd_id = add_command(content)
    return jsonify({'id': cmd_id}), 201

@app.route('/api/commands/<int:id>', methods=['DELETE'])
def remove_command(id):
    if delete_command(id):
        return jsonify({'success': True})
    return jsonify({'error': 'not found'}), 404

@app.route('/api/commands/reorder', methods=['POST'])
def reorder_commands():
    data = request.json
    # 支持两种格式：
    # 1. 批量: {"ids": [id1, id2, id3]} - 按新顺序重排所有
    # 2. 单个: {"id": x, "position": y} - 移动单个到指定位置
    if 'ids' in data:
        ids = data['ids']
        if reorder_commands_batch(ids):
            return jsonify({'success': True})
        return jsonify({'error': 'not found'}), 404
    else:
        id = data.get('id')
        position = data.get('position')
        if reorder_command(id, position):
            return jsonify({'success': True})
        return jsonify({'error': 'not found'}), 404

@app.route('/api/commands/generate', methods=['POST'])
def make_command_file():
    content = generate_command_file()
    data_dir = '/app/data'
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, 'scout_directives.md')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return jsonify({'file': 'data/scout_directives.md'})

# ========== 评论 API（仅 Agent） ==========
AGENT_API_KEY = os.environ.get('INTELLIGENCE_AGENT_KEY', 'agent-secret-key')

def require_agent():
    """验证 Agent API Key，无 key 或 key 错误则拒绝"""
    key = request.headers.get('X-Agent-Key', '')
    if key != AGENT_API_KEY:
        return jsonify({'error': 'Unauthorized: valid agent key required'}), 401
    return None

@app.route('/api/intelligence/<int:id>/comments', methods=['GET'])
def list_comments(id):
    limit = request.args.get('limit', 20, type=int)
    comments = get_comments(id, limit)
    # 按时间正序返回（旧的在前，新的在后，方便滚动）
    return jsonify(list(reversed(comments)))

@app.route('/api/intelligence/<int:id>/comments', methods=['POST'])
def add_comment_api(id):
    unauthorized = require_agent()
    if unauthorized:
        return unauthorized
    
    data = request.json
    if not data.get('agent_name') or not data.get('content'):
        return jsonify({'error': 'agent_name and content are required'}), 400
    
    comment_id = add_comment(
        id,
        data['agent_name'],
        data['content'],
        data.get('agent_id', '')
    )
    return jsonify({'id': comment_id, 'success': True}), 201

# ========== 总结 API（仅 Agent） ==========
@app.route('/api/intelligence/<int:id>/summary', methods=['GET'])
def get_summary_api(id):
    summary = get_summary(id)
    if not summary:
        return jsonify({'error': 'no summary yet'}), 404
    return jsonify(summary)

@app.route('/api/intelligence/<int:id>/summary', methods=['POST'])
def add_summary_api(id):
    unauthorized = require_agent()
    if unauthorized:
        return unauthorized
    
    data = request.json
    if not data.get('content'):
        return jsonify({'error': 'content is required'}), 400
    
    summary_id = add_summary(id, data['content'])
    return jsonify({'id': summary_id, 'success': True}), 201

@app.route('/api/summaries', methods=['GET'])
def list_all_summaries():
    """获取所有有总结的情报的总结列表，用于全局总结栏"""
    with get_db() as conn:
        cursor = conn.cursor()
        # 获取所有 approved/active 情报
        cursor.execute("SELECT id, title, status FROM intelligence WHERE status IN ('approved', 'active') ORDER BY updated_at DESC")
        items = [dict(row) for row in cursor.fetchall()]
    
    result = []
    for item in items:
        summary = get_summary(item['id'])
        if summary:
            result.append({
                'intelligence_id': item['id'],
                'title': item['title'],
                'status': item['status'],
                'summary': summary['content'],
                'updated_at': summary['updated_at']
            })
    return jsonify(result)

# ========== 分发评论任务 API（仅 Agent） ==========
@app.route('/api/review/dispatch', methods=['POST'])
def dispatch_review():
    """触发对 approved/active 项目的评论分发。由定时任务调用。"""
    unauthorized = require_agent()
    if unauthorized:
        return unauthorized
    
    items = get_approved_intelligences()
    agent_names = get_agent_names()
    dispatched = []
    for item in items:
        dispatched.append({
            'id': item['id'],
            'title': item['title'],
            'status': item['status'],
            'content': item['content'],
            'opinion': item.get('opinion', ''),
            'category': item.get('category', '')
        })
    return jsonify({
        'dispatched': dispatched,
        'count': len(dispatched),
        'agents': agent_names
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8766, debug=True)
