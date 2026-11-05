import os
import sqlite3
import requests
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_secreta_2026_auto_dispatch')

DB_NAME = 'database.db'

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
    
    # Configurações de Notificação Automática (API WhatsApp, Twilio, Webhook)
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

    # Configurações padrão
    configs_iniciais = [
        ('whatsapp_admin', '5511999999999'),
        ('sms_admin', '11999999999'),
        ('whatsapp_api_url', ''),      # URL da API de WhatsApp (ex: Z-API, Evolution API ou CallMeBot)
        ('whatsapp_api_token', ''),    # Token / Chave da API de WhatsApp
        ('twilio_account_sid', ''),    # SID da conta Twilio para SMS automático
        ('twilio_auth_token', ''),     # Token da conta Twilio para SMS
        ('twilio_phone_number', '')    # Número de envio Twilio
    ]
    for c_chave, c_val in configs_iniciais:
        cursor.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)', (c_chave, c_val))

    # Serviços Iniciais
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

def disparar_notificacoes_automaticas(nome, telefone, servico, preco, data, hora):
    """Envia automaticamente Notificações de WhatsApp e SMS no momento exato do agendamento sem ação do admin."""
    conn = get_db_connection()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
    conn.close()

    whatsapp_admin = configs.get('whatsapp_admin', '')
    sms_admin = configs.get('sms_admin', '')
    
    msg_texto = f"💅 *NOVO AGENDAMENTO AUTOMÁTICO - Cath Unhas*\n\n👤 *Cliente:* {nome}\n📞 *Telefone:* {telefone}\n✨ *Serviço:* {servico}\n💰 *Valor:* R$ {preco:.2f}\n📅 *Data:* {data}\n⏰ *Horário:* {hora}"

    # 1. Envio Automático por WhatsApp via CallMeBot / Gateway Webhook / Z-API
    wa_api_url = configs.get('whatsapp_api_url', '').strip()
    wa_api_token = configs.get('whatsapp_api_token', '').strip()

    if wa_api_url:
        try:
            # Exemplo de integração universal via HTTP POST / GET
            payload = {
                'phone': whatsapp_admin,
                'message': msg_texto,
                'apikey': wa_api_token
            }
            requests.post(wa_api_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Erro ao enviar WhatsApp automático: {e}")
    elif whatsapp_admin:
        # Integração gratuita automática via API Pública CallMeBot (WhatsApp)
        try:
            callmebot_url = f"https://api.callmebot.com/whatsapp.php?phone={whatsapp_admin}&text={quote(msg_texto)}&apikey={wa_api_token}"
            requests.get(callmebot_url, timeout=5)
        except Exception as e:
            print(f"Erro no envio CallMeBot WhatsApp: {e}")

    # 2. Envio Automático por SMS via Twilio API
    twilio_sid = configs.get('twilio_account_sid', '').strip()
    twilio_token = configs.get('twilio_auth_token', '').strip()
    twilio_from = configs.get('twilio_phone_number', '').strip()

    if twilio_sid and twilio_token and twilio_from and sms_admin:
        try:
            sms_body = f"Cath Unhas: Novo Agendamento de {nome} - {servico} em {data} as {hora}. R$ {preco:.2f}"
            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            requests.post(
                twilio_url,
                data={'From': twilio_from, 'To': f"+55{sms_admin}", 'Body': sms_body},
                auth=(twilio_sid, twilio_token),
                timeout=5
            )
        except Exception as e:
            print(f"Erro ao enviar SMS via Twilio: {e}")

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

            # DISPARO AUTOMÁTICO DE NOTIFICAÇÕES (SEM NECESSIDADE DE ACESSAR O SITE)
            disparar_notificacoes_automaticas(nome, telefone, servico['nome'], servico['preco'], data, hora)

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

    # Métricas Financeiras
    total_faturamento = conn.execute("SELECT SUM(preco) FROM agendamentos").fetchone()[0] or 0.0
    total_atendimentos = len(agendamentos)
    ticket_medio = (total_faturamento / total_atendimentos) if total_atendimentos > 0 else 0.0

    # Relatório por Serviço
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
    campos = ['whatsapp_admin', 'sms_admin', 'whatsapp_api_url', 'whatsapp_api_token', 'twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number']
    
    for c in campos:
        val = request.form.get(c, '').strip()
        conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave=?), ?, ?)", (c, c, val))
        
    conn.commit()
    conn.close()

    flash('Configurações de Disparo Automático salvas com sucesso!', 'success')
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
            flash('Novo serviço cadastrado!', 'success')
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
        flash('Preço alterado!', 'success')

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
        flash('Horário alterado!', 'success')
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
            flash('Horário incluído!', 'success')
        except sqlite3.IntegrityError:
            flash('Este horário já existe.', 'danger')
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
