from functools import wraps
from flask import Flask, render_template, flash, redirect, url_for, session, logging, request, make_response
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from datetime import *

app = Flask(__name__)

# Config Mysql
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = "889095"
app.config['MYSQL_DB'] = 'postit'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
#init MySql
mysql = MySQL(app)

# Checks if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Você precisa logar primeiro', 'message')
            return redirect(url_for('login'))
    return wrap  

# Home page
@app.route('/')
def home():
    return render_template('home.html')

# About Page
@app.route('/about')
def about():
    return render_template('about.html')

# Messages Page
@app.route('/messages')
@is_logged_in
def messages():
    # Create Cursor
    cur = mysql.connection.cursor()
    # Get Messages
    result = cur.execute("SELECT * FROM messages")
    messages = cur.fetchall()
    if result > 0:
        return render_template('messages.html', messages=messages)
    else:
        flash('Nenhum recado encontrado', 'message')
        return render_template('messages.html')
    # Close Connex
    cur.close()
    
# Messages ID
@app.route('/messages/<string:id>/')
def message(id):
    # Create Cursor
    cur = mysql.connection.cursor()
    # Get Message
    result = cur.execute("SELECT * FROM messages WHERE id = %s", [id])
    message = cur.fetchone()
    if result:
        return render_template('message.html', message=message)
    else:
        flash('mensagem não encontrada', 'message')
        return render_template('message.html', message=message)
        
class RegisterForm(Form):
    name = StringField('Nome', [validators.Length(min=3, max=50)])
    username = StringField('Username', [validators.Length(min=5, max=25)])
    email = StringField('Email',[validators.Length(min=10, max=50)])
    password = PasswordField('Senha', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='As senhas não correspondem')
    ])
    confirm = PasswordField('Confirmar Senha')
       
@app.route('/register', methods=['GET'])
def register():
    form = RegisterForm(request.form)
    return render_template('register.html', form=form)
    
    

@app.route('/register', methods=['POST'])
def regpost():
    form = RegisterForm(request.form)
    if form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))      
        # Create Cursor
        cur = mysql.connection.cursor()
        usermail = cur.execute("SELECT * FROM users WHERE email LIKE %s", [email])
        nickname = cur.execute("SELECT * FROM users Where username LIKE %s", [username])
        if usermail or nickname > 0:
            flash('Usuário já cadastrado! Deseja logar?', 'message')
            return render_template('login.html', form=form)
        else:
            # Execute Query
            cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))
            # Commit to DB
            mysql.connection.commit()
            # Close Connection
            cur.close()
            flash('Cadastrado com sucesso', 'success')
            return render_template('login.html')
    else:
        flash('Dados informados inválidos', 'message')
        return render_template('register.html', form=form)
        
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']
        # Create Cursor
        cur = mysql.connection.cursor()
        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])
        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']
            register_date = data['register_date']
            userdate = register_date.strftime("%d/%m/%Y")
            # Compare Pass
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                session['register_date'] = userdate
                flash('Logado com sucesso', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Os dados informados são inválidos', 'message')
                return render_template('login.html')
            # Close Connex
            cur.close()        
        else:
            flash('Usuário não encontrado', 'message')
            return render_template('login.html')
        
    return render_template('login.html')    

# Log Out
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('Você foi deslogado', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    cur =  mysql.connection.cursor()
    # Get post its
    result = cur.execute("SELECT * FROM messages")
    messages = cur.fetchall()
    if result > 0:
        for data in messages:
            create_date = data['create_date']
            data['create_date'] = create_date.strftime("%d/%m/%Y")
        return render_template('dashboard.html', messages=messages)
    else:
        flash('Sem mensagens', 'message')
        return render_template('dashboard.html')
    
    # Close Connex
    cur.close()
    
# Post it Form Class
class MessageForm(Form):
    title = StringField('Título', [validators.Length(min=3, max=15)])
    body = TextAreaField('Mensagem', [validators.Length(min=5, max=255)])
    
# Add Post It
@app.route('/add_message', methods=['GET', 'POST'])
@is_logged_in
def add_message():
    form = MessageForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data
        # Create Cursor
        cur = mysql.connection.cursor()
        # Execute
        cur.execute("INSERT INTO messages(title, body, author) VALUES (%s, %s, %s)", (title, body, session['username']))
        # Commit to DB
        mysql.connection.commit()
        # Close Connex
        cur.close()
        flash('Mensagem Criada!', 'success')
        return redirect(url_for('dashboard'))
    else:
        return render_template('add_message.html', form=form)

# Edit Message
@app.route('/edit_message/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_message(id):
    user = session['username']
    # Create Cursor
    cur = mysql.connection.cursor()
    # Get message by ID
    result = cur.execute("SELECT * FROM messages WHERE id = %s", [id])
    message = cur.fetchone()
    if message:
        author = message['author']
    else:
        flash('Mensagem não encontrada', 'message')
        return redirect(url_for('dashboard'))
    if user == author:
        # Get Form
        form = MessageForm(request.form)
        form.title.data = message['title']
        form.body.data =  message['body']
        if request.method == 'POST' and form.validate():
            title = request.form['title']
            body = request.form['body']
            # Create Cursor
            cur = mysql.connection.cursor()
            # Execute
            cur.execute("UPDATE messages SET title = %s, body = %s WHERE id = %s", (title, body, id))
            # Commit to DB
            mysql.connection.commit()
            # Close Connection
            cur.close()
            flash('Mensagem Editada!', 'success')
            return redirect(url_for('dashboard'))
    else:
        flash('Acesso negado', 'message')
        return redirect(url_for('dashboard'))
    return render_template('edit_message.html', form=form)               

# Delete Message
@app.route('/delete_message/<string:id>', methods=['GET','POST'])
@is_logged_in
def delete_message(id):
    user = session['username']
    # Create Cursor
    cur = mysql.connection.cursor()
    # Execute
    cur.execute("SELECT * FROM messages WHERE id = %s", [id])
    message = cur.fetchone()
    if message:
        author = message['author']
    else:
        flash('Mensagem não encontrada', 'message')
        return redirect(url_for('dashboard'))
    if user == author:
        cur.execute("DELETE FROM messages WHERE id = %s", [id])
        # Commit to DB
        mysql.connection.commit()
        # Close Connection
        cur.close()
        flash('Mensagem Apagada!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Acesso negado', 'message')
        return redirect(url_for('dashboard'))
    
if __name__ == "__main__":
    app.secret_key='secret123'
    app.run(debug=True)