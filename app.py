import os
import sqlite3
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cath_unhas_cathelin_eloim_v14_clean')

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
            status TEXT DEFAULT 'Confirmado'
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
        ('whatsapp_admin', '5511963271437'),
        ('sms_admin', '11963271437'),
        ('email_admin', ''),
        ('green_instance_id', '710722792308'),
        ('green_api_token', 'df045e5d35e245f08cda18c3dab805e49ecbf003012d478089')
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

def disparar_todos_os_meios(nome, telefone, servico, preco, data, hora):
    conn = get_db_connection()
    configs = {row['chave']: row['valor'] for row in conn.execute('SELECT * FROM config').fetchall()}
    conn.close()

    target_wa = configs.get('whatsapp_admin', '5511963271437').strip()
    green_id = configs.get('green_instance_id', '').strip()
    green_token = configs.get('green_api_token', '').strip()

    msg_texto = (
        f"💅 *NOVO AGENDAMENTO - Cathelin Eloim | Nail Designer*\n\n"
        f"👤 *Cliente:* {nome}\n"
        f"📞 *Contato:* {telefone}\n"
        f"✨ *Procedimento:* {servico}\n"
        f"💰 *Valor:* R$ {preco:.2f}\n"
        f"📅 *Data:* {data}\n"
        f"⏰ *Horário:* {hora}"
    )

    if green_id and green_token and target_wa:
        try:
            url_green = f"https://7107.api.greenapi.com/waInstance{green_id}/sendMessage/{green_token}"
            payload_wa = {"chatId": f"{target_wa}@c.us", "message": msg_texto}
            headers = {'Content-Type': 'application/json'}
            requests.post(url_green, json=payload_wa, headers=headers, timeout=5)
        except Exception as e:
            print(f"Erro WhatsApp: {e}")

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
    datas_disponiveis = conn.execute('SELECT * FROM datas_config WHERE ativo = 1 ORDER BY data ASC').fetchall()
    horarios_ativos = conn.execute('SELECT * FROM horarios_config WHERE ativo = 1 ORDER BY hora ASC').fetchall()
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        servico_id = request.form.get('servico_id')
        data = request.form.get('data')
        hora = request.form.get('hora')

        # Validação de segurança se a data escolhida no calendário está autorizada pelo Admin
        dt_valida = conn.execute('SELECT * FROM datas_config WHERE data = ? AND ativo = 1', (data,)).fetchone()
        if not dt_valida:
            flash('A data selecionada não está disponível no sistema. Por favor, escolha uma data liberada.', 'danger')
            conn.close()
            return redirect(url_for('booking'))

        # Impedir agendamento duplicado
        ocupado = conn.execute('SELECT * FROM agendamentos WHERE data = ? AND hora = ?', (data, hora)).fetchone()
        if ocupado:
            flash(f'O horário {hora} para o dia {data} acabou de ser preenchido. Por favor selecione outro horário.', 'danger')
            conn.close()
            return redirect(url_for('booking'))

        servico = conn.execute('SELECT * FROM servicos WHERE id = ?', (servico_id,)).fetchone()
        
        if servico:
            conn.execute(
                'INSERT INTO agendamentos (nome, telefone, servico, preco, data, hora) VALUES (?, ?, ?, ?, ?, ?)',
                (nome, telefone, servico['nome'], servico['preco'], data, hora)
            )
            conn.commit()
            conn.close()

            disparar_todos_os_meios(nome, telefone, servico['nome'], servico['preco'], data, hora)

            return render_template('booking_sucesso.html', nome=nome, servico=servico['nome'], data=data, hora=hora, preco=servico['preco'])

    conn.close()
    return render_template('booking.html', servicos=servicos, datas=datas_disponiveis, horarios=horarios_ativos)

@app.route('/api/horarios-ocupados/<data>')
def horarios_ocupados(data):
    conn = get_db_connection()
    agendamentos = conn.execute('SELECT hora FROM agendamentos WHERE data = ?', (data,)).fetchall()
    conn.close()
    ocupados = [row['hora'] for row in agendamentos]
    return jsonify(ocupados)

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
    agendamentos = conn.execute('SELECT * FROM agendamentos ORDER BY data ASC, hora ASC').fetchall()
    servicos = conn.execute('SELECT * FROM servicos').fetchall()
    datas_config = conn.execute('SELECT * FROM datas_config ORDER BY data ASC').fetchall()
    horarios_config = conn.execute('SELECT * FROM horarios_config ORDER BY hora ASC').fetchall()
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
                           horarios=horarios_config, 
                           configs=configs,
                           username=session.get('username'),
                           total_faturamento=total_faturamento,
                           total_atendimentos=total_atendimentos,
                           ticket_medio=ticket_medio,
                           relatorio_servicos=relatorio_servicos,
                           imagens_disponiveis=imagens_disponiveis)

@app.route('/admin/adicionar-data', methods=['POST'])
def adicionar_data():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    nova_data = request.form.get('nova_data', '').strip()
    if nova_data:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO datas_config (data, ativo) VALUES (?, 1)', (nova_data,))
            conn.commit()
            flash(f'Data {nova_data} liberada no sistema!', 'success')
        except sqlite3.IntegrityError:
            flash('Data já existente.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/toggle-data/<int:data_id>', methods=['POST'])
def toggle_data(data_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    d = conn.execute('SELECT ativo FROM datas_config WHERE id = ?', (data_id,)).fetchone()
    if d:
        novo_status = 0 if d['ativo'] == 1 else 1
        conn.execute('UPDATE datas_config SET ativo = ? WHERE id = ?', (novo_status, data_id))
        conn.commit()
        flash('Status da data alterado!', 'success')
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/remover-data/<int:data_id>', methods=['POST'])
def remover_data(data_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM datas_config WHERE id = ?', (data_id,))
    conn.commit()
    conn.close()
    flash('Data removida!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/adicionar-horario', methods=['POST'])
def adicionar_horario():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    novo_horario = request.form.get('novo_horario', '').strip()
    if novo_horario:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO horarios_config (hora, ativo) VALUES (?, 1)', (novo_horario,))
            conn.commit()
            flash('Horário adicionado!', 'success')
        except sqlite3.IntegrityError:
            flash('Este horário já existe.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/toggle-horario/<int:horario_id>', methods=['POST'])
def toggle_horario(horario_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    h = conn.execute('SELECT ativo FROM horarios_config WHERE id = ?', (horario_id,)).fetchone()
    if h:
        novo_status = 0 if h['ativo'] == 1 else 1
        conn.execute('UPDATE horarios_config SET ativo = ? WHERE id = ?', (novo_status, horario_id))
        conn.commit()
        flash('Status do horário alterado!', 'success')
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/remover-horario/<int:horario_id>', methods=['POST'])
def remover_horario(horario_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM horarios_config WHERE id = ?', (horario_id,))
    conn.commit()
    conn.close()
    flash('Horário removido!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/remover-agendamento/<int:agendamento_id>', methods=['POST'])
def remover_agendamento(agendamento_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM agendamentos WHERE id = ?', (agendamento_id,))
    conn.commit()
    conn.close()
    flash('Agendamento cancelado com sucesso!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/atualizar-config-api', methods=['POST'])
def atualizar_config_api():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    campos = ['whatsapp_admin', 'sms_admin', 'email_admin', 'green_instance_id', 'green_api_token', 'telegram_bot_token', 'telegram_chat_id', 'twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number', 'resend_api_key']
    
    for c in campos:
        val = request.form.get(c, '').strip()
        conn.execute("INSERT OR REPLACE INTO config (id, chave, valor) VALUES ((SELECT id FROM config WHERE chave=?), ?, ?)", (c, c, val))
        
    conn.commit()
    conn.close()

    flash('Configurações salvas!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/alterar-senha', methods=['POST'])
def alterar_senha():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    novo_usuario = request.form.get('novo_usuario', '').strip()
    nova_senha = request.form.get('nova_senha', '').strip()
    confirmar_senha = request.form.get('confirmar_senha', '').strip()

    if not novo_usuario or not nova_senha:
        flash('Preencha todos os campos.', 'danger')
        return redirect(url_for('admin'))

    if nova_senha != confirmar_senha:
        flash('As senhas não coincidem.', 'danger')
        return redirect(url_for('admin'))

    senha_hash = generate_password_hash(nova_senha)
    conn = get_db_connection()
    try:
        conn.execute('UPDATE usuarios SET usuario = ?, senha = ? WHERE id = ?', 
                     (novo_usuario, senha_hash, session['user_id']))
        conn.commit()
        session['username'] = novo_usuario
        flash('Login e senha atualizados!', 'success')
    except sqlite3.IntegrityError:
        flash('Usuário já em uso.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/adicionar-servico', methods=['POST'])
def adicionar_servico():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    nome_servico = request.form.get('nome_servico').strip()
    preco_servico = request.form.get('preco_servico')
    imagem_servico = 'banho_gel.jpeg'
    
    if 'foto_file' in request.files and request.files['foto_file'].filename != '':
        file = request.files['foto_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagem_servico = filename
    elif request.form.get('imagem_url'):
        imagem_servico = request.form.get('imagem_url').strip()
    elif request.form.get('imagem_servico'):
        imagem_servico = request.form.get('imagem_servico')

    if nome_servico and preco_servico:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)', 
                         (nome_servico, float(preco_servico), imagem_servico))
            conn.commit()
            flash('Serviço cadastrado com foto!', 'success')
        except sqlite3.IntegrityError:
            flash('Serviço já existente.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/atualizar-servico-foto', methods=['POST'])
def atualizar_servico_foto():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    servico_id = request.form.get('servico_id')
    novo_preco = request.form.get('novo_preco')
    imagem_selecionada = request.form.get('imagem_servico')
    url_imagem = request.form.get('imagem_url', '').strip()

    imagem_final = None

    if 'nova_foto_file' in request.files and request.files['nova_foto_file'].filename != '':
        file = request.files['nova_foto_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagem_final = filename

    if not imagem_final and url_imagem:
        imagem_final = url_imagem

    if not imagem_final and imagem_selecionada:
        imagem_final = imagem_selecionada

    if servico_id and novo_preco:
        conn = get_db_connection()
        if imagem_final:
            conn.execute('UPDATE servicos SET preco = ?, imagem = ? WHERE id = ?', (float(novo_preco), imagem_final, servico_id))
        else:
            conn.execute('UPDATE servicos SET preco = ? WHERE id = ?', (float(novo_preco), servico_id))
        conn.commit()
        conn.close()
        flash('Serviço e foto atualizados com sucesso!', 'success')

    return redirect(url_for('admin'))

@app.route('/admin/remover-servico/<int:servico_id>', methods=['POST'])
def remover_servico(servico_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM servicos WHERE id = ?', (servico_id,))
    conn.commit()
    conn.close()
    flash('Serviço removido!', 'success')

    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
