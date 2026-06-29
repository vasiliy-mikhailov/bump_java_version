#!/usr/bin/env python3
"""TDD regression tests for scoring/anti-cheat/router bugs found in the 2026-06-28 pipeline review.
Stdlib only (runs in python:3-slim, no pytest). Run: `python3 test_pipeline_bugs.py` -> exit 0 if all green.
Each test name cites the review finding id. Bugs are reward-corrupting (false PASS/FAIL or cheat-hole),
so these stay as the regression net (P17 spirit) against re-introduction.
"""
import os, sys, struct, subprocess, tempfile, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # module body is guarded by __main__, so import is side-effect-free

CHECK  = os.path.join(HERE, "check_program.py")
DETECT = os.path.join(HERE, "..", "rung2", "detect_java.py")

def _classfile(path, major):
    """minimal .class: CAFEBABE + minor(0) + major."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(b"\xca\xfe\xba\xbe\x00\x00" + struct.pack(">H", major))

def _run(script, *args):
    p = subprocess.run([sys.executable, script, *args], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)

# ---------- score.py: conservation matching (score-2) ----------
def test_lost_numbered_tests_stay_distinct():
    # testCase3 was DROPPED; testCase9 is new. The bare \d+ digit-strip used to bucket all of
    # testCase{1,2,3,9} -> "testcase", letting testCase9 absorb the lost testCase3 -> LOST=0 (false PASS).
    pre  = ["com.A#testCase1", "com.A#testCase2", "com.A#testCase3"]
    post = ["com.A#testCase1", "com.A#testCase2", "com.A#testCase9"]
    assert score.lost(pre, post) == 1, f"expected 1 lost (testCase3), got {score.lost(pre, post)}"

def test_lost_uuid_still_normalized():
    # regression guard: genuinely-volatile UUID/hex suffixes must STILL match after the fix.
    pre  = ["com.A#run_550e8400-e29b-41d4-a716-446655440000"]
    post = ["com.A#run_111e2222-e29b-41d4-a716-446655449999"]
    assert score.lost(pre, post) == 0, "volatile UUID test name should still be matched as conserved"

# ---------- score.py: effective target (score-3 + score-4) ----------
def test_efftarget_ignores_test_only_classes():
    # no MAIN classes, only TEST classes -> must be -1 (cannot confirm the bump from test bytecode),
    # NOT the test classes' major. `pool = mains or tests` used to read the target from test bytecode.
    with tempfile.TemporaryDirectory() as d:
        _classfile(os.path.join(d, "target/test-classes/Bar.class"), 65)  # 65 = Java 21
        assert score.efftarget(d) == -1, f"test-only workspace must yield -1, got {score.efftarget(d)}"

def test_efftarget_reads_main_ignores_test():
    # regression guard: with MAIN present, target comes from MAIN, not TEST.
    with tempfile.TemporaryDirectory() as d:
        _classfile(os.path.join(d, "target/classes/Foo.class"), 61)        # 61 = Java 17
        _classfile(os.path.join(d, "target/test-classes/Bar.class"), 65)   # 65 = Java 21
        assert score.efftarget(d) == 17, f"main bytecode is 17, got {score.efftarget(d)}"

def test_efftarget_reads_kotlin_multiplatform_jvm_main():
    # KMP puts JVM bytecode at build/classes/kotlin/<target>/main/, not single-platform kotlin/main/ ->
    # efftarget must still read it, else a real KMP PASS is a false FAIL_no_main_bytecode (rr_8_72 XenoECS).
    with tempfile.TemporaryDirectory() as d:
        _classfile(os.path.join(d, "build/classes/kotlin/jvm/main/Foo.class"), 55)   # 55 = Java 11
        assert score.efftarget(d) == 11, f"KMP jvm/main bytecode must be read, got {score.efftarget(d)}"

def test_efftarget_kmp_custom_target_name_and_test_split():
    # robust to a custom JVM target name (not just 'jvm'); KMP test classes must NOT count as the main target.
    with tempfile.TemporaryDirectory() as d:
        _classfile(os.path.join(d, "build/classes/kotlin/desktop/main/Foo.class"), 61)  # 61 = Java 17 (main)
        _classfile(os.path.join(d, "build/classes/kotlin/desktop/test/Bar.class"), 65)  # 65 = Java 21 (test)
        assert score.efftarget(d) == 17, f"must read KMP main (17), not test (21), got {score.efftarget(d)}"

def test_verdict_no_main_bytecode_is_not_pass():
    # build OK + tests conserved + ETGT == -1 (no inspectable main classes) used to fall through to PASS,
    # never verifying the target -> soft-pin false PASS. Must NOT be PASS.
    v = score.decide(pre=["com.A#t"], comprc=0, LOST=0, ETGT=-1, to=17)
    assert v != "PASS", f"ETGT==-1 must not be PASS, got {v}"

def test_verdict_real_pass_still_passes():
    # regression guard: a genuine bump (built, conserved, target==to) still PASSes.
    assert score.decide(pre=["com.A#t"], comprc=0, LOST=0, ETGT=17, to=17) == "PASS"

# ---------- check_program.py: anti-cheat (anticheat-1, anticheat-4) ----------
def _rewrite_yml(body):
    f = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False)
    f.write("type: specs.openrewrite.org/v1beta/recipe\nname: com.example.X\nrecipeList:\n" + body)
    f.close()
    return f.name

def test_flowstyle_parametric_recipe_is_counted():
    # a model-chosen parametric recipe written in YAML FLOW style ({...}) used to be invisible to the
    # $-anchored recipe regex -> PARAMETRIC=0 -> reward stayed 1.0 (cheat-hole). Must count as parametric.
    yml = _rewrite_yml(
        "  - org.openrewrite.java.migrate.UpgradeToJava17\n"
        "  - org.openrewrite.java.ChangeMethodName: {methodPattern: 'a.b foo()', newMethodName: bar}\n")
    rc, out = _run(CHECK, yml, "x", "17")
    os.unlink(yml)
    assert "PARAMETRIC=1" in out, f"flow-style parametric recipe must count (expect PARAMETRIC=1), got: {out.strip()}"

def test_inline_comment_on_free_intent_value_not_violation():
    # `version: 17 # comment` used to capture the comment into the value -> '17 # comment' != '17'
    # -> false VIOLATION / under-reward. The real YAML value is 17.
    yml = _rewrite_yml(
        "  - org.openrewrite.java.migrate.UpgradeJavaVersion:\n"
        "      version: 17 # bump to the target LTS\n")
    rc, out = _run(CHECK, yml, "x", "17")
    os.unlink(yml)
    assert out.startswith("OK") and rc == 0, f"value-correct UpgradeJavaVersion must be OK, got: {out.strip()}"

# ---------- check_program.py: free-intent table must match the per-hop SKILL recommendations ----------
# (skill bug-hunt 2026-06-28: the SKILLs recommend floors the table didn't credit -> penalty / FAIL_CHEAT)
def _udv(group, artifact, ver):
    return ("  - org.openrewrite.java.dependencies.UpgradeDependencyVersion:\n"
            f"      groupId: {group}\n      artifactId: {artifact}\n      newVersion: {ver}\n")

def test_free_gradle_wrapper_6_9_at_8to11():
    # the 8->11 skill recommends wrapper 6.9 (7.x removed compile/testCompile); must be FREE at TO=11,
    # not a VIOLATION/FAIL_CHEAT (was pinned to 7.6).
    yml = _rewrite_yml('  - org.openrewrite.gradle.UpdateGradleWrapper:\n      version: "6.9"\n')
    rc, out = _run(CHECK, yml, "x", "11"); os.unlink(yml)
    assert out.startswith("OK") and "PARAMETRIC=0" in out, f"wrapper 6.9 must be free at 8->11, got: {out.strip()}"

def test_free_lombok_floor_at_17_and_21():
    # AGENTS.md lists Lombok as a free hop-fixed floor; the 11->17 and 17->21 skills floor it to 1.18.30.
    for to in ("17", "21"):
        yml = _rewrite_yml(_udv("org.projectlombok", "lombok", "1.18.30"))
        rc, out = _run(CHECK, yml, "x", to); os.unlink(yml)
        assert "PARAMETRIC=0" in out, f"lombok 1.18.30 must be free at TO={to}, got: {out.strip()}"

def test_free_mockito_floor_at_21():
    # the 17->21 skill floors Mockito for JDK 21; the credited exact value is 5.18.0.
    yml = _rewrite_yml(_udv("org.mockito", "mockito-core", "5.18.0"))
    rc, out = _run(CHECK, yml, "x", "21"); os.unlink(yml)
    assert "PARAMETRIC=0" in out, f"mockito 5.18.0 must be free at TO=21, got: {out.strip()}"

# ---------- detect_java.py: router (router-1, router-7) ----------
def _ws(files):
    d = tempfile.mkdtemp()
    for rel, content in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(content)
    return d

def test_javadoc_source_tag_not_treated_as_compiler_target():
    # real target 17 (compiler properties); a maven-javadoc-plugin <source>8</source> used to pollute the
    # source list -> detected=8 (wrong hop) + multi_target=True (false NOT_A_BUMP).
    ws = _ws({"pom.xml":
        "<project><properties>"
        "<maven.compiler.source>17</maven.compiler.source>"
        "<maven.compiler.target>17</maven.compiler.target>"
        "</properties><build><plugins>"
        "<plugin><artifactId>maven-javadoc-plugin</artifactId>"
        "<configuration><source>8</source></configuration></plugin>"
        "</plugins></build></project>"})
    rc, out = _run(DETECT, ws)
    j = json.loads(out.strip().splitlines()[-1])
    assert j["detected"] == 17 and j["multi_target"] is False, f"javadoc <source> leaked into target: {j}"

def test_gradleplugin_no_space_detected_as_plugin():
    # `gradlePlugin{` (no space) used to be missed by the redundant `"gradlePlugin {" in t` re-test
    # -> is_gradle_plugin=False -> a real Gradle plugin gets its bytecode bumped (should be NOT_A_BUMP).
    ws = _ws({"build.gradle":
        "plugins { id 'java' }\n"
        "sourceCompatibility = JavaVersion.VERSION_11\n"
        "gradlePlugin{\n  plugins { create('x') { id = 'y' } }\n}\n"})
    rc, out = _run(DETECT, ws)
    j = json.loads(out.strip().splitlines()[-1])
    assert j["is_gradle_plugin"] is True, f"gradlePlugin{{ (no space) must be detected as a plugin: {j}"

# ---------- KNOWN LIMITATION (xfail) — score-1 class-blind level-2 match ----------
# The review's lead-ruling: a naive class-aware key re-introduces false FAILs on legitimate class renames,
# so this needs design (evidence-based rename detection), NOT a one-liner. Documented here so the next TDD
# cycle has a red target; it does not gate the suite.
def xfail_score1_class_blind_match():
    pre  = ["com.A#foo"]; post = ["com.B#foo"]   # com.A#foo deleted, absorbed by unrelated com.B#foo
    return score.lost(pre, post)  # IDEALLY 1; currently 0 (known limitation)

def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = []
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed.append(t.__name__); print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed.append(t.__name__); print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    xf = xfail_score1_class_blind_match()
    print(f"XFAIL score1_class_blind_match: lost={xf} (ideal 1; known limitation, needs design)")
    print(f"\n{len(tests)-len(failed)}/{len(tests)} passed" + (f"; FAILED: {failed}" if failed else ""))
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
