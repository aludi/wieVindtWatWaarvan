# wieVindtWatWaarvan
Sentiment analyse gebaseerd op de poliflw API, de spacy tagger, en pattern sentimenten.

De flow van de hard_work() module die de sentiment-analyse doet is te zien in de flow_hard_work.png.

Twee API methodes:

1.
Input: json file vanuit Poliflw
Method: wie.poliflw.nl/api/get_sentiment  
  run met: curl 'https://wie.poliflw.nl/api/get_sentiment' -d @'app/test-item.json'
  waar 'app/test-item.json' een gedownloade json file is van een Poliflw document.
Output: Polariteit rating, subjectiviteit rating

2.
Input: json file vanuit Poliflw
Method: wie.poliflw.nl/api/get_sentiment_verbose
  run met: curl 'https://wie.poliflw.nl/api/get_sentiment_verbose' -d @'app/test-item.json'
Output: Polariteit rating, subjectiviteit rating
        voor elk woord waar een sentiment opzit:
        (woord, polariteit, subjectiviteit, context-lijst)
 
 Voorbeeld:
 1.curl 'https://wie.poliflw.nl/api/get_sentiment' -d @'app/test-item.json'
EENDUIDIG POSITIEF ERG SUBJECTIEF 


 2.
 curl 'https://wie.poliflw.nl/api/get_sentiment_verbose' -d @'app/test-item.json'
EENDUIDIG POSITIEF ERG SUBJECTIEF 
('moeders', 50, 50, [' gratis ! entree moeders'])
('soorten', 0, 75, [' klassieke muziek soorten'])
('middag', 70, 100, [' mooie plekken middag'])
('muziek', 0, 20, [' verschillende soorten muziek'])
('klassiekop', 0, 75, [' klassiek klassiek klassiekop'])


