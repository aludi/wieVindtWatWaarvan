from app import app
import time
from flask import render_template, flash, redirect, url_for, send_file, Response, request
import random as random
from app.hard_work import Hard_Work
from app.forms import LoginForm, textInputForm, download_as_csv
from app.models import Words, Sents
#from app.models import Sents
from app import db


@app.route('/', methods = ['GET', 'POST'])
@app.route('/index', methods = ['GET', 'POST'])
def index():
    for searchPairs in Words().query.all():
        db.session.delete(searchPairs)
    for sents_on_ents in Sents().query.all():
        db.session.delete(sents_on_ents)
    db.session.commit()
    user = "friend"
    form = textInputForm()
    if form.validate_on_submit():
        flash('running code')
        words = Words(corpus_words_raw=form.corpus_words.data, topic_words_raw=form.topic_words.data, max_texts=form.max_val.data)
        db.session.add(words)
        db.session.commit()
        return redirect(url_for("outcome"))
    return render_template('index.html', title='run', form=form, user=user)


@app.route('/api/get_sentiment', methods=['POST', 'GET'])
def get_sentiment_document():
    if request.method == 'POST':
        json_document = request.get_json(force=True)
    hardwork = Hard_Work([], [], 0, json_document, "api")
    polarity, subjectivity = hardwork.get_polarity_and_objectivity()
    return '{} {}'.format(polarity, subjectivity)


@app.route('/api/get_sentiment_verbose', methods=['POST', 'GET'])   # this one also returns the terms and sentence fragments that led to the classification
def get_sentiment_document_verbose():
    if request.method == 'POST':
        json_document = request.get_json(force=True)
    hardwork = Hard_Work([], [], 0, json_document, "api")
    polarity, subjectivity = hardwork.get_polarity_and_objectivity()
    dict_of_entities = hardwork.get_verbose_dict()
    formatted_string_of_entities = "\n"
    for row in zip(*dict_of_entities.values()):
        formatted_string_of_entities = formatted_string_of_entities + str(row) + "\n"
    return '{} {} {}'.format(polarity, subjectivity, formatted_string_of_entities)

    
    
@app.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        flash('Login for user {}, remember_me={}'.format(form.username.data, form.remember_me.data))
        return redirect(url_for("index"))
    return render_template('login.html', title='Sign In', form=form)


@app.route('/outcome', methods = ['POST', 'GET'])
def outcome():
    form = download_as_csv()
    if form.validate_on_submit():
        return redirect(url_for('download_data'))
    else:
        for searchPairs in Words().query.all():
            corpus, topic, poliIter = searchPairs.corpus_words_raw, searchPairs.topic_words_raw, searchPairs.max_texts
        flash("searching for topics {} in corpus {}...".format(corpus, topic))
        hardwork = Hard_Work(corpus, topic, poliIter, 0, "flask")
        return render_template('outcome.html', title='Output', form=form)

@app.route('/raw_data',  methods = ['POST', 'GET'])
def raw_data():
    form = download_as_csv()
    if form.validate_on_submit():
        return redirect(url_for('download_data'))
    relevantList = []
    words = Words().query.all()
    for w in words:
        relevantList.append(w.corpus_words_raw)
        relevantList.append(w.topic_words_raw)
    print(relevantList)
    rel_items = []
    for sents_on_ents in Sents().query.all():
        if sents_on_ents.entity in relevantList:
            #flash("In article {} by {}, found sentiments polarity {} objectivity {} on entity \"{}\" through words \'{}\' ".format(
            #        sents_on_ents.title, sents_on_ents.parties, sents_on_ents.polarity, sents_on_ents.objectivity,
            #        sents_on_ents.entity, sents_on_ents.direct_words))
            rel_items.append({'title_doc': sents_on_ents.title, 'party': sents_on_ents.parties, 'polarity': sents_on_ents.polarity,
                              'objectivity': sents_on_ents.objectivity,
                              'entity': sents_on_ents.entity,
                              'words': sents_on_ents.direct_words})

    return render_template('raw_data.html', title='ruwe data', form=form, relevant_items=rel_items)

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