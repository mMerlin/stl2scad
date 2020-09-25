#!/usr/bin/env python
# coding=utf-8

""" STL to SCAD converter.

Convert stl file to OpenSCAD .scad format

This processing logic for this code was initially based on
https://github.com/joshuaflanagan/stl2scad, which in turn came (indirectly)
from the Riham javascript code http://www.thingiverse.com/thing:62666.

Big thanks to [numpy-stl](https://github.com/WoLpH/numpy-stl/) for doing the
heavy lifting of parsing and loading stl files.

pipenv install
"""
# pylint: disable=fixme

import os
import sys
import argparse
import array
import time # DEBUG
from functools import wraps # DEBUG
import numpy as np
from stl import mesh

# Pseudo constants
# Semantic Versioning 2.0.0 # http://semver.org/
STL2SCAD_VERSION = '0.0.6'

# regular globals: might be better implemented as singleton
# objectSequence = 0 # use when multiple stl input files, and overriding output
# file or module name
CMD_LINE_ARGS = None # command line line argument information used throughout
CFG = {}


def elapsed_time ( context ):
    """ elapsed_time ( context )

    Elapsed time reporting decorator

    NOTE: Decorators need to be defined before use

    IDEA: Move to external common library, then import

    @param context - string to include in elapsed time report
    @returns elapsed time decorator
    """
    def decorator ( timed_function ):
        @wraps ( timed_function )
        def wrapper ( *args, **kwargs ):
            start_time = time.time ()
            rslt = timed_function ( *args, **kwargs )
            end_time = time.time ()
            print ( 'elapsed time for {0}: {1}'.format ( context, end_time - start_time ))
            return rslt
        # end wrapper (…)
        return wrapper
    # end decorator (…)
    return decorator
# end elapsed_time (…)


def mesh2polyhedron ( mdl, msh ):
    """ mesh2polyhedron ( mdl, msh )

    Populate .scad 3d polyhedron model from a stored stl mesh

    Trivial conversion: vertex to point, facet to face, with no changes

    @param mdl - the 3d scad model to update
    @param msh - the stl mesh (numpy-stl) to get model information from
    @outputs updated mdl
    """
    pts = np.reshape( msh.vectors, ( -1, 3 )) # change shape( facets, 3, 3 ) to ( facets * 3, 3 )
    face_points = np.reshape( np.arange( 0, len ( pts )), ( -1, 3 ))
    # straight start to finish point sequence

    # scad polyhedron details
    mdl [ 'objects' ].append ({ 'points': pts, 'faces': face_points })
# end mesh2polyhedron (…)


def mesh2minimized_polyhedron ( mdl, msh ):
    """ mesh2minimized_polyhedron ( mdl, msh )

    Populate .scad 3d polyhedron model from a stored stl mesh

    Remove duplicate vertices, and adjust the face indices to match the collapsed
    set of data points.

    @param mdl - the 3d scad model to update
    @param msh - the stl mesh (numpy-stl) to get model information from
    @outputs updated mdl
    """
    pnt_vectors = np.reshape ( msh.vectors, ( -1, 3 )) # ( n, 3, 3 ) to ( 3n, 3 )
    # convert vertex point with x,y,z coordinates to single string that can be compared easily
    pnt_strings = [ point2str ( pt ) for pt in  pnt_vectors ] # 3n strings, not a numpy array

    # unq_strings = unique vector string representations from pnt_strings
    # vector_idx = indexes into pnt_strings that gave entries in unq_strings
    # face_points = for each ptString entry, index in unq_strings
    _unq_strings, vector_idx, face_points = np.unique (
        pnt_strings, return_index = True, return_inverse = True )

    # scad polyhedron details
    mdl [ 'objects' ].append ({
        'points': np.array([ pnt_vectors[i] for i in vector_idx]), # recreate numeric vectors
        'faces': np.reshape ( face_points, ( -1, 3 )) }) # vectors lookup for face point groups
# end mesh2minimized_polyhedron (…)


def polyhedron2disjoint_surfaces ( mdl ):
    """ polyhedron2disjoint_surfaces( mdl )

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
    def faces2edge_hashes ( faces ):
        """ faces2edge_hashes ( faces )

        Generate edge based hashes from the vertex point indexes of the faces.  These
        are used to match adjacent (edge to edge) connected faces of a surface.

        @param faces - array of face vertex indexes for each face of a polyhedron
        @returns dictionary of hashes used for locating disjoint surfaces in the faces
        """
        hashed_face_edges = [ array.array ( 'L', [
            oneFace [ 0 ] << 32 | oneFace [ 1 ],
            oneFace [ 1 ] << 32 | oneFace [ 2 ],
            oneFace [ 2 ] << 32 | oneFace [ 0 ]])
            for oneFace in faces] # generate edge hashes by face
        hashed_edges = np.reshape ( hashed_face_edges, -1 ).tolist()

        edge_hashes = {
            'byFace': hashed_face_edges, # used in add_face_and_edges
            'byEdge': hashed_edges # used in get_adjacent_face
        }
        return edge_hashes
    # end faces2edge_hashes (…)

    ######## end of nested function definitions #######

    disjoint_polyhedron = []

    for obj in mdl [ 'objects' ]:
        edge_hashes = faces2edge_hashes ( obj [ 'faces' ])
        closed_surfaces = [] # disjoint surfaces for a single object

        remaining_faces = set ( np.arange ( 0, len ( obj [ 'faces' ])))
        while len ( remaining_faces ) > 0: # more faces to process
            # Collect the set of faces for a (the next) closed surface
            surface_faces = get_faces_of_surface( obj, edge_hashes, remaining_faces )
            closed_surfaces.append ( surface_faces ) # add surface to list

            remaining_faces = remaining_faces.difference ( surface_faces )
        # end while len ( remaining_faces ) > 0

        for face_set in closed_surfaces:
            disjoint_polyhedron.append ( surface2polyhedron ( face_set, obj ))
        # end for face_set in closed_surfaces
    # end for obj in mdl [ 'objects' ]

    mdl [ 'objects' ] = disjoint_polyhedron
# end polyhedron2disjoint_surfaces(…)


@elapsed_time ( 'get_faces_of_surface' ) # DEBUG
def get_faces_of_surface ( _obj, edge_data, faces ):
    """ get_faces_of_surface ( obj, edge_data, faces )

    Extract a single closed surface from the object face data

    @param obj - 3d polyhedron object with (disjoint) surfaces
    @param edge_data - dictionary with different formats of edge data and hashes
    @param faces - object faces that are not assigned to a surface yet
    @returns set of faces (indexes) on the closed surface
    """
    new_surface = { 'faceindex': set(), 'edgehash': []}

    add_face_and_edges ( new_surface, faces.pop(), edge_data ) # get a starting face
    # add the rest of the connected faces to complete the surface
    cur_edge = 0
    while cur_edge < len ( new_surface [ 'edgehash' ]):
        next_face = get_adjacent_face ( new_surface, edge_data, cur_edge )
        add_face_and_edges ( new_surface, next_face, edge_data ) # add new face + edges to surface
        cur_edge += 1
    # end while cur_edge < len ( new_surface [ 'edgehash' ])

    return new_surface [ 'faceindex' ]
    # remaining_faces = faces.difference ( new_surface [ 'faceindex' ])
    # return ( remaining_faces, new_surface [ 'faceindex' ])
# end get_faces_of_surface (…)


def add_face_and_edges ( surface, face_num, edge_data ):
    """ add_face_and_edges ( surface, face_num, edge_data )

    Add a single face (by index) to the working surface, as well as all of the
    edges for that face

    @param surface - working surface structure (dictionary)
    @param face_num - the index of the face to add from o [ 'faces' ], or None
    @param edge_data - pregenerated edge (hash) data
    @outputs updated surface
    """
    if not face_num is None:
        surface [ 'faceindex' ].add ( face_num )
        surface [ 'edgehash' ].extend ( edge_data [ 'byFace' ][ face_num ])
# end add_face_and_edges (…)


def get_adjacent_face ( surface, edge_data, idx ):
    """ get_adjacent_face ( surface, edge_data, idx )

    Get the number (index) of the face that includes the edge that is the reverse
    direction of the passed (hashed) edge

    @param surface - working surface structure (dictionary)
    @param edge_data - pre generated object edge data
    @param idx - index of the edge to process (in surface [ 'edgehash' ])
    @return face number to add to the surface
    """
    # get the existing stored edge hash from the surface
    edge_hash = surface [ 'edgehash'][ idx ]
    # get the edge end point indexes back from the (searchable) hash
    # create a new hash for the reverse direction edge
    reverse_edge = [ edge_hash & 0xffffffff, edge_hash >> 32 ]
    reverse_hash = reverse_edge [ 0 ] << 32 | reverse_edge [ 1 ]

    if reverse_hash in surface [ 'edgehash' ]:
        return None # Face already on the surface: do not add again

    # return the adjacent face index
    return int ( edge_data [ 'byEdge' ].index ( reverse_hash ) / 3 ) # 3 edges/face
# end get_adjacent_face (…)


# @elapsed_time ( 'surface2polyhedron' ) # DEBUG
def surface2polyhedron ( faces, poly ):
    """ surface2polyhedron ( faces, poly )

    Create structure containing an scad polyhedron from the subset of faces
    (indexes) that define a closed surface within an existing polyhedron

    @param faces - close surface faces with vertex indexes to original polyhedron
    @param o - object the close surface is a subset of
    @returns 3d object dictionary of polyhedron defining the surface
    """
    # get unique (poly) vertex indexes used in the closed surface faces
    object_points = np.unique ( np.reshape ([ poly [ 'faces' ][ faceIdx ]
        for faceIdx in faces ], -1 )).tolist ()
    return {
        'faces': np.array ([[ object_points.index ( pt )
            for pt in poly [ 'faces' ][ faceIdx ]]
            for faceIdx in faces ]), # surface faces with indexes to surface points
        'points': np.array ([ poly [ 'points' ][ idx ]
            for idx in object_points ])} # vertex points for the closed surface
# end surface2polyhedron (…)


def model2file ( mdl ):
    """ model2file ( mdl )

    Save 3d model polyhedron(s) to scad file(s)

    @param mdl - description of 3d OpenScad model (as polyhedrons)
    """
    obj_cnt = len ( mdl [ 'objects' ])
    obj_seq = '' if obj_cnt < 2 else 0
    wrapper_file = None
    w_file = None
    for obj in mdl [ 'objects' ]:
        if obj_seq == '':
            m_name = mdl [ 'model' ]
        else:
            obj_seq += 1
            # TODO implement CMD_LINE_ARGS.precision
            m_name = '{0}{1:03d}'.format ( mdl [ 'model' ], obj_seq)

        if not wrapper_file == mdl [ 'model' ]:
            if not w_file is None:
                # TODO handle --quiet
                print ( 'object load wrapper ==> {0} '.format ( w_file.name ))
                w_file.close ()
            if obj_seq == '':
                wrapper_file = None
                w_file = None
            else:
                w_file = init_scad_file ( mdl, '' )
                if w_file is None:
                    print ( 'failed to create OpenSCAD module wrapper file' )
                    return False
                wrapper_file = mdl [ 'model' ]

        o_file = init_scad_file ( mdl, obj_seq )
        if o_file is None:
            # return? raise?
            print ( 'failed to create OpenSCAD module save file' )
            return False # IDEA continue, but set failure flag
        o_file.write ( CFG [ 'moduleFormat' ].format (
            name  = m_name,
            # pts   = CFG [ 'dataJoin' ].join ( obj [ 'points' ]), # points already stringified
            pts   = CFG [ 'dataJoin' ].join ([ point2str ( pt ) for pt in obj [ 'points' ]]),
            faces = CFG [ 'dataJoin' ].join ([ point2str ( pt ) for pt in obj [ 'faces' ]])))
        if wrapper_file == mdl [ 'model' ]:
            w_file.write ( 'use <{0}>\n'.format ( os.path.split ( o_file.name )[ 1 ]))
            # TODO buffer the m_name calls until closing w_file, so the `use` all end up at the top
            w_file.write ( '{0}();\n'.format ( m_name ))
        # TODO handle --quiet
        print ( '{0} ==> {1}'.format (
            os.path.join ( mdl [ 'stlPath' ], mdl [ 'stlFile' ]),
            o_file.name ))
        o_file.close ()

    if not wrapper_file is None:
        # TODO handle --quiet
        print ( 'object load wrapper ==> {0} '.format ( w_file.name ))
        w_file.close()

    return True
# end model2file (…)


def point2str ( pnt ):
    """ point2str( pnt )

    format a 3d data point (list of 3 floating values) for output to a .scad file.

    Also used to do equality comparison between data points.

    @param pnt - list containing the x,y,z data point coordinates
    @returns '[{x}, {y}, {z}]' with coordinate values formatted by specifications
    """
    # IDEA use command line parameter to set the precission
    # IDEA have call time precission, so internal use (for point comparison) can be higher
    return ''.join ([ '[', ', '.join ([ '%.9g' % c for c in pnt ]), ']' ])
# end point2str (…)


def full_scad_file_spec ( mdl, seq ):
    """ full_scad_file_spec ( mdl, seq )

    generate the full path and file specification for an output .scad module

    @inputs global CMD_LINE_ARGS - parsed command line arguments

    @param mdl - 3d scad model
    @param seq - object sequence number in the model
    @returns .scad file specification
    """
    # TODO check CMD_LINE_ARGS for rules to append sequence / suffix / prefix to
    #  file name
    # --destination «path» --size «digits» --type «alpha¦decimal¦hex»
    # --separator «string» --prefix «string» --noseparator --seqalways
    # --module «solid¦stl¦quoted»

    if seq == '':
        # TODO handle --seqalways
        sfx = ''
    else:
        # TODO handle --type --size --noseparator
        # fmt = '%s%%0%d' % ( CMD_LINE_ARGS.separator, CMD_LINE_ARGS.size )
        fmt = '%s%%0%dd' % ( '_', 3 )
        sfx = fmt % seq
    # TODO handle --module
    f_name = '%s%s%s%sscad' % (
        '', # CMD_LINE_ARGS.prefix
        mdl [ 'model' ],
        sfx,
        os.path.extsep )
    if mdl [ 'stlPath' ] == '':
        return f_name
    # TODO handle --destination
    return os.path.join ( os.path.relpath ( mdl [ 'stlPath' ]), f_name )
# end full_scad_file_spec (…)


def init_scad_file ( mdl, seq ):
    """ init_scad_file ( mdl, seq )

    open and prepare a file to hold an OpenScad script

    @param mdl - 3d scad model
    @param seq - object sequence number in the model
    @returns file handle or None
    """
    full_spec = full_scad_file_spec ( mdl, seq )
    return open ( full_spec, mode = 'x' )
# end init_scad_file (…)


def generate_module_name ( mdl ):
    """ generate_module_name ( mdl )

    Determine the name to use as the base for modules generated from the current
    stl file.

    Sources of information to use:
    - options from the command line
    - information already loaded into the model

    @inputs global CMD_LINE_ARGS - parsed command line arguments

    @param mdl - 3d scad model
    @outputs updated mdl with (base) scad module name
    """
    # TODO handle --module
    # print ( 'generate_module_name:\n{0}'.format ( mdl )) # DEBUG
    if len ( mdl [ 'solid' ]) > 1:
        mdl [ 'model' ] = mdl [ 'solid' ]
    else:
        # IDEA: with linux, remove (possible) multiple extentions?
        split_name = os.path.splitext ( mdl [ 'stlFile' ])
        # TODO replace manifest constants with named CFG values
        if len ( split_name [ 0 ] )> 1 and len ( split_name [ 1 ] )< 5:
            mdl [ 'model' ] = split_name [ 0 ]
        else:
            mdl [ 'model' ] = mdl [ 'stlFile' ]
    if len ( mdl [ 'model' ] ) < 2:
        mdl [ 'model' ] = 'stlmodule'
# end generate_module_name (…)


def process_stl_file ( f_handle ):
    """ process_stl_file ( f_handle )

    process a single input stl file

    @inputs global CMD_LINE_ARGS - parsed command line arguments

    @param f_handle - handle for stl file
    @outputs converted .scad file(s)
    """
    if CMD_LINE_ARGS.verbose:
        file_path_info ( f_handle )
    scad_model = new_scad_model ( f_handle.name )
    stl_mesh = get_mesh ( f_handle.name )
    f_handle.close()

    if stl_mesh is None:
        return
    scad_model [ 'solid' ] = stl_mesh.name.decode( "ascii" )
    generate_module_name( scad_model )
    if CMD_LINE_ARGS.verbose:
        show_mesh_info( stl_mesh )

    # TODO handle --mode «conversion_mode»
    # «raw¦dedup¦split¦simplify¦«?other?»»
    # mesh2polyhedron ( scad_model, stl_mesh ) # DEBUG
    mesh2minimized_polyhedron ( scad_model, stl_mesh )

    print ( len ( scad_model [ 'objects' ][ 0 ]['faces' ]),
        len ( scad_model [ 'objects' ][ 0 ]['points'])) # DEBUG
    if CMD_LINE_ARGS.analyze:
        check_surface_integrity( scad_model )

    if CMD_LINE_ARGS.split:
        polyhedron2disjoint_surfaces( scad_model )

    model2file ( scad_model ) # save the objects to .scad module files
# end process_stl_file (…)


def new_scad_model ( src_spec ):
    """ new_scad_model ( solid, srcPath, srcFile )

    Create and initialize a dictionary to hold object data for a 3D model

    @param srcPath - path to folder containing stl file
    @param srcFile - name of stl file, without path
    @returns initialized stl model structure (dictionary)
    """
    stl_path, stl_file = os.path.split ( src_spec )
    return {
        'stlPath': stl_path,
        'stlFile': stl_file,
        'objects': []
    }
# end new_scad_model (…)


def check_surface_integrity ( mdl ):
    """ check_surface_integrity( mdl )

    Do checks to validate the integrity of the model surfaces.  Check for
    leaks, and more problems

    TODO summarize checks based on documentation for the individual function calls

    IDEA is it practical to run (some of) these checks against the raw mesh data
    loaded by numpy-stl ??
    - not really.  Needs to start with the de-dupped point list for the checks

    NOTE This code is **VERY** slow.  Both check functions.

    @param mdl - the 3d scad model to check
    """
    for obj in mdl [ 'objects' ]:
        # IDEA check for self intersecting surfaces: maybe a case where an edge
        # is referenced twice? (twice in each direction)

        # check_vertexes_of_faces ( obj [ 'faces'], len ( obj [ 'points' ]))
        # check_vertexes_of_faces ( obj [ 'faces'], obj [ 'points' ])
        if not check_vertexes_of_faces ( obj ):
            print ( 'problem detected with face vertex references' )

        # Edge endpoint (indexes) by face for whole object
        edge_by_face = np.array ([[
            [ fc [0], fc [1]],
            [ fc [1], fc [2]],
            [ fc [2], fc [0]]] for fc in obj [ 'faces' ]])
        # The (directed) edges that make up the surface mesh
        if not check_edge_reuse ( np.reshape ( edge_by_face, (-1, 2 )) ):
            print ( 'problem detected with face edge usage' )
# end check_surface_integrity (…)


@elapsed_time ( 'check_vertexes_of_faces' ) # DEBUG
def check_vertexes_of_faces ( obj ):
    """ check_vertexes_of_faces ( obj )

    See if every vertex point in the object is part of at least 3 different faces

    @param obj - dictionary object with the points and faces for a 3d object
    @returns boolean false if problem seen with the vertex references
    """
    all_good = True
    reported_some = False

    vertex_indexes = np.reshape ( obj [ 'faces' ], -1 ).tolist() # no count in np.array
    vertex_references = [ vertex_indexes.count ( idx )
        for idx in np.arange ( 0, len ( obj [ 'points' ]))]

    if CMD_LINE_ARGS.verbose:
        print ( 'Each face vertex is used from {0} to {1} times'.format (
            min ( vertex_references ), max ( vertex_references )))
        reported_some = True

    if min ( vertex_references ) < 3:
        all_good = False
        # Need at least 3 references to every vertex of a triangle mesh to have
        # a closed surface
        print ( 'Not enough face vertex references to close the surface' )
        reported_some = True
        if min ( vertex_references ) < 1: # orphan vertexes
            print ( 'Some vertexes are not used for any face' )

    # IDEA TODO make sure no vertex (index) is referenced more than once per face
    #   - each face must have 3 different vertex indexes

    if reported_some:
        print ( '' )
    return all_good
# end check_vertexes_of_faces (…)


@elapsed_time ( 'check_edge_reuse' ) # DEBUG
def check_edge_reuse ( edges ):
    """ check_edge_reuse ( edges )

    Verify that every (directed) edge has a matching reverse direction edge

    @param edges - numpy array of surface edges
    @returns boolean false if problem seen with the edges that are in the surface
    """
    # print ( 'check_edge_reuse' ) # TRACE
    all_good = True

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
    edge_counts = [ np.where(( edges == ( edg [ 0 ], edg [ 1 ])).all (
        axis = 1 ))[ 0 ].size for edg in edges ]
    # print('Edge usage counts: {0}'.format ( edge_counts )) # DEBUG
    # print('{0} Edges used exactly once'.format(edge_counts.count(1))) # DEBUG == len(edges)
    if max ( edge_counts ) > 1:
        all_good = False
        # These are directed edges: no edge should be reused
        print ( 'Duplicate edges encountered' )

    # the number of instances (in faces) of edges going the reverse direction
    counter_edge_counts = [ np.where(( edges == ( edg [ 1 ], edg [ 0 ])).all (
        axis = 1 ))[ 0 ].size for edg in edges ]
    # print ( 'Reverse direction edge usage counts: {0}'.format ( counter_edge_counts )) # DEBUG
    if min ( counter_edge_counts ) < 1:
        all_good = False
        print ( 'Missing {0} reverse direction edges'.format ( counter_edge_counts.count ( 0 )))

    # IDEA TODO check that reverse edge is not in the same face
    return all_good
# end check_edge_reuse (…)


def main ():
    '''the main function to start processing'''
    get_cmd_line_args()
    initialize ()
    if CMD_LINE_ARGS.verbose:
        print ( '\nstl2scad converter version %s' % STL2SCAD_VERSION )
    for one_file in CMD_LINE_ARGS.file:
        process_stl_file ( one_file )
# end main (…)


def get_cmd_line_args ():
    """ get_cmd_line_args ()

    Collect information from command line arguments

    # TODO add verbose descriptions of the purpose and usage of the flags and options
    @outputs global CMD_LINE_ARGS
    """
    global CMD_LINE_ARGS # The only place this is modified in any function
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
    CMD_LINE_ARGS = parser.parse_args()
    # print ( CMD_LINE_ARGS ) # DEBUG
# end get_cmd_line_args (…)


def initialize ():
    """ initialize ()

    Initialize processing based on the provided command line arguments

    @inputs global CMD_LINE_ARGS
    @outputs global CFG
    """
    global CFG # The only place this is modified in any function

    # Create some configuration values one time that will (or at least could)
    # get reused

    # format string to use to build a .scad module file
    CFG [ 'moduleFormat'] = (
        'module {lMark}name{rMark}() {lMark}{lMark}\n'
        '{indent1}polyhedron(\n'
        '{indent2}points=[\n{indent3}{lMark}pts{rMark}\n{indent2}],\n'
        '{indent2}{compat}=[\n{indent3}{lMark}faces{rMark}\n{indent2}]\n'
        '{indent1});\n'
        '{rMark}{rMark}\n\n'
        '{lMark}name{rMark}();\n'.format (
            lMark = '{',
            rMark = '}',
            indent1 = CMD_LINE_ARGS.indent * 1,
            indent2 = CMD_LINE_ARGS.indent * 2,
            indent3 = CMD_LINE_ARGS.indent * 3,
            compat = 'triangles' if CMD_LINE_ARGS.scad_version == '2014.03' else 'faces'
        ))
    # string to use to join a set of vectors for output to a .scad file
    CFG [ 'dataJoin' ] = ',\n{indent3}'.format ( indent3 = CMD_LINE_ARGS.indent * 3 )
    # print ( 'moduleFormat:\n%s' % CFG [ 'moduleFormat'] ) # DEBUG
    # print ( 'datajoin: "%s"' % CFG [ 'dataJoin' ] ) # DEBUG
# end initialize (…)


def get_mesh ( file_spec ):
    """ get_mesh ( file_spec )

    Load an (ascii or binary) stl file to a mesh structure

    @param file_spec - full file path specification for stl file to load
    @returns numpy-stl mesh.Mesh.from_file or None
    """
    stl_mesh = None
    try:
        stl_mesh = mesh.Mesh.from_file( file_spec )
    except AssertionError: # error cases explicitly checked for by the library code
        _t, err_details, _tb = sys.exc_info()
        print('\n|%s| is probably not a (valid) STL file.\nLibrary refused to load it. '
              'Details:\n  %s\n' % ( file_spec, err_details ))
        # File too large, triangles which exceeds the maximum of 100000000
        # probably means start of file not recognized as stl solid name, so
        # attempted to load as binary stl, but was really an ascii file.
    except: # catchall
        print ( '\n\nFailed to load %s as STL file' % file_spec )
        print ( sys.exc_info ())
    return stl_mesh
# end get_mesh (…)


def file_path_info ( f_handle ):
    """show file path information for a file handle"""
    # keep (part) around for --verbose
    print ( 'f_handle.name = "%s"' % f_handle.name )
    # print ( os.statvfs ( f_handle.name ))
    # p = Path ( '.' ) # v3.4
    # https://docs.python.org/3/library/pathlib.html
    print ( 'fileno: %d' % f_handle.fileno ())
    # print ( 'os.stat_float_times: %s' % os.stat_float_times ())
    # print ( 'os.stat: %s' % ( os.stat ( f_handle.name ), ))
    # os.path # https://docs.python.org/2.7/library/os.path.html
# end file_path_info (…)


def show_mesh_info ( msh ):
    """ show_mesh_info( msh )

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
    - each element is an array with 9 elements: facet vertices
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
    vol, cog, inertia = msh.get_mass_properties()
    bounding_box = np.array ([
        [ min(np.reshape(msh.x, -1)), min(np.reshape(msh.y, -1)), min(np.reshape(msh.z, -1))],
        [ max(np.reshape(msh.x, -1)), max(np.reshape(msh.y, -1)), max(np.reshape(msh.z, -1))]])
    print ( '\nSTL Mesh properties:\n'
        '\nName = "{0}"'
        '\nVolume = {1}'
        '\n{2} Facets, {3} Vertexes'
        '\nPosition of the center of gravity (COG):\n{4}'
        '\nInertia matrix expressed at the COG:\n{5}'
        '\nBounding Box:\n{6}'
        ''.format ( msh.name, vol, len ( msh ), 3 * len ( msh.v0 ), cog,
        inertia, bounding_box ))

    if min ( bounding_box [ 0 ]) <= 0:
        print ( '\nNOTE: Not a standard STL source file;\n'
            '  not all points are in the positive quadrant\n' )
#end show_mesh_info (…)


# Run the script
if __name__ == '__main__':
    main()

# cSpell:disable
# cSpell:enable
# names, variable names, keywords
#   cSpell:words riham rslt stlmodule nargs statvfs fileno pylint
# functions, methods
#   cSpell:words arange tolist
# terms
#   cSpell:words dedup
# cSpell:words
# cSpell:ignore sscad nstl
# cSpell:enableCompoundWords
