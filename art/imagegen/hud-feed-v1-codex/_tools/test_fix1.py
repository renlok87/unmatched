"""Small regressions for composite metrics, ink and rejected outline selection."""
import sys
sys.dont_write_bytecode=True
import unittest
from PIL import Image, ImageDraw
import fix1_font as ff

class CompositeTests(unittest.TestCase):
    def test_arrow_primary_missing_fallback_has_real_ink(self):
        arrow=chr(0x2192)
        for bold in (False,True):
            for size in (12,16,18,24):
                f=ff.font(size,bold)
                self.assertNotIn(ord(arrow),f.primary_cmap)
                self.assertIn(ord(arrow),f.fallback_cmap)
                self.assertEqual(f.getlength(arrow),f.fallback.getlength(arrow))
                plain=Image.new('L',(60,60));fallback=plain.copy()
                ff._text(ImageDraw.Draw(plain),(0,0),arrow,font=f.primary,fill=255)
                ff.draw_text(ImageDraw.Draw(fallback),(0,0),arrow,font=f,fill=255)
                self.assertIsNone(plain.getbbox())
                self.assertIsNotNone(fallback.getbbox())

    def test_supported_strings_keep_original_pixels(self):
        for bold in (False,True):
            for size in (11,16,21,24):
                f=ff.font(size,bold)
                for text in ('Medusa M13','King Arthur 17/18','rejected: upward '+chr(0xD7)+'123',chr(0x41C)+chr(0x410)+chr(0x41D)+chr(0x401)+chr(0x412)+chr(0x420)):
                    for anchor in (None,'lt'):
                        old=Image.new('L',(600,60));new=old.copy()
                        ff._text(ImageDraw.Draw(old),(3,3),text,font=f.primary,fill=255,anchor=anchor)
                        ff.draw_text(ImageDraw.Draw(new),(3,3),text,font=f,fill=255,anchor=anchor)
                        self.assertEqual(old.tobytes(),new.tobytes())
                        self.assertEqual(f.getbbox(text,anchor=anchor),f.primary.getbbox(text,anchor=anchor))

    def test_same_baseline_and_width_for_mixed_runs(self):
        text='Medusa M13'+chr(0x2192)+'M25'
        for bold in (False,True):
            f=ff.font(24,bold);expected=Image.new('L',(600,60));actual=expected.copy()
            x=0;baseline=f.primary.getmetrics()[0]
            for face,run in f.runs(text):
                ff._text(ImageDraw.Draw(expected),(x,baseline),run,font=face,fill=255,anchor='ls')
                x+=face.getlength(run)
            ff.draw_text(ImageDraw.Draw(actual),(0,0),text,font=f,fill=255)
            self.assertEqual(expected.tobytes(),actual.tobytes())
            self.assertEqual(x,f.getlength(text))

if __name__=='__main__':unittest.main()
