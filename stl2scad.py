#!/usr/bin/python
# -*- coding: utf-8 -*-

""" STL to SCAD converter.

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
import inspect # DEBUG

# Pseudo constants: some would be better as enums, but backward compatibility …
STL2SCAD_VERSION = '0.0.1'
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

Create .scad 3d model from a stored mesh

@param msh - model mesh structure from numpy-stl
@outputs one or more scad models
"""
def mesh2scad ( msh ):
    # print ( 'mesh2scad: build module(s) for "%s"' % msh.name ) # TRACE
    # is a class needed here to hold the data? similar to numpy-stl with different details?

    # print ( 'msh.vectors.shape:', msh.vectors.shape ) # DEBUG
    # print ( 'pts.shape:', pts.shape ) # DEBUG
    # print ( 'vectors,pts len: %d, %d' % ( len ( msh.vectors ), len ( pts ))) # DEBUG
    # print ( 'len arange %d' % len ( np.arange ( 0, len ( pts )))) # DEBUG

    # the 'trivial' keep all duplicate points
    pts = np.reshape ( msh.vectors, ( -1, 3 )) # change shape( facets, 3, 3 ) to ( facets * 3, 3 )
    fcs = np.reshape ( np.arange ( 0, len ( pts )), ( -1, 3 )) # straight start to finish point sequence
    return { 'points': pts, 'faces': fcs, 'name': msh.name }
# end mesh2scad (…)


"""model2File ( )

Save 3d model to scad file

@param scadModel - OpenSCAD description of 3d object model
@param fNmPieces - tupple of string pieces to use to create .scad save file name
@param seq - sequence number of model within sub-assembly: None when complete model
"""
def model2File ( scadModel, fNmPieces, seq ):
    # python 2 must have expanded tupple arguments at the end
    # oSpec = fullScadFileSpec ( *fNmPieces, seq )
    oSpec = fullScadFileSpec ( seq, *fNmPieces )
    # print ( 'fullSpec "%s"' % oSpec ) # DEBUG
    oFile = initScadFile ( oSpec )
    if ( oFile == None ):
        # return? raise?
        print ( 'failed to open file to save OpenSCAD module to: "%s"' % oSpec )
        return
    # print ( 'have writeable module file' )
    # tst = point2str( [27.794734954833984, 20.38167953491211, 6.700000199089118e-07] )
    # print ( tst )
    # print ( 'model: %s' % scadModel )
    # print ( 'points: %s' % scadModel [ 'points' ] )
    # print ( 'points: %s' % scadModel [ 'points' ].tolist ())
    # print ( 'points: %s' % [ pt for pt in scadModel [ 'points' ].tolist () ])
    # print ( 'str pts: %s' % scadModel [ 'points' ].tostring ())
    oFile.write ( 'module %s() {\n' % scadModel [ 'name' ] )
    oFile.write ( '\tpolyhedron(\n' )
    oFile.write ( '\t\tpoints=[\n\t\t\t' )
    # That join seems rather convoluted for the result.  It *works* but…
    # oFile.write ( ",\n\t\t\t".join ([ str(pt) for pt in scadModel [ 'points' ].tolist ()]))
    oFile.write ( ",\n\t\t\t".join ([ point2str ( pt ) for pt in scadModel [ 'points' ].tolist ()]))
    oFile.write ( '\n\t\t],\n' ) # end of points
    oFile.write ( '\t\t%s=[\n\t\t\t' % 'faces' ) # 'triangles' for compatibility
    oFile.write ( ",\n\t\t\t".join ([ str(pt) for pt in scadModel [ 'faces' ].tolist ()]))
    oFile.write ( '\n\t\t]\n' ) # end of faces
    oFile.write ( '\t);\n' ) # end of polyhedron
    oFile.write ( '}\n' ) # end of module
    oFile.write ( '\n%s();\n' % scadModel [ 'name' ] )
    oFile.close()
# end model2File (…)


"""point2str( pnt )

format a 3d data point (list of 3 floating values) for output in a .scad file

@param pnt - list containing the x,y,z data point coordinates
@returns '[{x}, {y}, {z}]' with coordinate values formatted by specifications
"""
def point2str( pnt ):
    # too many digits when switches to 'e' formating
    # too many digits for values < 1.0
    # drops extra digit for negative values (minus sign counted as digit?)
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
    # print ( 'fullScadFileSpec for solid "%s" of "%s" from "%s|%s"' %
    #     ( solName, modName, stlPath, stlName )) # TRACE
    # print ( os.path.normpath ( stlPath ))
    # print ( os.path.realpath ( stlPath ))
    # print ( os.path.relpath ( stlPath ))

    # TODO check cmdLineArgs for rules to append sequence / suffix / prefix to
    #  file name
    # --destination «path» --size «digits» --type «alpha¦decimal¦hex»
    # --separator «string» --prefix «string» --noseparator --seqalways
    # --module «solid¦stl¦quoted»

    if ( seq == None ):
        # TODO handle --seqalways
        sfx = ''
    else:
        # TODO handle --type and --size --noseparator
        # fmt = '%s%%0%d' % ( cmdLineArgs.separtor, cmdLineArgs.size )
        fmt = '%s%%0%dd' % ( '_', 3 )
        print ( 'sequence format: %s' % fmt ) # DEBUG
        sfx = fmt % seq
        # sfx = '%03d' % seq
    # TODO handle --module
    # fName = '%s%s%s' ( cmdLineArgs.prefix, solName, sfx )
    fName = '%s%s%s%sscad' % ( '', solName, sfx, os.path.extsep )
    # print ( 'sequenced name "%s"' % fName ) # DEBUG
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
    # initial setup/test : open file, write header and footer
    if ( not isV3 ): # python 2 does not have 'x' mode for file open: check first
        try:
            f = open ( fullSpec, mode = 'r' )
        # except FileNotFoundError: # python3
        except IOError: # python2
            print ( 'Good, %s does not exist yet' % fullSpec ) # DEBUG
        else:
            # TODO ask to overwrite
            f.close() # *REALLY* an error, should not exist
            print ( '%s already exists, aborting write' % fullSpec ) # DEBUG
            return None
        # print ( 'ready to open %s for write' % fullSpec ) # DEBUG
        # try wrapper? include (with another isV3) below?
        return open ( fullSpec, mode = 'w' ) # mode = 'x' not in python 2.7.12

    # print ( 'ready to open %s for exclusive write' % fullSpec ) # DEBUG
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

@param solName - the name of the solid loaded from the stl file
@param stlName - the name (without path) of the input stl file
@returns string with desired (base) scad module name
"""
def getBaseModuleName ( solName, stlName ):
    # print ('getBaseModuleName called for solid "%s" in "%s"' %
    #     ( solName, stlName )) # TRACE
    # TESTING block
    # print ( 'rsplit abc: %s' % 'abc'.rsplit( '.', 1 ))
    # print ( 'rsplit abc.def: %s' % 'abc.def'.rsplit( '.', 1 ))
    # print ( 'rsplit abc.def.z: %s' % 'abc.def.z'.rsplit( '.', 1 ))
    # print ( 'rsplit .abc: %s' % '.abc'.rsplit( '.', 1 ))
    # print ( 'stlName: "%s"' % stlName )
    # print ( 'solName: "%s"' % solName )
    if ( len ( solName ) > 1 ):
        # convert from byte string to string object.  Could use utf-8 here,
        # but given the general feel of the stl file format specification, I
        # think ascii is more appropriate
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
    # print ( '\nstl2scad converter version %s' % STL2SCAD_VERSION )
    # print ( cmdLineArgs ) # DEBUG
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
        # print ( 'stlMesh.shape: %s' % stlMesh.shape )
        # print ( 'stlMesh.data.shape:', stlMesh.data.shape )
        # print ( 'stlMesh.normals.shape:', stlMesh.normals.shape )
        # print ( 'stlMesh.vectors.shape:', stlMesh.vectors.shape )
        # print ( 'stlMesh.v0.shape:', stlMesh.v0.shape )
        # print ( 'stlMesh.x.shape:', stlMesh.v0.shape )
        # print ( 'stlMesh.attrs.shape:', stlMesh.attrs.shape )
        # print ( 'stlMesh.points.shape:', stlMesh.points.shape )
        f.close() # done with the stl file opened via command line arguments
        # showMeshInfo( stlMesh )
        # doIntrospect ( mesh )
        # matchMeshInfo( stlMesh )
        stlMesh.name = stlMesh.name.decode( "ascii" ) # byte string to string object
        mName = getBaseModuleName( stlMesh.name, stlFile )
        # print ( 'Generated (base) scad module name: "%s"' % mName ) # DEBUG
        # hmmmm, overwrite stlMesh.name with the output scad filename?
        # stlMesh.name = mName
        scadModel = mesh2scad ( stlMesh )
        # TODO get sequence number from scadModel, itterate over model
        oSpec = fullScadFileSpec ( None, stlMesh.name, mName, stlPath, stlFile )
        # TODO pass oSpec to model2File instead of parmeeters?
        # is (will) it be possible for model2File to output multiple files?
        model2File ( scadModel, ( stlMesh.name, mName, stlPath, stlFile ), None )
        # model2File ( scadModel, ( stlMesh.name, mName, stlPath, stlFile ), 0 )
        print ( '%s ==> %s' % ( os.path.join ( stlPath, stlFile ), oSpec ))

# end main (…)


def filePathInfo ( fh ):
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
    os.stat_float_times ( False )
    print ( 'os.stat_float_times: %s' % os.stat_float_times ())
    if ( isV3 ):
        # adds extra outer bracket with python2
        print ( 'os.stat:', os.stat ( fh.name ))
    else:
        # TypeError: not all arguments converted during string formatting python3
        print ( 'os.stat: %s' % os.stat ( fh.name ))
    # print ( os.stat ( fh ))
    print ( 'os.pathconf_names: %s' % os.pathconf_names )
    # os.pathconf_names: {
    #   'PC_MAX_INPUT': 2, 'PC_VDISABLE': 8, 'PC_SYNC_IO': 9,
    #   'PC_SOCK_MAXBUF': 12, 'PC_NAME_MAX': 3, 'PC_MAX_CANON': 1,
    #   'PC_PRIO_IO': 11, 'PC_CHOWN_RESTRICTED': 6, 'PC_ASYNC_IO': 10,
    #   'PC_NO_TRUNC': 7, 'PC_FILESIZEBITS': 13, 'PC_LINK_MAX': 0,
    #   'PC_PIPE_BUF': 5, 'PC_PATH_MAX': 4}
    for k in os.pathconf_names:
        print ( 'Key: %s; conf: %s' % ( k, os.pathconf ( fh.name, k )))
    # os.walk
    # os.path # https://docs.python.org/2.7/library/os.path.html
    print ( 'split:', ( os.path.split ( fh.name )))
    print ( 'sep: "%s"' % os.sep )
    print ( 'test out: "%s"' % os.path.join ( os.path.dirname( fh.name ), 'test.scad' ))
# end filePathInfo (…)


"""matchMeshInfo ( msh )

Manual match the content of the loaded mesh with the source STL file

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
def matchMeshInfo ( msh ):
    # print ( 'msh Keys: %s' % msh.__dict__.keys ()) # DEBUG
    # msh Keys: ['speedups', 'vectors', 'attr', 'v0', 'v1', 'v2', 'points',
    #            'normals', 'y', 'x', 'z', 'data', 'name']
    print ( 'msh.name: "%s"' % msh.name ) # stl solid
    print ( 'msh.speedups: "%s"' % msh.speedups ) # True
    print ( 'msh Len: %d' % len ( msh ))
    print ( 'msh.attr Len: %d' % len ( msh.attr ))
    # print ( 'msh.attr:\n%s' % msh.attr )
    # print 'attr: [',
    # for x in msh.attr:
    #     print x,
    # print ']'
    print ( 'msh.points Len: %d' % len ( msh.points ))
    # print ( 'msh.points:\n%s' % msh.points )
    print ( 'msh.vectors Len: %d' % len ( msh.vectors ))
    # print ( 'msh.vectors: %s' % msh.vectors ) # long
    print ( 'msh.v0,1,2 Len: %d,%d,%d' % ( len ( msh.v0 ), len ( msh.v1 ), len ( msh.v2 )))
    print ( 'msh.x,y,z Len: %d,%d,%d' % ( len ( msh.x ), len ( msh.y ), len ( msh.z )))
    print ( 'msh.data Len: %d' % len ( msh.data ))
    for facet in range ( 0, ( len ( msh.points ))):
        assert ( msh.points [facet] [0:3] == msh.vectors [facet] [0] ).all
        assert ( msh.points [facet] [3:6] == msh.vectors [facet] [1] ).all
        assert ( msh.points [facet] [6:9] == msh.vectors [facet] [2] ).all
        assert ( msh.points [facet] == [num for elem in msh.vectors[facet] for num in elem] ).all
        # print ( '%d@%s:%s' % ( facet, msh.v0 [facet], msh.vectors [facet][0] ))
        assert ( msh.v0 [facet] == msh.vectors [facet] [0] ).all
        assert ( msh.v1 [facet] == msh.vectors [facet] [1] ).all
        assert ( msh.v2 [facet] == msh.vectors [facet] [2] ).all
        for p in range ( 0, 3 ):
            # print ( '(%d,%d)&%s' % ( facet, p, msh.x [facet] [p] ))
            assert msh.x [facet] [p] == msh.vectors[facet] [p] [0]
            assert msh.y [facet] [p] == msh.vectors[facet] [p] [1]
            assert msh.z [facet] [p] == msh.vectors[facet] [p] [2]
        assert ( msh.data [facet] [0] == msh.normals [facet] ).all
        # assert ( msh.data [facet] [1] [0] == msh.v0 [facet] ).all
        # assert ( msh.data [facet] [1] [1] == msh.v1 [facet] ).all
        # assert ( msh.data [facet] [1] [2] == msh.v2 [facet] ).all
        assert ( msh.data [facet] [1] == msh.vectors [facet] ).all
        assert ( msh.data [facet] [2] == msh.attr [facet] ).all
    # print ( 'msh.normals:\n%s' % msh.normals )
    # print ( 'msh.x:\n%s' % msh.x )
 # - msh.data[n][1] == msh.vectors[n]

    # print 'raw msh:',
    # print ( msh )
    # print ( 'raw msh: %s' % msh )
    # raw msh: <stl.mesh.Mesh object at 0x7f9f8e14b6d0>

    # print ( 'msh.data:\n%s' % msh.data )
# end matchMeshInfo (…)


def showMeshInfo( msh ):
    vol, cog, inertia = msh.get_mass_properties()
    print( "Volume                                  = {0}".format(vol))
    print( "Position of the center of gravity (COG) = {0}".format(cog))
    print( "Inertia matrix at expressed at the COG  = {0}".format(inertia[0,:]))
    print( "                                          {0}".format(inertia[1,:]))
    print( "                                          {0}".format(inertia[2,:]))

    # print ( '\nmesh Len: %d' % len ( mesh )) # object of type 'module' has no len()
    # print ( 'mesh.Mesh Len: %d' % len ( mesh.Mesh )) # object of type 'ABCMeta' has no len()
    print ( 'msh Len: %d' % len ( msh )) # 12
    print ( 'msh[0] Len: %d' % len ( msh[0] )) # 9
    # print ( msh.__dict__ )
    print ( len ( msh.__dict__ ))
    print ( msh.__dict__.keys() )
    # print ( msh[0].__dict__ )
    print ( '\nmsh.name |%s|@%d' % ( msh.name, len ( msh.name )))
    print ( 'msh.speedups: %s' % msh.speedups )
    print ( 'msh.normals Len: %d' % len ( msh.normals ))
    print ( 'msh.vectors Len: %d' % len ( msh.vectors ))
    print ( 'msh.attr Len: %d' % len ( msh.attr ))
    print ( 'msh.data Len: %d' % len ( msh.data ))
    print ( 'msh.x Len: %d' % len ( msh.x ))
    print ( 'msh.y Len: %d' % len ( msh.y ))
    print ( 'msh.z Len: %d' % len ( msh.z ))
    print ( 'msh.points Len: %d' % len ( msh.points ))
    print ( 'msh.v0 Len: %d' % len ( msh.v0 ))
    print ( 'msh.v1 Len: %d' % len ( msh.v1 ))
    print ( 'msh.v2 Len: %d' % len ( msh.v2 ))
    print ( 'full msh' )
    for x in msh:
        print ( '%d %s' % ( len ( x ), x ))
    # print ( 'attr: %s' % msh.attr )
    print ( 'attr: %s' % [ [x[0]] for x in msh.attr ])
    print ( 'points: %s' % msh.points )
    # print ( 'x: %s' % msh.x )
    # print ( 'v0: %s' % msh.v0 )
#end showMeshInfo (…)

def showIntrospectionInfo ( msh ):
    # print ( inspect.getmembers ( inspect ))
    # for x in inspect.getmembers ( inspect ):
    #     print ( x[0] )
    # print ( '\nmesh inspection:' )
    # doIntrospect ( mesh )
    # print ( '\nmesh.Mesh inspection:' )
    # doIntrospect ( mesh.Mesh )
    # print ( '\nmsh inspection:' )
    # doIntrospect ( msh )
    pass
# end showIntrospectionInfo (..)


def memTree ( o ):
    m = inspect.getmembers( o )
    print ( 'object members: %s' % [e[0] for e in inspect.getmembers( m )])
    # for e in inspect.getmembers( m ):
    #     print ( '%s members:' % e[ 0 ])
    #     try:
    #         memTree ( o.e )
    #     except AttributeError:
    #         print ( 'object has no attribute %s' % e[ 0 ])
# end memTree (..)


def doIntrospect ( o ):
    memTree ( o )

    print ( 'object ismodule ? %s' % inspect.ismodule ( o ))
    print ( 'object isclass ? %s' % inspect.isclass ( o ))
    print ( 'object ismethod ? %s' % inspect.ismethod ( o ))
    print ( 'object isfunction ? %s' % inspect.isfunction ( o ))
    print ( 'object isgeneratorfunction ? %s' % inspect.isgeneratorfunction ( o ))
    print ( 'object isgenerator ? %s' % inspect.isgenerator ( o ))
    try:
        print ( 'object iscoroutinefunction ? %s' % inspect.iscoroutinefunction ( o )) # v3.5
    except AttributeError:
        print ( 'object has no iscoroutinefunction attribute' )
    try:
        print ( 'object iscoroutine ? %s' % inspect.iscoroutine ( o )) # v3.5
    except AttributeError:
        print ( 'object has no iscoroutine attribute' )
    try:
        print ( 'object isawaitable ? %s' % inspect.isawaitable ( o ))
    except AttributeError:
        print ( 'object has no isawaitable attribute' )
    print ( 'object istraceback ? %s' % inspect.istraceback ( o ))
    print ( 'object isframe ? %s' % inspect.isframe ( o ))
    print ( 'object iscode ? %s' % inspect.iscode ( o ))
    print ( 'object isbuiltin ? %s' % inspect.isbuiltin ( o ))
    print ( 'object isroutine ? %s' % inspect.isroutine ( o ))
    print ( 'object isabstract ? %s' % inspect.isabstract ( o ))
    print ( 'object ismethoddescriptor ? %s' % inspect.ismethoddescriptor ( o ))
    print ( 'object isdatadescriptor ? %s' % inspect.isdatadescriptor ( o ))
    print ( 'object isgetsetdescriptor ? %s' % inspect.isgetsetdescriptor ( o ))
    print ( 'object ismemberdescriptor ? %s' % inspect.ismemberdescriptor ( o ))

    # print ( inspect.getmoduleinfo ( o ))
    # print ( 'object iscode ? %s' % inspect.iscode ( o ))
    # print ( 'object isdatadescriptor ? %s' % inspect.isdatadescriptor ( o ))
    # print ( 'msh.values Len: %d' % len ( o.values ))
# end doIntrospect (..)


# Run the script
if __name__ == '__main__':
    main()
