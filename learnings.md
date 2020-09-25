# Learnings

Information collected while developing the stl2scan program.  Mostly code that was tested in sts2scad, but found not to be the best implementation.  Still want to keep it around for later, because the structure looks good, and may be useful as a starting point later.

The running code was getting way to cluttered with notes

## general

Rough timing says that python3 is about 20% faster than python2 (for this code)

## reverseHash ( edgeHash )

Swap high and low words of a long word ¦ unsigned 64 bit integer

Not currently needed in stl2scad.  Existing location logic is used has it inlined.  The place this was intended to be used «» turned out to be less efficient than the longer original.

```py
""" reverseHash ( edgeHash )

Reverse the edge endpoint indices in a edge hash

Hashes are a 64 unsigned integer, with the 32 bit unsigned index for the first
endpoint of the edge in the upper 32 bits, and the 32 bit unsigned index of the
second endpoint in the lower 32 bits.

@param edgeHash - the hash the uniquely identifies a directed surface edge
@returns the hash for the same edge in the opposite direction
"""
def reverseHash ( edgeHash ):
    # TODO double check the processing time: previous information (memory) says
    # splitting the hash to a list, then combining again is faster than creating
    # the reverse hash directly from expressions
    edgeIndexes = [ edgeHash >> 32, edgeHash & 0xffffffff ]
    return edgeIndexes [ 1 ] << 32 | edgeIndexes [ 0 ]
    # return (( edgHash & 0xffffffff )<< 32 )|( edgHash >> 32 )
    # TODO try a variant using a tuple instead of list?
# end reverseHash (…)
```

## polyhedron2disjointSurfaces( mdl )

```py
# hashedFaceEdges = [[ … ] for oneFace in obj [ 'faces' ]]
# hsh1 = np.array ([[ … ] for oneFace in obj [ 'faces' ]])
hashedFaceEdges = [ array.array ( 'L', [
    oneFace [ 0 ] << 32 | oneFace [ 1 ],
    oneFace [ 1 ] << 32 | oneFace [ 2 ],
    oneFace [ 2 ] << 32 | oneFace [ 0 ]])
    for oneFace in obj [ 'faces' ]]
```

* IDEA turn into array of arrays
* when the array structure is used in addFacesAndEdges, it is significantly faster than using the equivalent numpy array.  A standard python list is about the same speed as the numpy array.  It appears that the iterator for an array is a lot faster than the other 2.

Given the ordering rules for points on a triangular face, faces with a common edge will have the edge endpoints reversed, making the directed edge hash unique.

* This applies to a simple, non-intersecting surface.  This will break for either distinct surfaces that touch at an edge, or a single surface that folds around so that 2 edges of the same surface (that are not on adjacent triangles) touch.

```py
hashedEdges = array.array ( 'L', np.reshape ( hashedFaceEdges, -1 ).tolist()) # 12sec
```

* here, an array is slower then a numpy array.  About 25%

* IDEA create lookup from edge hash to face for reversed edge hash
  * starting face (index number) to set of 3 edge hashes, resshaped to a single dimension list of edge hashed.
    * hashedEdges above.
  * build reversed edged hashes for all the same edges
  * for each forward edge hash, get the index (in the forward list) of the reverse hash
  * that index / 3 (truncated) is the face number the revese edge is in.

```py
nextFaces = [ int ( hashedEdges.index ( reverseHash ( hsh )) / 3 ) for hsh in hashedEdges ]
# usage: nextFaceNumber = nextFaces [ hashedEdges.index ( edgeHash )]
# 'nextFace': nextFaces, # (NOT) used in getAdjacentFace
```

* This simplified implementation is faster for the first surface, slower for the rest.  Probably the index lookup is non-linear: significantly faster near the beginning of the list.
* IDEA do extra setup to get the edge hashes sorted, then use binary search

## collectSurfaceFaces( obj, edgData, seedFace )

* numpy array is immutable: no dynamic appending;
* newSurface = { 'faces': np.empty( 0, np.int64 ), 'edges': np.empty(( 0, 2 ), np.int64 )}
* newSurface = { 'faceindex': array.array( 'I' ), 'edgehash': array.array( 'L' )}
* newSurface = { 'faceindex': [], 'edgehash': []}

* Change from 37 to 21 seconds when change edgehast from array to list,
* reduce another second when also change faceindex to list, and using a set saves another second.  edgehash must be accessed by index, so can not be a set.

## addFaceAndEdges ( sf, faceNum, edgDt )

* for list (or array?) instead of set

```py
sf [ 'faceindex' ].append ( faceNum ) # Add face number to the surface
```

```py
# for hsh in edgDt [ 'naHshByFace' ][ faceNum ]:
# for hsh in edgDt [ 'naFwdBckEdgeHshByFace' ][ faceNum ][ 0 ]:
for hsh in edgDt [ 'byFace' ][ faceNum ]: # significantly faster
    if ( not hsh in sf [ 'edgehash' ]):
        sf [ 'edgehash' ].append ( hsh )
```

* Given the calling sequence, should not need to check for existing edges.  The directed edges used will only exist in a single face, so if the face does not exist on the surface, neither do the edges.
  * At least for a 'proper' surface mesh. What about intersecting mesh?
* above code replaced with a one liner to append all of the face edges to the hash at once.
* Removing the exist check (in the loop) reduced time from 19 seconds to 12

## getAdjacentFace ( sf, edgDt, idx )

```py
reverseHash = (( edgHash & 0xffffffff )<< 32 )|( edgHash >> 32 )

hshIdx = edgDt [ 'byEdge' ].index ( edgHash )
reverseHash = edgDt [ 'laBckHshByEdge' ][ hshIdx ]

if ( reverseHash in sf [ 'edgehash' ]):
    return None
```

* Every (directed) edge for a surface is only used once, on a single face.  When a face is added to the surface, all of the associated edges are too.  If an edge exists in the surface, the owning face is already there, and so are the other edges of that face.

```py
owningFace = np.where(( edgDt [ 'naEdgeByFace' ] == reverseEdge ).all ( axis = 2 ))[ 0 ][ 0 ]
```

```py
edgHash = sf [ 'edgehash' ][ idx ]
nextFace = edgDt [ 'nextFace' ][ edgDt [ 'byEdge' ].index ( edgHash )]
if ( nextFace in sf [ 'faceindex' ]):
    return None
return nextFace
```

* The above simplified code turns out to be slower than the original longer version.  It looks nice though.  Maybe if setup sorted lists, and use binary search?

## surface2polyhedronObject ( sf, o )

* IDEA use face index set parameter, instead of full surface.  Those indexes are used to build both the face and vertex arrays

## numpy-stl

```py
# internal structure data types
print ( pts.dtype, facePoints.dtype ) # DEBUG float32, int64
```

## functional comment block

Header prevents the comments here from being hidden if the previous block is folded in the editor

<!-- cSpell:disable -->
<!-- cSpell:enable -->
<!--
# cSpell:disable
# cSpell:enable
program terms, functions, methods
  cSpell:words tolist dtype
cSpell:ignore
cSpell:enableCompoundWords
-->
