FROM python:3

WORKDIR /opt/wvww

COPY requirements.txt ./
COPY db/app.db .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download nl_core_news_sm

CMD flask run --host=0.0.0.0
