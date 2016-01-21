import platform

if platform.system() == "Windows":
    import ctypes
    from ctypes import windll
    from ctypes import wintypes

    kernel32 = windll.kernel32
    iphlpapi = windll.iphlpapi
    Ws2_32 = windll.Ws2_32
    ERROR_INSUFFICIENT_BUFFER = 122
    ERROR_NO_DATA = 232

    class Win32MIBIPFORWARDROW(ctypes.Structure):
        _fields_ = [
            ('dwForwardDest', wintypes.DWORD),
            ('dwForwardMask', wintypes.DWORD),
            ('dwForwardPolicy', wintypes.DWORD),
            ('dwForwardNextHop', wintypes.DWORD),
            ('dwForwardIfIndex', wintypes.DWORD),
            ('dwForwardType', wintypes.DWORD),
            ('dwForwardProto', wintypes.DWORD),
            ('dwForwardAge', wintypes.DWORD),
            ('dwForwardNextHopAS', wintypes.DWORD),
            ('dwForwardMetric1', wintypes.DWORD),
            ('dwForwardMetric2', wintypes.DWORD),
            ('dwForwardMetric3', wintypes.DWORD),
            ('dwForwardMetric4', wintypes.DWORD),
            ('dwForwardMetric5', wintypes.DWORD)
        ]

    class Win32MIBIPFORWARDTABLE(ctypes.Structure):
        _fields_ = [
            ('dwNumEntries', wintypes.DWORD),
            ('table', Win32MIBIPFORWARDROW * 1)
        ]

    kernel32.GetProcessHeap.argtypes = []
    kernel32.GetProcessHeap.restype = wintypes.HANDLE

    # Note: wintypes.ULONG must be replaced with a 64 bit variable on x64
    kernel32.HeapAlloc.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                   wintypes.ULONG]
    kernel32.HeapAlloc.restype = wintypes.LPVOID

    kernel32.HeapFree.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                  wintypes.LPVOID]
    kernel32.HeapFree.restype = wintypes.BOOL

    iphlpapi.GetIpForwardTable.argtypes = [
        ctypes.POINTER(Win32MIBIPFORWARDTABLE),
        ctypes.POINTER(wintypes.ULONG),
        wintypes.BOOL]
    iphlpapi.GetIpForwardTable.restype = wintypes.DWORD

    Ws2_32.inet_ntoa.restype = ctypes.c_char_p

    def get_ipv4_routing_table():
        routing_table = []

        heap = kernel32.GetProcessHeap()

        size = wintypes.ULONG(ctypes.sizeof(Win32MIBIPFORWARDTABLE))
        p = kernel32.HeapAlloc(heap, 0, size)
        if not p:
            raise Exception('Unable to allocate memory for the IP forward '
                            'table')
        p_forward_table = ctypes.cast(
            p, ctypes.POINTER(Win32MIBIPFORWARDTABLE))

        try:
            err = iphlpapi.GetIpForwardTable(p_forward_table,
                                             ctypes.byref(size), 0)
            if err == ERROR_INSUFFICIENT_BUFFER:
                kernel32.HeapFree(heap, 0, p_forward_table)
                p = kernel32.HeapAlloc(heap, 0, size)
                if not p:
                    raise Exception('Unable to allocate memory for the IP '
                                    'forward table')
                p_forward_table = ctypes.cast(
                    p, ctypes.POINTER(Win32MIBIPFORWARDTABLE))

            err = iphlpapi.GetIpForwardTable(p_forward_table,
                                             ctypes.byref(size), 0)
            if err != ERROR_NO_DATA:
                if err:
                    raise Exception('Unable to get IP forward table. '
                                    'Error: %s' % err)

                forward_table = p_forward_table.contents
                table = ctypes.cast(
                    ctypes.addressof(forward_table.table),
                    ctypes.POINTER(Win32MIBIPFORWARDROW *
                                   forward_table.dwNumEntries)).contents

                i = 0
                while i < forward_table.dwNumEntries:
                    row = table[i]
                    routing_table.append((
                        Ws2_32.inet_ntoa(row.dwForwardDest),
                        Ws2_32.inet_ntoa(row.dwForwardMask),
                        Ws2_32.inet_ntoa(row.dwForwardNextHop),
                        row.dwForwardIfIndex,
                        row.dwForwardMetric1))
                    i += 1

            return routing_table
        finally:
            kernel32.HeapFree(heap, 0, p_forward_table)
