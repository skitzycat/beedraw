# used to make app into windows executable by running command:
# /cygdrive/c/Python25/python.exe setup-win.py py2exe

import sys

from distutils.core import setup
import py2exe

options={
  "py2exe" : {
    "excludes" : ['NumPy', 'Numeric', 'core.abs', 'core.max', 'core.min', 'core.round', 'email.Generator', 'email.Iterators', 'email.Utils', 'lib.add_newdoc', 'nose', 'nose.plugins', 'nose.plugins.base', 'nose.plugins.builtin', 'nose.plugins.errorclass', 'nose.tools', 'nose.util', 'scipy', 'testing.Tester', 'win32pdh', 'numpy.absolute', 'numpy.arccos', 'numpy.arccosh', 'numpy.arcsin', 'numpy.arcsinh', 'numpy.arctan', 'numpy.arctanh', 'numpy.bitwise_and', 'numpy.bitwise_or', 'numpy.bitwise_xor', 'numpy.bool_', 'numpy.ceil', 'numpy.conjugate', 'numpy.core.add', 'numpy.core.cdouble', 'numpy.core.complexfloating', 'numpy.core.conjugate', 'numpy.core.csingle', 'numpy.core.double', 'numpy.core.float64', 'numpy.core.float_', 'numpy.core.inexact', 'numpy.core.intc', 'numpy.core.isfinite', 'numpy.core.isnan', 'numpy.core.maximum', 'numpy.core.multiply', 'numpy.core.number', 'numpy.core.single', 'numpy.core.sqrt', 'numpy.cosh', 'numpy.divide', 'numpy.fabs', 'numpy.floor', 'numpy.floor_divide', 'numpy.fmod', 'numpy.greater', 'numpy.hypot', 'numpy.invert', 'numpy.left_shift', 'numpy.less', 'numpy.log', 'numpy.logical_and', 'numpy.logical_not', 'numpy.logical_or', 'numpy.logical_xor', 'numpy.maximum', 'numpy.minimum', 'numpy.negative', 'numpy.not_equal', 'numpy.power', 'numpy.remainder', 'numpy.right_shift', 'numpy.sign', 'numpy.sinh', 'numpy.tan', 'numpy.tanh', 'numpy.true_divide'],
    "includes" : ['sip']

  }
}

sys.path.append("designer")

setup(windows=['beedraw.py','hive.py'],options=options)
