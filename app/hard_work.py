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
    #text = '''Onder het motto: "Ook dit is kernenergie" geeft het A2-affiche een aantal redenen waarom kernenergie niet die veilige, schone energievorm is die ons onafhankelijker maakt van invoer van bijv. olie . '''
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

def cleanUp(incoming_text):
    cleanList = incoming_text.split(', ')
    #print(cleanList)
    return cleanList
    
def collectDataPoliflw(userQueryTerms, maxVal):
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
        #print(p.json())
        collection.append(p.json())

        i = i + 100
    '''
    for term in userQueryTerms:
        i = 0
        if maxVal > 10:
            maxVal = 1
    '''
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
    table = str.maketrans("","",string.punctuation)
    strip = [t.translate(table) for t in text]
    return strip

def getCleanDocument(text):
    text = text.replace("\n", ' ')
    text = text.replace("\r", ' ')
    text = text.replace("\t", ' ')
    text = text.replace("\xa0", ' ')
    text = text.replace("’", '')
    text = text.replace(",", ' , ')
    cleanDocument = text.lower().split(' ')
    cleanDocument = stripTextOfAllPunct(cleanDocument)
    #cleanDocument= "er zijn bakken met water aanwezig ."
    return cleanDocument

        
def calculateIDF(collection):
    idfDict = {}
    count = 0
    #print(collection)
    #print("\n")
    collection_dict = {}
    for entry in collection:
        try:
            #print(entry)
            #print(entry['item'])
            for p in entry['item']:
                party, location, date, text, topic, title = loadAttributes(p, 0)
                cleanDocument = getCleanDocument(text)
                #print(cleanDocument)
                collection_dict[title] = (party, location, date, cleanDocument, text, topic, title)
                bagOfWords = cleanDocument
                idfDict = addToIDF(idfDict, bagOfWords)
                count += 1
        except KeyError:
            pass
    for word, val in idfDict.items():
        idfDict[word] = math.log(count/float(val))
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
            relevantWords[w] = ([], [], tfidf[w])
            counter += 1
        #if tfidf[w] < 2*(max/3):
            #pass
            #break
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

    


class Hard_Work():
    def __init__(self, corpus, topics, poliIter, local_call):
        self.corpus = cleanUp(corpus)
        self.topics = cleanUp(topics)
        self.collection = collectDataPoliflw(self.corpus, poliIter)
        self.idfDict, collection_dict = calculateIDF(self.collection)
        self.local_call = local_call
        mainLoop(self.collection, self.idfDict, self.topics, self.corpus, self.local_call, collection_dict)
        
def not_a_filtered_expression(phrase):
    filteredList = ["huiselijk geweld", "doorgaande weg", "sociale huurwoningen", "sociale huurbouw", "publieke tribune", "hard gemaakt", "speciaal onderwijs", "provinciale staten",
                    "vinger aan de pols", "schoon genoeg"]
    if phrase in filteredList:
        return False
    else:
        return True

#def recurse_to_find_entity(max_val_tf, relevantWords, chunk, collected_words, attachment_strength, userTopics):
    '''
    if chunk.text in relevantWords.keys():
        print("\t", chunk.text, relevantWords[chunk.text][2])

    print("\t", chunk.text, chunk.head, chunk.dep_, chunk.pos_, chunk.lemma_, userTopics)
    print("\t", collected_words)
    print("\n\n")
    print(chunk.lemma_ in userTopics, chunk.text in userTopics)
    '''

    #if attachment_strength < 0.10:
    #    return chunk.text, collected_words, attachment_strength
    '''
    if chunk.pos_ == "NOUN" and userTopics != 0:
        userTopics = chunk.head.text
        return recurse_to_find_entity(max_val_tf, relevantWords, chunk.head, collected_words, attachment_strength/2, userTopics)

    if chunk.pos_ != "NOUN" and userTopics == 0:
        # go for nearest noun
        collected_words.append(chunk.text)
        return recurse_to_find_entity(max_val_tf, relevantWords, chunk.head, collected_words, attachment_strength / 2,
                                      userTopics)

    if chunk.pos_ != "NOUN" and userTopics != 0:
        # you already found the nearest head, so find the children

        collected_words.append(chunk.text)
        return recurse_to_find_entity(max_val_tf, relevantWords, chunk.head, collected_words, attachment_strength / 2,
                                      userTopics)
    '''

    '''

    if chunk.pos_ not in ["VERB", "CONJ"] and chunk.dep_ not in ["advmod", "xcomp"]:
        collected_words.append(chunk.text)

    if (chunk.text in relevantWords.keys() and relevantWords[chunk.text][2] >= max_val_tf/2) or (chunk.lemma_ in userTopics) or (chunk.text in userTopics):
        return chunk.text, collected_words, attachment_strength
    elif chunk.dep_ == "ROOT":
        for child in chunk.children:
            if (child.text in relevantWords.keys() and relevantWords[child.text][2] > max_val_tf/2) or child.text in userTopics:  # dealing with "hij is blij"   #TODO: adjust to num items in document maybe?
                collected_words.append(child.text)
                return child.text, collected_words, attachment_strength/2
        return "", [], 0
    else:

        return recurse_to_find_entity(max_val_tf, relevantWords, chunk.head, collected_words, attachment_strength / 2, userTopics)
    '''

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

    checkList=[("stroom", 10, 40), ("stroom", 15, 60), ("kernenergie", -12, 35),
               ]
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





    '''
    if (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and first_noun == 0:
        print("you found the first noun!")
        collected_words.append(chunk.text)
        first_noun = chunk.text
        head = chunk
        # two options, either you look for the second noun in the children, or you look for it in the head
        #for child in chunk.children:
        #    return recurse_to_find_entity(child, head, first_noun, collected_words)
        #print("first noun has no children")
        #return recurse_to_find_entity(chunk.head, head, first_noun, collected_words)

    if (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and first_noun != 0:
        print("you found the second noun!, we're done!")
        print(chunk.text, first_noun)
        collected_words.append(chunk.text)
        return collected_words

    if chunk.pos_ != "NOUN" and first_noun == 0:
        collected_words.append(chunk.text)
        print("you start here, most likely, with the sentiment")

        return recurse_to_find_entity(chunk.head, head, first_noun, collected_words)
        #for child in chunk.children:
        #    if child.text not in collected_words:
        #        return recurse_to_find_entity(child, head, first_noun, collected_words)
        #return recurse_to_find_entity(chunk.head, head, first_noun, collected_words)
        #return collected_words

    if chunk.pos_ != "NOUN" and first_noun != 0:
        print("you have found the first noun and are looking for the second one")
        #for child in chunk.children:
        #    return recurse_to_find_entity(child, head, first_noun, collected_words)
        #print("no children")
        #return collected_words

        #print("you haven't found a second noun. returning...")
        #print(collected_words)
        #return collected_words
    '''





    '''
    if chunk.pos_ == "NOUN" and head == 0:
        print("situation 1")
        collected_words.append(chunk.text)
        if chunk.head.dep_ == "ROOT" or chunk.head.pos_ == "VERB":
            head = chunk.head.text
        first_noun = chunk.text
        for child in chunk.children:    # two nouns under the same head
            if (child.pos_ == "NOUN" or child.dep_ == "nsubj") and child.text != first_noun:
                collected_words.append(child.text)
                #print(child.text, child.pos_, child.dep_)
                return collected_words
            return collected_words
        return recurse_to_find_entity(chunk.head, head, first_noun, collected_words)

    if chunk.pos_ != "NOUN":
        print("situation 2")
        # you already found the nearest head, so find the children
        for child in chunk.children:
            #print("find the noun in the children")
            #print(child.text)
            if (child.pos_ == "NOUN" or (child.dep_ == "nsubj" and child.pos_!= "PRON")) and (child.text != first_noun and first_noun != 0):
                #print(child.text, child.pos_, child.dep_)
                collected_words.append(child.text)
                return collected_words

        if chunk.dep_ == "ROOT" or chunk.text == head:
            #print("find the noun near the root")
            collected_words.append(chunk.text)
            for child in chunk.children:
                #print(child.text)
                if (child.pos_ == "NOUN" or child.dep_ == "nsubj") and (child.text != first_noun and first_noun !=0):
                    #print(child.text, child.pos_, child.dep_)
                    collected_words.append(child.text)
                    return collected_words
            return collected_words
        else:
            return recurse_to_find_entity(chunk.head, head, first_noun, collected_words)
    '''

def classify_message_status( funct, ratio, average, median, stdev):
    status = ""
    if funct == "polarity":
        if abs(median) - stdev < 0: # if you have a median of -0.3 and a std of 0.9, you have a mized story
            #print("MIXED")
            status = "MIXED"
        else:   # if you have a median of 0.9 and a std of 0.01, you have a uniformly positive story
            # almost no spread in the message
            #print("UNIFORMLY")
            status = "UNIFORM"
        if median > 0.2:
            #print("POSITIVE")
            status = status + " POSITIVE"
        elif median > 0.4:
            #print("VERY POSITIVE")
            status = status + " VERY POSITIVE"
        elif median < -0.2:
            #print("NEGATIVE")
            status = status + " NEGATIVE"
        elif median < -0.4:
            #print("VERY NEGATIVE")
            status = status + " VERY NEGATIVE"
        else:
            #print("NEUTRAL")
            status = status + " NEUTRAL"
    else:
        if median < 0.2:
            #print("VERY OBJECTIVE")
            status = "VERY OBJECTIVE"
        elif median < 0.4:
            #print("OBJECTIVE")
            status = "OBJECTIVE"
        elif median < 0.7:
            #print("SUBJECTIVE")
            status = "SUBJECTIVE"
        elif median < 1:
            #print("VERY SUBJECTIVE")
            status = "VERY SUBJECTIVE"
    print(status)
    return status


def calculate_status_of_message(max_tfidf_val, userTopics, relevantWords, title):
    dict_of_items = {"positive":0, "negative":0, "objective": 0, "subjective":0, "av_pol":[], "av_obj":[], "total":0}
    for entry in relevantWords.keys():
        directList, contextList, tfidfVal = relevantWords[entry]
        list_polarities = []
        list_objectivities = []
        list_words = []
        if tfidfVal > max_tfidf_val/4 or entry in userTopics:
            for tuple in directList:
                a, b = tuple
                direction = reverse_polarity_if_needed(a, b[1], b[0])
                pol_word = direction*b[1]
                obj_word = b[2]
                if pol_word > 0.0:
                    dict_of_items["positive"] += 1
                elif pol_word < 0.0:
                    dict_of_items["negative"] += 1
                if pol_word != 0:
                    dict_of_items["av_pol"].append(pol_word)
                if obj_word < 0.5:
                    dict_of_items["objective"] += 1
                else:
                    dict_of_items["subjective"] += 1
                dict_of_items["av_obj"].append(obj_word)
                dict_of_items["total"] += 1
    print(dict_of_items["av_pol"])

    # average:
    average_pol = round(deal_with_empty_lists("mean", dict_of_items["av_pol"]), 2)
    average_obj= round(deal_with_empty_lists("mean", dict_of_items["av_obj"]), 2)

    stdev_pol = round(deal_with_empty_lists("sdev", dict_of_items["av_pol"]), 2)
    stdev_obj= round(deal_with_empty_lists("sdev", dict_of_items["av_obj"]), 2)

    mode_pol = round(deal_with_empty_lists("mode", dict_of_items["av_pol"]), 2)
    mode_obj = round(deal_with_empty_lists("mode", dict_of_items["av_obj"]), 2)

    med_pol = round(deal_with_empty_lists("median", dict_of_items["av_pol"]), 2)
    med_obj = round(deal_with_empty_lists("median", dict_of_items["av_obj"]), 2)

    #ratio
    if dict_of_items["total"] > 0:
        ratio_pol_pos = round(dict_of_items["positive"] / dict_of_items["total"], 2)
        ratio_obj = round(dict_of_items["objective"] / dict_of_items["total"], 2)
    else:
        ratio_pol_pos = 0
        ratio_obj = 0


    print("average of article: ", average_pol, average_obj)
    print("median of article: ", med_pol, med_obj)
    print("standard dev: ", stdev_pol, stdev_obj)
    print("ratio of article: ", ratio_pol_pos, ratio_obj, "out of a total: ", dict_of_items["total"])
    if med_pol == 0 and med_obj == 0 and stdev_pol == 0 and stdev_obj == 0:
        polarity_status = "NO SENTIMENT"
        objectivity_status = "NO SENTIMENT"
    else:
        polarity_status = classify_message_status("polarity", ratio_pol_pos, average_pol, med_pol, stdev_pol)
        objectivity_status = classify_message_status("objectivity", ratio_obj, average_obj, med_obj, stdev_obj)

    return polarity_status, objectivity_status


def reverse_polarity_if_needed(list_of_string, polarity, sent):
    polarity_reversers = ["risico"]
    #print(list_of_string)

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

def get_values_for_row(relevantWords, text_attributes_collection, topics, corpus, local_call, max_tfidf_val):
    party, location, date, cleanDocument, text, topic, title = text_attributes_collection
    attached_count = 0
    for entry in relevantWords.keys():
        average_polarity_word = 0
        average_objectivity_word = 0
        #print(entry, relevantWords[entry])
        directList, contextList, tfidfVal = relevantWords[entry]
        list_polarities = []
        list_objectivities = []
        list_words = []
        if tfidfVal > max_tfidf_val / 4 or entry in topics:
            for tuple in directList:
                a, b = tuple
                #print("a: ",a, "b: ", b)
                direction = reverse_polarity_if_needed(a, b[1], b[0])
                if b[1] != 0:
                    list_polarities.append(direction*b[1])
                list_objectivities.append(b[2])
                list_words.append(a)
            # print("\t\t", entry, list_polarities, list_objectivities, list_words)
            average_polarity_word = int(deal_with_empty_lists("mean", list_polarities) * 100)
            average_objectivity_word = int(deal_with_empty_lists("mean", list_objectivities) * 100)

        if average_polarity_word != 0 or average_objectivity_word != 0:
            attached_count += len(list_words)
            print("\t", entry, party, average_polarity_word, average_objectivity_word, list_words, tfidfVal)
            if local_call:
                pass
            else:
                write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words)
    print("ATTACHED COUNT", attached_count)



def write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words):
            sent_entry_in_db = Sents(parties=str(party), location=str(location), date=str(date),topic=str(topics), title=str(title), corpus=str(corpus), entity=str(entry), polarity=average_polarity_word, objectivity=average_objectivity_word, direct_words=str(list_words))
            #print("adding entry", entry)
            db.session.add(sent_entry_in_db)
        
def do_nlp_recursion(sentiment, sentiment_words, relevantWords, sentence, userTopics):
    #print(sentence)
    for chunk in nlp(sentence):
        if chunk.text in sentiment_words and chunk.dep_ not in ['advmod', 'case', 'mark', 'advcl',
        "obl"]:
            word, collected_words, attachment_strength = recurse_to_find_entity(relevantWords, chunk, [], 2, 0)
            #print(chunk, word, collected_words, attachment_strength)
            if attachment_strength > 0.10:
                if len(collected_words) > 1:
                    collected_words.pop(0)
                collected_words = sentiment_words+collected_words
                if not_a_filtered_expression(" ".join(collected_words)):
                    # take care of lemma
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
                    break
    return relevantWords

def attach_direct_list(relevantWords, attachment_strength, total_list, collected_words, word, sentiment):
    if word is not "":
        #if len(collected_words) > 1:
        #    collected_words.pop(0)

        if not_a_filtered_expression(" ".join(total_list)):
            # take care of lemma
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
                    #word, collected_words, attachment_strength = recurse_to_find_entity(max_val_tf, relevantWords, chunk, [], 2, 0)
                    collected_words = recurse_to_find_entity(chunk, 0, 0, 0, 0, [])
                    #print(collected_words)

                    if i == 2 and 'niet' not in sent:
                        missed_negation = ["niet"]
                    else:
                        missed_negation= [""]

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
                            relevantWords = attach_direct_list(relevantWords, 0, collected_words, new_collected, word, tuple)

                    #print(relevantWords[word])
                if flag == 1:
                    i += 1

            '''
            for chunk in nlp(sentence):
            #print(sentence)
            entitiesFound = []
            for sentiment in pl.sentiment(sentence).assessments:
                sentiment_words, pol, obj, x = sentiment
                print(sentiment_words)
                if sentiment_words is ['naar']:       # contains?
                    break
                #print(sentiment_count, sentiment_words)
                sentiment_count += 1
                relevantWords = do_nlp_recursion(sentiment, sentiment_words, relevantWords, sentence, userTopics)
            '''
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
        
    #print("COLLECTION: ")
    #print(collection)
    #print("\n")
    count = 0

    #run_test_set()

    dict_of_status = {}

    for item in collection_dict.keys():
        (party, location, date, cleanDocument, text, topic, title) = collection_dict[item]
        print("\t", title)
        tfidf, max = getTFIDF(cleanDocument, idfDict)
        #print("MAX:", max)
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
        #break
        print('\n')
        #get_values_for_row(relevantWords, collection_dict[item], topics, corpus, local_call)

    '''
    for item in collection:
        #try:
        for p in item['item']:
            #print("in P")
            text_attributes = loadAttributes(p, count)
            party, location, date, text, topic, title = text_attributes
            count += 1
       
            cleanDocument = getCleanDocument(text)
            #print(cleanDocument)
            tfidf, max = getTFIDF(cleanDocument, idfDict)
            #print("TFODF:", tfidf, max)
            entities = getEntities(cleanDocument, tfidf, max)
            #print("ENTITIES", entities)
            relevantWords = getRelevantTerms(entities, userTopics, tfidf)      # TODO: look at this
            taggedText = pl.tokenize(text)
            #print(taggedText)
            relevantWords = getSentiments(relevantWords, taggedText, userTopics)
            #print(relevantWords)
            t_new = party, location, date, cleanDocument, text, topic, title

            get_values_for_row(relevantWords, t_new, topics, corpus, local_call)
        #except KeyError:
        #    print("ERROR?")
        #    pass
    '''

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
                f.write("%s,%s,%s\n"%(key, over_pol, over_obj))

            
            

