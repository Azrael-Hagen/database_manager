#!/usr/bin/env python
"""Verify offline-sync integration into mobile UI."""

import sys
import os
os.chdir('backend')
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

    r = client.get('/m')
    html = r.data.decode()
    
    checks = {
        'Sync banner': 'id="syncStatusBanner"' in html,
        'Conflict modal': 'id="offlineConflictModal"' in html,
        'Pending badge': 'id="pendingPagosCount"' in html,
        'Sync button': 'id="syncNowBtn"' in html,
        'Keep both btn': 'id="conflictKeepBoth"' in html,
        'Keep local btn': 'id="conflictKeepLocal"' in html,
        'Keep server btn': 'id="conflictKeepServer"' in html,
        'LocalDb script': 'src="/m/lib/localdb.js"' in html,
        'Queue script': 'src="/m/lib/offlinequeue.js"' in html,
        'Conflict script': 'src="/m/lib/conflictresolver.js"' in html,
        'SyncMgr script': 'src="/m/lib/syncmanager.js"' in html,
    }
    
    print("=" * 60)
    print("OFFLINE-SYNC MOBILE INTEGRATION VERIFICATION")
    print("=" * 60)
    
    for name, result in checks.items():
        status = '✓' if result else '✗'
        print(f'  {status} {name}')
    
    all_pass = all(checks.values())
    passed = sum(checks.values())
    total = len(checks)
    
    print("=" * 60)
    if all_pass:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print("✅ Mobile integration is complete and ready!")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
        print("Please review the checkpoints above.")
    print("=" * 60)
    exit(0 if all_pass else 1)
