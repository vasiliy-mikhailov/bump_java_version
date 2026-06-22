#!/usr/bin/env python3
"""Hand-edit (Phase 1): add the --add-exports compiler args that the build error named, to
maven-compiler-plugin. Counts as ONE edit (one patch hunk). Namespace-aware, idempotent.
  edit_pom_addexports.py <pom.xml> <export1> [export2 ...]   e.g. java.desktop/java.awt.peer
"""
import sys, xml.etree.ElementTree as ET
NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", NS)
def q(t): return f"{{{NS}}}{t}"
pom = sys.argv[1]; exports = sys.argv[2:]
tree = ET.parse(pom); root = tree.getroot()
target = None
for plugin in root.iter(q("plugin")):
    aid = plugin.find(q("artifactId"))
    if aid is not None and aid.text == "maven-compiler-plugin":
        target = plugin; break
if target is None:
    sys.stderr.write("NO maven-compiler-plugin declared\n"); sys.exit(1)
cfg = target.find(q("configuration")) or ET.SubElement(target, q("configuration"))
if target.find(q("configuration")) is None: target.append(cfg)
ca = cfg.find(q("compilerArgs"))
if ca is None: ca = ET.SubElement(cfg, q("compilerArgs"))
have = {a.text for a in ca.findall(q("arg"))}
for e in exports:
    val = f"--add-exports={e}=ALL-UNNAMED"
    if val not in have:
        ET.SubElement(ca, q("arg")).text = val
tree.write(pom, xml_declaration=True, encoding="UTF-8")
print("added --add-exports:", ", ".join(exports))
