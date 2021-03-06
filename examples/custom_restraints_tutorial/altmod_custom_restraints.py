# In this tutorial we will illustrate how to use altMOD to build multiple-template
# 3D models using homology-derived distance restraints (HDDRs) with a series of
# custom parameters.

from __future__ import print_function
import os

from modeller import environ
from altmod.automodel_custom_restraints import Automodel_custom_restraints


# Initialize the MODELLER environment.
examples_dirpath = os.path.dirname(__file__)
env = environ()
env.io.atom_files_directory = [".", examples_dirpath]


#------------
# Step 1/3. -
#------------

# As a first thing, we initialize an automodel object like we usually do in
# MODELLER, except that we will use the 'Automodel_custom_restraints' class
# imported from the 'altmod' package. Here, we will be modeling a target protein
# (UniProtKB: P56406) with two templates.
a = Automodel_custom_restraints(env, alnfile=os.path.join(examples_dirpath, 'model_1_mt.pir'),
                                knowns=('template_0', 'template_1'), sequence='model_1_mt')


#------------
# Step 2/3. -
#------------

# As a second step, we must provide the automodel object with a list of .csv files
# (each template must be associated with one) where the custom parameters for the
# HDDRs are stored.
# NOTE: in this example we already have some HDDR parameters files, but in general
# you might want to build your own. See the 'altmod_build_hddr_params_file.py' script
# in this examples folder to get more information on ways to do that.
hddr_params_filepaths = [os.path.join(examples_dirpath, "template_0_hddr_params.csv"),
                         os.path.join(examples_dirpath, "template_1_hddr_params.csv")]


# We have to use the 'set_custom_hddr_options' method to set some options about
# the HDDR we want to rebuild.
# Essentially, altMOD will parse the default restraints file generated by MODELLER
# and for each HDDR acting between two model atoms it finds, it will look up in
# the HDDR parameters files you provided to check if there is a matching row based
# on two atoms specified in the 'atom_i_col' and 'atom_j_col' columns. If it finds
# such a row, it will edit the restraints file by changing the parameters of
# the Gaussian HDDRs using the values you provide in the 'sigma_col' and 'location_col'
# columns of the .csv files.
a.set_custom_hddr_options(# Paths of the custom "HDDR parameters" files.
                          hddr_params_filepaths=hddr_params_filepaths,
                          # Each row in .csv file corresponds to a couple of
                          # restrained of atoms in the model. The
                          # 'MOD_ATOM_INDEX_I' and 'MOD_ATOM_INDEX_J' columns define
                          # which atoms. Note that the atom indices must be ones
                          # used in the PDB file of the model produced by MODELLER
                          # (which are the same indices used in the restraints
                          # files of MODELLER).
                          atom_i_col="MOD_ATOM_INDEX_I",
                          atom_j_col="MOD_ATOM_INDEX_J",
                          # Define the name of the custom sigma values column in
                          # the "HDDR parameters" files. In this example, the
                          # 'CUSTOM_SIGMA' column contains the optimal sigma
                          # values for each target-template pair, perturbed with
                          # a small amount of random noise.
                          sigma_col="CUSTOM_SIGMA",
                          # Define the name of the custom location values column in
                          # the "HDDR parameters". When using multiple-templates
                          # it is mandatory to specify one (when using a single
                          # template, by default altMOD will use the location
                          # parameters already present in the default .rsr file).
                          # In this example, the "CUSTOM_LOCATION" column contains
                          # the distance values oberved in the templates (therefore
                          # they are exactly the same values used by default in
                          # MODELLER).
                          location_col="CUSTOM_LOCATION",
                          # We specify the multiple-template weighting scheme as
                          # the one used in RosettaCM (with a parameter k=5.0).
                          mt_weights_scheme="rosetta", mt_rosetta_k=5.0)


#------------
# Step 3/3. -
#------------

# We can actually build the models in the traditional way. MODELLER will generate
# its default restraints file, and then the 'Automodel_custom_restraints' class
# will take care of editing the HDDRs lines with the parameters you specified in
# the HDDR parameters files.
a.starting_model = 1
a.ending_model = 1
a.make()
