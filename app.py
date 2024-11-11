from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import pyodbc
from config import DSN_NAME, DB_USER, DB_PASSWORD, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY



