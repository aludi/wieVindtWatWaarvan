from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
	username = StringField('Username', validators=[DataRequired()])
	password = PasswordField('Password', validators=[DataRequired()])
	remember_me = BooleanField('Remember Me')
	submit = SubmitField('Sign In')
 
class textInputForm(FlaskForm):
    corpus_words = TextAreaField("Onderwerpen", validators=[Length(min=0, max=140)])
    topic_words = TextAreaField("Sub-onderwerpen", validators=[Length(min=0, max=140)])
    max_val = IntegerField("Hoeveelheid berichten (x100)")
    submit = SubmitField("Go")

class download_as_csv(FlaskForm):
    submit = SubmitField("Download")
