#!/usr/bin/env python

# (C) 2018 OpenEye Scientific Software Inc. All rights reserved.
#
# TERMS FOR USE OF SAMPLE CODE The software below ("Sample Code") is
# provided to current licensees or subscribers of OpenEye products or
# SaaS offerings (each a "Customer").
# Customer is hereby permitted to use, copy, and modify the Sample Code,
# subject to these terms. OpenEye claims no rights to Customer's
# modifications. Modification of Sample Code is at Customer's sole and
# exclusive risk. Sample Code may require Customer to have a then
# current license or subscription to the applicable OpenEye offering.
# THE SAMPLE CODE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED.  OPENEYE DISCLAIMS ALL WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. In no event shall OpenEye be
# liable for any damages or liability in connection with the Sample Code
# or its use.

from floe.api import WorkFloe

from MDCubes.OpenMMCubes.cubes import (OpenMMminimizeCube,
                                       OpenMMNvtCube,
                                       OpenMMNptCube)

from ComplexPrepCubes.cubes import (SolvationCube,
                                    ComplexPrepCube)

from ProtPrepCubes.cubes import ProteinSetting

from ForceFieldCubes.cubes import ForceFieldCube

from LigPrepCubes.cubes import (LigandChargeCube,
                                LigandSetting)

from YankCubes.cubes import (SyncBindingFECube,
                             YankBindingFECube)

from cuberecord import (DataSetWriterCube,
                        DataSetReaderCube)

# *************USER SETTING**************
yank_iteration_per_chunk = 200
chunks = 5
# ***************************************

cube_list = []

job = WorkFloe('Binding Affinity')

job.description = """
Set up an OpenMM complex then minimize, warm up and equilibrate a system by using three equilibration stages

Ex: python floes/openmm_MDprep.py --ligands ligands.oeb --protein protein.oeb --ofs-data_out prep.oeb

Parameters:
-----------
ligands (file): oeb file of ligand posed in the protein active site.
protein (file): oeb file of the protein structure, assumed to be pre-prepared

Optionals:
-----------

Outputs:
--------
ofs: Outputs a ready system to MD production run
"""

job.classification = [['BindingFreeEnergy', 'Yank']]
job.tags = [tag for lists in job.classification for tag in lists]

# Ligand setting
iligs = DataSetReaderCube("LigandReader", title="Ligand Reader")
iligs.promote_parameter("data_in", promoted_name="ligands", title="Ligand Input File", description="Ligand file name")
job.add_cube(iligs)

chargelig = LigandChargeCube("LigCharge")
chargelig.promote_parameter('charge_ligands', promoted_name='charge_ligands',
                            description="Charge the ligand or not", default=True)
job.add_cube(chargelig)

ligset = LigandSetting("LigandSetting")
job.add_cube(ligset)

# Protein Reading cube. The protein prefix parameter is used to select a name for the
# output system files
iprot = DataSetReaderCube("ProteinReader", title="Protein Reader")
iprot.promote_parameter("data_in", promoted_name="protein", title='Protein Input File',
                        description="Protein file name")
job.add_cube(iprot)

protset = ProteinSetting("ProteinSetting")
protset.promote_parameter("protein_prefix", promoted_name="protein_prefix", default="PRT")
job.add_cube(protset)

# COMPLEX SETTING

# Complex cube used to assemble the ligands and the solvated protein
complx = ComplexPrepCube("Complex")
job.add_cube(complx)

# The solvation cube is used to solvate the system and define the ionic strength of the solution
solvateComplex = SolvationCube("HydrationComplex", title="Complex Hydration")
solvateComplex.promote_parameter('density', promoted_name='density', default=1.03,
                                 description="Solution density in g/ml")
solvateComplex.promote_parameter('close_solvent', promoted_name='close_solvent', default=True,
                                 description='The solvent molecules will be placed very close to the solute')
solvateComplex.promote_parameter('salt_concentration', promoted_name='salt_concentration', default=50.0,
                                 description='Salt concentration (Na+, Cl-) in millimolar')

job.add_cube(solvateComplex)

# Complex Force Field Application
ffComplex = ForceFieldCube("ForceFieldComplex", title="Complex Parametrization")
ffComplex.promote_parameter('ligand_forcefield', promoted_name='ligand_ff', default='GAFF2')
ffComplex.promote_parameter('other_forcefield', promoted_name='other_ff', default='GAFF2')
job.add_cube(ffComplex)

# First Yank Cube used to build the UI interface
abfe0 = YankBindingFECube("ABFE0", title="ABFE")
abfe0.promote_parameter('iterations', promoted_name='iterations', default=yank_iteration_per_chunk)
abfe0.promote_parameter('verbose', promoted_name='verbose', default=True)
abfe0.promote_parameter('temperature', promoted_name='temperature', default=300.0,
                        description='Temperature (Kelvin)')
abfe0.promote_parameter('pressure', promoted_name='pressure', default=1.0,
                        description='Pressure (atm)')
abfe0.promote_parameter('hmr', promoted_name='hmr', default=False,
                        description='Hydrogen Mass Repartitioning')
abfe0.promote_parameter('sampler', promoted_name='sampler', default='repex',
                        description='Yank Sampling mode: '
                                    'REPEX Replica Exchange and SAMS Self-Adjusted Mixture Sampling')
abfe0.promote_parameter('restraints', promoted_name='restraints',
                        description='Select the restraint types. '
                                    'Choices: harmonic, boresch')
abfe0.promote_parameter('protocol', promoted_name='protocol',
                        description='Select the protocol types. '
                                    'Choices: auto, restraint-on-when-decoupled')
abfe0.promote_parameter('max_parallel', promoted_name='num_gpus', default=1,
                        description='Number of GPUS to make available - '
                                    'should be less than the number of ligands')
abfe0.promote_parameter('min_parallel', promoted_name='num_gpus', default=1,
                        description='Number of GPUS to make available - '
                                    'should be less than the number of ligands')
abfe0.promote_parameter('hmr', promoted_name='hmr', default=False, description='Hydrogen Mass Repartitioning')
abfe0.set_parameters(rerun=False)
abfe0.set_parameters(minimize=True)
abfe0.set_parameters(analyze=False)

job.add_cube(abfe0)

# Minimization
minComplex = OpenMMminimizeCube('minComplex', title='Complex Minimization')
minComplex.promote_parameter('hmr', promoted_name='hmr')
minComplex.set_parameters(restraints="noh (ligand or protein)")
minComplex.set_parameters(restraintWt=5.0)
minComplex.set_parameters(steps=1000)
minComplex.set_parameters(center=True)
job.add_cube(minComplex)

# NVT simulation. Here the assembled system is warmed up to the final selected temperature
warmupComplex = OpenMMNvtCube('warmupComplex', title='Complex Warm Up')
warmupComplex.set_parameters(time=0.02)
warmupComplex.promote_parameter('temperature', promoted_name='temperature')
warmupComplex.promote_parameter('hmr', promoted_name='hmr')
warmupComplex.set_parameters(restraints="noh (ligand or protein)")
warmupComplex.set_parameters(restraintWt=2.0)
warmupComplex.set_parameters(trajectory_interval=0.0)
warmupComplex.set_parameters(reporter_interval=0.0)
warmupComplex.set_parameters(suffix='warmup_complex')
job.add_cube(warmupComplex)

# The system is equilibrated at the right pressure and temperature in 3 stages
# The main difference between the stages is related to the restraint force used
# to keep the ligand and protein in their starting positions. A relatively strong force
# is applied in the first stage while a relatively small one is applied in the latter

# NPT Equilibration stage 1
equil1Complex = OpenMMNptCube('equil1Complex', title='Complex Equilibration I')
equil1Complex.set_parameters(time=0.02)
equil1Complex.promote_parameter('temperature', promoted_name='temperature')
equil1Complex.promote_parameter('pressure', promoted_name='pressure')
equil1Complex.promote_parameter('hmr', promoted_name='hmr')
equil1Complex.set_parameters(restraints="noh (ligand or protein)")
equil1Complex.set_parameters(restraintWt=2.0)
equil1Complex.set_parameters(trajectory_interval=0.0)
equil1Complex.set_parameters(reporter_interval=0.0)
equil1Complex.set_parameters(suffix='equil1')
job.add_cube(equil1Complex)

# NPT Equilibration stage 2
equil2Complex = OpenMMNptCube('equil2Complex', title='Complex Equilibration II')
equil2Complex.set_parameters(time=0.02)
equil2Complex.promote_parameter('temperature', promoted_name='temperature')
equil2Complex.promote_parameter('pressure', promoted_name='pressure')
equil2Complex.promote_parameter('hmr', promoted_name='hmr')
equil2Complex.set_parameters(restraints="noh (ligand or protein)")
equil2Complex.set_parameters(restraintWt=0.5)
equil2Complex.set_parameters(trajectory_interval=0.0)
equil2Complex.set_parameters(reporter_interval=0.0)
equil2Complex.set_parameters(suffix='equil2')
job.add_cube(equil2Complex)

# NPT Equilibration stage 3
equil3Complex = OpenMMNptCube('equil3Complex', title='Complex Equilibration III')
equil3Complex.set_parameters(time=0.02)
equil3Complex.promote_parameter('temperature', promoted_name='temperature')
equil3Complex.promote_parameter('pressure', promoted_name='pressure')
equil3Complex.promote_parameter('hmr', promoted_name='hmr')
equil3Complex.set_parameters(restraints="ca_protein or (noh ligand)")
equil3Complex.set_parameters(restraintWt=0.1)
equil3Complex.set_parameters(trajectory_interval=0.0)
equil3Complex.set_parameters(reporter_interval=0.0)
equil3Complex.set_parameters(suffix='equil3')
job.add_cube(equil3Complex)

# LIGAND SETTING

# Solvate Ligands
solvateLigand = SolvationCube("HydrationLigand", title="Unbounded Ligand Hydration")
job.add_cube(solvateLigand)

# Ligand Force Field Application
ffLigand = ForceFieldCube("ForceFieldLigand", title="Unbounded Ligand Parametrization")
ffLigand.promote_parameter('ligand_forcefield', promoted_name='ligand_forcefield')
ffLigand.promote_parameter('other_forcefield', promoted_name='other_forcefield')
job.add_cube(ffLigand)

# Ligand Minimization
minimizeLigand = OpenMMminimizeCube("MinimizeLigand", title="Unbounded Ligand Minimization")
minimizeLigand.set_parameters(restraints='noh ligand')
minimizeLigand.promote_parameter('hmr', promoted_name='hmr')
minimizeLigand.set_parameters(restraintWt=5.0)
minimizeLigand.set_parameters(center=True)
job.add_cube(minimizeLigand)

# Ligand NVT Warm-up
warmupLigand = OpenMMNvtCube('warmupLigand', title='Unbounded Ligand Warm Up')
warmupLigand.set_parameters(time=0.02)
warmupLigand.promote_parameter('temperature', promoted_name='temperature')
warmupLigand.promote_parameter('hmr', promoted_name='hmr')
warmupLigand.set_parameters(restraints="noh ligand")
warmupLigand.set_parameters(restraintWt=2.0)
warmupLigand.set_parameters(trajectory_interval=0.0)
warmupLigand.set_parameters(reporter_interval=0.0)
warmupLigand.set_parameters(suffix='warmup_ligand')
job.add_cube(warmupLigand)

# Ligand NPT Equilibration stage
equilLigand = OpenMMNptCube('equilLigand', title='Unbounded Ligand Equilibration')
equilLigand.set_parameters(time=0.02)
equilLigand.promote_parameter('temperature', promoted_name='temperature')
equilLigand.promote_parameter('pressure', promoted_name='pressure')
equilLigand.promote_parameter('hmr', promoted_name='hmr')
equilLigand.set_parameters(restraints="noh ligand")
equilLigand.set_parameters(restraintWt=0.1)
equilLigand.set_parameters(trajectory_interval=0.0)
equilLigand.set_parameters(reporter_interval=0.0)
equilLigand.set_parameters(suffix='equil')
job.add_cube(equilLigand)

sync = SyncBindingFECube("SyncCube", title="Unbounded and Bonded Synchronization")
job.add_cube(sync)
cube_list.append(sync)

# Add YANK first Cube
cube_list.append(abfe0)

for i in range(1, chunks):
    abfe = YankBindingFECube("ABFE"+str(i), title="ABFE"+str(i))
    abfe.set_parameters(iterations=yank_iteration_per_chunk*(i+1))
    abfe.promote_parameter("verbose", promoted_name="verbose")
    abfe.promote_parameter("temperature", promoted_name="temperature")
    abfe.promote_parameter("pressure", promoted_name="pressure")
    abfe.promote_parameter("max_parallel", promoted_name="num_gpus")
    abfe.promote_parameter("min_parallel", promoted_name="num_gpus")
    abfe.promote_parameter("hmr", promoted_name="hmr")
    abfe.set_parameters(rerun=True)
    abfe.set_parameters(minimize=False)
    abfe.set_parameters(analyze=False)

    if i == (chunks - 1):
        abfe.set_parameters(analyze=True)

    job.add_cube(abfe)
    cube_list.append(abfe)


ofs = DataSetWriterCube('ofs', title='Out')
ofs.promote_parameter("data_out", promoted_name="out")
job.add_cube(ofs)
cube_list.append(ofs)

fail = DataSetWriterCube('fail', title='Failures')
fail.set_parameters(data_out='fail.oedb')
job.add_cube(fail)
cube_list.append(fail)

# Connections
iligs.success.connect(chargelig.intake)
chargelig.success.connect(ligset.intake)
ligset.success.connect(complx.intake)

iprot.success.connect(protset.intake)
protset.success.connect(complx.protein_port)

# Complex Connections
complx.success.connect(solvateComplex.intake)
solvateComplex.success.connect(ffComplex.intake)
ffComplex.success.connect(minComplex.intake)
minComplex.success.connect(warmupComplex.intake)
warmupComplex.success.connect(equil1Complex.intake)
equil1Complex.success.connect(equil2Complex.intake)
equil2Complex.success.connect(equil3Complex.intake)
equil3Complex.success.connect(sync.intake)
# Ligand Connections
ligset.success.connect(solvateLigand.intake)
solvateLigand.success.connect(ffLigand.intake)
ffLigand.success.connect(minimizeLigand.intake)
minimizeLigand.success.connect(warmupLigand.intake)
warmupLigand.success.connect(equilLigand.intake)
equilLigand.success.connect(sync.solvated_ligand_in_port)

# Connections Yank cubes
for i in range(0, len(cube_list)-2):
    cube_list[i].success.connect(cube_list[i + 1].intake)
    if i == len(cube_list) - 3:
        cube_list[i].failure.connect(cube_list[i+2].intake)


if __name__ == "__main__":
    job.run()
