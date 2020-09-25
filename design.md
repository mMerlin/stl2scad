# stl to scad conversion program design

Initial reference information

* [https://github.com/joshuaflanagan/stl2scad](https://github.com/joshuaflanagan/stl2scad)

My current repository

* [https://github.com/mMerlin/stl2scad](https://github.com/mMerlin/stl2scad)

## Goals

Create as many separate objects / (closed) surfaces as possible from each input stl file, without changing the set of vertex points, or adding or removing any facets.  That is, create a separate scad object from each disjoint surface in each stl file.

Initially, the scad options are all polyhedrons.  Later enhancements are intended to build objects from primitive objects and operations.

### Future

* Turn the detected polyhedron objects into union, intersection, differences of primitive scad objects, operations.
* detect duplicate objects
  * in a single file
  * across multiple stl file processed together
  * as sub components of a single object

### data validation

How much is practical to do as part of the data format conversion, and how much should use an external, possibly 3rd party tool?

* [manifold](https://en.wikipedia.org/wiki/Manifold)
  * a manifold is not necessarily closed ??
* interpenetrating objects
* interpenetrating surfaces of a single object

### geometry discussion

disjoint surfaces can touch at one or more vertex points, edges, or faces.
They can also interpenetrate.

### test cases

2 completely disjoint tetrahedrons
2 tetrahedrons that meet at one vertex
2 tetrahedrons that meed at one edges
a single surface that meets itself at a single point
a single surface that meets itself at a single edge
a single surface that meets itself at a single face
a single surface that meets itself at multiple single points, edges, faces
disjoint surfaces that meet each other at multiple single points, edges, faces
Given the surface/face walk processing, interpenetrating surfaces are not a
problem when the surface faces do not share any vertices, edges, faces.

intersecting (with or without interpenetrating) surface segments, with either a
single or disjoint surfaces.
negative surface / volume (hollow interior)

### python

* create a dictionary using a list comprehensive.
  * Actually a [dictionary comprehensive](http://stackoverflow.com/questions/1747817/create-a-dictionary-with-list-comprehension-in-python#1747827)

* [numpy.where](http://docs.scipy.org/doc/numpy/reference/generated/numpy.where.html#numpy.where)
  * [find matching rows in 2 dimensional numpy array](http://stackoverflow.com/questions/25823608/find-matching-rows-in-2-dimensional-numpy-array#25823673)
  * [](http://stackoverflow.com/questions/10565598/numpy-how-to-check-if-array-contains-certain-numbers#10565640)

## sample calls

python stl2scad -i$'\t' file.stl

## definitions

¦ terms ¦ meanings ¦ acronyms ¦ backronyms ¦ alias ¦

* stl
  * STereoLithography
  * backronyms
    * Standard Triangle Language
    * Standard Tessellation Language
  * surface geometry of a 3D object

## data file format

* [ASCII stl](http://www.fabbers.com/tech/STL_Format#Sct_ASCII)
* [binary stl](http://www.fabbers.com/tech/STL_Format#Sct_binary)
* [csg](http://forum.openscad.org/Specification-of-CSG-file-format-td12676.html)
* [scad](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language)
  * [user defined functions and modules](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language#Chapter_7_--_User-Defined_Functions_and_Modules)
  * [polyhedron](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language#polyhedron)

### stl ASCII

```stl
solid <<name>>
«indent» «facet»+
endsolid <<name>>
```

* «name» is optional, but the preceding space is not
* name is a simple text string
  * no spaces?
* indent is one or more spaces (no tabs)

```stl_facet
facet normal «n~i~» «n~j~» «n~k~»
«indent» «oloop»
endfacet
```

* the normal is a vector or length 1.0.  Each «n» is (the decimal number text representation of) a single precision float. «n» may be negative.

```stl_oloop
outer loop
«indent» «vert»
«indent» «vert»
«indent» «vert»
endloop
```

```stl_vert
vertex «v~x~» «v~y~» «v~z~»
```

* a vertex is a 3 dimensional coordinate in the all-positive octant.  Each «v» must be positive-definite (non-negative, and nonzero).
* standard format specification says there are exactly 3 vertex entries in an outer loop (triangle definition).  Other information says that technically there could be more data points, as long as they are all co-planar.

#### parsing

* [js code](https://github.com/thibauts/parse-stl)
* [python](https://w.wol.ph/2015/01/28/readingwriting-3d-stl-files-numpy-stl/)
  * [numpy-stl](http://numpy-stl.readthedocs.io/en/latest/)

### stl binary

* [sct binary](http://www.fabbers.com/tech/STL_Format#Sct_binary)

```stlb
80 bytes ASCII characters ¦ header data
4 bytes unsigned long integer ¦ number of facets in file
«facet»…«4:»
```

```stlb_facet
«normal»
«vert»
«vert»
«vert»
2 bytes unsigned integer ¦ attribute byte count (0)
```

```stlb_normal
4 bytes float ¦ i
4 bytes float ¦ j
4 bytes float ¦ k
```

```stlb_vert
4 bytes float ¦ x
4 bytes float ¦ y
4 bytes float ¦ z
```

## concepts

* hollow, void, manifold, polyhedron
* stl ASCII vertex format text is close enough to a point in an scad polyhedron to not need to convert to floating point and back.  Could just trim extra spaces, insert commas, and wrap with "[]".

## splitDisjointObjects( mdl )

### processing environment

#### Inputs

The model structure contains an objects array (normally with a single entry) that holds dictionary entries with faces and points data as numpy arrays.  The points data is shape (-1, 3).  Each point entry holds the x, y, and z coordinates of a single vertex on the surface defined by the object.  The faces data is shape (-1, 3).  Each face is a triangle, and has 3 index values, one for each vertex.  There are no duplicate points.  Faces that share vertices with connected faces
include 1 or 2 of the same point indexes.

#### Outputs

The objects array updated to hold the disjoint surfaces from the input object(s).
Each input object entry will generate 1 or more dictionary elements with the
same structure as the input.  Each dictionary will contain only the points from
the input that define a single complete surface.  Starting from any face it will
be possible to recursively traverse to 3 adjacent faces (based on the command
edges), and visit every face in the set.  Common edges are used, not common
vertices, because 2 (or more) surface could meet at a single point, without
sharing any faces.  Those cases will create separate disjoint objects.

### processing ideas

* directed edge as hash of 2 endpoint indexes
* generate face, edge, reverse edge, face lookup before start disjoint detection

#### current

* create empty list of disjoint objects
* for each input object, create directed edges for every face, empty list of disjoint surfaces, and a set of faces (all of them) that are not on any disjoint surface
  * while there are any faces not on a disjoint surface
    * create a new empty disjoint surface
    * add any one face that is not part of a disjoint surface to the surface
      * add edges of the face to the surface too
    * process edges while there are unprocessed edges in the disjoint surface
      * if the reverse of the edge is not in the surface, locate the face for the reverse edge, and add it and its edges to the surface
    * add the surface to the list of disjoint surfaces for the object
    * update the set of faces that are not yet on a disjoint surface
  * for each disjoint surface, create a new scad polyhedron object, and add it to the list of disjoint objects
* replace the objects list in the model with the list of disjoint objects

## blue sky features

* calculation and reporting
  * surface area
  * volume
* check for and repair manifold
* split to multiple objects
  * disjoint face sets
  * handle void as a negated (from stl) object, differenced out of outer object
* convert polyhedron to operations on more primitive objects
  * during conversion? separate program that used scad file as input?
* merge co-planar adjacent faces

## scad simplify, optimize, compress

Generate series of primitive scad operations + actions that will generate an equivalent 3D model.

* /home/phil/Documents/evernote/openscad.md # language, primitives

* curve fitting
  * 'knife' edges
  * merge co-planar adjacent faces
    * intermediate step

## environment

¦ virtualenv ¦ venv ¦ python2 ¦ python3 ¦
[https://virtualenv.pypa.io/en/](https://virtualenv.pypa.io/en/)

## notes

* /home/phil/Documents/evernote/stl file manipulation.md

Need a sample stl file with separate objects connected at a single edge

IDEA remove test stl file(s) from repository that are generated programmatically (ie export from OpenScad)
-- that would rely on other versions of OpenScad creating the same content

NOTE: Remember to post a note to [Rick van Hattem](https://w.wol.ph/) ¦ [numpy-stl](https://github.com/WoLpH/numpy-stl/) when have a usable / public version of stl2scad

* web search
  * stl2scad
    * [joshua flanagan](https://github.com/joshuaflanagan/stl2scad)
      * [thingiverse 64709](http://www.thingiverse.com/thing:64709)
      * [thingiverse 62666](http://www.thingiverse.com/thing:62666)
      * [thingiverse 850853](http://www.thingiverse.com/thing:850853)
      * [Convertisseur wiki](https://www.logre.eu/wiki/Convertisseur_STL_vers_SCAD)

Existing code is actually fairly simple.  It seems to extract all data points from the stl facets, generating matching points in a polyhedron, then creating faces from the points.  Could be a lot smarter.  As a start, duplicate points could be merged across facets, reducing the number of data points to about 1 third (with triangular mesh faces, each point will typically be used in 3 different faces).

Do heavy math lifting to find edges to generate simpler 3d solids.  Or 2d extrusions.

* curve fitting : points, edges
  * limited set of equations to attempt to match : limited number of graphic object primitives
    * other than polygon / polyhedron, which the intent is to avoid / minimize usage of.
  * watch for 2D extrude: straight lines in one dimension, arbitrary polygon shape 90° from that.
    * twist, scale can turn 'simple' extrude into complex forms.  Going to be interesting to detect
    * rotate_extrude: watch for circles with common axis
  * locate disjoint subsets, and process separately (in initial passes)

Use ?oct?-i-tree? data structure for storing and finding 'near' points.  And higher level entities / objects.  overlapping cubes at multiple scales.

```sh
virtualenv --python=python3 -v --prompt=py3 basepy3
virtualenv --python=python2 -v --prompt=py2 basepy2
```

Is it practical to user virtualenv for python < 3.3, and venv for 3.3+?

## functional comment block

Header prevents the comments here from being hidden if the previous block is folded in the editor

<!-- cSpell:disable -->
<!-- cSpell:enable -->
<!--
# cSpell:disable
# cSpell:enable
variable, internal abbreviations, acronyms
  cSpell:words oloop stlb basepy
cSpell:ignore
cSpell:enableCompoundWords
-->
