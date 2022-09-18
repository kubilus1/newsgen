#!/usr/bin/env python3

import fire
import json
import os
import numpy as np
#import tensorflow as tf
import tensorflow.compat.v1 as tf

#import model, sample, encoder
from gpt_2_simple.src import model, sample, encoder, memory_saving_gradients
from fuzzywuzzy import process
from nltk import tokenize
import nltk

from aitextgen import aitextgen

class TextGen(object):

    def __init__(
        self,
        model_name = None,
        models_dir = 'models',
        checkpoint_dir = 'checkpoint',
        run_name = 'run1',
        batch_size = 1,
        nsamples = 1,
        length = None,
        seed=None,
        temperature=0.7,
        top_k=0,
        top_p=1,
    ):
        """
        :model_name=124M : String, which model to use
        :seed=None : Integer seed for random number generators, fix seed to reproduce
        results
        :nsamples=1 : Number of samples to return total
        :batch_size=1 : Number of batches (only affects speed/memory).  Must divide nsamples.
        :length=None : Number of tokens in generated text, if None (default), is
        determined by model hyperparameters
        :temperature=1 : Float value controlling randomness in boltzmann
        distribution. Lower temperature results in less random completions. As the
        temperature approaches zero, the model will become deterministic and
        repetitive. Higher temperature results in more random completions.
        :top_k=0 : Integer value controlling diversity. 1 means only 1 word is
        considered for each step (token), resulting in deterministic completions,
        while 40 means 40 words are considered at each step. 0 (default) is a
        special setting meaning no restrictions. 40 generally is a good value.
        :models_dir : path to parent folder containing model subfolders
        (i.e. contains the <model_name> folder)
        """

        nltk.download('stopwords')
        self.ai = aitextgen(model_folder="trained_model", to_gpu=False)
        self.temperature = temperature

        return

        self.model_name = model_name
        self.models_dir = os.path.expanduser(os.path.expandvars(models_dir))
        self.run_name = run_name

        if model_name:
            self.checkpoint_path = os.path.join(models_dir, model_name)
        else:
            self.checkpoint_path = os.path.join(checkpoint_dir, run_name)

        print(f"Using model: {self.checkpoint_path}")
        self.enc = encoder.get_encoder(self.checkpoint_path)
        self.hparams = model.default_hparams()
        with open(os.path.join(self.checkpoint_path, 'hparams.json')) as f:
            self.hparams.override_from_dict(json.load(f))

        if batch_size is None:
            batch_size = 1
        assert nsamples % batch_size == 0

        if length is None:
            length = self.hparams.n_ctx // 2
        elif length > self.hparams.n_ctx:
            raise ValueError("Can't get samples longer than window size: %s" % self.hparams.n_ctx)

        tf.disable_eager_execution()
        #self.sess._default_graph_context_manager = self.sess.graph.as_default()
        #self.sess =  tf.Session(graph=tf.Graph())

        g = tf.Graph()
        with g.as_default():

            self.context = tf.placeholder(tf.int32, [batch_size, None])
            np.random.seed(seed)
            tf.set_random_seed(seed)
            self.output = sample.sample_sequence(
                hparams=self.hparams, length=length,
                context=self.context,
                batch_size=batch_size,
                temperature=temperature, top_k=top_k, top_p=top_p
            )

            saver = tf.train.Saver()
            ckpt = tf.train.latest_checkpoint(self.checkpoint_path)
            self.sess =  tf.Session(graph=g)
        saver.restore(self.sess, ckpt)

        # with tf.Session(graph=tf.Graph()) as sess:
        #     context = tf.placeholder(tf.int32, [batch_size, None])
        #     np.random.seed(seed)
        #     tf.set_random_seed(seed)
        #     output = sample.sample_sequence(
        #         hparams=self.hparams, length=length,
        #         context=context,
        #         batch_size=batch_size,
        #         temperature=temperature, top_k=top_k, top_p=top_p
        #     )

        #     saver = tf.train.Saver()
        #     ckpt = tf.train.latest_checkpoint(self.checkpoint_path)
        #     saver.restore(sess, ckpt)


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type:
            print("Closing session.")
            #self.sess.close()

    #def close(self):
    #    self.sess.close()

    def interact_model(
        self,
    ):
        """
        Interactively run the model
        """
        while True:
            raw_text = input("Model prompt >>> ")
            while not raw_text:
                print('Prompt should not be empty!')
                raw_text = input("Model prompt >>> ")
            text = self.get_text(raw_text)
            print(text)
            continue

    def get_text(self, in_text="", endtoken="<|endoftext|>", max_cycles=3,
            as_list=False, post_process=True, remove_prefix=True):
        
        initial_prompt = in_text
        text = ""
        for i in range(max_cycles):
            if in_text:
                outtext = self.ai.generate_one(
                    prompt=in_text,
                    max_length=512,
                    temperature=self.temperature
                )
            else:
                outtext = self.ai.generate_one(
                    max_length=512,
                    temperature=self.temperature
                )

            if remove_prefix and i == 0:
                # If on the first cycle, drop the prompt input
                outtext = outtext.replace(initial_prompt, "", 1)

            #print(outtext)
            endtextpos = outtext.find(endtoken)
            if endtextpos == -1:
                #print(f"CONTINUED! {i}")
                text += outtext
                #lastlines = "\n".join(outtext.split('\n')[-10:])
                lastlines = outtext[-128:]
                #print(f"LAST LINES: {lastlines}")
                in_text = lastlines
            else:
                #print("END DETECTED!")
                text += outtext[:endtextpos]
                break

        #print("####ORIG####")
        #print(text)
        #print("####DEDUPED###")

        if not post_process:
            return text

        lastperiod = text.rfind('.')
        text = text[:(lastperiod+1)]

        #lines = text.split('.')
        #lines = tokenize.sent_tokenize(text)
        lines = re.split('(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)

        deduped = process.dedupe(lines, threshold=92)
        if as_list:
            return list(deduped)

        text = "  ".join(deduped)
        return text


        ttt = tokenize.TextTilingTokenizer()
        tiles = ttt.tokenize(text)
        print("TILES ....")
        print(len(tiles))
        print(tiles)

        outtext = ""
        for t in tiles:
            outtext += f"{t}\n"
    
        return outtext

    def _get_text(self, in_text="", endtoken="<|endoftext|>", max_cycles=3,
            as_list=False, post_process=True, remove_prefix=True):
        
        initial_prompt = in_text
        text = ""
        for i in range(max_cycles):
            if in_text:
                context_tokens = self.enc.encode(in_text)
                out = self.sess.run(self.output, feed_dict={
                    self.context: [context_tokens]
                })
            else:
                out = self.sess.run()
            #dir(out)
            #print(out)
            outtext = self.enc.decode(out[0])
            if remove_prefix and i == 0:
                # If on the first cycle, drop the prompt input
                outtext = outtext.replace(initial_prompt, "", 1)

            #print(outtext)
            endtextpos = outtext.find(endtoken)
            if endtextpos == -1:
                #print(f"CONTINUED! {i}")
                text += outtext
                #lastlines = "\n".join(outtext.split('\n')[-10:])
                lastlines = outtext[-128:]
                #print(f"LAST LINES: {lastlines}")
                in_text = lastlines
            else:
                #print("END DETECTED!")
                text += outtext[:endtextpos]
                break

        #print("####ORIG####")
        #print(text)
        #print("####DEDUPED###")

        if not post_process:
            return text

        lastperiod = text.rfind('.')
        text = text[:(lastperiod+1)]

        return text


        #lines = text.split('.')
        lines = tokenize.sent_tokenize(text)

        deduped = process.dedupe(lines)
        if as_list:
            return list(deduped)



        text = "\n".join(deduped)
        
        ttt = tokenize.TextTilingTokenizer()
        tiles = ttt.tokenize(text)
        print("TILES ....")
        print(len(tiles))
        print(tiles)

        outtext = ""
        for t in tiles:
            outtext += f"{t}\n"
    
        return outtext

# def dedupe(contains_dupes, threshold=70, scorer=fuzz.token_set_ratio):
# 
#     extractor = []
# 
#     # iterate over items in *contains_dupes*
#     for item in contains_dupes:
#         # return all duplicate matches found
#         matches = extract(item, contains_dupes, limit=None, scorer=scorer)
#         # filter matches based on the threshold
#         filtered = [x for x in matches if x[1] > threshold]
#         # if there is only 1 item in *filtered*, no duplicates were found so append to *extracted*
#         if len(filtered) == 1:
#             extractor.append(filtered[0][0])
# 
#         else:
#             # alpha sort
#             filtered = sorted(filtered, key=lambda x: x[0])
#             # length sort
#             filter_sort = sorted(filtered, key=lambda x: len(x[0]), reverse=True)
#             # take first item as our 'canonical example'
#             extractor.append(filter_sort[0][0])
# 
#     # uniquify *extractor* list
#     keys = {}
#     for e in extractor:
#         keys[e] = 1
#     extractor = keys.keys()
# 
#     # check that extractor differs from contain_dupes (e.g. duplicates were found)
#     # if not, then return the original list
#     if len(extractor) == len(contains_dupes):
#         return contains_dupes
#     else:
#         return extractor


if __name__ == '__main__':
    
    with TextGen() as gtext:
        fire.Fire(gtext.interact_model)

