import feedparser
from bs4 import BeautifulSoup

import os
import re
import sys
import string
import random
import urllib
import urllib2
import urlparse
import argparse
import markovify
from unidecode import unidecode
from markovbrain import POSifiedText

import tinydb

DEBUG=False

STATESIZE=2
TEXTMETHOD=POSifiedText
#TEXTMETHOD=markovify.Text

import shelve

class ArticleStore(object):

    texts = {}
    ads = {}
    imgs = set()
    ad_imgs = set()
    text_model = 0
    title_model = 0
    combo_model = 0
    force = False
	
 
    def __init__(self, force=False):
        self.force = force

    def save(self, filename="argen.db"):
        db = shelve.open(filename)
        try:
            db['texts'] = self.texts
            db['imgs'] = self.imgs
            db['ads'] = self.ads
            db['ad_imgs'] = self.ad_imgs
        finally:
            db.close()

    def load(self, filename="argen.db"):
        db = shelve.open(filename)
        try:
            if db.has_key('texts'):
                self.texts.update(db['texts'])
            if db.has_key('imgs'):
                self.imgs.update(db['imgs'])
            if db.has_key('ads'):
                self.ads = db['ads']
            if db.has_key('ad_imgs'):
                self.ad_imgs = db['ad_imgs']
        finally:
            db.close()


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
            req.add_unredirected_header('User-Agent', 'Mozilla/5.0')
            req.add_header('User-Agent', 'Mozilla/5.0')
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


    def pull(self, feedurl):
        print "Pulling %s" % feedurl
        feed = feedparser.parse(feedurl)
        if len(feed.entries) == 0:
            print "Not an rss feed, trying to pull link..."
            try:
                article, article_title, img_srcs = self.link_pull(feedurl)
                for src in img_srcs:
                    self.imgs.add(src)
                print "    (%s)" % len(article)
                self.texts[article_title] = article
            except AttributeError, e:
                print "  no article data. skipping.", e

        for entry in feed.get('entries'):
            print entry.title,
            if self.texts.get(entry.title) and self.force == False:
            #if hasattr(self.texts, entry.title):
                print "  skipping..."
                continue

            content = entry.get('content')
            if content:
                soup = BeautifulSoup(content[0].value)
                article = soup.get_text()
                imgs = soup.findAll('img')
                print "IMGS:", imgs
                for img in imgs:
                    src = img.get('src')
                    if src:
                        self.imgs.add(src)
            else:
                url = entry.get('feedburner_origlink')
                if not url:
                    url = entry.get('link')
                #article, article_title, img_srcs = self.link_pull(url)
                try:
                    article, article_title, img_srcs = self.link_pull(url)
                    for src in img_srcs:
                        self.imgs.add(src)
                except AttributeError, e:
                    print "  no article data. skipping.", e
                    continue

            print "    (%s)" % len(article)
            self.texts[entry.title] = article
        print

    def title(self, seed=None):
        if self.title_model:
            self.title_model.reset_text()
        if self.text_model:
            self.text_model.reset_text()
        if self.combo_model:
            self.combo_model.reset_text()

        titletext = ".  ".join(s for s in self.texts.iterkeys())
        if not self.title_model:
            self.title_model = TEXTMETHOD(titletext, state_size=STATESIZE)
        alltext = " ".join(s for s in self.texts.itervalues())
        alltext += "."
        if not self.text_model:
            self.text_model = TEXTMETHOD(alltext, state_size=STATESIZE)
        if not self.combo_model:
            self.combo_model = markovify.combine(
                [ self.title_model, self.text_model ], 
                [ 1, 1 ]
            )
        
        if seed:
            self.combo_model.seed(seed)

        title = string.capwords(self.combo_model.make_sentence(maxlen=75, tries=50))
        self.text_model.last_words = self.combo_model.last_words

        return title

    def img(self):
        imglist = list(self.imgs)
        return imglist[random.randrange(len(imglist))]

    def tagline(self):
        titletext = ".  ".join(s for s in self.texts.iterkeys())
        if not self.title_model:
            self.title_model = TEXTMETHOD(titletext, state_size=STATESIZE)
        alltext = " ".join(s for s in self.texts.itervalues())
        alltext += "."
        if not self.text_model:
            self.text_model = TEXTMETHOD(alltext, state_size=STATESIZE)

        return self.text_model.make_short_sentence(40)

    def body(self):
        alltext = " ".join(s for s in self.texts.itervalues())
        alltext += "."
        if not self.text_model:
            self.text_model = TEXTMETHOD(alltext, state_size=STATESIZE)
        outstr = ""
        for i in range(random.randrange(3,7)):
            outstr = "%s  %s" % (outstr,
                    self.text_model.make_sentence(tries=100))
    
        return outstr

    def article(self, seed=None):
        print
        print self.img()
        print
        print self.title(seed)
        print
        #print "          - ", names.get_full_name()
        print
        for i in range(random.randrange(3,7)):
            print
            print self.body()

        #print 
        #print "Tags: ", ", ".join(self.combo_model.keyword_tags)

    def quote(self, seed):
        arts.text_model.seed(seed)
        print "'%s' - %s" % (
            arts.text_model.make_sentence(),
            name.get_full_name()
        )
    

