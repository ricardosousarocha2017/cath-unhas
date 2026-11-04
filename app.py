import os, sqlite3
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","troque-esta-chave-antes-de-publicar")
DB=os.environ.get("DATABASE_PATH","studio_nails.db")
ADMIN_USER=os.environ.get("ADMIN_USER","admin")
ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD","admin123")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', price REAL NOT NULL, duration INTEGER NOT NULL DEFAULT 60, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY, client_id INTEGER, service_id INTEGER, day TEXT NOT NULL, time TEXT NOT NULL, status TEXT DEFAULT 'Agendado', notes TEXT DEFAULT '', created TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(client_id) REFERENCES clients(id), FOREIGN KEY(service_id) REFERENCES services(id));
        CREATE TABLE IF NOT EXISTS gallery(id INTEGER PRIMARY KEY, image_url TEXT NOT NULL, caption TEXT DEFAULT '');
        """)
        if c.execute("SELECT COUNT(*) FROM services").fetchone()[0]==0:
            c.executemany("INSERT INTO services(name,description,price,duration) VALUES(?,?,?,?)",[
             ("Alongamento em gel","Alongamento com acabamento delicado",120,120),
             ("Manutenção de gel","Manutenção do alongamento",80,90),
             (" esmaltação em gel".strip(),"Esmaltação duradoura",50,60),
             ("Banho de gel","Proteção e nivelamento das unhas naturais",70,75)])
init_db()

def admin_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a,**kw)
    return wrap

@app.route("/")
def home():
    with db() as c:
        services=c.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
        gallery=c.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
    return render_template("home.html",services=services,gallery=gallery)

@app.route("/agendar",methods=["GET","POST"])
def book():
    with db() as c:
        services=c.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    if request.method=="POST":
        name=request.form.get("name","").strip()
        phone=request.form.get("phone","").strip()
        sid=request.form.get("service","")
        day=request.form.get("day","")
        time=request.form.get("time","")
        if not all([name,phone,sid,day,time]) or day<date.today().isoformat():
            flash("Confira os dados e escolha uma data válida.","error")
            return render_template("booking.html",services=services,min_day=date.today().isoformat())
        with db() as c:
            # prevent exact slot duplicate; admin can configure duration later
            occupied=c.execute("SELECT 1 FROM bookings WHERE day=? AND time=? AND status='Agendado'",(day,time)).fetchone()
            if occupied:
                flash("Esse horário já está reservado. Escolha outro.","error")
                return render_template("booking.html",services=services,min_day=date.today().isoformat())
            client=c.execute("SELECT id FROM clients WHERE phone=?",(phone,)).fetchone()
            if client: cid=client["id"]; c.execute("UPDATE clients SET name=? WHERE id=?",(name,cid))
            else: cid=c.execute("INSERT INTO clients(name,phone) VALUES(?,?)",(name,phone)).lastrowid
            c.execute("INSERT INTO bookings(client_id,service_id,day,time,notes) VALUES(?,?,?,?,?)",(cid,int(sid),day,time,request.form.get("notes","").strip()))
        flash("Solicitação de agendamento registrada! Aguarde confirmação pelo WhatsApp.","success")
        return redirect(url_for("home"))
    return render_template("booking.html",services=services,min_day=date.today().isoformat())

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        if request.form.get("username")==ADMIN_USER and check_password_hash(generate_password_hash(ADMIN_PASSWORD),request.form.get("password","")):
            session["admin"]=True; return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos.","error")
    return render_template("login.html")

@app.route("/sair")
def logout(): session.clear(); return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def dashboard():
    with db() as c:
        bookings=c.execute("""SELECT b.*,cl.name client,cl.phone,s.name service,s.price FROM bookings b
          JOIN clients cl ON cl.id=b.client_id JOIN services s ON s.id=b.service_id
          ORDER BY b.day DESC,b.time DESC LIMIT 200""").fetchall()
        total=c.execute("SELECT COUNT(*) FROM bookings WHERE status='Agendado'").fetchone()[0]
        clients=c.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        revenue=c.execute("SELECT COALESCE(SUM(s.price),0) FROM bookings b JOIN services s ON s.id=b.service_id WHERE b.status='Concluído'").fetchone()[0]
        services=c.execute("SELECT * FROM services ORDER BY id DESC").fetchall()
        gallery=c.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
    return render_template("admin.html",bookings=bookings,total=total,clients=clients,revenue=revenue,services=services,gallery=gallery)

@app.route("/admin/status/<int:bid>",methods=["POST"])
@admin_required
def status(bid):
    val=request.form.get("status")
    if val in ["Agendado","Concluído","Cancelado"]:
        with db() as c: c.execute("UPDATE bookings SET status=? WHERE id=?",(val,bid))
    return redirect(url_for("dashboard"))

@app.route("/admin/servico",methods=["POST"])
@admin_required
def service_add():
    name=request.form.get("name","").strip()
    try: price=float(request.form.get("price","")); duration=int(request.form.get("duration","60"))
    except: flash("Preço e duração devem ser numéricos.","error"); return redirect(url_for("dashboard"))
    if name and price>=0 and duration>0:
        with db() as c: c.execute("INSERT INTO services(name,description,price,duration) VALUES(?,?,?,?)",(name,request.form.get("description",""),price,duration))
        flash("Serviço cadastrado.","success")
    return redirect(url_for("dashboard"))

@app.route("/admin/servico/<int:sid>/toggle",methods=["POST"])
@admin_required
def service_toggle(sid):
    with db() as c: c.execute("UPDATE services SET active=1-active WHERE id=?",(sid,))
    return redirect(url_for("dashboard"))

@app.route("/admin/galeria",methods=["POST"])
@admin_required
def gallery_add():
    url=request.form.get("image_url","").strip()
    if url.startswith(("https://","http://")):
        with db() as c: c.execute("INSERT INTO gallery(image_url,caption) VALUES(?,?)",(url,request.form.get("caption","")))
        flash("Foto adicionada à galeria.","success")
    else: flash("Informe um link de imagem válido.","error")
    return redirect(url_for("dashboard"))

@app.route("/admin/galeria/<int:gid>/delete",methods=["POST"])
@admin_required
def gallery_delete(gid):
    with db() as c: c.execute("DELETE FROM gallery WHERE id=?",(gid,))
    return redirect(url_for("dashboard"))

@app.route("/robots.txt")
def robots(): return "User-agent: *\\nDisallow: /admin\\n",200,{"Content-Type":"text/plain"}

if __name__=="__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG","0")=="1")
