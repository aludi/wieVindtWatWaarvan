from app import app
import time
from flask import render_template, flash, redirect, url_for, send_file, Response
import random as random
from app.hard_work import Hard_Work
from app.forms import LoginForm, textInputForm, download_as_csv
from app.models import Words, Sents
from app import db
import csv




def getPosts():
    colors = ["tomato", "orange","slateblue", "powderblue", "darkturquoise", "coral", "indianred", "steelblue"]

    posts = [
    {
        'author':'huib',
        'book': 'het is oorlog maar niemand die het ziet',
        'rating':'3.5/5',
        'color': colors[random.randint(1,len(colors)-1)]
    },
    {
        'author':'nick',
        'book':'superintelligence',
        'rating':'4/5',
        'color': colors[random.randint(1,len(colors)-1)]
    },
    {
        'author':'max',
        'book':'life 3.0',
        'rating':'incomplete',
        'color': colors[random.randint(0,len(colors)-1)]
    
    }
    ]
    random.shuffle(posts)
    return posts
    
@app.route('/', methods = ['GET', 'POST'])
@app.route('/index', methods = ['GET', 'POST'])
def index():
    for searchPairs in Words().query.all():
        db.session.delete(searchPairs)
    for sents_on_ents in Sents().query.all():
        db.session.delete(sents_on_ents)
    db.session.commit()
    user = "friend"
    posts = getPosts()
    form = textInputForm()
    if form.validate_on_submit():
        flash('running code')
        words = Words(corpus_words_raw=form.corpus_words.data, topic_words_raw=form.topic_words.data, max_texts=form.max_val.data)
        db.session.add(words)
        db.session.commit()
        return redirect(url_for("outcome"))
    return render_template('index.html', title='run', form=form, user=user, posts=posts)

    
    
@app.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        flash('Login for user {}, remember_me={}'.format(form.username.data, form.remember_me.data))
        return redirect(url_for("index"))
    return render_template('login.html', title='Sign In', form=form)
    
    
@app.route('/processing', methods = ['GET', 'POST'])
def processing():
    print(Words().query.all())
    
    #if time.time() - startTime > 2:
    return redirect(url_for('outcome'))
    #return render_template('processing.html', title='processing')

@app.route('/outcome', methods = ['POST', 'GET'])
def outcome():
    form = download_as_csv()
    if form.validate_on_submit():
        return redirect(url_for('download_data'))
    else:
        for searchPairs in Words().query.all():
            corpus, topic, poliIter =searchPairs.corpus_words_raw, searchPairs.topic_words_raw, searchPairs.max_texts
        flash("searching for topics {} in corpus {}...".format(corpus, topic))
        hardwork = Hard_Work(corpus, topic, poliIter)
        for sents_on_ents in Sents().query.all():
            flash("In article {} by {}, found sentiments polarity {} objectivity {} on entity \"{}\" through words \'{}\' ". format(sents_on_ents.title, sents_on_ents.parties, sents_on_ents.polarity, sents_on_ents.objectivity, sents_on_ents.entity, sents_on_ents.direct_words))
        print("in here")
        return render_template('outcome.html', title='Output', form=form)
            
            
@app.route('/download_data', methods = ['POST', 'GET'])
def download_data():
    def create_appended_list(direct_words):
        list_direct = direct_words.split(',')
        string_direct = ""
        for item in list_direct:
            string_direct = string_direct + item
        return string_direct
        
    def generate():
        yield ','.join(["title", "parties", "location", "date", "entity", "polarity", "objectivity", "direct_words"]) +'\n'
        for row in Sents().query.all():
            direct_words_string = create_appended_list(row.direct_words)
            yield ','.join([row.title, row.parties, row.location, row.date, row.entity, row.polarity, row.objectivity, direct_words_string])+'\n'
            
    return Response(generate(), mimetype="text/csv", headers={"Content-disposition":"attachment; filename=entitiesSentiment.csv"})

@app.route('/about')
def about():
    return render_template('about.html', title='about')
    
@app.route('/examples')
def examples():
    return render_template('examples.html', title='examples')
    
@app.route('/references')
def references():
    return render_template('references.html', title='references')
    
