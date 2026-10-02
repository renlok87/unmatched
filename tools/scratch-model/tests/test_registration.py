"""Synthetic registration regressions; python -m unittest discover -s tools/scratch-model/tests -v."""
import sys
import unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from register_views import detect, fit

class RegistrationTest(unittest.TestCase):
    measurements=[]
    def test_shift_scale_recovery(self):
        target=np.array([[40,40],[983,40],[40,1495],[983,1495]],dtype=float)
        for scale,shift in [(1.018,[9,-7]),(.984,[-5,12]),(1,[.25,-.25])]:
            source=(target-np.array(shift))/scale
            im=Image.new('RGB',(1024,1536),'#B4B4B4');d=ImageDraw.Draw(im)
            for x,y in source:
                d.ellipse((round(x-12),round(y-12),round(x+12),round(y+12)),fill='black')
                d.line((round(x-8),round(y),round(x+8),round(y)),fill='white',width=2)
                d.line((round(x),round(y-8),round(x),round(y+8)),fill='white',width=2)
            detected=detect(im,target);recovered,translation,residual=fit(detected,target)
            error=np.linalg.norm(recovered*source+translation-target,axis=1)
            type(self).measurements.append(dict(source_scale=scale,source_translation_px=shift,max_recovery_error_px=float(error.max()),max_residual_px=float(residual.max())))
            self.assertLessEqual(float(error.max()),.5)
            self.assertLessEqual(float(residual.max()),.5)

    def test_missing_mark_rejected(self):
        with self.assertRaisesRegex(ValueError,'missing_registration_mark'):
            detect(Image.new('RGB',(1024,1536),'#B4B4B4'),[[40,40],[983,40],[40,1495],[983,1495]])

    def test_rotation_cannot_hide_in_translation(self):
        source=np.array([[40,40],[983,40],[40,1495],[983,1495]],dtype=float)
        angle=.008;rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        _,_,residual=fit(source,source@rot)
        self.assertGreater(float(residual.max()),1.5)

if __name__=='__main__':
    import argparse
    from common import report,check
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path)
    args=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistrationTest))
    if args.report:
        report(args.report,{'synthetic_shift_scale':check(result.wasSuccessful(),RegistrationTest.measurements,'recovery and residual each <=0.5 px'),
            'missing_marks_and_rotation_rejected':check(result.wasSuccessful(),result.testsRun,'3 tests succeed')})
    raise SystemExit(0 if result.wasSuccessful() else 1)
