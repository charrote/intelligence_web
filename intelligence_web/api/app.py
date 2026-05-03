from flask import Flask, request, jsonify
from flask_cors import CORS
from models import init_db, create_intelligence, get_intelligences, get_intelligence_by_id, update_intelligence_status, add_history, get_history, get_categories, get_commands, add_command, delete_command, generate_command_file, reorder_command
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
    if status not in ['approved', 'rejected', 'active', 'completed']:
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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8766, debug=True)
