# NewsGen:  Your friendly neighborhood article generator

NewsGen provides tooling to pull corpuses of articles in order to generate new
articles utlizing parts of speech tagging and markov chain natural language
generation techniques.

## Generation techniques

At the core, NewsGen, uses the excellent NLTK project to parse sentences and identify parts of
speech.  Markovify is used to generate sentences, but we add a few twists.

Markov chains by default are pretty effective at creating reasonable sounding
gobbledygook, but are ineffective at creating a reasonably coherent connection
between junk sentences.  If that is a thing at all.

In order to do slightly better, we do two things:

1) Provide a mechanism to cull the corpus based on keywords to so that we have
a more coherent starting set of data.

2) Generate a lot of candidate sentences and use Levenshtein distance to
attempt to pick the most coherent candidate sentence for our generated
articles.

# Usage

## View help

```
$ python3 ./newsgen.py -h
```


## Setup

You will want to create an 'rss file' basically a text file containing a list
of pages and rss feeds to pull from.  'left.txt', and 'right.txt' provide some
sources leaning one way or the other.

You will save the article in a db file that you get to name.


## Pull data

You can pull in corpuses of data by....

```
$ python3 ./newsgen.py -r <rss file> -d <db file> pull
```

## Generate an article

You can generate articles, and optionally push articles directly to wordpress.
Note: Your wordpress setup must have basic authentication access enabled and a
user with the appropriate permissions.

```
$ python3 ./newsgen.py -r <rss file> -d <db file> [-H optional wordpress host] [-u optional wordpress user] [-p optional wordpress password ] article [optional search criteria]
```


