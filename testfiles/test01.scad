use <tetrahedron.scad>

// move to origin, edge on y axis
// r0 = 1;
// translate ([ r0*0.5, pow(3*r0*r0/4, 0.5), 0 ])
//   tetrahedron( radius = r0 );

// move to origin, edge on y axis
// t = 1;
// translate ([ pow(3*t*t/4, 0.5) - t * tan(30), t/2, 0 ])
//   tetrahedron( length = t );

t = 1;
translate ([ 1 + pow(3*t*t/4, 0.5) - t * tan(30), 1 + t/2, t ])
  tetrahedron( length = t );
translate ([ 0.5 + pow(3*t*t/4, 0.5) - t * tan(30), 0.2 + t/2, t / 2 ])
  tetrahedron( length = t );
