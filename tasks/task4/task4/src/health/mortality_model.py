"""Thin named wrapper around baseline_risk's mortality model, so the
repo matches the playbook's expected file layout. Logic lives in
baseline_risk.py (train_baseline_models / evaluate).
"""
from src.health.baseline_risk import train_baseline_models, evaluate

TARGET = "daily_mortality"

def train_mortality_model(train_df):
    return train_baseline_models(train_df)[TARGET]

def evaluate_mortality_model(model, eval_df):
    return evaluate({TARGET: model}, eval_df)
