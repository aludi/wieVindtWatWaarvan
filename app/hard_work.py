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

# the program starts here, by initializing a Hard_Work() object.
# the hard_work object contains a polarity classification, an objectivity classification
# and a dict containing all the "subject, polarity, objectivity, context" pairs

# the init function collects the list of documents that are to be analysed.
# this depends on the call_type:
#           in this case, there's no corpus,topic/number_of_documents, but there is a single json file
# #     a call from the api has a list of length 1, since the api
# #     is called per document (so each document that is analysed, has to call the api to get the sentiments)
#
#          in these cases, a corpus/topic/number of documents has to be specified
##      a call from local is used for debugging (see the call in the localTest.py file)
#       a call from flask is if a user is using wie.poliflw.nl to search through a corpus
class Hard_Work():
    def __init__(self, corpus, topics, number_of_documents_to_search_for, json_doc, call_type):
        self.verbose_dict = {"entity":[], "polarity": [], "objectivity": [], "fragment": []}
        self.polarity = "0"
        self.objectivity = "0"
        if call_type == 'api':
            collection = [json_doc]
            pass
        if call_type == 'local' or call_type == 'flask':
            corpus = cleanUp(corpus)
            topics = cleanUp(topics)
            collection = collectDataPoliflw(corpus, number_of_documents_to_search_for)  # returns a list of json objects that match search criteria of "corpus" in poliflw.
        idfDict, collection_dict = calculateIDF(collection, False, call_type)           # get dict of collection and initialize idf for filtering of irrelevant entities
        mainLoop(self, idfDict, topics, corpus, call_type, collection_dict)
        # main call, passes the idfDict, the topics and corpus, the type, and
        # # most importantly: the documents (collection_dict) to the main loop to be processed

    # some getters and setters
    def set_polarity_and_objectivity(self, pol_class, obj_class):
        self.polarity = pol_class
        self.objectivity = obj_class

    def get_polarity_and_objectivity(self):
        return(self.polarity, self.objectivity)

    def update_verbose_dict(self, entity, polarity, objectivity, fragment):
        self.verbose_dict["entity"].append(entity)
        self.verbose_dict["polarity"].append(polarity)
        self.verbose_dict["objectivity"].append(objectivity)
        self.verbose_dict["fragment"].append(fragment)

    def get_verbose_dict(self):
        return self.verbose_dict


####    BEGIN TEXT CLEANING FUNCTIONS #####

# this function splits the user input for corpus and topics into a list, based on commas
# input: string, output: list
def cleanUp(incoming_text):
    cleanList = incoming_text.split(', ')
    return cleanList

# strips the the text of all punctuation
def stripTextOfAllPunct(text):
    table = str.maketrans({ord(ch): "" for ch in string.punctuation})
    strip = [t.translate(table) for t in text]
    return strip

# filter out the things that are not filtered out by the function above (stripTextOFAllPunct)
# TODO: this is inefficient, make one nice filtering function
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
    return cleanDocument

####    END TEXT CLEANING FUNCTIONS #####


####    BEGIN LOADING FUNCTIONS #####
# function that loads the attributes from the json file and returns
# the different aspects (party, location etc) as a tuple containing strings.
# if no attribute can be found, then it returns a
# "Geen X"
def loadAttributes(p):
    party = p["parties"][0]
    try:
        location = p["location"]
    except KeyError:
        location = "Geen locatie"
    try:
        date = p["date"]
    except KeyError:
        date = "Geen datum"
    text = p["description"]
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text().lower()
    try:
        topic = p["topics"]
    except KeyError:
        topic = "Geen topic"
    try:
        title = p["title"]
        soup = BeautifulSoup(title, 'html.parser')
        title = soup.get_text().lower()
        title = title.replace("\t", " ")    # filter out the tokens in the title that mess up the .csv file that is produced at the end.
        title = title.replace("\n", " ")
        title = title.replace(",", " ")
        title = title.replace("&nbsp ;", " ")
    except KeyError:
        title = "Geen titel"
    print(title, party)
    return party, location, date, text, topic, title    # tuple, every item is a string


# this function is only called if type = local or type = api.
# Here we query a number of items from the poliflw database,
# based on the query terms that the user has provided.
# we're searching for an "or" query on these terms (so, if
# the user wants to query "zonnepanelen, biomassa", we will search
# for "zonnepanelen OR biomass").

# the user can't query fewer than 100 documents (if you want to change this, you should change
# the "size" attribute. I think 100 is a good minimum for basic data analysis.
# the user also can't query more than 1000 documents, for time constraints.

# the resulting json files are then added to the collection list
def collectDataPoliflw(userQueryTerms, maxVal): # input types: list, int
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
    return collection   # returns a list of json files.

####    END LOADING FUNCTIONS #####


####    BEGIN TFIDF FUNCTIONS #####
# functions for calculating the TF-IDF values for each entity, to make
# sure that only relevant "subjects"/"entities" have sentiments attached.
# this prevents stuff like:
# #     "Het is verschrikkelijk" -> het -100 -100 [verschrikkelijk]


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

# TODO: refactor so calculating IDF and loading in the data happens in two separate functions
# this function loads, for every json document in the collection
# the attributes, and puts it in a dict (collection_dict).
# the collection_dict is used later on in the main loop, this is where the documents reside.
def calculateIDF(collection, calculate_own_idf, type_call):
    idfDict = {}
    collection_dict = {}
    count = 0
    for entry in collection:
        try:
            for p in entry['item']:
                party, location, date, text, topic, title = loadAttributes(p)
                cleanDocument = getCleanDocument(text)
                collection_dict[title] = (party, location, date, cleanDocument, text, topic, title)
                if calculate_own_idf:
                    bagOfWords = cleanDocument
                    idfDict = addToIDF(idfDict, bagOfWords)
                    count += 1
        except KeyError:
            pass
    if calculate_own_idf:       # if you want to calculate the idf on the corpus that you've found (not possible for api call)
        for word, val in idfDict.items():
            idfDict[word] = math.log(count/float(val))
    else:                       # we usually don't want that, and instead want to calculate the idf based on the corpus I already have in idfDict.json (based on 2000 documents)
        if type_call == 'local':
            with open('idfDict.json', 'r') as fp:
                idfDict = json.load(fp)
        elif type_call == 'api' or type_call == 'flask':
            with open('app/idfDict.json', 'r') as fp:
                idfDict = json.load(fp)
    return idfDict, collection_dict
    
def getTFIDF(cleanSentence, idfDict):
    bagOfWords = cleanSentence
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
            tfidf[word] = val   # if the word is not in the corpus, it is not a stopword, so it is relevant.
    return tfidf, max

####    END TFIDF FUNCTIONS #####

####   BEGIN STATUS AND COLLECTING FUNCTIONS ####
# in this section, the functions are used to calculate and classify
# the polarity and subjectivity of documents.


# this function classifies the document as some sort of sentiment
# the boundaries between categories here are.. well, let's call them intuitive.
# if you want to change them to see how the classification changes
# feel free.
def classify_message_status(funct, average, median, stdev):
    status = ""
    if funct == "polarity":
        if abs(median) - stdev < 0: # if you have a median of -0.3 and a std of 0.9, you have a mixed story
            status = "GEMENGD"
        else:   # if you have a median of 0.9 and a std of 0.01, you have a uniformly positive story
            # almost no spread in the message
            status = "EENDUIDIG"
        if 0.2 < median < 0.4:
            status = status + " POSITIEF"
        elif median > 0.4:
            status = status + " ERG POSITIEF"
        elif -0.2 > median > -0.4:
            status = status + " NEGATIEF"
        elif median < -0.4:
            status = status + " ERG NEGATIEF"
        else:
            status = status + " NEUTRAAL"
    else:
        if median < 0.2:
            status = "ERG OBJECTIEF"
        elif 0.4 > median >= 0.2:
            status = "OBJECTIEF"
        elif 0.7 > median >= 0.4:
            status = "SUBJECTIEF"
        elif 1 > median >= 0.7:
            status = "ERG SUBJECTIEF"
    return status


def calculate_status_of_message(max_tfidf_val, userTopics, relevantWords, title):
    average_polarity_message_list = []
    average_objectivity_message_list = []

    for entry in relevantWords.keys():
        directList, indirectList, tfidfVal = relevantWords[entry]
        list_polarities, list_objectivities, list_words = get_lists(directList, tfidfVal, max_tfidf_val, userTopics, entry)
        average_polarity_message_list = average_polarity_message_list + list_polarities
        average_objectivity_message_list = average_objectivity_message_list + list_objectivities

    # average:
    average_pol = round(deal_with_empty_lists("mean", average_polarity_message_list), 2)
    average_obj = round(deal_with_empty_lists("mean", average_objectivity_message_list), 2)
    # standard deviation
    stdev_pol = round(deal_with_empty_lists("sdev", average_polarity_message_list), 2)
    stdev_obj = round(deal_with_empty_lists("sdev", average_objectivity_message_list), 2)
    # median
    med_pol = round(deal_with_empty_lists("median", average_polarity_message_list), 2)
    med_obj = round(deal_with_empty_lists("median", average_objectivity_message_list), 2)

    print("average of article: ", average_pol, average_obj)
    print("median of article: ", med_pol, med_obj)
    print("standard dev: ", stdev_pol, stdev_obj)

    if med_pol == 0 and med_obj == 0 and stdev_pol == 0 and stdev_obj == 0:
        polarity_status = "GEEN POLARITEIT"
        objectivity_status = "GEEN OBJECTIVITEIT"
    else:
        polarity_status = classify_message_status("polarity", average_pol, med_pol, stdev_pol)
        objectivity_status = classify_message_status("objectivity", average_obj, med_obj, stdev_obj)
    return polarity_status, objectivity_status


# here, I'm changing the polarity of some sentiments
# if the term is
#       'groot risico', and 'groot' has a positive sentiment,
# that doesn't mean 'risico' is positive. The second word changes the meaning
# TODO: check if this is the case for more terms
def reverse_polarity_if_needed(list_of_string, polarity, sent):
    polarity_reversers = ["risico", "probleem", "problemen", "moeilijkheden", "bedreiging", "consequentie"]
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
            val = statistics.stdev(list_sentiment)
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


# in this function, we're saying which subjects are interesting/relevant enough
# to pass and be counted for our sentiment analysis.
# i chose a
def get_lists(directList, tfidfVal, max_tfidf_val, userTopics, entry):
    list_polarities = []
    list_objectivities = []
    list_words = []
    if tfidfVal >= 0 or entry in userTopics:        # an alternative could be tfidfVal >= max_tfidf_val/2, where you only want the most 'relevant' words
        for (context, sentiment) in directList:
            direction = reverse_polarity_if_needed(context, sentiment[1], sentiment[0]) # sentiment has a structure of [[sentiment, words], polarity, objectivity, None]
            if sentiment[1] != 0:
                list_polarities.append(direction * sentiment[1])
            list_objectivities.append(sentiment[2])
            list_words.append(context)
    return list_polarities, list_objectivities, list_words


# in this function, a dictionary (relevantTerms) of one document is passed
# this dictionary contains, for each "subject"/entity,
# the context, and the sentiment, as tuple
# if multiple contexts and sentiments, then it is a list of them
# based on the sentiments, an average is calculated of polarity, objectivity for each term, as well as a list of contexts
# this is then written to either the database (flask), or to the verbose_dict (api) option.
def get_values_for_row(self, relevantWords, text_attributes_collection, topics, corpus, type_call, max_tfidf_val):
    party, location, date, cleanDocument, text, topic, title = text_attributes_collection
    attached_count = 0
    for entry in relevantWords.keys():
        directList, indirectList, tfidfVal = relevantWords[entry]
        list_polarities, list_objectivities, list_words = get_lists(directList, tfidfVal, max_tfidf_val, topics, entry)
        average_polarity_word = int(deal_with_empty_lists("mean", list_polarities) * 100)
        average_objectivity_word = int(deal_with_empty_lists("mean", list_objectivities) * 100)
        if average_polarity_word != 0 or average_objectivity_word != 0:
            attached_count += len(list_words)
            print("\t", entry, party, average_polarity_word, average_objectivity_word, list_words, tfidfVal )
            if type_call == 'local':
                pass
            elif type_call == 'api':
                self.update_verbose_dict(entry, average_polarity_word, average_objectivity_word, list_words)
            else:
                write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words)
    #print("ATTACHED COUNT", attached_count)

# this is only used in the type_call == flask option
def write_to_db(party, location, date, topics, title, corpus, entry, average_polarity_word, average_objectivity_word, list_words):
            sent_entry_in_db = Sents(parties=str(party), location=str(location), date=str(date),topic=str(topics), title=str(title), corpus=str(corpus), entity=str(entry), polarity=average_polarity_word, objectivity=average_objectivity_word, direct_words=str(list_words))
            db.session.add(sent_entry_in_db)

####   END STATUS AND COLLECTING FUNCTIONS ####


####   BEGIN CONNECTING FUNCTIONS  ####
# the functions in this section are the functions used
# to connect the sentiment to the subject/entity


# here, we are filtering the phrase for filtered expressions
# and we are attaching the sentiment to the lemma of the subject
# this is to prevent kerncentrale having a different sentiment from kerncentrales
# and, we are storing a tuple of (sentiments, string(context + sentiment) as an item
# in the list.

# recursion_path_list is a list of all the words that we found during the recurion, example: ['duur', 'KERNENERGIE', 'duur', 'is', 'duur', 'te', 'duur', 'duurt']
# context_fragment is a sublist of recursion_path_list that contains all the context we want, example: ['duur', 'kernenergie']

def attach_direct_list(relevantWords, recursion_path_list, context_fragment, word, sentiment):
    if not_a_filtered_expression(recursion_path_list):
        lemma = nlp(word)[0].lemma_
        if lemma in relevantWords.keys():    # we want to collect the lemmas as much as possible
            directList, indirectList, tfidfVal = relevantWords[lemma]
            directList.append((" ".join(context_fragment), sentiment))
        else:   # if we cannot find the lemma, we need to just add the non-lemmatized word
            try:
                directList, indirectList, tfidfVal = relevantWords[word]
                directList.append((" ".join(context_fragment), sentiment))   # attaching the tuple: (context, sentiment)
            except KeyError:
                pass
    return relevantWords


# this function gets a "phrase" as input. This phrase
# is a list that contains all the words that were found during the
# recursion, and will look like this:
#       ['nieuwe', 'KERNCENTRALE', 'van', 'kerncentrale', 'een', 'kerncentrale', 'BOUW']
#       ['schoon', 'INTERNETPETITIE', 'onder', 'internetpetitie', 'de', 'internetpetitie', '“', 'internetpetitie', 'genoeg', 'KERNENERGIE']
# this is to prevent attaching 'schoon' to 'kernenergie", since that's not the intended meaning
# TODO: add this for more expressions
# TODO: find a way to speed this up

def not_a_filtered_expression(phrase):
    filteredList = [["huiselijk", "geweld"], ["doorgaande", "weg"], ["sociale", "huurwoningen"],
                    ["sociale", "huurbouw"], ["publieke", "tribune"], ["hard", "gemaakt"],
                    ["speciaal", "onderwijs"], ["provinciale", "staten"],
                    ["vinger", "aan", "pols"], ["schoon", "genoeg"]]
    for subList in filteredList:
        check = all(item1 in phrase for item1 in subList)   # if the phrase contains all the words that are in the list,
        if check:                                           # then it's an expression, or a compound term
            return False                                    # and it doesn't count as sentiment
    return True


def get_sentiments_from_text_chunk(sentiments_in_sentence, text):
    res = [val for key, val in sentiments_in_sentence.items() if text in key]
    return res[0]

# deals with additional missed negation
# for example: "kernenergie is niet helemaal mooi" -> [niet, mooi]
def find_missed_negation(i, sent_words):
    if (i == 2 or i == 3) and 'niet' not in sent_words:
        return ["niet"]
    else:
        return [""]

# The recursion!
# so, here we're starting from the first item in a a sentiment list. This is either the sentiment itself ['duur'],
# a negation ['niet', 'duur'], or an amplifyer ['erg', 'duur'].
#       NB: sometimes, it is a conjunction, and then the results are not good. TODO: find fix for conjunction
# So, we start with the first item, add it to "collected_words",
#   If the item is a noun, we add it to "collected_words" in UPPERCASE.
# and we go to the 'head' (parent), as defined by the spacy dep tagger.
# when we reach the head, we look through all the children that we haven't looked through before
# we go, until we:
#       1. find two nouns
#       2. find one noun, and more than one non-aux, non-cop verb
#       3. find one noun, and find a conjunction
#       4. have traversed all children, and are at "ROOT"
#          these are the stop conditions

def recurse_to_find_entity(chunk, head, first_noun, second_noun, verb_count, collected_words):
    # print("\t", chunk.text, chunk.pos_, chunk.dep_, head, first_noun, second_noun)
    if (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and len(
            chunk.text) > 1 and first_noun != 0 and chunk.text != head:
            # found the second noun, append it and we're done! Case 1.
        second_noun = chunk.text
        collected_words.append(second_noun.upper())
        return collected_words
    elif (chunk.pos_ == "NOUN" or chunk.pos_ == "PROPN") and first_noun == 0:
        # found the first noun. Appending it
        first_noun = chunk.text
        collected_words.append(first_noun.upper())
        head = first_noun   # set it as head so we can't accidentally find it again as second_noun
        for child in chunk.children:
            if child.text not in collected_words and child.text.upper() not in collected_words:
                return recurse_to_find_entity(child, head, first_noun, second_noun, verb_count, collected_words)    # look through children
        return recurse_to_find_entity(chunk.head, head, first_noun, second_noun, verb_count, collected_words)       # go to the head
    else:
        # you didn't find a noun. Append it
        collected_words.append(chunk.text)
        # increase the verbcount if you found a verb
        if chunk.pos_ == "VERB" and (chunk.dep_ != "aux" or chunk.dep_ != "cop"):
            verb_count += 1
        # if you found more than one relevant verb, you're probably in a new sentence fragment where you don't want to be. Case 2
        if verb_count > 1:
            return collected_words
        # if you found a conjunction after the first noun, you're probably in a new sentence fragment where you don't want to be. Case 3
        if chunk.pos_ == "CONJ" and first_noun != 0:
            return collected_words
        # go through all the children of the word, that have not already been found
        for child in chunk.children:
            if child.text not in collected_words and child.text.upper() not in collected_words:
                return recurse_to_find_entity(child, head, first_noun, second_noun, verb_count, collected_words)
        # if you haven't found root, go to head
        if chunk.dep_ != "ROOT":
            return recurse_to_find_entity(chunk.head, head, first_noun, second_noun, verb_count, collected_words)
        else: # if you found root, you can't go to head, and now you're done. Case 4
            return collected_words

# in this function, we are scanning the text sentence by sentence
# for each sentence, we are checking what the sentiments in that sentence are
# and then we try to attach them to an entity/subject, if they are interesting
def getSentiments(max_val_tf, relevantWords, text):
    sentiment_count = 0
    for sentence in text:   #passing each sentence the number of times a sentiment has occurred. do this before.
        sentiments_in_sentence = {}
        sentiments_in_sentence_list = []
        for sentiment in pl.sentiment(sentence).assessments:
            sentiment_words, pol, obj, x = sentiment
            # only add sentiments with a bit of flavor
            if abs(pol) + abs(obj) > 0.1:       # interestingness
                sentiments_in_sentence[" ".join(sentiment_words)] = sentiment # appending a tuple
                # assumption: if the sentiment is longer than 1 item,
                #  the head of the first item will be the second item, etc.
                #  This assumption is not always correct (case of conjunction)
                # TODO: fix conjunction case
                sentiments_in_sentence_list.append(sentiment_words[0])
                sentiment_count += 1
        if sentiments_in_sentence:  # if there are interesting sentiments in the sentence, we want to do a recursion to match them with an entity/subject
            i, flag = 0, 0
            for chunk in nlp(sentence): # we are going through the nlp (spacy) tagged sentence
                if chunk.text == 'niet': # we found a negation
                    flag = 1
                if chunk.text in sentiments_in_sentence_list and chunk.dep_ not in ['case', 'mark', 'advcl'] and chunk.pos_ not in ["VERB"]:
                    sentiment_chunk = get_sentiments_from_text_chunk(sentiments_in_sentence, chunk.text)
                    recursion_path_list = recurse_to_find_entity(chunk, 0, 0, 0, 0, [])
                    missed_negation = find_missed_negation(i, sentiment_chunk[0])
                    context_fragment = missed_negation + sentiment_chunk[0]
                    if 'naar' not in sentiment_chunk[0]:    # hand-filtering out "naar", which keeps being classified as a sentiment
                        word = ""
                        for item in recursion_path_list:
                            if item.isupper():
                                word = item.lower()
                                if word not in context_fragment:  # the word can't be in "context_fragment" already, that's how you get "ramp ramp chernobyl"
                                    context_fragment.append(word)
                        if word != "":  # if we found at least one potential noun to be the entity/subject
                            relevantWords = attach_direct_list(relevantWords, recursion_path_list, context_fragment, word, sentiment_chunk)
                if flag == 1:   # for the missed_negation
                    i += 1
    #print("SENTIMENT COUNT: ", sentiment_count)
    return relevantWords

# this function initializes a dictionary of relevant words.
# this dictionary does not contain any words that are sentiment words,
# words that are too short, or words that are too long (likely urls or other
# non-filtered entities.
# essentially, this is a pre-filter
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
        if w not in listSent and 2 < len(w) < 25:
            relevantWords[w] = ([], [], tfidf[w])
            counter += 1
    return relevantWords

# in this function we create the relevantWords dict.
# for each word, we attach the sentiment in direct_words
def getRelevantTerms(relevantWords, userInput, tfidf):
    relevantTermsList = userInput
    for term in relevantTermsList:
        try:
            relevantWords[term] = ([], [], tfidf[term])     # triple: direct_words, indirect_words, and tfidf-value
        except KeyError:
            try:
                #problem 1: honden -> hond
                lemma = nlp(term)[0].lemma_
                relevantWords[lemma] = ([], [], tfidf[lemma])
            except KeyError:
                #problem 2: meerdere zoektermen (kat in hondenartikel)
                pass
    return relevantWords

####   END CONNECTING FUNCTIONS  ####

####   The MAIN Loop  ####

def mainLoop(self, idfDict, topics, corpus, type_call, collection_dict):
    if type_call != "api":
        if topics[0] != '':
            userTopics = corpus
            for item in topics:
                userTopics.append(item)
        else:
            userTopics = corpus
    if type_call == "api":  # no corpus and no topics
        userTopics = []
    dict_of_status = {}
    for item in collection_dict.keys():
        (party, location, date, cleanDocument, text, topic, title) = collection_dict[item]
        print("\t", title)
        tfidf, max = getTFIDF(cleanDocument, idfDict)       # max is the maximum value found in the tfidf, you could use to to specify some cut-off point at which terms become irrelevant.
        entities = getEntities(cleanDocument, tfidf, max)
        relevantWords = getRelevantTerms(entities, userTopics, tfidf)
        taggedText = pl.tokenize(text)      # text has to be tagged by the pattern tokenizer as well, otherwise sentiments are not recognized.
        relevantWords = getSentiments(max, relevantWords, taggedText)
        get_values_for_row(self, relevantWords, collection_dict[item], userTopics, corpus, type_call, max)
        polarity_status, objectivity_status = calculate_status_of_message(max, userTopics, relevantWords, title)
        dict_of_status[title] = (polarity_status, objectivity_status)
        print(polarity_status, objectivity_status)
        if type_call == 'api':
            self.set_polarity_and_objectivity(polarity_status, objectivity_status)  # setting so it is accessible in routes.py
            print(title, polarity_status, objectivity_status)
    if type_call == "flask":
        sentiments = Sents.query.all()
        for x in sentiments:
            print(x.id, x.corpus, x.entity, x.polarity, x.objectivity, x.direct_words)
        db.session.commit()     # you have written to the db in the function "get_values_for_row". this was done per document. Now you're committing everything.
    elif type_call == "local":
        with open('text.csv', 'w') as f:
            for key in dict_of_status.keys():
                over_pol, over_obj = dict_of_status[key]
                f.write("%s,%s,%s\n"%(key, over_pol, over_obj))

            
            

