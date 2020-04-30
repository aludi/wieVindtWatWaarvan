import time
from hard_work import Hard_Work
import string
import spacy
from spacy import displacy
import nl_core_news_sm
nlp = nl_core_news_sm.load()

start = time.time()
hw = Hard_Work('kernenergie', '', 100, 0, "local")      #call on corpus "kernenergie", with no added topics, no json doc, and return 100 documents for a local call.
#displacy.serve(nlp("We hebben kernenergie helemaal niet nodig."), style="dep")
print("runtime ", time.time() - start)

