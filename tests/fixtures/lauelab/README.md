# lauelab synthetic fixtures

Copied from the lauelab repository at commit d9ff8d1 (`tests/data/geo`,
`tests/config`, `tests/data/synthetic/frames`). Nothing here is measured data:
the frames are deterministic renderings of simulated Ni reflections for
detector `PE1621 723-3335` of the geometry file (see the library's
`tests/data/synthetic/README.md`). `synthetic_ni_empty.h5` is a 256 x 256
sub-region with no spots. They let the portal exercise native indexing end to
end without beamline data.
