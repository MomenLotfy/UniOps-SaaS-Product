"""BUG-010 — the cluster selector must reach the wire.

The backend half of this is covered by ``test_cluster_selector_routing.py``.
This file covers the half that a backend test cannot see: **does the UI actually
put ``cluster_id`` on the request?**

The repository has no JavaScript test runner (no vitest/jest, no ``test`` script
in ``package.json``), so a DOM-level test is not possible here. Rather than
re-implement the frontend logic in Python — which would prove nothing about the
shipped code — these tests execute the **real compiled hook**:

1. the workspace's own TypeScript compiles the actual
   ``src/pages/DevOpsCenter/hooks.ts``;
2. only its unresolvable *import specifiers* are rewritten to local stubs (no
   function body is altered), and the stubbed ``useApi`` records the exact path
   the hook asks for;
3. Node imports the emitted module and the assertions run against the URLs the
   real code produces.

So "selecting cluster A sends ``cluster_id=A``" is observed, not inferred. If
someone later drops the parameter from ``usePods`` or ``clusterScoped``, these
tests fail.

The static test at the bottom is the complement: it fails if a cluster-scoped
call site in a component stops forwarding the selection, which the hook-level
test cannot see.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
FRONTEND = REPO_ROOT / "artifacts" / "uniops"
HOOKS_TS = FRONTEND / "src" / "pages" / "DevOpsCenter" / "hooks.ts"


def _tsc() -> pathlib.Path | None:
    """The workspace's own TypeScript compiler (hoisted to the repo root)."""
    for cand in (
        REPO_ROOT / "node_modules" / ".bin" / "tsc",
        FRONTEND / "node_modules" / ".bin" / "tsc",
    ):
        if cand.exists():
            return cand
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Harness: compile the real hook, stub only its imports, run it in Node
# ─────────────────────────────────────────────────────────────────────────────

_STUBS = {
    # hooks.ts imports these but `clusterScoped` / `usePods` query construction
    # does not depend on their behaviour; the stubs exist so the module loads.
    "stub-react.js": (
        "export const useState = (init) => "
        "[typeof init === 'function' ? init() : init, () => {}];\n"
        "export const useEffect = () => {};\n"
        "export const useCallback = (fn) => fn;\n"
        "export const useRef = (v) => ({ current: v });\n"
    ),
    # The point of this stub: it RECORDS the path instead of fetching, so the
    # test asserts the real URL the hook builds.
    "stub-use-api.js": (
        "export const requested = [];\n"
        "export const useApi = (path) => { requested.push(path); "
        "return { data: null, loading: false, error: null, refetch: () => {} }; };\n"
        "export const apiPost = async () => ({});\n"
        "export const apiDelete = async () => ({});\n"
    ),
    "stub-int.js": (
        "export const useIntegrationsCtx = () => "
        "({ integrations: [], isLoading: false, isConnected: () => false });\n"
    ),
    "stub-ws.js": (
        "export const useWebSocket = () => "
        "({ subscribe: () => () => {}, status: 'connected' });\n"
    ),
}

_SPECIFIER_REWRITES = {
    "'react'": "'./stub-react.js'",
    "'@/hooks/use-api'": "'./stub-use-api.js'",
    "'@/contexts/IntegrationsContext'": "'./stub-int.js'",
    "'@/contexts/WebSocketContext'": "'./stub-ws.js'",
}

_RUNNER = r"""
import { clusterScoped, usePods } from './hooks.js';
import { requested } from './stub-use-api.js';
const out = [];
const eq = (label, got, want) =>
  out.push({ label, got, want, ok: JSON.stringify(got) === JSON.stringify(want) });

// ── clusterScoped: the real compiled helper ──────────────────────────────────
eq('A', clusterScoped('/kubernetes/pods/workloads/deployments', 'cluster-A-id'),
   '/kubernetes/pods/workloads/deployments?cluster_id=cluster-A-id');
eq('B', clusterScoped('/kubernetes/pods/workloads/deployments', 'cluster-B-id'),
   '/kubernetes/pods/workloads/deployments?cluster_id=cluster-B-id');
eq('no selection', clusterScoped('/kubernetes/pods', undefined), '/kubernetes/pods');
eq('empty selection', clusterScoped('/kubernetes/pods', ''), '/kubernetes/pods');
eq('null path passthrough', clusterScoped(null, 'cluster-A-id'), null);
eq('existing querystring', clusterScoped('/gitops?health_status=ok', 'c1'),
   '/gitops?health_status=ok&cluster_id=c1');
eq('encodes the id', clusterScoped('/gitops', 'a b/c'), '/gitops?cluster_id=a%20b%2Fc');

// ── usePods: the real compiled hook, transport stubbed ───────────────────────
requested.length = 0;
usePods(undefined, { clusterId: 'cluster-A-id' });
eq('usePods list A', [...requested][0], '/kubernetes/pods?page_size=100&cluster_id=cluster-A-id');
eq('usePods stats A', [...requested][1], '/kubernetes/pods/stats?cluster_id=cluster-A-id');

requested.length = 0;
usePods(undefined, { clusterId: 'cluster-B-id' });
eq('usePods list B', [...requested][0], '/kubernetes/pods?page_size=100&cluster_id=cluster-B-id');
eq('usePods stats B', [...requested][1], '/kubernetes/pods/stats?cluster_id=cluster-B-id');

requested.length = 0;
usePods(undefined, {});
eq('usePods no selection', [...requested],
   ['/kubernetes/pods?page_size=100', '/kubernetes/pods/stats']);

requested.length = 0;
usePods('jobs', { clusterId: 'c1', includeStats: false });
eq('usePods namespace+cluster', [...requested],
   ['/kubernetes/pods?page_size=100&namespace=jobs&cluster_id=c1', null]);
// A disabled fetch must pass `null`, which useApi short-circuits on — the
// request is genuinely absent from the network, not merely ignored (BUG-016).
eq('disabled stats fetch is null', [...requested][1], null);

console.log(JSON.stringify(out));
process.exit(out.every(o => o.ok) ? 0 : 1);
"""


@pytest.fixture
def compiled_hook(tmp_path):
    """Compile the real hooks.ts and make it importable by Node."""
    if shutil.which("node") is None:
        pytest.skip("node is not available in this environment")
    tsc = _tsc()
    if tsc is None:
        pytest.skip("workspace TypeScript compiler not installed")
    if not HOOKS_TS.exists():
        pytest.fail(f"{HOOKS_TS} disappeared — the DevOps Center hooks moved")

    # tsc reports TS2307 for the aliased imports but still emits JavaScript,
    # which is exactly what we want: real function bodies, stubbable specifiers.
    subprocess.run(
        [str(tsc), str(HOOKS_TS), "--outDir", str(tmp_path),
         "--module", "esnext", "--target", "es2020",
         "--moduleResolution", "bundler", "--skipLibCheck", "--noResolve"],
        cwd=str(FRONTEND), capture_output=True, text=True,
    )
    emitted = tmp_path / "hooks.js"
    if not emitted.exists():
        pytest.fail("tsc emitted no JavaScript for hooks.ts")

    src = emitted.read_text()
    for original, stub in _SPECIFIER_REWRITES.items():
        if original in src:
            src = src.replace(original, stub)
    emitted.write_text(src)

    for name, body in _STUBS.items():
        (tmp_path / name).write_text(body)
    (tmp_path / "runner.mjs").write_text(_RUNNER)
    (tmp_path / "package.json").write_text('{"type": "module"}')
    return tmp_path


def test_frontend_sends_the_selected_cluster(compiled_hook):
    """
    1. selecting cluster A sends ``cluster_id=A``
    2. selecting cluster B sends ``cluster_id=B``
    3. switching A -> B changes the subsequent requests
    4. the Kubernetes read hooks preserve the selection
    5. "All Clusters" omits the parameter entirely
    """
    proc = subprocess.run(
        ["node", "runner.mjs"], cwd=str(compiled_hook),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.fail(
            "the real compiled hook produced the wrong URLs:\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results = json.loads(proc.stdout)
    assert results, "the runner produced no assertions"
    for row in results:
        assert row["ok"], (
            f"{row['label']}: got {row['got']!r}, expected {row['want']!r}"
        )
    labels = {r["label"] for r in results}
    for required in ("A", "B", "usePods list A", "usePods list B",
                     "usePods no selection"):
        assert required in labels, f"runner no longer covers {required!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Static complement: every cluster-scoped call site forwards the selection
# ─────────────────────────────────────────────────────────────────────────────

DEVOPS_DIR = FRONTEND / "src" / "pages" / "DevOpsCenter"

# (file, substring that must appear) — the nine Control-Plane resource fetches
# plus the pod list, which together are every cluster-shaped read in the section.
_REQUIRED_WIRING = [
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'workloads' ? '/kubernetes/pods/workloads/deployments' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'workloads' ? '/kubernetes/pods/workloads/statefulsets' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'workloads' ? '/kubernetes/pods/workloads/daemonsets' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'network' ? '/kubernetes/pods/network/services' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'network' ? '/kubernetes/pods/network/ingresses' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'jobs' ? '/kubernetes/pods/batch/jobs' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'config' ? '/kubernetes/pods/config/configmaps' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'config' ? '/kubernetes/pods/config/secrets' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "clusterScoped(tab === 'hpa' ? '/kubernetes/pods/autoscaling/hpa' : null, clusterId)"),
    ("ClusterControlPlane.tsx", "usePods(undefined, { includeStats: false, clusterId })"),
    ("PlatformObservability.tsx", "usePods(undefined, { includeStats: false, clusterId })"),
    ("AlertsTab.tsx", "qs.set('cluster_id', clusterId)"),
    ("GitOpsTab.tsx", "qs.set('cluster_id',    clusterId)"),
]


def test_every_cluster_scoped_call_site_forwards_the_selection():
    """
    Guards the wiring the hook-level test cannot see.

    This is deliberately a source-level check: it does not execute the
    components (there is no JS test runner in this repository). It fails if any
    cluster-scoped request stops forwarding the selector.
    """
    missing = []
    for filename, needle in _REQUIRED_WIRING:
        text = (DEVOPS_DIR / filename).read_text()
        if needle not in text:
            missing.append(f"{filename}: {needle}")
    assert not missing, "cluster scoping was dropped from:\n  " + "\n  ".join(missing)


def test_root_forwards_the_selection_to_the_cluster_aware_sections():
    """The selector's value must be handed down, not left in local state."""
    text = (DEVOPS_DIR / "index.tsx").read_text()
    for needle in (
        "const activeClusterId: string | undefined = selectedClusterId || undefined;",
        "clusterId: activeClusterId",                       # root pod summary tiles
        "<ClusterControlPlane showToast={showToast} clusterId={activeClusterId} />",
        "<PlatformObservability showToast={showToast} clusterId={activeClusterId} />",
        "clusterId={activeClusterId} />",                   # DeliveryGitOps
    ):
        assert needle in text, f"index.tsx no longer forwards the selection: {needle}"


def test_catalog_is_deliberately_not_cluster_scoped():
    """
    The selector must not touch sections with no cluster context.

    The Self-Service Catalog is a service registry — its rows have no cluster —
    so forwarding the selection there would filter on a column that does not
    exist. Same reasoning excludes pipelines (CI/CD objects) and the pod
    restart/delete/exec actions, which resolve their cluster from the pod row.
    """
    catalog = (DEVOPS_DIR / "CatalogTab.tsx").read_text()
    assert "cluster_id" not in catalog

    index = (DEVOPS_DIR / "index.tsx").read_text()
    assert re.search(r"<CatalogTab\s+showToast=\{showToast\}\s*/>", index), (
        "CatalogTab should receive no clusterId prop"
    )


def test_security_center_uses_the_parameter_the_endpoint_declares():
    """
    ``/kubernetes/pods/cluster/summary`` declares ``cluster_id`` only. The
    SecurityCenter selector sent ``?cluster=<id>``, which FastAPI ignores, so the
    summary silently showed tenant-wide data beside cluster-scoped panels.
    """
    text = (FRONTEND / "src" / "pages" / "SecurityCenter" / "sections"
            / "KubernetesSecurity.tsx").read_text()
    assert "`?cluster_id=${selectedCluster}`" in text
    assert "`?cluster=${selectedCluster}`" not in text
