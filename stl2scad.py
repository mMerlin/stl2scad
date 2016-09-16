#!/usr/bin/python
# coding=utf-8

""" STL to SCAD converter.

Convert stl file to OpenSCAD .scad format

This processing logic for this code was initially based on
https://github.com/joshuaflanagan/stl2scad, which in turn came (indirectly)
from the Riham javascript code http://www.thingiverse.com/thing:62666.

Big thanks to [numpy-stl](https://github.com/WoLpH/numpy-stl/) for doing the
heavy lifting of parsing and loading stl files.

This should work when run using either python2 or python3

pip install -r requirements.txt
"""

import os
import sys
import argparse
import numpy as np
from stl import mesh
import array
import time # DEBUG
from functools import wraps # DEBUG

# Pseudo constants
# Semantic Versioning 2.0.0 # http://semver.org/
STL2SCAD_VERSION = '0.0.5'
isV3 = ( sys.hexversion >= 0x030000F0 ) # running with python3 or later

# regular globals: might be better implemented as singleton
# objectSequence = 0 # use when multiple stl input files, and overriding output
# file or module name
cmdLineArgs = None # command line line argument information used throughout
cfg = {}


""" elapsedTime ( context )

Elapsed time reporting decorator

NOTE: Decorators need to be defined before use

IDEA: Move to external common library, then import

@param context - string to include in elapsed time report
@returns elapsed time decorator
"""
def elapsedTime ( context ):
    def decorator ( timedFunction ):
        @wraps ( timedFunction )
        def wrapper ( *args, **kwargs ):
            start_time = time.time ()
            rslt = timedFunction ( *args, **kwargs )
            end_time = time.time ()
            print ( 'elapsed time for {0}: {1}'.format ( context, end_time - start_time ))
            return rslt
        # end wrapper (…)
        return wrapper
    # end decorator (…)
    return decorator
# end elapsedTime (…)


""" mesh2polyhedron ( mdl, msh )

Populate .scad 3d polyhedron model from a stored stl mesh

Trivial conversion: vertex to point, facet to face, with no changes

@param mdl - the 3d scad model to update
@param msh - the stl mesh (numpy-stl) to get model information from
@outputs updated mdl
"""
def mesh2polyhedron ( mdl, msh ):
    pts = np.reshape ( msh.vectors, ( -1, 3 )) # change shape( facets, 3, 3 ) to ( facets * 3, 3 )
    facePoints = np.reshape ( np.arange ( 0, len ( pts )), ( -1, 3 )) # straight start to finish point sequence

    # scad polyhedron details
    mdl [ 'objects' ].append ({ 'points': pts, 'faces': facePoints })
# end mesh2polyhedron (…)


""" mesh2minimizedPolyhedron ( mdl, msh )

Populate .scad 3d polyhedron model from a stored stl mesh

Remove duplicate vertices, and adjust the face indices to match the collapsed
set of data points.

@param mdl - the 3d scad model to update
@param msh - the stl mesh (numpy-stl) to get model information from
@outputs updated mdl
"""
def mesh2minimizedPolyhedron ( mdl, msh ):
    ptVectors = np.reshape ( msh.vectors, ( -1, 3 )) # ( n, 3, 3 ) to ( 3n, 3 )
    # convert vertex point with x,y,z coordinates to single string that can be compared easily
    ptStrings = [ point2str ( pt ) for pt in  ptVectors ] # 3n strings, not a numpy array

    # unqStrings = unique vector string representations from ptStrings
    # vectorIdx = indexes into ptStrings that gave entries in unqStrings
    # facePoints = for each ptString entry, index in unqStrings
    unqStrings, vectorIdx, facePoints = np.unique (
        ptStrings, return_index = True, return_inverse = True )

    # scad polyhedron details
    mdl [ 'objects' ].append ({
        'points': np.array([ ptVectors [ i ] for i in vectorIdx ]), # Get numeric version of vectors back
        'faces': np.reshape ( facePoints, ( -1, 3 )) }) # straight vectors lookup to groups of face points
# end mesh2minimizedPolyhedron (…)


""" polyhedron2disjointSurfaces( mdl )

Split single optimized (no duplicate vertex points) polyhedron to multiple
disjoint polyhedrons.

The total number of faces and points in the generated polyhedrons will be the
same as the number of faces in the input polyhedron.

This will likely fail, or not split, disjoint surfaces that actually have one
or more vertex points in common.
TODO detect / handle in later versions

@param mdl - the 3d scad model to update
@outputs updated mdl
"""
def polyhedron2disjointSurfaces ( mdl ):
    """ faces2edgeHashes ( faces )

    Generate edge based hashs from the vertex point indexes of the faces.  These
    are used to match adjacent (edge to edge) connected faces of a surface.

    @param faces - array of face vertex indexes for each face of a polyhedron
    @returns dictionary of hashes used for locating disjoint surfaces in the faces
    """
    def faces2edgeHashes ( faces ):
        hashedFaceEdges = [ array.array ( 'L', [
            oneFace [ 0 ] << 32 | oneFace [ 1 ],
            oneFace [ 1 ] << 32 | oneFace [ 2 ],
            oneFace [ 2 ] << 32 | oneFace [ 0 ]])
            for oneFace in faces] # generate edge hashes by face
        hashedEdges = np.reshape ( hashedFaceEdges, -1 ).tolist()

        edgeHashes = {
            'byFace': hashedFaceEdges, # used in addFaceAndEdges
            'byEdge': hashedEdges # used in getAdjacentFace
        }
        return edgeHashes
    # end faces2edgeHashes (…)

    ######## end of nested function definitions #######

    disjointPolyhedron = []

    for obj in mdl [ 'objects' ]:
        edgeHashes = faces2edgeHashes ( obj [ 'faces' ])
        closedSurfaces = [] # disjoint surfaces for a single object

        remainingFaces = set ( np.arange ( 0, len ( obj [ 'faces' ])))
        while ( len ( remainingFaces ) > 0 ): # more faces to process
            # Collect the set of faces for a (the next) closed surface
            surfaceFaces = getFacesOfSurface( obj, edgeHashes, remainingFaces )
            closedSurfaces.append ( surfaceFaces ) # add surface to list

            remainingFaces = remainingFaces.difference ( surfaceFaces )
        # end while ( len ( remainingFaces ) > 0 )

        for faceSet in closedSurfaces:
            disjointPolyhedron.append ( surface2polyhedron ( faceSet, obj ))
        # end for faceSet in closedSurfaces
    # end for obj in mdl [ 'objects' ]

    mdl [ 'objects' ] = disjointPolyhedron
# end polyhedron2disjointSurfaces(…)


""" getFacesOfSurface ( obj, edgData, faces )

Extract a single closed surface from the object face data

@param obj - 3d polyhedron object with (disjoint) surfaces
@param edgData - dictionary with different formats of edge data and hashes
@param faces - object faces that are not assigned to a surface yet
@returns set of faces (indexes) on the closed surface
"""
@elapsedTime ( 'getFacesOfSurface' ) # DEBUG
def getFacesOfSurface ( obj, edgData, faces ):
    newSurface = { 'faceindex': set(), 'edgehash': []}

    addFaceAndEdges ( newSurface, faces.pop(), edgData ) # get a starting face
    # add the rest of the connected faces to complete the surface
    curEdge = 0
    while ( curEdge < len ( newSurface [ 'edgehash' ])):
        nextFace = getAdjacentFace ( newSurface, edgData, curEdge )
        addFaceAndEdges ( newSurface, nextFace, edgData ) # add new face to the surface, with its edges
        curEdge += 1
    # end while ( curEdge < len ( newSurface [ 'edgehash' ]))

    return newSurface [ 'faceindex' ]
    # remainingFaces = faces.difference ( newSurface [ 'faceindex' ])
    # return ( remainingFaces, newSurface [ 'faceindex' ])
# end getFacesOfSurface (…)


""" addFaceAndEdges ( sf, faceNum, edgDt )

Add a single face (by index) to the working surface, as well as all of the
edges for that face

@param sf - working surface structure (dictionary)
@param faceNum - the index of the face to add from o [ 'faces' ], or None
@param edgDt - pregenerated edge (hash) data
@outputs updated sf
"""
def addFaceAndEdges ( sf, faceNum, edgDt ):
    if ( not faceNum == None ):
        sf [ 'faceindex' ].add ( faceNum )
        sf [ 'edgehash' ].extend ( edgDt [ 'byFace' ][ faceNum ])
# end addFaceAndEdges (…)


""" getAdjacentFace ( sf, edgDt, idx )

Get the number (index) of the face that includes the edge that is the reverse
direction of the passed (hashed) edge

@param sf - working surface structure (dictionary)
@param edgDt - pre generated object edge data
@param idx - index of the edge to process (in sf [ 'edgehash' ])
@return face number to add to the surface
"""
def getAdjacentFace ( sf, edgDt, idx ):
    # get the existing stored edge hash from the surface
    edgHash = sf [ 'edgehash'][ idx ]
    # get the edge end point indexes back from the (searchable) hash
    # create a new hash for the reverse direction edge
    reverseEdge = [ edgHash & 0xffffffff, edgHash >> 32 ]
    reverseHash = reverseEdge [ 0 ] << 32 | reverseEdge [ 1 ]

    if ( reverseHash in sf [ 'edgehash' ]):
        return None # Face already on the surface: do not add again

    # return the adjacent face index
    return int ( edgDt [ 'byEdge' ].index ( reverseHash ) / 3 ) # 3 edges/face
# end getAdjacentFace (…)


""" surface2polyhedron ( faces, poly )

Create structure containing an scad polyhedron from the subset of faces
(indexes) that define a closed surface within an existing polyhedron

@param faces - close surface faces with vertex indexes to original polyhedron
@param o - object the close surface is a subset of
@returns 3d object dictionary of polyhedron defining the surface
"""
# @elapsedTime ( 'surface2polyhedron' ) # DEBUG
def surface2polyhedron ( faces, poly ):
    # get unique (poly) vertex indexes used in the closed surface faces
    objectPoints = np.unique ( np.reshape ([ poly [ 'faces' ][ faceIdx ]
        for faceIdx in faces ], -1 )).tolist ()
    return {
        'faces': np.array ([[ objectPoints.index ( pt )
            for pt in poly [ 'faces' ][ faceIdx ]]
            for faceIdx in faces ]), # surface faces with indexes to surface points
        'points': np.array ([ poly [ 'points' ][ idx ]
            for idx in objectPoints ])} # vertex points for the closed surface
# end surface2polyhedron (…)


""" model2File ( mdl )

Save 3d model polyhedron(s) to scad file(s)

@param mdl - description of 3d OpenScad model (as polyhedrons)
"""
def model2File ( mdl ):
    objCnt = len ( mdl [ 'objects' ])
    objSeq = '' if objCnt < 2 else 0
    wrapperFile = None
    wFile = None
    for obj in mdl [ 'objects' ]:
        if ( objSeq == '' ):
            mName = mdl [ 'model' ]
        else:
            objSeq += 1
            # TODO implement cmdLineArgs.precision
            mName = '{0}{1:03d}'.format ( mdl [ 'model' ], objSeq)

        if ( not wrapperFile == mdl [ 'model' ]):
            if ( not wFile == None):
                # TODO handle --quiet
                print ( 'object load wrapper ==> {0} '.format ( wFile.name ))
                wFile.close ()
            if ( objSeq == '' ):
                wrapperFile = None
                wFile = None
            else:
                wFile = initScadFile ( mdl, '' )
                if ( wFile == None ):
                    print ( 'failed to create OpenSCAD module wrapper file' )
                    return False
                wrapperFile = mdl [ 'model' ]

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
        if ( wrapperFile == mdl [ 'model' ]):
            wFile.write ( 'use <{0}>\n'.format ( os.path.split ( oFile.name )[ 1 ]))
            # TODO buffer the mName calls until closing wFile, so the use all end up at the top
            wFile.write ( '{0}();\n'.format ( mName ))
        # TODO handle --quiet
        print ( '{0} ==> {1}'.format (
            os.path.join ( mdl [ 'stlPath' ], mdl [ 'stlFile' ]),
            oFile.name ))
        oFile.close ()

    if ( not wrapperFile == None ):
        # TODO handle --quiet
        print ( 'object load wrapper ==> {0} '.format ( wFile.name ))
        wFile.close()

    return True
# end model2File (…)


""" point2str( pnt )

format a 3d data point (list of 3 floating values) for output to a .scad file.

Also used to do equality comparison between data points.

@param pnt - list containing the x,y,z data point coordinates
@returns '[{x}, {y}, {z}]' with coordinate values formatted by specifications
"""
def point2str ( pnt ):
    # IDEA use command line parameter to set the precission
    # IDEA have call time precission, so interal use (for point comparison) can be higher
    return ''.join ([ '[', ', '.join ([ '%.9g' % c for c in pnt ]), ']' ])
# end point2str (…)


""" fullScadFileSpec ( mdl, seq )

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


""" initScadFile ( mdl, seq )

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


""" generateModuleName ( mdl )

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


""" processStlFile ( fh )

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
    # mesh2polyhedron ( scadModel, stlMesh ) # DEBUG
    mesh2minimizedPolyhedron ( scadModel, stlMesh )

    print ( len ( scadModel [ 'objects' ][ 0 ]['faces' ]),
        len ( scadModel [ 'objects' ][ 0 ]['points'])) # DEBUG
    if ( cmdLineArgs.analyze ):
        checkSurfaceIntegrity( scadModel )

    if ( cmdLineArgs.split ):
        polyhedron2disjointSurfaces( scadModel )

    # model2File ( scadModel ) # save the objects to .scad module files
# end processStlFile (…)


""" newScadModel ( solid, srcPath, srcFile )

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


""" checkSurfaceIntegrity( mdl )

Do checks to validate the integrity of the model surfaces.  Check for
leaks, and more problems

TODO summarize checks based on documentation for the individual function calls

IDEA is it practical to run (some of) these checks against the raw mesh data
loaded by numpy-stl ??
- not really.  Needs to start with the de-dupped point list for the checks

NOTE This code is **VERY** slow.  Both check functions.

@param mdl - the 3d scad model to check
"""
def checkSurfaceIntegrity ( mdl ):
    for obj in mdl [ 'objects' ]:
        # IDEA check for self intersecting surfaces: maybe a case where an edge
        # is referenced twice? (twice in each direction)

        # checkVertexesOfFaces ( obj [ 'faces'], len ( obj [ 'points' ]))
        # checkVertexesOfFaces ( obj [ 'faces'], obj [ 'points' ])
        if ( not checkVertexesOfFaces ( obj )):
            print ( 'problem detected with face vertex references' )

        # Edge endpoint (indexes) by face for whole object
        edgByFace = np.array ([[
            [ fc [0], fc [1]],
            [ fc [1], fc [2]],
            [ fc [2], fc [0]]] for fc in obj [ 'faces' ]])
        # The (directed) edges that make up the surface mesh
        if ( not checkEdgeReuse ( np.reshape ( edgByFace, (-1, 2 )) )):
            print ( 'problem detected with face edge usage' )
# end checkSurfaceIntegrity (…)


""" checkVertexesOfFaces ( obj )

See if every vertex point in the object is part of at least 3 different faces

@param obj - dictionary object with the points and faces for a 3d object
@returns boolean false if problem seen with the vertex references
"""
@elapsedTime ( 'checkVertexesOfFaces' ) # DEBUG
def checkVertexesOfFaces ( obj ):
    allGood = True
    reportedSome = False

    vertextIndexes = np.reshape ( obj [ 'faces' ], -1 ).tolist() # no count in np.array
    vertexReferences = [ vertextIndexes.count ( idx )
        for idx in np.arange ( 0, len ( obj [ 'points' ]))]

    if ( cmdLineArgs.verbose ):
        print ( 'Each face vertex is used from {0} to {1} times'.format (
            min ( vertexReferences ), max ( vertexReferences )))
        reportedSome = True

    if ( min ( vertexReferences ) < 3 ):
        allGood = False
        # Need at least 3 references to every vertex of a triangle mesh to have
        # a closed surface
        print ( 'Not enough face vertex references to close the surface' )
        reportedSome = True
        if ( min ( vertexReferences ) < 1 ): # orphan vertexes
            print ( 'Some vertexes are not used for any face' )

    # IDEA TODO make sure no vertex (index) is referenced more than once per face
    #   - each face must have 3 differnt vertex indexes

    if ( reportedSome ):
        print ( '' )
    return allGood
# end checkVertexesOfFaces (…)


""" checkEdgeReuse ( edges )

Verify that every (directed) edge has a matching reverse direction edge

@param edges - numpy array of surface edges
@returns boolean false if problem seen with the edges that are in the surface
"""
@elapsedTime ( 'checkEdgeReuse' ) # DEBUG
def checkEdgeReuse ( edges ):
    # print ( 'checkEdgeReuse' ) # TRACE
    allGood = True

    # print ( 'face edges shape: {0}'.format ( edges.shape )) # DEBUG
    # print ( 'face edges shape: {0}; content:\n{1}'.format (
    #     edges.shape, edges )) # DEBUG
    # print ( 'face edges shape: {0}; content:\n{1}'.format (
    #     edges.shape, edges.tolist ())) # DEBUG

    # print ( edges == ( 3, 0 ))
    # print (( edges == ( 3, 0 )).all (axis = 1 ))
    # print ( np.where(( edges == ( 3, 0 )).all ( axis = 1 )))
    # print ( np.where(( edges == ( 0, 3 )).all ( axis = 1 )))
    # print ([ np.where(( edges == ( 3, 0 )).all ( axis = 1 ))[ 0 ][ 0 ]])
    # print ([ np.where(( edges == ( 0, 3 )).all ( axis = 1 ))[ 0 ][ 0 ]])
    # print ( np.where(( edges == ( 0, 3 )).all ( axis = 1 ))[ 0 ].size )

    # the number of instances (in faces) of each edge
    edgeCounts = [ np.where(( edges == ( edg [ 0 ], edg [ 1 ])).all (
        axis = 1 ))[ 0 ].size for edg in edges ]
    # print ( 'Edge usage counts: {0}'.format ( edgeCounts )) # DEBUG
    # print ( '{0} Edges used exactly once'.format ( edgeCounts.count ( 1 ))) # DEBUG == len ( edges )
    if ( max ( edgeCounts ) > 1 ):
        allGood = False
        # These are directed edges: no edge should be reused
        print ( 'Duplicate edges encountered' )

    # the number of instances (in faces) of edges going the reverse direction
    counterEdgeCounts = [ np.where(( edges == ( edg [ 1 ], edg [ 0 ])).all (
        axis = 1 ))[ 0 ].size for edg in edges ]
    # print ( 'Reverse direction edge usage counts: {0}'.format ( counterEdgeCounts )) # DEBUG
    if ( min ( counterEdgeCounts ) < 1 ):
        allGood = False
        print ( 'Missing {0} reverse direction edges'.format ( counterEdgeCounts.count ( 0 )))

    # IDEA TODO check that reverse edge is not in the same face
    return allGood
# end checkEdgeReuse (…)


def main ():
    getCmdLineArgs()
    initialize ()
    if ( cmdLineArgs.verbose ):
        print ( '\nstl2scad converter version %s' % STL2SCAD_VERSION )
    for f in cmdLineArgs.file:
        processStlFile ( f )
# end main (…)


""" getCmdLineArgs ()

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
    parser.add_argument ( '-a', '--analyze',
        action = 'store_true',
        help = 'analyze the stl data for problems' )
    parser.add_argument ( '-s', '--split',
        action = 'store_true',
        help = 'output separate modules for each disjoint surface' )
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


""" initialize ()

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


""" getMesh ( fileSpec )

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


""" showMeshInfo( msh )

http://numpy-stl.readthedocs.io/en/latest/stl.html#module-stl.base ¦ Variables
msh = mesh.Mesh.from_file( f.name )
 - len ( msh ) == grep --count "facet " test01.stl
msh.name - string name of solid from (ascii) stl file
msh.data - np.array of facet tuples (normal, facet, attr)
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
def showMeshInfo ( msh ):
    vol, cog, inertia = msh.get_mass_properties()
    boundingBox = np.array ([
        [ min ( np.reshape ( msh.x, -1 )), min ( np.reshape ( msh.y, -1 )), min ( np.reshape ( msh.z, -1 ))],
        [ max ( np.reshape ( msh.x, -1 )), max ( np.reshape ( msh.y, -1 )), max ( np.reshape ( msh.z, -1 ))]])
    print ( '\nSTL Mesh properties:\n'
        '\nName = "{0}"'
        '\nVolume = {1}'
        '\n{2} Facets, {3} Vertexes'
        '\nPosition of the center of gravity (COG):\n{4}'
        '\nInertia matrix expressed at the COG:\n{5}'
        '\nBounding Box:\n{6}'
        ''.format ( msh.name, vol, len ( msh ), 3 * len ( msh.v0 ), cog,
        inertia, boundingBox ))

    if ( min ( boundingBox [ 0 ]) <= 0 ):
        print ( '\nNOTE: Not a standard STL source file;\n'
            '  not all points are in the positive quadrant\n' )
#end showMeshInfo (…)


# Run the script
if __name__ == '__main__':
    main()
