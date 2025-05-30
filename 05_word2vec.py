import pandas as pd
from gensim.models import Word2Vec

df_review = pd.read_csv('./Data/sample_preprocessed_data.csv')
df_review.info()

reviews = list(df_review['reviews'])
print(df_review.iloc[0,0], reviews[0])

tokens = []
for sentence in reviews:
    token = sentence.split()
    tokens.append(token)
print(tokens[0:2])

embedding_model = Word2Vec(tokens, vector_size=100, window=4,
                           min_count=15, workers=4, epochs=100, sg=1)
embedding_model.save('./models/word2vec_music_review.model')
print(list(embedding_model.wv.index_to_key))
print(len(embedding_model.wv.index_to_key))