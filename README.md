# STL to OpenSCAD conversion

Convert .stl file to OpenSCAD .scad

## Usage

stl2scad [-h] [-v] [-s] [-a] [-V] [-C«version»] [-i«string»] [file]…

## Setup and prerequisites

This program was originally written to run using either python2 or python3. Since python2 is now end-of-life, python2 compatibility is being dropped. If you really need to use python2, it should not be too difficult, but I am not going to make any effort in that direction.

This was originally setup using a virtualenv environment. That has been changed to pipenv.

To get this up and running on your system, you need `python3` installed. To match my environment, `pipenv` is also needed. `pipenv` is not needed, as long as you manage the dependencies yourself. See `Pipfile` for what is needed.  With that, download the repository, either as a zip file and unpack it, or using git. The steps here show using git from the command line.

```sh
git clone https://github.com/mMerlin/stl2scad.git
cd stl2scad
pipenv --three
pipenv install
pipenv shell
stl2scad -h
```

OpenSCAD is not needed to run the conversion, but you will probably want it available to view and work with the results.

To run and examine the output from the minimal test files:

```sh
cd testfiles
OpenSCAD test01.scad
../stl2scad -V test01.stl
OpenSCAD OpenSCAD_Model.scad
rm OpenSCAD_Model.scad
../stl2scad -V -s test01.stl
OpenSCAD OpenSCAD_Model.scad
```

`test01.scad` is used to verify that OpenSCAD is installed and working. It creates and displays a couple of tetrahedron objects. `test01.stl` contains the stl equivalent of the tetrahedron objects. The 2 other `OpenSCAD` command lines create the OpenSCAD polyhedron objects from that, either as a single file, or as disjoint objects with a wrapper to display them. The generated file needs to be deleted (or renamed) before the second run, because stl2scad is configured to refuse to overwrite an existing file.

## Attribution

This script was written from scratch, after looking over:

* [https://github.com/joshuaflanagan/stl2scad](https://github.com/joshuaflanagan/stl2scad)
* [https://www.thingiverse.com/thing:64709](https://www.thingiverse.com/thing:64709)
* [https://www.thingiverse.com/thing:62666](https://www.thingiverse.com/thing:62666)
* [https://www.thingiverse.com/thing:850853](https://www.thingiverse.com/thing:850853)
* [https://www.logre.eu/wiki/Convertisseur_STL_vers_SCAD](https://www.logre.eu/wiki/Convertisseur_STL_vers_SCAD)
Then finding [http://numpy-stl.readthedocs.io](http://numpy-stl.readthedocs.io) to do the heavy lifting for loading
from STL files.

It is licensed under the [MIT license](https://opensource.org/licenses/MIT).

## Reference information

### OpenSCAD import file formats

* stl
* off
* amf
* svg
* csg
* dxf
* png

#### stl file format

* [wiki STL (file_format)](https://en.wikipedia.org/wiki/STL_(file_format))
* [fabbers STL_Format](http://www.fabbers.com/tech/STL_Format)

#### scad file format

An .scad file is not just a data storage format (like stl).  It is a script containing OpenSCAD operations.  Initially though, the only thing of interest is a module creating a polyhedron object.

```scad
module «objectname» () {
  polyhedron (
    points = [
      «[«x~n», «y~n», «z~n» ],»…«4:»
    ],
    faces = [
      «[ «idx, »…«3:»],»…«4:»
    ]
  );
}

«objectname» ();
```

### csg (Constructive Solid Geometry) file format

As for .scad, .csg is really a script file.  It is similar to .scad.  Again, the only initial interest is a polyhedron object.

```csg
group() {
  group() {
    polyhedron(points=[…], faces=[…], convexity = «n»);
  }
}
```

## functional comment block

Header prevents the comments here from being hidden if the previous block is folded in the editor

<!-- cSpell:disable -->
<!-- cSpell:enable -->
<!--
# cSpell:disable
# cSpell:enable
cSpell:words
cSpell:ignore
cSpell:enableCompoundWords
-->
