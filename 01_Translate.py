import pandas as pd
from deep_translator import GoogleTranslator

def split_comments_by_char_limit(comments, char_limit=4500):
    batches = []
    current_batch = []
    current_length = 0

    for comment in comments.split('\n'):
        comment.replace('\n\n', '\n')
        # 줄바꿈 포함해서 계산
        comment_length = len(comment) + 1  # '\n' 포함

        # 만약 현재 배치에 넣으면 제한 초과 시
        if current_length + comment_length > char_limit:
            # 지금까지 쌓인 댓글을 하나의 문자열로 만들어 batches에 추가
            batches.append('\n'.join(current_batch))
            # 새로운 배치 시작
            current_batch = [comment]
            current_length = comment_length
        else:
            current_batch.append(comment)
            current_length += comment_length

    # 마지막 남은 배치 처리
    if current_batch:
        batches.append('\n'.join(current_batch))

    return batches

def translate_review(text):
    try:
        if pd.isna(text) or not text.strip():
            return ''
        batches = split_comments_by_char_limit(text)
        translated_batches = translator.translate_batch(batches)
        return '\n'.join(translated_batches)
    except Exception as e:
        print(f'번역 실패 : {e}')
        return text

translator = GoogleTranslator(source='auto', target='ko')

df = pd.read_csv('./Data/NCS_Crawling_0_500_backup.csv')

# 번역 적용
df['tr_reviews'] = df['reviews'].apply(translate_review)

# 결과 저장 (선택)
df.to_csv('./Data/sample_NCS_translated_data.csv', index=False)

# 결과 출력 (선택)
print(df.head())
