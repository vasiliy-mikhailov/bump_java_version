import sys, os, struct
root = sys.argv[1]
MAIN=("/target/classes/","/build/classes/java/main/","/build/classes/kotlin/main/","/build/classes/groovy/main/","/build/classes/scala/main/","/out/production/")
TEST=("/target/test-classes/","/build/classes/java/test/","/build/classes/kotlin/test/","/build/classes/groovy/test/","/out/test/")
def major(p):
    try:
        with open(p,"rb") as f: h=f.read(8)
        if len(h)<8 or h[:4]!=b"\xca\xfe\xba\xbe": return None
        return struct.unpack(">H",h[6:8])[0]
    except Exception: return None
mains=[]; tests=[]
for dp,_,fn in os.walk(root):
    pp=dp.replace("\\","/")+"/"
    if "/META-INF/versions/" in pp or "/buildSrc/" in pp or "/build-logic/" in pp: continue
    for f in fn:
        if not f.endswith(".class") or f=="module-info.class": continue
        fp=os.path.join(dp,f)
        if any(h in pp for h in MAIN): mains.append(fp)
        elif any(h in pp for h in TEST): tests.append(fp)
pool = mains or tests
majs=[m for m in (major(x) for x in pool) if m]
print("pool=%s mains=%d tests=%d majors=%s -> feature=%s" % (
    "main" if mains else "test", len(mains), len(tests),
    sorted(set(majs)), (min(majs)-44 if majs else -1)))
