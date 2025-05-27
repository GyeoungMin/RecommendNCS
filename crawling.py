import pandas as pd
from Crawler import Crawler

# start_index와 end_index 조절만 하면 됩니다.
start_index = 0
end_index = 1
crawler = Crawler()
crawler.start_driver()
titles, reviews, ids = crawler.musics(start_index=start_index, end_index=end_index)
df = pd.DataFrame({'title':titles, 'reviews':reviews, 'id':ids})

df.info()
print(df.head())

df.to_csv(f'./Data/NCS_Crawling_{start_index}_{end_index}.csv', index=False)