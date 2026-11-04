import os
import sqlite3
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_secreta_2026_pro')

DB_NAME = 'database.db'
NUMERO_WHATSAPP_ADMIN = "5511963271437"  # Substitua pelo número com DDD

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de Agendamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            servico TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    
    # Tabela de Usuários Admin
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    
    # Cria usuário padrão admin/1234 se não existir nenhum
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        senha_hash = generate_password_hash('1234')
        cursor.execute('INSERT INTO usuarios (usuario, senha) VALUES (?, ?)', ('admin', senha_hash))
        
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

        # Monta mensagem para o WhatsApp do Administrador
        mensagem = f"💅 *Novo Agendamento - Cath Unhas*\n\n👤 *Cliente:* {nome}\n📞 *Telefone:* {telefone}\n✨ *Serviço:* {servico}\n📅 *Data:* {data}\n⏰ *Horário:* {hora}"
        link_whatsapp = f"https://api.whatsapp.com/send?phone={NUMERO_WHATSAPP_ADMIN}&text={quote(mensagem)}"

        return render_template('booking_sucesso.html', nome=nome, link_whatsapp=link_whatsapp)

    return render_template('booking.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get('username') or request.form.get('usuario')
        senha_input = request.form.get('password') or request.form.get('senha')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE usuario = ?', (usuario_input,)).fetchone()
        conn.close()

        if user and check_password_hash(user['senha'], senha_input):
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['usuario']
            flash('Login efetuado com sucesso!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')

    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    agendamentos = conn.execute('SELECT * FROM agendamentos ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin.html', agendamentos=agendamentos, username=session.get('username'))

@app.route('/admin/alterar-senha', methods=['POST'])
def alterar_senha():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    novo_usuario = request.form.get('novo_usuario').strip()
    nova_senha = request.form.get('nova_senha')

    if novo_usuario and nova_senha:
        senha_hash = generate_password_hash(nova_senha)
        conn = get_db_connection()
        try:
            conn.execute('UPDATE usuarios SET usuario = ?, senha = ? WHERE id = ?', 
                         (novo_usuario, senha_hash, session['user_id']))
            conn.commit()
            session['username'] = novo_usuario
            flash('Usuário e senha alterados com sucesso!', 'success')
        except sqlite3.IntegrityError:
            flash('Este nome de usuário já está em uso.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
