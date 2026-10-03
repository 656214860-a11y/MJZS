"""临时仓库/项目阶段探针：发现既有红灯立即停止，不接受真实项目路径。"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))


def run_probe():
    """只在自身创建的系统临时目录中操作；没有外部项目路径参数。"""
    from agent.core import save
    from asset_context import library_dir
    from stage_completion_service import completion_evidence
    import stage_parallel
    import storage_maintenance

    with tempfile.TemporaryDirectory(prefix="stage-gate-e2e-") as temporary:
        repo = Path(temporary) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "master", str(repo)],
                       capture_output=True, check=True, timeout=20)
        project = repo / "project"
        project.mkdir()
        stages = (("SG-01", "assets", "continuity"), ("SG-02", "continuity", "final"),
                  ("SG-03", "final", "keyframe"), ("SG-04", "keyframe", "previs"),
                  ("SG-05", "previs", "video"))
        result = {"empty": [], "findings": [], "not_executed": []}
        for gate_id, source, target in stages:
            entry = stage_parallel.evaluate(project, target)
            completed, _ = completion_evidence(project, source)
            result["empty"].append({"id": gate_id, "entry_ok": entry["ok"],
                                    "started": entry["started"], "completed": completed})

        base = library_dir(project)
        image = base / "assets/characters/CHAR_001.png"
        image.parent.mkdir(parents=True)
        original = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII=")
        image.write_bytes(original)
        manifest = base / "assets/资产清单/assets.json"
        save(manifest, {"CHAR_001": {"image": "assets/characters/CHAR_001.png",
                                    "locked": True, "character_anchor": "临时探针角色"}})
        result["asset_before"] = {"completed": completion_evidence(project, "assets")[0],
                                  "file_exists": image.is_file(), "bytes": image.stat().st_size}
        records = storage_maintenance.recycle_paths(project, [image], "临时项目端到端探针")
        if len(records) != 1:
            raise AssertionError("真实回收入口未产生一条恢复记录")
        recycled = project / records[0]["recycle_path"]
        try:
            result["deleted"] = {"file_exists": image.is_file(),
                                 "recycled_file_exists": recycled.is_file(),
                                 "completed": completion_evidence(project, "assets")[0],
                                 "gate_ok": stage_parallel.evaluate(project, "continuity")["ok"]}
        finally:
            # 即使发现门禁红灯，也先恢复探针文件；始终只在本次临时项目内。
            storage_maintenance.restore_latest_recycled_path(project, image)
        result["restored"] = {"same_bytes": image.read_bytes() == original,
                              "completed": completion_evidence(project, "assets")[0]}
        runtime_names = {"上次关闭清理.json", "full-safe-receipts.json", "selftest-incremental.json"}
        result["runtime_leaks"] = [str(path.relative_to(project)) for path in project.rglob("*")
                                   if path.name in runtime_names]
        if result["deleted"]["completed"] or result["deleted"]["gate_ok"]:
            result["findings"].append("SG-01：真实图片回收后，清单仍有路径时门禁/完成核验错误通过")
            result["not_executed"] = ["SG-02 成果构造", "SG-03 成果构造", "SG-04 成果构造", "SG-05 成果构造"]
        return result


def main():
    result = run_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["findings"]))


if __name__ == "__main__":
    raise SystemExit(main())
