import pandas as pd
from Crawler import Crawler

# start_index와 end_index 조절만 하면 됩니다.
start_index = 751
end_index = 1000
crawler = Crawler()
crawler.start_driver()
titles, reviews, ids = crawler.musics(start_index=start_index, end_index=end_index)
crawler.quit_driver()
df = pd.DataFrame({'title':titles, 'reviews':reviews, 'id':ids})

df.info()
print(df.head())

df.to_csv(f'./Data/NCS_Crawling_{start_index}_{end_index if not None else "end"}.csv', index=False)