from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# Convert refined SVG to PDF
drawing = svg2rlg("ordinal_precision_refined.svg")
renderPDF.drawToFile(drawing, "ordinal_precision_refined.pdf")

print("Refined PDF created successfully")
