import math


def lagrange(x, y, xx):
    n = len(x)
    s = 0
    for i in range(n):
        li = 1
        for j in range(n):
            if j != i:
                li *= (xx - x[j]) / (x[i] - x[j])
        s += y[i] * li
    return s


def razdel_raznosti(x, y):
    n = len(x)
    tabl = [list(y)]
    for k in range(1, n):
        stolb = []
        for i in range(n - k):
            stolb.append((tabl[k - 1][i + 1] - tabl[k - 1][i]) / (x[i + k] - x[i]))
        tabl.append(stolb)
    return tabl


def konech_raznosti(y):
    n = len(y)
    tabl = [list(y)]
    for k in range(1, n):
        stolb = []
        for i in range(n - k):
            stolb.append(tabl[k - 1][i + 1] - tabl[k - 1][i])
        tabl.append(stolb)
    return tabl


def vybor_newton(x, xx):
    n = len(x) - 1
    if xx <= (x[0] + x[n]) / 2:
        return 1
    return 2


def newton_razdel(x, y, xx):
    n = len(x) - 1
    tabl = razdel_raznosti(x, y)
    if vybor_newton(x, xx) == 1:
        s = y[0]
        p = 1
        for k in range(1, n + 1):
            p *= xx - x[k - 1]
            s += tabl[k][0] * p
    else:
        s = y[n]
        p = 1
        for k in range(1, n + 1):
            p *= xx - x[n - k + 1]
            s += tabl[k][n - k] * p
    return s


def newton_konech(x, y, xx):
    n = len(x) - 1
    h = x[1] - x[0]
    tabl = konech_raznosti(y)
    if vybor_newton(x, xx) == 1:
        t = (xx - x[0]) / h
        s = y[0]
        p = 1
        for k in range(1, n + 1):
            p *= t - (k - 1)
            s += p / math.factorial(k) * tabl[k][0]
    else:
        t = (xx - x[n]) / h
        s = y[n]
        p = 1
        for k in range(1, n + 1):
            p *= t + (k - 1)
            s += p / math.factorial(k) * tabl[k][n - k]
    return s


if __name__ == "__main__":
    x = [0.1, 0.2, 0.3, 0.4, 0.5]
    y = [1.25, 2.38, 3.79, 5.44, 7.14]
    print(lagrange(x, y, 0.35))
    print(newton_konech(x, y, 0.15), newton_konech(x, y, 0.47))
    print(newton_razdel([0.15, 0.2, 0.33, 0.47], [1.25, 2.38, 3.79, 5.44], 0.22))
    for stroka in konech_raznosti(y):
        print(stroka)
