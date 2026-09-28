"""CLI: build features -> aggregate daily -> generate synthetic labels -> write CSV."""
import argparse
from src.health.feature_builder import build_features
from src.health.daily_aggregation import aggregate_to_daily
from src.health.generate_synthetic_health import generate_synthetic_health

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stage1", default="data/processed/thermal/stage1_output.csv")
    p.add_argument("--vulnerability", default="data/processed/vulnerability/ward_vulnerability.csv")
    p.add_argument("--out", default="data/synthetic/health_outcomes_demo.csv")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    features = build_features(args.stage1, args.vulnerability)
    daily = aggregate_to_daily(features)
    synthetic = generate_synthetic_health(daily, seed=args.seed)
    synthetic.to_csv(args.out, index=False)
    print(f"Wrote {len(synthetic)} ward-day rows to {args.out}")
