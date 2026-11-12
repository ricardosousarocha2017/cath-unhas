import os
import sqlite3
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_cathelin_eloim_v23_final_fix')

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DB_NAME = 'database.db'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
            forma_pagamento TEXT DEFAULT 'Pix (QR Code / Copia e Cola)',
            link_pagamento TEXT DEFAULT '',
            valor_sinal REAL DEFAULT 30.0,
            status_sinal TEXT DEFAULT 'Pendente',
            status TEXT DEFAULT 'Confirmado'
        )
    ''')

    colunas_novas = [
        ("forma_pagamento", "TEXT DEFAULT 'Pix (QR Code / Copia e Cola)'"),
        ("link_pagamento", "TEXT DEFAULT ''"),
        ("valor_sinal", "REAL DEFAULT 30.0"),
        ("status_sinal", "TEXT DEFAULT 'Pendente'")
    ]
    for col, def_val in colunas_novas:
        try:
            cursor.execute(f"ALTER TABLE agendamentos ADD COLUMN {col} {def_val}")
        except sqlite3.OperationalError:
            pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            preco REAL NOT NULL,
            imagem TEXT DEFAULT ''
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS datas_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
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
        ('whatsapp_admin', os.environ.get('WHATSAPP_ADMIN', '5511963271437')),
        ('sms_admin', os.environ.get('SMS_ADMIN', '11963271437')),
        ('email_admin', os.environ.get('EMAIL_ADMIN', '')),
        ('green_instance_id', os.environ.get('GREEN_INSTANCE_ID', '710722792308')),
        ('green_api_token', os.environ.get('GREEN_API_TOKEN', 'df045e5d35e245f08cda18c3dab805e49ecbf003012d478089')),
        ('pix_chave', os.environ.get('PIX_CHAVE', '11963271437')),
        ('pix_titular', os.environ.get('PIX_TITULAR', 'Cathelin Eloim')),
        ('pix_banco', os.environ.get('PIX_BANCO', 'Nubank')),
        ('valor_sinal_padrao', os.environ.get('VALOR_SINAL_PADRAO', '30.00')),
        ('link_cartao_padrao', os.environ.get('LINK_CARTAO_PADRAO', 'https://pay.mercadopago.com.br/checkout-exemplo-sinal')),
        ('qr_code_image', os.environ.get('QR_CODE_IMAGE', 'qrcode_pix.png')),
        ('avatar_perfil', os.environ.get('AVATAR_PERFIL', 'alongamento_molde.jpeg')),
        ('admin_senha_texto', os.environ.get('ADMIN_SENHA_TEXTO', '1234'))
    ]
    for c_chave, c_val in configs_iniciais:
        cursor.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)', (c_chave, c_val))

    servicos_iniciais = [
        ('Alongamento Molde F1', 150.00, 'alongamento_molde.jpeg'),
        ('Manutenção de Molde F1', 90.00, 'manutencao_molde.jpeg'),
        ('Banho de Gel', 100.00, 'banho_gel.jpeg'),
        ('Manutenção de Banho de Gel', 70.00, 'manutencao_banho_gel.jpeg')
    ]
    for s_nome, s_preco, s_img in servicos_iniciais:
        cursor.execute('''
            INSERT INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)
            ON CONFLICT(nome) DO UPDATE SET imagem=excluded.imagem, preco=excluded.preco
        ''', (s_nome, s_preco, s_img))

    horarios_padrao = ["08:00", "09:30", "11:00", "13:30", "15:00", "16:30", "18:00"]
    for h in horarios_padrao:
        cursor.execute('INSERT OR IGNORE INTO horarios_config (hora, ativo) VALUES (?, 1)', (h,))

    hoje = datetime.now()
    cursor.execute('SELECT COUNT(*) FROM datas_config')
    if cursor.fetchone()[0] == 0:
        from datetime import timedelta
        for i in range(14):
            dt_str = (hoje + timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute('INSERT OR IGNORE INTO datas_config (data, ativo) VALUES (?, 1)', (dt_str,))

    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        senha_hash = generate_password_hash('1234')
        cursor.execute('INSERT INTO usuarios (usuario, senha) VALUES (?, ?)', ('admin', senha_hash))
        
    conn.commit()
    conn.close()

init_db()

def disparar_comprovantes_e_notificacoes(agendamento_id, nome, telefone, servico, preco, data, hora, forma_pagamento, valor_sinal, status_sinal, link_pagamento):
    try:
        conn = get_db_connection()
        configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
        conn.close()

        target_wa = configs.get('whatsapp_admin', '5511963271437').strip()
        green_id = configs.get('green_instance_id', '').strip()
        green_token = configs.get('green_api_token', '').strip()

        msg_admin = (
            f"🧾 *COMPROVANTE DE AGENDAMENTO (ADMIN)*\n"
            f"📋 *ID da Reserva:* #{agendamento_id}\n"
            f"👤 *Cliente:* {nome}\n"
            f"📞 *Contato:* {telefone}\n"
            f"✨ *Procedimento:* {servico}\n"
            f"💰 *Valor Total:* R$ {preco:.2f}\n"
            f"💳 *Sinal de Garantia:* R$ {valor_sinal:.2f} ({status_sinal})\n"
            f"💵 *Forma de Pagamento:* {forma_pagamento}\n"
            f"📅 *Data:* {data}\n"
            f"⏰ *Horário:* {hora}"
        )

        if green_id and green_token and target_wa:
            url_green = f"https://7107.api.greenapi.com/waInstance{green_id}/sendMessage/{green_token}"
            headers = {'Content-Type': 'application/json'}
            requests.post(url_green, json={"chatId": f"{target_wa}@c.us", "message": msg_admin}, headers=headers, timeout=5)
    except Exception as e:
        print(f"Erro ao disparar WhatsApp: {e}")

@app.route('/')
def home():
    try:
        conn = get_db_connection()
        servicos = conn.execute('SELECT * FROM servicos').fetchall()
        configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
        conn.close()
        return render_template('home.html', servicos=servicos, configs=configs)
    except Exception as e:
        return f"Erro na página inicial: {e}", 500

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    try:
        conn = get_db_connection()
        servicos = conn.execute('SELECT * FROM servicos').fetchall()
        datas_disponiveis = conn.execute('SELECT * FROM datas_config WHERE ativo = 1 ORDER BY data ASC').fetchall()
        horarios_ativos = conn.execute('SELECT * FROM horarios_config WHERE ativo = 1 ORDER BY hora ASC').fetchall()
        configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
        
        valor_sinal_padrao = float(str(configs.get('valor_sinal_padrao', '30.00')).replace(',', '.'))
        link_cartao_padrao = configs.get('link_cartao_padrao', 'https://pay.mercadopago.com.br/checkout-exemplo')

        if request.method == 'POST':
            nome = request.form.get('nome')
            telefone = request.form.get('telefone')
            servico_id = request.form.get('servico_id')
            data = request.form.get('data')
            hora = request.form.get('hora')
            forma_pagamento = request.form.get('forma_pagamento', 'Pix (QR Code / Copia e Cola)')

            if 'Pix' in forma_pagamento:
                status_sinal = 'Pix Enviado (A Confirmar)'
            elif 'Crédito' in forma_pagamento or 'Débito' in forma_pagamento or 'Cartão' in forma_pagamento:
                status_sinal = 'Link Cartão Emitido (Pendente)'
            else:
                status_sinal = 'Pagar Sinal no Studio'

            dt_valida = conn.execute('SELECT * FROM datas_config WHERE data = ? AND ativo = 1', (data,)).fetchone()
            if not dt_valida:
                flash('A data selecionada não está disponível. Por favor escolha uma data liberada.', 'danger')
                conn.close()
                return redirect(url_for('booking'))

            ocupado = conn.execute('SELECT * FROM agendamentos WHERE data = ? AND hora = ?', (data, hora)).fetchone()
            if ocupado:
                flash(f'O horário {hora} para o dia {data} já foi preenchido. Por favor selecione outro horário.', 'danger')
                conn.close()
                return redirect(url_for('booking'))

            servico = conn.execute('SELECT * FROM servicos WHERE id = ?', (servico_id,)).fetchone()
            
            if servico:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO agendamentos 
                       (nome, telefone, servico, preco, data, hora, forma_pagamento, link_pagamento, valor_sinal, status_sinal) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (nome, telefone, servico['nome'], servico['preco'], data, hora, forma_pagamento, link_cartao_padrao, valor_sinal_padrao, status_sinal)
                )
                novo_id = cursor.lastrowid
                conn.commit()
                conn.close()

                disparar_comprovantes_e_notificacoes(novo_id, nome, telefone, servico['nome'], servico['preco'], data, hora, forma_pagamento, valor_sinal_padrao, status_sinal, link_cartao_padrao)

                return render_template('booking_sucesso.html', 
                                       agendamento_id=novo_id,
                                       nome=nome, 
                                       telefone=telefone,
                                       servico=servico['nome'], 
                                       data=data, 
                                       hora=hora, 
                                       preco=servico['preco'],
                                       forma_pagamento=forma_pagamento,
                                       link_pagamento=link_cartao_padrao,
                                       valor_sinal=valor_sinal_padrao,
                                       status_sinal=status_sinal,
                                       configs=configs)

        conn.close()
        return render_template('booking.html', 
                               servicos=servicos, 
                               datas=datas_disponiveis, 
                               horarios=horarios_ativos,
                               configs=configs,
                               valor_sinal_padrao=valor_sinal_padrao,
                               link_cartao_padrao=link_cartao_padrao)
    except Exception as e:
        return f"Erro no agendamento: {e}", 500

@app.route('/comprovante/<int:agendamento_id>')
def comprovante(agendamento_id):
    try:
        conn = get_db_connection()
        agendamento = conn.execute('SELECT * FROM agendamentos WHERE id = ?', (agendamento_id,)).fetchone()
        configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
        conn.close()

        if not agendamento:
            flash('Comprovante não encontrado.', 'danger')
            return redirect(url_for('home'))

        return render_template('comprovante.html', agendamento=agendamento, configs=configs)
    except Exception as e:
        return f"Erro ao gerar comprovante: {e}", 500

@app.route('/api/horarios-ocupados/<data>')
def horarios_ocupados(data):
    try:
        conn = get_db_connection()
        agendamentos = conn.execute('SELECT hora FROM agendamentos WHERE data = ?', (data,)).fetchall()
        conn.close()
        ocupados = [row['hora'] for row in agendamentos]
        return jsonify(ocupados)
    except Exception as e:
        return jsonify([])

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
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
    except Exception as e:
        return f"Erro no login: {e}", 500

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        agendamentos = conn.execute('SELECT * FROM agendamentos ORDER BY data ASC, hora ASC').fetchall()
        servicos = conn.execute('SELECT * FROM servicos').fetchall()
        datas_config = conn.execute('SELECT * FROM datas_config ORDER BY data ASC').fetchall()
        horarios_config = conn.execute('SELECT * FROM horarios_config ORDER BY hora ASC').fetchall()
        configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}

        total_faturamento = conn.execute("SELECT SUM(preco) FROM agendamentos").fetchone()[0] or 0.0
        total_atendimentos = len(agendamentos)
        ticket_medio = (total_faturamento / total_atendimentos) if total_atendimentos > 0 else 0.0

        sinais_pix = len([a for a in agendamentos if 'Pix' in (a['forma_pagamento'] or '')])
        sinais_cartao = len([a for a in agendamentos if 'Crédito' in (a['forma_pagamento'] or '') or 'Débito' in (a['forma_pagamento'] or '') or 'Cartão' in (a['forma_pagamento'] or '')])
        sinais_studio = len([a for a in agendamentos if 'Studio' in (a['forma_pagamento'] or '')])

        relatorio_servicos = conn.execute('''
            SELECT servico, COUNT(*) as qtd, SUM(preco) as total 
            FROM agendamentos 
            GROUP BY servico 
            ORDER BY total DESC
        ''').fetchall()

        imagens_disponiveis = []
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for f in os.listdir(app.config['UPLOAD_FOLDER']):
                if allowed_file(f):
                    imagens_disponiveis.append(f)
        imagens_disponiveis.sort()

        conn.close()

        return render_template('admin.html', 
                               agendamentos=agendamentos, 
                               servicos=servicos, 
                               datas_config=datas_config,
                               horarios_config=horarios_config, 
                               configs=configs,
                               username=session.get('username'),
                               total_faturamento=total_faturamento,
                               total_atendimentos=total_atendimentos,
                               ticket_medio=ticket_medio,
                               sinais_pix=sinais_pix,
                               sinais_cartao=sinais_cartao,
                               sinais_studio=sinais_studio,
                               relatorio_servicos=relatorio_servicos,
                               imagens_disponiveis=imagens_disponiveis)
    except Exception as e:
        return f"Erro interno no Painel Admin: {e}", 500

@app.route('/admin/alterar-status-sinal/<int:agendamento_id>', methods=['POST'])
def alterar_status_sinal(agendamento_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        novo_status_sinal = request.form.get('novo_status_sinal')
        if novo_status_sinal:
            conn = get_db_connection()
            agendamento = conn.execute('SELECT * FROM agendamentos WHERE id = ?', (agendamento_id,)).fetchone()
            configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
            
            conn.execute('UPDATE agendamentos SET status_sinal = ? WHERE id = ?', (novo_status_sinal, agendamento_id))
            conn.commit()
            conn.close()

            # Disparar devolutiva via Green-API para o WhatsApp do cliente quando o sinal for confirmado/pago
            if agendamento and novo_status_sinal and novo_status_sinal != 'Pendente':
                telefone_cliente = agendamento['telefone']
                nome_cliente = agendamento['nome']
                servico_cliente = agendamento['servico']
                data_cliente = agendamento['data']
                hora_cliente = agendamento['hora']
                valor_sinal_val = agendamento['valor_sinal'] if agendamento['valor_sinal'] else 30.0

                target_wa = "".join([c for c in str(telefone_cliente) if c.isdigit()])
                if len(target_wa) <= 11 and not target_wa.startswith('55'):
                    target_wa = '55' + target_wa

                green_id = configs.get('green_instance_id', '710722792308').strip()
                green_token = configs.get('green_api_token', 'df045e5d35e245f08cda18c3dab805e49ecbf003012d478089').strip()

                if green_id and green_token and target_wa:
                    msg_confirmacao = (
                        f"✨ *CATHELIN ELOIM STUDIO — SINAL CONFIRMADO* ✨\n\n"
                        f"Olá, *{nome_cliente}*! 💖\n\n"
                        f"Informamos que o pagamento do seu sinal (R$ {valor_sinal_val:.2f}) referente ao agendamento de *{servico_cliente}* para o dia *{data_cliente}* às *{hora_cliente}* foi **conferido e confirmado junto ao banco com sucesso!** ✅\n\n"
                        f"Seu horário está oficialmente garantido. Estamos ansiosas para recebê-la! 💅✨"
                    )
                    url_green = f"https://7107.api.greenapi.com/waInstance{green_id}/sendMessage/{green_token}"
                    headers = {'Content-Type': 'application/json'}
                    try:
                        requests.post(url_green, json={"chatId": f"{target_wa}@c.us", "message": msg_confirmacao}, headers=headers, timeout=5)
                    except Exception as ex:
                        print("Erro ao enviar WhatsApp Green-API ao cliente:", ex)

            flash(f'Status do sinal atualizado para "{novo_status_sinal}" e devolutiva enviada ao cliente com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao alterar status: {e}', 'danger')

    return redirect(url_for('admin'))



@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('home'))
