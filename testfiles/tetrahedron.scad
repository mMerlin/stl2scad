// A simple tetrahedron with (approximately) unit length edges
// translate ([ 1.288675, 1.5, 1 ])
module tetrahedron () {
 linear_extrude ( height = .885151766, center = false, scale = 0 )
  circle ( r = .57735, $fn = 3 );
}
echo ( "tetrahedron()" );
