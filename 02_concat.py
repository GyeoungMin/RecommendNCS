import pandas as pd
import glob

path = './Data'
data_path = glob.glob(path)
print(data_path)

df = pd.DataFrame()

for path in data_path:
    df_temp = pd.read_csv(path)
    df_temp.dropna(inplace=True)
    df = pd.concat([df, df_temp], ignore_index=True)

df.info()
print(df.head())

df.to_csv('./Data/NCS_Data.csv', index=False)
