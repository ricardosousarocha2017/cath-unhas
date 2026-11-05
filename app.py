import os
import sqlite3
import requests
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_secreta_2026_green_api')

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
            preco REAL NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            preco REAL NOT NULL,
            imagem TEXT DEFAULT ''
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS horarios_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            valor TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')

    configs_iniciais = [
        ('whatsapp_admin', '5511991255823'),
        ('green_instance_id', ''),       # Seu idInstance da Green-API
        ('green_api_token', '')          # Seu apiTokenInstance da Green-API
    ]
    for c_chave, c_val in configs_iniciais:
        cursor.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)', (c_chave, c_val))

    servicos_iniciais = [
        ('Alongamento Molde F1', 150.00, 'img_brasil.jpeg'),
        ('Manutenção de Molde F1', 90.00, 'img_gel.jpeg'),
        ('Banho de Gel', 100.00, 'img_coracoes.jpeg'),
        ('Manutenção de Banho de Gel', 70.00, 'img_silver.jpeg')
    ]
    for s_nome, s_preco, s_img in servicos_iniciais:
        cursor.execute('INSERT OR IGNORE INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)', (s_nome, s_preco, s_img))

    horarios_padrao = ["08:00", "09:30", "11:00", "13:30", "15:00", "16:30", "18:00"]
    for h in horarios_padrao:
        cursor.execute('INSERT OR IGNORE INTO horarios_config (hora, ativo) VALUES (?, 1)', (h,))

    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        senha_hash = generate_password_hash('1234')
        cursor.execute('INSERT INTO usuarios (usuario, senha) VALUES (?, ?)', ('admin', senha_hash))
        
    conn.commit()
    conn.close()

init_db()

def disparar_whatsapp_automatico(nome, telefone, servico, preco, data, hora):
    """Envia mensagem direta no WhatsApp usando a Green-API."""
    conn = get_db_connection()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
    conn.close()

    wa_number = configs.get('whatsapp_admin', '5511991255823').strip()
    instance_id = configs.get('green_instance_id', '').strip()
    api_token = configs.get('green_api_token', '').strip()

    if instance_id and api_token and wa_number:
        try:
            url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{api_token}"
            mensaje = (
                f"💅 *NOVO AGENDAMENTO - Cath Unhas*\n\n"
                f"👤 *Cliente:* {nome}\n"
                f"📞 *Contato:* {telefone}\n"
                f"✨ *Procedimento:* {servico}\n"
                f"💰 *Valor:* R$ {preco:.2f}\n"
                f"📅 *Data:* {data}\n"
                f"⏰ *Horário:* {hora}"
            )
            payload = {
                "chatId": f"{wa_number}@c.us",
                "message": mensaje
            }
            headers = {'Content-Type': 'application/json'}
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            print(f"Erro ao disparar WhatsApp: {e}")

@app.route('/')
def home():
    conn = get_db_connection()
    servicos = conn.execute('SELECT * FROM servicos').fetchall()
    conn.close()
    return render_template('home.html', servicos=servicos)

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    conn = get_db_connection()
    servicos = conn.execute('SELECT * FROM servicos').fetchall()
    horarios = conn.execute('SELECT * FROM horarios_config WHERE ativo = 1 ORDER BY hora ASC').fetchall()
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        servico_id = request.form.get('servico_id')
        data = request.form.get('data')
        hora = request.form.get('hora')

        servico = conn.execute('SELECT * FROM servicos WHERE id = ?', (servico_id,)).fetchone()
        
        if servico:
            conn.execute(
                'INSERT INTO agendamentos (nome, telefone, servico, preco, data, hora) VALUES (?, ?, ?, ?, ?, ?)',
                (nome, telefone, servico['nome'], servico['preco'], data, hora)
            )
            conn.commit()
            conn.close()

            # Disparo imediato para o seu WhatsApp
            disparar_whatsapp_automatico(nome, telefone, servico['nome'], servico['preco'], data, hora)

            return render_template('booking_sucesso.html', nome=nome, servico=servico['nome'], data=data, hora=hora, preco=servico['preco'])

    conn.close()
    return render_template('booking.html', servicos=servicos, horarios=horarios)

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
    servicos = conn.execute('SELECT * FROM servicos').fetchall()
    horarios = conn.execute('SELECT * FROM horarios_config ORDER BY hora ASC').fetchall()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}

    total_faturamento = conn.execute("SELECT SUM(preco) FROM agendamentos").fetchone()[0] or 0.0
    total_atendimentos = len(agendamentos)
    ticket_medio = (total_faturamento / total_atendimentos) if total_atendimentos > 0 else 0.0

    relatorio_servicos = conn.execute('''
        SELECT servico, COUNT(*) as qtd, SUM(preco) as total 
        FROM agendamentos 
        GROUP BY servico 
        ORDER BY total DESC
    ''').fetchall()

    conn.close()

    return render_template('admin.html', 
                           agendamentos=agendamentos, 
                           servicos=servicos, 
                           horarios=horarios, 
                           configs=configs,
                           username=session.get('username'),
                           total_faturamento=total_faturamento,
                           total_atendimentos=total_atendimentos,
                           ticket_medio=ticket_medio,
                           relatorio_servicos=relatorio_servicos)

@app.route('/admin/atualizar-config-api', methods=['POST'])
def atualizar_config_api():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    whatsapp_admin = request.form.get('whatsapp_admin', '').strip()
    green_instance_id = request.form.get('green_instance_id', '').strip()
    green_api_token = request.form.get('green_api_token', '').strip()

    conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave='whatsapp_admin'), 'whatsapp_admin', ?)", (whatsapp_admin,))
    conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave='green_instance_id'), 'green_instance_id', ?)", (green_instance_id,))
    conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave='green_api_token'), 'green_api_token', ?)", (green_api_token,))
        
    conn.commit()
    conn.close()

    flash('Dados do WhatsApp salvos com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)