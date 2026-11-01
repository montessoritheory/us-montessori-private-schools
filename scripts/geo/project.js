// project lon/lat points with d3.geoAlbersUsa, scale 1300, translate [487.5, 305] = the us-atlas "albers" files
const d3 = require('d3-geo'); const fs = require('fs');
const proj = d3.geoAlbersUsa().scale(1300).translate([487.5, 305]);
const pts = JSON.parse(fs.readFileSync(process.argv[2]));
fs.writeFileSync(process.argv[3], JSON.stringify(pts.map(([lon, lat]) => proj([lon, lat]) || null)));
