import sfnr._rate
# Wrapper for sfnr._rate.Rate -> Cythonized code
__all__ = ["Rate"]

def Rate(rate, tolerance=0.1):
    return sfnr._rate.Rate(rate, tolerance)
