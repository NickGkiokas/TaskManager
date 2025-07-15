from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import sqlite3
import csv
from io import BytesIO, TextIOWrapper
from datetime import datetime
from openpyxl import Workbook


app = Flask(__name__)
DB_NAME = 'tasks.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            client TEXT,
            contact_person TEXT,
            contact_method TEXT,
            status TEXT,
            status_details TEXT,
            duration REAL,
            assigned_to TEXT,
            request_date TEXT,
            active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

@app.template_filter('format_date')
def format_date(value, format="%d/%m/%Y"):
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except:
        return value


@app.route('/')
def index():
    client_filter = request.args.get('client')
    status_filter = request.args.get('status')
    category_filter = request.args.get('category')
    show_completed = request.args.get('show_completed') == '1'

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    query = 'SELECT * FROM tasks WHERE 1=1'
    params = []

    if show_completed:
        query += ' AND status = ?'
        params.append('Done')
    else:
        query += ' AND active = 1'
    if client_filter:
        query += ' AND client = ?'
        params.append(client_filter)
    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)
    if category_filter:
        query += ' AND category = ?'
        params.append(category_filter)

    # Προκαθορισμένες λίστες
    predefined_clients = ["ΣΥΦΑ ΕΒΡΟΥ", "ΠΗΓΑΣΟΣ", "ΑΚΜΟΝ", "MEVACO", "ΚΑΝΑΚΗΣ","ΣΥΝΔΕΣΜΟΣ", "ΕΥΡΥΠΙΔΗΣ", "IEECP"]
    predefined_categories = ["Qlik", "Timesheets", "SQL"]


    c.execute(query, params)
    rows = c.fetchall()

    c.execute('SELECT DISTINCT client FROM tasks')
    clients = [r[0] for r in c.fetchall() if r[0]]

    c.execute('SELECT DISTINCT status FROM tasks')
    statuses = [r[0] for r in c.fetchall() if r[0]]

    c.execute('SELECT DISTINCT category FROM tasks')
    categories = [r[0] for r in c.fetchall() if r[0]]

    conn.close()
    return render_template(
        'index.html',
        tasks=rows,
        clients=clients,
        statuses=statuses,
        categories=categories,
        predefined_clients=predefined_clients,
        predefined_categories=predefined_categories,
        show_completed=show_completed
    )


@app.route('/add', methods=['POST'])
def add_task_form():
    task_id = request.form.get('task_id')
    data = {
        "title": request.form['title'],
        "category": request.form['category'],
        "client": request.form.get('client', ''),
        "contact_person": request.form['contact_person'],
        "contact_method": request.form['contact_method'],
        "status": request.form['status'],
        "status_details": request.form['status_details'],
        "duration": request.form['duration'],
        "assigned_to": request.form['assigned_to'],
        "request_date": request.form['request_date']
    }

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if task_id:
        c.execute('''
            UPDATE tasks SET
                title = ?, category = ?, client = ?, contact_person = ?, contact_method = ?,
                status = ?, status_details = ?, duration = ?, assigned_to = ?, request_date = ?
            WHERE id = ?
        ''', (*data.values(), task_id))
    else:
        c.execute('''
            INSERT INTO tasks (title, category, client, contact_person, contact_method, status,
                status_details, duration, assigned_to, request_date, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', tuple(data.values()))

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT active FROM tasks WHERE id = ?', (task_id,))
    row = c.fetchone()
    if row:
        new_status = 0 if row[0] == 1 else 1
        c.execute('UPDATE tasks SET active = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/advance/<int:task_id>', methods=['GET'])
def advance_task_status(task_id):
    status_order = ["Filed", "In Progress", "Testing", "Done"]

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT status, status_details FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if row:
        current_status, current_details = row
        try:
            next_index = status_order.index(current_status) + 1
            if next_index < len(status_order):
                next_status = status_order[next_index]
                date_tag = datetime.now().strftime("%d/%m/%Y")
                updated_details = f"{current_details},{next_status} ({date_tag})"
                c.execute("UPDATE tasks SET status = ?, status_details = ? WHERE id = ?", (next_status, updated_details, task_id))
                conn.commit()
        except ValueError:
            pass  # status not found in list
    conn.close()
    return redirect(url_for('index'))

@app.route('/export')
def export_tasks():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM tasks')
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Tasks"

    headers = ['ID', 'Title', 'Category', 'Client', 'Contact Person', 'Contact Method', 
               'Status', 'Status Details', 'Duration', 'Assigned To', 'Request Date', 'Active']
    ws.append(headers)

    for row in rows:
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="tasks_export.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
