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

## Install
```bash
git clone https://github.com/chen121760/Hydride-Tc-Predictor.git
cd Hydride-Tc-Predictor
pip install -r requirements.txt
chmod +x H-Tc_predicter.py
export PATH="$(pwd):$PATH" #temp add to PATH
```

## Usage
Show help:
```bash
H-Tc_predicter -h
```
Process all subfolders under a parent directory(such as calculate):
```bash
H-Tc_predicter calculate/
```
Process specific folders:
```bash
H-Tc_predicter folder1 folder2 folder3
```

## Citation 
If you use this code in your research, please cite us，thanks :)

```bibtex
@article{CHEN2026102073,
title = {Interpretable descriptors enable prediction of hydrogen-based superconductors at moderate pressures},
journal = {Materials Today Physics},
volume = {63},
pages = {102073},
year = {2026},
issn = {2542-5293},
doi = {https://doi.org/10.1016/j.mtphys.2026.102073},
url = {https://www.sciencedirect.com/science/article/pii/S2542529326000647},
author = {Jiawei Chen and Junhao Peng and Yanwei Liang and Renhai Wang and Huafeng Dong and Wei Zhang},
}
