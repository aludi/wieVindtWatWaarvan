import os
import sys
import json
import statistics
import string
from bs4 import BeautifulSoup
import math
import pattern.text.nl as pl # USE PATTERN NOT PATTERNLITE
import requests
import spacy
import nl_core_news_sm
try:
    from app import db
    from app.models import Sents
except ModuleNotFoundError:
    print("you are running locally and don't use a database")
    db = None
    Sents = None


nlp = nl_core_news_sm.load()

class Hard_Work():
    def __init__(self, corpus, topics, poliIter, local_call):
        self.corpus = cleanUp(corpus)
        self.topics = cleanUp(topics)
        self.collection = collectDataPoliflw(self.corpus, poliIter)
        self.idfDict, collection_dict = calculateIDF(self.collection, False, local_call)

        self.local_call = local_call
        mainLoop(self.collection, self.idfDict, self.topics, self.corpus, self.local_call, collection_dict)

def loadAttributes(p, count):
    party = p["parties"][0]
    try:
        location = p["location"]
    except KeyError:
        location = "Geen locatie"
    try:
        date = p["date"]
    except KeyError:
        date = "Geen datum"
    # print(date)
    text = p["description"]
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text().lower()
    #text = '''Een nieuwe kerncentrale in het dorp? Dat nooit!'''
    try:
        topic = p["topics"]
    except KeyError:
        topic = "Geen topic"
    try:
        title = p["title"]
        soup = BeautifulSoup(title, 'html.parser')
        title = soup.get_text().lower()
        title = title.replace("\t", " ")
        title = title.replace("\n", " ")
        title = title.replace(",", " ")
        title = title.replace("&nbsp ;", " ")

    except KeyError:
        title = "Geen titel"
    print(count, title, party)
    return party, location, date, text, topic, title

def cleanUp(incoming_text): #splitting into list
    cleanList = incoming_text.split(', ')
    return cleanList
    
def collectDataPoliflw(userQueryTerms, maxVal): # query from poliflw database
    collection = []
    stringJoin = "|".join(userQueryTerms)
    if maxVal > 1000 or maxVal < 0:
        maxVal = 100
    i = 0
    while i < maxVal:
        p = requests.get('https://api.poliflw.nl/v0/search', params={"query": stringJoin,
                                                                    "filter": {
                                                                        "interestingness": {
                                                                            "terms": ["hoog"]
                                                                        }
                                                                    },
                                                                     "from": i,
                                                                     "size": "100"})
        collection.append(p.json())
        i = i + 100
    return collection

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
    table = str.maketrans({ord(ch): "" for ch in string.punctuation})
    strip = [t.translate(table) for t in text]
    return strip

def getCleanDocument(text):
    text = text.replace("\n", ' ')
    text = text.replace("\r", ' ')
    text = text.replace("\t", ' ')
    text = text.replace("\xa0", ' ')
    text = text.replace("’", '')
    text = text.replace(",", ' , ')
    text = text.replace("‘", ' ')
    cleanDocument = text.lower().split(' ')
    cleanDocument = stripTextOfAllPunct(cleanDocument)
    #cleanDocument= "er zijn bakken met water aanwezig ."
    return cleanDocument

        
def calculateIDF(collection, calculate_own_idf, local_call):   # calculates IDF and loads in the documents
    idfDict = {}
    count = 0
    collection_dict = {}
    for entry in collection:
        try:
            for p in entry['item']:
                party, location, date, text, topic, title = loadAttributes(p, 0)
                cleanDocument = getCleanDocument(text)
                collection_dict[title] = (party, location, date, cleanDocument, text, topic, title)
                if calculate_own_idf:
                    bagOfWords = cleanDocument
                    idfDict = addToIDF(idfDict, bagOfWords)
                    count += 1
        except KeyError:
            pass
    if calculate_own_idf:
        for word, val in idfDict.items():
            idfDict[word] = math.log(count/float(val))
    else:
        if local_call:
            with open('idfDict.json', 'r') as fp:
                idfDict = json.load(fp)
        else:
            with open('app/idfDict.json', 'r') as fp:
                idfDict = json.load(fp)

    return idfDict, collection_dict
    
def getTFIDF(cleanSentence, idfDict):
    #print('getTFIDF')
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
        try:
            tfidf[word] = val * idfDict[word]
            if tfidf[word] > max:
                max = tfidf[word]
        except KeyError:
            print(word, "word is not in corpus, not a stopword, so just set it to val. This is not the correct way but it's fine")
            tfidf[word] = val
    
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
            relevantWords[w] = ([], [], tfidf[w])
            counter += 1
    return relevantWords

def getRelevantTerms(relevantWords, userInput, tfidf):
    relevantTermsList = userInput
    for term in relevantTermsList:
        try:
            relevantWords[term] = ([], [], tfidf[term])
        except KeyError:
            try:
                #problem 1: honden -> hond
                lemma=nlp(term)[0].lemma_
                relevantWords[lemma] = ([], [], tfidf[lemma])
            except KeyError:
                #problem 2: meerdere zoektermen (kat in hondenartikel)
                pass
    return relevantWords

def initialize_empty(item):
    relevantWords = {}
    for term in item:
        try:
            relevantWords[term] = ([], [], 0)
        except KeyError:
            try:
                # problem 1: honden -> hond
                lemma = nlp(term)[0].lemma_
                relevantWords[lemma] = ([], [], 0)
            except KeyError:
                # problem 2: meerdere zoektermen (kat in hondenartikel)
                pass
    return relevantWords



        
def not_a_filtered_expression(phrase):
    filteredList = ["huiselijk geweld", "doorgaande weg", "sociale huurwoningen", "sociale huurbouw", "publieke tribune", "hard gemaakt", "speciaal onderwijs", "provinciale staten",
                    "vinger aan de pols", "schoon genoeg"]
    if phrase in filteredList:
        return False
    else:
        return True

def run_test_set():
    print("\n\n")
    finalList = []
    testList = ["We willen duurzame stroom en warmte .", "We willen groene stroom", "Er moet een Deltawet komen voor schone energie, we hebben kernenergie helemaal niet nodig.",
                "de snelle ontwikkelingen op het gebied van duurzame energie en berichten over mogelijke gezondheidsrisico's van windmolens ",
                "deze vorm van geluid wordt onder andere veroorzaakt door windmolens en is zeer lastig te bestrijden, de bron is lastig te vinden."

                ]
    for item in testList:
        #print(item)
        relevantWords = initialize_empty(item.split(" "))
        taggedText = pl.tokenize(item)
        relevantWords = getSentiments(-1, relevantWords, taggedText)
        for key in relevantWords.keys():
            direct, context, val = relevantWords[key]
            list_polarities = []
            list_objectivities = []
            list_words = []
            for tuple in direct:
                a, b = tuple
                direction = reverse_polarity_if_needed(a, b[1], b[0])
                list_polarities.append(direction * b[1])
                list_objectivities.append(b[2])
                list_words.append(a)
            average_polarity_word = int(deal_with_empty_lists("mean", list_polarities) * 100)
            average_objectivity_word = int(deal_with_empty_lists("mean", list_objectivities) * 100)
            if len(direct) > 0:
                print("\t", key, direct, average_polarity_word, average_objectivity_word)
                finalList.append((key, average_polarity_word, average_objectivity_word))

    checkList=[("stroom", 10, 40), ("stroom", 15, 60), ("kernenergie", -12, 35)]
    '''
    i = 0
    while i < len(checkList):
        if checkList[i] == finalList[i]:
            print(i, "True")
        else:
            print(i, "False")
        i += 1

    '''

def recurse_to_find_entity(chunk, head, first_noun, second_noun, verb_count, collected_words):
    #print("\t", chunk.text, chunk.pos_, chunk.dep_, head, first_noun, second_noun)
    if (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and len(chunk.text) > 1 and first_noun != 0 and chunk.text != head:
        #print("found the second noun")
        #print(chunk.text, first_noun)
        second_noun = chunk.text
        collected_words.append(second_noun.upper())
        #print("final collected words: ", collected_words)
        return collected_words
    elif (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and first_noun == 0:
        #print("found the first noun")
        #print(chunk.text)
        first_noun = chunk.text
        collected_words.append(first_noun.upper())
        #print("collected words: ", collected_words)
        #return collected_words
        head = first_noun
        for child in chunk.children:
            if child.text not in collected_words and child.text.upper() not in collected_words:
                return recurse_to_find_entity(child, head, first_noun, second_noun, verb_count, collected_words)
        #print("end of children")
        return recurse_to_find_entity(chunk.head, head, first_noun, second_noun, verb_count, collected_words)
    else:
        #print("didn't find a noun")
        #print("look through children first")
        collected_words.append(chunk.text)
        if chunk.pos_ == "VERB":
            verb_count += 1
        if verb_count > 1:
            return collected_words
        for child in chunk.children:
            if child.text not in collected_words and child.text.upper() not in collected_words:
                return recurse_to_find_entity(child, head, first_noun, second_noun, verb_count, collected_words)
        #print("end of children")
        #print("collected words: ", collected_words)
        #print("go to head")
        if chunk.dep_ != "ROOT":
            return recurse_to_find_entity(chunk.head, head, first_noun, second_noun, verb_count, collected_words)
        else:
            return collected_words


def classify_message_status( funct, average, median, stdev):
    status = ""
    if funct == "polarity":
        if abs(median) - stdev < 0: # if you have a median of -0.3 and a std of 0.9, you have a mized story
            status = "MIXED"
        else:   # if you have a median of 0.9 and a std of 0.01, you have a uniformly positive story
            # almost no spread in the message
            status = "UNIFORM"
        if median > 0.2:
            status = status + " POSITIVE"
        elif median > 0.4:
            status = status + " VERY POSITIVE"
        elif median < -0.2:
            status = status + " NEGATIVE"
        elif median < -0.4:
            status = status + " VERY NEGATIVE"
        else:
            status = status + " NEUTRAL"
    else:
        if median < 0.2:
            status = "VERY OBJECTIVE"
        elif median < 0.4:
            status = "OBJECTIVE"
        elif median < 0.7:
            status = "SUBJECTIVE"
        elif median < 1:
            status = "VERY SUBJECTIVE"
    #print(status)
    return status


def calculate_status_of_message(max_tfidf_val, userTopics, relevantWords, title):
    average_polarity_message_list = []
    average_objectivity_message_list = []

    for entry in relevantWords.keys():
        directList, contextList, tfidfVal = relevantWords[entry]
        list_polarities, list_objectivities, list_words = get_lists(directList, tfidfVal, max_tfidf_val, userTopics, entry)
        average_polarity_message_list = average_polarity_message_list + list_polarities
        average_objectivity_message_list = average_objectivity_message_list + list_objectivities

    print(average_polarity_message_list, average_objectivity_message_list)


    # average:
    average_pol = round(deal_with_empty_lists("mean", average_polarity_message_list), 2)
    average_obj = round(deal_with_empty_lists("mean", average_objectivity_message_list), 2)

    stdev_pol = round(deal_with_empty_lists("sdev", average_polarity_message_list), 2)
    stdev_obj = round(deal_with_empty_lists("sdev", average_objectivity_message_list), 2)

    med_pol = round(deal_with_empty_lists("median", average_polarity_message_list), 2)
    med_obj = round(deal_with_empty_lists("median", average_objectivity_message_list), 2)


    print("average of article: ", average_pol, average_obj)
    print("median of article: ", med_pol, med_obj)
    print("standard dev: ", stdev_pol, stdev_obj)

    if med_pol == 0 and med_obj == 0 and stdev_pol == 0 and stdev_obj == 0:
        polarity_status = "NO SENTIMENT"
        objectivity_status = "NO SENTIMENT"
    else:
        polarity_status = classify_message_status("polarity", average_pol, med_pol, stdev_pol)
        objectivity_status = classify_message_status("objectivity", average_obj, med_obj, stdev_obj)
    return polarity_status, objectivity_status


def reverse_polarity_if_needed(list_of_string, polarity, sent):
    polarity_reversers = ["risico"]
    if "niet" in list_of_string and "niet" not in sent: # the pl tagger missed a negation
        return -1
    if polarity > 0:    # "enorm risico" is negatief
        for item in polarity_reversers:
            if item in list_of_string:
                return -1
    return 1

        
def deal_with_empty_lists(statistic, list_sentiment):
    if list_sentiment == []:
        return 0
    if statistic == "mean":
        return statistics.mean(list_sentiment)
    elif statistic == "svar":
        return statistics.variance(list_sentiment)
    elif statistic == "sdev":
        try:
            val =statistics.stdev(list_sentiment)

        except statistics.StatisticsError:
            val = 0
        return val
    elif statistic == "mode":
        try:
            return statistics.mode(list_sentiment)
        except statistics.StatisticsError:
            return deal_with_empty_lists("mean", list_sentiment)
    elif statistic == "median":
        return statistics.median(list_sentiment)

def get_lists(directList, tfidfVal, max_tfidf_val, userTopics, entry):
    list_polarities = []
    list_objectivities = []
    list_words = []

    if tfidfVal >= 0.01 or entry in userTopics:
        for tuple in directList:
            a, b = tuple
            # print("a: ",a, "b: ", b)
            direction = reverse_polarity_if_needed(a, b[1], b[0])
            if b[1] != 0:
                list_polarities.append(direction * b[1])
            list_objectivities.append(b[2])
            list_words.append(a)
        # print("\t\t", entry, list_polarities, list_objectivities, list_words)
    return list_polarities, list_objectivities, list_words


def get_values_for_row(relevantWords, text_attributes_collection, topics, corpus, local_call, max_tfidf_val):
    party, location, date, cleanDocument, text, topic, title = text_attributes_collection
    attached_count = 0
    print(max_tfidf_val)
    for entry in relevantWords.keys():
        directList, contextList, tfidfVal = relevantWords[entry]
        list_polarities, list_objectivities, list_words = get_lists(directList, tfidfVal, max_tfidf_val, topics, entry)
        average_polarity_word = int(deal_with_empty_lists("mean", list_polarities) * 100)
        average_objectivity_word = int(deal_with_empty_lists("mean", list_objectivities) * 100)
        if average_polarity_word != 0 or average_objectivity_word != 0:
            attached_count += len(list_words)
            print("\t", entry, party, average_polarity_word, average_objectivity_word, list_words, tfidfVal )
            if local_call:
                pass
            else:
                write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words)
    print("ATTACHED COUNT", attached_count)


def write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words):
            sent_entry_in_db = Sents(parties=str(party), location=str(location), date=str(date),topic=str(topics), title=str(title), corpus=str(corpus), entity=str(entry), polarity=average_polarity_word, objectivity=average_objectivity_word, direct_words=str(list_words))
            #print("adding entry", entry)
            db.session.add(sent_entry_in_db)

def attach_direct_list(relevantWords, total_list, collected_words, word, sentiment):
    if not_a_filtered_expression(" ".join(total_list)):
        lemma = nlp(word)[0].lemma_
        if lemma in relevantWords.keys():    # we want to collect the lemmas as much as possible
            directList, contextList, tfidfVal = relevantWords[lemma]
            directList.append((" ".join(collected_words), sentiment))
            #print("adding lemma: ", lemma, " for word ", word, collected_words)
        else:   # if we cannot find the lemma, we need to just add the non-lemmatized word
            try:
                directList, contextList, tfidfVal = relevantWords[word]
                directList.append((" ".join(collected_words), sentiment))
            except KeyError:
                pass
            #print("adding word: ", word, collected_words)
    return relevantWords

        
def getSentiments(max_val_tf, relevantWords, text):
    sentiment_count = 0
    for sentence in text:   #passing each sentence the number of times a sentiment has occurred. do this before.
        #print(sentence)
        sentiments_in_sentence = {}
        sentiments_in_sentence_list = []
        for sentiment in pl.sentiment(sentence).assessments:
            sentiment_words, pol, obj, x = sentiment
            #print(sentiment_words, sentiment)
            # only add sentiments with a bit of flavor
            if (abs(pol) + abs(obj) > 0.1):
                sentiments_in_sentence[" ".join(sentiment_words)] = sentiment # appending a tuple
                # assumption: if the sentiment is longer than 1 item, the head of the first item will be the second item, etc.
                sentiments_in_sentence_list.append(sentiment_words[0])
                sentiment_count += 1
        if not sentiments_in_sentence:
            pass
        else:
            i = 0
            flag = 0
            #print("before chunk", sentiments_in_sentence_list)
            for chunk in nlp(sentence):
                if chunk.text == 'niet':
                    # we found a negation
                    flag = 1
                #print(chunk.text, chunk.dep_, chunk.pos_, sentiments_in_sentence_list)
                if chunk.text in sentiments_in_sentence_list and chunk.dep_ not in ['case', 'mark', 'advcl'] and chunk.pos_ not in ["VERB"]:
                    #print(chunk.text, chunk.pos_, chunk.dep_, "in here")
                    res = [val for key, val in sentiments_in_sentence.items() if chunk.text in key]
                    #print(res)
                    tuple = res[0]
                    sent, a, b, c = tuple
                    collected_words = recurse_to_find_entity(chunk, 0, 0, 0, 0, [])
                    #print(collected_words)
                    if i == 2 and 'niet' not in sent:
                        missed_negation = ["niet"]
                    else:
                        missed_negation = [""]
                    new_collected = missed_negation + sent
                    if 'naar' not in sent:
                        word = ""
                        for item in collected_words:
                            if item.isupper():
                                word = item.lower()
                                new_collected.append(word)
                        #word = collected_words[len(collected_words) - 1]
                        #print("\t", word , new_collected, sent)
                        if word != "":
                            relevantWords = attach_direct_list(relevantWords, collected_words, new_collected, word, tuple)
                    #print(relevantWords[word])
                if flag == 1:
                    i += 1
    print("SENTIMENT COUNT: ", sentiment_count)
    return relevantWords

    
def mainLoop(collection, idfDict, topics, corpus, local_call, collection_dict):
    #print(topics, corpus, type(topics), type(corpus))
    if topics[0] != '':
        userTopics = corpus
        for item in topics:
            userTopics.append(item)
    else:
        userTopics = corpus
    count = 0
    #run_test_set()
    dict_of_status = {}
    for item in collection_dict.keys():
        (party, location, date, cleanDocument, text, topic, title) = collection_dict[item]
        print("\t", title)
        tfidf, max = getTFIDF(cleanDocument, idfDict)
        print("MAX:", max)
        entities = getEntities(cleanDocument, tfidf, max)
        # print("ENTITIES", entities)
        relevantWords = getRelevantTerms(entities, userTopics, tfidf)  # TODO: look at this
        taggedText = pl.tokenize(text)
        # print(taggedText)
        relevantWords = getSentiments(max, relevantWords, taggedText)
        #print(relevantWords)
        get_values_for_row(relevantWords, collection_dict[item], userTopics, corpus, local_call, max)
        polarity_status, objectivity_status = calculate_status_of_message(max, userTopics, relevantWords, title)
        dict_of_status[title] = (polarity_status, objectivity_status)
        #print('\n')
        #break

    if not local_call:
        sentiments = Sents.query.all()
        for x in sentiments:
            print(x.id, x.corpus, x.entity, x.polarity, x.objectivity, x.direct_words)
        db.session.commit()
    else:
        import csv
        with open('text.csv', 'w') as f:
            for key in dict_of_status.keys():
                over_pol, over_obj = dict_of_status[key]
                print(over_pol, over_obj)
                f.write("%s,%s,%s\n"%(key, over_pol, over_obj))
        print("NEW CSV")

            
            

