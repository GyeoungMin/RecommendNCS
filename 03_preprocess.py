import pandas as pd
import re
from konlpy.tag import Okt

data_path = './Data/NCS_translated_data_0_500.csv'
result_data_path = './Data/sample_preprocessed_data.csv'

df_raw = pd.read_csv(data_path)
df_raw.info()
print(df_raw.head())
df = df_raw[['title', 'tr_reviews', 'id']]
df.columns = ['title', 'reviews', 'id']

df = df.dropna()
df.info()

# reviews = df['reviews']
# print(reviews[0])
# print(type(reviews[0]))

with open('./stopwords-ko.txt',  'r', encoding='utf-8') as f:
    stop_words = [line.strip() for line in f if line.strip()]

print(stop_words)

# stop_words = [
#     '의', '가', '이', '은', '들', '는', '좀', '잘', '걍', '과', '도', '를',
#     '으로', '자', '에', '와', '한', '하다', '되다', '있다', '되', '수',
#     '그', '다', '것', '하다', '에서', '입니다', '그리고', '하지만', '그러나',
#     '또한', '저', '나', '너', '우리', '너희', '그녀', '그들', '저희', '때문에',
#     '해서', '하여', '혹은', '및', '또는', '만약', '하지만', '그러면', '이제',
#     '그런데', '아니', '같이', '처럼', '더', '가장', '제일', '많이', '적게', '조금',
#     '정말', '진짜', '아주', '매우', '너무', '항상', '자주', '가끔', '한번',
#     '다시', '계속', '좀', '그만', '이런', '저런', '그런', '어떤', '무슨', '왜',
#     '어떻게', '어디', '언제', '누가', '무엇', '몇', '그때', '지금', '오늘', '내일',
#     '이다', ''
# ]


okt = Okt()
cleaned_sentences = []
for reviews in df['reviews']:
    reviews = re.sub('[^가-힣]', ' ', reviews)
    token_reviews = okt.pos(reviews,stem=True)
    # print(token_reviews)
    df_token = pd.DataFrame(token_reviews, columns=['word', 'class'])
    df_token = df_token[(df_token['class'] == 'Noun') |
                        (df_token['class'] == 'Adjective') |
                        (df_token['class'] == 'Verb')]

    print(df_token)
    words = []
    for word in df_token['word']:
        if 1 < len(word):
            if word not in stop_words:
                words.append(word)
    cleaned_sentence = ' '.join(words)
    cleaned_sentences.append(cleaned_sentence)

# df = df_raw
df['reviews'] = cleaned_sentences
df.dropna(inplace=True)
df.info()

df.to_csv(result_data_path, index=False)

df = pd.read_csv(result_data_path)
df.dropna(inplace=True)

df.to_csv(result_data_path, index=False)