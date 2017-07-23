import re
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

        #ret = self.consistency_check(words)
        return True

    def reset_text(self):
        print "Resetting last_words..."
        self.last_words = []
        self.keyword_tags = []
        random.seed()

    
    def tags(self, words):
        words = [ w.split('::')[0].rstrip('s').lower() for w in words if w.split('::')[1] in ['NNP','NNPS' ]]
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
            sentences.append(sentence)

                
        best_sentence, best_ratio = process.extractOne(self.last_words, sentences)

        if best_ratio:
            if DEBUG:
                print "BEST RATIO:", best_ratio
            best_words = best_sentence.split()
            self.keyword_tags.extend(self.tags(best_words))
            #best_sentence = self.word_join(best_words)
            self.last_words.extend(self.keywords(best_words))
        return best_sentence

