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
    from continuity_ledger import build as build_ledger
    from continuity_ledger import write as write_ledger
    from shot_batches import assign
    from stage_completion_service import completion_evidence
    from project_context_factory import project_context
    from storyboard_paths import media_root
    import stage_parallel
    import stage_layout
    import storage_maintenance
    import white_model_service

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
        result = {"empty": [], "findings": [], "executed": []}
        for gate_id, source, target in stages:
            entry = stage_parallel.evaluate(project, target)
            completed, _ = completion_evidence(project, source)
            result["empty"].append({"id": gate_id, "entry_ok": entry["ok"],
                                    "started": entry["started"], "completed": completed})

        def verify_gate(gate_id, source, target):
            entry = stage_parallel.evaluate(project, target)
            completed, _ = completion_evidence(project, source)
            row = {"completed": completed, "gate_ok": entry["ok"],
                   "gate_started": entry["started"]}
            result["stages"][gate_id] = row
            result["executed"].append(gate_id)
            if not all(row.values()):
                result["findings"].append(
                    f"{gate_id}：真实成果已构造但完成证据或下一阶段门禁未通过：{row}")

        # 这份真实分镜同时提供 SG-02 台账、SG-03 批次与 SG-04 首帧的唯一来源。
        stage_layout.ensure(project)
        source = project / "storyboard" / "分镜文档" / "episode.json"
        source.parent.mkdir(parents=True)
        shots = list(assign([{
            "id": "SH001", "title": "临时探针镜头", "duration": 3,
            "characters": ["CHAR_001"], "location": "LOC_001",
            "frame": "frames/SH001.png", "video_prompt": "角色追逐后接住道具",
            "action_complexity": "complex", "dialogue": [],
        }]))
        save(source, {"episode_id": "EP001", "title": "临时探针", "shots": shots})
        relative_source = source.relative_to(project).as_posix()
        save(project / "ui_settings.json", {"adopted_storyboards": [relative_source],
                                             "frame_json": relative_source})
        result["stages"] = {}

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
        verify_gate("SG-01", "assets", "continuity")

        ledger = build_ledger(shots, {
            "CHAR_001": {"character_anchor": "临时探针角色", "state_variants": []},
            "LOC_001": {"lighting_direction": "左侧柔光", "spatial_anchors": []},
        })
        if not ledger["summary"]["ok"]:
            result["findings"].append(f"SG-02：临时连贯性台账无法自洽：{ledger['summary']}")
        write_ledger(project, ledger)
        verify_gate("SG-02", "continuity", "final")

        verify_gate("SG-03", "final", "keyframe")

        frame = media_root(source) / "frames" / "SH001.png"
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame.write_bytes(original)
        verify_gate("SG-04", "keyframe", "previs")

        # 白模服务的工作区也限定在临时仓库；复用真实记录读取与预演路由判据。
        workspace = repo / "previs-workspace"
        original_workspace = white_model_service.workspace
        white_model_service.workspace = lambda: workspace
        white_model_service._BASE_CACHE.clear()
        white_model_service._DIR_CACHE.clear()
        try:
            shot_dir = white_model_service.shot_directory(project_context(project), "SH001")
            preview = shot_dir / "preview.mp4"
            preview.parent.mkdir(parents=True, exist_ok=True)
            preview.write_bytes(b"stage-gate-e2e-preview")
            white_model_service.write_record(
                shot_dir, {"shot_id": "SH001", "preview": str(preview)}, publish=save)
            verify_gate("SG-05", "previs", "video")
        finally:
            white_model_service.workspace = original_workspace
            white_model_service._BASE_CACHE.clear()
            white_model_service._DIR_CACHE.clear()
        runtime_names = {"上次关闭清理.json", "full-safe-receipts.json", "selftest-incremental.json"}
        result["runtime_leaks"] = [str(path.relative_to(project)) for path in project.rglob("*")
                                   if path.name in runtime_names]
        if result["deleted"]["completed"] or result["deleted"]["gate_ok"]:
            result["findings"].append("SG-01：真实图片回收后，清单仍有路径时门禁/完成核验错误通过")
        return result


def main():
    result = run_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["findings"]))


if __name__ == "__main__":
    raise SystemExit(main())
