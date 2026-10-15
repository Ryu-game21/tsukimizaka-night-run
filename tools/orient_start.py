"""orient cl_xz.npy clockwise (screen) and rotate so index 0 is nearest (sx, sz). usage: orient_start.py sx sz [ccw]"""
import sys, numpy as np
C = np.load('cl_xz.npy'); X, Z = C[:, 0], C[:, 1]
sl = 0.5 * np.sum(X * np.roll(Z, -1) - np.roll(X, -1) * Z)
want_cw = not (len(sys.argv) > 3 and sys.argv[3] == 'ccw')
if (sl > 0) != want_cw: C = C[::-1].copy(); print('reversed')
X, Z = C[:, 0], C[:, 1]
k = int(np.argmin(np.hypot(X - float(sys.argv[1]), Z - float(sys.argv[2]))))
C = np.roll(C, -k, 0); np.save('cl_xz.npy', C)
print('start', C[0, :2].round(1), 'heading', (C[1, :2] - C[0, :2]).round(2), 'n', len(C))
