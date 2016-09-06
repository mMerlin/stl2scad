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
STL2SCAD_VERSION = '0.0.2'
# This version matches the functionality of
# https://github.com/joshuaflanagan/stl2scad, though the output coordinate
# precission is different for some cases
isV3 = ( sys.hexversion >= 0x030000F0 ) # running with python3 or later

# regular globals: might be better implemented as singleton
# objectSequence = 0
cmdLineArgs = None # command line line argument information used throughout
cfg = {}


"""mesh2scadTrivial ( mdl, msh )

Populate .scad 3d model from a stored stl mesh

Trivial conversion: vertex to point, facet to face, with no changes

@param mdl - the 3d scad model to update
@param msh - the stl mesh (numpy-stl) to get update information from
@outputs updated mdl
"""
def mesh2scadTrivial ( mdl, msh ):
    pts = np.reshape ( msh.vectors, ( -1, 3 )) # change shape( facets, 3, 3 ) to ( facets * 3, 3 )
    facePoints = np.reshape ( np.arange ( 0, len ( pts )), ( -1, 3 )) # straight start to finish point sequence
    mdl [ 'objects' ].append ({ 'points': pts, 'faces': facePoints })
# end mesh2scadTrivial (…)


"""mesh2scadDedup  ( mdl, msh )

Populate .scad 3d model from a stored stl mesh

De-duplicated conversion: matching facet to faces, but with only unique points
from vertices

@param mdl - the 3d scad model to update
@param msh - the stl mesh (numpy-stl) to get update information from
@outputs updated mdl
"""
def mesh2scadDedup ( mdl, msh ):
    # http://docs.scipy.org/doc/numpy/reference/generated/numpy.unique.html
    # np.unique works with a 1d (flatten) array.

    # change shape( facets, 3, 3 ) to ( facets * 3, 3 ) of float coordinates
    ptVectors = np.reshape ( msh.vectors, ( -1, 3 ))
    # change shape( facets * 3, 3 ) to ( facets * 3, 1 ) of stringified vectors
    ptStrings = [ point2str ( pt ) for pt in  ptVectors ]

    # unqStrings = unique vector string representations from ptStrings
    # idx = indicies into ptStrings that gave entries in unqStrings
    # facePoints = for each ptString entry, index in unqStrings
    unqStrings, idx, facePoints = np.unique ( ptStrings, return_index = True, return_inverse = True )

    mdl [ 'objects' ].append ({
        'points': [ ptVectors [ i ] for i in idx ] , # Get numeric version of vectors back
        'faces': np.reshape ( facePoints, ( -1, 3 )) }) # straight vectors lookup to groups of face points
# end mesh2scadDedup (…)


"""model2File ( mdl )

Save 3d model to scad file

@param mdl - description of 3d OpenScad model
"""
def model2File ( mdl ):
    objCnt = len ( mdl [ 'objects' ])
    objSeq = '' if objCnt < 2 else 0
    # print ( 'model2File: {0} objects; starting sequence: {1}'
    #     ''.format ( objCnt, objSeq )) # DEBUG
    for obj in mdl [ 'objects' ]:
        if ( objSeq == '' ):
            mName = mdl [ 'model' ]
        else:
            objSeq += 1
            mName = '{0}{1:03d}'.format ( mdl [ 'model' ], objSeq)
        # print ( 'module: "{0}"'.format ( mName )) # DEBUG

        oFile = initScadFile ( mdl, objSeq )
        if ( oFile == None ):
            # return? raise?
            print ( 'failed to create OpenSCAD module save file' )
            return False # IDEA continue, but set failure flag
        oFile.write ( cfg [ 'moduleFormat' ].format (
                name  = mName,
                # pts   = cfg [ 'dataJoin' ].join ( obj [ 'points' ]), # points already converted to strings
                pts   = cfg [ 'dataJoin' ].join ([ point2str ( pt ) for pt in obj [ 'points' ]]),
                faces = cfg [ 'dataJoin' ].join ([ point2str ( pt ) for pt in obj [ 'faces' ]])))
        oFile.close()
        # TODO handle --quiet
        print ( '{0} ==> {1}'.format (
            os.path.join ( mdl [ 'stlPath' ], mdl [ 'stlFile' ]),
            oFile.name ))
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


"""fullScadFileSpec ( mdl, seq )

generate the full path and file specification for an output .scad module

@inputs global cmdLineArgs - parsed command line arguments

@param mdl - 3d scad model
@param seq - object sequence number in the model
@returns .scad file specification
"""
def fullScadFileSpec ( mdl, seq ):
    # TODO check cmdLineArgs for rules to append sequence / suffix / prefix to
    #  file name
    # --destination «path» --size «digits» --type «alpha¦decimal¦hex»
    # --separator «string» --prefix «string» --noseparator --seqalways
    # --module «solid¦stl¦quoted»

    if ( seq == '' ):
        # TODO handle --seqalways
        sfx = ''
    else:
        # TODO handle --type --size --noseparator
        # fmt = '%s%%0%d' % ( cmdLineArgs.separtor, cmdLineArgs.size )
        fmt = '%s%%0%dd' % ( '_', 3 )
        sfx = fmt % seq
    # TODO handle --module
    fName = '%s%s%s%sscad' % (
        '', # cmdLineArgs.prefix
        mdl [ 'model' ],
        sfx,
        os.path.extsep )
    if ( mdl [ 'stlPath' ] == '' ):
        return fName
    # TODO handle --destination
    return os.path.join ( os.path.relpath ( mdl [ 'stlPath' ]), fName )
# end fullScadFileSpec (…)


"""initScadFile ( mdl, seq )

open and prepare a file to hold an OpenScad script

@param mdl - 3d scad model
@param seq - object sequence number in the model
@returns file handle or None
"""
def initScadFile ( mdl, seq ):
    fullSpec = fullScadFileSpec ( mdl, seq )
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


"""generateModuleName ( mdl )

Determine the name to use as the base for modules generated from the current
stl file.

Sources of information to use:
- options from the command line
- information already loaded into the model

@inputs global cmdLineArgs - parsed command line arguments

@param mdl - 3d scad model
@outputs updated mdl with (base) scad module name
"""
def generateModuleName ( mdl ):
    # TODO handle --module
    # print ( 'generateModuleName:\n{0}'.format ( mdl )) # DEBUG
    if ( len ( mdl [ 'solid' ]) > 1 ):
        mdl [ 'model' ] = mdl [ 'solid' ]
    else:
        # IDEA: with linux, remove (possible) multiple extentions?
        splitName = os.path.splitext ( mdl [ 'stlFile' ])
        # TODO replace manifest constants with named cfg values
        if ( len ( splitName [ 0 ] )> 1 and len ( splitName [ 1 ] )< 5 ):
            mdl [ 'model' ] = splitName [ 0 ]
        else:
            mdl [ 'model' ] = mdl [ 'stlFile' ]
    if ( len ( mdl [ 'model' ] ) < 2 ):
        mdl [ 'model' ] = 'stlmodule'
# end generateModuleName (…)


"""processStlFile ( fh )

process a single input stl file

@inputs global cmdLineArgs - parsed command line arguments

@param fh - handle for stl file
@outputs converted .scad file(s)
"""
def processStlFile ( fh ):
    if ( cmdLineArgs.verbose ):
        filePathInfo ( fh )
    scadModel = newScadModel ( fh.name )
    stlMesh = getMesh ( fh.name )
    fh.close()

    if ( stlMesh == None ):
        return
    scadModel [ 'solid' ] = stlMesh.name.decode( "ascii" )
    generateModuleName( scadModel )
    if ( cmdLineArgs.verbose ):
        showMeshInfo( stlMesh )

    # TODO handle --mode «conversion_mode»
    # «raw¦dedup¦split¦simplify¦«?other?»»
    # mesh2scadTrivial ( scadModel, stlMesh ) # DEBUG
    mesh2scadDedup ( scadModel, stlMesh )

    model2File ( scadModel )
# end processStlFile (…)


"""newScadModel ( solid, srcPath, srcFile )

Create and initialize a dictionary to hold object data for a 3D model

@param srcPath - path to folder containing stl file
@param srcFile - name of stl file, without path
@returns initialized stl model structure (dictionary)
"""
def newScadModel ( srcSpec ):
    stlPath, stlFile = os.path.split ( srcSpec )
    return {
        'stlPath': stlPath,
        'stlFile': stlFile,
        'objects': []
    }
# end newScadModel (…)


def main ():
    getCmdLineArgs()
    initialize ()
    if ( cmdLineArgs.verbose ):
        print ( '\nstl2scad converter version %s' % STL2SCAD_VERSION )
    for f in cmdLineArgs.file:
        # print ( '\nnew file: |%s|' % f.name ) # DEBUG TRACE
        processStlFile ( f )
# end main (…)


"""getCmdLineArgs ()

Collect information from command line arguments

# TODO add verbose descriptions of the purpose and usage of the flags and options
@outputs global cmdLineArgs
"""
def getCmdLineArgs ():
    global cmdLineArgs # The only place this is modified in any function
    parser = argparse.ArgumentParser (
        prog = 'stl2scad',
        description = 'Convert .stl format file to OpenSCAD script' )
    parser.add_argument ( '-v', '--version', action = 'version',
        version = '%(prog)s {ver}'.format ( ver = STL2SCAD_VERSION ))
    parser.add_argument ( 'file', default = sys.stdin,
        nargs = '*',
        type = argparse.FileType ( 'r' ),
        # action = 'append',
        help = 'The .stl file(s) to process' )
    # can not figure out how to tell parse to (also) accept -C without any
    # argument after it. "-C", "-C2014.03" should be treated the same
    parser.add_argument ( '-C', '--scad-version',
        # const = '2014.03',
        # nargs = '?',
        choices = [ '2014.03', 'current'],
        # type = str,
        default = 'current',
        help = 'OpenSCAD compatibility version (default: current)' )
    parser.add_argument ( '-i', '--indent',
        default = '\t',
        help = 'line prefix string to use for each level of nested indenting' )
    parser.add_argument ( '-V', '--verbose',
        # IDEA TODO change to numeric verbosity; change to count instances
        # nargs = 0,
        action = 'store_true',
        help = 'show verbose output' )

    # TODO add (many) more arguments
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

    # save the collected information to a global structure
    cmdLineArgs = parser.parse_args()
    # print ( cmdLineArgs ) # DEBUG
# end getCmdLineArgs (…)


"""def initialize ()

Initialize processing based on the provided command line arguments

@inputs global cmdLineArgs
@outputs global cfg
"""
def initialize ():
    global cfg # The only place this is modified in any function

    # Create some configuration values one time that will (or at least could)
    # get reused

    # format string to use to build a .scad module file
    cfg [ 'moduleFormat'] = (
        'module {lMark}name{rMark}() {lMark}{lMark}\n'
        '{indent1}polyhedron(\n'
        '{indent2}points=[\n{indent3}{lMark}pts{rMark}\n{indent2}],\n'
        '{indent2}{compat}=[\n{indent3}{lMark}faces{rMark}\n{indent2}]\n'
        '{indent1});\n'
        '{rMark}{rMark}\n\n'
        '{lMark}name{rMark}();\n'.format (
            lMark = '{',
            rMark = '}',
            indent1 = cmdLineArgs.indent * 1,
            indent2 = cmdLineArgs.indent * 2,
            indent3 = cmdLineArgs.indent * 3,
            compat = 'triangles' if cmdLineArgs.scad_version == '2014.03' else 'faces'
        ))
    # string to use to join a set of vectors for output to a .scad file
    cfg [ 'dataJoin' ] = ',\n{indent3}'.format ( indent3 = cmdLineArgs.indent * 3 )
    # print ( 'moduleFormat:\n%s' % cfg [ 'moduleFormat'] ) # DEBUG
    # print ( 'datajoin: "%s"' % cfg [ 'dataJoin' ] ) # DEBUG
# end initialize (…)


"""getMesh ( fileSpec )

Load an (ascii or binary) stl file to a mesh structure

@param fileSpec - full file path specification for stl file to load
@returns numpy-stl mesh.Mesh.from_file or None
"""
def getMesh ( fileSpec ):
    stlMesh = None
    try:
        stlMesh = mesh.Mesh.from_file( fileSpec )
    except AssertionError: # error cases explicitly checked for by the library code
        t, v, tb = sys.exc_info()
        print ( '\n|%s| is probably not a (valid) STL file.\nLibrary refused to load it. Details:\n  %s\n'
            % ( fileSpec, v ))
        # File too large, triangles which exceeds the maximum of 100000000
        # probably means start of file not recognized as stl solid name, so
        # attempted to load as binary stl, but was really an ascii file.
    except: # catchall
        print ( '\n\nFailed to load %s as STL file' % fileSpec )
        print ( sys.exc_info ())
    return stlMesh
# end getMesh (…)


def filePathInfo ( fh ):
    # keep (part) arround for --verbose
    print ( 'fh.name = "%s"' % fh.name )
    # print ( os.statvfs ( fh.name ))
    # p = Path ( '.' ) # v3.4
    # https://docs.python.org/3/library/pathlib.html
    print ( 'fileno: %d' % fh.fileno ())
    # print ( 'os.stat_float_times: %s' % os.stat_float_times ())
    # print ( 'os.stat: %s' % ( os.stat ( fh.name ), ))
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
    vol, cog, inertia = msh.get_mass_properties()
    print ( '\nSTL Mesh properties:\n' )
    print ( 'Name = "{0}"'.format ( msh.name ))
    print ( 'Volume = {0}'.format ( vol ))
    print ( 'Facets: %d' % len ( msh ))
    print ( 'Position of the center of gravity (COG):\n{0}'.format ( cog ))
    print ( 'Inertia matrix expressed at the COG:\n{0}'.format ( inertia ))

    # print ( msh.x.shape ) # DEBUG
    boundingBox = np.array ([
        [ min ( np.reshape ( msh.x, -1 )), min ( np.reshape ( msh.y, -1 )), min ( np.reshape ( msh.z, -1 ))],
        [ max ( np.reshape ( msh.x, -1 )), max ( np.reshape ( msh.y, -1 )), max ( np.reshape ( msh.z, -1 ))]])
    print ( 'Bounding Box:\n{0}'.format( boundingBox ))
    if ( min ( boundingBox [ 0 ]) <= 0 ):
        print ( '\nNOTE: Not a standard STL source file;\n'
            '  not all points are in the positive quadrant\n' )
#end showMeshInfo (…)


# Run the script
if __name__ == '__main__':
    main()
