# In this tutorial we will illustrate how to build and use a .csv file containing
# custom paramaters for homology-derived distance restraints (HDDRs) of MODELLER.
# This file can be used by the 'Automodel_custom_restraints' class of altMOD (see
# also the 'altmod_custom_restraints.py' script in this examples folder).
# In a custom HDDR parameters file you can define two parameters for an HDDR:
# its location and sigma value. MODELLER treats an HDDR as a Gaussian pdf [1],
# therefore these two parameters define the shapes of these pdfs. The selection
# of these parameters can have a huge impact on the quality of 3D models [2].

# References:
# [1] A. Sali & T.L. Blundell. Comparative protein modelling by satisfaction of
#     spatial restraints. J. Mol. Biol. 234, 779-815, 1993.
# [2] Janson et al. Revisiting the "satisfaction of spatial restraints" approach of MODELLER for protein homology modeling". 2019

from __future__ import print_function
import os
import random
import csv

from modeller import environ, log
from altmod.automodel_custom_restraints import Automodel_custom_restraints


# Initialize the MODELLER environment.
examples_dirpath = os.path.dirname(__file__)
log.none()
env = environ()
env.io.atom_files_directory = [".", examples_dirpath]


#----------------------------------------
# Step 1/5: obtain custom sigma values. -
#----------------------------------------

# We will start by deriving our sigma values. In MODELLER, by default, sigma
# values are assigned by the "histogram-based" algorithm of the program [1].
# To serve as an illustratory purpose, here we will generate new sigma values
# randomly, but you can use the methods presented in this tutorial to build your
# own HDDR parameters file with sigma values originating from any algorithm
# (for example, our group is currently working to develop a machine learning
# system to estimate optimal sigma values).

# We will be modeling a target protein (UniProtKB: P56406) with one template.
# Our target has 132 residues. Let's generate a list of 132 random numbers which
# will serve as a base to build the custom sigma values. For example, these numbers
# might be some scores that express some kind of "target-template" expected
# structural divergence that we extract from an external algorithm.

# Generate 132 random floats ranging from 0.05 to 1.0.
target_seq = "TVTVTYDPSNAPSFQQEIANAAQIWNSSVRNVQLRAGGNADFSYYEGNDSRGSYAQTDGHGRGYIFLDYQQNQQYDSTRVTAHETGHVLGLPDHYQGPCSELMSGGGPGPSCTNPYPNAQERSRVNALWANG"
residue_scores = [random.uniform(0.05, 1.0) for i in target_seq]

# Our list is 1d, but sigma values are parameters for distance restraints acting
# between pair of atoms: each distance in an model could potentially have
# its own sigma value.
# In this tutorial we will generate the sigma values only for CA-CA (Carbon alpha)
# distances. Therefore we need a 132x132 matrix in which each element could
# be used a sigma value for a distance restraint between two CA.

# Let's initialize the matrix.
sigma_values_matrix = [[None]*len(target_seq) for i in range(0, len(target_seq))]

# In this matrix, each element ij will be just the mean of the values of i and j
# in the initial 1d array.
for i, val_i in enumerate(residue_scores):
    for j, val_j in enumerate(residue_scores):
        sigma_values_matrix[i][j] = (val_i+val_j)/2.0


#-------------------------------------------
# Step 2/5: obtain custom location values. -
#-------------------------------------------

# Next we need location parameters for the HDDRs of our model. When performing
# single-template modeling, providing custom location parameters is optional, but
# to provide an example, we will see how it can be done. As a reminder, in MODELLER,
# the location of an HDDR is by default the distance observed in our template.
# As a source of custom location parameters, we will use the distances observed
# in our target experimentally-determined structure (PDB ID: 1C7K chain A), perturbed
# with a small error. We have stored the orginal distance matrix in a file in this
# example folder.

# Let's parse the observed distance matrix file.
m_fh = open(os.path.join(examples_dirpath, "target_calpha_distance_matrix.txt"), "r")
ca_ca_distance_maxtrix = []
for i, line in enumerate(m_fh):
    row = [float(v) for v in line.rstrip().split(",")]
    ca_ca_distance_maxtrix.append(row)
m_fh.close()

# And add some random errors to off-diagonal elements. We may think of these
# perturbed distances as the values generated by some accurate distance map
# prediction program.
for i, row in enumerate(ca_ca_distance_maxtrix):
    for j, val in enumerate(row):
        if i < j:
            ca_ca_distance_maxtrix[i][j] += random.normalvariate(0, 0.25)
            ca_ca_distance_maxtrix[j][i] = ca_ca_distance_maxtrix[i][j]


#---------------------------------------------------------------------------
# Step 3/5: obtain the HDDRs list in the MODELLER default restraints file. -
#---------------------------------------------------------------------------

# In a .rsr file of MODELLER, each HDDR line is defined by the two atoms on which the
# HDDR is acting (the atoms are specified by their serial numbers in the PDB file of
# the model created by MODELLER). The 'Automodel_custom_restraints' class of altMOD
# will look up for each HDDR in the default .rsr file produced by MODELLER, and
# every time it finds one, it will search in our HDDR parameters file (which is a
# .csv file) for a row specified by the same atoms. If it finds such a row, it will
# edit the HDDR line in the MODELLER .rsr file inserting the custom parameters.
# In our example, we would like to edit all the CA-CA HDDRs produced by MODELLER.
# MODELLER writes its .rsr file when we call the 'make' method of the 'automodel'
# class, which will also actually build the final 3D models. How do we know which
# CA-CA HDDRs MODELLER will use for our model without having to actually carry out
# the 3D model building phase (and wait for it to complete)?
# The 'Automodel_custom_restraints' class has a method called 'build_initial_files'
# which will make MODELLER anticipate the writing of its .rsr file and the .ini
# PDB file (which contains the model in its initial non-optimized conformation).
# This method also parses these two files so that we can get information about the
# HDDRs that MODELLER intends to use before actually building the model.

# Let's first initialze an "automodel" object with the custom class.
a = Automodel_custom_restraints(env, alnfile=os.path.join(examples_dirpath, 'model_1_st.pir'),
                                knowns=('template_0',), sequence='model_1_st')

# And then let's call the method. It will write the .rsr and .ini files and parse
# them.
a.build_initial_files()

# Now, our "automodel" object has an attribute called the 'hddr_dict', which
# contains information on all the HDDR written in the MODELLER .rsr file.
# It is a dictionary, where each key is the MODELLER code for an HDDR group
# ("9" is the code for CA-CA HDDRs). The values are lists of tuples, where each
# tuple contains the serial numbers of the atoms engaged in a HDDR.
print("\n################################")
print("# MODELLER .rsr file contents. #")
print("################################\n")
print("\n# There are %s CA-CA HDDRs used for this model." % len(a.hddr_dict["9"]))

# Let's take a look at some CA-CA HDDRs.
for i in range(0, 1000, 100):

    # We get the serial numbers of the atoms engaged in a HDDR.
    atm_num_i, atm_num_j = a.hddr_dict["9"][i]
    print("\n- CA-CA HDDR %s is acting on atoms: %s and %s." % (i, atm_num_i, atm_num_j))

    # Any atom serial number of our model can now be associated to its corresponding
    # residue number by using the 'atm_to_res_dict' dictionary (which maps an atom
    # serial number to the number of its corresponding residue in the PDB).
    res_num_i = a.atm_to_res_dict[atm_num_i]
    res_num_j = a.atm_to_res_dict[atm_num_j]
    print("- These two atoms belong to residues: %s and %s." % (res_num_i, res_num_j))

print("\n")


#-----------------------------------------------
# Step 4/5: write the "HDDR parameters" files. -
#-----------------------------------------------

# We will create a list of dictionaries to store our custom HDDRs parameters (where
# each dictionary represents a row of the HDDR parameters file).
hddr_params_list = []

# Let's iterate through all the CA-CA HDDRs present in the MODELLER restraints file
# that we intend to modify.
for atm_1, atm_2 in a.hddr_dict["9"]:

    # From the atoms serial numbers we get the corresponding residue numbers.
    res_num_1 = a.atm_to_res_dict[atm_1]
    res_num_2 = a.atm_to_res_dict[atm_2]

    # Now we obtain from our data matrices the new parameters for the CA-CA HDDRs.
    # Note that we can use the residue numbers of the model as indices for our
    # matrices, because by default in MODELLER residues are numbered from 1.
    new_sigma = sigma_values_matrix[res_num_1-1][res_num_2-1]
    new_location = ca_ca_distance_maxtrix[res_num_1-1][res_num_2-1]

    # As an example, let's also take a look at how to obtain template distances.
    # In this tutorial, we will not be using these distances, but when you write
    # your own HDDR parameters files it will be useful to obtain these distances
    # to recreate the default behaviour of MODELLER (which uses template distances
    # as the location parameters for its HDDRs).
    # Suppose we have two atom serial numbers of our model, and we would like
    # to know what is the corresponding distance between the equivalent atoms in
    # the template. To do that, we can use the 'get_template_distance' method of
    # the 'Automodel_custom_restraints' class.
    template_distance = a.get_template_distance(atm_1, atm_2, template_index=0)

    # We build a dictionary representing a .csv file line.
    hddr_params = {# Serial numbers of the atoms on which the HDDR is acting.
                   "MOD_ATOM_INDEX_I": atm_1, "MOD_ATOM_INDEX_J": atm_2,
                   # New sigma and location parameters.
                   "NEW_SIGMA": new_sigma, "NEW_LOCATION": new_location,
                   # Template distance (not actually used to build the new HDDRs now).
                   "_TEMPLATE_DISTANCE": template_distance
                   }
    hddr_params_list.append(hddr_params)


# Let's write the HDDR parameters file. Here we are using the 'csv' module of the
# standard library of Python, but you may build an these files with any method
# (for example, pandas).
custom_hddr_params_filepath = "custom_hddr_params.csv"
c_fh = open(custom_hddr_params_filepath, "w")
column_names = ["MOD_ATOM_INDEX_I", "MOD_ATOM_INDEX_J", "NEW_SIGMA", "NEW_LOCATION", "_TEMPLATE_DISTANCE"]
csv_writer = csv.DictWriter(c_fh, fieldnames=column_names)
csv_writer.writeheader()
for hddr_params in hddr_params_list:
    csv_writer.writerow(hddr_params)
c_fh.close()


#-----------------------------------------------------------------
# Step 5/5: build the 3D models with the custom HDDR parameters. -
#-----------------------------------------------------------------

# Before actually building the models, we have to use the 'set_custom_hddr_options'
# method to define options about the HDDR we want to rebuild.
a.set_custom_hddr_options(# Path of the custom HDDR parameters files.
                          hddr_params_filepaths=custom_hddr_params_filepath,
                          # Names of the atom i and j columns.
                          atom_i_col="MOD_ATOM_INDEX_I",
                          atom_j_col="MOD_ATOM_INDEX_J",
                          # Define the name of the custom sigma values column.
                          sigma_col="NEW_SIGMA",
                          # Define the name of the custom location values column.
                          # When performing single-template modeling, this is
                          # optional, since if whe do not provide one, altMOD will
                          # use as location parameters the values present in the
                          # default MODELLER .rsr file.
                          location_col="NEW_LOCATION",
                          # By setting as 'True' this argument, those HDDRs in the
                          # .rsr file which are not found in the HDDR paramaters
                          # file, will be deleted. In our example, this will remove
                          # from the .rsr file all the non CA-CA HDDRs (for example
                          # the side chains ones), because we did not insert custom
                          # parameters for these HDDRs in our parameters file.
                          # While CA-CA HDDRs are the most important ones to
                          # correctly model backbones, removing additional HDDRs
                          # usually results in poor side chain modeling and bad
                          # stereochemistry, so use this option carefully.
                          remove_missing_hddrs=True,
                          )

# We can finally build the models in the traditional way. The 'Automodel_custom_restraints'
# class will take care of editing the HDDRs lines in the .rsr file of MODELLER with
# the parameters you specified in the HDDR parameters files. In this way, MODELLER
# will build the model using our custom parameters for its CA-CA HDDRs.
a.starting_model = 1
a.ending_model = 1
a.make()