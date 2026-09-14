"""Inventory the resolved dependency closure and copy distributed notice files.

This is a technical inventory, NOT a claim of legal approval. Missing wheel
notices and corresponding-source obligations remain explicit release gates.
"""
from importlib import metadata
from pathlib import Path
import json
import re
from packaging.requirements import Requirement

root=Path(__file__).resolve().parents[1];output=root/"third_party_licenses";output.mkdir(exist_ok=True)
queue=[line.strip() for line in (root/"requirements.txt").read_text().splitlines() if line.strip() and not line.startswith("#")]
seen=set();report=[]
while queue:
    requirement=Requirement(queue.pop(0))
    if requirement.marker and not requirement.marker.evaluate():continue
    key=requirement.name.lower().replace("_","-")
    if key in seen:continue
    seen.add(key)
    dist=metadata.distribution(requirement.name)
    name=dist.metadata["Name"];version=dist.version
    folder=output/(name+"-"+version);folder.mkdir(exist_ok=True)
    copies=[]
    for file in dist.files or []:
        base=Path(str(file)).name.lower()
        if any(base.startswith(s) for s in ["license","copying","notice","copyright"]):
            source=Path(dist.locate_file(file))
            if source.is_file() and source.stat().st_size<4*1024**2:
                target=folder/re.sub(r"[^A-Za-z0-9._-]","_",str(file))
                target.write_bytes(source.read_bytes());copies.append(str(target.relative_to(root)))
    report.append({"name":name,"version":version,"license_metadata":dist.metadata.get("License-Expression") or dist.metadata.get("License") or "See upstream",
                   "homepage":dist.metadata.get("Home-page") or dist.metadata.get_all("Project-URL"),
                   "notices":copies,"notice_files_present":bool(copies)})
    queue.extend(dist.requires or [])
(output/"inventory.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"packages":len(report),"missing_notice_files":[r["name"] for r in report if not r["notices"]]},ensure_ascii=False))
