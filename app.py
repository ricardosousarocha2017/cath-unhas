import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_chave_secreta_padrao')

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            servico TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        servico = request.form.get('servico')
        data = request.form.get('data')
        hora = request.form.get('hora')

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO agendamentos (nome, telefone, servico, data, hora) VALUES (?, ?, ?, ?, ?)',
            (nome, telefone, servico, data, hora)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
        
    return render_template('booking.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        
        if usuario == 'admin' and senha == '1234':
            session['logged_in'] = True
            return redirect(url_for('admin'))
            
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    agendamentos = conn.execute('SELECT * FROM agendamentos').fetchall()
    conn.close()
    return render_template('admin.html', agendamentos=agendamentos)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
