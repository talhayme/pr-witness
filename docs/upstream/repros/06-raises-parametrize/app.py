def checked(x):
    if not 0 <= x <= 100:
        raise ValueError(x)
    return x
