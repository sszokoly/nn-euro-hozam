#!/usr/bin/env python3

import pandas as pd

data = (
    {"asset1":  0.00}, {"asset2":  0.01}, {"asset3":  0.01},
    {"asset1":  0.01}, {"asset2":  0.02}, {"asset3": -0.01},
    {"asset1":  0.01}, {"asset2":  0.01}, {"asset3":  0.01},
    {"asset1":  0.01}, {"asset2": -0.01}, {"asset3": -0.01},
    {"asset1": -0.01}, {"asset2": -0.01}, {"asset3":  0.01},
    {"asset1": -0.01}, {"asset2": -0.02}, {"asset3":  0.01},
    {"asset1":  0.01}, {"asset2":  0.01}, {"asset3": -0.01},
    {"asset1":  0.01}, {"asset2": -0.01}, {"asset3": -0.01},
    {"asset1": -0.01}, {"asset2": -0.01}, {"asset3":  0.01},
    {"asset1": -0.01}, {"asset2": -0.01}, {"asset3":  0.01},
)

asset = [list(d.keys())[0] for d in data]
yield_pct = [list(d.values())[0] for d in data]
df = pd.DataFrame({'asset': asset, 'yield_pct': yield_pct})

# 1. Calculate growth factor (1 + return)
df['growth_factor'] = 1 + df['yield_pct']

# 2. Calculate cumulative product per asset
df['cumulative_growth'] = df.groupby('asset')['growth_factor'].cumprod()

# 3. Convert back to cumulative yield (optional: subtract 1)
df['compound_yield'] = df['cumulative_growth'] - 1

print(df)
