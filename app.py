import os
import sqlite3
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_secreta_2026_v3')

DB_NAME = 'database.db'
NUMERO_WHATSAPP_ADMIN = "5511963271437"  # Substitua pelo seu número com DDD

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
            preco REAL NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    
    # Tabela de Serviços e Preços
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            preco REAL NOT NULL
        )
    ''')

    # Tabela de Configurações de Horários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS horarios_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
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

    # Serviços Iniciais Solicitados
    servicos_iniciais = [
        ('Alongamento Molde F1', 150.00),
        ('Manutenção de Molde F1', 90.00),
        ('Banho de Gel', 100.00),
        ('Manutenção de Banho de Gel', 70.00)
    ]
    for s_nome, s_preco in servicos_iniciais:
        cursor.execute('INSERT OR IGNORE INTO servicos (nome, preco) VALUES (?, ?)', (s_nome, s_preco))

    # Horários Iniciais de Atendimento (exemplo: 08:00 às 18:00)
    horarios_padrao = ["08:00", "09:30", "11:00", "13:30", "15:00", "16:30", "18:00"]
    for h in horarios_padrao:
        cursor.execute('INSERT OR IGNORE INTO horarios_config (hora, ativo) VALUES (?, 1)', (h,))

    # Usuário Admin Padrão
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        senha_hash = generate_password_hash('1234')
        cursor.execute('INSERT INTO usuarios (usuario, senha) VALUES (?, ?)', ('admin', senha_hash))
        
    conn.commit()
    conn.close()

init_db()

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

        # Buscar detalhes do serviço selecionado
        servico = conn.execute('SELECT * FROM servicos WHERE id = ?', (servico_id,)).fetchone()
        
        if servico:
            conn.execute(
                'INSERT INTO agendamentos (nome, telefone, servico, preco, data, hora) VALUES (?, ?, ?, ?, ?, ?)',
                (nome, telefone, servico['nome'], servico['preco'], data, hora)
            )
            conn.commit()
            conn.close()

            # Mensagem formatada para o WhatsApp da Admin
            mensagem = f"💅 *Novo Agendamento - Cath Unhas*\n\n👤 *Cliente:* {nome}\n📞 *Telefone:* {telefone}\n✨ *Serviço:* {servico['nome']}\n💰 *Valor:* R$ {servico['preco']:.2f}\n📅 *Data:* {data}\n⏰ *Horário:* {hora}"
            link_whatsapp = f"https://api.whatsapp.com/send?phone={NUMERO_WHATSAPP_ADMIN}&text={quote(mensagem)}"

            return render_template('booking_sucesso.html', nome=nome, link_whatsapp=link_whatsapp)

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
    conn.close()
    
    return render_template('admin.html', 
                           agendamentos=agendamentos, 
                           servicos=servicos, 
                           horarios=horarios, 
                           username=session.get('username'))

@app.route('/admin/atualizar-preco', methods=['POST'])
def atualizar_preco():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    servico_id = request.form.get('servico_id')
    novo_preco = request.form.get('novo_preco')

    if servico_id and novo_preco:
        conn = get_db_connection()
        conn.execute('UPDATE servicos SET preco = ? WHERE id = ?', (float(novo_preco), servico_id))
        conn.commit()
        conn.close()
        flash('Preço do serviço atualizado com sucesso!', 'success')

    return redirect(url_for('admin'))

@app.route('/admin/toggle-horario', methods=['POST'])
def toggle_horario():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    horario_id = request.form.get('horario_id')
    conn = get_db_connection()
    h = conn.execute('SELECT ativo FROM horarios_config WHERE id = ?', (horario_id,)).fetchone()
    if h:
        novo_status = 0 if h['ativo'] == 1 else 1
        conn.execute('UPDATE horarios_config SET ativo = ? WHERE id = ?', (novo_status, horario_id))
        conn.commit()
        flash('Status do horário atualizado!', 'success')
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/adicionar-horario', methods=['POST'])
def adicionar_horario():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    novo_horario = request.form.get('novo_horario').strip()
    if novo_horario:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO horarios_config (hora, ativo) VALUES (?, 1)', (novo_horario,))
            conn.commit()
            flash('Novo horário adicionado!', 'success')
        except sqlite3.IntegrityError:
            flash('Este horário já existe na lista.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

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
