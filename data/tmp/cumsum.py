#!/usr/bin/env python3

import pandas as pd

data = (
    {"asset1":  0}, {"asset2":  1}, {"asset3":  1},
    {"asset1":  1}, {"asset2":  2}, {"asset3": -1},
    {"asset1":  1}, {"asset2":  1}, {"asset3":  1},
    {"asset1":  1}, {"asset2": -1}, {"asset3": -1},
    {"asset1": -1}, {"asset2": -1}, {"asset3":  1},
    {"asset1": -1}, {"asset2": -2}, {"asset3":  1},
    {"asset1":  1}, {"asset2":  1}, {"asset3": -1},
    {"asset1":  1}, {"asset2": -1}, {"asset3": -1},
    {"asset1": -1}, {"asset2": -1}, {"asset3":  1},
    {"asset1": -1}, {"asset2": -1}, {"asset3":  1},
    #           1              -2               2  
)

asset = [list(d.keys())[0] for d in data]
values = [list(d.values())[0] for d in data]
df = pd.DataFrame({'asset': asset, 'value': values})
df['cumsum_value'] = df.groupby('asset')['value'].cumsum()
print(df)
