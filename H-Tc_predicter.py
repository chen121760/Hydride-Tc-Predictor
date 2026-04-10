#!/usr/bin/env python3
"""
Batch Tc Prediction Script

This script predicts superconducting critical temperatures (Tc) for hydrogen-based
materials from VASP calculations using the symbolic regression formula.

Usage:
    H-Tc_predicter calculate/*
    H-Tc_predicter calculate/
    H-Tc_predicter folder1 folder2 folder3
    H-Tc_predicter -d calculate/ -e -1.0 1.0
    H-Tc_predicter --help

Author: Based on Chen et al. (2025)
Reference: 10.1016/j.mtphys.2026.102073
"""

import sys
import os
import shutil
import argparse
from SR_H_Tc_pred import TcPredictor
import pandas as pd
from datetime import datetime


def find_vasp_files(folder):
    """Find vasprun.xml in a folder"""
    vasprun = os.path.join(folder, "vasprun.xml")

    # Check if file exists
    if os.path.exists(vasprun):
        return vasprun
    else:
        return None


def process_single_structure(folder, energy_min=-1.0, energy_max=1.0, bandgap_threshold=0.1):
    """Process a single structure with early bandgap filtering"""
    structure_name = os.path.basename(folder)

    print(f"\n{'='*70}")
    print(f"Processing: {structure_name}")
    print(f"{'='*70}")

    # Find files
    vasprun = find_vasp_files(folder)

    if vasprun is None:
        print(f"ERROR: Cannot find vasprun.xml")
        return None

    # Execute prediction with early filtering
    try:
        predictor = TcPredictor(energy_min=energy_min, energy_max=energy_max)
        tc = predictor.predict_tc(vasprun, bandgap_threshold=bandgap_threshold)

        # If tc is None, it was filtered by bandgap
        if tc is None:
            bandgap_val = predictor.bandgap
            print(f"FILTERED: Band gap {bandgap_val:.6f} eV >= threshold {bandgap_threshold:.2f} eV")
            return {
                'name': structure_name,
                'folder': folder,
                'bandgap': bandgap_val,
                'status': 'filtered',
                'reason': f'Bandgap {bandgap_val:.6f} >= {bandgap_threshold:.2f} eV'
            }

        # Passed filtering, get complete features
        features = predictor.get_features()

        # Save individual result
        output_file = os.path.join(folder, "Tc_pred.txt")
        predictor.save_results(output_file)

        print(f"SG = {features['spacegroup']}")
        print(f"P  = {features['P']:.1f} GPa")
        bandgap_str = f"{features['bandgap']:.6f}" if features['bandgap'] is not None else "N/A"
        print(f"Eg = {bandgap_str} eV")
        print(f"Tc = {tc:.3f} K")
        print(f"S  = {features['S']:.6f}")

        return {
            'name': structure_name,
            'folder': folder,
            'spacegroup': features['spacegroup'],
            'Tc': tc,
            'P': features['P'],
            'bandgap': features['bandgap'],
            'S': features['S'],
            'IDOS_H': features['IDOS_H'],
            'IDOS_H_p': features['IDOS_H_p'],
            'IDOS_Tot': features['IDOS_Tot'],
            'IDOS_X': features['IDOS_X'],
            'N_H': features['N_H'],
            'N_Tot': features['N_Tot'],
            'status': 'success'
        }

    except Exception as e:
        print(f"ERROR: {e}")
        return {
            'name': structure_name,
            'folder': folder,
            'Tc': None,
            'P': None,
            'bandgap': None,
            'status': 'failed',
            'error': str(e)
        }


def batch_predict(folders, energy_min=-1.0, energy_max=1.0, bandgap_threshold=0.1, output_dir=None):
    """Batch predict multiple structures"""

    if output_dir is None:
        output_dir = os.getcwd()

    print("\n" + "="*70)
    print("Batch Tc Prediction Started")
    print("="*70)
    print(f"Energy window: [{energy_min:.2f}, {energy_max:.2f}] eV")
    print(f"Band gap threshold: {bandgap_threshold:.2f} eV (filter out Eg >= threshold)")
    print(f"Number of structures to process: {len(folders)}")
    print(f"Output directory: {output_dir}")

    results = []
    filtered_count = 0
    success_count = 0
    failed_count = 0

    # Process each structure (bandgap filtering happens early in process_single_structure)
    for folder in folders:
        result = process_single_structure(folder, energy_min, energy_max, bandgap_threshold)
        if result:
            if result['status'] == 'success':
                results.append(result)
                success_count += 1
            elif result['status'] == 'filtered':
                filtered_count += 1
                # Filtered results not added to results (per user preference, not saved to file)
            elif result['status'] == 'failed':
                results.append(result)  # Keep failed results for reporting
                failed_count += 1

    # Display filtering statistics
    print(f"\n{'='*70}")
    print(f"Bandgap Filtering Statistics:")
    print(f"{'='*70}")
    print(f"Total structures processed: {len(folders)}")
    print(f"Passed filter (Eg < {bandgap_threshold:.2f} eV): {success_count}")
    print(f"Filtered out (Eg >= {bandgap_threshold:.2f} eV): {filtered_count}")
    print(f"Failed to process: {failed_count}")

    # Generate summary report
    generate_summary(results, output_dir, bandgap_threshold)

    return results


def generate_summary(results, output_dir, bandgap_threshold=0.1):
    """Generate summary report"""

    if not results:
        print("\nNo successfully processed structures")
        return

    # Separate successful and failed results
    success = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']

    print("\n" + "="*70)
    print("Batch Processing Completed")
    print("="*70)
    print(f"Success: {len(success)}/{len(results)}")
    print(f"Failed: {len(failed)}/{len(results)}")

    if not success:
        return

    # Create DataFrame with explicit column order
    df = pd.DataFrame(success)
    column_order = ['name', 'folder', 'spacegroup', 'Tc', 'P', 'bandgap', 'S',
                    'IDOS_H', 'IDOS_H_p', 'IDOS_Tot', 'IDOS_X', 'N_H', 'N_Tot']
    df = df[column_order]

    # Sort by Tc (descending)
    df = df.sort_values('Tc', ascending=False)

    # Save detailed results to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = os.path.join(output_dir, f"Tc_batch_results_{timestamp}.csv")
    df.to_csv(csv_file, index=False, float_format='%.6f')
    print(f"\nDetailed results saved: {csv_file}")

    # Generate text summary
    summary_file = os.path.join(output_dir, f"Tc_batch_summary_{timestamp}.txt")
    with open(summary_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("Tc Prediction Batch Results Summary\n")
        f.write("="*70 + "\n\n")

        f.write(f"Processing time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Band gap filter: Eg < {bandgap_threshold:.2f} eV\n")
        f.write(f"Total structures: {len(results)}\n")
        f.write(f"Success: {len(success)}\n")
        f.write(f"Failed: {len(failed)}\n\n")

        if success:
            f.write("="*100 + "\n")
            f.write("Results Sorted by Tc (Top 10)\n")
            f.write("="*100 + "\n")
            f.write(f"{'Rank':<6} {'Structure':<20} {'SG':<5} {'Tc (K)':<10} {'P (GPa)':<10} {'Eg (eV)':<10} {'S':<12}\n")
            f.write("-"*100 + "\n")

            for idx, row in df.head(10).iterrows():
                rank = df.index.get_loc(idx) + 1
                sg_str = str(row['spacegroup']) if row['spacegroup'] is not None else 'N/A'
                bg_str = f"{row['bandgap']:.4f}" if row['bandgap'] is not None else "N/A"
                f.write(f"{rank:<6} {row['name']:<20} {sg_str:<5} {row['Tc']:>8.3f}  {row['P']:>8.1f}  {bg_str:>8}  {row['S']:>10.6f}\n")

            f.write("\n" + "="*70 + "\n")
            f.write("Statistical Information\n")
            f.write("="*70 + "\n")
            f.write(f"Highest Tc:  {df['Tc'].max():.3f} K  ({df.loc[df['Tc'].idxmax(), 'name']})\n")
            f.write(f"Lowest Tc:   {df['Tc'].min():.3f} K  ({df.loc[df['Tc'].idxmin(), 'name']})\n")
            f.write(f"Average Tc:  {df['Tc'].mean():.3f} K\n")
            f.write(f"Std Dev:     {df['Tc'].std():.3f} K\n")

        if failed:
            f.write("\n" + "="*70 + "\n")
            f.write("Failed Structures\n")
            f.write("="*70 + "\n")
            for r in failed:
                f.write(f"- {r['name']}: {r.get('error', 'Unknown error')}\n")

    print(f"Summary report saved: {summary_file}")

    # Print top 10 to screen
    print("\n" + "="*100)
    print("Top 10 Highest Tc (after bandgap filtering):")
    print("="*100)
    print(f"{'Rank':<6} {'Structure':<20} {'SG':<5} {'Tc (K)':<10} {'P (GPa)':<10} {'Eg (eV)':<10} {'S':<12}")
    print("-"*100)
    for idx, row in df.head(10).iterrows():
        rank = df.index.get_loc(idx) + 1
        sg_str = str(row['spacegroup']) if row['spacegroup'] is not None else 'N/A'
        bg_str = f"{row['bandgap']:.4f}" if row['bandgap'] is not None else "N/A"
        print(f"{rank:<6} {row['name']:<20} {sg_str:<5} {row['Tc']:>8.3f}  {row['P']:>8.1f}  {bg_str:>8}  {row['S']:>10.6f}")


def interactive_save_structures(results, current_dir=None):
    """
    Interactive function to save high-Tc structures

    Parameters:
        results: List of result dictionaries
        current_dir: Directory where goodstructure folder will be created
    """
    if current_dir is None:
        current_dir = os.getcwd()

    # Filter only successful results
    success_results = [r for r in results if r['status'] == 'success']

    if not success_results:
        print("\nNo successful structures to save.")
        return

    # Interactive prompt
    print("\n" + "="*70)
    print("Structure Saving Option")
    print("="*70)
    print("Enter a Tc threshold to save structures with Tc above this value")
    print("Or enter 'F' to skip saving")
    print("="*70)

    while True:
        user_input = input("Tc threshold (K) or F: ").strip()

        # Check if user wants to skip
        if user_input.upper() == 'F':
            print("Skipping structure saving.")
            return

        # Try to parse as float
        try:
            tc_threshold = float(user_input)
            break
        except ValueError:
            print("Invalid input. Please enter a number or 'F'.")

    # Filter structures by Tc threshold
    filtered_structures = [r for r in success_results if r['Tc'] >= tc_threshold]

    if not filtered_structures:
        print(f"\nNo structures found with Tc >= {tc_threshold:.2f} K")
        return

    print(f"\nFound {len(filtered_structures)} structure(s) with Tc >= {tc_threshold:.2f} K")

    # Create goodstructure directory
    goodstructure_dir = os.path.join(current_dir, "goodstructure")

    if not os.path.exists(goodstructure_dir):
        os.makedirs(goodstructure_dir)
        print(f"Created directory: {goodstructure_dir}")
    else:
        print(f"Using existing directory: {goodstructure_dir}")

    # Copy CONTCAR files
    success_count = 0
    failed_count = 0

    print("\n" + "="*70)
    print("Copying CONTCAR files...")
    print("="*70)

    for result in filtered_structures:
        structure_name = result['name']
        tc_value = result['Tc']
        folder_path = result['folder']

        # Source CONTCAR path
        contcar_path = os.path.join(folder_path, "CONTCAR")

        # Check if CONTCAR exists
        if not os.path.exists(contcar_path):
            print(f"WARNING: CONTCAR not found for {structure_name}, skipping...")
            failed_count += 1
            continue

        # Destination filename: structure_name_Tc_value.vasp
        dest_filename = f"{structure_name}_{tc_value:.3f}.vasp"
        dest_path = os.path.join(goodstructure_dir, dest_filename)

        # Copy file
        try:
            shutil.copy2(contcar_path, dest_path)
            print(f"✓ Copied: {structure_name} (Tc = {tc_value:.3f} K)")
            success_count += 1
        except Exception as e:
            print(f"ERROR: Failed to copy {structure_name}: {e}")
            failed_count += 1

    # Summary
    print("\n" + "="*70)
    print("Structure Saving Complete")
    print("="*70)
    print(f"Successfully saved: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Output directory: {goodstructure_dir}")
    print("="*70)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Batch prediction of superconducting critical temperature (Tc) '
                    'for hydrogen-based materials from VASP calculations.',
        epilog="""
Examples:
  %(prog)s calculate/*                    # Process all folders in calculate/
  %(prog)s calculate/                     # Process all subfolders
  %(prog)s folder1 folder2 folder3        # Process specific folders
  %(prog)s -d calculate/ -e -1.0 1.5      # Custom energy window

Reference:
  Chen et al. (2025), arXiv:2511.11284
  "Interpretable descriptors enable prediction of hydrogen-based
   superconductors at moderate pressures"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'folders',
        nargs='*',
        help='Folders containing VASP outputs (vasprun.xml). '
             'Can be specific folders, wildcards, or parent directories.'
    )

    parser.add_argument(
        '-d', '--directory',
        dest='parent_dir',
        help='Parent directory containing calculation folders'
    )

    parser.add_argument(
        '-e', '--energy-window',
        nargs=2,
        type=float,
        metavar=('EMIN', 'EMAX'),
        default=[-1.0, 1.0],
        help='Energy window relative to Fermi level in eV (default: -1.0 1.0)'
    )

    parser.add_argument(
        '--bandgap-threshold',
        type=float,
        default=0.1,
        metavar='THRESHOLD',
        help='Maximum band gap threshold in eV (default: 0.1). '
             'Materials with Eg >= threshold are filtered out.'
    )

    parser.add_argument(
        '-o', '--output',
        dest='output_dir',
        default=None,
        help='Output directory for summary files (default: current directory)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0 - Based on arXiv:2511.11284'
    )

    return parser.parse_args()


def main():
    """Main function"""

    # Parse command line arguments
    args = parse_arguments()

    # Collect all folders
    folders = []

    # If parent directory is specified
    if args.parent_dir:
        parent = args.parent_dir
        if os.path.isdir(parent):
            # Get all subdirectories
            subdirs = [os.path.join(parent, d) for d in os.listdir(parent)
                      if os.path.isdir(os.path.join(parent, d))]
            folders.extend(subdirs)
        else:
            print(f"ERROR: Directory not found: {parent}")
            sys.exit(1)

    # Process folders from command line
    for arg in args.folders:
        # If it's a directory, get its subdirectories
        if os.path.isdir(arg):
            # Check if it contains vasprun.xml (is a calculation directory)
            if os.path.exists(os.path.join(arg, "vasprun.xml")):
                folders.append(arg)
            else:
                # Get all subdirectories
                subdirs = [os.path.join(arg, d) for d in os.listdir(arg)
                          if os.path.isdir(os.path.join(arg, d))]
                folders.extend(subdirs)

        # If it's a file, use its parent directory
        elif os.path.isfile(arg):
            folder = os.path.dirname(arg)
            if folder not in folders:
                folders.append(folder)

    # Remove duplicates and sort
    folders = sorted(list(set(folders)))

    if not folders:
        print("ERROR: No valid calculation folders found")
        print("\nUsage: H-Tc_predicter [OPTIONS] FOLDERS...")
        print("Try 'H-Tc_predicter --help' for more information.")
        sys.exit(1)

    # Execute batch prediction
    energy_min, energy_max = args.energy_window
    results = batch_predict(
        folders,
        energy_min=energy_min,
        energy_max=energy_max,
        bandgap_threshold=args.bandgap_threshold,
        output_dir=args.output_dir
    )

    # Interactive structure saving
    interactive_save_structures(results, current_dir=os.getcwd())

if __name__ == "__main__":
    main()
