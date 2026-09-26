from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# Convert SVG to PDF
drawing = svg2rlg("ordinal_precision.svg")
renderPDF.drawToFile(drawing, "ordinal_precision.pdf")

print("PDF created successfully")
