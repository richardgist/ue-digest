#!/usr/bin/env python3
"""把一期 JSON 加入站点并重新生成。
用法: python3 add_issue.py path/to/issue.json [--force]
      cat issue.json | python3 add_issue.py - [--force]
同日期已存在时默认拒绝,加 --force 覆盖。校验失败不会写入任何文件。
"""
import json, sys, shutil
from pathlib import Path
import build


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
    if len(args) != 1:
        sys.exit(__doc__)
    raw = sys.stdin.read() if args[0] == "-" else Path(args[0]).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"[错误] 不是有效 JSON:{e}")
    errs = build.validate(data)
    if errs:
        sys.exit("[错误] 校验失败:\n  - " + "\n  - ".join(errs))
    dest = build.ISSUES_DIR / f'{data["date"]}.json'
    if dest.exists() and not force:
        sys.exit(f"[错误] {dest.name} 已存在;确认覆盖请加 --force")
    build.ISSUES_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {dest}")
    build.main()


if __name__ == "__main__":
    main()
