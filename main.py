import os
import io
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, current_app, abort, flash
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from functools import wraps
from hashlib import md5
import smtplib
from email.mime.text import MIMEText

from forms import PostForm, RegistrationForm, LoginForm, CommentForm, RequestResetForm, ResetPasswordForm

# initialize app
app = Flask(__name__)

# configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('SQLALCHEMY_DATABASE_URI')



# initialize class 
bootstrap = Bootstrap5(app)
ckeditor = CKEditor(app)
db = SQLAlchemy()
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

# create user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# create admin_required decorator 
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


# send email for new messages come in and for users resetting passwords
def send_email(subject, body, recipient):
    sender = os.environ.get('SENDER_EMAIL')
    password = os.environ.get('SENDER_PASSWORD')

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender, password)
    server.sendmail(sender, [recipient], msg.as_string())
    server.quit()

# create database tables
with app.app_context():
    db.create_all()


# adding profiles images
# current version of flask_gravatar is not compatible with current version of Flask, found substitute solution on Github.
# below function is taken from https://github.com/zzzsochi/Flask-Gravatar/issues/31#issuecomment-1818098438, created by user animitchel.
def gravatar_url(email, size=100, rating='g', default='retro', force_default=False):
    hash_value = md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_value}?s={size}&d={default}&r={rating}&f={force_default}"



# *******************DATABASE********************
# create users table 
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # admin flag
    # relationships with other tables
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

    # functions for user to reset password
    
    def get_reset_token(self, expire_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')

    
    @staticmethod
    def verify_reset_token(token, expire_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expire_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)


# create posts table
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250))
    # relationships with other tables
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")

# create comments table
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    # relationships with other tables
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    parent_post = relationship("Post", back_populates="comments")
    
# creat databse
with app.app_context():
    db.create_all()




# **********************************
# home, about and contact routes
@app.route("/")
def home():
    with open('text/home.txt', 'r') as f:
        lines = f.readlines()   
    return render_template("home.html", lines=lines)

@app.route("/about")
def about():
    with open('text/about.txt', 'r') as f:
        lines = f.readlines()
    return render_template("about.html", lines=lines)

@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        subject = f"New Message from {name}"
        body = f"Email: {email}\nMessage: {message}"
        email_recipient = os.environ.get('RECIPIENT_EMAIL')
        try:
            send_email(subject, body, email_recipient)
            flash('Message sent out successfully, thanks for reaching out!','success')
        except:
            flash('There was an error sending your message.', 'danger')
        finally:
            return redirect(url_for('contact'))
    return render_template('contact.html')



# routes about post
@app.route("/posts")
def get_all_posts():
    page_index = request.args.get('page',1, type=int)
    all_posts = Post.query.order_by(Post.date.desc()).paginate(page=page_index, per_page=5)
    return render_template("all_posts.html", all_posts=all_posts)

@app.route("/post/<int:post_id>", methods=['POST', 'GET'])
def get_post(post_id):
    form = CommentForm()
    post = Post.query.get_or_404(post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('You need to log in or register to comment.', 'danger')
            return redirect(url_for('get_post', post_id=post_id)+ '#comment-box')
        else:
            new_comment = Comment(
                body = form.comment.data,
                comment_author = current_user,
                parent_post = post
            )
            db.session.add(new_comment)
            db.session.commit()
            flash('Thanks for your comment!', 'success')
            return redirect(url_for('get_post', post_id=post_id)+ '#comment-box')
    return render_template("post.html", post=post, form=form, gravatar_url=gravatar_url)

@app.route('/new-post', methods=['POST', 'GET'])
@admin_required
def create_new_post():
    form = PostForm()
    if form.validate_on_submit():
        new_post = Post(
            title = form.title.data,
            author = current_user,
            img_url = form.img_url.data,
            body = form.body.data
        )
        db.session.add(new_post)
        db.session.commit()
        flash('Your post has been created!','success')
        return redirect(url_for('get_all_posts'))
    return render_template('edit.html', form=form, is_edit=False)

@app.route('/edit-post/<int:post_id>', methods=['POST', 'GET'])
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    form = PostForm(
        title = post.title,
        img_url = post.img_url,
        body = post.body
    )
    if form.validate_on_submit():
        post.title = form.title.data
        post.img_url = form.img_url.data
        post.body = form.body.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('get_post', post_id=post.id)+ '#comment-box')
    return render_template('edit.html', form=form, is_edit=True)

@app.route('/delete/<int:post_id>')
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('get_all_posts'))



# routes about user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('You have signed up with this email, please log in instead.', 'danger')
            return redirect(url_for('login'))
        else:
            hash_and_salted_pw = generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=8
            )
            new_user = User(
                username = form.username.data,
                email = form.email.data,
                password = hash_and_salted_pw
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('You have successfully registered. Welcome!','success')
            return redirect(url_for('get_all_posts'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash('This email does not exist, please register first.', 'danger')
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, form.password.data):
            flash('Password incorrect, please try again', 'danger')
            return redirect(url_for('login'))
        else:
            login_user(user)
            flash('You have successfully logged in','success')
            return redirect(url_for('get_all_posts'))
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    flash('You have successfully logged out','success')
    return redirect(url_for('get_all_posts'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        token = user.get_reset_token()
        name = user.username
        email_recipient = user.email
        subject = f"Reset password for {name}"
        body = f'''To reset your password, please click the following link:
{url_for('reset_token', token=token, _external=True)}

If you didn't make this request then simply ignore this email and no changes will be made.
'''
        try:
            send_email(subject, body, email_recipient)
            flash('An email has been sent with instructions to reset your password', 'info')
        except:
            flash('There was an error sending your message, please try again.', 'danger')
        finally:
            return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('Expired or invalid token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hash_and_salted_pw = generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=8
            )
        user.password = hash_and_salted_pw
        try:
            db.session.commit()
            flash('Your password has been updated!', 'success')
        except:
            flash('Sorry! Password reset failed.', 'danger')
        finally:
            return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

def get_static_file(path):
    site_root = os.path.realpath(os.path.dirname(__file__))
    return os.path.join(site_root, path)

def get_static_json(path):
    return json.load(open(get_static_file(path)))

def order_projects_by_weight(projects):
    try:
        return int(projects['weight'])
    except KeyError:
        return 0

@app.route('/projects')
def get_projects():
    data = get_static_json("static/projects/projects.json")['projects']
    data.sort(key=order_projects_by_weight, reverse=True)

    tag = request.args.get('tags')
    if tag is not None:
        data = [project for project in data if tag.lower() in [project_tag.lower() for project_tag in project['tags']]]

    return render_template('projects.html', projects=data, tag=tag)

@app.route('/projects/<title>')
def project(title):
    projects = get_static_json("static/projects/projects.json")['projects']

    in_project = next((p for p in projects if p['link'] == title), None)

    if in_project is None:
        return render_template('404.html'), 404
    else:
        selected = in_project

    # load html if the json file doesn't contain a description
    if 'description' not in selected:
        path = "projects"
        selected['description'] = io.open(get_static_file(
            'static/%s/%s/%s.html' % (path, selected['link'], selected['link'])), "r", encoding="utf-8").read()
    return render_template('project.html', project=selected)


if __name__ == '__main__':
    app.run(debug=True)
