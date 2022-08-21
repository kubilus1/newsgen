FROM ubuntu:focal

RUN apt-get update && apt-get install -y \
    python3-pip

COPY requirements.txt /opt/newsgen/

RUN python3 -m pip install -U pip
RUN python3 -m pip install -r /opt/newsgen/requirements.txt

RUN python3 -m nltk.downloader -d /usr/local/share/nltk_data punkt
RUN python3 -m nltk.downloader -d /usr/local/share/nltk_data averaged_perceptron_tagger

COPY *.py /opt/newsgen/

ENV PYTHONIOENCODING=utf-8

WORKDIR /opt/newsgen

ENTRYPOINT ["python3", "newsgen.py"]
