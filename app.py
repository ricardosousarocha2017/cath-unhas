from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura'

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        return redirect(url_for('booking_sucesso'))
    return render_template('booking.html')

@app.route('/booking_sucesso')
def booking_sucesso():
    return render_template('booking_sucesso.html')

@app.route('/comprovante')
def comprovante():
    return render_template('comprovante.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        flash('Instruções enviadas para o e-mail.', 'success')
    return render_template('recuperar_senha.html')

@app.errorhandler(500)
def internal_error(error):
    return "<h1>Erro 500: Erro interno no servidor.</h1><p>Verifique o terminal para mais detalhes do erro.</p>", 500

@app.errorhandler(404)
def not_found_error(error):
    return "<h1>Erro 404: Página não encontrada.</h1>", 404

if __name__ == '__main__':
    app.run(debug=True)
