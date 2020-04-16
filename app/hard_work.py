import os
import sys
import json
#from termcolor import colored
import pathlib
import time
import statistics
import string
from bs4 import BeautifulSoup
import math
import csv
import pattern.text.nl as pl # USE PATTERN NOT PATTERNLITE
import requests
import spacy
from app import db
from app.models import Sents

nlp = spacy.load("nl_core_news_sm")

def loadAttributes(p):
    party = p["parties"][0]
    try:
        location = p["location"]
    except KeyError:
        location = "no location given"
    try:
        date = p["date"]
    except KeyError:
        date = "NA"
    # print(date)
    text = p["description"]
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text().lower()
    try:
        topic = p["topics"]
    except KeyError:
        topic = "No topic given"
    try:
        title = p["title"]
        soup = BeautifulSoup(title, 'html.parser')
        title = soup.get_text().lower()
        title = title.replace("\t", "")
        title = title.replace("\n", "")
        title = title.replace(",", "")
    except KeyError:
        title = "\n"
    print(title)
    return party, location, date, text, topic, title

def cleanUp(incoming_text):
    cleanList = incoming_text.split(' ')
    #print(cleanList)
    return cleanList
    
def collectDataPoliflw(userQueryTerms, maxVal):
    collection = []
    for term in userQueryTerms:
        i = 0
        if maxVal > 10:
            maxVal = 1
        while i < maxVal*100:
            p = requests.get('https://api.poliflw.nl/v0/search', params={"query" : term,
            "from": i,
            "size": "100"})
            #print(p.json())
            collection.append(p.json())
            i = i + 100
    #print(collection)
    return collection
    
def cleanText(relevantSection, arg):
    specialPunct = set(string.punctuation)
    specialPunct.add("”")
    specialPunct.add("’")
    specialPunct.add("–")
    specialPunct.add("…")
    specialPunct.add("‘")
    specialPunct.add("“")
    specialPunct.add("„")
    specialPunct.add(";")
    specialPunct.add("“")
    cleanSentence = ""
    if arg == 1:
        for letter in relevantSection:
            if letter not in specialPunct:
                if letter == "\n" or letter =="\t":
                    cleanSentence += " "
                else:
                    cleanSentence += letter
            elif letter in [":", "?", "!", ">", ".", "..."]:
                cleanSentence += " . "
    if arg == 2:
        for letter in relevantSection:
            if letter in [".", ":", "?", "!", ">"]:
                cleanSentence += " . "
            if letter not in specialPunct:
                if letter == "\n" or letter == "\t":
                    cleanSentence += " . "
                elif letter in [":", "?", "!", ">"]:
                    cleanSentence += " .  "
                elif letter != ".":
                    cleanSentence += letter
    return cleanSentence

    
def getCleanText(text):
    soup = BeautifulSoup(text, 'html.parser')
    relevantSection = soup.get_text().lower()  # prefilter for tokenizer
    cleanSentence = cleanText(relevantSection, 1)
    return cleanSentence
    
def computeFrequency(bag, num):
    frequency = {}
    denom = len(bag)
    for word, count in num.items():
        frequency[word] = count / float(denom)
    return frequency

def addToIDF(idfDict, bag):
    for word in bag:
        if word not in idfDict:
            idfDict[word] = 1
        else:
            idfDict[word] += 1
    return idfDict

def stripTextOfAllPunct(text):
    table = str.maketrans("","",string.punctuation)
    strip = [t.translate(table) for t in text]
    return strip

        
def calculateIDF(collection):
    idfDict = {}
    count = 0
    #print(collection)
    #print("\n")
    for entry in collection:
        try:
            #print(entry)
            #print(entry['item'])
            for p in entry['item']:
                party, location, date, text, topic, title = loadAttributes(p)
                '''
                text = "ik geef hem de mooie sigaren. Ik geef de mooie sigaren aan hem. De mooie sigaren zijn van hem. Hij is mooi, De man is mooi. De man is niet mooi. De man is lelijk. De lelijke man rookt de mooie sigaren."
                '''
                cleanDocument = text.lower().split(' ')
                cleanDocument = stripTextOfAllPunct(cleanDocument)
                #print(cleanDocument)
                bagOfWords = cleanDocument
                idfDict = addToIDF(idfDict, bagOfWords)
                count += 1
        except KeyError:
            pass


            
    for word, val in idfDict.items():
        idfDict[word] = math.log(count/float(val))
    return idfDict
    
def getTFIDF(cleanSentence, idfDict):
    
    #print(idfDict)
    bagOfWords = cleanSentence
    #print(bagOfWords)
    numWords = dict.fromkeys(bagOfWords, 0)
    for word in bagOfWords:
        numWords[word] += 1
    frequencyWordsInDoc = computeFrequency(bagOfWords, numWords)
    tfidf = {}
    max = -10
    for word, val in frequencyWordsInDoc.items():
        tfidf[word] = val * idfDict[word]
        if tfidf[word] > max:
            max = tfidf[word]
    
    return tfidf, max
    
def getEntities(cleanSentence, tfidf, max):
    relevantWords = {}
    counter = 0
    x = pl.sentiment(cleanSentence).assessments
    listSent = []
    for x1 in x:
        w, a, b, c = x1
        for p in w:
            listSent.append(p)
    for w in sorted(tfidf, key=tfidf.get, reverse=True):
        if w not in listSent and len(w) > 2 and len(w) < 25:
            relevantWords[w] = ([], [])
            counter += 1
        if tfidf[w] < 2*(max/3):
            break
    return relevantWords

def getRelevantTerms(relevantWords, userInput):
    relevantTermsList = userInput
    for term in relevantTermsList:
        relevantWords[term] = ([], [])
    return relevantWords
    
def add_singular_topics(topics_plural):
    newList= []
    for items in topics_plural:
        newList.append(items)
        newList.append(pl.singularize(items))
    return newList

class Hard_Work():
    def __init__(self, corpus, topics, poliIter):
        self.corpus = cleanUp(corpus)
        topics_plural = cleanUp(topics)
        self.topics = add_singular_topics(topics_plural)
        self.collection = collectDataPoliflw(self.corpus, poliIter)
        self.idfDict = calculateIDF(self.collection)
        mainLoop(self.collection, self.idfDict, self.topics, self.corpus)
        
def not_a_filtered_expression(phrase):
    filteredList = ["huiselijk geweld", "doorgaande weg", "sociale huurwoningen", "sociale huurbouw", "publieke tribune", "hard gemaakt", "speciaal onderwijs", "provinciale staten"]
    if phrase in filteredList:
        return False
    else:
        return True
        
def recurse_to_find_entity(relevantWords, chunk, attachment_strength):
    #print(relevantWords.keys())
    #print(chunk.text, chunk.dep_, chunk.pos_)
    if chunk.text in relevantWords.keys():
        return chunk.text, attachment_strength
    elif chunk.dep_ == "ROOT":
        for child in chunk.children:
            if child.text in relevantWords.keys():  # dealing with "hij is blij"
                return child.text, attachment_strength/2
        return "", 0
    else:
        return recurse_to_find_entity(relevantWords, chunk.head, attachment_strength / 2)
        
        
def deal_with_empty_lists(list_sentiment):
    if list_sentiment == []:
        return 0
    else:
        return statistics.mean(list_sentiment)

def write_to_db(relevantWords, text_attributes, topics, corpus):
    party, location, date, text, topic_tag, title = text_attributes
    for entry in relevantWords.keys():
        directList, contextList = relevantWords[entry]
        list_polarities = []
        list_objectivities = []
        list_words = []
        for tuple in directList:
            a, b = tuple
            list_polarities.append(b[1])
            list_objectivities.append(b[2])
            list_words.append(b[0])
        #print("\t\t", entry, list_polarities, list_objectivities, list_words)
        average_polarity_word = int(deal_with_empty_lists(list_polarities)*100)
        average_objectivity_word = int(deal_with_empty_lists(list_objectivities)*100)
        if average_polarity_word != 0 and average_objectivity_word != 0:
            print("\t", entry, party, average_polarity_word, average_objectivity_word)
            sent_entry_in_db = Sents(parties=str(party), location=str(location), date=str(date),topic=str(topics), title=str(title), corpus=str(corpus), entity=str(entry), polarity=average_polarity_word, objectivity=average_objectivity_word, direct_words=str(list_words))
            #print("adding entry", entry)
            db.session.add(sent_entry_in_db)
        
def do_nlp_recursion(sentiment, sentiment_words, relevantWords, sentence):
    for chunk in nlp(sentence):
        if chunk.text in sentiment_words and chunk.dep_ not in ['advmod', 'case', 'mark', 'advcl',
        "obl"]:
            word, attachment_strength = recurse_to_find_entity(relevantWords, chunk, 2)
            if attachment_strength > 0.3:
                direct_attachment_text = " ".join(sentiment_words) + " " + word
                if not_a_filtered_expression(direct_attachment_text):
                    directList, contextList = relevantWords[word]
                    directList.append((direct_attachment_text, sentiment))
                    break
    return relevantWords
        
def getSentiments(relevantWords, text):
    for sentence in text:
        entitiesFound = []
        for sentiment in pl.sentiment(sentence).assessments:
            sentiment_words, pol, obj, x = sentiment
            if sentiment_words is ['naar']:       # contains?
                break
            #print(sentiment_words)
            relevantWords = do_nlp_recursion(sentiment, sentiment_words, relevantWords, sentence)
    return relevantWords

    
def mainLoop(collection, idfDict, topics, corpus):
    print(topics, corpus, type(topics), type(corpus))
    if topics[0] != '':
        userTopics = corpus
        for item in topics:
            userTopics.append(item)
    else:
        userTopics = corpus
        
    #print("COLLECTION: ")
    #print(collection)
    #print("\n")
        
    for item in collection:
        try:
            for p in item['item']:
                #print("in P")
                text_attributes = loadAttributes(p)
                party, location, date, text, topic, title = text_attributes
                '''
                text = "ik geef hem de mooie sigaren. Ik geef de mooie sigaren aan hem. De mooie sigaren zijn van hem. Hij is mooi. De man is mooi. De man is niet mooi. De man is lelijk. De lelijke man rookt de mooie sigaren."
                '''
                
                
                cleanDocument = text.lower().split(' ')
                cleanDocument = stripTextOfAllPunct(cleanDocument)
               
                #print(cleanDocument)
                tfidf, max = getTFIDF(cleanDocument, idfDict)
                #print("TFODF:", tfidf, max)
                entities = getEntities(cleanDocument, tfidf, max)
                #print("ENTITIES", entities)
                relevantWords = getRelevantTerms(entities, userTopics)
                taggedText = pl.tokenize(text)
                #print(taggedText)
                relevantWords = getSentiments(relevantWords, taggedText)
                #print(relevantWords)
                write_to_db(relevantWords, text_attributes, topics, corpus)
        except KeyError:
            pass
        
    sentiments = Sents.query.all()
    for x in sentiments:
        print(x.id, x.corpus, x.entity, x.polarity, x.objectivity, x.direct_words)
    db.session.commit()
            
            
            

