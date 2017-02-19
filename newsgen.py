#!/usr/bin/python

import feedparser
from bs4 import BeautifulSoup

import os
import re
import sys
import string
import random
import shelve
import codecs
import urllib
import urllib2
import urlparse
import argparse
from unidecode import unidecode

import nltk
import names
import markovify

DEBUG=False

STATESIZE=2
DEFAULT_MAX_OVERLAP_RATIO = 0.7
DEFAULT_MAX_OVERLAP_TOTAL = 15
DEFAULT_TRIES = 40

DEFAULT_MIN_OVERLAP_RATIO = 0.3
DEFAULT_MIN_OVERLAP_TOTAL = 15

class POSifiedText(markovify.Text):
    
    last_words = []
    last_state = None

    def word_split(self, sentence):
        words = re.split(self.word_split_pattern, sentence)
        words = [ "::".join(tag) for tag in nltk.pos_tag(words) ]
        return words

    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence

    def _consistency_check(self, words):
        #if len(self.last_words) > 15: 
        #print "Checking consistency: ", len(self.last_words)
        lw_set = set(self.last_words)
        w_set = set(words)

        both_set = lw_set & w_set
        #print "BOTH SET:", both_set
        ratio = (float(len(both_set)) / float(len(w_set)))
        #ratio = (float(len(both_set)) / float(15))
        print "(%s) (%s) %s" % (ratio, both_set, self.word_join(words))
        return ratio
        #if (float(len(both_set)) / float(len(w_set))) >= DEFAULT_MIN_OVERLAP_RATIO:
        #    print "SUCCESS:", words
        #    return True


    def consistency_check(self, words):
        proper_nouns = ['NNP', 'NNPS' ]
        nouns = ['NN', 'NNS' ]
        found_nouns = [ x.split('::')[0].rstrip('s').lower() for x in words if x.split('::')[1] in nouns ]
        found_pnouns = [ x.split('::')[0].rstrip('s').lower() for x in words if x.split('::')[1] in proper_nouns ]
        pn_mis_match = [ x for x in found_pnouns if x not in self.last_words and self.last_words]
        pn_match = [ x for x in found_pnouns if x in self.last_words ]
        n_match = [ x for x in found_nouns if x in self.last_words ]
        n_mis_match = [ x for x in found_nouns if x not in self.last_words and self.last_words]

        weight = 0.5
        
        for fn in found_nouns:
            weight += 0.1

        for pn in found_pnouns:
            weight += 0.1

        for m in pn_match:
            weight += 1
            
        for m in n_match:
            weight += 0.2
            
        for m in pn_mis_match:
            weight -= 1
        
        for m in n_mis_match:
            weight -= 0.1

        if DEBUG:
            print "last_words:", self.last_words
            print "found nouns:", found_nouns
            print "PN mis-matches:", pn_mis_match
            print "PN match:", pn_match
            print "N mis-match:", n_mis_match
            print "N match:", n_match
            print "weight:", weight

        return weight
        #if proper_nouns and not pn_match:
        #    return 0
        #else:
        #    return 1

    def test_sentence_output(self, words, max_overlap_ratio, max_overlap_total):
        """
        Given a generated list of words, accept or reject it. This one rejects
        sentences that too closely match the original text, namely those that
        contain any identical sequence of words of X length, where X is the
        smaller number of (a) `max_overlap_ratio` (default: 0.7) of the total
        number of words, and (b) `max_overlap_total` (default: 15).
        """
        # Reject large chunks of similarity
        overlap_ratio = int(round(max_overlap_ratio * len(words)))
        overlap_max = min(max_overlap_total, overlap_ratio)
        overlap_over = overlap_max + 1
        gram_count = max((len(words) - overlap_max), 1)
        grams = [ words[i:i+overlap_over] for i in range(gram_count) ]
        for g in grams:
            gram_joined = self.word_join(g)
            if gram_joined in self.rejoined_text:
                return -1000

        ret = self.consistency_check(words)

        return ret

    def reset_text(self):
        print "Resetting last_words..."
        self.last_words = []
        random.seed()

    def keywords(self, words):
        #skipits = ['DT', 'IN', 'CC', 'TO', 'PRP']
        nouns = ['NNP', 'NNPS', 'NN', 'NNS' ]
        #words = [ w for w in words if w.split('::')[1] not in skipits ]
        words = [ w.split('::')[0].rstrip('s').lower() for w in words if w.split('::')[1] in nouns ]
        return words
    
    def generate_corpus(self, text):
        """
        Given a text string, returns a list of lists; that is, a list of
        "sentences," each of which is a list of words. Before splitting into 
        words, the sentences are filtered through `self.test_sentence_input`
        """
        sentences = self.sentence_split(text)
        cleaned = map(self.clean_sentence, sentences)
        passing = filter(self.test_sentence_input, cleaned)
        runs = map(self.word_split, passing)
        return runs

    def clean_sentence(self, sentence):
        replace_pat = re.compile(r"( [\"\'])|([\"\'] )|(\.\.\.)|(Alex Jones Show)|(Engineered Lifestyles)|(\[.*\][ ]?-?[ ]?)|([\(\)])|(\n)")
        # Decode unicode, mainly to normalize fancy quotation marks
        if sentence.__class__.__name__ == "str":
            decoded = sentence
        else:
            decoded = unidecode(sentence)
        
        cleaned = replace_pat.sub(' ', decoded)
        cleaned = cleaned.strip()
        return cleaned

    def test_sentence_input(self, sentence):
        """
        A basic sentence filter. This one rejects sentences that contain
        the type of punctuation that would look strange on its own
        in a randomly-generated sentence. 
        """
        reject_pat = re.compile(r"(\.\.\.)|(Tumblr)|(http)|(#\D)|(Alex Jones Show)|(^')|('$)|\s'|'\s|[\"(\(\)\[\])]|(\n)|(^\s*$)")
        #reject_pat = re.compile(r"(\.\.\.)|(Tumblr)|(http)|(#\D)|(Alex Jones Show)|(^')|('$)|\s'|'\s|[\"(\(\)\[\])]|(\n)|(^\s*$)")
        #reject_pat = re.compile(r"(Tumblr)|(http)|(#\D)|(^')|('$)|\s'|'\s|[\"(\(\)\[\])]")
        # Decode unicode, mainly to normalize fancy quotation marks
        if sentence.__class__.__name__ == "str":
            decoded = sentence
        else:
            decoded = unidecode(sentence)
        
        # Sentence shouldn't contain problematic characters
        if re.search(reject_pat, decoded):
            if DEBUG:
                print "REJECTING:", decoded
            return False
        
        return True

    def seed(self, sentence):
        words = self.word_split(sentence)
        self.last_words = self.keywords(words)
    
    def make_sentence(self, init_state=None, **kwargs):
        """
        Attempts `tries` (default: 10) times to generate a valid sentence,
        based on the model and `test_sentence_output`. Passes `max_overlap_ratio`
        and `max_overlap_total` to `test_sentence_output`.

        If successful, returns the sentence as a string. If not, returns None.

        If `init_state` (a tuple of `self.chain.state_size` words) is not specified,
        this method chooses a sentence-start at random, in accordance with
        the model.
        """
        tries = kwargs.get('tries', DEFAULT_TRIES)
        mor = kwargs.get('max_overlap_ratio', DEFAULT_MAX_OVERLAP_RATIO)
        mot = kwargs.get('max_overlap_total', DEFAULT_MAX_OVERLAP_TOTAL)
        maxlen = kwargs.get('maxlen', 0)
    
        if not init_state and self.last_state:
            print "last state:", self.last_state
            init_state = self.last_state
        #else:
        #    print "no last state"

        sentence = None
        words = []
        best_words = []
        best_sentence = ""
        best_ratio = -999
        ratio = -999
        for _ in range(tries):
            if init_state != None:
                if init_state[0] == BEGIN:
                    prefix = list(init_state[1:])
                else:
                    prefix = list(init_state)
            else:
                prefix = []
            words = prefix + self.chain.walk(init_state)
            ratio = self.test_sentence_output(words, mor, mot)
           
            if maxlen > 0 and len(self.word_join(words)) > maxlen:
                continue

            if ratio >= 900:
                best_ratio = ratio
                best_words = words
                break
            elif ratio <= -900:
                if DEBUG:
                    print "Very bad sentence, skipping...", ratio
                continue
            elif ratio >= best_ratio:
                if DEBUG:
                    print "Best so far", ratio
                best_ratio = ratio
                best_words = words
                
        if best_ratio:
            if DEBUG:
                print "BEST RATIO:", best_ratio
            self.last_words.extend(self.keywords(best_words))
            best_sentence = self.word_join(best_words)
            
 
        starts = []
        #for i in words:
        #    b = "%s%s" % (i[0].capitalize(), i[1:])
            #if b in self.chain.begin_choices and (b.endswith('NNP') or b.endswith('VBG')):
        #    if b in self.chain.begin_choices and not (b.endswith('DT') or b.endswith('CC')):
        #        starts.append(b)

        #print starts
        self.last_state = []

        #if starts:
        #    startword = starts[random.randint(0, len(starts)-1)]
        #    self.last_state = tuple([ BEGIN ] * (self.state_size - 1) + [startword])

        return best_sentence


TEXTMETHOD=POSifiedText
#TEXTMETHOD=markovify.Text

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
        #if not os.path.exists(datadir):
        #    os.makedirs(datadir)
        #for k, v in self.texts.iteritems():
        #    with codecs.open("%s/%s" % (datadir, k), "w", 'utf-8-sig') as h:
        #        h.write(v)

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

        #items = os.listdir("data")
        #for item in items:
        #    with codecs.open("data/%s" % item, "r", 'utf-8-sig') as h:
        #        self.texts[item] = h.read()

        #items = os.listdir("ad_data")
        #for item in items:
        #    with codecs.open("data/%s" % item, "r", 'utf-8-sig') as h:
        #        self.ads[item] = h.read()


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
            resp = urllib2.urlopen(req)
        except urllib2.HTTPError, err:
            print "ERR:", err
            resp = urllib.urlopen(url)

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

    def quote(self, seed):
        arts.text_model.seed(seed)
        print "'%s' - %s" % (
            arts.text_model.make_sentence(),
            name.get_full_name()
        )
    

class Generator(object):
    def __init__(self, text):
        tokens = nltk.word_tokenize(text)
        self.tags = nltk.pos_tag(tokens)
        #train_sents = nltk.corpus.brown.tagged_sents(categories='news')
        #t0 = nltk.DefaultTagger('NN')
        #t1 = nltk.UnigramTagger(train_sents, backoff=t0)
        #self.tagger = nltk.BigramTagger(train_sents, backoff=t1)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--rss_file")
    parser.add_argument("-d", "--dbfile", default="argen.db")
    parser.add_argument("-f", "--force", action="store_true")
    args = parser.parse_args()


    arts = ArticleStore(args.force)
    arts.load(args.dbfile)
    if args.rss_file:
        with open(args.rss_file, "r") as h:
            for a in h.readlines():
                arts.pull(a)
                arts.save(args.dbfile)     
        sys.exit(0)

    arts.article()
