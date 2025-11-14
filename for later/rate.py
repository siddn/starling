import starling._rate
# Wrapper for starling._rate.Rate -> Cythonized code
__all__ = ["Rate"]

def Rate(rate, tolerance=0.1):
    return sfnr._rate.Rate(rate, tolerance)
