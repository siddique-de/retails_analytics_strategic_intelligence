"""
Shared helpers and seeded RNG used by every generator module.
"""

import numpy as np
import pandas as pd
from config import RANDOM_SEED

rng = np.random.default_rng(RANDOM_SEED)


def weighted_choice(options: list, weights: list, size: int = 1):
    """Return an array of choices drawn from *options* with *weights*."""
    weights = np.array(weights, dtype=float)
    weights /= weights.sum()
    return rng.choice(options, size=size, p=weights)


def date_range_array(start: str, end: str, n: int) -> np.ndarray:
    """Return *n* random dates (as numpy datetime64) between start and end."""
    s = np.datetime64(start, "D")
    e = np.datetime64(end,   "D")
    days = int((e - s) / np.timedelta64(1, "D"))
    offsets = rng.integers(0, days, size=n)
    return s + offsets.astype("timedelta64[D]")


def save_csv(df: pd.DataFrame, path: str, **kwargs) -> None:
    """Save dataframe to CSV, creating parent directories as needed."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, **kwargs)
    mb = os.path.getsize(path) / 1_048_576
    print(f"  → {path}  ({len(df):,} rows, {mb:.1f} MB)")


def save_parquet(df: pd.DataFrame, path: str) -> None:
    """Save dataframe to Parquet, creating parent directories as needed."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    mb = os.path.getsize(path) / 1_048_576
    print(f"  → {path}  ({len(df):,} rows, {mb:.1f} MB)")
