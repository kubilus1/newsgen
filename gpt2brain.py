#!/usr/bin/env python3


import gpt_2_simple as gpt2
import os
import string
import requests
import random

from unidecode import unidecode
from fuzzywuzzy import process

from gpt2textgen import TextGen

class GPT2Brain(object):
    sess = None

    def __init__(self):
        pass
        #self.sess = gpt2.start_tf_sess()
        #self.in_text = in_text

    def build_model(self, in_text, key):
        sess = gpt2.start_tf_sess()
        model_name = "124M"
        if not os.path.isdir(os.path.join("models", model_name)):
                print(f"Downloading {model_name} model...")
                gpt2.download_gpt2(model_name=model_name)   # model is saved into current directory under /models/124M/

        file_name = "/tmp/gpt-tune-data.txt"
        with open(file_name, 'w') as f:
            f.write(unidecode(in_text))
            
        gpt2.finetune(sess,
                    file_name,
                    save_every=100,
                    model_name=model_name,
                    steps=100)   # steps is max number of training steps


    def get_article_text(self):
        tg = TextGen()
        
        title = ""
        while not title:
            title = tg.get_text("title:", endtoken="\n", post_process=False)
        print(f"GOT TITLE: {title}")
        texts = tg.get_text(f"{title}\n", as_list=True)
        print(texts)
        print("Formatted ---->>")
        text = "\n\n".join(self.format_paragraphs(texts))
        print(text)
        return title, text


    def format_paragraphs(self, in_text):
        idx = 0
        while idx <= len(in_text):
            num = random.randint(1,5)
            yield " ".join(in_text[idx:idx+num])
            idx+=num


    def _get_article_text(self):
        gpt2.load_gpt2(self.sess)
        
        article_title_texts = gpt2.generate(
            self.sess,
            length=20,
            return_as_list=True,
            temperature=0.4
        )
        article_title = string.capwords(" ".join(article_title_texts).split(".")[0])

        article_texts = gpt2.generate(
            self.sess,
            return_as_list=True,
            temperature=0.7,
            nsamples=1
        )

        # Join the list of chunks
        chunk_text = " ".join(article_texts)

        sentences = chunk_text.split(".")[:-1]
        
        deduped = process.dedupe(
            sentences
        )

        article_text = ".".join(deduped)
       
        for s in sentences:
            if s not in deduped:
                print("DUPE: ", s)

        return article_title, article_text
