# stl to scad conversion program design

Initial reference information
* https://github.com/joshuaflanagan/stl2scad

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
* ascii stl http://www.fabbers.com/tech/STL_Format#Sct_ASCII
* binary stl http://www.fabbers.com/tech/STL_Format#Sct_binary
* csg http://forum.openscad.org/Specification-of-CSG-file-format-td12676.html
* scad https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language
  * https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language#Chapter_7_--_User-Defined_Functions_and_Modules
  * https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/The_OpenSCAD_Language#polyhedron

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
* the normal is a vector or length 1.0.  Each «n» is (the decimal number text representation of) a single precission float. «n» may be negative.

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
* a vertex is a 3 dimensional coordinate in the all-positive octant.  Each «v» must be postive-definite (nonnegative, and nonzero).
* standard format specification says there are exactly 3 vertex entries in an outer loop (triangle definition).  Other information says that technically there could be more data points, as long as they are all co-planar.

#### parsing
* js code https://github.com/thibauts/parse-stl
* python https://w.wol.ph/2015/01/28/readingwriting-3d-stl-files-numpy-stl/
  * http://numpy-stl.readthedocs.io/en/latest/

### stl binary
* http://www.fabbers.com/tech/STL_Format#Sct_binary

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
* void, manifold, polyhedron
* stl ascci vertex format text is close enough to a point in an scad polyhedron to not need to convert to floating point and back.  Just trim extra spaces, insert commas, and wrap with "[]".

## blue sky features
* calculation and reporting
  * surface area
  * volume
* check for and repair manifold
* split to multiple objects
  * disjoint face sets
  * handle voids at negated (from stl) object, differenced out of outer object
* convert polyhedron to operations on more primitive objects
  * during conversion? separate program that used scad file as input?
* merge co-planar adjacent faces

## scad simplify, optimize, compress

Generate series of primitive scad operations + actions that will generate an equivalent 3D model.

* /home/phil/Documents/evernote/openscad.md # language, primitives

* curve fitting
  * 'knife' edges
  * merge co-planar adjcent faces
    * intermediate step

## environment
¦ virtualenv ¦ venv ¦ python2 ¦ python3 ¦
https://virtualenv.pypa.io/en/


## notes
* /home/phil/Documents/evernote/stl file manipultaion.md

NOTE: Remember to post a note to https://w.wol.ph/ ¦ Rick van Hattem ¦ https://github.com/WoLpH/numpy-stl/ when have a usable / public version of stl2scad

* web search
  * stl2scad
    * https://github.com/joshuaflanagan/stl2scad
      * http://www.thingiverse.com/thing:64709
      * http://www.thingiverse.com/thing:62666
      * http://www.thingiverse.com/thing:850853
      * https://www.logre.eu/wiki/Convertisseur_STL_vers_SCAD

Existing code is actually fairly simple.  It seems to extract all data points from the stl facets, generating matching points in a polyhedron, then creating faces from the points.  Could be a lot smarter.  As a start, duplicate points could be merged across facets, reducing the number of data points to about 1 third (with triangluar mesh faces, each point will typically be used in 3 different faces).

Do heavy math lifting to find edges to generate simpler 3d solids.  Or 2d extrusions.
* curve fitting : points, edges
  * limited set of equations to attempt to match : limited number of graphic object primitives
    * other than polygon / polyhedron, which the intent is to avoid / minimize usage of.
  * watch for 2D extrude: straight lines in one dimension, arbitrary polygon shape 90° from that.
    * twist, scale can turn 'simple' extrude into complex forms.  Going to be interesting to detect
    * rotate_extrude: watch for circles with common axis  
  * locate disjoint subsets, and process separtely (in initial passes)

Use ?oct?-i-tree? data structure for storing and finding 'near' points.  And higher level entities / objects.  overlapping cubes at multiple scales.

```sh
virtualenv --python=python3 -v --prompt=py3 basepy3
virtualenv --python=python2 -v --prompt=py2 basepy2
```
Is it practical to user virtualenv for python < 3.3, and venv for 3.3+?
