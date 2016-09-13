/* A simple tetrahedron

One face on the xy plane.
One edge of that face parallel to the y axis, crossing the negitive x axis
final vertex on the positive z axis

To move to non-negative quadrant, use:
translate ([ pow(3*t*t/4, 0.5) - t * tan(30), t/2, 0 ])
where t is the length of an edge
translate ([ t*0.5, pow(3*t*t/4, 0.5), 0 ])
where t is either the height or the radius

sin(þ) = opp / hyp
cos(þ) = adj / hyp
tan(þ) = opp / adj

hyp = adj / cos(þ)
radius = ( edgeLengh / 2 ) / cos(30)
*/

module tetrahedronByRadius ( radius, center = false ) {
  linear_extrude ( height = radius, center = center, scale = 0 )
   circle ( r = radius, $fn = 3 );
}

module tetrahedron ( height = 1, radius = 0, length = 0, center = false ) {
  if ( radius > 0 ) {
    tetrahedronByRadius ( radius, center = center );
    echo ( "tetrahedron from radius" );
  } else if ( length > 0 ) {
    tetrahedronByRadius ( length * tan(30), center = center ); // .57735
    echo ( "tetrahedron from edge length" );
  } else {
    tetrahedronByRadius ( height, center = center );
    echo ( "tetrahedron from height" );
  }
}
