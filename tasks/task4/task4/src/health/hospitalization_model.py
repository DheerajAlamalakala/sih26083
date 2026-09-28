"""Thin named wrapper around baseline_risk's hospitalization model,
mirroring mortality_model.py.
"""
from src.health.baseline_risk import train_baseline_models, evaluate

TARGET = "daily_hospitalizations"

def train_hospitalization_model(train_df):
    return train_baseline_models(train_df)[TARGET]

def evaluate_hospitalization_model(model, eval_df):
    return evaluate({TARGET: model}, eval_df)
