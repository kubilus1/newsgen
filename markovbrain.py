import re
import string

import nltk
import names
import random
import markovify
from unidecode import unidecode
from fuzzywuzzy import process


DEBUG=False
STATESIZE=2
DEFAULT_MAX_OVERLAP_RATIO = 0.7
DEFAULT_MAX_OVERLAP_TOTAL = 15
DEFAULT_TRIES = 40

DEFAULT_MIN_OVERLAP_RATIO = 0.3
DEFAULT_MIN_OVERLAP_TOTAL = 15


class MKVBrain(object):
    
    models = {}
    in_text = ''

    def __init__(self, in_text=""):
        self.in_text = in_text

    def build_model(self, seed, search, key):
        model = self.models.get(key) 
        if not model:
            model = POSifiedText(self.in_text)
            self.models[key] = model

    def get_model(self, key, search=None, search_key='article_text'):
        model = self.models.get(key) 
        return model

    def paragraph(self, model):
        outstr = ""
        for i in range(random.randrange(3,7)):
            outstr = "%s %s" % (
                outstr,
                model.make_sentence(tries=100)
            )
        return outstr


    def tagline(self, seed=None, search=None, search_key='article_text'):
        text_model = self.get_model('article_text', search, search_key)
        print(text_model.make_sentence(maxlen=90, tries=20))
  

    def title(
            self, 
            seed=None, 
            search=None, 
            search_key='article_text',
            model=None):

        if not model:
            title_model = self.get_model('article_title', search, search_key)
            text_model = self.get_model('article_text', search, search_key)
            model = markovify.combine(
                [ title_model, text_model ],
                [ 100, 1 ]
            )
            
            if seed:
                model.seed(seed)

        raw_title = model.make_sentence(maxlen=120, tries=50)
        ascii_title = ''.join(
            [x for x in raw_title if ord(x) < 128]).replace('"', '')
        
        title = string.capwords(ascii_title)
        return title


    def sentences(self, num=3, seed=None, search=None, search_key='article_text'):
        text_model = self.get_model('article_text', search, search_key)
        if seed:
            text_model.seed(seed)

        resp = ""
        for i in range(num):
            resp += "%s " % text_model.make_sentence(tries=100)
        
        print(resp)


    def get_article_text(self, seed, search, search_key):
        title_model = self.get_model('article_title', search, search_key)
        text_model = self.get_model('article_text', search, search_key)
        combo_model = markovify.combine(
            [ title_model, text_model ],
            [ 100, 1 ]
        )
        
        if seed:
            combo_model.seed(seed)

        article_title = self.title(model=combo_model)
        text_model.last_words = combo_model.last_words
        
        article_title = self.title(model=combo_model)
        
        article_text = ""
        for i in range(random.randrange(3,7)):
            article_text += "\n%s\n" % self.paragraph(text_model)

        # ktags = combo_model.keyword_tags
        # ktags_sorted = sorted(ktags, key = ktags.count, reverse=True)
        # unique_ktags = [
        #     x for i, x in enumerate(ktags_sorted) if x not in ktags_sorted[0:i]
        # ]

        return article_title, article_text
    

class POSifiedText(markovify.Text):
   
    last_sentences = []
    last_words = []
    keyword_tags = []
    last_state = None

    def word_split(self, sentence):
        words = re.split(self.word_split_pattern, sentence)
        words = [ "::".join(tag) for tag in nltk.pos_tag(words) ]
        return words

    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence

    def test_sentence_output(self, words, intext, max_overlap_ratio, max_overlap_total):
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
            if gram_joined in intext:
                return False

        return True

    def reset_text(self):
        print("Resetting last_words...")
        self.last_words = []
        self.keyword_tags = []
        random.seed()

    
    def tags(self, words):
        words = [ w.split('::')[0].lower() for w in words if w.split('::')[1] in ['NNP','NNPS' ] and w.split('::')[0].isalpha()]
        return words

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
        reject_pat = re.compile(r"(\.\.\.)|(Tumblr)|(http)|(#\D)|(Infowar)|(Infowars)|(Alex Jones Show)|(^')|('$)|\s'|'\s|[\"(\(\)\[\])]|(\n)|(^\s*$)")
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
                print("REJECTING:", decoded)
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
        maxlen = kwargs.get('maxlen', 9999)
        
        if not init_state and self.last_state:
            print("last state:", self.last_state)
            init_state = self.last_state
        #else:
        #    print("no last state")

        sentence = None
        words = []
        best_words = []
        best_sentence = ""
        best_ratio = -999
        ratio = -999


        sentences = []

        for _ in range(tries):
            if init_state != None:
                if init_state[0] == BEGIN:
                    prefix = list(init_state[1:])
                else:
                    prefix = list(init_state)
            else:
                prefix = []
            words = prefix + self.chain.walk(init_state)
       
            # Make sure the sentence is not too similar to original corpus
            if not self.test_sentence_output(words, self.rejoined_text, mor, mot):
                continue
            # Now make sure sentence is not too similar to generated text
            if not self.test_sentence_output(words, self.last_words, mor, mot):
                continue
            
            sentence = self.word_join(words)

            if len(sentence) > maxlen:
                continue

            sentences.append(sentence)

        if DEBUG:
            print("LAST WORDS:", self.last_words)

        joined = self.word_join(self.last_words) 
        best_sentence, best_ratio = process.extractOne(joined, sentences)

        #if best_ratio:
        if DEBUG:
            print("BEST RATIO:", best_ratio)
        best_words = best_sentence.split()
        self.keyword_tags.extend(self.tags(self.word_split(best_sentence)))
        #best_sentence = self.word_join(best_words)
        #self.last_words.extend(self.keywords(best_words))
        self.last_words.extend(best_words)
        return best_sentence

