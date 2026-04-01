#!/usr/bin/env python3
import numpy as np
from pymatgen.io.vasp.outputs import Vasprun
from pymatgen.electronic_structure.core import OrbitalType
from pymatgen.core import Element
import os


class TcPredictor:

    def __init__(self, energy_min=-1.0, energy_max=1.0):
        self.energy_min = energy_min
        self.energy_max = energy_max

        self.P = None
        self.IDOS_H = None
        self.IDOS_H_p = None
        self.IDOS_Tot = None
        self.IDOS_X = None      # X=non_H
        self.N_H = None
        self.N_Tot = None
        self.Tc = None
        self.spacegroup = None  # Space group number
        self.S = None           # Superconducting performance indicator
        self.bandgap = None     # Band gap (eV)          
    
    
    def predict_tc(self, vasprun_path="vasprun.xml", bandgap_threshold=None):
        """
        Predict Tc value

        Parameters:
            vasprun_path: Path to vasprun.xml file
            bandgap_threshold: Band gap threshold (eV), if provided, perform early filtering

        Returns:
            Tc value, or None if filtered by bandgap threshold
        """
        vasprun = self._load_vasprun(vasprun_path)

        complete_dos = vasprun.complete_dos
        self._validate_pdos(complete_dos)

        # Calculate bandgap early for filtering
        self.bandgap = self._calculate_bandgap(complete_dos)

        # If threshold is provided, perform early filtering
        if bandgap_threshold is not None:
            if self.bandgap is not None and self.bandgap >= bandgap_threshold:
                # Does not meet requirements, return None to indicate filtered
                return None

        # Passed filtering, continue with subsequent calculations
        self.P = self._extract_pressure(vasprun)

        structure = complete_dos.structure
        self.N_Tot, self.N_H = self._get_structure_info(structure)
        self.spacegroup = self._get_spacegroup(structure)
        
        fermi_level = vasprun.efermi
        energies, total_dos, selected_indices = self._prepare_energy_grid(
            complete_dos, fermi_level
        )
        
        self.IDOS_Tot = self._calculate_total_idos(energies, total_dos, selected_indices)
        self.IDOS_H = self._calculate_hydrogen_idos(complete_dos, energies, selected_indices)
        self.IDOS_H_p = self._calculate_hydrogen_p_idos(complete_dos, energies, selected_indices)
        self.IDOS_X = self._calculate_nonhydrogen_idos(complete_dos, energies, selected_indices)

        self.Tc = self._calculate_tc_formula()
        self.S = self._calculate_performance_indicator()

        return self.Tc
    
    
    def get_features(self):
        return {
            'P': self.P,
            'IDOS_H': self.IDOS_H,
            'IDOS_H_p': self.IDOS_H_p,
            'IDOS_Tot': self.IDOS_Tot,
            'IDOS_X': self.IDOS_X,
            'N_H': self.N_H,
            'N_Tot': self.N_Tot,
            'Tc': self.Tc,
            'spacegroup': self.spacegroup,
            'S': self.S,
            'bandgap': self.bandgap
        }
    
    
    def save_results(self, output_file="Tc_pred.txt"):
        with open(output_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("Extracted Features for Tc Prediction\n")
            f.write("="*70 + "\n\n")
            
            f.write("Input Parameters:\n")
            f.write(f"  Energy window: [{self.energy_min:.2f}, {self.energy_max:.2f}] eV\n\n")
            
            f.write("Extracted Features:\n")
            f.write(f"  Pressure (P):                                    {self.P:.1f} GPa\n")
            f.write(f"  Space Group:                                     {self.spacegroup}\n")
            f.write(f"  Hydrogen integrated DOS (IDOS_H):                {self.IDOS_H:.6f}\n")
            f.write(f"  Hydrogen p-orbital integrated DOS (IDOS_H_p):    {self.IDOS_H_p:.6f}\n")
            f.write(f"  Total integrated DOS (IDOS_Tot):                 {self.IDOS_Tot:.6f}\n")
            f.write(f"  Non-hydrogen integrated DOS (IDOS_X):            {self.IDOS_X:.6f}\n")
            f.write(f"  Number of hydrogen atoms (N_H):                  {self.N_H}\n")
            f.write(f"  Number of total atoms (N_Tot):                   {self.N_Tot}\n")

            bandgap_str = f"{self.bandgap:.6f}" if self.bandgap is not None else "N/A"
            f.write(f"  Band gap (Eg):                                   {bandgap_str} eV\n\n")

            f.write("Prediction:\n")
            f.write(f"  Tc_predicted: {self.Tc:.3f} K\n")
            f.write(f"  Superconducting performance indicator (S): {self.S:.6f}\n")
    
    
    
    def _load_vasprun(self, vasprun_path):
        if not os.path.exists(vasprun_path):
            raise FileNotFoundError(f"File not found: {vasprun_path}")

        # Check if vasprun.xml is complete
        with open(vasprun_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read last few lines to check for completion
            f.seek(0, 2)  # Go to end of file
            file_size = f.tell()
            # Read last 1000 bytes (should be enough to find </modeling>)
            f.seek(max(0, file_size - 1000))
            last_content = f.read()

            if '</modeling>' not in last_content:
                raise ValueError("ERROR: vasprun.xml is incomplete - calculation may still be running or crashed")

        try:
            vasprun = Vasprun(vasprun_path, parse_dos=True)
        except Exception as e:
            raise ValueError(f"ERROR: Failed to parse vasprun.xml - file may be incomplete or corrupted\n{e}")

        return vasprun
    
    
    def _validate_pdos(self, complete_dos):
        if not hasattr(complete_dos, 'pdos') or complete_dos.pdos is None or len(complete_dos.pdos) == 0:
            raise ValueError(
                "ERROR:no PDOS in vasprun.xml\n"
                "Please set LORBIT = 10 or 11"
            )
    
    
    def _extract_pressure(self, vasprun):
        final_stress_kB = self._get_final_stress_kB(vasprun)
        stress_trace_kB = np.trace(final_stress_kB)
        return (stress_trace_kB / 3.0) * 0.1  # Convert to GPa
    
    
    def _get_final_stress_kB(self, vasprun_obj):
        """Extract stress tensor from vasprun.xml"""
        if vasprun_obj is None or not vasprun_obj.ionic_steps:
            raise ValueError("ERROR: no ionic steps found in vasprun.xml")

        step = vasprun_obj.ionic_steps[-1]
        if "stress" not in step or step["stress"] is None:
            raise ValueError("ERROR: no stress data found in vasprun.xml")

        stress_tensor = np.array(step["stress"], dtype=float)
        if stress_tensor.shape != (3, 3):
            raise ValueError(f"ERROR: stress tensor has invalid shape {stress_tensor.shape}, expected (3, 3)")

        return stress_tensor
    
    
    def _get_structure_info(self, structure):
        N_Tot = len(structure)
        N_H = sum(1 for site in structure if site.specie.symbol == 'H')
        return N_Tot, N_H


    def _get_spacegroup(self, structure):
        """Extract space group number from structure"""
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            sga = SpacegroupAnalyzer(structure)
            return sga.get_space_group_number()
        except Exception as e:
            print(f"WARNING: Could not determine space group: {e}")
            return None


    def _calculate_bandgap(self, complete_dos):
        """
        Calculate band gap from complete DOS
        Returns band gap in eV (0.0 for metals)
        """
        try:
            gap_info = complete_dos.get_gap()
            return gap_info
        except Exception as e:
            print(f"WARNING: Could not calculate band gap: {e}")
            return None

    
    def _prepare_energy_grid(self, complete_dos, fermi_level):
        energies = complete_dos.energies - fermi_level
        total_dos = complete_dos.get_densities()
        
        selected_indices = (energies >= self.energy_min) & (energies <= self.energy_max)
        
        return energies, total_dos, selected_indices
    
    
    def _calculate_total_idos(self, energies, total_dos, selected_indices):
        energies_in_range = energies[selected_indices]
        total_dos_in_range = total_dos[selected_indices]
        return np.trapezoid(total_dos_in_range, energies_in_range)
    
    
    def _calculate_hydrogen_idos(self, complete_dos, energies, selected_indices):
        H = Element("H")
        h_total_densities = self._get_element_total_dos_array(complete_dos, H)
        
        if h_total_densities is None:
            print("WARNING: no H_DOS")
            return 0.0
        
        h_dos_in_range = h_total_densities[selected_indices]
        energies_in_range = energies[selected_indices]
        return np.trapezoid(h_dos_in_range, energies_in_range)
    
    
    def _calculate_hydrogen_p_idos(self, complete_dos, energies, selected_indices):
        try:
            h_spd_dos = complete_dos.get_element_spd_dos(Element("H"))
            
            if OrbitalType.p in h_spd_dos:
                h_p_dos = h_spd_dos[OrbitalType.p]
                h_p_densities = h_p_dos.get_densities(spin=None)
                h_p_dos_in_range = h_p_densities[selected_indices]
                energies_in_range = energies[selected_indices]
                return np.trapezoid(h_p_dos_in_range, energies_in_range)
            else:
                print("WARNING: no H_p_DOS")
                return 0.0
        except Exception as e:
            print(f"WARNING: no H_p_DOS")
            print(f"WARNING: {e}")
            return 0.0
    
    
    def _calculate_nonhydrogen_idos(self, complete_dos, energies, selected_indices):
        element_dos_dict = complete_dos.get_element_dos()
        IDOS_X = 0.0
        
        for element, dos in element_dos_dict.items():
            if element.symbol == 'H':
                continue
            
            try:
                element_densities = dos.get_densities(spin=None)
                element_dos_in_range = element_densities[selected_indices]
                energies_in_range = energies[selected_indices]
                element_integral = np.trapezoid(element_dos_in_range, energies_in_range)
                IDOS_X += element_integral
            except Exception as e:
                print(f"WARNING:no non_H_DOS")
                print(f"WARNING: {e}")
        
        return IDOS_X
    
    
    def _get_element_total_dos_array(self, complete_dos, element_obj):
        try:
            edict = complete_dos.get_element_dos()
            dos_obj = edict.get(element_obj)
            if dos_obj is not None:
                try:
                    return dos_obj.get_densities()
                except TypeError:
                    from pymatgen.electronic_structure.core import Spin
                    d = dos_obj.get_densities(Spin.up)
                    if Spin.down in dos_obj.densities:
                        d = d + dos_obj.get_densities(Spin.down)
                    return d
        except:
            pass
        return None
    
    
    def _calculate_tc_formula(self):
        # Avoid division by zero
        if self.N_H == 0:
            raise ValueError("ERROR: No hydrogen atoms found in the structure")
        if self.IDOS_Tot == 0:
            raise ValueError("ERROR: Total DOS is zero")
        if self.IDOS_X == 0:
            raise ValueError("ERROR: Non-hydrogen DOS is zero")
        
        a = np.sqrt(self.IDOS_H_p / self.N_H) * (self.IDOS_H / self.IDOS_Tot)
        b = np.cbrt(self.IDOS_H / self.IDOS_X) * self.P
        Tc = 3930.62 * a - 0.17 * b - 4.69
        
        return Tc


    def _calculate_performance_indicator(self):
        """
        Calculate superconducting performance indicator S
        S = Tc / sqrt(Tc_MgB2^2 + P^2)
        where Tc_MgB2 = 39 K (critical temperature of MgB2)
        """
        Tc_MgB2 = 39.0  # K
        S = self.Tc / np.sqrt(Tc_MgB2**2 + self.P**2)
        return S


def predict_tc_simple(vasprun_path="vasprun.xml",
                     energy_min=-1.0,
                     energy_max=1.0,
                     output_file="Tc_pred.txt"):
    predictor = TcPredictor(energy_min=energy_min, energy_max=energy_max)
    tc = predictor.predict_tc(vasprun_path)
    predictor.save_results(output_file)
    
    features = predictor.get_features()
    print("\n" + "="*70)
    print("Summary:")
    print("="*70)
    print(f"Space Group:       {features['spacegroup']}")
    print(f"Pressure:          {features['P']:.1f} GPa")
    bandgap_str = f"{features['bandgap']:.6f}" if features['bandgap'] is not None else "N/A"
    print(f"Band gap:          {bandgap_str} eV")
    print(f"Tc_pred:           {features['Tc']:.3f} K")
    print(f"S (Performance):   {features['S']:.6f}")
    print("="*70)
    
    return tc


if __name__ == "__main__":
    tc = predict_tc_simple()

