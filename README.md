# STL to OpenSCAD conversion

Convert .stl file to OpenSCAD .scad

## Usage
stl2scad [-h] [-v] [file]…

## Attribution

This script was written from scratch, after looking over:
* https://github.com/joshuaflanagan/stl2scad
* https://www.thingiverse.com/thing:64709
* https://www.thingiverse.com/thing:62666
* https://www.thingiverse.com/thing:850853
* https://www.logre.eu/wiki/Convertisseur_STL_vers_SCAD
Then finding http://numpy-stl.readthedocs.io to do the heavy lifting for loading
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
* https://en.wikipedia.org/wiki/STL_(file_format)
* http://www.fabbers.com/tech/STL_Format

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

### csg (Constructive Solid Geometry) file format?
As for .scad, .csg is really a script file.  It is similar to .scad.  Again, the only initial interest is a polyhedron object.
```csg
group() {
  group() {
    polyhedron(points=[…], faces=[…], convexity = «n»);
  }
}
```
