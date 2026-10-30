"""Re-deflate the IDAT of packed PNGs (pack_png.py) with libdeflate level 12: ~3% smaller, the same bytes after inflating.
The Claude artifact is at its 256 MiB cap (2026-10-30): upload re-deflated copies of big files to make room. usage: redeflate.py files..."""
import sys,struct,zlib,ctypes,time
L=ctypes.CDLL('libdeflate.so.0');L.libdeflate_alloc_compressor.restype=ctypes.c_void_p
L.libdeflate_zlib_compress.restype=ctypes.c_size_t;L.libdeflate_zlib_compress.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_size_t]
L.libdeflate_zlib_compress_bound.restype=ctypes.c_size_t;L.libdeflate_zlib_compress_bound.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
c=L.libdeflate_alloc_compressor(12);saved=0
for f in sys.argv[1:]:
    png=open(f,'rb').read();i=8;chunks=[]
    while i<len(png):
        n=struct.unpack('>I',png[i:i+4])[0];chunks.append((png[i+4:i+8],png[i+8:i+8+n]));i+=12+n
    idat=b''.join(d for t,d in chunks if t==b'IDAT');raw=zlib.decompress(idat);t0=time.time()
    cap=L.libdeflate_zlib_compress_bound(c,len(raw));buf=ctypes.create_string_buffer(cap)
    n=L.libdeflate_zlib_compress(c,raw,len(raw),buf,cap);new=buf.raw[:n]
    assert zlib.decompress(new)==raw
    if len(new)<len(idat):
        def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
        out=b'\x89PNG\r\n\x1a\n'+b''.join(chunk(t,d) for t,d in chunks if t not in(b'IDAT',b'IEND'))+chunk(b'IDAT',new)+chunk(b'IEND',b'')
        open(f,'wb').write(out);saved+=len(png)-len(out)
    print(f,len(png),'->',len(new),'%.1fs'%(time.time()-t0),flush=True)
print('saved %.2f MB'%(saved/1e6))
