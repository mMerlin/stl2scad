#!/usr/bin/python
# -*- coding: utf-8 -*-

""" STL to SCAD converter.

Convert stl file to OpenSCAD .scad format

This processing logic for this code was initially based on
https://github.com/joshuaflanagan/stl2scad, which in turn came (indirectly)
from the Riham javascript code http://www.thingiverse.com/thing:62666.

Ascii STL file format http://www.fabbers.com/tech/STL_Format#Sct_ASCII
Binary STL file format http://www.fabbers.com/tech/STL_Format#Sct_binary

Big thanks to [numpy-stl](https://github.com/WoLpH/numpy-stl/) for doing the
heavy lifting of parsing and loading stl files.

This should work when run with either python2 or python3

pip install -r requirements.txt
"""

import os
import sys
import argparse
import numpy as np
from stl import mesh

# Pseudo constants: some would be better as enums, but backward compatibility …
# IDEA import enum for python2
STL2SCAD_VERSION = '0.0.1'
# This version matches the functionality of
# https://github.com/joshuaflanagan/stl2scad, though the output coordinate
# precission is different for some cases
isV3 = ( sys.hexversion >= 0x030000F0 ) # running with python3 or later

# regular globals: might be better implemented as singleton
# objectSequence = 0
cmdLineArgs = None # command line line argument information used throughout


def getCmdLineArgs():
    parser = argparse.ArgumentParser (
        prog = 'stl2scad',
        description = 'Convert .stl format file to OpenSCAD script' )
    parser.add_argument ( '-v', '--version', action = 'version',
        # version = '%(prog)s %s' STL2SCAD_VERSION )
        # version = '%(prog)s $STL2SCAD_VERSION' )
        version = '%(prog)s 0.0.1' )
    parser.add_argument ( 'file', default = sys.stdin,
        nargs = '*',
        type = argparse.FileType ( 'r' ),
        # action = 'append',
        help = 'The .stl file(s) to process' )
    parser.add_argument ( '-C', '--scad-version',
        choices = [ '2014.03', 'current'], default = 'current',
        help = 'OpenSCAD compatibility version (default: current)' )
# -V, --verbose
# single scad object per 'solid' ¦ one object per disjoint face set ¦ other for voids
# object name
# object name prefix
# destination folder (versus back where source file found)
# overwrite existing ¦ increment sequence
# .scad from input file
# .scad from solid objectname
# .scad from input
# [no]warn overwrite output
# optional positional arguments, so specify on per file bases
#  --opt v1 file1 --opt v2 file2
# global sequence numbering
    return parser.parse_args()
# end getCmdLineArgs (…)


"""mesh2scad( msh )

Create .scad 3d model from a stored stl mesh

@param msh - model mesh structure from numpy-stl
@outputs one or more scad models
"""
def mesh2scad ( msh ):
    # the 'trivial' keep all duplicate points
    pts = np.reshape ( msh.vectors, ( -1, 3 )) # change shape( facets, 3, 3 ) to ( facets * 3, 3 )
    fcs = np.reshape ( np.arange ( 0, len ( pts )), ( -1, 3 )) # straight start to finish point sequence
    return { 'points': pts, 'faces': fcs, 'name': msh.name }
# end mesh2scad (…)


"""model2File ( )

Save 3d model to scad file

@param scadModel - OpenSCAD description of 3d object model

@param fNmPieces - tupple of string pieces to use to create .scad save file name
# TODO generate the file name before calling, and pass only the file specification
@param seq - sequence number of model within sub-assembly: None when complete model
"""
def model2File ( scadModel, oSpec, seq ):
    oFile = initScadFile ( oSpec )
    if ( oFile == None ):
        # return? raise?
        print ( 'failed to open file to save OpenSCAD module to: "%s"' % oSpec )
        return False
    oFile.write ( 'module %s() {\n' % scadModel [ 'name' ] )
    oFile.write ( '\tpolyhedron(\n' )
    oFile.write ( '\t\tpoints=[\n\t\t\t' )
    # That join seems rather convoluted for the result.  It *works* but…
    # oFile.write ( ",\n\t\t\t".join ([ str(pt) for pt in scadModel [ 'points' ].tolist ()]))
    # Convert numpy array to python list; convert each (point) element in that
    # list to a string; join the strings with comma separators and whitespace
    oFile.write ( ",\n\t\t\t".join ([ point2str ( pt ) for pt in scadModel [ 'points' ].tolist ()]))
    oFile.write ( '\n\t\t],\n' ) # end of points
    oFile.write ( '\t\t%s=[\n\t\t\t' % 'faces' ) # 'triangles' for compatibility
    oFile.write ( ",\n\t\t\t".join ([ str(pt) for pt in scadModel [ 'faces' ].tolist ()]))
    oFile.write ( '\n\t\t]\n' ) # end of faces
    oFile.write ( '\t);\n' ) # end of polyhedron
    oFile.write ( '}\n' ) # end of module
    oFile.write ( '\n%s();\n' % scadModel [ 'name' ] )
    oFile.close()
    return True
# end model2File (…)


"""point2str( pnt )

format a 3d data point (list of 3 floating values) for output to a .scad file

@param pnt - list containing the x,y,z data point coordinates
@returns '[{x}, {y}, {z}]' with coordinate values formatted by specifications
"""
def point2str( pnt ):
    # IDEA use command line parameter to set the precission
    return ''.join ([ '[', ', '.join ([ '%.9g' % c for c in pnt ]), ']' ])
# end point2str(…)


"""fullScadFileSpec ( seq, solName, modName, stlName, StlPath )

generate the full path and file specification for an output .scad module

@global cmdLineArgs - parsed command line arguments

@param seq - sequence number of model within sub-assembly: None when complete model
@param solName - the name of the solid loaded from the stl file
@param modName - the module name
@param stlName - the name (without path) of the input stl file
@param stlPath - the path to the input stl file
@returns .scad file specification
"""
def fullScadFileSpec ( seq, solName, modName, stlPath, stlName ):
    # TODO check cmdLineArgs for rules to append sequence / suffix / prefix to
    #  file name
    # --destination «path» --size «digits» --type «alpha¦decimal¦hex»
    # --separator «string» --prefix «string» --noseparator --seqalways
    # --module «solid¦stl¦quoted»

    if ( seq == None ):
        # TODO handle --seqalways
        sfx = ''
    else:
        # TODO handle --type --size --noseparator
        # fmt = '%s%%0%d' % ( cmdLineArgs.separtor, cmdLineArgs.size )
        fmt = '%s%%0%dd' % ( '_', 3 )
        sfx = fmt % seq
    # TODO handle --module
    # fName = '%s%s%s%sscad' ( cmdLineArgs.prefix, solName, sfx, os.path.extsep )
    fName = '%s%s%s%sscad' % ( '', solName, sfx, os.path.extsep )
    if ( stlPath == '' ):
        return fName
    # handle --destination
    return os.path.join ( os.path.relpath ( stlPath ), fName )
# end fullScadFileSpec (…)


"""initScadFile ( fileSpec )

open and prepare a file to hold an OpenScad script

@param fileSpec - string with full specification for output file
@returns file handle or None
"""
def initScadFile ( fullSpec ):
    if ( not isV3 ): # python 2 does not have 'x' mode for file open: check first
        # IDEA TODO check if file exists without attempting to open it : os.stat
        try:
            f = open ( fullSpec, mode = 'r' )
        # except FileNotFoundError: # python3
        except IOError: # python2
            # targetExists = True
            pass
        else:
            # TODO ask to overwrite
            f.close() # *REALLY* an error, should not exist
            print ( '%s already exists, aborting write' % fullSpec ) # DEBUG
            return None
        # print ( 'ready to open %s for write' % fullSpec ) # DEBUG
        # try wrapper? include (with another isV3) below?
        return open ( fullSpec, mode = 'w' ) # mode = 'x' not in python 2.7.12

    # try:
    # if ( isV3 ):
    return open ( fullSpec, mode = 'x' )
    # except FileExistsError: # python3
    # except IOError: # python2
    # return None # STUB
# end initScadFile (…)


"""getBaseModuleName ( solName, stlName )

Determine the name to use as the base for modules generated from the current
stl file.

Sources of information to use:
- options from the command line
- the solid name from the STL file
- the (base) name of the input STL file

@global cmdLineArgs - parsed command line arguments

@param solName - the name of the solid loaded from the stl file
@param stlName - the name (without path) of the input stl file
@returns string with desired (base) scad module name
"""
def getBaseModuleName ( solName, stlName ):
    if ( len ( solName ) > 1 ):
        baseModule = solName
    else:
        # IDEA: with linux, remove (possible) multiple extentions?
        splitName = os.path.splitext ( stlName )
        # splitName = stlName.rsplit ( '.', 1 )
        if ( len ( splitName[0] )> 1 and len ( splitName[1] )< 5 ):
            baseModule = splitName[0]
        else:
            baseModule = stlName
    if ( len ( baseModule ) < 2 ):
        baseModule = 'stlmodule'

    return baseModule
# end getBaseModuleName (…)


def main ():
    cmdLineArgs = getCmdLineArgs()
    # if ( cmdLineArgs.verbosity > 0 ):
    #     print ( '\nstl2scad converter version %s' % STL2SCAD_VERSION )
    for f in cmdLineArgs.file:
    #     print ( '\nnew file: |%s|' % f.name ) # DEBUG
        stlPath, stlFile = os.path.split ( f.name )
        try:
            stlMesh = mesh.Mesh.from_file( f.name )
        except AssertionError: # error cases explicitly checked for by the library code
            t, v, tb = sys.exc_info()
            print ( '\n|%s| is probably not a (valid) STL file.\nLibrary refused to load it. Details:\n  %s\n'
                % ( f.name, v ))
            # print ( 'exception: %s\ntraceback: %s' % ( t, tb )) # DEBUG
            # print ( sys.excepthook ( t, v, tb )) # DEBUG
            stlMesh = None
        except: # catchall
            print ( '\n\nFailed to load %s as STL file' % f.name )
            print ( sys.exc_info() )
            stlMesh = None
        # filePathInfo ( f )
        f.close() # done with the stl file opened via command line arguments
        # showMeshInfo( stlMesh )

        # convert from byte array to string object.  Could use utf-8 here, but
        # given the general feel of the stl file format specification, I think
        # ascii is more appropriate
        stlMesh.name = stlMesh.name.decode( "ascii" ) # byte array to string object

        mName = getBaseModuleName( stlMesh.name, stlFile )
        scadModel = mesh2scad ( stlMesh )
        modelSequence = None # TODO get sequence number from scadModel, itterate over models
        oSpec = fullScadFileSpec ( modelSequence, stlMesh.name, mName, stlPath, stlFile )
        if ( model2File ( scadModel, oSpec, modelSequence )):
            print ( '%s ==> %s' % ( os.path.join ( stlPath, stlFile ), oSpec ))
# end main (…)


def filePathInfo ( fh ):
    # keep (part) arround for --verbose
    print ( 'fh.name = "%s"' % fh.name )
    print ( os.statvfs ( fh.name ))
    # p = Path ( '.' ) # v3.4
    # https://docs.python.org/3/library/pathlib.html
    print ( 'fileno: %d' % fh.fileno ())
    print ( 'os.stat_float_times: %s' % os.stat_float_times ())
    if ( isV3 ):
        print ( 'os.stat:', os.stat ( fh.name ))
    else:
        print ( 'os.stat: %s' % os.stat ( fh.name ))
    if ( isV3 ):
        # adds extra outer bracket with python2
        print ( 'os.stat:', os.stat ( fh.name ))
    else:
        # TypeError: not all arguments converted during string formatting python3
        print ( 'os.stat: %s' % os.stat ( fh.name ))
    # print ( os.stat ( fh ))
    # os.path # https://docs.python.org/2.7/library/os.path.html
# end filePathInfo (…)


"""showMeshInfo( msh )

http://numpy-stl.readthedocs.io/en/latest/stl.html#module-stl.base ¦ Variables
msh = mesh.Mesh.from_file( f.name )
 - len ( msh ) == grep --count "facet " test01.stl
msh.name - string name of solid from (ascii) stl file
msh.data - np.array of facet tupples (normal, facet, attr)
 - msh.data[n][0] == msh.normals[n]
 - msh.data[n][1] == msh.vectors[n]
 - msh.data[n][2] == msh.attr[n]
msh.normals - np.array of unit normal vectors for planes defined in vectors
 - normal vectors from loaded stl file seem to be ignored
msh.vectors - np.array of arrays of arrays
 - each (outer) element is an array of vertex coordinates for a single facet
 - each (inner) element is an array of the coordinates for a single vertex
msh.v0 - np.array of first vertex of each facet
 - msh.v0[n] == msh.vectors[n][0]
msh.v1 - np.array of second vertex of each facet
 - msh.v1[n] == msh.vectors[n][1]
msh.v2 - np.array of third vertex of each facet
 - msh.v2[n] == msh.vectors[n][2]
msh.attrs - np.array of attributes per vector (for binary STL)
msh.points - np.array with one member for each facet
 - each element is an array with 9 elements: facet verticies
  v0: x, y, z; v1: x, y, z; v2: x, y, z;
 - msh.points[n] == [num for elem in msh.vectors[n] for num in elem]
 - msh.points[n][0:3] == msh.vectors[n][0]
 - msh.points[n][3:6] == msh.vectors[n][1]
 - msh.points[n][6:9] == msh.vectors[n][2]
 - msh[n] = points[n]
msh.x - np.array of arrays of x coordinates for each facet from stl
 - msh.x[n][d] == msh.vectors[n][d][0]
msh.y - np.array of arrays of y coordinates for each facet from stl
 - msh.y[n][d] == msh.vectors[n][d][1]
msh.z - np.array of arrays of z coordinates for each facet from stl
 - msh.z[n][d] == msh.vectors[n][d][2]
msh.speedups - boolean ?internal? flag used during load attempts, switching
  between ascii and binary
"""
def showMeshInfo( msh ):
    # Keep around to use for --verbose
    vol, cog, inertia = msh.get_mass_properties()
    print( "Volume                                  = {0}".format(vol))
    print( "Position of the center of gravity (COG) = {0}".format(cog))
    print( "Inertia matrix at expressed at the COG  = {0}".format(inertia[0,:]))
    print( "                                          {0}".format(inertia[1,:]))
    print( "                                          {0}".format(inertia[2,:]))

    print ( 'msh Len: %d' % len ( msh )) # 12
#end showMeshInfo (…)


# Run the script
if __name__ == '__main__':
    main()
