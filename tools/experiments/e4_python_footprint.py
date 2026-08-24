"""E4: How much RAM does the Python agent stack cost before any query runs?

E3 showed the data layer needs ~183 MB peak. Render free gives 512 MB total.
This measures what the imports alone consume, to see what's left.
"""
import resource, sys, importlib, time


def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3


base = rss_mb()
print(f"baseline interpreter: {base:.0f} MB")

MODS = [
    "duckdb",
    "fastapi",
    "uvicorn",
    "pydantic",
    "langgraph.graph",
    "langchain_core.tools",
    "langchain_groq",
    "langchain_tavily",
    "scipy.stats",
    "statsmodels.stats.proportion",
    "pandas",
]

prev = base
for m in MODS:
    t = time.time()
    try:
        importlib.import_module(m)
        now = rss_mb()
        print(f"  +{m:34s} {now-prev:6.0f} MB  (total {now:5.0f} MB, {(time.time()-t)*1000:5.0f} ms)")
        prev = now
    except ImportError as e:
        print(f"  ?{m:34s} NOT INSTALLED ({str(e)[:40]})")

print(f"\nTOTAL after imports: {rss_mb():.0f} MB")
print(f"Budget check vs Render free (512 MB): data layer needs ~183 MB peak")
print(f"  -> imports {rss_mb():.0f} + data 183 = {rss_mb()+183:.0f} MB")
