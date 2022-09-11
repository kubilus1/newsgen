#!/usr/bin/env python3

import feedparser
from bs4 import BeautifulSoup

import os
import re
import sys
import time
import json
import atexit
import shelve
import string
import random
import urllib
import datetime
import urllib.request as urllib2
import urllib.parse as urlparse
import argparse

import markovify
from unidecode import unidecode

from markovbrain import MKVBrain
from gpt2brain import GPT2Brain

import newspaper
from fuzzywuzzy import fuzz
from tinydb import TinyDB, Query

import pprint
import postwp

DEBUG=False

#from articlestore import ArticleStore


def fuzzsearch(val, term, matchratio):
    ratio = fuzz.token_set_ratio(val, term)
    if ratio > matchratio:
        return True
    else:
        return False

def searchdb(db, search="", limit=1000000, search_key="article_text", ratio=50):
    query = Query()
    if search:
        text = " ".join(
            [ x.get(search_key) for x in db.search(
                query[search_key].test(fuzzsearch, search, ratio)
            ) ]
        )
    else:
        text = " ".join([ x.get(search_key) for x in db.all() ])
    text = text[:limit]
    return text


class Store(object):
    def __init__(self, filename):
        object.__setattr__(self, 'DICT', shelve.DbfilenameShelf(filename))
        # cleaning the dict on the way out
        atexit.register(self._clean)

    def __getattribute__(self, name):
        if name not in ("DICT", '_clean'):
            try:
                return self.DICT[name]
            except:
                return None
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in ("DICT", '_clean'):
            raise ValueError("'%s' is a reserved name for this store" % name)
        self.DICT[name] = value

    def _clean(self):
        self.DICT.sync()
        self.DICT.close()

'''
Article structure along the lines of

{ 
    "article_title":"....",
    "article_url":"...",
    "feed":"....",
    "timestamp":#####,
    "article_text":"...........",
    "imgs":["...",]
}

'''

Article = Query()

class Newspuller(object):
    def __init__(self, dbname):
        #self.store = Store(storename)
        self.articles = TinyDB(dbname)
        #self.articles = Query()


    def _extract(self, html):
        tag_list = [
            {"id":"content"},
            {"id":"content_area"},
            {"id":"content-area"},
            {"id":"story-target"},
            {"id":"single-articles"},
            {"class_":"content-main"},
            {"class_":"content"},
            {"class_":"entry-content"},
            {"class_":"articleContent"},
            {"class_":"blog-text"},
            {"class_":"newsentry"},
            {"class_":"itemFullText"},
            {"class_":"story_body"},
            {"class_":"introtext"},
            {"class_":"post-content"}
        ]
        
        article = ""
        imgs = []
        img_srcs = []
        article_title = ""
        alen = 0

        soup = BeautifulSoup(html)

        article_html = soup.find('article')
        if article_html:
            print("Found article!")
            article = article_html.get_text() 
            alen = len(article)

        for t in tag_list:
            article_html = soup.find(**t)
            if article_html:
                print("Found data for %s" % t)
                if len(article_html.get_text()) > alen:
                    print("most data so far...")
                    article = article_html.get_text()
                    imgs = article_html.findAll('img')
                    alen = len(article)

        article_title = soup.find('title').get_text()

        for img in imgs:
            if bool(urlparse.urlparse(img["src"]).netloc):
                img_srcs.append(img["src"])
            else:
                img_srcs.append(
                    urlparse.urljoin(url, img["src"])
                )

        return (article, article_title, img_srcs)

    def _extractNew(self, html):
        print("GOOSE extraction...")
        extr = Goose()
        data = extr.extract(raw_html=html)
        article = data.cleaned_text
        title = data.title
        img = data.infos.get('image',{}).get('url')
        return (article, title, [img])

    def _link_pull(self, url):
        print("Pulling link: ", url)
       
        try: 
            req = urllib2.Request(url)
            resp = urllib2.urlopen(req)
            print("urllib2, default")
        except urllib2.HTTPError as err:
            print("ERR:", err)
            try:
                req.add_unredirected_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
                req.add_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
                resp = urllib2.urlopen(req)
                print("urllib2")
            except urllib2.HTTPError as err:
                print("ERR:", err)
                resp = urllib.urlopen(url)
                print("urllib")

        html = resp.read()

        (article, article_title, img_srcs) = self._extract(html)

        return (article, article_title, img_srcs)

    def link_pull(self, url):
        parser = newspaper.Article(url, request_timeout=10)
        try:
            parser.download()
            parser.parse()
        except (newspaper.article.ArticleException, ValueError):
            return (None, None, [])
        article = parser.text
        title = parser.title
        img = parser.top_image

        return (article, title, [img])


    def feed_pull(self, feedurl):
        print("Pulling %s" % feedurl)
        feed = feedparser.parse(feedurl)
        article_url = feedurl
        timestamp = time.time()
        article_imgs = []
        
        if len(feed.entries) == 0:
            if self.articles.search(Article.article_url == article_url):
                print("  skipping...")
                return

            print("Not an rss feed, trying to pull link...")
            try:
                article_text, article_title, img_srcs = self.link_pull(feedurl)
                if not article_text:
                    print("  no article data. skipping.")
                    return
                for src in img_srcs:
                    article_imgs.append(src)
                print("    (%s)" % len(article_text))
                #self.texts[article_title] = article
                self.articles.insert({
                    "article_title":article_title,
                    "article_text":article_text,
                    "feed":feedurl,
                    "article_url":feedurl,
                    "timestamp":timestamp,
                    "imgs":article_imgs
                    })

            except AttributeError as e:
                print("  no article data. skipping.", e)

        for entry in feed.get('entries'):
            article_title = unidecode(entry.get('title'))
            if not article_title:
                continue

            print("TITLE:", article_title,)

            if self.articles.search(Article.article_title == article_title):
            #if self.texts.get(entry.title) and self.force == False:
            #if hasattr(self.texts, entry.title):
                print("  skipping...")
                continue

            content = entry.get('content')
            if content and len(content) > 300:
                soup = BeautifulSoup(content[0].value)
                article_text = soup.get_text()
                imgs = soup.findAll('img')
                print("IMGS:", imgs)
                for img in imgs:
                    src = img.get('src')
                    if src:
                        article_imgs.append(src)
            else:
                article_url = entry.get('feedburner_origlink')
                if not article_url:
                    article_url = entry.get('link')
                #article, article_title, img_srcs = self.link_pull(url)
                try:
                    article_text, article_title2, img_srcs = self.link_pull(article_url)
                    if not article_text:
                        continue
                    for src in img_srcs:
                        article_imgs.append(src)
                except AttributeError as e:
                    print("  no article data. skipping.", e)
                    continue

            print("    (%s)" % len(article_text))
            #self.texts[entry.title] = article
            self.articles.insert({
                "article_title":article_title,
                "article_text":article_text,
                "feed":feedurl,
                "article_url":article_url,
                "timestamp":timestamp,
                "imgs":article_imgs
                })
        print


BRAINS={
    "markov":MKVBrain,
    "gpt2":GPT2Brain
}

class ArticleGenerator(object):

    models = {}
    brain = None

    def __init__(self, 
            dbname, 
            brain,
            output="text", 
            outdir=None, 
            hosturl=None, 
            username=None,
            password=None
        ):

        self.brain_class = BRAINS.get(brain)
        self.articles = TinyDB(dbname)
        self.output = output
        self.outdir = outdir
        self.hosturl = hosturl
        self.username = username
        self.password = password


    def _flatten(self, alist):
        return [ y for z in alist for y in z if y ]

    def get_imgs(self, search=None):
        return self._flatten(
            [ x.get('imgs') for x in self.articles.search(Article.imgs.exists())]
        )

    def img(self):
        img_list = self.get_imgs()
        if img_list:
            img = img_list[random.randrange(len(img_list))]
        else:
            img = None
        return img

    def _get_tags(self, title, text):
        newsart = newspaper.Article('foo')
        newsart.text = text
        newsart.title = title

        newsart.download_state = 2
        newsart.is_parsed = True
        newsart.nlp()
        keywords = newsart.keywords
        summary = newsart.summary

        print("TITLE: %s" % newsart.title)
        return keywords, summary

    def _get_article_texts(self):
        #text = searchdb(
        #    self.articles, None, search_key=search_key, limit=1000
        #)
        #text += ". "

        text = ""
        for item in self.articles:
            text += "<|startoftext|>\n"
            text += "title: %s\n\n" % item.get('article_title')
            text += item.get('article_text')
            text += "\n<|endoftext|>\n"
        #print(text)
        return text

    def _find_text(self, seed, search, search_key='article_text'):
        text = searchdb(
            self.articles, search, search_key=search_key, limit=1000000
        )
        text += ". "
        return text

    def build_model(self, seed=None, search=None, search_key='article_text'):
        if self.brain is None:
            self.brain = self.brain_class()
                
        self.brain.build_model(
            #self._find_text(seed, search, search_key),
            self._get_article_texts(),
            search_key
        )

    def article(self, seed=None, search=None, search_key='article_text'):
        if self.brain is None:
            self.brain = self.brain_class()

        article_title, article_text = self.brain.get_article_text()
        article_img = self.img()
        article_date = datetime.datetime.now()
        article_keywords, article_summary = self._get_tags(article_title, article_text)

        if self.outdir:
            filename = "%s.md" % re.sub('\W+', '-', article_title.lower().strip())
            
            with open(os.path.join(self.outdir, filename), 'w') as h:
                sys.stdout = h
                self._print_article(
                    article_title,
                    article_text,
                    article_summary,
                    article_keywords,
                    article_date,
                    article_img
                )
        else:
            self._print_article(
                article_title,
                article_text,
                article_summary,
                article_keywords,
                article_date,
                article_img
            )

    def _print_article(
            self,
            article_title,
            article_text,
            article_summary,
            article_keywords,
            article_date,
            article_img
        ):

        if self.output == "json":
            payload = {
                "title":article_title,
                "content":article_text,
                "excerpt":newsart.summary,
                "tags":article_keywords
            }
            print(json.dumps(payload).__repr__())
        elif self.output == "markdown":
            print('---')
            print('title: %s' % article_title)
            print('featured_image: %s' % article_img)
            print('tags: %s' % article_keywords)
            print('date: %s' % article_date.strftime('%d/%m/%Y'))
            print('excerpt: %s' % article_summary)
            print('---')
            print(unidecode(article_text))
        else:
            print()
            print(article_img)
            print()
            print(article_title)
            print()
            print()
            print(article_text)
            print()
            print("KEYWORDS: %s" % ','.join(article_keywords))

        if self.hosturl:
            print("HOSTURL detected, posting article")
            wpp = postwp.WPPoster(
                self.hosturl,
                self.username,
                self.password
            )

            for i in range(5):
                imgid = wpp.upload_img(article_img)
                if imgid:
                    break
                article_img = self.img()

            ret = wpp.post(
                article_title,
                article_text,
                "%s..." % " ".join(article_text.split()[:30]),
                unique_ktags[:10],
                imgid=imgid
            )
            pprint.pprint(ret)
            print("POSTED draft")
            print(unique_ktags)
            print(article_keywords)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-H', "--hosturl", help="Wordpress host URL")
    parser.add_argument('-u', "--username")
    parser.add_argument('-p', "--password")
    parser.add_argument("-r", "--rss_file")
    parser.add_argument("-d", "--dbfile", default="argen.db")
    parser.add_argument("-b", "--brain", default="markov", choices=["markov", "gpt2"])
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-o", "--output", default="text", choices=["text", "json", "markdown"])
    parser.add_argument("-O", "--outdir", default=None, help="Output directory.")
    parser.add_argument("command", type=str, default="article", help="Command to execute")
    parser.add_argument("search", type=str, nargs='?', default=None, help="Article search string")
    args = parser.parse_args()

    if args.command == 'pull':
        newspull = Newspuller(args.dbfile)
        with open(args.rss_file, "r") as h:
            for a in h.readlines():
                if a.startswith('#'):
                    continue
                newspull.feed_pull(a)
        sys.exit(0)

    artgen = ArticleGenerator(
        args.dbfile,
        brain=args.brain,
        output=args.output,
        outdir=args.outdir,
        hosturl=args.hosturl,
        username=args.username,
        password=args.password
    )
    

    if args.command in ['article','title', 'sentences']:
        #print("SEARCH:", args.search)
        meth = getattr(artgen, args.command)
        meth(seed=args.search, search=args.search)
        sys.exit(0)

    if hasattr(artgen, args.command):
        meth = getattr(artgen, args.command)
        if callable(meth):
            ret = meth()
            if ret:
                print(ret)
    else:
        raise argparse.ArgumentTypeError("no command " + args.command)

