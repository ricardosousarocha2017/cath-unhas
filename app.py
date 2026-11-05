import os
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_resend_email_wa_2026')

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
        ('email_admin', 'seu_email@gmail.com'),
        ('resend_api_key', ''),
        ('green_instance_id', '710722792308'),
        ('green_api_token', 'df045e5d35e245f08cda18c3dab805e49ecbf003012d478089')
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

def disparar_notificacoes_multicanais(nome, telefone, servico, preco, data, hora):
    """Dispara notificações para WhatsApp (Green-API) e Notificação Instantânea por E-mail."""
    conn = get_db_connection()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
    conn.close()

    wa_number = configs.get('whatsapp_admin', '5511991255823').strip()
    green_id = configs.get('green_instance_id', '').strip()
    green_token = configs.get('green_api_token', '').strip()
    email_admin = configs.get('email_admin', '').strip()
    resend_key = configs.get('resend_api_key', '').strip()

    # 1. Envio por WhatsApp via Green-API
    if green_id and green_token and wa_number:
        try:
            url_green = f"https://7107.api.greenapi.com/waInstance{green_id}/sendMessage/{green_token}"
            mensaje_wa = (
                f"💅 *NOVO AGENDAMENTO AUTOMÁTICO - Cath Unhas*\n\n"
                f"👤 *Cliente:* {nome}\n"
                f"📞 *Contato:* {telefone}\n"
                f"✨ *Procedimento:* {servico}\n"
                f"💰 *Valor:* R$ {preco:.2f}\n"
                f"📅 *Data:* {data}\n"
                f"⏰ *Horário:* {hora}"
            )
            payload = {"chatId": f"{wa_number}@c.us", "message": mensaje_wa}
            headers = {'Content-Type': 'application/json'}
            requests.post(url_green, json=payload, headers=headers, timeout=5)
        except Exception as e:
            print(f"Erro no envio do WhatsApp via Green-API: {e}")

    # 2. Envio de Notificação por E-mail Instantâneo (Ultra Eficaz / Sem bloqueios)
    if resend_key and email_admin:
        try:
            url_resend = "https://api.resend.com/emails"
            email_payload = {
                "from": "Cath Unhas <onboarding@resend.dev>",
                "to": [email_admin],
                "subject": f"💅 NOVO AGENDAMENTO: {nome} - {servico}",
                "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #f7f2f5; border-radius: 12px;">
                    <h2 style="color: #421e2f;">💅 Novo Agendamento Confirmado!</h2>
                    <p>Um novo agendamento foi efetuado no site de forma automática:</p>
                    <ul style="line-height: 1.8;">
                        <li><strong>Cliente:</strong> {nome}</li>
                        <li><strong>Contato/WhatsApp:</strong> {telefone}</li>
                        <li><strong>Serviço:</strong> {servico}</li>
                        <li><strong>Valor:</strong> R$ {preco:.2f}</li>
                        <li><strong>Data:</strong> {data}</li>
                        <li><strong>Horário:</strong> {hora}</li>
                    </ul>
                </div>
                """
            }
            headers_resend = {
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            }
            requests.post(url_resend, json=email_payload, headers=headers_resend, timeout=5)
        except Exception as e:
            print(f"Erro no envio de e-mail Resend: {e}")

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

            disparar_notificacoes_multicanais(nome, telefone, servico['nome'], servico['preco'], data, hora)

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
    campos = ['whatsapp_admin', 'email_admin', 'resend_api_key', 'green_instance_id', 'green_api_token']
    
    for c in campos:
        val = request.form.get(c, '').strip()
        conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave=?), ?, ?)", (c, c, val))
        
    conn.commit()
    conn.close()

    flash('Configurações de Automação salvas com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/adicionar-servico', methods=['POST'])
def adicionar_servico():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    nome_servico = request.form.get('nome_servico').strip()
    preco_servico = request.form.get('preco_servico')
    imagem_servico = request.form.get('imagem_servico') or 'img_gel.jpeg'

    if nome_servico and preco_servico:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)', 
                         (nome_servico, float(preco_servico), imagem_servico))
            conn.commit()
            flash('Novo serviço cadastrado com sucesso!', 'success')
        except sqlite3.IntegrityError:
            flash('Este serviço já existe.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/remover-servico/<int:servico_id>', methods=['POST'])
def remover_servico(servico_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM servicos WHERE id = ?', (servico_id,))
    conn.commit()
    conn.close()
    flash('Serviço excluído!', 'success')

    return redirect(url_for('admin'))

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
        flash('Preço alterado com sucesso!', 'success')

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
        flash('Status do horário alterado!', 'success')
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
            flash('Horário adicionado com sucesso!', 'success')
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
            flash('Nome de usuário indisponível.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
