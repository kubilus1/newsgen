#!/usr/bin/python

import feedparser
from bs4 import BeautifulSoup

import os
import re
import sys
import time
import atexit
import shelve
import string
import random
import urllib
import urllib2
import urlparse
import argparse
import markovify
from unidecode import unidecode
from markovbrain import POSifiedText

from fuzzywuzzy import fuzz
from tinydb import TinyDB, Query

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

    def link_pull(self, url):
        print "Pulling link: ", url
       
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

        try: 
            req = urllib2.Request(url)
            resp = urllib2.urlopen(req)
            print "urllib2, default"
        except urllib2.HTTPError, err:
            print "ERR:", err
            try:
                req.add_unredirected_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
                req.add_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
                resp = urllib2.urlopen(req)
                print "urllib2"
            except urllib2.HTTPError, err:
                print "ERR:", err
                resp = urllib.urlopen(url)
                print "urllib"

        html = resp.read()
        soup = BeautifulSoup(html)

        article_html = soup.find('article')
        if article_html:
            print "Found article!"
            article = article_html.get_text() 
            alen = len(article)

        for t in tag_list:
            article_html = soup.find(**t)
            if article_html:
                print "Found data for %s" % t
                if len(article_html.get_text()) > alen:
                    print "most data so far..."
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


    def feed_pull(self, feedurl):
        print "Pulling %s" % feedurl
        feed = feedparser.parse(feedurl)
        article_url = feedurl
        timestamp = time.time()
        article_imgs = []
        
        if len(feed.entries) == 0:
            if self.articles.search(Article.article_url == article_url):
                print "  skipping..."
                return

            print "Not an rss feed, trying to pull link..."
            try:
                article_text, article_title, img_srcs = self.link_pull(feedurl)
                for src in img_srcs:
                    article_imgs.append(src)
                print "    (%s)" % len(article_text)
                #self.texts[article_title] = article
                self.articles.insert({
                    "article_title":article_title,
                    "article_text":article_text,
                    "feed":feedurl,
                    "article_url":feedurl,
                    "timestamp":timestamp,
                    "imgs":article_imgs
                    })

            except AttributeError, e:
                print "  no article data. skipping.", e

        for entry in feed.get('entries'):
            article_title = entry.title
            print "TITLE:", article_title,

            if self.articles.search(Article.article_title == article_title):
            #if self.texts.get(entry.title) and self.force == False:
            #if hasattr(self.texts, entry.title):
                print "  skipping..."
                continue

            content = entry.get('content')
            if content:
                soup = BeautifulSoup(content[0].value)
                article_text = soup.get_text()
                imgs = soup.findAll('img')
                print "IMGS:", imgs
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
                    for src in img_srcs:
                        article_imgs.append(src)
                except AttributeError, e:
                    print "  no article data. skipping.", e
                    continue

            print "    (%s)" % len(article_text)
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


class ArticleGenerator(object):

    models = {}

    def __init__(self, dbname):
        self.articles = TinyDB(dbname)
        self.modelstore = Store('models.db')

    def _getall_text(self):
        allarts = self.articles.all()
        print allarts

    def _flatten(self, alist):
        return [ y for z in alist for y in z ]

    def get_imgs(self, search=None):
        return self._flatten(
            [ x.get('imgs') for x in self.articles.search(Article.imgs.exists())]
        )

    def get_model(self, key, search=None, search_key='article_text'):
        model = self.models.get(key) 
        if not model:
            text = searchdb(
                self.articles, search, search_key=search_key, limit=1000000
            )
            text += ". "
            model = POSifiedText(text)
            #self.models[key]= model
        return model

    def paragraph(self, model):
        outstr = ""
        for i in range(random.randrange(3,7)):
            outstr = "%s %s" % (
                outstr,
                model.make_sentence(tries=100)
            )
        return outstr

    def img(self):
        img_list = self.get_imgs()
        img = img_list[random.randrange(len(img_list))]
        return img

    def tagline(self, seed=None, search=None, search_key='article_text'):
        text_model = self.get_model('article_text', search, search_key)
        print text_model.make_sentence(maxlen=90, tries=20)
    
    def article(self, seed=None, search=None, search_key='article_text'):
        title_model = self.get_model('article_title', search, search_key)
        text_model = self.get_model('article_text', search, search_key)
        combo_model = markovify.combine(
            [ title_model, text_model ],
            [ 1, 1 ]
        )
        
        if seed:
            combo_model.seed(seed)

        title = string.capwords(
            combo_model.make_sentence(maxlen=75, tries=50)
        )

        text_model.last_words = combo_model.last_words

        print
        print self.img()
        print
        print title
        print
        print
        for i in range(random.randrange(3,7)):
            print
            print self.paragraph(text_model)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--rss_file")
    parser.add_argument("-d", "--dbfile", default="argen.db")
    parser.add_argument("-f", "--force", action="store_true")
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

    artgen = ArticleGenerator(args.dbfile)
    

    if args.command == 'article':
        print "SEARCH:", args.search
        artgen.article(seed=args.search, search=args.search)
        sys.exit(0)

    if hasattr(artgen, args.command):
        meth = getattr(artgen, args.command)
        if callable(meth):
            ret = meth()
            if ret:
                print ret
    else:
        raise argparse.ArgumentTypeError("no command " + args.command)

