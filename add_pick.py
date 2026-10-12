#!/usr/bin/env python3
"""把一天的「每日精选」JSON 加入站点并重新生成。
用法: python3 add_pick.py path/to/pick.json [--force] [--allow-duplicates]
      cat pick.json | python3 add_pick.py - [--force]
  --force             同日期已存在时覆盖(默认拒绝)
  --allow-duplicates  URL 与往日重复时只警告、不拒绝(默认拒绝,同日自身重复始终拒绝)
校验失败不会写入任何文件。写入后自动重建整站(含 picks/)。
"""
import json, sys
from pathlib import Path
import build

FLAGS = {"--force", "--allow-duplicates"}


def main():
    args = [a for a in sys.argv[1:] if a not in FLAGS]
    force = "--force" in sys.argv[1:]
    allow_dup = "--allow-duplicates" in sys.argv[1:]
    if len(args) != 1:
        sys.exit(__doc__)
    raw = sys.stdin.read() if args[0] == "-" else Path(args[0]).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"[错误] 不是有效 JSON:{e}")
    if not isinstance(data, dict):
        sys.exit("[错误] 顶层必须是对象 {date, items}")
    errs = build.validate_picks(data)
    if errs:
        sys.exit("[错误] 校验失败:\n  - " + "\n  - ".join(errs))
    dest = build.PICKS_DIR / f'{data["date"]}.json'
    if dest.exists() and not force:
        sys.exit(f"[错误] {dest.name} 已存在;确认覆盖请加 --force")
    dups = build.find_duplicates(data, build.load_picks())
    if dups:
        lines = [f"《{t}》{u} 已在 {d} 收录" for t, u, d in dups]
        if not allow_dup:
            sys.exit("[错误] 与往日重复,未写入(换一条,或确认要保留请加 --allow-duplicates):\n  - " + "\n  - ".join(lines))
        print("[警告] 与往日重复(已按 --allow-duplicates 放行):\n  - " + "\n  - ".join(lines))
    build.PICKS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {dest}")
    build.main()


if __name__ == "__main__":
    main()
