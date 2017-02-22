import io, os, time, traceback, base64
from openeye import oechem
import numpy as np
from simtk import unit, openmm
from simtk.openmm import app

from floe.api import OEMolComputeCube, parameter, MoleculeInputPort, BinaryMoleculeInputPort, BinaryOutputPort, OutputPort, ParallelOEMolComputeCube
from floe.api.orion import in_orion, StreamingDataset
from floe.constants import BYTES

from LigPrepCubes.ports import CustomMoleculeInputPort, CustomMoleculeOutputPort
import YankCubes.utils as utils
from YankCubes.utils import get_data_filename

import yank
from yank.yamlbuild import *
import textwrap
import subprocess

hydration_yaml_default = """\
---
options:
  minimize: yes
  verbose: yes
  # TODO: Make these into parameters
  number_of_iterations: 10
  temperature: 300*kelvin
  pressure: 1*atmosphere

molecules:
  input_molecule:
    # Don't change input.mol2
    filepath: input.mol2
    # TODO: Can we autodetect whether molecule has charges or not?
    openeye:
      quacpac: am1-bcc
    antechamber:
      charge_method: null

solvents:
  pme:
    nonbonded_method: PME
    nonbonded_cutoff: 9*angstroms
    clearance: 16*angstroms
  vacuum:
    nonbonded_method: NoCutoff

systems:
  hydration:
    solute: input_molecule
    solvent1: pme
    solvent2: vacuum
    leap:
      parameters: [leaprc.gaff, leaprc.protein.ff14SB, leaprc.water.tip3p]

protocols:
  hydration-protocol:
    solvent1:
      alchemical_path:
        lambda_electrostatics: [1.00, 0.75, 0.50, 0.25, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00]
        lambda_sterics:        [1.00, 1.00, 1.00, 1.00, 1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00]
    solvent2:
      alchemical_path:
        lambda_electrostatics: [1.00, 0.75, 0.50, 0.25, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00]
        lambda_sterics:        [1.00, 1.00, 1.00, 1.00, 1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00]

experiments:
  system: hydration
  protocol: hydration-protocol
"""

def yank_load(script):
    """Shortcut to load a string YAML script with YankLoader."""
    return yaml.load(textwrap.dedent(script), Loader=YankLoader)

def run_cli(arguments):
    """Generic helper to run command line arguments"""
    # cli.main(argv=arguments.split())
    command = 'yank ' + arguments
    [stoutdata, sterrdata] = subprocess.Popen(command.split()).communicate()

    # TODO: Interpret suprocess data better
    if sterrdata:
        message = "An error return value (%s) was obtained:\n" % str(sterrdata)
        message += "\n"
        message += stoutdata
        message += "\n"
        raise Exception(message)

class YankHydrationCube(OEMolComputeCube):
    title = "YankHydrationCube"
    description = """
    Compute the hydration free energy of a small molecule with YANK.

    This cube uses the YANK alchemical free energy code to compute the
    transfer free energy of one or more small molecules from gas phase
    to TIP3P solvent.

    See http://getyank.org for more information about YANK.
    """
    classification = ["Alchemical free energy calculations"]
    tags = [tag for lists in classification for tag in lists]

    #Define Custom Ports to handle oeb.gz files
    intake = CustomMoleculeInputPort('intake')
    success = CustomMoleculeOutputPort('success')

    # TODO: Have these override YAML parameters
    simulation_time = parameter.DecimalParameter('simulation_time', default=1.0,
                                     help_text="Simulation time (ns/replica)")

    temperature = parameter.DecimalParameter('temperature', default=300.0,
                                     help_text="Temperature (Kelvin)")

    pressure = parameter.DecimalParameter('pressure', default=1.0,
                                 help_text="Pressure (atm)")

    # TODO: Check if this is the best way to present a large YAML file to be edited
    yaml_contents = parameter.StringParameter('yaml',
                                        default=hydration_yaml_default,
                                        description='suffix to append')

    def begin(self):
        # TODO: Make substitutions to YAML here.

        kB = unit.BOLTZMANN_CONSTANT_kB * unit.AVOGADRO_CONSTANT_NA # Boltzmann constant
        self.kT = self.kB * (self.args.temperature * unit.kelvin)
        pass

    def process(self, input_molecule, port):
        kT_in_kcal_per_mole = self.kT.value_in_unit(unit.kilocalories_per_mole)

        try:
            # Make a deep copy of the molecule to form the result molecule
            result_molecule = oechem.OEGraphMol(input_molecule)

            # Write the specified molecule out to a mol2 file
            # TODO: Can we read .oeb files directly into YANK?
            # TODO: Do we need to use a randomly-generated filename to avoid collisions?
            ofs = oechem.oemolostream('input.mol2')
            oechem.OEWriteMolecule(ofs, input_molecule)

            # Run YANK on the specified molecule.
            from yank.yamlbuild import YamlBuilder
            yaml_builder = YamlBuilder(self.args.yaml_contents)
            yaml_builder.build_experiments()

            # Analyze the hydration free energy.
            (Deltaf_ij_solvent, dDeltaf_ij_solvent) = estimate_free_energies('output/experiments/solvent1.nc')
            (Deltaf_ij_vacuum,  dDeltaf_ij_vacuum)  = estimate_free_energies('output/experiments/solvent2.nc')
            DeltaG_hydration = Deltaf_ij_vacuum - Deltaf_ij_solvent
            dDeltaG_hydration = np.sqrt(Deltaf_ij_vacuum**2 + Deltaf_ij_solvent**2)

            # Add result to original molecule
            result_molecule.SetData('DeltaG_hydration', DeltaG_hydration * kT_in_kcal_per_mole)
            result_molecule.SetData('dDeltaG_hydration', dDeltaG_hydration * kT_in_kcal_per_mole)
            self.success.emit(result_molecule)

        except Exception as e:
            # Attach error message to the molecule that failed
            self.log.error(traceback.format_exc())
            mol.SetData('error', str(e))
            # Return failed molecule
            self.failure.emit(mol)
