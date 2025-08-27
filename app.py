
from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
import pyodbc
import csv
from io import BytesIO, TextIOWrapper
from datetime import datetime
from openpyxl import Workbook
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)

def get_sql_server_connection():
    driver = os.getenv("DB_DRIVER", "{ODBC Driver 17 for SQL Server}")
    server = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "1433")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")

    conn_str = (
        f"DRIVER={driver};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(conn_str)

def init_db():
    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute('''
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='track_tasks' AND xtype='U'
        )
        CREATE TABLE track_tasks (
            id INT IDENTITY(1,1) PRIMARY KEY,
            title NVARCHAR(255) NOT NULL,
            category NVARCHAR(255),
            client NVARCHAR(255),
            contact_person NVARCHAR(255),
            contact_method NVARCHAR(255),
            status NVARCHAR(100),
            status_details NVARCHAR(MAX),
            duration FLOAT,
            assigned_to NVARCHAR(255),
            request_date DATE,
            active BIT DEFAULT 1,
            comment NVARCHAR(MAX)
        )
    ''')    
    conn.commit()
    conn.close()

def get_existing_request_date(task_id):
    if not task_id:
        return None
    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute("SELECT request_date FROM track_tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

@app.template_filter('format_date')
def format_date(value, format="%d/%m/%Y"):
    if not value:
        return ""
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime(format)
    except:
        return str(value)

@app.route('/')
def index():
    client_filter = request.args.get('client')
    status_filter = request.args.get('status')
    category_filter = request.args.get('category')
    keep_open = request.args.get('keep_open')
    show_completed = request.args.get('show_completed') == '1'

    conn = get_sql_server_connection()
    c = conn.cursor()

    query = "SELECT * FROM track_tasks WHERE 1=1"
    params = []

    if show_completed:
        query += ' AND status = ?'
        params.append('Done')
    else:
        query += ' AND active = 1 AND status != ?'
        params.append('Done')

    if client_filter:
        query += ' AND client = ?'
        params.append(client_filter)
    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)
    if category_filter:
        query += ' AND category = ?'
        params.append(category_filter)

    c.execute(query, params)
    rows = c.fetchall()
    tasks = [list(row) for row in rows]  # μετατροπή σε λίστα

    c.execute('SELECT CompanyDescription FROM Company')
    clients = sorted([r[0] for r in c.fetchall() if r[0]])

    c.execute('SELECT DISTINCT status FROM track_tasks')
    statuses = [r[0] for r in c.fetchall() if r[0]]

    c.execute('SELECT DISTINCT category FROM track_tasks')
    categories = [r[0] for r in c.fetchall() if r[0]]

    conn.close()

    return render_template(
        'index.html',
        tasks=tasks,
        clients=clients,
        statuses=statuses,
        categories=categories,
        predefined_clients=clients,
        predefined_categories=["Qlik", "Timesheets", "SQL", "Λογιστήριο","Μισθοδοσία"],
        show_completed=show_completed,
        current_date=datetime.today().strftime('%Y-%m-%d'),
        keep_open=keep_open
    )

@app.route('/add', methods=['POST'])
def add_task_form():
    task_id = request.form.get('task_id')
    category = request.form.get("category")
    if category == "__custom__":
        category = request.form.get("custom_category")

    data = {
        "title": request.form['title'],
        "category": category,
        "client": request.form.get('client', ''),
        "contact_person": request.form['contact_person'],
        "contact_method": request.form['contact_method'],
        "status": request.form['status'],
        "status_details": request.form['status_details'] or f"{request.form['status']} ({datetime.today().strftime('%d/%m/%Y')})",
        "duration": request.form['duration'],
        "assigned_to": request.form['assigned_to'],
        "request_date": request.form['request_date'] or get_existing_request_date(task_id)
    }

    conn = get_sql_server_connection()
    c = conn.cursor()

    if task_id:
        # Αν το status είναι Done, τότε active = 0, αλλιώς active = 1
        new_active = 0 if data["status"] == "Done" else 1
        c.execute('''
            UPDATE track_tasks SET
                title = ?, category = ?, client = ?, contact_person = ?, contact_method = ?,
                status = ?, status_details = ?, duration = ?, assigned_to = ?, request_date = ?, active = ?
            WHERE id = ?
        ''', (*data.values(), new_active, task_id))

    else:
        c.execute('''
            INSERT INTO track_tasks (title, category, client, contact_person, contact_method, status,
                status_details, duration, assigned_to, request_date, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', tuple(data.values()))

    conn.commit()
    conn.close()

    return redirect(url_for('index', keep_open=1))

@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute('DELETE FROM track_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute('SELECT active FROM track_tasks WHERE id = ?', (task_id,))
    row = c.fetchone()
    if row:
        new_status = 0 if row[0] == 1 else 1
        c.execute('UPDATE track_tasks SET active = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/advance/<int:task_id>', methods=['GET'])
def advance_task_status(task_id):
    status_order = ["Filed", "In Progress", "Testing", "Done"]

    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute("SELECT status, status_details FROM track_tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if row:
        current_status, current_details = row
        try:
            next_index = status_order.index(current_status) + 1
            if next_index < len(status_order):
                next_status = status_order[next_index]
                date_tag = datetime.now().strftime("%d/%m/%Y")
                updated_details = f"{current_details},{next_status} ({date_tag})"

                if next_status == "Done":
                    c.execute("UPDATE track_tasks SET status = ?, status_details = ?, active = 0 WHERE id = ?",
                              (next_status, updated_details, task_id))
                else:
                    c.execute("UPDATE track_tasks SET status = ?, status_details = ? WHERE id = ?",
                              (next_status, updated_details, task_id))
                conn.commit()
        except ValueError:
            pass
    conn.close()
    return redirect(url_for('index', keep_open=task_id))

@app.route("/update_status/<int:task_id>", methods=["POST"])
def update_status(task_id):
    new_status_id = request.form["status_id"]

    # Ενημέρωση τρέχουσας κατάστασης στον πίνακα track_tasks
    cursor.execute("""
        UPDATE track_tasks
        SET status = ?
        WHERE id = ?
    """, (new_status_id, task_id))

    # Προσθήκη νέου transaction
    cursor.execute("""
        INSERT INTO TaskTransactions (TaskStatusID, TaskNotesID, TT_IssueDate)
        VALUES (?, ?, GETDATE())
    """, (new_status_id, task_id))

    conn.commit()
    return redirect(url_for("index"))

@app.route("/task/<int:task_id>/history")
def task_history(task_id):
    conn = get_sql_server_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ts.TaskStatusDescription, 
               FORMAT(tt.TT_IssueDate, 'dd/MM/yyyy')
        FROM TaskTransactions tt
        JOIN TaskStatus ts ON tt.TaskStatusID = ts.TaskStatusID
        WHERE tt.TaskNotesID = ?
        ORDER BY tt.TT_IssueDate ASC
    """, (task_id,))
    rows = cursor.fetchall()
    conn.close()

    history = [{"status": r[0], "date": r[1]} for r in rows]
    return jsonify(history)


@app.route('/comment/<int:task_id>', methods=['POST'])
def save_comment(task_id):
    data = request.get_json()
    comment = data.get('comment', '')

    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute("UPDATE track_tasks SET comment = ? WHERE id = ?", (comment, task_id))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Comment updated successfully'})

@app.route('/export')
def export_tasks():
    conn = get_sql_server_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM track_tasks')
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Tasks"

    headers = ['ID', 'Title', 'Category', 'Client', 'Contact Person', 'Contact Method', 
               'Status', 'Status Details', 'Duration', 'Assigned To', 'Request Date', 'Active', 'Comment']
    ws.append(headers)

    for row in rows:
        ws.append(list(row))
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
    app.run(debug=True, port=80)


