from pathlib import Path


def generate_transactions(n_normal: int = 110_000, seed: int = 42, days: int = 90):
    from app.ml.synthetic import generate_transactions as gen

    return gen(n_normal=n_normal, seed=seed, days=days)


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parents[1] / "data"
    out_dir.mkdir(exist_ok=True)
    frame = generate_transactions()
    path = out_dir / "transactions.csv"
    frame.to_csv(path, index=False)
    fraud = int(frame["is_fraud"].sum())
    print(f"wrote {len(frame)} rows ({fraud} fraud) -> {path}")
