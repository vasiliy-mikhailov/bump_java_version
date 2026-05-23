"""attempt_5: verify each historical commit in each lineage builds clean under
its corresponding JDK. Output: lineage_dataset.json with build_pass flags per
commit. Only repos with ALL listed commits buildable advance into the final
dataset.
"""
import json, os, subprocess, threading, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

HERE = "/home/vmihaylov/java_8_11_17_to_java_21"

def verify_one_commit(repo_url, sha, jv):
    """Return True if `git checkout sha` + mvn compile succeeds under JDK jv."""
    tmp = tempfile.mkdtemp(prefix="lv-")
    try:
        # clone
        r = subprocess.run(["git","clone","--filter=blob:none","--no-checkout",repo_url,f"{tmp}/src"],
                           capture_output=True, timeout=120)
        if r.returncode != 0: return False
        subprocess.run(["git","fetch","--depth","50","origin",sha], cwd=f"{tmp}/src",
                       capture_output=True, timeout=120)
        r = subprocess.run(["git","checkout","--detach",sha], cwd=f"{tmp}/src",
                           capture_output=True, timeout=30)
        if r.returncode != 0: return False
        # find project root with pom.xml
        root = f"{tmp}/src"
        if not os.path.exists(f"{root}/pom.xml"):
            for r2,_,f in os.walk(root):
                if "pom.xml" in f: root = r2; break
        if not os.path.exists(f"{root}/pom.xml"): return False
        # docker compile
        jdk_path = f"/opt/jdk/{jv}"
        cmd = (
            "mvn -B -q -ntp -fae -Denforcer.skip=true -DskipTests "
            "-Dlombok.version=1.18.36 -Dmaven.javadoc.skip=true -Dcheckstyle.skip=true "
            "-Dspotbugs.skip=true -Dspring-javaformat.skip=true -Dformat.skip=true compile"
        )
        home = os.environ["HOME"]
        docker_cmd = ["docker","run","--rm","--cpus","2.5","--memory","6g",
                      "--entrypoint","/bin/bash",
                      "-v", f"{root}:/work",
                      "-v", f"{home}/.m2-fitness:/root/.m2",
                      "-e", f"JAVA_HOME={jdk_path}",
                      "-e", f"PATH={jdk_path}/bin:/opt/maven/bin:/usr/local/bin:/usr/bin:/bin",
                      "-w","/work","j21-fitness:latest","-c", cmd]
        try:
            r = subprocess.run(docker_cmd, capture_output=True, timeout=600)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    except Exception:
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    cands_path = f"{HERE}/attempt_5/lineage_candidates.json"
    if not os.path.exists(cands_path):
        print(f"lineage_candidates.json not found at {cands_path}; run discovery first")
        return
    lineages = json.load(open(cands_path))
    print(f"lineage candidates: {len(lineages)}", flush=True)

    # Filter to those that reached J21 (we know the migration was achievable)
    j21_lineages = [l for l in lineages if l["newest_java_version"] == 21]
    print(f"  ...reached J21: {len(j21_lineages)}", flush=True)

    sem = threading.BoundedSemaphore(8)
    verified = []
    lock = threading.Lock()
    done = [0]

    def worker(lin):
        repo_url = f"https://github.com/{lin['repo_full_name']}.git"
        per_commit = []
        ok = True
        for step in lin["lineage"]:
            with sem:
                bp = verify_one_commit(repo_url, step["commit_sha"], step["java_version"])
            per_commit.append({"java_version": step["java_version"],
                               "commit_sha": step["commit_sha"],
                               "build_pass": bp})
            if not bp:
                ok = False
        with lock:
            done[0] += 1
            entry = {**lin, "verified_lineage": per_commit, "all_pass": ok}
            verified.append(entry)
            if done[0] % 10 == 0:
                full_pass = sum(1 for e in verified if e["all_pass"])
                print(f"  verified {done[0]}/{len(j21_lineages)}, full-pass={full_pass}", flush=True)

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(worker, j21_lineages))

    out = f"{HERE}/attempt_5/lineage_verified.json"
    json.dump(verified, open(out, "w"), indent=2)
    full = [e for e in verified if e["all_pass"]]
    print(f"\nfull-pass lineages: {len(full)}")
    json.dump(full, open(f"{HERE}/attempt_5/lineage_dataset.json", "w"), indent=2)
    print(f"saved final dataset to {HERE}/attempt_5/lineage_dataset.json")


if __name__ == "__main__":
    main()
