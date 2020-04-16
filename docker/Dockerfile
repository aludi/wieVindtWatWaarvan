FROM python:3

WORKDIR /opt/wvww

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download nl_core_web_sm

CMD ["flask", "flaskTest.py"]
