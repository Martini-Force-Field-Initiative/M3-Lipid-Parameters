#!/usr/bin/env python

# ----------  Imports  --------------------------

import sys,os,math,random,subprocess,numpy
import re
import shlex

# ----------  Description  ----------------------

desc = """
 Compute the projected area per lipid (A_0) and area compressibility modulus (K_A). 
 Using "Box-X" and "Box-Y" extracted from an energy file given in the arguments and 
 dividing this area with the given number of lipids in each monolayer. 

 See for example {Marrink, Vries, Mark, J. Phys. Chem. 2004, 108:750-760} and {Feller
 SE and Pastor RW, J. Chem. Phys. 1999, 111:1281-1287}.
 Small system will overestimate the K(A)
 K(A) = kT<A> / (N<(A - A0)2>)

 USAGE: %s <.edr file> <begin time (ps)> <end time (ps)> <#lipids in a monolayer> <Temperature (K)> > ener-area-out.xvg

 WARNING: will override/output data to ener-area.xvg, ener-area-A0-block.xvg and ener-area-KA-block.xvg

 @author Helgi I. Ingolfsson 2012.08

 EDITS: Harvey Mudd Clinic team, 2018. Slight formatting change to make main code a function
 instead of a script taking in command line arguments. This was done in order to call the 
 code from inside a larger analysis file. Also commented out several print statements. The 
 return value is area compressibility, but can be changed
 EDITS: 2022.09.09 - Removed dependance on Mara_Python3.IO import XVGIO by adding parse_xvg function from analysis pipeline

""" % (sys.argv[0])


# ----------  Functions/procedures  -------------

# Call system or print (if in test mode)
test = False #True #False  # set to True for print only and False for exicuting commands
def sys_call(command):
    if test:
        print(command)
        return 0
    else:
        p = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        return p.wait()

# function from analysis pipeline 
# Functions for handling xvg files
def parse_xvg(fname, sel_columns='all'):
    """Parses XVG file legends and data"""

    _ignored = set(('legend', 'view'))
    _re_series = re.compile('s[0-9]+$')
    _re_xyaxis = re.compile('[xy]axis$')

    metadata = {}
    num_data = []

    metadata['labels'] = {}
    metadata['labels']['series'] = []

    ff_path = os.path.abspath(fname)
    if not os.path.isfile(ff_path):
        raise IOError('File not readable: {0}'.format(ff_path))

    with open(ff_path, 'r') as fhandle:
        for line in fhandle:
            line = line.strip()
            if line.startswith('@'):
                tokens = shlex.split(line[1:])
                if tokens[0] in _ignored:
                    continue
                elif tokens[0] == 'TYPE':
                    if tokens[1] != 'xy':
                        raise ValueError('Chart type unsupported: \'{0}\'. Must be \'xy\''.format(tokens[1]))
                elif _re_series.match(tokens[0]):
                    metadata['labels']['series'].append(tokens[-1])
                elif _re_xyaxis.match(tokens[0]):
                    metadata['labels'][tokens[0]] = tokens[-1]
                elif len(tokens) == 2:
                    metadata[tokens[0]] = tokens[1]
                else:
                    print('Unsupported entry: {0} - ignoring'.format(tokens[0]), file=sys.stderr)
            elif line[0].isdigit():
                num_data.append(map(float, line.split()))

    num_data = list(zip(*num_data))

    if not metadata['labels']['series']:
        for series in range(len(num_data) - 1):
            metadata['labels']['series'].append('')

    # Column selection if asked
    if sel_columns != 'all':
        sel_columns = map(int, sel_columns)
        x_axis = num_data[0]
        num_data = [x_axis] + [num_data[col] for col in sel_columns]
        metadata['labels']['series'] = [metadata['labels']['series'][col - 1] for col in sel_columns]

    return metadata, num_data

# ----------  Parse input/display help  ---------
def calculate_area_compressibility(ene_file, runDir, begin_time, end_time, lipids_per_mon, temperature):
    # Read input 
    #args = sys.argv[1:]

    #if '-h' in args or '--help' in args or len(args) != 5:
    #    print(desc)
    #    sys.exit()

    procString = "area-lipid.py from file " + ene_file + " starting " + str(begin_time) + " to " + str(end_time) + " lipid count " + str(lipids_per_mon) + " temperature " + str(temperature)
    # print procString

    # ensure that inputs are ints
    #begin_time = int(begin_time)
    #end_time = int(end_time)
    #lipids_per_mon = float(lipids_per_mon)
    #temperature = float(temperature)

    ene_out_file = runDir + '/ener-area.xvg'
    block_A0_out_file = runDir + '/ener-area-A0-block.xvg'
    block_KA_out_file = runDir + '/ener-area-KA-block.xvg'

    scaled_k = 0.013806488 # Boltzmann constant (1.3806488 x 10^23 J/K, but here scaled so final K(A) values is in mN/m)

    # ----------  Start script  ---------------------

    # print "Projected area per lipid (A_0) mean, sd and se (se is from block averaging see " + block_A0_out_file + ")"
    # print "and area compressibility modulus (K_A) men, sd and se (sd and se are from block averaging see " + block_KA_out_file + ")"

    sys_call('echo -e "Box-X\nBox-Y\n 0" | gmx energy -f ' + ene_file + ' -b ' + str(begin_time) + ' -e ' + str(end_time) + ' -o ' + ene_out_file)

    # read xvg files
    metadata, num_data = parse_xvg(ene_out_file)
    # As we only saved x2 values box-X is num_data[1][x] and box-Y is num_data[2][x]
    #print(f"Read from enegery file - metadata {metadata}")
    #print(f"Read from enegery file - len {len(num_data)} len1 {len(num_data[0])} len2 {len(num_data[1])}")

    line_count = len(num_data[1])
    area = numpy.zeros(line_count)
    area_lipid = numpy.zeros(line_count)
    sum = 0

    # Calculate area and area/per lipid - for each timepoint
    for ti in range(line_count):
        #area[ti] = set[0][ti] * set[1][ti]
        area[ti] = num_data[1][ti] * num_data[2][ti] # num_data[0] is the time step 
        area_lipid[ti] = area[ti] / lipids_per_mon
    # End for

    # Get ave +/- sd for area per lipid
    val_A0 = numpy.average(area_lipid)
    val_A0_sd_r = numpy.std(area_lipid)

    # Use block averaging to get the SD and SE of the average area per lipid
    # Use minimum x5 blocks, report SD SE as max value in the last 20% in block curve
    outFile = open(block_A0_out_file,"w")
    print('#' + procString, file=outFile)
    print('# block averaging for A_0', file=outFile)
    block_max = int(line_count/5)
    block_range = range(1, block_max, 5)
    block_in_top_20 = block_max * 0.8
    val_A0_sd = -1
    val_A0_se = -1
    for block_size in block_range:
        blocks = range(block_size, line_count+1, block_size)
        numBlocks = int(line_count / block_size)
        blocked_A0 = []
        index = 0
        last_block = 0
        for ti in blocks:
            blocked_A0.append(numpy.average(area_lipid[(ti-block_size):ti]))
        # End for

        currentSTD = numpy.std(blocked_A0)
        currentSE  = currentSTD / math.sqrt(numBlocks)
        print("%7i    %10.8f    %10.8f    %10.8f" % (block_size, numpy.average(blocked_A0), currentSTD, currentSE), file=outFile)

        if (block_size >=  block_in_top_20):
            if val_A0_sd < currentSTD:
                val_A0_sd = currentSTD
            if val_A0_se < currentSE:
                val_A0_se = currentSE

    # End for
    outFile.close()
    # Warning here the SD is the SD of the preaveraged, the SD we report is val_A0_sd_r (same as sd with block size of 1)
    # print "Average +/- sd projected area per lipid: %.5f sd %.5f se %.5f (nm^2)" % (val_A0, val_A0_sd_r, val_A0_se) 


    # Calculate area compressibility modulus K(A) = kTA0 / N<(A - A0)^2>
    val_ave_area_var = 0
    area_lipid_squear_diff = numpy.zeros(line_count)
    # For each timepoint
    for ti in range(line_count):
        area_lipid_squear_diff[ti] = (area_lipid[ti] - val_A0)**2
        val_ave_area_var += area_lipid_squear_diff[ti]
    # End for
    val_ave_area_var = val_ave_area_var / line_count
    val_scaling = (scaled_k * temperature * val_A0) / lipids_per_mon  # kT A0 / N
    val_KA = val_scaling * (1 / val_ave_area_var)

    # Calculate SD for area compressibility modulus K(A) - need to do block averaging 
    # Use minimum x5 blocks, report SD SE as max value in the last 20% in block curve
    outFile = open(block_KA_out_file,"w")
    print('#' + procString, file=outFile)
    print('# block averaging for K_A', file=outFile)
    block_max = int(line_count/5)
    block_range = range(1, block_max, 5)
    block_in_top_20 = block_max * 0.8
    val_KA_sd = -1
    val_KA_se = -1
    for block_size in block_range:
        blocks = range(block_size, line_count, block_size)
        numBlocks = int(line_count / block_size)
        blocked_A0 = []
        index = 0
        for ti in blocks:
            #print ti
            current_block = []
            while (index < ti):
                #print "inner %i %i " % (ti, index)
                #current_block.append((area_lipid[index] - val_A0)**2)
                current_block.append(area_lipid_squear_diff[index])
                index += 1
    
            blocked_A0.append(val_scaling * (1 / numpy.average(current_block)))
        # End for

        currentSTD = numpy.std(blocked_A0)
        currentSE  = currentSTD / math.sqrt(numBlocks)
        print("%7i    %10.8f    %10.8f    %10.8f" % (block_size, numpy.average(blocked_A0), currentSTD, currentSE), file=outFile)

        if (block_size >=  block_in_top_20):
            if val_KA_sd < currentSTD:
                val_KA_sd = currentSTD
            if val_KA_se < currentSE:
                val_KA_se = currentSE
    # End for 
    outFile.close()

    # print "Calculate compressibility moduleus: ave %.5f sd %.5f se %.5f (mN/m)" % (val_KA, val_KA_sd, val_KA_se) 
    #return (val_KA, val_KA_se)
    return (val_A0, val_A0_sd_r, val_A0_se, val_KA, val_KA_sd, val_KA_se)

# sys.exit(0)

# ----------  End script  -----------------------



