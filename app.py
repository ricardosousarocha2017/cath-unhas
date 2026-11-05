import os
import sqlite3
import requests
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_secreta_2026_auto_v5')

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Agendamentos
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
    
    # Serviços e Preços
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            preco REAL NOT NULL,
            imagem TEXT DEFAULT ''
        )
    ''')

    # Horários de Agendamento
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS horarios_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hora TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    # Configurações do Sistema e Apis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            valor TEXT NOT NULL
        )
    ''')
    
    # Usuários Admin
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')

    # Configurações iniciais
    configs_iniciais = [
        ('whatsapp_admin', '5511993947608'),
        ('sms_admin', '11993947608'),
        ('callmebot_apikey', ''),       # Chave da API gratuita do CallMeBot para WhatsApp
        ('whatsapp_api_url', ''),      # URL Webhook Z-API / Evolution
        ('whatsapp_api_token', ''),
        ('twilio_account_sid', ''),
        ('twilio_auth_token', ''),
        ('twilio_phone_number', '')
    ]
    for c_chave, c_val in configs_iniciais:
        cursor.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)', (c_chave, c_val))

    # Serviços Iniciais vinculados às imagens fornecidas
    servicos_iniciais = [
        ('Alongamento Molde F1', 150.00, 'img_brasil.jpeg'),
        ('Manutenção de Molde F1', 90.00, 'img_gel.jpeg'),
        ('Banho de Gel', 100.00, 'img_coracoes.jpeg'),
        ('Manutenção de Banho de Gel', 70.00, 'img_silver.jpeg')
    ]
    for s_nome, s_preco, s_img in servicos_iniciais:
        cursor.execute('INSERT OR IGNORE INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)', (s_nome, s_preco, s_img))

    # Horários Padrão
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

def enviar_notificacoes_automaticas(nome, telefone, servico, preco, data, hora):
    """Dispara a notificação automática para o telemóvel do Administrador no momento exato do agendamento."""
    conn = get_db_connection()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
    conn.close()

    wa_number = configs.get('whatsapp_admin', '').strip()
    callmebot_key = configs.get('callmebot_apikey', '').strip()
    wa_api_url = configs.get('whatsapp_api_url', '').strip()
    wa_api_token = configs.get('whatsapp_api_token', '').strip()

    msg = f"💅 *NOVO AGENDAMENTO - Cath Unhas*\n\n👤 *Cliente:* {nome}\n📞 *Telefone:* {telefone}\n✨ *Serviço:* {servico}\n💰 *Valor:* R$ {preco:.2f}\n📅 *Data:* {data}\n⏰ *Horário:* {hora}"

    # 1. Envio WhatsApp Automático via Z-API / Evolution / Webhook
    if wa_api_url and wa_number:
        try:
            payload = {'phone': wa_number, 'message': msg}
            headers = {'Authorization': f'Bearer {wa_api_token}'} if wa_api_token else {}
            requests.post(wa_api_url, json=payload, headers=headers, timeout=4)
        except Exception as e:
            print(f"Erro Webhook WhatsApp: {e}")

    # 2. Envio WhatsApp Automático Gratuito via CallMeBot API (com apikey cadastrada)
    elif wa_number and callmebot_key:
        try:
            url_callmebot = f"https://api.callmebot.com/whatsapp.php?phone={wa_number}&text={quote(msg)}&apikey={callmebot_key}"
            requests.get(url_callmebot, timeout=5)
        except Exception as e:
            print(f"Erro CallMeBot WhatsApp: {e}")

    # 3. Envio SMS Automático via Twilio API
    twilio_sid = configs.get('twilio_account_sid', '').strip()
    twilio_token = configs.get('twilio_auth_token', '').strip()
    twilio_from = configs.get('twilio_phone_number', '').strip()
    sms_admin = configs.get('sms_admin', '').strip()

    if twilio_sid and twilio_token and twilio_from and sms_admin:
        try:
            sms_body = f"Cath Unhas: Novo Agendamento - {nome} ({servico}) em {data} as {hora}. R$ {preco:.2f}"
            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            requests.post(
                twilio_url,
                data={'From': twilio_from, 'To': f"+55{sms_admin}", 'Body': sms_body},
                auth=(twilio_sid, twilio_token),
                timeout=4
            )
        except Exception as e:
            print(f"Erro SMS Twilio: {e}")

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

            # Executa o disparo automático no momento exato
            enviar_notificacoes_automaticas(nome, telefone, servico['nome'], servico['preco'], data, hora)
            conn.close()

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
    campos = ['whatsapp_admin', 'sms_admin', 'callmebot_apikey', 'whatsapp_api_url', 'whatsapp_api_token', 'twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number']
    
    for c in campos:
        val = request.form.get(c, '').strip()
        conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave=?), ?, ?)", (c, c, val))
        
    conn.commit()
    conn.close()

    flash('Configurações de Automação de WhatsApp e SMS salvas!', 'success')
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
