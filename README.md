# Hydride-Tc-Predictor
An interpretable predictor for superconducting critical temperature (Tc) in hydrogen-based superconductors from vasprun.

## Features

- Interpretable symbolic-regression model
- Direct parsing of `vasprun.xml`
- Fast estimation of `Tc` from DOS-based descriptors
- Output of key features, including pressure, DOS integrals, band gap, and screening index `S`

## Method

The predictor estimates Tc using a compact symbolic-regression formula derived from DOS descriptors near the Fermi level:

Tc = 3930.62 * sqrt(IDOS_H_p / N_H) * (IDOS_H / IDOS_Tot)
     - 0.17 * cbrt(IDOS_H / IDOS_X) * P
     - 4.69

where:
- `IDOS_H`: integrated hydrogen DOS within the selected energy window
- `IDOS_H_p`: integrated hydrogen p-orbital DOS
- `IDOS_Tot`: total integrated DOS
- `IDOS_X`: integrated DOS from non-hydrogen elements
- `N_H`: number of hydrogen atoms
- `P`: pressure extracted from the final stress tensor

## Requirements

- Python 3.10+
- numpy
- pymatgen

## Use
git clone <your-repo-url>
cd <your-repo-name>
```bash
pip install -r requirements.txt




