"""Visualise l'evolution de l'entrainement genetique a partir d'un CSV.

Usage:
    python Training/visualize_training.py
    python Training/visualize_training.py --csv training_results.csv --save training_evolution.png
    python Training/visualize_training.py --no-show
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt


REQUIRED_COLUMNS = ["Generation", "Avg", "Max", "Min"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Affiche des courbes pour suivre la progression de l'entrainement."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("training_results.csv"),
        help="Chemin vers le fichier CSV de resultats.",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Chemin de sortie pour sauvegarder la figure (ex: training_evolution.png).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="N'affiche pas la fenetre matplotlib (utile en execution distante).",
    )
    return parser.parse_args()


def load_training_data(csv_path: Path) -> Dict[str, List[float]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Fichier CSV introuvable: {csv_path}")

    data: Dict[str, List[float]] = {key: [] for key in REQUIRED_COLUMNS}

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Le CSV est vide ou invalide.")

        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"Colonnes manquantes dans le CSV: {missing}")

        for row in reader:
            data["Generation"].append(float(row["Generation"]))
            data["Avg"].append(float(row["Avg"]))
            data["Max"].append(float(row["Max"]))
            data["Min"].append(float(row["Min"]))

    if not data["Generation"]:
        raise ValueError("Aucune ligne de donnees trouvee dans le CSV.")

    return data


def build_figure(data: Dict[str, List[float]]) -> plt.Figure:
    generations = data["Generation"]
    avg = data["Avg"]
    max_values = data["Max"]
    min_values = data["Min"]

    fig, ax_scores = plt.subplots(1, 1, figsize=(12, 6))
    fig.suptitle("Evolution de l'entrainement genetique", fontsize=14, fontweight="bold")

    ax_scores.plot(generations, avg, label="Avg", linewidth=2)
    ax_scores.plot(generations, max_values, label="Max", alpha=0.9)
    ax_scores.plot(generations, min_values, label="Min", alpha=0.9)
    ax_scores.fill_between(generations, min_values, max_values, alpha=0.1)
    ax_scores.set_xlabel("Generation")
    ax_scores.set_ylabel("Fitness")
    ax_scores.grid(True, alpha=0.25)
    ax_scores.legend(loc="best")

    fig.tight_layout()
    return fig


def main() -> None:
    args = parse_args()

    data = load_training_data(args.csv)
    figure = build_figure(data)

    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.save, dpi=160)
        print(f"Figure sauvegardee: {args.save}")

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
