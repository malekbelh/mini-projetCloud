from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics
import psycopg2, redis, os, time, json

app = Flask(__name__)
metrics = PrometheusMetrics(app)
cache = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

def init_db():
    retries = 5
    while retries > 0:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS tasks
                           (id SERIAL PRIMARY KEY, title TEXT NOT NULL)''')
            conn.commit()
            cur.close(); conn.close()
            print("Database initialized!")
            break
        except Exception as e:
            print(f"Retrying... {e}")
            retries -= 1
            time.sleep(3)

@app.route('/tasks', methods=['GET'])
def get_tasks():
    cached = cache.get('tasks')
    if cached:
        print("Cache HIT")
        return jsonify(json.loads(cached))
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tasks')
    tasks = [{"id": r[0], "title": r[1]} for r in cur.fetchall()]
    cur.close(); conn.close()
    cache.setex('tasks', 30, json.dumps(tasks))
    return jsonify(tasks)

@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO tasks (title) VALUES (%s) RETURNING id', (data['title'],))
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    cache.delete('tasks')
    return jsonify({"id": task_id, "title": data['title']}), 201

@app.route('/tasks/<int:id>', methods=['DELETE'])
def delete_task(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM tasks WHERE id = %s', (id,))
    conn.commit()
    cur.close(); conn.close()
    cache.delete('tasks')
    return jsonify({"message": "deleted"}), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)